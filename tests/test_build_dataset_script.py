"""Tests for the Level 1 dataset-building script."""

from types import SimpleNamespace

import pandas as pd

from scripts import build_dataset


def test_main_uses_configured_output_dir(tmp_path, monkeypatch):
    output_dir = tmp_path / "custom_output"
    output_dir.mkdir()
    pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00:00Z"],
            "city": ["Hamburg"],
            "temperature_c": [4.5],
        }
    ).to_csv(output_dir / "weather.csv", index=False)
    pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00:00Z"],
            "market_area": ["DE-LU"],
            "electricity_price_eur_mwh": [75.0],
        }
    ).to_csv(output_dir / "prices.csv", index=False)
    monkeypatch.setattr(
        build_dataset,
        "get_settings",
        lambda: SimpleNamespace(output_dir=output_dir),
    )

    build_dataset.main()

    result = pd.read_csv(output_dir / "weather_energy_hourly.csv")
    assert result["timestamp_utc"].tolist() == ["2025-01-01T00:00:00Z"]
    assert result["electricity_price_eur_mwh"].tolist() == [75.0]


def test_loaders_keep_mixed_valid_timestamp_formats(tmp_path):
    weather_path = tmp_path / "weather.csv"
    prices_path = tmp_path / "prices.csv"
    pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00Z", "2025-01-01T01:00:00Z"],
            "city": ["Hamburg", "Hamburg"],
            "temperature_c": [4.5, 5.5],
        }
    ).to_csv(weather_path, index=False)
    pd.DataFrame(
        {
            "timestamp_utc": ["2025-01-01T00:00:00Z", "2025-01-01T01:00Z"],
            "market_area": ["DE-LU", "DE-LU"],
            "electricity_price_eur_mwh": [75.0, 76.0],
        }
    ).to_csv(prices_path, index=False)

    result = build_dataset.build_dataset(
        build_dataset.load_weather(weather_path),
        build_dataset.load_prices(prices_path),
    )

    assert result["timestamp_utc"].tolist() == [
        "2025-01-01T00:00:00Z",
        "2025-01-01T01:00:00Z",
    ]
