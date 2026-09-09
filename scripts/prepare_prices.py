"""Prepare hourly UTC prices using the input and output paths from settings."""

from weather_energy.clients.price_client import prepare_prices, read_price_csv
from weather_energy.config import get_settings


def main() -> None:
    """Read, prepare, and save hourly electricity prices."""
    settings = get_settings()
    prepared = prepare_prices(read_price_csv(settings.prices_csv))
    output_path = settings.output_dir / "prices.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(output_path, index=False)
    print(f"Erfolgreich gespeichert: {output_path} ({len(prepared)} Zeilen)")


if __name__ == "__main__":
    main()
