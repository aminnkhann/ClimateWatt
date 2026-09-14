"""Airflow-callable ingestion tasks; importing this module performs no I/O.

Intervals are timezone-aware, half-open UTC ranges [start, end). Each fetch
returns a CSV path in shared storage, suitable for passing through XCom.
"""

import logging
import math
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import psycopg

from weather_energy.clients.price_client import (
    normalize_columns,
    normalize_price,
    parse_timestamp_series,
    prepare_prices,
    read_price_csv,
    validate_columns,
)
from weather_energy.clients.weather_client import fetch_weather, validate_weather
from weather_energy.database.loader import load_prices, load_weather

LOGGER = logging.getLogger(__name__)


def _interval(start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if pd.isna(start) or pd.isna(end) or start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Processing interval requires timezone-aware timestamps")
    start, end = start.tz_convert("UTC"), end.tz_convert("UTC")
    if start >= end or start != start.floor("h") or end != end.floor("h"):
        raise ValueError("Processing interval must be increasing and aligned to hours")
    return start, end


def _coverage(frame, start, end, key, value):
    frame = frame.copy()
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True, errors="raise")
    if frame["timestamp_utc"].isna().any():
        raise ValueError("Missing timestamps")
    frame = frame.loc[
        (frame[key] == value)
        & (frame["timestamp_utc"] >= start)
        & (frame["timestamp_utc"] < end)
    ].copy()
    if frame.duplicated(["timestamp_utc", key]).any():
        raise ValueError("Duplicate hourly business keys")
    expected = pd.date_range(start, end, freq="h", inclusive="left")
    actual = pd.DatetimeIndex(frame["timestamp_utc"].sort_values())
    if not actual.equals(expected):
        raise ValueError(f"Incomplete hourly coverage for {key}={value}: {start} to {end}")
    return frame.sort_values("timestamp_utc").reset_index(drop=True)


def _write(frame, staging_dir, prefix, start, end, identity):
    directory = Path(staging_dir)
    directory.mkdir(parents=True, exist_ok=True)
    # Unique artifacts isolate concurrent DAG runs and retry attempts. A failed
    # write never returns a reference, so downstream tasks cannot consume it.
    with NamedTemporaryFile(mode="w", suffix=".csv", prefix=prefix, dir=directory,
                            delete=False) as artifact:
        path = Path(artifact.name)
        try:
            frame.to_csv(artifact, index=False)
        except Exception:
            path.unlink(missing_ok=True)
            raise
    LOGGER.info("Staged %s start=%s end=%s rows=%d", identity, start, end, len(frame))
    return str(path.resolve())


def fetch_weather_task(start, end, staging_dir, *, city="Hamburg",
                       latitude=53.5511, longitude=9.9937):
    """Fetch and stage complete weather; transient request errors propagate."""
    start, end = _interval(start, end)
    city = city.strip()
    if not city:
        raise ValueError("City must not be empty")
    weather = fetch_weather(
        start.date(), (end - pd.Timedelta(1, unit="h")).date(),
        city=city, latitude=latitude, longitude=longitude,
    )
    weather = _coverage(validate_weather(weather), start, end, "city", city)
    return _write(weather, staging_dir, "weather-", start, end, city)


def _validate_prices(prices):
    validate_columns(prices)
    prices = prices.copy()
    prices["electricity_price_eur_mwh"] = pd.to_numeric(
        prices["electricity_price_eur_mwh"], errors="coerce"
    )
    if not prices["electricity_price_eur_mwh"].map(math.isfinite).all():
        raise ValueError("Invalid electricity price values")
    return prices


def fetch_prices_task(start, end, staging_dir, *, prices_csv, market_area="DE-LU"):
    """Stage hourly prices, rejecting invalid source rows before aggregation."""
    market_area = market_area.strip()
    if not market_area:
        raise ValueError("Market area must not be empty")
    start, end = _interval(start, end)
    raw = normalize_columns(read_price_csv(Path(prices_csv)))
    validate_columns(raw)
    raw = raw.copy()
    raw["market_area"] = raw["market_area"].astype("string").str.strip()
    if raw["market_area"].isna().any() or raw["market_area"].eq("").any():
        raise ValueError("Missing market area")
    timestamps = parse_timestamp_series(raw["timestamp_utc"], raw["market_area"])
    if timestamps.isna().any():
        raise ValueError("Invalid price timestamps")
    values = pd.to_numeric(raw["electricity_price_eur_mwh"].map(normalize_price), errors="coerce")
    if not values.map(math.isfinite).all():
        raise ValueError("Invalid electricity price values")
    if raw.assign(timestamp_utc=timestamps).duplicated(["timestamp_utc", "market_area"]).any():
        raise ValueError("Duplicate source price business keys")
    selected = timestamps.loc[
        raw["market_area"].eq(market_area) & timestamps.ge(start) & timestamps.lt(end)
    ].sort_values()
    # Any sub-hourly row identifies quarter-hour input for this interval.
    # Validate before aggregation, which would otherwise hide missing quarters.
    if (selected != selected.dt.floor("h")).any():
        expected = pd.date_range(start, end, freq="15min", inclusive="left")
        if not pd.DatetimeIndex(selected).equals(expected):
            raise ValueError("incomplete or misaligned 15-minute price data")
    prices = _coverage(_validate_prices(prepare_prices(raw)), start, end,
                       "market_area", market_area)
    return _write(prices, staging_dir, "prices-", start, end, market_area)


def load_weather_raw_task(artifact, start, end, *, database_url, city="Hamburg"):
    """Validate staged weather and commit its upsert in one transaction."""
    city = city.strip()
    if not city:
        raise ValueError("City must not be empty")
    start, end = _interval(start, end)
    weather = _coverage(validate_weather(pd.read_csv(artifact)), start, end, "city", city)
    with psycopg.connect(database_url) as connection:
        load_weather(connection, weather)
    LOGGER.info("Loaded weather city=%s start=%s end=%s rows=%d", city, start, end, len(weather))
    return len(weather)


def load_prices_raw_task(artifact, start, end, *, database_url, market_area="DE-LU"):
    """Validate staged prices and commit their upsert in one transaction."""
    market_area = market_area.strip()
    if not market_area:
        raise ValueError("Market area must not be empty")
    start, end = _interval(start, end)
    prices = _coverage(_validate_prices(pd.read_csv(artifact)), start, end,
                       "market_area", market_area)
    with psycopg.connect(database_url) as connection:
        load_prices(connection, prices)
    LOGGER.info("Loaded prices market=%s start=%s end=%s rows=%d",
                market_area, start, end, len(prices))
    return len(prices)
