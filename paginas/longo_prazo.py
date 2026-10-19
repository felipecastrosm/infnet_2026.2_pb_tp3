"""Potencial de longo prazo: médias mensais históricas do CRESESB/SunData (coletadas com Selenium).

Responde a duas perguntas que a série de um ano da NASA não responde bem:
- como a geração varia ao longo dos meses em um ano típico;
- quanto se ganha inclinando os painéis (em vez de deixá-los na horizontal).
Dados: GET /irradiacao-longo-prazo, GET /clima/resumo e GET /estimativa da API.
"""

import pandas as pd
import streamlit as st

from src import api_client, ui
from src.data_processing import climate

PLANOS = ["Plano Horizontal", "Ângulo igual a latitude", "Maior média anual", "Maior mínimo mensal"]
EXPLICACAO_PLANOS = {
    "Plano Horizontal": "painel deitado (0°), referência das medições de satélite",
    "Ângulo igual a latitude": "regra prática de instalação: inclinação igual à latitude do local",
    "Maior média anual": "inclinação que maximiza a geração no ano",
    "Maior mínimo mensal": "inclinação que maximiza o pior mês (útil para quem quer geração mais estável)",
}

try:
    lp = ui.longo_prazo()
except api_client.ErroAPI as exc:
    ui.erro_api(exc)

capitais = sorted(lp["cidade"].unique())
with st.sidebar:
    st.header("Parâmetros")
    if "cidades_lp" not in st.session_state:
        padrao = st.session_state.get("cidades") or ["Rio de Janeiro (RJ)", "Fortaleza (CE)", "Curitiba (PR)"]
        st.session_state.cidades_lp = [c for c in padrao if c in capitais] or capitais[:3]
    cidades = st.multiselect("Capitais", capitais, key="cidades_lp")
potencia, desempenho, tarifa = ui.parametros_sistema()

st.title("Potencial de longo prazo")
st.caption(
    "Irradiação solar diária média de cada mês em um ano típico, segundo o "
    "[SunData do CRESESB/CEPEL](https://cresesb.cepel.br/index.php?section=sundata) (base do Atlas "
    "Brasileiro de Energia Solar). Coletado com Selenium, que preenche o formulário de coordenadas do site."
)

if not cidades:
    st.info("Selecione ao menos uma capital na barra lateral.")
    st.stop()

plano = st.radio("Inclinação dos painéis", PLANOS, index=2, horizontal=True, key="plano_lp")
st.caption(f"**{plano}**: {EXPLICACAO_PLANOS[plano]}.")

sel = lp[lp["cidade"].isin(cidades)]
do_plano = sel[sel["plano"] == plano].set_index("cidade")

st.subheader("Irradiação ao longo do ano (kWh/m²/dia)")
perfil = do_plano[climate.MESES].T
perfil.index = pd.CategoricalIndex(perfil.index, categories=climate.MESES, ordered=True)
st.line_chart(perfil, y_label="kWh/m²/dia", x_label="mês")

st.subheader("Geração estimada")
cidade = st.selectbox("Capital", cidades, key="cidade_lp")
try:
    est = ui.estimativa(cidade, potencia, desempenho, tarifa, "cresesb")
except api_client.ErroAPI as exc:
    ui.erro_api(exc)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Geração média (mês)", f"{ui.brl(est['geracao_mes_kwh'])} kWh")
m2.metric("Geração (ano)", f"{ui.brl(est['geracao_ano_kwh'])} kWh")
m3.metric("Economia (mês)", f"R$ {ui.brl(est['economia_mes_rs'], 2)}")
m4.metric("Economia (ano)", f"R$ {ui.brl(est['economia_ano_rs'], 2)}")
st.caption(f"Via `GET /estimativa` (fonte CRESESB, maior média anual). {est['observacao']}")

linha = do_plano.loc[cidade]
mensal = climate.geracao_mensal([linha[m] for m in climate.MESES], potencia, desempenho, tarifa)
st.bar_chart(mensal.set_index(pd.CategoricalIndex(mensal["mes"], categories=climate.MESES, ordered=True))["geracao_kwh"], y_label="kWh no mês")
st.caption(
    f"Geração mês a mês com painéis em **{plano.lower()}** ({int(linha['inclinacao_graus'])}°). "
    f"Pior mês: {mensal.loc[mensal['geracao_kwh'].idxmin(), 'mes']} · melhor mês: {mensal.loc[mensal['geracao_kwh'].idxmax(), 'mes']}."
)

st.subheader("Ganho com a inclinação")
ganho = sel.pivot_table(index="cidade", columns="plano", values="media_anual")[["Plano Horizontal", "Ângulo igual a latitude", "Maior média anual"]]
ganho["ganho (%)"] = ((ganho["Maior média anual"] / ganho["Plano Horizontal"] - 1) * 100).round(1)
st.dataframe(ganho, width="stretch")
st.caption("Médias anuais em kWh/m²/dia. O ganho de inclinar os painéis é maior quanto mais longe da linha do Equador.")

st.subheader("Último ano (NASA) x longo prazo (CRESESB)")
try:
    nasa = pd.DataFrame(api_client.get("/clima/resumo", cidade=cidades)).set_index("cidade")["ALLSKY_SFC_SW_DWN (mean)"]
except api_client.ErroAPI as exc:
    ui.erro_api(exc)
horizontal = sel[sel["plano"] == "Plano Horizontal"].set_index("cidade")["media_anual"]
comparacao = pd.DataFrame({"NASA, último ano": nasa, "CRESESB, longo prazo": horizontal}).round(2)
comparacao["diferença (%)"] = ((comparacao.iloc[:, 0] / comparacao.iloc[:, 1] - 1) * 100).round(1)
st.dataframe(comparacao, width="stretch")
st.caption(
    "Ambos no plano horizontal, em kWh/m²/dia. A diferença mostra se o último ano foi mais ou menos "
    "ensolarado que o normal (e também as diferenças entre a medição por satélite e a da estação)."
)

with st.expander("Estações de referência do CRESESB"):
    estacoes = sel.drop_duplicates("cidade")[["cidade", "estacao", "municipio", "uf", "distancia_km"]]
    st.dataframe(estacoes, hide_index=True, width="stretch")
