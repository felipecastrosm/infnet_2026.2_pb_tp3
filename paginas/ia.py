"""Rumo à IA: como os dados coletados serão usados com LLMs na próxima etapa (TP4).

Mostra o corpus já preparado (GET /llm/corpus), o plano de cada caso de uso e uma
demonstração da etapa de recuperação de contexto (GET /llm/contexto), que é a base do
sistema de perguntas e respostas.
"""

import pandas as pd
import streamlit as st

from src import api_client, ui

st.title("Rumo à IA (LLM)")
st.write(
    "Na próxima etapa o Solar Viável vai usar **LLMs** (modelos de linguagem) sobre os dados que já "
    "coleta. Esta página mostra como os dados foram preparados para isso e o que cada recurso vai fazer. "
    "O detalhamento está em `docs/llm_planejamento.md`."
)

try:
    stats = api_client.get("/llm/corpus")
except api_client.ErroAPI as exc:
    ui.erro_api(exc)

st.header("1. Corpus preparado")
c1, c2, c3 = st.columns(3)
c1.metric("Documentos (trechos)", stats["documentos"])
c2.metric("Palavras", ui.brl(stats["palavras"]))
c3.metric("Fichas de local", stats["por_tipo"].get("ficha_local", 0))
st.write(
    "O script `src/data_processing/llm_prep.py` gera `data/processed/corpus_llm.jsonl`. As matérias "
    "viram trechos de até ~220 palavras, com sobreposição e com o título em cada trecho, para que "
    "cada trecho caiba no contexto do modelo e faça sentido sozinho. Os números de clima viram "
    "**fichas de local** em texto, já que um LLM lida melhor com texto do que com tabelas grandes. "
    "Cada documento leva fonte, link e data, para a resposta poder citar de onde veio."
)
st.dataframe(
    pd.DataFrame({"documentos": stats["por_fonte"]}).rename_axis("fonte"),
    width="content",
)

st.header("2. Casos de uso planejados")
planos = pd.DataFrame(
    [
        {
            "recurso": "Perguntas e respostas (RAG)",
            "dados de entrada": "corpus completo (notícias + fichas de local)",
            "como": "recupera os trechos mais relevantes e pede ao LLM uma resposta citando as fontes",
            "rota planejada": "POST /llm/perguntar",
            "valor para o usuário": "tirar dúvidas em linguagem simples (ex.: 'vale a pena em Curitiba?')",
        },
        {
            "recurso": "Resumo de notícias",
            "dados de entrada": "texto completo das matérias (ABSOLAR, Canal Solar)",
            "como": "resumo em 3 frases + 'o que isso muda para quem quer instalar'",
            "rota planejada": "POST /llm/resumo",
            "valor para o usuário": "acompanhar o setor sem ler matérias longas e técnicas",
        },
        {
            "recurso": "Classificação de sentimento",
            "dados de entrada": "título + texto das matérias",
            "como": "positivo / neutro / negativo para o consumidor, com justificativa curta (saída em JSON)",
            "rota planejada": "POST /llm/sentimento",
            "valor para o usuário": "termômetro do setor (tarifas, regulação, preços) na página de notícias",
        },
        {
            "recurso": "Relatório de viabilidade",
            "dados de entrada": "ficha do local + estimativa da API (geração, economia) + parâmetros do usuário",
            "como": "o LLM redige um relatório explicativo; os números vêm da API, não do modelo",
            "rota planejada": "POST /llm/relatorio",
            "valor para o usuário": "um diagnóstico pronto para levar a um instalador ou comparar orçamentos",
        },
    ]
)
st.dataframe(planos, hide_index=True, width="stretch")
st.caption(
    "Princípio de projeto: **os cálculos continuam na API** (determinísticos e testados). O LLM explica, "
    "resume e conversa, mas não inventa números. Toda resposta deve citar a fonte dos dados."
)

st.header("3. Demonstração: recuperação de contexto")
st.write(
    "Antes de responder, o sistema de perguntas e respostas precisa achar os trechos certos. Hoje isso já "
    "funciona com uma busca por palavras-chave (TF-IDF simples, `GET /llm/contexto`), que monta o prompt "
    "que será enviado ao LLM. Na próxima etapa, essa busca passa a usar embeddings (busca semântica)."
)
exemplos = [
    "Qual capital tem a maior irradiação solar?",
    "O que é o leilão de baterias?",
    "Como está o custo da energia solar no Brasil?",
    "Quanto um sistema de 5 kWp gera em Curitiba?",
]
pergunta = st.selectbox("Pergunta de exemplo (ou escreva a sua abaixo)", exemplos, key="ia_exemplo")
pergunta = st.text_input("Pergunta", pergunta, key=f"ia_pergunta_{pergunta}")
k = st.slider("Quantos trechos recuperar", 1, 8, 4, key="ia_k")
try:
    contexto = api_client.get("/llm/contexto", pergunta=pergunta, k=k)
except api_client.ErroAPI as exc:
    st.warning(str(exc))
    st.stop()

if not contexto["trechos"]:
    st.info("Nenhum trecho do corpus contém as palavras da pergunta.")
for i, t in enumerate(contexto["trechos"], start=1):
    with st.container(border=True):
        titulo = f"[{t['titulo']}]({t['url']})" if t["url"] else t["titulo"]
        st.markdown(ui.sem_latex(f"**[{i}] {titulo}**"))
        st.caption(f"{t['fonte']} · {t['tipo']} · {t['data']} · relevância {t['pontuacao']:.2f}")
        st.write(ui.sem_latex(t["texto"][:600] + ("..." if len(t["texto"]) > 600 else "")))
with st.expander("Prompt que será enviado ao LLM na próxima etapa"):
    st.code(contexto["prompt"], language="markdown")
