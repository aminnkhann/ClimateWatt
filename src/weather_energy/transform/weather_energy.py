"""Validation and transformation for the joined weather-energy dataset."""

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


def build_hourly_dataset(weather: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Validate and inner-join weather and prices on UTC timestamps."""
    _validate_columns(weather, WEATHER_COLUMNS, "Weather")
    _validate_columns(prices, PRICE_COLUMNS, "Price")
    weather, prices = weather.copy(), prices.copy()
    for frame in (weather, prices):
        frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True, errors="coerce")
    weather["temperature_c"] = pd.to_numeric(weather["temperature_c"], errors="coerce")
    prices["electricity_price_eur_mwh"] = pd.to_numeric(
        prices["electricity_price_eur_mwh"], errors="coerce"
    )
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
