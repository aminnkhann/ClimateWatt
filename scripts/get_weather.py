"""Download hourly Open-Meteo weather data to ``data/output/weather.csv``."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd
import requests

API_URL = "https://archive-api.open-meteo.com/v1/archive"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "output" / "weather.csv"
HOURLY_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "cloud_cover",
)
OUTPUT_COLUMNS = (
    "timestamp_utc",
    "city",
    "temperature_c",
    "relative_humidity_percent",
    "wind_speed_kmh",
    "cloud_cover_percent",
)


def iso_date(value: str) -> date:
    """Convert a YYYY-MM-DD command-line value to a date."""
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"'{value}' is not a valid date; use YYYY-MM-DD"
        ) from error


def parse_args() -> argparse.Namespace:
    """Read location and date-range values from the command line."""
    parser = argparse.ArgumentParser(
        description="Download hourly weather data from Open-Meteo."
    )
    parser.add_argument("--city", default="Hamburg", help="Name stored in the output CSV")
    parser.add_argument("--latitude", type=float, default=53.5511)
    parser.add_argument("--longitude", type=float, default=9.9937)
    parser.add_argument("--start-date", type=iso_date, default=date(2025, 1, 1))
    parser.add_argument("--end-date", type=iso_date, default=date(2025, 1, 7))
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """Reject invalid coordinates and date ranges before calling the API."""
    if not args.city.strip():
        raise ValueError("city must not be empty")
    if not -90 <= args.latitude <= 90:
        raise ValueError("latitude must be between -90 and 90")
    if not -180 <= args.longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")
    if args.start_date > args.end_date:
        raise ValueError("start-date must be before or equal to end-date")


def fetch_weather(
    city: str,
    latitude: float,
    longitude: float,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Fetch one city's hourly weather, keyed by (timestamp_utc, city)."""
    city = city.strip()
    if not city:
        raise ValueError("city must not be empty")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "hourly": ",".join(HOURLY_FIELDS),
        "timezone": "GMT",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
    }

    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, dict):
        raise ValueError("Open-Meteo returned an unexpected response format")
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("Open-Meteo response does not contain hourly weather data")

    required_api_fields = ("time", *HOURLY_FIELDS)
    missing_fields = [field for field in required_api_fields if field not in hourly]
    if missing_fields:
        raise ValueError(f"Open-Meteo response is missing fields: {', '.join(missing_fields)}")

    invalid_fields = [field for field in required_api_fields if not isinstance(hourly[field], list)]
    if invalid_fields:
        raise ValueError(f"Open-Meteo returned invalid fields: {', '.join(invalid_fields)}")

    field_lengths = {field: len(hourly[field]) for field in required_api_fields}
    if not field_lengths["time"]:
        raise ValueError("Open-Meteo returned no hourly weather rows")
    if len(set(field_lengths.values())) != 1:
        raise ValueError("Open-Meteo returned hourly fields with different lengths")

    weather = pd.DataFrame(
        {
            "timestamp_utc": pd.to_datetime(hourly["time"], utc=True, errors="raise"),
            "city": city,
            "temperature_c": hourly["temperature_2m"],
            "relative_humidity_percent": hourly["relative_humidity_2m"],
            "wind_speed_kmh": hourly["wind_speed_10m"],
            "cloud_cover_percent": hourly["cloud_cover"],
        }
    )

    numeric_columns = OUTPUT_COLUMNS[2:]
    weather[list(numeric_columns)] = weather[list(numeric_columns)].apply(
        pd.to_numeric, errors="coerce"
    )
    if weather[list(OUTPUT_COLUMNS)].isna().any().any():
        raise ValueError("Open-Meteo returned missing or invalid required values")
    if weather.duplicated(subset=["timestamp_utc", "city"]).any():
        raise ValueError("Open-Meteo returned duplicate (timestamp_utc, city) keys")

    weather["timestamp_utc"] = weather["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return weather[list(OUTPUT_COLUMNS)]


def main() -> None:
    """Download the requested weather data and save it as CSV."""
    args = parse_args()

    try:
        validate_args(args)
        weather = fetch_weather(
            city=args.city,
            latitude=args.latitude,
            longitude=args.longitude,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        weather.to_csv(OUTPUT_PATH, index=False)
    except (ValueError, requests.RequestException) as error:
        raise SystemExit(f"Weather download failed: {error}") from error

    print(f"Wrote {len(weather)} hourly weather rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
