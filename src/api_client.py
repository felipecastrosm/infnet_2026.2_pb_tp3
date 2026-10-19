"""Cliente HTTP da API FastAPI, usado pelo app Streamlit.

O app não lê os arquivos de data/ diretamente: toda consulta e todo envio de dados
passa pela API. O endereço vem da variável de ambiente SOLAR_API_URL (padrão
http://127.0.0.1:8000).

- Em desenvolvimento, rode a API em um terminal (`uvicorn src.api.main:app --reload`)
  e o app em outro (`streamlit run app.py`).
- Se a API não estiver no ar e o endereço for local, `garantir_api()` sobe a própria
  API em uma thread do processo do Streamlit (útil no deploy do Streamlit Community
  Cloud, que roda um único processo). Mesmo assim o app continua falando com ela por
  HTTP, exatamente como falaria com uma API externa.
"""

from __future__ import annotations

import os
import threading
import time
from urllib.parse import urlparse

import requests

TIMEOUT_S = 60


class ErroAPI(Exception):
    """Erro devolvido pela API (mensagem já pronta para mostrar ao usuário)."""


def url_base() -> str:
    return os.environ.get("SOLAR_API_URL", "http://127.0.0.1:8000").rstrip("/")


def api_no_ar() -> bool:
    try:
        return requests.get(f"{url_base()}/saude", timeout=2).ok
    except requests.RequestException:
        return False


def garantir_api() -> str:
    """Garante que a API responde; devolve 'externa' ou 'embutida' (iniciada aqui)."""
    if api_no_ar():
        return "externa"
    destino = urlparse(url_base())
    if destino.hostname not in ("127.0.0.1", "localhost"):
        raise ErroAPI(f"A API em {url_base()} não respondeu.")

    import uvicorn

    from src.api.main import app

    config = uvicorn.Config(app, host=destino.hostname, port=destino.port or 80, log_level="warning")
    servidor = uvicorn.Server(config)
    servidor.install_signal_handlers = lambda: None  # thread secundária não pode tratar sinais
    threading.Thread(target=servidor.run, daemon=True, name="solar-viavel-api").start()
    for _ in range(100):
        if api_no_ar():
            return "embutida"
        time.sleep(0.1)
    raise ErroAPI("Não foi possível iniciar a API local.")


def _tratar(resposta: requests.Response):
    if resposta.ok:
        return resposta.json()
    try:
        detalhe = resposta.json().get("detail")
    except ValueError:
        detalhe = resposta.text
    if isinstance(detalhe, list):  # erros de validação (422) do FastAPI/Pydantic
        detalhe = "; ".join(f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}" for e in detalhe)
    raise ErroAPI(f"{resposta.status_code}: {detalhe}")


def get(caminho: str, **params):
    try:
        return _tratar(requests.get(f"{url_base()}{caminho}", params=params, timeout=TIMEOUT_S))
    except requests.RequestException as exc:
        raise ErroAPI(f"API indisponível ({exc}).") from exc


def post(caminho: str, dados: dict):
    try:
        return _tratar(requests.post(f"{url_base()}{caminho}", json=dados, timeout=TIMEOUT_S))
    except requests.RequestException as exc:
        raise ErroAPI(f"API indisponível ({exc}).") from exc


def delete(caminho: str):
    try:
        return _tratar(requests.delete(f"{url_base()}{caminho}", timeout=TIMEOUT_S))
    except requests.RequestException as exc:
        raise ErroAPI(f"API indisponível ({exc}).") from exc
