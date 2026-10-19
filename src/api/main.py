"""API do Solar Viável (FastAPI).

Expõe os dados do projeto (clima da NASA POWER, irradiação de longo prazo do CRESESB,
notícias do setor e medições enviadas por usuários) e os cálculos de geração, para que
o app Streamlit (ou qualquer outro cliente) consulte e envie dados por HTTP.

Rodar (na raiz do projeto):
    uvicorn src.api.main:app --reload
Documentação interativa: http://127.0.0.1:8000/docs (Swagger) e /redoc.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from typing import List, Literal, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, status

from src import repositorio
from src.api import schemas
from src.data_acquisition import nasa_power_client
from src.data_processing import climate, llm_prep, text

DESCRICAO = """
API do **Solar Viável**: dados e cálculos para avaliar o potencial de geração solar
fotovoltaica de residências e pequenos negócios no Brasil (ODS 7).

* **Locais e clima**: série diária da NASA POWER para 10 capitais, mais as medições
  enviadas pelos usuários; consulta ao vivo de qualquer coordenada.
* **Longo prazo**: irradiação média mensal do CRESESB/SunData (coletada com Selenium),
  no plano horizontal e inclinado.
* **Estimativa**: geração (kWh) e economia (R$) para um sistema de potência informada.
* **Notícias**: matérias do setor coletadas da ABSOLAR e do Canal Solar (Beautiful Soup).
* **Medições**: envio (POST), consulta e remoção de dados do usuário.
* **LLM**: corpus em trechos e recuperação de contexto, base para o uso de LLMs no TP4.
"""

TAGS = [
    {"name": "Locais e clima", "description": "Consulta da série diária de clima e irradiância."},
    {"name": "Longo prazo (CRESESB)", "description": "Médias mensais de longo prazo, plano horizontal e inclinado."},
    {"name": "Estimativa", "description": "Cálculo de geração e economia."},
    {"name": "Notícias", "description": "Notícias do setor solar extraídas por web scraping."},
    {"name": "Medições do usuário", "description": "Envio e gestão de dados próprios."},
    {"name": "LLM", "description": "Preparação para perguntas e respostas com LLM (próxima etapa)."},
]

app = FastAPI(title="Solar Viável API", version="1.0.0", description=DESCRICAO, openapi_tags=TAGS)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _clima_base() -> pd.DataFrame:
    return repositorio.carregar_clima_base()


@lru_cache(maxsize=1)
def _sundata() -> pd.DataFrame:
    return repositorio.carregar_sundata()


@lru_cache(maxsize=1)
def _noticias() -> pd.DataFrame:
    return repositorio.carregar_noticias()


@lru_cache(maxsize=1)
def _corpus() -> pd.DataFrame:
    return repositorio.carregar_corpus_llm()


def _clima(incluir_medicoes: bool = True) -> pd.DataFrame:
    partes = [_clima_base().assign(origem="nasa")]
    medicoes = repositorio.carregar_medicoes() if incluir_medicoes else pd.DataFrame()
    if not medicoes.empty:
        partes.append(medicoes)
    return pd.concat(partes, ignore_index=True)


def _registros(df: pd.DataFrame) -> list:
    """DataFrame -> lista de dicts serializável (NaN vira null, datas viram AAAA-MM-DD)."""
    df = df.copy()
    for col in df.select_dtypes("datetime").columns:
        df[col] = df[col].dt.strftime("%Y-%m-%d")
    return json.loads(df.to_json(orient="records", force_ascii=False))


def _filtrar_periodo(df: pd.DataFrame, inicio: Optional[date], fim: Optional[date]) -> pd.DataFrame:
    if inicio:
        df = df[df["date"].dt.date >= inicio]
    if fim:
        df = df[df["date"].dt.date <= fim]
    return df


def _exigir_cidades(df: pd.DataFrame, cidades: List[str]) -> None:
    desconhecidas = sorted(set(cidades) - set(df["cidade"]))
    if desconhecidas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Local não encontrado: {', '.join(desconhecidas)}. Veja GET /locais.")


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@app.get("/", summary="Boas-vindas e links úteis")
def raiz():
    return {"api": "Solar Viável", "versao": app.version, "documentacao": "/docs", "saude": "/saude"}


@app.get("/saude", summary="Verifica se a API está no ar")
def saude():
    return {"status": "ok"}


@app.get("/locais", response_model=List[schemas.Local], tags=["Locais e clima"], summary="Lista os locais disponíveis")
def listar_locais(incluir_medicoes: bool = True):
    """Capitais coletadas da NASA POWER e locais enviados por usuários, com o período e a irradiância média."""
    df = _clima(incluir_medicoes)
    resumo = (
        df.groupby(["cidade", "origem"], as_index=False)
        .agg(
            latitude=("latitude", "first"),
            longitude=("longitude", "first"),
            dias=("date", "count"),
            inicio=("date", "min"),
            fim=("date", "max"),
            irradiacao_media=("ALLSKY_SFC_SW_DWN", "mean"),
        )
        .round({"irradiacao_media": 3})
        .sort_values("irradiacao_media", ascending=False)
    )
    return _registros(resumo)


@app.get("/clima", response_model=List[schemas.RegistroClima], tags=["Locais e clima"], summary="Série diária de clima")
def consultar_clima(
    cidade: List[str] = Query(default=[], description="um ou mais locais (repita o parâmetro); vazio = todos"),
    inicio: Optional[date] = Query(None, description="data inicial, AAAA-MM-DD"),
    fim: Optional[date] = Query(None, description="data final, AAAA-MM-DD"),
    incluir_medicoes: bool = Query(True, description="inclui as medições enviadas por usuários"),
):
    """Irradiância, temperatura, umidade, vento e nuvens por dia. Ex.: `/clima?cidade=Recife (PE)&inicio=2026-01-01`."""
    df = _clima(incluir_medicoes)
    if cidade:
        _exigir_cidades(df, cidade)
        df = df[df["cidade"].isin(cidade)]
    return _registros(_filtrar_periodo(df, inicio, fim))


@app.get("/clima/resumo", tags=["Locais e clima"], summary="Estatísticas por local")
def resumo_clima(
    cidade: List[str] = Query(default=[]),
    inicio: Optional[date] = None,
    fim: Optional[date] = None,
):
    """Média, mínimo e máximo de cada variável por local, ordenado pela irradiância média."""
    df = _clima()
    if cidade:
        _exigir_cidades(df, cidade)
        df = df[df["cidade"].isin(cidade)]
    df = _filtrar_periodo(df, inicio, fim)
    if df.empty:
        return []
    return _registros(climate.resumo_por_cidade(df).reset_index())


@app.get("/clima/ao-vivo", response_model=List[schemas.RegistroClima], tags=["Locais e clima"], summary="Consulta ao vivo da NASA POWER")
def clima_ao_vivo(
    latitude: float = Query(..., ge=-35, le=6),
    longitude: float = Query(..., ge=-75, le=-30),
    dias: int = Query(180, ge=7, le=365),
    nome: str = Query("Meu local", max_length=80),
):
    """Busca na NASA POWER os últimos `dias` dias de qualquer coordenada do Brasil (não é salvo)."""
    fim = date.today() - timedelta(days=2)  # a NASA tem defasagem de poucos dias
    try:
        df = nasa_power_client.get_power_data(latitude, longitude, fim - timedelta(days=dias), fim)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Falha ao consultar a NASA POWER: {exc}") from exc
    df = df.reset_index()
    for col in climate.VARIAVEIS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.assign(cidade=f"{nome} (ao vivo)", latitude=latitude, longitude=longitude, origem="nasa_ao_vivo")
    return _registros(df[[*climate.COLUNAS_MODELO, "origem"]])


@app.get(
    "/irradiacao-longo-prazo",
    response_model=List[schemas.IrradiacaoLongoPrazo],
    tags=["Longo prazo (CRESESB)"],
    summary="Irradiação média mensal de longo prazo",
)
def irradiacao_longo_prazo(
    cidade: List[str] = Query(default=[]),
    plano: Optional[Literal["Plano Horizontal", "Ângulo igual a latitude", "Maior média anual", "Maior mínimo mensal"]] = None,
):
    """Dados do CRESESB/SunData para a estação de referência de cada capital (mais próxima em terra)."""
    df = _sundata()
    if cidade:
        _exigir_cidades(df, cidade)
        df = df[df["cidade"].isin(cidade)]
    if plano:
        df = df[df["plano"] == plano]
    return [
        {
            **{k: r[k] for k in ("cidade", "estacao", "municipio", "uf", "distancia_km", "plano", "inclinacao_graus", "media_anual", "delta")},
            "mensal": {m: r[m] for m in climate.MESES},
        }
        for r in _registros(df)
    ]


@app.get("/estimativa", response_model=schemas.Estimativa, tags=["Estimativa"], summary="Geração e economia estimadas")
def estimativa(
    cidade: str,
    potencia_kwp: float = Query(5.0, gt=0, le=1000, description="potência instalada"),
    desempenho: float = Query(0.80, ge=0.5, le=0.95, description="taxa de desempenho (perdas)"),
    tarifa: float = Query(0.90, gt=0, le=5, description="R$/kWh"),
    fonte: Literal["nasa", "cresesb"] = Query("cresesb", description="nasa = últimos 12 meses medidos; cresesb = longo prazo, painel inclinado"),
):
    """Geração = irradiância (horas de sol pleno) x potência x desempenho. Ex.: `/estimativa?cidade=Fortaleza (CE)&potencia_kwp=4`."""
    if fonte == "cresesb":
        df = _sundata()
        linha = df[(df["cidade"] == cidade) & (df["plano"] == "Maior média anual")]
        if linha.empty:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sem dados do CRESESB para '{cidade}'. Use fonte=nasa.")
        r = linha.iloc[0]
        mensal = climate.geracao_mensal([r[m] for m in climate.MESES], potencia_kwp, desempenho, tarifa)
        ano = float(mensal["geracao_kwh"].sum())
        irradiacao = float(r["media_anual"])
        obs = f"Estação {r['estacao']} ({r['distancia_km']} km), painéis a {r['inclinacao_graus']}° voltados para o norte."
    else:
        df = _clima()
        serie = df.loc[df["cidade"] == cidade, "ALLSKY_SFC_SW_DWN"]
        if serie.empty:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Local não encontrado: {cidade}. Veja GET /locais.")
        irradiacao = float(serie.mean())
        ano = climate.estimar_geracao(irradiacao, potencia_kwp, desempenho) * 365
        obs = f"Média de {serie.count()} dias de irradiância no plano horizontal."
    dia = ano / 365
    return {
        "cidade": cidade,
        "fonte": fonte,
        "irradiacao_media": round(irradiacao, 3),
        "potencia_kwp": potencia_kwp,
        "desempenho": desempenho,
        "tarifa": tarifa,
        "geracao_dia_kwh": round(dia, 2),
        "geracao_mes_kwh": round(ano / 12, 1),
        "geracao_ano_kwh": round(ano, 0),
        "economia_mes_rs": round(ano / 12 * tarifa, 2),
        "economia_ano_rs": round(ano * tarifa, 2),
        "observacao": obs,
    }


@app.get("/noticias", response_model=List[schemas.Noticia], tags=["Notícias"], summary="Notícias do setor solar")
def listar_noticias(
    fonte: List[str] = Query(default=[], description="ABSOLAR e/ou Canal Solar"),
    busca: Optional[str] = Query(None, description="filtra por termo no título/resumo/texto"),
    limite: int = Query(50, ge=1, le=500),
    incluir_texto: bool = Query(False, description="inclui o texto completo das matérias"),
):
    df = _noticias()
    if fonte:
        df = df[df["fonte"].isin(fonte)]
    if busca:
        conteudo = df["titulo"] + " " + df["resumo"] + " " + df["texto"]
        df = df[conteudo.str.contains(busca, case=False, regex=False)]
    df = df.assign(n_palavras=df["texto"].str.split().str.len()).sort_values("data", ascending=False).head(limite)
    if not incluir_texto:
        df = df.drop(columns="texto")
    return _registros(df)


@app.get("/noticias/palavras", tags=["Notícias"], summary="Palavras mais frequentes")
def palavras_frequentes(fonte: List[str] = Query(default=[]), top: int = Query(20, ge=1, le=100)):
    df = _noticias()
    if fonte:
        df = df[df["fonte"].isin(fonte)]
    return _registros(text.frequencia_palavras(text.montar_corpus(df), top))


@app.post(
    "/medicoes",
    response_model=schemas.RespostaMedicoes,
    status_code=status.HTTP_201_CREATED,
    tags=["Medições do usuário"],
    summary="Envia medições de um local",
)
def enviar_medicoes(lote: schemas.LoteMedicoes):
    """Recebe medições diárias (validadas) e as guarda; o local passa a aparecer em `/locais` e `/clima`.

    Datas repetidas para o mesmo local substituem as anteriores. Os nomes das capitais
    coletadas são reservados.
    """
    if lote.cidade in set(_clima_base()["cidade"]):
        raise HTTPException(status.HTTP_409_CONFLICT, f"'{lote.cidade}' é um local da base NASA; use outro nome.")
    df = pd.DataFrame([m.model_dump() for m in lote.medicoes])
    df["date"] = pd.to_datetime(df["date"])
    df = df.assign(cidade=lote.cidade, latitude=lote.latitude, longitude=lote.longitude)
    recebidas = repositorio.salvar_medicoes(df)
    return {"cidade": lote.cidade, "recebidas": recebidas, "mensagem": f"{recebidas} medição(ões) salva(s)."}


@app.get("/medicoes", response_model=List[schemas.RegistroClima], tags=["Medições do usuário"], summary="Lista as medições enviadas")
def listar_medicoes(cidade: Optional[str] = None):
    df = repositorio.carregar_medicoes()
    if cidade:
        df = df[df["cidade"] == cidade]
    return _registros(df)


@app.delete("/medicoes/{cidade}", tags=["Medições do usuário"], summary="Remove as medições de um local")
def remover_medicoes(cidade: str):
    removidas = repositorio.remover_medicoes(cidade)
    if not removidas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Nenhuma medição para '{cidade}'.")
    return {"cidade": cidade, "removidas": removidas}


@app.get("/llm/corpus", tags=["LLM"], summary="Estatísticas do corpus preparado para LLMs")
def corpus_llm():
    df = _corpus()
    return {
        "documentos": len(df),
        "palavras": int(df["n_palavras"].sum()) if len(df) else 0,
        "por_tipo": df["tipo"].value_counts().to_dict(),
        "por_fonte": df["fonte"].value_counts().to_dict(),
    }


@app.get("/llm/contexto", response_model=schemas.ContextoLLM, tags=["LLM"], summary="Recupera contexto para uma pergunta")
def contexto_llm(pergunta: str = Query(..., min_length=3), k: int = Query(4, ge=1, le=10)):
    """Busca os trechos mais relevantes do corpus e monta o prompt que será enviado ao LLM no TP4."""
    trechos = llm_prep.buscar(_corpus(), pergunta, k)
    return {"pergunta": pergunta, "trechos": _registros(trechos), "prompt": llm_prep.montar_prompt(pergunta, trechos)}
