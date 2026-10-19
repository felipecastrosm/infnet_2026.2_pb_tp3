"""Notícias do setor: nuvem de palavras, estatísticas e manchetes (dados via GET /noticias)."""

import streamlit as st

from src import api_client, ui
from src.data_processing import text


@st.cache_data
def nuvem_de_palavras(corpus: str):
    return text.gerar_nuvem(corpus)


st.title("Notícias do setor solar")
st.write(
    "Matérias da [ABSOLAR](https://www.absolar.org.br/noticias/) e do "
    "[Canal Solar](https://canalsolar.com.br/noticias/) extraídas com Beautiful Soup por scripts "
    "separados (`src/data_acquisition/`), com o texto completo de cada matéria. As coletas se "
    "acumulam a cada execução, e o app lê tudo pela rota `GET /noticias` da API."
)

try:
    todas = ui.noticias()
except api_client.ErroAPI as exc:
    ui.erro_api(exc)
if todas.empty:
    st.warning("Notícias não encontradas. Rode os scrapers em `src/data_acquisition/`.")
    st.stop()

todas_fontes = sorted(todas["fonte"].unique())
f1, f2 = st.columns([1, 2])
fontes = f1.multiselect("Fontes", todas_fontes, default=todas_fontes, key="fontes")
busca = f2.text_input("Buscar no título, resumo ou texto", key="busca_noticias")
try:
    sel = ui.noticias(tuple(fontes), busca) if fontes else todas.head(0)
except api_client.ErroAPI as exc:
    ui.erro_api(exc)

corpus = text.montar_corpus(sel) if not sel.empty else ""
tokens = text.tokenizar(corpus)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Notícias", len(sel))
m2.metric("Palavras (sem stopwords)", ui.brl(len(tokens)))
m3.metric("Palavras distintas", ui.brl(len(set(tokens))))
m4.metric("Com texto completo", int((sel["n_palavras"] > 0).sum()) if not sel.empty else 0)

if sel.empty:
    st.info("Nenhuma notícia com os filtros atuais.")
    st.stop()

col_nuvem, col_freq = st.columns([3, 2])
with col_nuvem:
    st.subheader("Nuvem de palavras")
    imagem = nuvem_de_palavras(corpus) if tokens else None
    if imagem is not None:
        st.image(imagem, width="stretch")
    else:
        st.info("Sem texto suficiente para a nuvem com os filtros atuais.")
with col_freq:
    st.subheader("Palavras mais frequentes")
    top = st.slider("Quantas palavras", 5, 30, 15, key="top_palavras")
    st.bar_chart(text.frequencia_palavras(corpus, top), x="palavra", y="frequencia", horizontal=True, sort="-frequencia")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Notícias por fonte e categoria")
    contagem = sel.groupby(["fonte", "categoria"]).size().rename("notícias").reset_index()
    st.dataframe(contagem, width="stretch", hide_index=True)
with col_b:
    st.subheader("Publicações por semana")
    datadas = sel.dropna(subset=["data"])
    semana = datadas["data"].dt.to_period("W").dt.start_time.dt.strftime("%Y-%m-%d")
    por_semana = datadas.groupby([semana.rename("semana"), "fonte"]).size().unstack(fill_value=0)
    st.bar_chart(por_semana, y_label="notícias", x_label="semana (início)")

st.subheader("Manchetes")
for row in sel.itertuples():
    with st.container(border=True):
        st.markdown(ui.sem_latex(f"**[{row.titulo}]({row.url})**"))
        data_txt = f" · {row.data:%d/%m/%Y}" if row.data == row.data else ""  # NaT != NaT
        st.caption(f"{row.fonte} · {row.categoria}{data_txt} · {row.n_palavras} palavras")
        if row.fonte == "Canal Solar" and row.resumo:
            st.write(ui.sem_latex(row.resumo))
        if row.texto:
            with st.expander("Ler o texto extraído"):
                st.write(ui.sem_latex(row.texto))
