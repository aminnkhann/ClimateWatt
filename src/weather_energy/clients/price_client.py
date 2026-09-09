"""Read and prepare electricity-price CSV data."""

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "timestamp_utc",
    "market_area",
    "electricity_price_eur_mwh",
}


def read_price_csv(path: Path) -> pd.DataFrame:
    """Read a price CSV and ensure that its required columns are present."""
    if not path.exists():
        raise FileNotFoundError(f"Price file does not exist: {path}")

    prices = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(prices.columns)
    if missing:
        raise ValueError(f"Price file is missing required columns: {sorted(missing)}")
    return prices


def prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Normalize prices to one UTC-hourly average per market area."""
    missing = REQUIRED_COLUMNS - set(prices.columns)
    if missing:
        raise ValueError(f"Price data is missing required columns: {sorted(missing)}")

    prepared = prices.copy()
    prepared["timestamp_utc"] = pd.to_datetime(
        prepared["timestamp_utc"], utc=True, errors="coerce"
    )
    prepared["electricity_price_eur_mwh"] = pd.to_numeric(
        prepared["electricity_price_eur_mwh"], errors="coerce"
    )
    prepared = prepared.dropna(
        subset=["timestamp_utc", "market_area", "electricity_price_eur_mwh"]
    )
    prepared["timestamp_utc"] = prepared["timestamp_utc"].dt.floor("h")

    prepared = (
        prepared.groupby(["timestamp_utc", "market_area"], as_index=False, sort=True)
        ["electricity_price_eur_mwh"]
        .mean()
    )
    prepared["timestamp_utc"] = prepared["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return prepared[
        ["timestamp_utc", "market_area", "electricity_price_eur_mwh"]
    ]
