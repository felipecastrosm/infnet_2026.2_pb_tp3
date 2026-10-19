"""Carga, validação e cálculos sobre os dados climáticos (NASA POWER)."""

from __future__ import annotations

import io

import pandas as pd

VARIAVEIS = ["ALLSKY_SFC_SW_DWN", "T2M", "RH2M", "WS10M", "CLOUD_AMT"]
COLUNAS_OBRIGATORIAS = ["date", "ALLSKY_SFC_SW_DWN"]
COLUNAS_MODELO = ["date", "cidade", "latitude", "longitude", *VARIAVEIS]

ROTULOS = {
    "ALLSKY_SFC_SW_DWN": "Irradiância solar (kWh/m²/dia)",
    "T2M": "Temperatura (°C)",
    "RH2M": "Umidade relativa (%)",
    "WS10M": "Vento (m/s)",
    "CLOUD_AMT": "Nuvens (%)",
}


def parse_uploaded_csv(raw: bytes, nome_arquivo: str) -> pd.DataFrame:
    """Valida e normaliza um CSV enviado pelo usuário.

    Exige as colunas `date` e `ALLSKY_SFC_SW_DWN`; `cidade` é opcional (se ausente,
    usa o nome do arquivo). Levanta ValueError com mensagem amigável se inválido.
    """
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise ValueError(f"Não foi possível ler o arquivo como CSV ({exc}).") from exc

    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(faltando)}.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date"].isna().all():
        raise ValueError("A coluna `date` não contém datas válidas (use AAAA-MM-DD).")
    for col in VARIAVEIS:
        df[col] = pd.to_numeric(df[col], errors="coerce") if col in df.columns else float("nan")
    df = df.dropna(subset=["date", "ALLSKY_SFC_SW_DWN"])
    if df.empty:
        raise ValueError("Nenhuma linha válida após remover datas/irradiância ausentes.")

    if "cidade" not in df.columns:
        df["cidade"] = f"Upload: {nome_arquivo.rsplit('.', 1)[0]}"
    for col in ("latitude", "longitude"):
        if col not in df.columns:
            df[col] = float("nan")
    return df[COLUNAS_MODELO].reset_index(drop=True)


def estimar_geracao(irradiancia_media: float, potencia_kwp: float, desempenho: float = 0.80) -> float:
    """Geração diária estimada (kWh/dia).

    A irradiância em kWh/m²/dia equivale às "horas de sol pleno" (HSP). A geração é
    HSP x potência instalada (kWp) x taxa de desempenho (perdas de inversor, cabos,
    temperatura e sujeira).
    """
    return irradiancia_media * potencia_kwp * desempenho


def resumo_por_cidade(df: pd.DataFrame) -> pd.DataFrame:
    """Estatísticas básicas por cidade, ordenadas pela irradiância média."""
    resumo = (
        df.groupby("cidade")[VARIAVEIS]
        .agg(["mean", "min", "max"])
        .round(2)
    )
    resumo.columns = [f"{v} ({stat})" for v, stat in resumo.columns]
    return resumo.sort_values("ALLSKY_SFC_SW_DWN (mean)", ascending=False)


# ---------------------------------------------------------------------------
# TP3: irradiação de longo prazo (CRESESB/SunData) e geração mês a mês
# ---------------------------------------------------------------------------
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS_NO_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def geracao_mensal(irradiacao_mensal: list[float], potencia_kwp: float, desempenho: float, tarifa: float) -> pd.DataFrame:
    """Geração (kWh) e economia (R$) em cada mês a partir da irradiação diária média do mês."""
    df = pd.DataFrame({"mes": MESES, "dias": DIAS_NO_MES, "irradiacao": irradiacao_mensal})
    df["geracao_kwh"] = (df["irradiacao"] * potencia_kwp * desempenho * df["dias"]).round(1)
    df["economia_rs"] = (df["geracao_kwh"] * tarifa).round(2)
    return df
