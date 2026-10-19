"""Testes dos parsers de coleta (HTML salvo em tests/fixtures) e do processamento."""

from pathlib import Path

import pandas as pd
import pytest
from bs4 import BeautifulSoup

from src.data_acquisition import canalsolar_scraper, cresesb_sundata
from src.data_processing import climate, llm_prep, text

FIXTURES = Path(__file__).parent / "fixtures"


# --- TP2 -----------------------------------------------------------------
def test_estimar_geracao():
    assert climate.estimar_geracao(5.0, 4.0, 0.8) == pytest.approx(16.0)


def test_upload_valido_e_cidade_padrao():
    csv = b"date,ALLSKY_SFC_SW_DWN\n2026-01-01,5.5\n2026-01-02,6.1\n"
    df = climate.parse_uploaded_csv(csv, "meu_telhado.csv")
    assert list(df.columns) == climate.COLUNAS_MODELO
    assert df["cidade"].iloc[0] == "Upload: meu_telhado"
    assert len(df) == 2


@pytest.mark.parametrize(
    "csv",
    [b"foo,bar\n1,2\n", b"date,ALLSKY_SFC_SW_DWN\nxx,yy\n", b"date,ALLSKY_SFC_SW_DWN\n2026-01-01,abc\n"],
)
def test_upload_invalido(csv):
    with pytest.raises(ValueError):
        climate.parse_uploaded_csv(csv, "x.csv")


def test_tokenizar_remove_stopwords():
    assert text.tokenizar("A energia solar para o Brasil") == ["energia", "solar", "brasil"]


def test_noticias_carregam_das_duas_fontes():
    n = text.carregar_noticias()
    assert set(n["fonte"]) == {"ABSOLAR", "Canal Solar"}
    assert n["data"].notna().all()


# --- TP3: Selenium (CRESESB) e Beautiful Soup (Canal Solar) ----------------
def test_parse_sundata():
    df = cresesb_sundata.parse_resultado((FIXTURES / "sundata_rio.html").read_text())
    assert set(df["plano"]) == {"Plano Horizontal", "Ângulo igual a latitude", "Maior média anual", "Maior mínimo mensal"}
    rio = df[(df["estacao"] == "Rio de Janeiro") & (df["plano"] == "Plano Horizontal")].iloc[0]
    assert rio["uf"] == "RJ"
    assert rio["lat_estacao"] == pytest.approx(-22.901)
    assert rio["jan"] == pytest.approx(6.04) and rio["media_anual"] == pytest.approx(4.73)
    assert (df["ordem_proximidade"].diff().fillna(0) >= 0).all()  # na ordem de proximidade


def test_parse_materia_canal_solar():
    soup = BeautifulSoup((FIXTURES / "canalsolar_materia.html").read_text(), "lxml")
    materia = canalsolar_scraper.parse_article(soup)
    assert materia["data"] == "2026-09-17"
    assert "aneel" in materia["tags"].split(";")
    assert "reajuste" in materia["texto"] and "Foto:" not in materia["texto"]
    assert len(materia["texto"].split()) > 150


def test_acumular_nao_duplica_e_preserva_texto(tmp_path):
    csv = tmp_path / "noticias.csv"
    antiga = pd.DataFrame([{"titulo": "A", "url": "u1", "texto": "texto completo", "data": "2026-09-01", "coletado_em": "2026-09-01"}])
    antiga.reindex(columns=canalsolar_scraper.COLUNAS).to_csv(csv, index=False)
    novas = pd.DataFrame([{"titulo": "A", "url": "u1", "coletado_em": "2026-10-01"}, {"titulo": "B", "url": "u2", "coletado_em": "2026-10-01"}])
    df = canalsolar_scraper.acumular(novas, csv)
    assert sorted(df["url"]) == ["u1", "u2"]
    assert df.set_index("url").at["u1", "texto"] == "texto completo"


def test_geracao_mensal_soma_os_dias_do_ano():
    df = climate.geracao_mensal([5.0] * 12, potencia_kwp=1, desempenho=1, tarifa=2)
    assert df["geracao_kwh"].sum() == pytest.approx(5 * 365)
    assert df["economia_rs"].sum() == pytest.approx(2 * 5 * 365)


# --- TP3: preparação para LLM ---------------------------------------------
def test_dividir_em_trechos_com_sobreposicao():
    palavras = [f"p{i}" for i in range(500)]
    trechos = llm_prep.dividir_em_trechos(" ".join(palavras), max_palavras=200, sobreposicao=50)
    assert all(len(t.split()) <= 200 for t in trechos)
    assert trechos[1].split()[0] == "p150"  # começa 50 palavras antes do fim do anterior
    assert trechos[-1].split()[-1] == "p499"  # nada se perde no fim


def test_buscar_prioriza_trecho_relevante():
    corpus = pd.DataFrame(
        {
            "titulo": ["Baterias", "Tarifas"],
            "texto": ["leilão de baterias e armazenamento", "reajuste das tarifas de energia"],
        }
    )
    resultado = llm_prep.buscar(corpus, "Como funciona o leilão de baterias?", k=2)
    assert list(resultado["titulo"]) == ["Baterias"]


def test_corpus_tem_noticias_e_fichas():
    from src import repositorio

    corpus = repositorio.carregar_corpus_llm()
    assert set(corpus["tipo"]) == {"noticia", "ficha_local"}
    assert corpus["n_palavras"].max() <= llm_prep.MAX_PALAVRAS + 30  # título + trecho
    assert corpus["id"].is_unique
