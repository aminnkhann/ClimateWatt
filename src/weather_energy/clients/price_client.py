"""Read and clean electricity prices into hourly UTC DataFrames.

Naive timestamps use Europe/Berlin. Invalid rows are removed; an empty
result raises ValueError. Values within each UTC hour and market are averaged.
"""
from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pandas as pd


DEFAULT_MARKET_AREA = "DE-LU"
SOURCE_TIMEZONE = "Europe/Berlin"
DST_GAP = timedelta(hours=1)

OUTPUT_COLUMNS = [
    "timestamp_utc",
    "market_area",
    "electricity_price_eur_mwh",
]

REQUIRED_COLUMNS = {
    "timestamp_utc",
    "market_area",
    "electricity_price_eur_mwh",
}


def read_price_csv(path: Path) -> pd.DataFrame:
    """Read a comma- or semicolon-separated electricity price CSV."""

    if not path.exists():
        raise FileNotFoundError(
            f"Eingabedatei nicht gefunden: {path}"
        )

    return pd.read_csv(
        path,
        sep=None,
        engine="python",
    )


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize source column names to the project schema."""

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


def _parse_datetime_value(value: object) -> pd.Timestamp:
    """Parse ISO and German day-first datetime formats."""

    if pd.isna(value):
        return pd.NaT

    text = str(value).strip()

    # German format, for example: 01.02.2026 10:00
    german_date_pattern = r"^\d{1,2}\.\d{1,2}\.\d{4}"

    if re.match(german_date_pattern, text):
        parsed = pd.to_datetime(
            text,
            errors="coerce",
            dayfirst=True,
        )
    else:
        parsed = pd.to_datetime(
            value,
            errors="coerce",
        )

    if pd.isna(parsed):
        return pd.NaT

    return pd.Timestamp(parsed)


def parse_timestamp(
    value: object,
    *,
    ambiguous: bool = True,
) -> pd.Timestamp:
    """Parse one timestamp and convert it to UTC.

    Naive timestamps are interpreted as German local time.

    During the spring DST gap, nonexistent times are shifted forward by one
    hour. For ambiguous autumn timestamps, ``ambiguous=True`` selects the
    first occurrence.
    """

    timestamp = _parse_datetime_value(value)

    if pd.isna(timestamp):
        return pd.NaT

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
    """Parse timestamps while preserving repeated autumn DST hours.

    Duplicate naive timestamps belonging to the same market area alternate
    between the summer-time and standard-time occurrence.
    """

    occurrence_counts: dict[
        tuple[object, pd.Timestamp],
        int,
    ] = {}

    parsed_values: list[pd.Timestamp] = []

    for value, market_area in zip(
        values,
        market_areas,
        strict=True,
    ):
        timestamp = _parse_datetime_value(value)

        if pd.isna(timestamp):
            parsed_values.append(pd.NaT)
            continue

        ambiguous = True

        if timestamp.tzinfo is None:
            key = (
                market_area,
                timestamp,
            )

            occurrence = occurrence_counts.get(
                key,
                0,
            )

            occurrence_counts[key] = occurrence + 1

            # First duplicate = summer time
            # Second duplicate = standard time
            ambiguous = occurrence % 2 == 0

        parsed_values.append(
            parse_timestamp(
                timestamp,
                ambiguous=ambiguous,
            )
        )

    return pd.Series(
        parsed_values,
        index=values.index,
        dtype="datetime64[ns, UTC]",
    )


def normalize_price(value: object) -> str | None:
    """Normalize German and international number formats."""

    if pd.isna(value):
        return None

    cleaned = (
        str(value)
        .strip()
        .replace("\u00a0", "")
        .replace(" ", "")
    )

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            # German format: 1.234,56
            cleaned = (
                cleaned
                .replace(".", "")
                .replace(",", ".")
            )
        else:
            # International format: 1,234.56
            cleaned = cleaned.replace(",", "")

    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    return cleaned


def validate_columns(df: pd.DataFrame) -> None:
    """Validate that all required columns are available."""

    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            "Input price file is missing required columns: "
            f"{sorted(missing)}"
        )


def prepare_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Clean electricity prices and aggregate them to hourly UTC values."""

    df = normalize_columns(df)
    validate_columns(df)

    df = df.copy()

    # Important:
    # Normalize market_area BEFORE timestamp processing so values like
    # "DE-LU" and " DE-LU " are treated as the same DST business key.
    df["market_area"] = (
        df["market_area"]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
    )

    df["timestamp_utc"] = parse_timestamp_series(
        df["timestamp_utc"],
        df["market_area"],
    )

    cleaned_prices = (
        df["electricity_price_eur_mwh"]
        .map(normalize_price)
    )

    df["electricity_price_eur_mwh"] = pd.to_numeric(
        cleaned_prices,
        errors="coerce",
    )

    # pd.to_numeric("inf") returns infinity instead of NaN.
    # Use NaN to preserve the numeric dtype for aggregation and rounding.
    df["electricity_price_eur_mwh"] = (
        df["electricity_price_eur_mwh"]
        .replace(
            [
                float("inf"),
                float("-inf"),
            ],
            float("nan"),
        )
    )

    df = df.dropna(
        subset=[
            "timestamp_utc",
            "market_area",
            "electricity_price_eur_mwh",
        ]
    )

    if df.empty:
        raise ValueError(
            "No valid electricity price rows remain after cleaning"
        )

    # Convert quarter-hourly values to hourly UTC buckets.
    df["timestamp_utc"] = (
        df["timestamp_utc"]
        .dt.floor("h")
    )

    hourly = (
        df.groupby(
            [
                "timestamp_utc",
                "market_area",
            ],
            as_index=False,
        )["electricity_price_eur_mwh"]
        .mean()
    )

    hourly["electricity_price_eur_mwh"] = (
        hourly["electricity_price_eur_mwh"]
        .round(2)
    )

    if hourly.duplicated(
        subset=[
            "timestamp_utc",
            "market_area",
        ]
    ).any():
        raise ValueError(
            "Prepared prices contain duplicate hourly business keys"
        )

    hourly = hourly.sort_values(
        [
            "timestamp_utc",
            "market_area",
        ]
    ).reset_index(drop=True)

    hourly["timestamp_utc"] = (
        hourly["timestamp_utc"]
        .dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    return hourly[OUTPUT_COLUMNS]
