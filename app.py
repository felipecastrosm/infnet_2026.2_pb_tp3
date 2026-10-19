"""Solar Viável: ponto de entrada do app Streamlit com múltiplas páginas.

Define o menu de navegação (st.navigation) e o que é comum a todas as páginas:
configuração, estado de sessão e conexão com a API FastAPI (src/api/main.py), de onde
vêm todos os dados exibidos.
"""

import streamlit as st

from src import api_client, ui

st.set_page_config(page_title="Solar Viável", page_icon=":material/solar_power:", layout="wide")


@st.cache_resource(show_spinner="Conectando à API...")
def conectar_api() -> str:
    return api_client.garantir_api()


try:
    modo_api = conectar_api()
except api_client.ErroAPI as exc:
    st.error(f"API indisponível: {exc}")
    st.stop()

ui.iniciar_sessao()
ui.manter_parametros()

paginas = {
    "Projeto": [
        st.Page("paginas/inicio.py", title="Início", icon=":material/home:", default=True),
    ],
    "Análises": [
        st.Page("paginas/clima.py", title="Clima e geração", icon=":material/partly_cloudy_day:"),
        st.Page("paginas/longo_prazo.py", title="Potencial de longo prazo", icon=":material/solar_power:"),
        st.Page("paginas/noticias.py", title="Notícias do setor", icon=":material/newspaper:"),
    ],
    "Dados": [
        st.Page("paginas/meus_dados.py", title="Meus dados", icon=":material/upload_file:"),
        st.Page("paginas/api.py", title="Explorar a API", icon=":material/api:"),
    ],
    "Inteligência artificial": [
        st.Page("paginas/ia.py", title="Rumo à IA (LLM)", icon=":material/smart_toy:"),
    ],
}

pagina = st.navigation(paginas)
pagina.run()

with st.sidebar:
    st.caption(
        f"Dados servidos pela API FastAPI em `{api_client.url_base()}` "
        f"({'externa' if modo_api == 'externa' else 'iniciada pelo app'}) · "
        f"[documentação]({api_client.url_base()}/docs)"
    )
