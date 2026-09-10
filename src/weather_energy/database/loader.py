"""Idempotent PostgreSQL loading helpers."""

from collections.abc import Iterable

import pandas as pd

from weather_energy.clients.weather_client import validate_weather


def initialize_database(connection) -> None:
    """Create database objects from the checked-in SQL schema."""
    from pathlib import Path

    schema = Path(__file__).resolve().parents[3] / "sql" / "create_tables.sql"
    with connection.cursor() as cursor:
        cursor.execute(schema.read_text())
    connection.commit()


def _upsert(
    connection, table: str, columns: list[str], keys: list[str], rows: Iterable[tuple]
) -> None:
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"{column}=EXCLUDED.{column}" for column in columns if column not in keys)
    column_list = ", ".join(columns)
    key_list = ", ".join(keys)
    query = (
        f"INSERT INTO {table} ({column_list}) VALUES ({placeholders}) "
        f"ON CONFLICT ({key_list}) DO UPDATE SET {updates}"
        if updates
        else f"INSERT INTO {table} ({column_list}) VALUES ({placeholders}) "
        f"ON CONFLICT ({key_list}) DO NOTHING"
    )
    with connection.cursor() as cursor:
        cursor.executemany(query, rows)


def load_weather(connection, weather: pd.DataFrame) -> int:
    weather = validate_weather(weather)
    columns = [
        "timestamp_utc",
        "city",
        "temperature_c",
        "relative_humidity_percent",
        "wind_speed_kmh",
        "cloud_cover_percent",
    ]
    _upsert(
        connection,
        "raw.weather_hourly",
        columns,
        ["timestamp_utc", "city"],
        weather[columns].itertuples(index=False, name=None),
    )
    return len(weather)


def load_prices(connection, prices: pd.DataFrame) -> None:
    columns = ["timestamp_utc", "market_area", "electricity_price_eur_mwh"]
    _upsert(
        connection,
        "raw.electricity_price_hourly",
        columns,
        ["timestamp_utc", "market_area"],
        prices[columns].itertuples(index=False, name=None),
    )


def load_analytics(connection, dataset: pd.DataFrame) -> None:
    columns = ["timestamp_utc", "city", "market_area", "temperature_c", "electricity_price_eur_mwh"]
    rows = dataset.assign(timestamp_utc=pd.to_datetime(dataset["timestamp_utc"], utc=True))[columns]
    _upsert(
        connection,
        "analytics.weather_energy_hourly",
        columns,
        ["timestamp_utc", "city", "market_area"],
        rows.itertuples(index=False, name=None),
    )
