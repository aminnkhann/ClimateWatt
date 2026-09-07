"""Prepare the local price CSV using the reusable Level 2 client.

Install the project first with ``pip install -e ".[dev]"``.
"""

from pathlib import Path

from weather_energy.clients.price_client import prepare_prices, read_price_csv

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "data" / "input" / "electricity_prices_sample.csv"
OUTPUT_PATH = BASE_DIR / "data" / "output" / "prices.csv"


def main() -> None:
    """Read, prepare, and save hourly electricity prices."""
    prepared = prepare_prices(read_price_csv(INPUT_PATH))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(OUTPUT_PATH, index=False)
    print(f"Erfolgreich gespeichert: {OUTPUT_PATH} ({len(prepared)} Zeilen)")


if __name__ == "__main__":
    main()
