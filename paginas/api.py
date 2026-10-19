"""Explorar a API: lista as rotas (lidas do /openapi.json) e permite testá-las pelo app."""

import json
import shlex
from urllib.parse import quote, urlencode

import pandas as pd
import requests
import streamlit as st

from src import api_client, ui

st.title("Explorar a API")
base = api_client.url_base()
st.write(
    f"O Solar Viável tem uma API própria, feita com **FastAPI**, em `{base}`. Todas as páginas "
    "do app buscam e enviam dados por ela. A documentação interativa (Swagger) fica em "
    f"[{base}/docs]({base}/docs), e a lista de rotas abaixo é lida da especificação OpenAPI da API."
)


@st.cache_data(ttl=300, show_spinner=False)
def especificacao() -> dict:
    return api_client.get("/openapi.json")


try:
    spec = especificacao()
except api_client.ErroAPI as exc:
    ui.erro_api(exc)

rotas = [
    {"método": metodo.upper(), "rota": caminho, "grupo": (op.get("tags") or ["Geral"])[0], "resumo": op.get("summary", ""), "op": op}
    for caminho, ops in spec["paths"].items()
    for metodo, op in ops.items()
]
st.dataframe(pd.DataFrame(rotas).drop(columns="op"), hide_index=True, width="stretch", height=(len(rotas) + 1) * 35 + 3)

st.subheader("Testar uma rota")
escolha = st.selectbox(
    "Rota", range(len(rotas)), format_func=lambda i: f"{rotas[i]['método']} {rotas[i]['rota']}: {rotas[i]['resumo']}", key="api_rota"
)
rota = rotas[escolha]
op = rota["op"]
if op.get("description"):
    st.caption(op["description"].split("\n\n")[0])

caminho = rota["rota"]
query = {}
for p in op.get("parameters", []):
    esquema = p.get("schema", {})
    padrao = esquema.get("default", "")
    exemplo = {"cidade": "Fortaleza (CE)", "pergunta": "Quanto custa a energia solar no Brasil?", "latitude": -22.9, "longitude": -43.2}.get(p["name"], padrao)
    if esquema.get("type") == "array":
        exemplo = "Fortaleza (CE)" if p["name"] == "cidade" else ""
    rotulo = f"{p['name']} ({p['in']}{', obrigatório' if p.get('required') else ''})"
    valor = st.text_input(rotulo, "" if exemplo is None else str(exemplo), key=f"api_{escolha}_{p['name']}", help=p.get("description"))
    if valor == "":
        continue
    if p["in"] == "path":
        caminho = caminho.replace("{" + p["name"] + "}", quote(valor, safe=""))
    else:
        query[p["name"]] = valor

corpo = None
if "requestBody" in op:
    ref = op["requestBody"]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
    exemplo = spec["components"]["schemas"][ref].get("examples", [{}])[0]
    corpo = st.text_area("Corpo da requisição (JSON)", json.dumps(exemplo, ensure_ascii=False, indent=2), height=260, key=f"api_corpo_{escolha}")

url = f"{base}{caminho}" + (f"?{urlencode(query)}" if query else "")
comando = f"curl -X {rota['método']} {shlex.quote(url)}"
if corpo:
    comando += f" -H 'Content-Type: application/json' -d {shlex.quote(json.dumps(json.loads(corpo), ensure_ascii=False))}"
st.code(comando, language="bash")

if st.button("Enviar requisição", type="primary", icon=":material/send:"):
    try:
        resposta = requests.request(rota["método"], url, json=json.loads(corpo) if corpo else None, timeout=60)
    except (requests.RequestException, json.JSONDecodeError) as exc:
        st.error(str(exc))
    else:
        st.caption(f"Status: **{resposta.status_code}** · {len(resposta.content):,} bytes".replace(",", "."))
        try:
            dados = resposta.json()
        except ValueError:
            st.text(resposta.text[:5000])
        else:
            if isinstance(dados, list) and dados and isinstance(dados[0], dict):
                st.dataframe(pd.json_normalize(dados), hide_index=True, width="stretch")
            st.json(dados, expanded=1)
        if rota["método"] in ("POST", "DELETE") and resposta.ok:
            ui.limpar_cache_medicoes()
