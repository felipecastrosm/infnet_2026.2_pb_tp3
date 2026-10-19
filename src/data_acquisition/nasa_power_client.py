"""Cliente para a NASA POWER API (dados meteorológicos e de irradiância solar)."""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

try:
    from src.locations import CAPITAIS
except ImportError:  # execução direta do script (python src/data_acquisition/...)
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.locations import CAPITAIS

BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

DEFAULT_PARAMETERS = [
    "ALLSKY_SFC_SW_DWN",
    "T2M",
    "RH2M",
    "WS10M",
    "CLOUD_AMT",
]


def get_power_data(
    lat: float,
    lon: float,
    start: date,
    end: date,
    parameters: list[str] = DEFAULT_PARAMETERS,
    community: str = "RE",
) -> pd.DataFrame:
    """Busca uma série temporal diária da NASA POWER API para um ponto geográfico.

    Retorna um DataFrame indexado por data, com uma coluna por parâmetro.
    Valores ausentes da API (-999) são convertidos para NaN.
    """
    response = requests.get(
        BASE_URL,
        params={
            "parameters": ",".join(parameters),
            "community": community,
            "longitude": lon,
            "latitude": lat,
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()["properties"]["parameter"]

    df = pd.DataFrame(payload)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"
    df = df.replace(-999, pd.NA)
    return df


def collect_capitals(days: int = 365) -> pd.DataFrame:
    """Coleta a série diária dos últimos `days` dias para cada capital em `locations`."""
    end_date = date.today() - timedelta(days=2)  # a NASA tem defasagem de poucos dias
    start_date = end_date - timedelta(days=days)
    frames = []
    for city, (lat, lon) in CAPITAIS.items():
        df = get_power_data(lat, lon, start_date, end_date)
        df.insert(0, "cidade", city)
        df.insert(1, "latitude", lat)
        df.insert(2, "longitude", lon)
        frames.append(df)
        print(f"{city}: {len(df)} dias")
    return pd.concat(frames)


if __name__ == "__main__":
    raw_dir = Path(__file__).resolve().parents[2] / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_path = raw_dir / "nasa_power_capitais.csv"
    collect_capitals().to_csv(output_path)
    print(f"Dados salvos em {output_path}")
