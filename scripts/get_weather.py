"""Download hourly Open-Meteo weather data to the configured output directory."""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

import requests

from weather_energy.clients.weather_client import fetch_weather
from weather_energy.config import get_settings


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
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Download hourly weather data from Open-Meteo."
    )
    parser.add_argument("--city", default=settings.city, help="Name stored in the output CSV")
    parser.add_argument("--latitude", type=float, default=settings.latitude)
    parser.add_argument("--longitude", type=float, default=settings.longitude)
    parser.add_argument("--start-date", type=iso_date, default=settings.weather_start_date)
    parser.add_argument("--end-date", type=iso_date)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=settings.output_dir,
        help="Directory where weather.csv will be written",
    )
    args = parser.parse_args()
    if args.end_date is None:
        args.end_date = args.start_date + timedelta(days=settings.weather_days - 1)
    return args


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


def main() -> None:
    """Download the requested weather data and save it as CSV."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
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
        output_path = args.output_dir / "weather.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        weather["timestamp_utc"] = weather["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        weather.to_csv(output_path, index=False)
    except (ValueError, requests.RequestException) as error:
        raise SystemExit(f"Weather download failed: {error}") from error

    print(f"Wrote {len(weather)} hourly weather rows to {output_path}")


if __name__ == "__main__":
    main()
