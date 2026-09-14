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
from weather_energy.database.loader import (
    initialize_database,
    load_analytics,
    load_prices,
    load_weather,
)
from weather_energy.transform.weather_energy import build_hourly_dataset

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
    """Stage the requested market/window, validating its rows before aggregation.

    Unparseable timestamps in the requested market fail because their window
    cannot be determined. Rows belonging to other markets are ignored entirely.
    """
    market_area = market_area.strip()
    if not market_area:
        raise ValueError("Market area must not be empty")
    start, end = _interval(start, end)
    raw = normalize_columns(read_price_csv(Path(prices_csv)))
    validate_columns(raw)
    raw = raw.copy()
    raw["market_area"] = raw["market_area"].astype("string").str.strip()
    raw = raw.loc[raw["market_area"].eq(market_area)].copy()
    timestamps = parse_timestamp_series(raw["timestamp_utc"], raw["market_area"])
    if timestamps.isna().any():
        raise ValueError("Invalid price timestamps in requested market; cannot determine interval")
    # Resolve local/DST timestamps once, preserving source order, then narrow
    # the window before validating prices or duplicate business keys.
    raw["timestamp_utc"] = timestamps
    raw = raw.loc[timestamps.ge(start) & timestamps.lt(end)].copy()
    values = pd.to_numeric(raw["electricity_price_eur_mwh"].map(normalize_price), errors="coerce")
    if not values.map(math.isfinite).all():
        raise ValueError("Invalid electricity price values")
    if raw.duplicated(["timestamp_utc", "market_area"]).any():
        raise ValueError("Duplicate source price business keys")
    selected = raw["timestamp_utc"].sort_values()
    # Any sub-hourly row identifies quarter-hour input for this interval.
    # Validate before aggregation, which would otherwise hide missing quarters.
    if (selected != selected.dt.floor("h")).any():
        expected = pd.date_range(start, end, freq="15min", inclusive="left")
        if not pd.DatetimeIndex(selected).equals(expected):
            raise ValueError("incomplete or misaligned 15-minute price data")
    prices = _coverage(_validate_prices(prepare_prices(raw)), start, end,
                       "market_area", market_area)
    return _write(prices, staging_dir, "prices-", start, end, market_area)


def initialize_database_task(*, database_url):
    """Create the pipeline schemas before any raw-load task runs.

    ``initialize_database`` is idempotent, so this is safe for every DAG run
    and also supports databases that were not created through Docker Compose.
    """
    with psycopg.connect(database_url) as connection:
        initialize_database(connection)
    LOGGER.info("Initialized weather-energy database schema")


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


def _read_raw_frame(connection, table, columns, start, end, key, value):
    column_list = ", ".join(columns)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {column_list}
            FROM {table}
            WHERE {key} = %s AND timestamp_utc >= %s AND timestamp_utc < %s
            ORDER BY timestamp_utc
            """,
            (value, start.to_pydatetime(), end.to_pydatetime()),
        )
        return pd.DataFrame(cursor.fetchall(), columns=columns)


def build_analytics_task(start, end, *, database_url, city="Hamburg", market_area="DE-LU"):
    """Join loaded raw rows for the interval and upsert analytics rows."""
    city = city.strip()
    market_area = market_area.strip()
    if not city:
        raise ValueError("City must not be empty")
    if not market_area:
        raise ValueError("Market area must not be empty")
    start, end = _interval(start, end)
    weather_columns = [
        "timestamp_utc",
        "city",
        "temperature_c",
        "relative_humidity_percent",
        "wind_speed_kmh",
        "cloud_cover_percent",
    ]
    price_columns = ["timestamp_utc", "market_area", "electricity_price_eur_mwh"]
    with psycopg.connect(database_url) as connection:
        initialize_database(connection)
        weather = _read_raw_frame(
            connection, "raw.weather_hourly", weather_columns, start, end, "city", city,
        )
        prices = _read_raw_frame(
            connection,
            "raw.electricity_price_hourly",
            price_columns,
            start,
            end,
            "market_area",
            market_area,
        )
        weather = _coverage(validate_weather(weather), start, end, "city", city)
        prices = _coverage(_validate_prices(prices), start, end, "market_area", market_area)
        dataset = build_hourly_dataset(weather, prices)
        load_analytics(connection, dataset)
    LOGGER.info("Loaded analytics city=%s market=%s start=%s end=%s rows=%d",
                city, market_area, start, end, len(dataset))
    return len(dataset)


def validate_analytics_task(start, end, *, database_url, city="Hamburg", market_area="DE-LU"):
    """Fail if the analytics interval is incomplete or has duplicate business keys."""
    city = city.strip()
    market_area = market_area.strip()
    if not city:
        raise ValueError("City must not be empty")
    if not market_area:
        raise ValueError("Market area must not be empty")
    start, end = _interval(start, end)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT timestamp_utc, city, market_area, temperature_c, electricity_price_eur_mwh
                FROM analytics.weather_energy_hourly
                WHERE city = %s AND market_area = %s
                  AND timestamp_utc >= %s AND timestamp_utc < %s
                ORDER BY timestamp_utc
                """,
                (city, market_area, start.to_pydatetime(), end.to_pydatetime()),
            )
            rows = cursor.fetchall()
    dataset = pd.DataFrame(
        rows,
        columns=[
            "timestamp_utc",
            "city",
            "market_area",
            "temperature_c",
            "electricity_price_eur_mwh",
        ],
    )
    _coverage(dataset, start, end, "city", city)
    _coverage(dataset, start, end, "market_area", market_area)
    if dataset.duplicated(["timestamp_utc", "city", "market_area"]).any():
        raise ValueError("Duplicate analytics business keys")
    LOGGER.info("Validated analytics city=%s market=%s start=%s end=%s rows=%d",
                city, market_area, start, end, len(dataset))
    return len(dataset)
