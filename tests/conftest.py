"""Configuração comum dos testes.

As medições enviadas nos testes vão para um CSV temporário (não sujam data/processed/),
e o app usa uma porta própria para a API embutida.
"""

import os
import socket
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="solar_viavel_testes_"))
os.environ["SOLAR_MEDICOES_CSV"] = str(_tmp / "medicoes.csv")

with socket.socket() as _s:
    _s.bind(("127.0.0.1", 0))
    os.environ["SOLAR_API_URL"] = f"http://127.0.0.1:{_s.getsockname()[1]}"
