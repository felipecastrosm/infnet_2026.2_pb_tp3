"""Testes da API FastAPI (rotas GET, POST e DELETE)."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.data_acquisition import nasa_power_client
from src.data_processing import climate

client = TestClient(app)


@pytest.fixture(autouse=True)
def sem_medicoes():
    """Cada teste começa sem medições de usuários."""
    for local in {m["cidade"] for m in client.get("/medicoes").json()}:
        client.delete(f"/medicoes/{local}")


def test_saude_e_documentacao():
    assert client.get("/saude").json() == {"status": "ok"}
    spec = client.get("/openapi.json").json()
    assert {"/locais", "/clima", "/estimativa", "/noticias", "/medicoes", "/llm/contexto"} <= set(spec["paths"])


def test_locais_lista_as_capitais():
    locais = client.get("/locais").json()
    assert len(locais) == 10
    assert {"cidade", "irradiacao_media", "inicio", "fim"} <= set(locais[0])
    medias = [loc["irradiacao_media"] for loc in locais]
    assert medias == sorted(medias, reverse=True)


def test_clima_filtra_por_cidade_e_periodo():
    resp = client.get("/clima", params={"cidade": ["Recife (PE)", "Manaus (AM)"], "inicio": "2026-01-01", "fim": "2026-01-31"})
    assert resp.status_code == 200
    df = pd.DataFrame(resp.json())
    assert set(df["cidade"]) == {"Recife (PE)", "Manaus (AM)"}
    assert len(df) == 62
    assert df["date"].min() == "2026-01-01" and df["date"].max() == "2026-01-31"


def test_clima_local_inexistente_da_404():
    resp = client.get("/clima", params={"cidade": "Atlântida"})
    assert resp.status_code == 404
    assert "Atlântida" in resp.json()["detail"]


def test_irradiacao_longo_prazo():
    resp = client.get("/irradiacao-longo-prazo", params={"cidade": "Curitiba (PR)", "plano": "Maior média anual"})
    [dado] = resp.json()
    assert dado["estacao"] == "Curitiba"
    assert list(dado["mensal"]) == climate.MESES
    assert dado["inclinacao_graus"] > 15  # no Sul, a inclinação ótima é alta


@pytest.mark.parametrize("fonte", ["cresesb", "nasa"])
def test_estimativa(fonte):
    params = {"cidade": "Fortaleza (CE)", "potencia_kwp": 4, "desempenho": 0.8, "tarifa": 1.0, "fonte": fonte}
    est = client.get("/estimativa", params=params).json()
    assert est["geracao_dia_kwh"] == pytest.approx(est["irradiacao_media"] * 4 * 0.8, rel=0.02)
    assert est["economia_ano_rs"] == pytest.approx(est["geracao_ano_kwh"], rel=0.01)


def test_estimativa_valida_parametros():
    assert client.get("/estimativa", params={"cidade": "Fortaleza (CE)", "potencia_kwp": -1}).status_code == 422


def test_noticias_busca_e_fontes():
    todas = client.get("/noticias", params={"limite": 500}).json()
    assert {n["fonte"] for n in todas} == {"ABSOLAR", "Canal Solar"}
    assert todas[0]["texto"] is None  # texto completo só com incluir_texto=true
    filtradas = client.get("/noticias", params={"busca": "baterias", "incluir_texto": True}).json()
    assert filtradas and all("bateria" in (n["titulo"] + n["resumo"] + n["texto"]).lower() for n in filtradas)


def test_post_get_delete_medicoes():
    lote = {
        "cidade": "Meu telhado",
        "latitude": -22.9,
        "longitude": -43.1,
        "medicoes": [
            {"date": "2026-09-01", "ALLSKY_SFC_SW_DWN": 5.2, "T2M": 24.0},
            {"date": "2026-09-02", "ALLSKY_SFC_SW_DWN": 3.9},
        ],
    }
    resp = client.post("/medicoes", json=lote)
    assert resp.status_code == 201
    assert resp.json()["recebidas"] == 2

    assert "Meu telhado" in {loc["cidade"] for loc in client.get("/locais").json()}
    serie = client.get("/clima", params={"cidade": "Meu telhado"}).json()
    assert [r["ALLSKY_SFC_SW_DWN"] for r in serie] == [5.2, 3.9]
    assert serie[0]["origem"] == "usuario"

    # reenviar a mesma data substitui o valor anterior
    client.post("/medicoes", json={**lote, "medicoes": [{"date": "2026-09-02", "ALLSKY_SFC_SW_DWN": 4.4}]})
    assert [r["ALLSKY_SFC_SW_DWN"] for r in client.get("/medicoes").json()] == [5.2, 4.4]

    assert client.delete("/medicoes/Meu telhado").json()["removidas"] == 2
    assert client.get("/medicoes").json() == []
    assert client.delete("/medicoes/Meu telhado").status_code == 404


@pytest.mark.parametrize(
    "lote",
    [
        {"cidade": "X", "medicoes": [{"date": "2026-09-01", "ALLSKY_SFC_SW_DWN": 5}]},  # nome curto
        {"cidade": "Meu local", "medicoes": []},  # sem medições
        {"cidade": "Meu local", "medicoes": [{"date": "2026-09-01", "ALLSKY_SFC_SW_DWN": 50}]},  # irradiância impossível
        {"cidade": "Meu local", "medicoes": [{"date": "ontem", "ALLSKY_SFC_SW_DWN": 5}]},  # data inválida
    ],
)
def test_post_medicoes_invalidas(lote):
    assert client.post("/medicoes", json=lote).status_code == 422


def test_post_nao_sobrescreve_capital():
    lote = {"cidade": "Recife (PE)", "medicoes": [{"date": "2026-09-01", "ALLSKY_SFC_SW_DWN": 5}]}
    assert client.post("/medicoes", json=lote).status_code == 409


def test_clima_ao_vivo(monkeypatch):
    def api_falsa(lat, lon, start, end, *args, **kwargs):
        return pd.DataFrame({v: 5.0 for v in climate.VARIAVEIS}, index=pd.date_range(start, end, name="date"))

    monkeypatch.setattr(nasa_power_client, "get_power_data", api_falsa)
    dados = client.get("/clima/ao-vivo", params={"latitude": -10, "longitude": -50, "dias": 30, "nome": "Palmas"}).json()
    assert len(dados) == 31
    assert dados[0]["cidade"] == "Palmas (ao vivo)"


def test_llm_contexto_monta_prompt():
    resp = client.get("/llm/contexto", params={"pergunta": "leilão de baterias", "k": 3}).json()
    assert 0 < len(resp["trechos"]) <= 3
    assert "leilão" in resp["trechos"][0]["texto"].lower()
    assert "leilão de baterias" in resp["prompt"] and "[1]" in resp["prompt"]
