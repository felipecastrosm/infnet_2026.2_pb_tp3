"""Processamento de texto das notícias: corpus, frequência de palavras e nuvem."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

STOPWORDS = set(
    """a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sob
    sobre entre até após ante e ou mas que se como quando onde quem qual quais porque
    também já não sim mais menos muito muita muitos muitas pouco ao aos à às pelo pela
    pelos pelas isso isto esse essa esses essas este esta estes estas aquele aquela seu
    sua seus suas ele ela eles elas nós você vocês foi ser são é era eram será serão
    tem têm ter tinha há haver ainda só apenas cada outro outra outros outras mesmo
    mesma todo toda todos todas ano anos segundo conforme durante desde pode podem
    deve devem fazer feito fez vai vão ir assim então dia dias mês meses fonte data
    autor read more home leia veja saiba""".split()
)


def carregar_noticias() -> pd.DataFrame:
    """Une as duas fontes (ABSOLAR e Canal Solar) em um único DataFrame.

    Colunas: fonte, titulo, categoria, resumo, url, data (pode ser nula) e texto.
    """
    frames = []
    absolar = RAW_DIR / "absolar_noticias.csv"
    if absolar.exists():
        df = pd.read_csv(absolar, parse_dates=["data"])
        df["fonte"] = "ABSOLAR"
        frames.append(df)
    canal = RAW_DIR / "canalsolar_noticias.csv"
    if canal.exists():
        df = pd.read_csv(canal, parse_dates=["data", "coletado_em"])
        # TP3: data de publicação vem da matéria; nas coletas antigas, usa a data da coleta
        df["data"] = df["data"].fillna(df["coletado_em"])
        df["fonte"] = "Canal Solar"
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    noticias = pd.concat(frames, ignore_index=True)
    noticias["texto"] = noticias["texto"].fillna("")
    noticias["resumo"] = noticias["resumo"].fillna("")
    return noticias[["fonte", "titulo", "categoria", "resumo", "url", "data", "texto"]]


def montar_corpus(noticias: pd.DataFrame) -> str:
    """Concatena título, resumo e texto de cada notícia em um único corpus."""
    partes = noticias["titulo"] + " " + noticias["resumo"] + " " + noticias["texto"]
    return " ".join(partes)


def tokenizar(texto: str, min_len: int = 4) -> list[str]:
    palavras = re.findall(r"[a-záàâãéêíóôõúç]+", texto.lower())
    return [p for p in palavras if len(p) >= min_len and p not in STOPWORDS]


def frequencia_palavras(texto: str, top: int = 20) -> pd.DataFrame:
    contagem = Counter(tokenizar(texto)).most_common(top)
    return pd.DataFrame(contagem, columns=["palavra", "frequencia"])


def gerar_nuvem(texto: str):
    """Gera a nuvem de palavras (objeto PIL) a partir do texto já filtrado."""
    from wordcloud import WordCloud

    freq = Counter(tokenizar(texto))
    if not freq:
        return None
    return (
        WordCloud(width=900, height=450, background_color="white", colormap="viridis", max_words=80)
        .generate_from_frequencies(freq)
        .to_image()
    )
