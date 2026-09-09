"""Fetch and validate hourly Open-Meteo weather for Level 2."""

from __future__ import annotations

import logging
import math
from datetime import date

import pandas as pd
import requests

logger = logging.getLogger(__name__)

API_URL = "https://archive-api.open-meteo.com/v1/archive"
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


def fetch_weather(
    start_date: date,
    end_date: date,
    *,
    city: str = "Hamburg",
    latitude: float = 53.5511,
    longitude: float = 9.9937,
) -> pd.DataFrame:
    """Fetch one city's hourly weather, keyed by (timestamp_utc, city)."""
    city = city.strip()
    if not city:
        raise ValueError("city must not be empty")

    if not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")
    if start_date > end_date:
        raise ValueError("start-date must be before or equal to end-date")
    logger.info("Fetching weather for %s from %s to %s", city, start_date, end_date)
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

    try:
        response = requests.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        logger.error("Weather request failed for %s from %s to %s", city, start_date, end_date)
        raise

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

    weather = validate_weather(weather)
    logger.info("Fetched %d weather rows for %s", len(weather), city)
    return weather


def validate_weather(weather: pd.DataFrame) -> pd.DataFrame:
    """Return a validated copy with UTC datetimes for database loading."""
    missing = set(OUTPUT_COLUMNS) - set(weather.columns)
    if missing:
        raise ValueError(f"Weather is missing required columns: {', '.join(sorted(missing))}")
    weather = weather[list(OUTPUT_COLUMNS)].copy()
    if weather.empty:
        raise ValueError("Weather contains no hourly rows")
    weather["timestamp_utc"] = pd.to_datetime(weather["timestamp_utc"], utc=True, errors="raise")
    if not weather["city"].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
        raise ValueError("Weather city must not be empty and must be a string")
    weather["city"] = weather["city"].str.strip()
    for column in OUTPUT_COLUMNS[2:]:
        weather[column] = pd.to_numeric(weather[column], errors="coerce")
        if not weather[column].map(math.isfinite).all():
            raise ValueError(f"Weather contains missing or invalid required values in {column}")
    if weather["timestamp_utc"].isna().any():
        raise ValueError("Weather contains missing timestamps")
    if (weather["timestamp_utc"] != weather["timestamp_utc"].dt.floor("h")).any():
        raise ValueError("Weather timestamps must be aligned to an hour")
    if weather.duplicated(subset=["timestamp_utc", "city"]).any():
        raise ValueError("Weather contains duplicate (timestamp_utc, city) keys")
    return weather
