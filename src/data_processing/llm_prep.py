"""Preparação dos dados para uso com LLMs (próxima etapa do projeto).

Transforma o que já foi coletado em um corpus de documentos curtos e autocontidos,
prontos para:
- perguntas e respostas com recuperação de contexto (RAG): o LLM responde com base
  nos trechos mais relevantes, citando a fonte;
- resumo e classificação de sentimento das notícias (um documento = uma matéria);
- geração de relatórios: as "fichas de local" descrevem em texto os números do clima.

Tipos de documento:
- `noticia`: matérias da ABSOLAR e do Canal Solar, divididas em trechos de até
  ~220 palavras com sobreposição, para caber na janela de contexto;
- `ficha_local`: um resumo em texto, gerado a partir dos números da NASA POWER e do
  CRESESB, de cada capital (irradiação, melhor/pior mês, geração estimada).

Também traz um recuperador simples por palavras-chave (`buscar`) e o modelo de prompt
(`montar_prompt`) que será usado com o LLM no TP4. O recuperador serve de linha de
base e será substituído por embeddings na próxima etapa.

Uso (na raiz do projeto):
    python -m src.data_processing.llm_prep      # gera data/processed/corpus_llm.jsonl
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from pathlib import Path

import pandas as pd

from src.data_processing import climate, text

SAIDA = Path(__file__).resolve().parents[2] / "data" / "processed" / "corpus_llm.jsonl"
MAX_PALAVRAS = 220
SOBREPOSICAO = 40

PROMPT_QA = """Você é um assistente do Solar Viável, que ajuda pessoas leigas a avaliar
energia solar fotovoltaica no Brasil. Responda em português, de forma simples, usando
SOMENTE as informações do contexto abaixo. Cite as fontes entre colchetes, por exemplo
[1]. Se o contexto não tiver a resposta, diga que não sabe.

Contexto:
{contexto}

