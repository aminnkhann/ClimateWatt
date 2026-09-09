"""Tests for weather downloads and raw weather key validation."""

from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest

from weather_energy.clients.weather_client import OUTPUT_COLUMNS, fetch_weather


@pytest.fixture
def weather_api(monkeypatch):
    payload = {
        "hourly": {
            "time": ["2025-01-01T00:00", "2025-01-01T01:00"],
            "temperature_2m": [1.0, 2.0],
            "relative_humidity_2m": [70, 80],
            "wind_speed_10m": [5.0, 6.0],
            "cloud_cover": [10, 20],
        }
    }
    response = Mock()
    response.json.return_value = payload
    get = Mock(return_value=response)
    monkeypatch.setattr("weather_energy.clients.weather_client.requests.get", get)
    return payload, get


def download(city="Hamburg"):
    return fetch_weather(date(2025, 1, 1), date(2025, 1, 1), city=city)


def test_fetch_preserves_hourly_rows_and_normalizes_city(weather_api):
    weather = download(" Hamburg ")

    assert list(weather.columns) == list(OUTPUT_COLUMNS)
    assert weather["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ").tolist() == [
        "2025-01-01T00:00:00Z",
        "2025-01-01T01:00:00Z",
    ]
    assert weather["city"].tolist() == ["Hamburg", "Hamburg"]
    assert weather["temperature_c"].tolist() == [1.0, 2.0]


def test_fetch_rejects_duplicate_weather_keys(weather_api):
    payload, _ = weather_api
    payload["hourly"]["time"][1] = payload["hourly"]["time"][0]

    with pytest.raises(ValueError, match=r"duplicate \(timestamp_utc, city\) keys"):
        download()


def test_separate_city_downloads_preserve_shared_timestamps(weather_api):
    weather = pd.concat([download("Hamburg"), download("Berlin")], ignore_index=True)

    assert len(weather) == 4
    assert weather["timestamp_utc"].nunique() == 2
    assert not weather.duplicated(subset=["timestamp_utc", "city"]).any()


@pytest.mark.parametrize("city", ["", " ", "\t\n"])
def test_fetch_rejects_empty_city_before_request(weather_api, city):
    _, get = weather_api

    with pytest.raises(ValueError, match="city must not be empty"):
        download(city)

    get.assert_not_called()


@pytest.mark.parametrize("value", [None, "bad", float("inf")])
def test_rejects_invalid_temperature(weather_api, value):
    payload, _ = weather_api
    payload["hourly"]["temperature_2m"][0] = value
    with pytest.raises(ValueError, match="invalid required values"):
        download()


@pytest.mark.parametrize("value", [None, "bad", "2025-01-01T00:30"])
def test_rejects_invalid_timestamp(weather_api, value):
    payload, _ = weather_api
    payload["hourly"]["time"][0] = value
    with pytest.raises(ValueError):
        download()


def test_http_failure_is_logged(weather_api, caplog):
    import requests

    _, get = weather_api
    get.return_value.raise_for_status.side_effect = requests.HTTPError("failed")
    with pytest.raises(requests.HTTPError):
        download()
    get.return_value.json.assert_not_called()
    assert "Weather request failed" in caplog.text


@pytest.mark.parametrize("change", ["missing", "length", "empty"])
def test_rejects_malformed_response(weather_api, change):
    payload, _ = weather_api
    if change == "missing":
        del payload["hourly"]["temperature_2m"]
    elif change == "length":
        payload["hourly"]["temperature_2m"].pop()
    else:
        payload["hourly"] = {key: [] for key in payload["hourly"]}
    with pytest.raises(ValueError):
        download()


@pytest.mark.parametrize("options", [
    {"latitude": 91}, {"longitude": -181},
    {"start_date": date(2025, 1, 2)},
])
def test_validates_arguments_before_request(weather_api, options):
    _, get = weather_api
    args = {"start_date": date(2025, 1, 1), "end_date": date(2025, 1, 1)}
    with pytest.raises(ValueError):
        fetch_weather(**(args | options))
    get.assert_not_called()


def test_loader_validates_before_database_access(weather_api):
    from weather_energy.database.loader import load_weather

    connection = Mock()
    weather = download().drop(columns="temperature_c")
    with pytest.raises(ValueError, match="missing required columns"):
        load_weather(connection, weather)
    connection.cursor.assert_not_called()


def test_loader_passes_typed_rows_and_leaves_transaction_to_caller(weather_api):
    from unittest.mock import MagicMock

    from weather_energy.database.loader import load_weather

    connection = MagicMock()
    assert load_weather(connection, download()) == 2
    _, rows = connection.cursor.return_value.__enter__.return_value.executemany.call_args.args
    assert rows[0][0].utcoffset().total_seconds() == 0
    assert rows[0][1:] == ("Hamburg", 1.0, 70, 5.0, 10)
    connection.commit.assert_not_called()
