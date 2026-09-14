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
    assert len(statements) == 2
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


def test_incomplete_quarter_hour_prices_fail(tmp_path):
    frame = pd.DataFrame(
        {
            "timestamp_utc": [
                "2025-01-01T00:00:00Z",
                "2025-01-01T00:15:00Z",
                # 00:30 intentionally missing
                "2025-01-01T00:45:00Z",
            ],
            "market_area": ["DE-LU"] * 3,
            "electricity_price_eur_mwh": [10.0, 20.0, 30.0],
        }
    )

    prices_csv = tmp_path / "quarter_hour_prices.csv"
    frame.to_csv(prices_csv, index=False)

    with pytest.raises(
        ValueError,
        match="quarter|15-minute|incomplete",
    ):
        tasks.fetch_prices_task(
            "2025-01-01T00:00:00Z",
            "2025-01-01T01:00:00Z",
            tmp_path,
            prices_csv=prices_csv,
            market_area="DE-LU",
        )

    assert not list(tmp_path.glob("prices-*.csv"))


@pytest.mark.parametrize("minutes", [[0, 15, 30, 45], [0, 10, 30, 45]])
def test_quarter_hour_alignment_and_average(tmp_path, minutes):
    path = tmp_path / "input.csv"
    pd.DataFrame({
        "timestamp_utc": [pd.Timestamp(START) + pd.Timedelta(m, unit="min") for m in minutes],
        "market_area": "DE-LU", "electricity_price_eur_mwh": [-10, 10, 30, 50],
    }).to_csv(path, index=False)
    if minutes == [0, 15, 30, 45]:
        artifact = tasks.fetch_prices_task(START, "2025-01-01T01:00:00Z", tmp_path,
                                          prices_csv=path)
        assert pd.read_csv(artifact).electricity_price_eur_mwh.tolist() == [20.0]
    else:
        with pytest.raises(ValueError, match="15-minute"):
            tasks.fetch_prices_task(START, "2025-01-01T01:00:00Z", tmp_path, prices_csv=path)


@pytest.mark.parametrize("source", ["weather", "prices"])
@pytest.mark.parametrize("operation", ["fetch", "load"])
@pytest.mark.parametrize("value", ["", "   "])
def test_empty_identity_fails_before_io(monkeypatch, tmp_path, source, operation, value):
    def unexpected(*args, **kwargs):
        pytest.fail("Empty identity must fail before I/O")

    monkeypatch.setattr(tasks, "fetch_weather", unexpected)
    monkeypatch.setattr(tasks, "read_price_csv", unexpected)
    monkeypatch.setattr(tasks.pd, "read_csv", unexpected)
    monkeypatch.setattr(tasks.psycopg, "connect", unexpected)
    identity = {"city" if source == "weather" else "market_area": value}
    message = "City must not be empty" if source == "weather" else "Market area must not be empty"
    with pytest.raises(ValueError, match=message):
        if operation == "fetch":
            extra = {"prices_csv": tmp_path / "missing.csv"} if source == "prices" else {}
            getattr(tasks, f"fetch_{source}_task")(START, END, tmp_path, **identity, **extra)
        else:
            getattr(tasks, f"load_{source}_raw_task")(
                tmp_path / "missing.csv", START, END, database_url="unused", **identity,
            )


@pytest.mark.parametrize("source", ["weather", "prices"])
def test_padded_identity_fetch_and_load(monkeypatch, tmp_path, weather, prices, source):
    def fetch(*args, **kwargs):
        assert kwargs["city"] == "Hamburg"
        return weather

    monkeypatch.setattr(tasks, "fetch_weather", fetch)
    identity = {"city": " Hamburg "} if source == "weather" else {"market_area": " DE-LU "}
    extra = {"prices_csv": prices} if source == "prices" else {}
    artifact = getattr(tasks, f"fetch_{source}_task")(START, END, tmp_path, **identity, **extra)
    loaded = []

    @contextmanager
    def connect(url):
        yield object()

    monkeypatch.setattr(tasks.psycopg, "connect", connect)
    monkeypatch.setattr(tasks, f"load_{source}", lambda conn, frame: loaded.append(frame))
    assert getattr(tasks, f"load_{source}_raw_task")(
        artifact, START, END, database_url="unused", **identity,
    ) == 24
    assert len(loaded) == 1
    key = "city" if source == "weather" else "market_area"
    assert loaded[0][key].unique().tolist() == [identity[key].strip()]


@pytest.mark.parametrize("source", ["weather", "prices"])
@pytest.mark.parametrize("failure_at", ["connect", "write"])
def test_database_errors_propagate(monkeypatch, tmp_path, weather, prices, source,
                                   failure_at, caplog):
    monkeypatch.setattr(tasks, "fetch_weather", lambda *a, **kw: weather)
    extra = {"prices_csv": prices} if source == "prices" else {}
    artifact = getattr(tasks, f"fetch_{source}_task")(START, END, tmp_path, **extra)
    error = tasks.psycopg.OperationalError("temporary database failure")
    transaction_errors = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            # psycopg uses this exception to roll back; no real database here.
            transaction_errors.append(exc_value)
            return False

    def connect(url):
        if failure_at == "connect":
            raise error
        return Connection()

    def write(*args):
        raise error

    monkeypatch.setattr(tasks.psycopg, "connect", connect)
    monkeypatch.setattr(tasks, f"load_{source}", write)
    with caplog.at_level("INFO"), pytest.raises(tasks.psycopg.OperationalError) as caught:
        getattr(tasks, f"load_{source}_raw_task")(artifact, START, END, database_url="unused")
    assert caught.value is error
    assert transaction_errors == ([error] if failure_at == "write" else [])
    assert "Loaded " not in caplog.text
