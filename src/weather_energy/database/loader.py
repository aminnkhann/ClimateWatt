"""Load validated weather through a psycopg connection."""

import logging

import pandas as pd

from weather_energy.clients.weather_client import validate_weather

logger = logging.getLogger(__name__)

WEATHER_UPSERT = """
INSERT INTO raw.weather_hourly (
    timestamp_utc, city, temperature_c, relative_humidity_percent,
    wind_speed_kmh, cloud_cover_percent
) VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (timestamp_utc, city) DO UPDATE SET
    temperature_c = EXCLUDED.temperature_c,
    relative_humidity_percent = EXCLUDED.relative_humidity_percent,
    wind_speed_kmh = EXCLUDED.wind_speed_kmh,
    cloud_cover_percent = EXCLUDED.cloud_cover_percent,
    loaded_at = NOW()
"""


def load_weather(connection, weather: pd.DataFrame) -> int:
    """Upsert weather; the caller owns the transaction and commits or rolls back."""
    weather = validate_weather(weather)
    rows = [
        (timestamp.to_pydatetime(), city, *values)
        for timestamp, city, *values in weather.itertuples(index=False, name=None)
    ]
    try:
        with connection.cursor() as cursor:
            cursor.executemany(WEATHER_UPSERT, rows)
    except Exception:
        logger.error("Failed to load %d weather rows", len(rows))
        raise
    logger.info("Upserted %d weather rows; transaction awaits caller commit", len(rows))
    return len(rows)
