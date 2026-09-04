"""Read the electricity price sample, normalize timestamps, and write ``data/output/prices.csv``.

Expected behavior for the first implementation:
- read ``data/input/electricity_prices_sample.csv``
- clean column names and timestamps
- aggregate quarter-hourly data to hourly values if needed

Naive source timestamps are interpreted as German local time before conversion to UTC.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "data" / "input" / "electricity_prices_sample.csv"
OUTPUT_DIR = BASE_DIR / "data" / "output"
OUTPUT_PATH = OUTPUT_DIR / "prices.csv"
DEFAULT_MARKET_AREA = "DE-LU"
SOURCE_TIMEZONE = "Europe/Berlin"
DST_GAP = timedelta(hours=1)

REQUIRED_COLUMNS = {
    "timestamp_utc",
    "market_area",
    "electricity_price_eur_mwh",
}


def read_price_csv(path: Path) -> pd.DataFrame:
    """Read a comma- or semicolon-separated electricity price CSV."""

    if not path.exists():
        raise FileNotFoundError(f"Eingabedatei nicht gefunden: {path}")

    # sep=None + engine="python" lets pandas detect ',' or ';'
    return pd.read_csv(path, sep=None, engine="python")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize and rename known source column names."""

    df = df.copy()

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    rename_mapping = {
        "datum_von": "timestamp_utc",
        "date": "timestamp_utc",
        "timestamp": "timestamp_utc",
        "preis_[eur/mwh]": "electricity_price_eur_mwh",
        "price_eur_mwh": "electricity_price_eur_mwh",
        "price": "electricity_price_eur_mwh",
    }

    df = df.rename(columns=rename_mapping)

    if "market_area" not in df.columns:
        df["market_area"] = DEFAULT_MARKET_AREA

    return df


def parse_timestamp(
    value: object,
    *,
    ambiguous: bool = True,
) -> pd.Timestamp:
    """Parse one timestamp, treating naive values as German local time.

    A nonexistent spring-transition time is moved forward by the one-hour DST
    gap, preserving its minutes. For a standalone ambiguous autumn-transition
    time, ``ambiguous=True`` selects the first (summer-time) occurrence. The
    dataframe preparation function assigns repeated occurrences in source
    order so that both market hours are retained.
    """

    timestamp = pd.to_datetime(value, errors="coerce")

    if pd.isna(timestamp):
        return pd.NaT

    timestamp = pd.Timestamp(timestamp)

    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(
            SOURCE_TIMEZONE,
            ambiguous=ambiguous,
            nonexistent=DST_GAP,
        )

    return timestamp.tz_convert("UTC")


def parse_timestamp_series(
    values: pd.Series,
    market_areas: pd.Series,
) -> pd.Series:
    """Parse timestamps and distinguish repeated local times in source order.

    For each market area and naive wall-clock timestamp, the first occurrence
    uses the DST offset and the second uses the standard-time offset. Further
    duplicate occurrences alternate between those offsets. Explicitly zoned
    source timestamps keep their supplied offset.
    """

    occurrence_counts: dict[tuple[object, pd.Timestamp], int] = {}
    parsed_values: list[pd.Timestamp] = []

    for value, market_area in zip(values, market_areas, strict=True):
        timestamp = pd.to_datetime(value, errors="coerce")

        if pd.isna(timestamp):
            parsed_values.append(pd.NaT)
            continue

        timestamp = pd.Timestamp(timestamp)
        ambiguous = True

        if timestamp.tzinfo is None:
            key = (market_area, timestamp)
            occurrence = occurrence_counts.get(key, 0)
            occurrence_counts[key] = occurrence + 1
            ambiguous = occurrence % 2 == 0

        parsed_values.append(
            parse_timestamp(timestamp, ambiguous=ambiguous)
        )

    return pd.Series(parsed_values, index=values.index, dtype="datetime64[ns, UTC]")


def normalize_price(value: object) -> str | None:
    """Normalize German and international decimal/thousands separators."""

    if pd.isna(value):
        return None

    cleaned = str(value).strip().replace("\u00a0", "").replace(" ", "")

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            # German notation, for example 1.234,56
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # International notation, for example 1,234.56
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    return cleaned


def validate_columns(df: pd.DataFrame) -> None:
    """Check that all required columns exist."""

    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            f"Input price file is missing required columns: {sorted(missing)}"
        )


def prepare_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Clean prices and aggregate them to one UTC value per hour."""

    df = normalize_columns(df)
    validate_columns(df)

    df = df.copy()

    df["timestamp_utc"] = parse_timestamp_series(
        df["timestamp_utc"],
        df["market_area"],
    )

    # Works independently of pandas string dtype implementation
    cleaned_prices = df["electricity_price_eur_mwh"].map(normalize_price)

    df["electricity_price_eur_mwh"] = pd.to_numeric(
        cleaned_prices,
        errors="coerce",
    )

    df["market_area"] = (
        df["market_area"]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
    )

    # Remove unusable rows
    df = df.dropna(
        subset=[
            "timestamp_utc",
            "market_area",
            "electricity_price_eur_mwh",
        ]
    )

    if df.empty:
        raise ValueError("No valid electricity price rows remain after cleaning")

    # Convert 15-minute values to hourly buckets
    df["timestamp_utc"] = df["timestamp_utc"].dt.floor("h")

    # Keep market_area as part of the business key
    hourly = (
        df.groupby(
            ["timestamp_utc", "market_area"],
            as_index=False,
        )["electricity_price_eur_mwh"]
        .mean()
    )

    hourly["electricity_price_eur_mwh"] = (
        hourly["electricity_price_eur_mwh"]
        .round(2)
    )

    if hourly.duplicated(
        subset=["timestamp_utc", "market_area"]
    ).any():
        raise ValueError(
            "Prepared prices contain duplicate hourly business keys"
        )

    hourly = hourly.sort_values(
        ["timestamp_utc", "market_area"]
    )

    hourly["timestamp_utc"] = (
        hourly["timestamp_utc"]
        .dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    return hourly[
        [
            "timestamp_utc",
            "market_area",
            "electricity_price_eur_mwh",
        ]
    ]


def main() -> None:
    """Run the Level 1 electricity price preparation."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    prices = read_price_csv(INPUT_PATH)
    prepared = prepare_prices(prices)

    prepared.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print(
        f"Erfolgreich gespeichert: "
        f"{OUTPUT_PATH} ({len(prepared)} Zeilen)"
    )


if __name__ == "__main__":
    main()
