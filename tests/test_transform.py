"""Tests for Level 2 transformation and validation."""

import pandas as pd
import pytest

from weather_energy.transform.weather_energy import build_hourly_dataset


def test_build_hourly_dataset_joins_and_normalizes_timestamps():
    weather = pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00:00+01:00"],
            "city": ["Hamburg"],
            "temperature_c": [5.5],
        }
    )
    prices = pd.DataFrame(
        {
            "timestamp_utc": ["2024-12-31T23:00:00Z"],
            "market_area": ["DE-LU"],
            "electricity_price_eur_mwh": [81.5],
        }
    )
    result = build_hourly_dataset(weather, prices)
    assert result.loc[0, "timestamp_utc"] == "2024-12-31T23:00:00Z"
    assert result.loc[0, "electricity_price_eur_mwh"] == 81.5


def test_build_hourly_dataset_rejects_duplicate_business_keys():
    weather = pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00:00Z"] * 2,
            "city": ["Hamburg", "Hamburg"],
            "temperature_c": [1, 2],
        }
    )
    prices = pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00:00Z"],
            "market_area": ["DE-LU"],
            "electricity_price_eur_mwh": [50],
        }
    )
    with pytest.raises(ValueError, match="duplicate business keys"):
        build_hourly_dataset(weather, prices)


def test_build_hourly_dataset_keeps_mixed_valid_timestamp_formats():
    weather = pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00Z", "2025-01-01T01:00:00Z"],
            "city": ["Hamburg", "Hamburg"],
            "temperature_c": [5.5, 6.5],
        }
    )
    prices = pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00:00Z", "2025-01-01T01:00Z"],
            "market_area": ["DE-LU", "DE-LU"],
            "electricity_price_eur_mwh": [81.5, 82.5],
        }
    )

    result = build_hourly_dataset(weather, prices)

    assert result["timestamp_utc"].tolist() == [
        "2025-01-01T00:00:00Z",
        "2025-01-01T01:00:00Z",
    ]


@pytest.mark.parametrize(
    ("city", "temperature"),
    [
        ("   ", 5.5),
        ("Hamburg", float("inf")),
    ],
)
def test_build_hourly_dataset_rejects_invalid_weather_values(city, temperature):
    weather = pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00:00Z"],
            "city": [city],
            "temperature_c": [temperature],
        }
    )
    prices = pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00:00Z"],
            "market_area": ["DE-LU"],
            "electricity_price_eur_mwh": [81.5],
        }
    )

    with pytest.raises(ValueError, match="no shared timestamp_utc|empty"):
        build_hourly_dataset(weather, prices)
