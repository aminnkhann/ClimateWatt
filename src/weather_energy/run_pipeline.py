"""Run the Level 2 weather-energy pipeline."""

import logging
from datetime import date

from weather_energy.clients.price_client import prepare_prices, read_price_csv
from weather_energy.config import get_settings
from weather_energy.database.loader import (
    initialize_database,
    load_analytics,
    load_prices,
    load_weather,
)
from weather_energy.transform.weather_energy import build_hourly_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def run() -> None:
    """Fetch, transform, and idempotently load the configured Level 2 data."""
    import psycopg

    from scripts.get_weather import fetch_weather

    settings = get_settings()
    weather = fetch_weather(
        settings.city, settings.latitude, settings.longitude, date(2025, 1, 1), date(2025, 1, 7)
    )
    prices = prepare_prices(read_price_csv(settings.prices_csv))
    dataset = build_hourly_dataset(weather, prices)
    with psycopg.connect(settings.database_url) as connection:
        initialize_database(connection)
        load_weather(connection, weather)
        load_prices(connection, prices)
        load_analytics(connection, dataset)
    LOGGER.info(
        "Loaded weather=%d prices=%d analytics=%d rows", len(weather), len(prices), len(dataset)
    )


if __name__ == "__main__":
    run()
