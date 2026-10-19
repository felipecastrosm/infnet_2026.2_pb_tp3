"""Acesso aos dados do projeto (arquivos em data/), usado pela API FastAPI.

Centraliza onde cada base está e como é carregada, para que a API (e os testes) leiam
sempre do mesmo lugar. O app Streamlit não lê estes arquivos direto: ele consome a API
(ver src/api_client.py).
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from src.data_processing import climate, text

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"


def caminho_medicoes() -> Path:
    """CSV onde a API guarda as medições enviadas por usuários (POST /medicoes).

    Pode ser trocado pela variável de ambiente SOLAR_MEDICOES_CSV (usado nos testes).
    """
    return Path(os.environ.get("SOLAR_MEDICOES_CSV", PROCESSED_DIR / "medicoes_usuarios.csv"))


def carregar_clima_base() -> pd.DataFrame:
    """Série diária da NASA POWER para as capitais (coletada por nasa_power_client.py)."""
    return pd.read_csv(RAW_DIR / "nasa_power_capitais.csv", parse_dates=["date"])


def carregar_medicoes() -> pd.DataFrame:
    caminho = caminho_medicoes()
    if not caminho.exists():
        return pd.DataFrame(columns=[*climate.COLUNAS_MODELO, "origem"]).astype({"date": "datetime64[ns]"})
    return pd.read_csv(caminho, parse_dates=["date"])


def salvar_medicoes(novas: pd.DataFrame) -> int:
    """Acrescenta medições; se já houver o mesmo local e data, a nova substitui a antiga."""
    novas = novas.assign(origem="usuario")[[*climate.COLUNAS_MODELO, "origem"]]
    todas = pd.concat([carregar_medicoes(), novas], ignore_index=True)
    todas = todas.drop_duplicates(["cidade", "date"], keep="last").sort_values(["cidade", "date"])
    caminho = caminho_medicoes()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    todas.to_csv(caminho, index=False)
    return len(novas)


def remover_medicoes(local: str) -> int:
    medicoes = carregar_medicoes()
    restantes = medicoes[medicoes["cidade"] != local]
    removidas = len(medicoes) - len(restantes)
    if removidas:
        restantes.to_csv(caminho_medicoes(), index=False)
    return removidas


def carregar_clima(incluir_medicoes: bool = True) -> pd.DataFrame:
    """NASA POWER (origem 'nasa') + medições dos usuários (origem 'usuario')."""
    partes = [carregar_clima_base().assign(origem="nasa")]
    if incluir_medicoes:
        medicoes = carregar_medicoes()
        if not medicoes.empty:
            partes.append(medicoes)
    return pd.concat(partes, ignore_index=True)


def carregar_sundata(somente_referencia: bool = True) -> pd.DataFrame:
    """Irradiação de longo prazo do CRESESB/SunData (coletada com Selenium)."""
    df = pd.read_csv(RAW_DIR / "cresesb_sundata_capitais.csv", keep_default_na=False)
    return df[df["estacao_referencia"]] if somente_referencia else df


def carregar_noticias() -> pd.DataFrame:
    return text.carregar_noticias()


def carregar_corpus_llm() -> pd.DataFrame:
    """Documentos em trechos (chunks) preparados para o uso com LLMs (ver llm_prep.py)."""
    caminho = PROCESSED_DIR / "corpus_llm.jsonl"
    if not caminho.exists():
        return pd.DataFrame(columns=["id", "tipo", "fonte", "titulo", "url", "data", "cidade", "texto", "n_palavras"])
    return pd.read_json(caminho, lines=True, dtype={"data": str})
