"""Tests for the Level 1 weather download script."""

from datetime import date
from types import SimpleNamespace

import pandas as pd

from scripts import get_weather


def test_parse_args_uses_configured_city_range_and_output_dir(tmp_path, monkeypatch):
    output_dir = tmp_path / "configured"
    monkeypatch.setattr(
        get_weather,
        "get_settings",
        lambda: SimpleNamespace(
            city="Berlin",
            latitude=52.52,
            longitude=13.405,
            weather_start_date=date(2025, 1, 1),
            weather_days=180,
            output_dir=output_dir,
        ),
    )
    monkeypatch.setattr("sys.argv", ["get_weather.py"])

    args = get_weather.parse_args()

    assert args.city == "Berlin"
    assert args.latitude == 52.52
    assert args.longitude == 13.405
    assert args.start_date == date(2025, 1, 1)
    assert args.end_date == date(2025, 6, 29)
    assert args.output_dir == output_dir


def test_main_writes_weather_to_configured_output_dir(tmp_path, monkeypatch):
    output_dir = tmp_path / "configured"
    monkeypatch.setattr(
        get_weather,
        "get_settings",
        lambda: SimpleNamespace(
            city="Berlin",
            latitude=52.52,
            longitude=13.405,
            weather_start_date=date(2025, 1, 1),
            weather_days=1,
            output_dir=output_dir,
        ),
    )
    monkeypatch.setattr("sys.argv", ["get_weather.py"])

    calls = []

    def fake_fetch_weather(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame(
            {
                "timestamp_utc": pd.to_datetime(["2025-01-01T00:00:00Z"], utc=True),
                "city": ["Berlin"],
                "temperature_c": [4.5],
            }
        )

    monkeypatch.setattr(get_weather, "fetch_weather", fake_fetch_weather)

    get_weather.main()

    assert calls == [
        {
            "city": "Berlin",
            "latitude": 52.52,
            "longitude": 13.405,
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 1),
        }
    ]
    result = pd.read_csv(output_dir / "weather.csv")
    assert result["city"].tolist() == ["Berlin"]
