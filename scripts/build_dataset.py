"""Join weather and electricity price data into ``data/output/weather_energy_hourly.csv``.

This script reads the weather and price outputs created by the other Level 1 scripts,
normalizes their timestamps to UTC, joins them on ``timestamp_utc``, and writes the
final hourly dataset.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from weather_energy.config import get_settings
from weather_energy.transform.weather_energy import build_hourly_dataset

REQUIRED_WEATHER_COLUMNS = {"timestamp_utc", "city", "temperature_c"}
REQUIRED_PRICE_COLUMNS = {"timestamp_utc", "market_area", "electricity_price_eur_mwh"}


def load_weather(path: Path) -> pd.DataFrame:
    """Load the weather output and validate the required columns."""
    if not path.exists():
        raise FileNotFoundError(f"Weather file does not exist: {path}")
    weather = pd.read_csv(path)
    missing = REQUIRED_WEATHER_COLUMNS - set(weather.columns)
    if missing:
        raise ValueError(f"Weather file is missing required columns: {sorted(missing)}")

    weather["timestamp_utc"] = pd.to_datetime(
        weather["timestamp_utc"], utc=True, errors="coerce", format="mixed"
    )
    weather["temperature_c"] = pd.to_numeric(weather["temperature_c"], errors="coerce")
    weather = weather.dropna(subset=["timestamp_utc", "city", "temperature_c"])
    return weather


def load_prices(path: Path) -> pd.DataFrame:
    """Load the prepared price output and validate the required columns."""
    if not path.exists():
        raise FileNotFoundError(f"Price file does not exist: {path}")
    prices = pd.read_csv(path)
    missing = REQUIRED_PRICE_COLUMNS - set(prices.columns)
    if missing:
        raise ValueError(f"Price file is missing required columns: {sorted(missing)}")

    prices["timestamp_utc"] = pd.to_datetime(
        prices["timestamp_utc"], utc=True, errors="coerce", format="mixed"
    )
    prices["electricity_price_eur_mwh"] = pd.to_numeric(
        prices["electricity_price_eur_mwh"], errors="coerce"
    )
    prices = prices.dropna(subset=["timestamp_utc", "market_area", "electricity_price_eur_mwh"])
    return prices


def build_dataset(weather: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Join weather and price data on UTC timestamps and keep the final columns."""
    return build_hourly_dataset(weather, prices)


def main() -> None:
    output_dir = get_settings().output_dir
    weather_path = output_dir / "weather.csv"
    prices_path = output_dir / "prices.csv"
    final_path = output_dir / "weather_energy_hourly.csv"

    output_dir.mkdir(parents=True, exist_ok=True)

    weather = load_weather(weather_path)
    prices = load_prices(prices_path)
    final_dataset = build_dataset(weather, prices)

    final_dataset.to_csv(final_path, index=False)
    print(f"Wrote {len(final_dataset)} rows to {final_path}")


if __name__ == "__main__":
    main()
