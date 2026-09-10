"""Configuration helpers for the Level 1 scripts."""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.city")


def _env(name: str, default: str) -> str:
    """Return a non-empty environment value or its default."""
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_float(name: str, default: float) -> float:
    """Return a float from the environment with a clear error message."""
    value = _env(name, str(default))
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number, got {value!r}") from error


def _env_int(name: str, default: int) -> int:
    """Return a positive integer from the environment."""
    value = _env(name, str(default))
    try:
        result = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer, got {value!r}") from error
    if result < 1:
        raise ValueError(f"{name} must be at least 1")
    return result


def _env_date(name: str, default: date) -> date:
    """Return an ISO date from the environment."""
    value = _env(name, default.isoformat())
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must use YYYY-MM-DD format, got {value!r}") from error


def _database_url() -> str:
    """Use DATABASE_URL or build one from the PostgreSQL environment values."""
    configured_url = os.getenv("DATABASE_URL")
    if configured_url and configured_url.strip():
        return configured_url.strip()

    user = _env("POSTGRES_USER", "weather_user")
    password = _env("POSTGRES_PASSWORD", "weather_password")
    host = _env("POSTGRES_HOST", "localhost")
    port = _env("POSTGRES_PORT", "5442")
    database = _env("POSTGRES_DB", "weather_energy")
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(database)}"
    )

@dataclass(frozen=True)
class Settings:
    """Paths used by the local CSV pipeline."""

    prices_csv: Path
    output_dir: Path
    city: str = "Hamburg"
    latitude: float = 53.5511
    longitude: float = 9.9937
    weather_start_date: date = date(2025, 1, 1)
    weather_days: int = 180
    database_url: str = ""


def get_settings() -> Settings:
    """Return settings from general and city-specific environment files.

    Database and path settings come from ``.env``. Location settings are kept
    separately in ``.env.city`` so changing the city does not require editing
    application code. Explicit shell environment variables still take priority.
    """
    return Settings(
        prices_csv=Path(_env(
            "PRICES_CSV",
            str(BASE_DIR / "data" / "input" / "electricity_prices_sample.csv"),
        )),
        output_dir=Path(_env("OUTPUT_DIR", str(BASE_DIR / "data" / "output"))),
        city=_env("CITY_NAME", "Hamburg"),
        latitude=_env_float("CITY_LATITUDE", 53.5511),
        longitude=_env_float("CITY_LONGITUDE", 9.9937),
        weather_start_date=_env_date("WEATHER_START_DATE", date(2025, 1, 1)),
        weather_days=_env_int("WEATHER_DAYS", 180),
        database_url=_database_url(),
    )
