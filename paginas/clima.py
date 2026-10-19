"""Clima e geração: compara locais no período escolhido e estima geração e economia.

Dados: GET /locais e GET /clima da API (NASA POWER + medições enviadas por usuários),
mais as consultas ao vivo feitas nesta sessão (GET /clima/ao-vivo).
"""

import pandas as pd
import streamlit as st

from src import api_client, ui
from src.data_processing import climate

try:
    locais = ui.locais()
except api_client.ErroAPI as exc:
    ui.erro_api(exc)

live = st.session_state.locais_live
disponiveis = sorted([*locais["cidade"], *live])
data_min = min([pd.to_datetime(locais["inicio"]).min(), *[df["date"].min() for df in live.values()]]).date()
data_max = max([pd.to_datetime(locais["fim"]).max(), *[df["date"].max() for df in live.values()]]).date()

cidades, periodo = ui.parametros_locais(disponiveis, data_min, data_max)
potencia, desempenho, tarifa = ui.parametros_sistema()

st.title("Clima e geração")
st.caption("Irradiância e clima diários (NASA POWER e medições de usuários), servidos pela API.")

da_api = [c for c in cidades if c not in live]
try:
    partes = [ui.clima(tuple(da_api), periodo[0].isoformat(), periodo[1].isoformat())] if da_api else []
except api_client.ErroAPI as exc:
    ui.erro_api(exc)
partes += [live[c] for c in cidades if c in live]
filtrado = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=climate.COLUNAS_MODELO)
filtrado = filtrado[(filtrado["date"].dt.date >= periodo[0]) & (filtrado["date"].dt.date <= periodo[1])]

if filtrado.empty:
    st.info("Selecione ao menos um local (e um período com dados) na barra lateral.")
    st.stop()

resumo = filtrado.groupby("cidade")["ALLSKY_SFC_SW_DWN"].mean().sort_values(ascending=False)
melhor = resumo.index[0]
geracao_dia = climate.estimar_geracao(resumo.iloc[0], potencia, desempenho)
c1, c2, c3 = st.columns(3)
c1.metric("Melhor local no período", melhor.split(" (")[0], f"{resumo.iloc[0]:.2f} kWh/m²/dia", delta_color="off")
c2.metric("Geração estimada (mês)", f"{ui.brl(geracao_dia * 30)} kWh")
c3.metric("Economia estimada (mês)", f"R$ {ui.brl(geracao_dia * 30 * tarifa, 2)}")
st.caption(f"Cálculo para {melhor}: irradiância média x {potencia:g} kWp x desempenho {desempenho:.2f} x 30 dias.")

variavel = st.selectbox("Variável", climate.VARIAVEIS, format_func=climate.ROTULOS.get, key="variavel")
suavizar = st.checkbox("Suavizar (média móvel de 7 dias)", value=True, key="suavizar")
serie = filtrado.pivot_table(index="date", columns="cidade", values=variavel)
if suavizar:
    serie = serie.rolling(7, min_periods=1).mean()
st.line_chart(serie, y_label=climate.ROTULOS[variavel])

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Ranking de irradiância")
    st.bar_chart(resumo.rename("kWh/m²/dia"), horizontal=True)
with col_b:
    st.subheader("Geração estimada por local")
    geracao = (resumo * potencia * desempenho * 30).round(0).rename("kWh/mês")
    st.dataframe(geracao, width="stretch")

st.subheader("Estatísticas por local")
st.dataframe(climate.resumo_por_cidade(filtrado), width="stretch")
