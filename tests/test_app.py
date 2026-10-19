"""Testes do app Streamlit com múltiplas páginas (Streamlit AppTest).

O app sobe a API embutida (porta definida em conftest.py) e consome os dados por HTTP.
"""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.data_acquisition import nasa_power_client
from src.data_processing import climate

PAGINAS = [
    "paginas/inicio.py",
    "paginas/clima.py",
    "paginas/longo_prazo.py",
    "paginas/noticias.py",
    "paginas/meus_dados.py",
    "paginas/api.py",
    "paginas/ia.py",
]


def abrir(pagina: str = None) -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=60).run()
    if pagina:
        at.switch_page(pagina).run()
    return at


@pytest.fixture
def nasa_falsa(monkeypatch):
    def api_falsa(lat, lon, start, end, *args, **kwargs):
        return pd.DataFrame({v: 5.0 for v in climate.VARIAVEIS}, index=pd.date_range(start, end, name="date"))

    monkeypatch.setattr(nasa_power_client, "get_power_data", api_falsa)


@pytest.mark.parametrize("pagina", PAGINAS)
def test_todas_as_paginas_abrem_sem_erro(pagina):
    at = abrir(pagina)
    assert not at.exception
    assert not at.error
    assert at.title  # cada página tem seu título


def test_menu_de_navegacao_tem_todas_as_paginas():
    from pathlib import Path

    app = Path("app.py").read_text()
    assert "st.navigation(" in app
    assert all(p in app for p in PAGINAS)


def test_parametros_persistem_entre_paginas():
    at = abrir("paginas/clima.py")
    at.number_input(key="potencia").set_value(10.0).run()
    at.switch_page("paginas/noticias.py").run()  # página sem esses widgets
    at.switch_page("paginas/longo_prazo.py").run()
    assert not at.exception
    assert at.number_input(key="potencia").value == 10.0


def test_clima_interativo():
    at = abrir("paginas/clima.py")
    at.checkbox(key="suavizar").uncheck().run()
    at.selectbox(key="variavel").select("T2M").run()
    assert not at.exception
    assert at.session_state["suavizar"] is False


def test_consulta_ao_vivo_preserva_estado_e_selecao(nasa_falsa):
    """Regressões do TP2: a consulta não pode resetar widgets nem a seleção de locais."""
    at = abrir("paginas/clima.py")
    at.checkbox(key="suavizar").uncheck().run()
    at.multiselect(key="cidades").set_value(["Recife (PE)", "Manaus (AM)"]).run()

    [b for b in at.button if "NASA" in b.label][0].click().run()

    assert not at.exception
    assert at.session_state["suavizar"] is False
    selecionadas = at.multiselect(key="cidades").value
    assert "Recife (PE)" in selecionadas and "Manaus (AM)" in selecionadas
    assert any("ao vivo" in c for c in selecionadas)  # o novo local entra selecionado


def test_medicao_manual_e_enviada_para_a_api():
    from src import api_client

    at = abrir("paginas/meus_dados.py")
    form = at.get("form")[0]
    form.text_input[0].set_value("Telhado de teste")
    form.number_input[0].set_value(6.5)
    [b for b in at.button if b.label == "Enviar medição"][0].click().run()
    assert not at.exception

    salvas = api_client.get("/medicoes", cidade="Telhado de teste")
    assert [m["ALLSKY_SFC_SW_DWN"] for m in salvas] == [6.5]
    api_client.delete("/medicoes/Telhado de teste")


def test_pagina_ia_recupera_contexto():
    at = abrir("paginas/ia.py")
    assert not at.exception
    assert any("Prompt" in e.label for e in at.expander)
