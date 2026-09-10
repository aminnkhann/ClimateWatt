"""Configuration helpers for the Level 1 scripts."""

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Paths used by the local CSV pipeline."""

    prices_csv: Path
    output_dir: Path
    city: str = "Hamburg"
    latitude: float = 53.5511
    longitude: float = 9.9937
    database_url: str = ""


def get_settings() -> Settings:
    """Return the default repository paths."""
    return Settings(
        prices_csv=BASE_DIR / "data" / "input" / "electricity_prices_sample.csv",
        output_dir=BASE_DIR / "data" / "output",
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql://weather_user:weather_password@localhost:5432/weather_energy",
        ),
    )
