"""Meus dados: envio de medições para a API (POST), gestão (GET/DELETE) e downloads."""

import json
from datetime import date
from urllib.parse import quote

import pandas as pd
import streamlit as st

from src import api_client, ui
from src.data_processing import climate


def lote_para_api(df: pd.DataFrame, cidade: str) -> dict:
    """Converte as linhas de um local no corpo JSON esperado por POST /medicoes."""
    df = df[df["cidade"] == cidade]
    medicoes = df[["date", *climate.VARIAVEIS]].assign(date=df["date"].dt.strftime("%Y-%m-%d"))
    lat, lon = df["latitude"].iloc[0], df["longitude"].iloc[0]
    return {
        "cidade": cidade,
        "latitude": None if pd.isna(lat) else float(lat),
        "longitude": None if pd.isna(lon) else float(lon),
        "medicoes": json.loads(medicoes.to_json(orient="records")),  # NaN vira null
    }


def enviar(lotes: list) -> None:
    for lote in lotes:
        try:
            resposta = api_client.post("/medicoes", lote)
        except api_client.ErroAPI as exc:
            st.error(f"{lote['cidade']}: {exc}")
            continue
        st.toast(f"{resposta['cidade']}: {resposta['mensagem']}", icon=":material/cloud_done:")
        st.session_state.novas_cidades.append(resposta["cidade"])
    ui.limpar_cache_medicoes()


st.title("Meus dados")
st.write(
    "Envie medições do seu local (de um piranômetro, do app do inversor ou de outra fonte). "
    "Elas são enviadas para a API (`POST /medicoes`), validadas e guardadas, e passam a "
    "aparecer na lista de locais da página **Clima e geração**."
)

aba_csv, aba_manual = st.tabs(["Enviar CSV", "Adicionar uma medição"])
with aba_csv:
    st.markdown(
        "**Formato:** colunas `date` (AAAA-MM-DD) e `ALLSKY_SFC_SW_DWN` (kWh/m²/dia) são "
        "obrigatórias; `cidade`, `latitude`, `longitude`, `T2M`, `RH2M`, `WS10M` e `CLOUD_AMT` são opcionais."
    )
    try:
        modelo = ui.clima(("Rio de Janeiro (RJ)",)).head(5).drop(columns="origem")
    except api_client.ErroAPI as exc:
        ui.erro_api(exc)
    modelo["cidade"] = "Meu telhado"
    st.download_button(
        "Baixar CSV modelo", modelo.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"), "modelo_upload.csv", "text/csv"
    )
    arquivo = st.file_uploader("Escolha um CSV", type="csv", key=f"uploader_{st.session_state.uploader_n}")
    if arquivo is not None:
        try:
            df_up = climate.parse_uploaded_csv(arquivo.getvalue(), arquivo.name)
        except ValueError as exc:
            st.error(f"{arquivo.name}: {exc}")
        else:
            locais_up = list(df_up["cidade"].unique())
            st.caption(f"{len(df_up)} linhas válidas, {len(locais_up)} local(is): {', '.join(locais_up)}")
            st.dataframe(df_up.head(10), hide_index=True, width="stretch", column_config={"date": st.column_config.DateColumn("date", format="YYYY-MM-DD")})
            if st.button("Enviar para a API", type="primary", icon=":material/cloud_upload:"):
                enviar([lote_para_api(df_up, c) for c in locais_up])
                st.session_state.uploader_n += 1  # limpa o seletor de arquivo
                st.rerun()

with aba_manual:
    with st.form("form_medicao", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        nome = c1.text_input("Local", "Meu telhado")
        dia = c2.date_input("Data", date.today(), format="DD/MM/YYYY")
        irradiancia = c3.number_input("Irradiância (kWh/m²/dia)", 0.0, 12.0, 5.0, 0.1)
        c4, c5 = st.columns(2)
        temperatura = c4.number_input("Temperatura (°C, opcional)", -20.0, 55.0, None)
        nuvens = c5.number_input("Nuvens (%, opcional)", 0.0, 100.0, None)
        if st.form_submit_button("Enviar medição", icon=":material/send:"):
            enviar(
                [{
                    "cidade": nome,
                    "medicoes": [{"date": dia.isoformat(), "ALLSKY_SFC_SW_DWN": irradiancia, "T2M": temperatura, "CLOUD_AMT": nuvens}],
                }]
            )

st.subheader("Medições salvas na API")
try:
    salvas = ui.medicoes()
except api_client.ErroAPI as exc:
    ui.erro_api(exc)
if salvas.empty:
    st.caption("Nenhuma medição enviada ainda.")
for local, df_local in salvas.groupby("cidade"):
    with st.expander(f"{local}: {len(df_local)} dia(s), de {df_local['date'].min():%d/%m/%Y} a {df_local['date'].max():%d/%m/%Y}"):
        st.dataframe(df_local.drop(columns="origem"), hide_index=True, width="stretch", column_config={"date": st.column_config.DateColumn("date", format="DD/MM/YYYY")})
        if st.button("Remover da API", key=f"rm_{local}", icon=":material/delete:"):
            try:
                api_client.delete(f"/medicoes/{quote(local, safe='')}")
            except api_client.ErroAPI as exc:
                st.error(str(exc))
            ui.limpar_cache_medicoes()
            st.rerun()

st.subheader("Downloads")
try:
    clima_todos = ui.clima(())
    noticias = ui.noticias()
    longo = ui.longo_prazo()
except api_client.ErroAPI as exc:
    ui.erro_api(exc)
d1, d2, d3 = st.columns(3)
d1.download_button(
    "Dados climáticos consolidados (CSV)",
    clima_todos.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"),
    "dados_climaticos_consolidados.csv",
    "text/csv",
    help="NASA POWER (capitais) + medições enviadas por usuários, via GET /clima",
)
d2.download_button(
    "Notícias extraídas (CSV)",
    noticias.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"),
    "noticias_setor_solar.csv",
    "text/csv",
)
d3.download_button(
    "Irradiação de longo prazo, CRESESB (CSV)",
    longo.to_csv(index=False).encode("utf-8"),
    "irradiacao_longo_prazo_cresesb.csv",
    "text/csv",
)
