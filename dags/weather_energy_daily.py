"""Daily Airflow DAG for the weather-energy pipeline."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from airflow.decorators import dag, task
from airflow.operators.python import get_current_context

from weather_energy.config import get_settings
from weather_energy.ingestion_tasks import (
    build_analytics_task,
    fetch_prices_task,
    fetch_weather_task,
    load_prices_raw_task,
    load_weather_raw_task,
    validate_analytics_task,
)


def _processing_interval() -> tuple[str, str]:
    context = get_current_context()
    start = context["data_interval_start"].in_timezone("UTC")
    end = context["data_interval_end"].in_timezone("UTC")
    return start.to_iso8601_string(), end.to_iso8601_string()


@dag(
    dag_id="weather_energy_daily",
    description="Fetch, load, transform, and validate daily weather-energy data.",
    schedule="0 2 * * *",
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=15),
    },
    tags=["weather-energy", "level3"],
)
def weather_energy_daily():
    @task
    def fetch_weather() -> str:
        settings = get_settings()
        start, end = _processing_interval()
        staging_dir = os.getenv("AIRFLOW_STAGING_DIR", "/tmp/weather-energy-staging")
        return fetch_weather_task(
            start,
            end,
            staging_dir,
            city=settings.city,
            latitude=settings.latitude,
            longitude=settings.longitude,
        )

    @task
    def fetch_prices() -> str:
        settings = get_settings()
        start, end = _processing_interval()
        staging_dir = os.getenv("AIRFLOW_STAGING_DIR", "/tmp/weather-energy-staging")
        return fetch_prices_task(
            start,
            end,
            staging_dir,
            prices_csv=settings.prices_csv,
            market_area=os.getenv("MARKET_AREA", "DE-LU"),
        )

    @task
    def load_weather_raw(artifact: str) -> int:
        settings = get_settings()
        start, end = _processing_interval()
        return load_weather_raw_task(
            artifact,
            start,
            end,
            database_url=settings.database_url,
            city=settings.city,
        )

    @task
    def load_prices_raw(artifact: str) -> int:
        settings = get_settings()
        start, end = _processing_interval()
        return load_prices_raw_task(
            artifact,
            start,
            end,
            database_url=settings.database_url,
            market_area=os.getenv("MARKET_AREA", "DE-LU"),
        )

    @task
    def build_analytics(_weather_rows: int, _price_rows: int) -> int:
        settings = get_settings()
        start, end = _processing_interval()
        return build_analytics_task(
            start,
            end,
            database_url=settings.database_url,
            city=settings.city,
            market_area=os.getenv("MARKET_AREA", "DE-LU"),
        )

    @task
    def validate_analytics(_analytics_rows: int) -> int:
        settings = get_settings()
        start, end = _processing_interval()
        return validate_analytics_task(
            start,
            end,
            database_url=settings.database_url,
            city=settings.city,
            market_area=os.getenv("MARKET_AREA", "DE-LU"),
        )

    weather_artifact = fetch_weather()
    price_artifact = fetch_prices()
    weather_rows = load_weather_raw(weather_artifact)
    price_rows = load_prices_raw(price_artifact)
    analytics_rows = build_analytics(weather_rows, price_rows)
    validate_analytics(analytics_rows)


weather_energy_daily()
