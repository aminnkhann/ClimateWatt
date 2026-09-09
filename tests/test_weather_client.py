"""Tests for weather downloads and raw weather key validation."""

from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest

from scripts.get_weather import OUTPUT_COLUMNS, fetch_weather


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
    monkeypatch.setattr("scripts.get_weather.requests.get", get)
    return payload, get


def download(city="Hamburg"):
    return fetch_weather(city, 53.5511, 9.9937, date(2025, 1, 1), date(2025, 1, 1))


def test_fetch_preserves_hourly_rows_and_normalizes_city(weather_api):
    weather = download(" Hamburg ")

    assert list(weather.columns) == list(OUTPUT_COLUMNS)
    assert weather["timestamp_utc"].tolist() == [
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
