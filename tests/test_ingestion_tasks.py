"""Tests of the Level 3 ingestion boundary without network or Airflow."""

from contextlib import contextmanager
from datetime import date

import pandas as pd
import pytest
import requests

from weather_energy import ingestion_tasks as tasks

START = "2025-01-01T00:00:00Z"
END = "2025-01-02T00:00:00Z"


@pytest.fixture
def prices(tmp_path):
    frame = pd.DataFrame({
        "timestamp_utc": pd.date_range(START, periods=24, freq="h"),
        "market_area": "DE-LU",
        "electricity_price_eur_mwh": -5.0,
    })
    path = tmp_path / "input.csv"
    frame.to_csv(path, index=False)
    return path


@pytest.fixture
def weather():
    return pd.DataFrame({
        "timestamp_utc": pd.date_range(START, periods=24, freq="h"),
        "city": "Hamburg", "temperature_c": 4.0,
        "relative_humidity_percent": 80, "wind_speed_kmh": 10,
        "cloud_cover_percent": 50,
    })


def test_weather_dates_and_artifact_isolation(monkeypatch, tmp_path, weather):
    calls = []

    def fetch(start, end, **kwargs):
        calls.append((start, end))
        return weather

    monkeypatch.setattr(tasks, "fetch_weather", fetch)
    first = tasks.fetch_weather_task(START, END, tmp_path)
    second = tasks.fetch_weather_task(START, END, tmp_path)
    assert first != second
    assert calls == [(date(2025, 1, 1), date(2025, 1, 1))] * 2
    assert len(pd.read_csv(first)) == 24


def test_weather_failure_can_be_retried(monkeypatch, tmp_path, weather):
    attempts = iter([requests.Timeout("temporary"), weather])

    def fetch(*args, **kwargs):
        result = next(attempts)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(tasks, "fetch_weather", fetch)
    with pytest.raises(requests.Timeout):
        tasks.fetch_weather_task(START, END, tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert len(pd.read_csv(tasks.fetch_weather_task(START, END, tmp_path))) == 24


def test_invalid_weather_is_not_staged(monkeypatch, tmp_path, weather):
    weather.loc[0, "temperature_c"] = float("nan")
    monkeypatch.setattr(tasks, "fetch_weather", lambda *a, **kw: weather)
    with pytest.raises(ValueError, match="invalid required values"):
        tasks.fetch_weather_task(START, END, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_negative_prices_and_period_filtering(tmp_path, prices):
    artifact = tasks.fetch_prices_task(START, "2025-01-01T02:00:00Z", tmp_path,
                                      prices_csv=prices)
    result = pd.read_csv(artifact)
    assert len(result) == 2
    assert result.electricity_price_eur_mwh.tolist() == [-5.0, -5.0]


@pytest.mark.parametrize("problem", ["timestamp", "gap", "duplicate", "value"])
def test_invalid_prices_fail(tmp_path, prices, problem):
    frame = pd.read_csv(prices)
    if problem == "timestamp":
        frame.loc[0, "timestamp_utc"] = "invalid"
    elif problem == "gap":
        frame = frame.iloc[1:]
    elif problem == "duplicate":
        frame = pd.concat([frame, frame.iloc[:1]])
    else:
        frame.loc[0, "electricity_price_eur_mwh"] = float("inf")
    frame.to_csv(prices, index=False)
    with pytest.raises(ValueError):
        tasks.fetch_prices_task(START, END, tmp_path, prices_csv=prices)
    assert not list(tmp_path.glob("prices-*.csv"))


def test_missing_price_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        tasks.fetch_prices_task(START, END, tmp_path, prices_csv=tmp_path / "missing.csv")


@pytest.mark.parametrize("start,end", [
    ("2025-01-01", END), (END, START),
    ("2025-01-01T00:30:00Z", END), ("NaT", END),
])
def test_invalid_interval(start, end, tmp_path):
    with pytest.raises(ValueError):
        tasks.fetch_weather_task(start, end, tmp_path)


@pytest.mark.parametrize("source", ["weather", "prices"])
def test_load_transaction_and_upsert(monkeypatch, tmp_path, weather, prices, source, caplog):
    monkeypatch.setattr(tasks, "fetch_weather", lambda *a, **kw: weather)
    artifact = (tasks.fetch_weather_task(START, END, tmp_path) if source == "weather"
                else tasks.fetch_prices_task(START, END, tmp_path, prices_csv=prices))
    statements = []
    exits = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def executemany(self, sql, rows):
            statements.append((sql, list(rows)))

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def connect(url):
        assert url == "secret-url"
        yield Connection()
        exits.append("committed")

    monkeypatch.setattr(tasks.psycopg, "connect", connect)
    loader = getattr(tasks, f"load_{source}_raw_task")
    with caplog.at_level("INFO"):
        for _ in range(2):
            assert loader(artifact, START, END, database_url="secret-url") == 24
    assert exits == ["committed", "committed"]
    assert all("ON CONFLICT" in sql and len(rows) == 24 for sql, rows in statements)
    assert "secret-url" not in caplog.text
    assert "rows=24" in caplog.text


def test_corrupt_artifact_never_opens_database(monkeypatch, tmp_path, prices):
    artifact = tasks.fetch_prices_task(START, END, tmp_path, prices_csv=prices)
    pd.read_csv(artifact).iloc[1:].to_csv(artifact, index=False)

    def connect(url):
        pytest.fail("Invalid artifact must be rejected before opening database")

    monkeypatch.setattr(tasks.psycopg, "connect", connect)
    with pytest.raises(ValueError, match="coverage"):
        tasks.load_prices_raw_task(artifact, START, END, database_url="unused")