Pergunta: {pergunta}
Resposta:"""


def dividir_em_trechos(texto: str, max_palavras: int = MAX_PALAVRAS, sobreposicao: int = SOBREPOSICAO) -> list[str]:
    """Divide um texto em janelas de palavras com sobreposição (para não cortar ideias)."""
    palavras = texto.split()
    if len(palavras) <= max_palavras:
        return [" ".join(palavras)] if palavras else []
    passo = max_palavras - sobreposicao
    return [" ".join(palavras[i : i + max_palavras]) for i in range(0, len(palavras) - sobreposicao, passo)]


def _id(*partes) -> str:
    return hashlib.md5("|".join(map(str, partes)).encode()).hexdigest()[:12]


def documentos_noticias(noticias: pd.DataFrame) -> list[dict]:
    docs = []
    for row in noticias.itertuples():
        corpo = row.texto or row.resumo
        data = row.data.date().isoformat() if pd.notna(row.data) else ""
        for i, trecho in enumerate(dividir_em_trechos(corpo)):
            docs.append(
                {
                    "id": _id(row.url, i),
                    "tipo": "noticia",
                    "fonte": row.fonte,
                    "titulo": row.titulo,
                    "url": row.url,
                    "data": data,
                    "cidade": "",
                    # o título vai junto em cada trecho para o trecho fazer sentido sozinho
                    "texto": f"{row.titulo}. {trecho}",
                }
            )
    return docs


def _num(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def fichas_locais(clima: pd.DataFrame, sundata: pd.DataFrame, potencia_kwp: float = 5.0, desempenho: float = 0.80) -> list[dict]:
    """Uma ficha em linguagem natural por capital, combinando NASA POWER e CRESESB."""
    docs = []
    for cidade, df in clima.groupby("cidade"):
        mensal = df.set_index("date")["ALLSKY_SFC_SW_DWN"].resample("MS").mean()
        frases = [
            f"Potencial solar da capital {cidade}. Entre {df['date'].min():%d/%m/%Y} e {df['date'].max():%d/%m/%Y}, a irradiação solar "
            f"média medida por satélite (NASA POWER) foi de {_num(df['ALLSKY_SFC_SW_DWN'].mean())} kWh/m² por dia "
            "(o mesmo que horas de sol pleno por dia), "
            f"com temperatura média de {_num(df['T2M'].mean(), 1)} °C e cobertura de nuvens média de "
            f"{_num(df['CLOUD_AMT'].mean(), 0)}%.",
            f"O mês mais ensolarado do período foi {mensal.idxmax():%m/%Y} ({_num(mensal.max())} kWh/m²/dia) e o "
            f"menos ensolarado foi {mensal.idxmin():%m/%Y} ({_num(mensal.min())} kWh/m²/dia).",
        ]
        ref = sundata[(sundata["cidade"] == cidade) & (sundata["plano"] == "Maior média anual")]
        if not ref.empty:
            r = ref.iloc[0]
            meses = pd.Series({m: r[m] for m in climate.MESES})
            ger = climate.geracao_mensal(meses.tolist(), potencia_kwp, desempenho, tarifa=0)
            frases.append(
                f"Na base de longo prazo do CRESESB (estação {r['estacao']}, a {_num(r['distancia_km'], 1)} km), "
                f"com os painéis inclinados a {int(r['inclinacao_graus'])}° voltados para o norte, a irradiação média "
                f"anual é de {_num(r['media_anual'])} kWh/m²/dia, variando de {_num(meses.min())} ({meses.idxmin()}) "
                f"a {_num(meses.max())} ({meses.idxmax()})."
            )
            frases.append(
                f"Um sistema de {_num(potencia_kwp, 1)} kWp com taxa de desempenho de {_num(desempenho)} geraria cerca de "
                f"{_num(ger['geracao_kwh'].sum() / 12, 0)} kWh por mês em média ({_num(ger['geracao_kwh'].sum(), 0)} kWh por ano)."
            )
        docs.append(
            {
                "id": _id("ficha", cidade),
                "tipo": "ficha_local",
                "fonte": "NASA POWER + CRESESB",
                "titulo": f"Ficha de potencial solar: {cidade}",
                "url": "",
                "data": f"{df['date'].max():%Y-%m-%d}",
                "cidade": cidade,
                "texto": " ".join(frases),
            }
        )
    return docs


def construir_corpus(noticias: pd.DataFrame, clima: pd.DataFrame, sundata: pd.DataFrame) -> pd.DataFrame:
    corpus = pd.DataFrame(documentos_noticias(noticias) + fichas_locais(clima, sundata))
    corpus["n_palavras"] = corpus["texto"].str.split().str.len()
    return corpus


def buscar(corpus: pd.DataFrame, pergunta: str, k: int = 4) -> pd.DataFrame:
    """Recuperador de linha de base: pontua cada trecho pelas palavras da pergunta (TF-IDF simples)."""
    termos = set(text.tokenizar(pergunta))
    if corpus.empty or not termos:
        return corpus.head(0).assign(pontuacao=[])
    tokens = corpus["texto"].map(lambda t: Counter(text.tokenizar(t)))
    n_docs = len(corpus)
    idf = {t: math.log(1 + n_docs / (1 + sum(t in c for c in tokens))) for t in termos}
    pontuacao = tokens.map(lambda c: sum(math.log1p(c[t]) * idf[t] for t in termos if t in c))
    resultado = corpus.assign(pontuacao=pontuacao.round(3))
    return resultado[resultado["pontuacao"] > 0].nlargest(k, "pontuacao")


def montar_prompt(pergunta: str, trechos: pd.DataFrame) -> str:
    contexto = "\n\n".join(
        f"[{i}] {row.titulo} ({row.fonte}{', ' + row.data if row.data else ''})\n{row.texto}"
        for i, row in enumerate(trechos.itertuples(), start=1)
    )
    return PROMPT_QA.format(contexto=contexto or "(nenhum trecho encontrado)", pergunta=pergunta)


if __name__ == "__main__":
    from src import repositorio

    corpus = construir_corpus(
        repositorio.carregar_noticias(),
        repositorio.carregar_clima_base(),
        repositorio.carregar_sundata(),
    )
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    corpus.to_json(SAIDA, orient="records", lines=True, force_ascii=False)
    print(f"{len(corpus)} documentos ({corpus['tipo'].value_counts().to_dict()}) salvos em {SAIDA}")
