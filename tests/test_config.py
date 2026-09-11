"""Tests for environment-driven pipeline configuration."""

from datetime import date
from urllib.parse import urlsplit

import pytest

from weather_energy.config import get_settings


def test_get_settings_reads_city_and_weather_range(monkeypatch):
    monkeypatch.setenv("CITY_NAME", "Berlin")
    monkeypatch.setenv("CITY_LATITUDE", "52.5200")
    monkeypatch.setenv("CITY_LONGITUDE", "13.4050")
    monkeypatch.setenv("WEATHER_START_DATE", "2025-01-01")
    monkeypatch.setenv("WEATHER_DAYS", "180")

    settings = get_settings()

    assert settings.city == "Berlin"
    assert settings.latitude == 52.52
    assert settings.longitude == 13.405
    assert settings.weather_start_date == date(2025, 1, 1)
    assert settings.weather_days == 180


@pytest.mark.parametrize("value", ["0", "-1"])
def test_get_settings_rejects_non_positive_weather_days(monkeypatch, value):
    monkeypatch.setenv("WEATHER_DAYS", value)

    with pytest.raises(ValueError, match="WEATHER_DAYS must be at least 1"):
        get_settings()


def test_get_settings_rejects_invalid_weather_start_date(monkeypatch):
    monkeypatch.setenv("WEATHER_START_DATE", "01-01-2025")

    with pytest.raises(ValueError, match="WEATHER_START_DATE must use YYYY-MM-DD"):
        get_settings()


def test_database_url_percent_encodes_spaces_in_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "weather_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "a b")

    settings = get_settings()

    assert "a%20b" in settings.database_url
    assert "a+b" not in settings.database_url
    assert urlsplit(settings.database_url).password == "a%20b"
