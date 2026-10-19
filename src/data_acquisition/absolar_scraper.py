"""Scraper de notícias da ABSOLAR (Associação Brasileira de Energia Solar Fotovoltaica).

Usa requests + Beautiful Soup para coletar a lista de notícias e o texto completo de
cada matéria. Roda separadamente do app e grava os resultados em data/raw/.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.absolar.org.br/noticias/"
HEADERS = {"User-Agent": "Mozilla/5.0 (projeto academico Infnet - Solar Viavel)"}
REQUEST_DELAY_S = 1.0  # pausa entre requisições para não sobrecarregar o servidor

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
CSV_PATH = RAW_DIR / "absolar_noticias.csv"
TXT_PATH = RAW_DIR / "absolar_corpus.txt"


def fetch_html(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")


def parse_listing(soup: BeautifulSoup) -> list[dict]:
    """Extrai título, data, link, categoria e resumo de cada item da listagem."""
    items, seen = [], set()
    for li in soup.select("li:has(.wp-block-latest-posts__post-title)"):
        link = li.select_one("a.wp-block-latest-posts__post-title")
        url = link["href"]
        if url in seen:  # a página repete matérias em blocos diferentes
            continue
        seen.add(url)
        time_tag = li.select_one("time")
        excerpt = li.select_one(".wp-block-latest-posts__post-excerpt")
        if excerpt:
            for read_more in excerpt.select("a.wp-block-latest-posts__read-more"):
                read_more.decompose()
        items.append(
            {
                "titulo": link.get_text(" ", strip=True),
                "data": time_tag["datetime"][:10] if time_tag else None,
                "url": url,
                # a categoria é o primeiro segmento do caminho: /home/, /associados/...
                "categoria": url.replace(BASE_URL.rsplit("/noticias/", 1)[0], "").strip("/").split("/")[0],
                "resumo": excerpt.get_text(" ", strip=True) if excerpt else "",
            }
        )
    return items


def parse_article_text(soup: BeautifulSoup) -> str:
    """Extrai o texto corrido de uma matéria (parágrafos dentro de <article>)."""
    article = soup.select_one("article")
    if article is None:
        return ""
    paragraphs = (p.get_text(" ", strip=True) for p in article.find_all("p"))
    return re.sub(r"\s+", " ", " ".join(p for p in paragraphs if p)).strip()


def data_no_texto(texto) -> str | None:
    """(TP3) Alguns itens da listagem vêm sem <time>; o texto da matéria traz "Data: dd/mm/aaaa"."""
    achado = re.search(r"Data:\s*(\d{2})/(\d{2})/(\d{4})", texto if isinstance(texto, str) else "")
    return f"{achado[3]}-{achado[2]}-{achado[1]}" if achado else None


def scrape(max_articles: int | None = None) -> pd.DataFrame:
    items = parse_listing(fetch_html(BASE_URL))
    if max_articles:
        items = items[:max_articles]
    for i, item in enumerate(items, start=1):
        time.sleep(REQUEST_DELAY_S)
        try:
            item["texto"] = parse_article_text(fetch_html(item["url"]))
        except requests.RequestException as exc:
            print(f"[{i}/{len(items)}] falha em {item['url']}: {exc}")
            item["texto"] = ""
        item["data"] = item["data"] or data_no_texto(item["texto"])
        print(f"[{i}/{len(items)}] {item['titulo'][:70]}")
    df = pd.DataFrame(items)
    df["data"] = pd.to_datetime(df["data"])
    return df.sort_values("data", ascending=False).reset_index(drop=True)


def acumular(novas: pd.DataFrame) -> pd.DataFrame:
    """(TP3) Soma as notícias novas às já salvas em coletas anteriores, sem duplicar links.

    A listagem da ABSOLAR só mostra as matérias mais recentes (não há paginação), então
    acumular as coletas é o que faz o acervo crescer ao longo do tempo.
    """
    if CSV_PATH.exists():
        antigas = pd.read_csv(CSV_PATH, parse_dates=["data"])
        novas = pd.concat([novas, antigas], ignore_index=True).drop_duplicates("url", keep="first")
    sem_data = novas["data"].isna()
    novas.loc[sem_data, "data"] = pd.to_datetime(novas.loc[sem_data, "texto"].map(data_no_texto))
    return novas.sort_values("data", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    df = acumular(scrape())
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False)
    corpus = "\n\n".join(f"{row.titulo}\n{row.texto or row.resumo}" for row in df.fillna({"texto": "", "resumo": ""}).itertuples())
    TXT_PATH.write_text(corpus, encoding="utf-8")
    print(f"{len(df)} notícias salvas em {CSV_PATH} e {TXT_PATH}")
