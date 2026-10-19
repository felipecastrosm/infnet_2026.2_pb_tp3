"""Funções compartilhadas pelas páginas do app: dados via API, cache e parâmetros da barra lateral."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from src import api_client
from src.data_processing import climate

# Widgets da barra lateral usados por mais de uma página. O Streamlit apaga o estado de
# um widget quando a página atual não o desenha; regravar a chave a cada execução
# (manter_parametros) mantém as escolhas do usuário ao trocar de página.
CHAVES_PARAMETROS = ["cidades", "cidades_lp", "periodo", "potencia", "desempenho", "tarifa"]


def iniciar_sessao() -> None:
    st.session_state.setdefault("locais_live", {})  # consultas ao vivo {rótulo: DataFrame}
    st.session_state.setdefault("consultas", [])  # histórico das consultas ao vivo
    st.session_state.setdefault("novas_cidades", [])  # locais recém-adicionados, a selecionar
    st.session_state.setdefault("uploader_n", 0)  # muda a key do uploader para limpá-lo


def manter_parametros() -> None:
    for chave in CHAVES_PARAMETROS:
        if chave in st.session_state:
            st.session_state[chave] = st.session_state[chave]


def brl(valor: float, casas: int = 0) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def sem_latex(texto: str) -> str:
    """Escapa o cifrão: no Markdown do Streamlit, "R$ 10 ... R$ 20" viraria fórmula LaTeX."""
    return texto.replace("$", "\\$")


def erro_api(exc: Exception) -> None:
    st.error(f"Não foi possível falar com a API. {exc}", icon=":material/cloud_off:")
    st.stop()


# ---------------------------------------------------------------------------
# Dados (sempre via API). O cache evita repetir requisições a cada interação; as
# rotas que mudam com POST/DELETE (/locais, /clima, /medicoes) usam um cache curto
# e são limpas logo após cada envio (limpar_cache_medicoes).
# ---------------------------------------------------------------------------
def _df_clima(registros: list) -> pd.DataFrame:
    df = pd.DataFrame(registros, columns=[*climate.COLUNAS_MODELO, "origem"])
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(ttl=60, show_spinner=False)
def locais() -> pd.DataFrame:
    return pd.DataFrame(api_client.get("/locais"))


@st.cache_data(ttl=60, show_spinner="Buscando dados climáticos na API...")
def clima(cidades: tuple, inicio=None, fim=None) -> pd.DataFrame:
    return _df_clima(api_client.get("/clima", cidade=list(cidades), inicio=inicio, fim=fim))


@st.cache_data(ttl=60, show_spinner=False)
def medicoes() -> pd.DataFrame:
    return _df_clima(api_client.get("/medicoes"))


def limpar_cache_medicoes() -> None:
    for funcao in (locais, clima, medicoes):
        funcao.clear()


@st.cache_data(ttl=3600, show_spinner="Consultando a NASA POWER pela API...")
def clima_ao_vivo(lat: float, lon: float, dias: int, nome: str) -> pd.DataFrame:
    return _df_clima(api_client.get("/clima/ao-vivo", latitude=lat, longitude=lon, dias=dias, nome=nome))


@st.cache_data(show_spinner=False)
def longo_prazo(plano: str = None) -> pd.DataFrame:
    df = pd.DataFrame(api_client.get("/irradiacao-longo-prazo", plano=plano))
    return pd.concat([df.drop(columns="mensal"), df["mensal"].apply(pd.Series)], axis=1)


@st.cache_data(ttl=60, show_spinner=False)
def estimativa(cidade: str, potencia: float, desempenho: float, tarifa: float, fonte: str) -> dict:
    return api_client.get(
        "/estimativa", cidade=cidade, potencia_kwp=potencia, desempenho=desempenho, tarifa=tarifa, fonte=fonte
    )


@st.cache_data(show_spinner=False)
def noticias(fontes: tuple = (), busca: str = None, incluir_texto: bool = True) -> pd.DataFrame:
    df = pd.DataFrame(api_client.get("/noticias", fonte=list(fontes), busca=busca or None, limite=500, incluir_texto=incluir_texto))
    if not df.empty:
        df["data"] = pd.to_datetime(df["data"])
    return df


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
def buscar_local_ao_vivo() -> None:
    """Callback do formulário: roda antes do script, então não precisa de st.rerun().

    Um st.rerun() no meio do script faria o Streamlit descartar o estado dos widgets
    ainda não desenhados nesta execução.
    """
    nome, lat, lon = st.session_state.live_nome, st.session_state.live_lat, st.session_state.live_lon
    dias = st.session_state.live_dias
    try:
        df_live = clima_ao_vivo(lat, lon, dias, nome)
    except api_client.ErroAPI as exc:  # falha de rede/API não pode derrubar o app
        st.session_state.live_erro = f"Falha na consulta: {exc}"
        return
    st.session_state.live_erro = None
    rotulo = df_live["cidade"].iloc[0]
    st.session_state.locais_live[rotulo] = df_live
    st.session_state.consultas.append(f"{nome} ({lat:.2f}, {lon:.2f}), {dias} dias")
    st.session_state.novas_cidades.append(rotulo)


def parametros_locais(cidades_disponiveis: list, data_min=None, data_max=None, com_ao_vivo: bool = True):
    """Seleção de locais (e período, se informado) na barra lateral. Devolve (cidades, período)."""
    with st.sidebar:
        st.header("Parâmetros")
        # A seleção vive no session_state: quando a lista de opções muda (novo envio ou
        # consulta ao vivo), o widget é recriado e voltaria ao padrão, perdendo a escolha.
        if "cidades" not in st.session_state:
            st.session_state.cidades = [
                c for c in ["Rio de Janeiro (RJ)", "Fortaleza (CE)", "Curitiba (PR)"] if c in cidades_disponiveis
            ]
        st.session_state.cidades = [
            c for c in [*st.session_state.cidades, *st.session_state.novas_cidades] if c in cidades_disponiveis
        ]
        st.session_state.novas_cidades = []
        cidades = st.multiselect("Locais para comparar", cidades_disponiveis, key="cidades")
        periodo = None
        if data_min is not None:
            if "periodo" not in st.session_state:
                st.session_state.periodo = (max(data_min, data_max - timedelta(days=180)), data_max)
            inicio, fim = st.session_state.periodo
            st.session_state.periodo = (max(min(inicio, data_max), data_min), min(max(fim, data_min), data_max))
            periodo = st.slider("Período", min_value=data_min, max_value=data_max, format="DD/MM/YYYY", key="periodo")
        if com_ao_vivo:
            with st.expander("Consultar outro local (ao vivo)"):
                with st.form("form_live"):
                    st.text_input("Nome do local", "Meu local", key="live_nome")
                    st.number_input("Latitude", -35.0, 6.0, -22.9, format="%.4f", key="live_lat")
                    st.number_input("Longitude", -75.0, -30.0, -43.2, format="%.4f", key="live_lon")
                    st.slider("Últimos N dias", 30, 365, 180, key="live_dias")
                    st.form_submit_button("Buscar na NASA POWER", on_click=buscar_local_ao_vivo)
                if st.session_state.get("live_erro"):
                    st.error(st.session_state.live_erro)
                if st.session_state.consultas:
                    st.caption("Consultas nesta sessão: " + "; ".join(st.session_state.consultas))
    return cidades, periodo


def parametros_sistema():
    """Potência, taxa de desempenho e tarifa do sistema fotovoltaico (barra lateral)."""
    with st.sidebar:
        st.subheader("Sistema fotovoltaico")
        st.session_state.setdefault("potencia", 5.0)
        st.session_state.setdefault("desempenho", 0.80)
        st.session_state.setdefault("tarifa", 0.90)
        potencia = st.number_input("Potência instalada (kWp)", 0.5, 100.0, step=0.5, key="potencia")
        desempenho = st.slider(
            "Taxa de desempenho", 0.60, 0.90, step=0.01, key="desempenho",
            help="Perdas de inversor, cabos, temperatura e sujeira. Valores típicos: 0,75 a 0,85.",
        )
        tarifa = st.number_input("Tarifa de energia (R$/kWh)", 0.20, 2.00, step=0.05, key="tarifa")
    return potencia, desempenho, tarifa
