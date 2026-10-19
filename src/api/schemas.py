"""Modelos (Pydantic) de entrada e saída da API: validam os dados e aparecem no /docs."""

from __future__ import annotations

import datetime as dt
from typing import List, Optional

from pydantic import BaseModel, Field


class Local(BaseModel):
    cidade: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    origem: str = Field(description="nasa (capitais coletadas) ou usuario (medições enviadas via POST)")
    dias: int
    inicio: dt.date
    fim: dt.date
    irradiacao_media: float = Field(description="kWh/m²/dia no período")


class RegistroClima(BaseModel):
    date: dt.date
    cidade: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    ALLSKY_SFC_SW_DWN: Optional[float] = Field(None, description="irradiância solar, kWh/m²/dia")
    T2M: Optional[float] = Field(None, description="temperatura a 2 m, °C")
    RH2M: Optional[float] = Field(None, description="umidade relativa, %")
    WS10M: Optional[float] = Field(None, description="vento a 10 m, m/s")
    CLOUD_AMT: Optional[float] = Field(None, description="cobertura de nuvens, %")
    origem: str = "nasa"


class Medicao(BaseModel):
    """Uma medição diária enviada pelo usuário (ex.: de um piranômetro ou do inversor)."""

    date: dt.date
    ALLSKY_SFC_SW_DWN: float = Field(ge=0, le=12, description="irradiância solar, kWh/m²/dia (0 a 12)")
    T2M: Optional[float] = Field(None, ge=-20, le=55)
    RH2M: Optional[float] = Field(None, ge=0, le=100)
    WS10M: Optional[float] = Field(None, ge=0, le=60)
    CLOUD_AMT: Optional[float] = Field(None, ge=0, le=100)


class LoteMedicoes(BaseModel):
    cidade: str = Field(min_length=2, max_length=80, description="nome do local, ex.: 'Meu telhado - Niterói'")
    latitude: Optional[float] = Field(None, ge=-35, le=6)
    longitude: Optional[float] = Field(None, ge=-75, le=-30)
    medicoes: List[Medicao] = Field(min_length=1, max_length=5000)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "cidade": "Meu telhado - Niterói",
                    "latitude": -22.88,
                    "longitude": -43.10,
                    "medicoes": [
                        {"date": "2026-09-01", "ALLSKY_SFC_SW_DWN": 5.2, "T2M": 24.1},
                        {"date": "2026-09-02", "ALLSKY_SFC_SW_DWN": 3.8},
                    ],
                }
            ]
        }
    }


class RespostaMedicoes(BaseModel):
    cidade: str
    recebidas: int
    mensagem: str


class Estimativa(BaseModel):
    cidade: str
    fonte: str
    irradiacao_media: float = Field(description="kWh/m²/dia usada no cálculo")
    potencia_kwp: float
    desempenho: float
    tarifa: float
    geracao_dia_kwh: float
    geracao_mes_kwh: float
    geracao_ano_kwh: float
    economia_mes_rs: float
    economia_ano_rs: float
    observacao: str


class IrradiacaoLongoPrazo(BaseModel):
    cidade: str
    estacao: str
    municipio: str
    uf: str
    distancia_km: float
    plano: str
    inclinacao_graus: int
    mensal: dict = Field(description="irradiação diária média de cada mês, kWh/m²/dia")
    media_anual: float
    delta: float = Field(description="diferença entre o maior e o menor mês")


class Noticia(BaseModel):
    fonte: str
    titulo: str
    categoria: str
    resumo: str
    url: str
    data: Optional[dt.date] = None
    n_palavras: int
    texto: Optional[str] = None


class TrechoContexto(BaseModel):
    id: str
    tipo: str
    fonte: str
    titulo: str
    url: str
    data: str
    cidade: str
    texto: str
    pontuacao: float


class ContextoLLM(BaseModel):
    pergunta: str
    trechos: List[TrechoContexto]
    prompt: str = Field(description="prompt pronto para ser enviado a um LLM (próxima etapa)")
