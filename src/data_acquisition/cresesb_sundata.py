"""Scraper dinâmico (Selenium) do SunData, do CRESESB/CEPEL.

O SunData (https://cresesb.cepel.br/index.php?section=sundata) devolve a irradiação
solar diária média de cada mês (base de longo prazo do Atlas Brasileiro de Energia
Solar, 2ª edição) para as estações mais próximas de uma coordenada. Além do plano
horizontal, ele calcula a irradiação no plano inclinado (ângulo igual à latitude, maior
média anual e maior mínimo mensal), que é como os painéis são instalados de fato.

Por que Selenium: os dados não estão em uma URL que dê para baixar direto. É preciso
preencher um formulário. O botão "Buscar" é um <button type="button"> que dispara
JavaScript (js/rer_init.js): ele valida a coordenada, converte e preenche campos ocultos
(`latitude`/`longitude`) e só então envia o POST. O Selenium abre um Chrome sem
interface, preenche o formulário como um usuário, clica em "Buscar", espera as
tabelas de resultado aparecerem e entrega o HTML para o Beautiful Soup extrair os
números.

O site não tem robots.txt (404); mesmo assim, há pausa entre as consultas.

Uso (na raiz do projeto):
    python -m src.data_acquisition.cresesb_sundata              # 10 capitais
    python -m src.data_acquisition.cresesb_sundata --mostrar    # Chrome visível
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from src.locations import CAPITAIS

URL = "https://cresesb.cepel.br/index.php?section=sundata"
CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "cresesb_sundata_capitais.csv"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
PAUSA_ENTRE_CONSULTAS_S = 2.0


def criar_driver(mostrar: bool = False) -> webdriver.Chrome:
    """Chrome headless; o Selenium Manager baixa o chromedriver compatível sozinho."""
    opcoes = webdriver.ChromeOptions()
    if not mostrar:
        opcoes.add_argument("--headless=new")
    opcoes.add_argument("--window-size=1366,900")
    opcoes.add_experimental_option("prefs", {"intl.accept_languages": "pt-BR,pt"})
    return webdriver.Chrome(options=opcoes)


def consultar(driver: webdriver.Chrome, lat: float, lon: float) -> str:
    """Preenche o formulário de coordenadas, clica em Buscar e devolve o HTML do resultado."""
    driver.get(URL)
    espera = WebDriverWait(driver, 30)
    espera.until(EC.element_to_be_clickable((By.ID, "latitude_dec")))
    # o formulário pede valores absolutos + hemisfério (a longitude é sempre Oeste)
    driver.find_element(By.ID, "latitude_dec").send_keys(f"{abs(lat):.4f}")
    Select(driver.find_element(By.NAME, "hemi_lat")).select_by_value("0" if lat < 0 else "1")
    driver.find_element(By.ID, "longitude_dec").send_keys(f"{abs(lon):.4f}")
    driver.find_element(By.ID, "submit_btn").click()
    espera.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#data_output table.tb_sundata")))
    return driver.page_source


def _numero(texto: str) -> float:
    """'22,901° S' -> 22.901 ; '6,18' -> 6.18 (formato brasileiro do site)."""
    return float(re.sub(r"[^\d,.-]", "", texto).replace(",", "."))


def _linhas(tabela) -> list[list[str]]:
    """Linhas de dados (ignora os dois cabeçalhos) como listas de textos das células."""
    linhas = [[c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])] for tr in tabela.find_all("tr")]
    return [lin for lin in linhas[2:] if len(lin) > 10]


def parse_resultado(html: str) -> pd.DataFrame:
    """Extrai, para cada estação próxima, a irradiação mensal em cada plano de inclinação.

    A primeira tabela (#tb_sundata) lista as estações (até 3, da mais próxima para a mais
    distante); as tabelas seguintes (.tb_sundata), na mesma ordem, trazem os planos.
    """
    saida = BeautifulSoup(html, "lxml").select_one("#data_output")
    estacoes = _linhas(saida.select_one("table#tb_sundata"))
    planos_por_estacao = [_linhas(t) for t in saida.select("table.tb_sundata")]
    registros = []
    for ordem, (est, planos) in enumerate(zip(estacoes, planos_por_estacao), start=1):
        # est: ['', estação, município, UF, país, lat, lon, distância, jan..dez, média, delta]
        _, estacao, municipio, uf, pais, lat_txt, lon_txt, dist = est[:8]
        for plano in planos:
            # plano: ['', nome do ângulo, '23° N', jan..dez, média, delta]
            valores = [_numero(v) for v in plano[3:17]]
            registros.append(
                {
                    "ordem_proximidade": ordem,
                    "estacao": estacao,
                    "municipio": municipio,
                    "uf": uf,
                    "pais": pais,
                    "lat_estacao": -_numero(lat_txt) if "S" in lat_txt else _numero(lat_txt),
                    "lon_estacao": -_numero(lon_txt),
                    "distancia_km": _numero(dist),
                    "plano": plano[1],
                    "inclinacao_graus": int(_numero(plano[2])),
                    **dict(zip(MESES, valores[:12])),
                    "media_anual": valores[12],
                    "delta": valores[13],
                }
            )
    return pd.DataFrame(registros)


def scrape(mostrar: bool = False) -> pd.DataFrame:
    driver = criar_driver(mostrar)
    frames = []
    try:
        for i, (cidade, (lat, lon)) in enumerate(CAPITAIS.items(), start=1):
            if i > 1:
                time.sleep(PAUSA_ENTRE_CONSULTAS_S)
            df = parse_resultado(consultar(driver, lat, lon))
            frames.append(df.assign(cidade=cidade, latitude=lat, longitude=lon))
            print(f"[{i}/{len(CAPITAIS)}] {cidade}: {df['estacao'].nunique()} estações, {len(df)} linhas")
    finally:
        driver.quit()
    df = pd.concat(frames, ignore_index=True)
    # estação usada no app: a mais próxima em terra (com UF); se não houver, a mais próxima
    em_terra = df[df["uf"] != ""].groupby("cidade")["ordem_proximidade"].min()
    escolhida = df["cidade"].map(em_terra).fillna(1)
    df["estacao_referencia"] = df["ordem_proximidade"] == escolhida
    colunas = ["cidade", "latitude", "longitude", *[c for c in df.columns if c not in ("cidade", "latitude", "longitude")]]
    return df[colunas]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mostrar", action="store_true", help="abre o Chrome visível (sem headless)")
    args = parser.parse_args()
    df = scrape(args.mostrar)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False)
    print(f"{len(df)} linhas salvas em {CSV_PATH}")
