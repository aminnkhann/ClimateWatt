"""Integration-boundary tests for the Level 2 pipeline runner."""

from types import SimpleNamespace

import pandas as pd

from weather_energy import run_pipeline


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, *_args, **_kwargs):
        return None

    def executemany(self, *_args, **_kwargs):
        return None


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def cursor(self):
        return _Cursor()

    def commit(self):
        return None


def test_run_normalizes_prepared_price_timestamps_before_range_check(monkeypatch):
    """String price timestamps should not raise during weather/price range checks."""
    weather = pd.DataFrame(
        {
            "timestamp_utc": pd.to_datetime(["2025-01-01T00:00:00Z"], utc=True),
            "city": ["Hamburg"],
            "temperature_c": [4.5],
            "relative_humidity_percent": [80],
            "wind_speed_kmh": [12],
            "cloud_cover_percent": [90],
        }
    )
    prices = pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00:00Z"],
            "market_area": ["DE-LU"],
            "electricity_price_eur_mwh": [75.0],
        }
    )
    dataset = pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00:00Z"],
            "city": ["Hamburg"],
            "market_area": ["DE-LU"],
            "temperature_c": [4.5],
            "electricity_price_eur_mwh": [75.0],
        }
    )

    monkeypatch.setattr(
        run_pipeline,
        "get_settings",
        lambda: SimpleNamespace(
            weather_start_date=pd.Timestamp("2025-01-01").date(),
            weather_days=1,
            city="Hamburg",
            latitude=53.5511,
            longitude=9.9937,
            prices_csv="prices.csv",
            database_url="postgresql://example",
        ),
    )
    monkeypatch.setattr(run_pipeline, "fetch_weather", lambda *_args, **_kwargs: weather)
    monkeypatch.setattr(run_pipeline, "read_price_csv", lambda _path: pd.DataFrame())
    monkeypatch.setattr(run_pipeline, "prepare_prices", lambda _frame: prices)
    monkeypatch.setattr(run_pipeline, "build_hourly_dataset", lambda *_args: dataset)
    monkeypatch.setattr(run_pipeline, "initialize_database", lambda _connection: None)
    monkeypatch.setattr(run_pipeline, "load_weather", lambda *_args: None)
    monkeypatch.setattr(run_pipeline, "load_prices", lambda *_args: None)
    monkeypatch.setattr(run_pipeline, "load_analytics", lambda *_args: None)
    monkeypatch.setitem(
        __import__("sys").modules,
        "psycopg",
        SimpleNamespace(connect=lambda _url: _Connection()),
    )

    run_pipeline.run()
