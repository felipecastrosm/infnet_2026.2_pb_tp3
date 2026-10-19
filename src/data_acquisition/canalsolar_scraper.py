"""Scraper das notícias do Canal Solar (portal de notícias do setor solar brasileiro).

1. Lê a página de notícias e extrai título, categoria, resumo (linha fina), autor e link
   de cada matéria (TP2).
2. (TP3) Abre cada matéria e extrai o texto completo, a data de publicação e as tags,
   também com requests + Beautiful Soup (as matérias são HTML estático).
3. (TP3) Acumula as coletas: as matérias novas são somadas às do CSV existente
   (sem duplicar pelo link), então o acervo cresce a cada execução.

Respeita o robots.txt do site (as rotas de notícias são permitidas) e pausa entre
requisições.

Uso (na raiz do projeto):
    python -m src.data_acquisition.canalsolar_scraper
"""

from __future__ import annotations

import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

URL = "https://canalsolar.com.br/noticias/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (projeto academico Infnet - Solar Viavel)",
    "Accept-Language": "pt-BR,pt;q=0.9",  # o site redireciona para /en/ conforme o idioma
}
REQUEST_DELAY_S = 1.0
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
CSV_PATH = RAW_DIR / "canalsolar_noticias.csv"
TXT_PATH = RAW_DIR / "canalsolar_corpus.txt"
COLUNAS = ["titulo", "url", "categoria", "resumo", "autor", "data", "tags", "texto", "coletado_em"]


def _text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def fetch_html(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")


def parse_listing(soup: BeautifulSoup) -> list[dict]:
    """Extrai os cards de destaque (hero) e do feed da página de notícias."""
    items, seen = [], set()
    for card in soup.select("a.cs-noticias-hero__card, a.cs-noticias-feed__item"):
        url = card["href"]
        if url in seen:
            continue
        seen.add(url)
        items.append(
            {
                "titulo": _text(card.select_one("h2, h3")),
                "url": url,
                "categoria": _text(card.select_one(".cs-noticias-hero__cat, .cs-noticias-feed__cat")),
                "resumo": _text(card.select_one(".cs-noticias-hero__dek, .cs-noticias-feed__dek")),
                "autor": _text(card.select_one(".cs-noticias-feed__author"))
                or _text(card.select_one(".cs-noticias-hero__meta")).split("·")[0].strip(),
            }
        )
    return items


def parse_article(soup: BeautifulSoup) -> dict:
    """Texto corrido, data de publicação e tags de uma matéria."""
    corpo = soup.select_one(".cs-article__content")
    paragrafos = [_text(p) for p in corpo.find_all("p")] if corpo else []
    # descarta legendas curtas de foto ("Foto: Canva") e linhas vazias
    paragrafos = [p for p in paragrafos if p and not re.match(r"^(foto|imagem|crédito)s?:", p, re.I)]
    publicado = soup.select_one('meta[property="article:published_time"]')
    artigo = soup.select_one("article")
    tags = [c.removeprefix("tag-") for c in (artigo.get("class", []) if artigo else []) if c.startswith("tag-")]
    return {
        "data": publicado["content"][:10] if publicado else None,
        "tags": ";".join(tags),
        "texto": re.sub(r"\s+", " ", " ".join(paragrafos)).strip(),
    }


def acumular(novas: pd.DataFrame, csv_path: Path = CSV_PATH) -> pd.DataFrame:
    """Soma as matérias novas às já salvas, mantendo a versão mais completa de cada link."""
    if csv_path.exists():
        antigas = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        novas = pd.concat([novas.astype(str), antigas], ignore_index=True)
    novas = novas.reindex(columns=COLUNAS).fillna("")
    novas["_tem_texto"] = novas["texto"].str.len() > 0
    novas = novas.sort_values("_tem_texto", ascending=False).drop_duplicates("url").drop(columns="_tem_texto")
    return novas.sort_values(["data", "coletado_em"], ascending=False).reset_index(drop=True)


def completar_textos(df: pd.DataFrame) -> pd.DataFrame:
    """Baixa o texto completo das matérias que ainda não têm (inclusive as de coletas antigas)."""
    pendentes = df.index[df["texto"] == ""]
    for n, i in enumerate(pendentes, start=1):
        time.sleep(REQUEST_DELAY_S)
        try:
            for campo, valor in parse_article(fetch_html(df.at[i, "url"])).items():
                df.at[i, campo] = valor or df.at[i, campo]
        except requests.RequestException as exc:
            print(f"[{n}/{len(pendentes)}] falha em {df.at[i, 'url']}: {exc}")
            continue
        print(f"[{n}/{len(pendentes)}] {df.at[i, 'titulo'][:70]}")
    return df


def scrape() -> pd.DataFrame:
    novas = pd.DataFrame(parse_listing(fetch_html(URL)))
    novas["coletado_em"] = date.today().isoformat()
    df = completar_textos(acumular(novas))
    return df.sort_values(["data", "coletado_em"], ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    df = scrape()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False)
    corpus = "\n\n".join(f"{row.titulo}\n{row.texto or row.resumo}" for row in df.itertuples())
    TXT_PATH.write_text(corpus, encoding="utf-8")
    print(f"{len(df)} notícias salvas em {CSV_PATH} e {TXT_PATH}")
