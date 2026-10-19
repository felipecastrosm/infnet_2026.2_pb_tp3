"""Página inicial: problema, objetivo, como usar, arquitetura e inspirações."""

import streamlit as st

st.title("Solar Viável")
st.caption("Diagnóstico acessível de potencial solar para residências e pequenos negócios")

st.header("O problema")
st.write(
    "Decidir se vale a pena instalar painéis solares em um imóvel exige avaliar dados "
    "climáticos (irradiância solar, temperatura, nuvens) que não são triviais de encontrar "
    "e interpretar para quem não é da área técnica. Hoje, essa avaliação depende de uma "
    "consultoria paga ou de simuladores comerciais que priorizam a venda de um sistema "
    "específico, não uma análise neutra de viabilidade."
)
st.header("Objetivo do projeto")
st.write(
    "Um app que traduz dados de irradiância e clima (NASA POWER e CRESESB/CEPEL) em uma "
    "estimativa de geração solar fotovoltaica e de economia na conta de luz, complementada "
    "por notícias do setor e por dados que o próprio usuário pode enviar. Alinhado ao "
    "**ODS 7 (Energia limpa e acessível)** e, secundariamente, ao **ODS 13 (Ação contra a "
    "mudança global do clima)**."
)

st.header("Como usar")
st.page_link("paginas/clima.py", label="**Clima e geração**: compare locais no último ano e estime a geração", icon=":material/partly_cloudy_day:")
st.page_link("paginas/longo_prazo.py", label="**Potencial de longo prazo**: médias mensais históricas e painel inclinado", icon=":material/solar_power:")
st.page_link("paginas/noticias.py", label="**Notícias do setor**: nuvem de palavras, estatísticas e manchetes", icon=":material/newspaper:")
st.page_link("paginas/meus_dados.py", label="**Meus dados**: envie suas medições (POST na API) e baixe os dados", icon=":material/upload_file:")
st.page_link("paginas/api.py", label="**Explorar a API**: teste as rotas da API FastAPI pelo navegador", icon=":material/api:")
st.page_link("paginas/ia.py", label="**Rumo à IA**: corpus e plano de uso de LLMs na próxima etapa", icon=":material/smart_toy:")
st.caption("Use o menu à esquerda para navegar. Locais, período e sistema fotovoltaico ficam na barra lateral das páginas de análise.")

st.header("Arquitetura (TP3)")
st.write(
    "Os dados são coletados por scripts independentes e servidos por uma **API FastAPI**. "
    "O app Streamlit consome essa API por HTTP, tanto para consultar (GET) quanto para "
    "enviar dados (POST/DELETE)."
)
st.graphviz_chart(
    """
digraph {
  rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#FEF3C7", color="#F59E0B", fontname="Helvetica", fontsize=11];
  edge [color="#78716C", fontname="Helvetica", fontsize=9];
  nasa [label="NASA POWER\\n(API REST)"]; cresesb [label="CRESESB SunData\\n(formulário dinâmico)"];
  absolar [label="ABSOLAR\\n(HTML)"]; canal [label="Canal Solar\\n(HTML)"];
  dados [label="data/raw e data/processed\\n(CSV, TXT, JSONL)", shape=cylinder, fillcolor="#E7E5E4", color="#78716C"];
  api [label="API FastAPI\\n/locais /clima /estimativa\\n/noticias /medicoes /llm", fillcolor="#FDE68A"];
  app [label="App Streamlit\\n(múltiplas páginas)", fillcolor="#FDE68A"];
  usuario [label="Usuário", shape=ellipse, fillcolor="white"];
  nasa -> dados [label="requests"]; cresesb -> dados [label="Selenium + BS4"];
  absolar -> dados [label="BS4"]; canal -> dados [label="BS4"];
  dados -> api; nasa -> api [label="consulta ao vivo", style=dashed];
  api -> app [label="GET"]; app -> api [label="POST / DELETE"]; usuario -> app;
}
"""
)

st.header("Iniciativas e projetos que inspiraram este trabalho")
st.write(
    "O Solar Viável se inspira em ferramentas e iniciativas que já ajudam a avaliar o "
    "potencial solar, e busca preencher uma lacuna: um primeiro diagnóstico em "
    "português, neutro e acessível a quem não é da área técnica."
)
st.markdown(
    """
- [**Atlas Brasileiro de Energia Solar** (INPE/LABREN)](https://www.gov.br/pt-br/servicos/obter-dados-do-atlas-brasileiro-de-energia-solar-atlas-solar): mapeia a irradiação solar do Brasil com 17 anos de imagens de satélite; inspirou a comparação do potencial entre regiões.
- [**SunData** (CRESESB/CEPEL)](https://cresesb.cepel.br/index.php?section=sundata): calcula a irradiação média mensal em qualquer ponto do Brasil, inclusive no plano inclinado; no TP3 virou fonte de dados do app (coletada com Selenium).
- [**Global Solar Atlas** (Banco Mundial/ESMAP e Solargis)](https://globalsolaratlas.info/): mapa interativo de recurso solar e produção fotovoltaica para pré-viabilidade; inspirou a ideia de um diagnóstico rápido por localização.
- [**PVWatts** (NREL/NLR, EUA)](https://pvwatts.nlr.gov/pvwatts.php): estima a produção de sistemas fotovoltaicos para proprietários de imóveis e instaladores; inspirou o cálculo de geração a partir de potência (kWp) e taxa de desempenho.
- [**PVGIS** (Comissão Europeia, JRC)](https://re.jrc.ec.europa.eu/pvg_tools/en/): ferramenta gratuita de estimativa de geração fotovoltaica com dados históricos; referência de transparência sobre premissas.
- [**ANEEL: Micro e Minigeração Distribuída**](https://www.gov.br/aneel/pt-br/assuntos/geracao-distribuida): contexto regulatório da geração solar própria no Brasil, o cenário em que o público do projeto toma decisão.
- [**ABSOLAR: Infográfico do mercado**](https://www.absolar.org.br/mercado/infografico/): números do setor solar brasileiro; a ABSOLAR também é uma das fontes de notícias do app.
"""
)
st.caption(
    "**Diferencial:** essas ferramentas são, em sua maioria, voltadas a profissionais e/ou em "
    "inglês. O Solar Viável une clima, estimativa de geração, notícias do setor e dados do "
    "próprio usuário em uma interface simples em português, alinhada ao ODS 7."
)

st.header("Links úteis")
st.markdown(
    """
- [NASA POWER](https://power.larc.nasa.gov/) e [documentação da API](https://power.larc.nasa.gov/docs/services/api/)
- [Dicionário de parâmetros](https://power.larc.nasa.gov/docs/methodology/parameters/)
- [CRESESB SunData](https://cresesb.cepel.br/index.php?section=sundata)
- [ABSOLAR](https://www.absolar.org.br/noticias/) e [Canal Solar](https://canalsolar.com.br/noticias/) (fontes das notícias)
- [ODS 7 da ONU](https://brasil.un.org/pt-br/sdgs/7)
"""
)
