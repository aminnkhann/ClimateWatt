"""Join weather and electricity price data into ``data/output/weather_energy_hourly.csv``.

This script reads the weather and price outputs created by the other Level 1 scripts,
normalizes their timestamps to UTC, joins them on ``timestamp_utc``, and writes the
final hourly dataset.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output"
WEATHER_PATH = OUTPUT_DIR / "weather.csv"
PRICES_PATH = OUTPUT_DIR / "prices.csv"
FINAL_PATH = OUTPUT_DIR / "weather_energy_hourly.csv"

REQUIRED_WEATHER_COLUMNS = {"timestamp_utc", "city", "temperature_c"}
REQUIRED_PRICE_COLUMNS = {"timestamp_utc", "market_area", "electricity_price_eur_mwh"}
FINAL_COLUMNS = [
    "timestamp_utc",
    "city",
    "market_area",
    "temperature_c",
    "electricity_price_eur_mwh",
]


def load_weather(path: Path) -> pd.DataFrame:
    """Load the weather output and validate the required columns."""
    if not path.exists():
        raise FileNotFoundError(f"Weather file does not exist: {path}")
    weather = pd.read_csv(path)
    missing = REQUIRED_WEATHER_COLUMNS - set(weather.columns)
    if missing:
        raise ValueError(f"Weather file is missing required columns: {sorted(missing)}")

    weather["timestamp_utc"] = pd.to_datetime(weather["timestamp_utc"], utc=True, errors="coerce")
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

    prices["timestamp_utc"] = pd.to_datetime(prices["timestamp_utc"], utc=True, errors="coerce")
    prices["electricity_price_eur_mwh"] = pd.to_numeric(
        prices["electricity_price_eur_mwh"], errors="coerce"
    )
    prices = prices.dropna(subset=["timestamp_utc", "market_area", "electricity_price_eur_mwh"])
    return prices


def build_dataset(weather: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Join weather and price data on UTC timestamps and keep the final columns."""
    if weather.duplicated(subset=["timestamp_utc", "city"]).any():
        raise ValueError("Weather data contains duplicate timestamp_utc and city values")
    if prices.duplicated(subset=["timestamp_utc", "market_area"]).any():
        raise ValueError("Price data contains duplicate timestamp_utc and market_area values")

    merged = weather.merge(prices, on="timestamp_utc", how="inner", validate="one_to_one")
    if merged.empty:
        raise ValueError("Weather and price data have no shared timestamp_utc values")

    merged = merged.loc[:, FINAL_COLUMNS].copy()
    merged = merged.dropna(subset=FINAL_COLUMNS)
    merged = merged.sort_values("timestamp_utc").drop_duplicates(subset=["timestamp_utc"])
    if merged["timestamp_utc"].duplicated().any():
        raise ValueError("Final dataset contains duplicate timestamp_utc values")
    merged["timestamp_utc"] = pd.to_datetime(merged["timestamp_utc"], utc=True).dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return merged


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    weather = load_weather(WEATHER_PATH)
    prices = load_prices(PRICES_PATH)
    final_dataset = build_dataset(weather, prices)

    final_dataset.to_csv(FINAL_PATH, index=False)
    print(f"Wrote {len(final_dataset)} rows to {FINAL_PATH}")


if __name__ == "__main__":
    main()
