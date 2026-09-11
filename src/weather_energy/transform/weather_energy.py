"""Validation and transformation for the joined weather-energy dataset."""

import numpy as np
import pandas as pd

WEATHER_COLUMNS = {"timestamp_utc", "city", "temperature_c"}
PRICE_COLUMNS = {"timestamp_utc", "market_area", "electricity_price_eur_mwh"}
FINAL_COLUMNS = [
    "timestamp_utc",
    "city",
    "market_area",
    "temperature_c",
    "electricity_price_eur_mwh",
]


def _validate_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{name} data is missing required columns: {sorted(missing)}")


def _parse_utc_timestamps(values: pd.Series) -> pd.Series:
    """Parse mixed ISO timestamp strings to UTC datetimes."""
    return pd.to_datetime(values, utc=True, errors="coerce", format="mixed")


def build_hourly_dataset(weather: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Validate and inner-join weather and prices on UTC timestamps."""
    _validate_columns(weather, WEATHER_COLUMNS, "Weather")
    _validate_columns(prices, PRICE_COLUMNS, "Price")
    weather, prices = weather.copy(), prices.copy()
    for frame in (weather, prices):
        frame["timestamp_utc"] = _parse_utc_timestamps(frame["timestamp_utc"])
    weather["temperature_c"] = pd.to_numeric(weather["temperature_c"], errors="coerce")
    prices["electricity_price_eur_mwh"] = pd.to_numeric(
        prices["electricity_price_eur_mwh"], errors="coerce"
    )
    weather["city"] = weather["city"].astype("string").str.strip()
    prices["market_area"] = prices["market_area"].astype("string").str.strip()
    weather = weather[np.isfinite(weather["temperature_c"])]
    prices = prices[np.isfinite(prices["electricity_price_eur_mwh"])]
    weather = weather[weather["city"] != ""]
    prices = prices[prices["market_area"] != ""]
    weather = weather.dropna(subset=["timestamp_utc", "city", "temperature_c"])
    prices = prices.dropna(subset=["timestamp_utc", "market_area", "electricity_price_eur_mwh"])
    if weather.duplicated(["timestamp_utc", "city"]).any():
        raise ValueError("Weather data contains duplicate business keys")
    if prices.duplicated(["timestamp_utc", "market_area"]).any():
        raise ValueError("Price data contains duplicate business keys")
    result = weather.merge(prices, on="timestamp_utc", how="inner", validate="many_to_many")
    if result.empty:
        raise ValueError("Weather and price data have no shared timestamp_utc values")
    result = result[FINAL_COLUMNS].sort_values("timestamp_utc")
    if result.duplicated(["timestamp_utc", "city", "market_area"]).any():
        raise ValueError("Final dataset contains duplicate business keys")
    result["timestamp_utc"] = result["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return result.reset_index(drop=True)
