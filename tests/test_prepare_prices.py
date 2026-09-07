from pathlib import Path

import pandas as pd
import pytest

from weather_energy.clients.price_client import (
    normalize_price,
    parse_timestamp,
    prepare_prices,
    read_price_csv,
)


def test_parse_timestamp_german_local_time():
    """Testet die Umwandlung von naiven Zeitstempeln (Europe/Berlin) nach UTC."""
    # Winterzeit (UTC+1): 10:00 Uhr Berlin -> 09:00 UTC
    winter_ts = parse_timestamp("2026-01-15 10:00:00")
    assert winter_ts.strftime("%Y-%m-%dT%H:%M:%SZ") == "2026-01-15T09:00:00Z"

    # Sommerzeit (UTC+2): 10:00 Uhr Berlin -> 08:00 UTC
    summer_ts = parse_timestamp("2026-06-15 10:00:00")
    assert summer_ts.strftime("%Y-%m-%dT%H:%M:%SZ") == "2026-06-15T08:00:00Z"


def test_parse_timestamp_invalid():
    """Ungültige Zeitstempel müssen pd.NaT zurückgeben."""
    assert pd.isna(parse_timestamp("invalid-date"))
    assert pd.isna(parse_timestamp(None))


def test_prepare_prices_german_date_is_day_first():
    result = prepare_prices(
        pd.DataFrame({"timestamp": ["01.02.2026 10:00"], "price": ["25,5"]})
    )
    assert result.iloc[0]["timestamp_utc"] == "2026-02-01T09:00:00Z"
    assert result.iloc[0]["electricity_price_eur_mwh"] == 25.5


@pytest.mark.parametrize("price", ["inf", "-inf"])
def test_prepare_prices_rejects_infinite_prices(price):
    with pytest.raises(ValueError, match="No valid electricity price rows remain"):
        prepare_prices(
            pd.DataFrame({"timestamp": ["2026-01-10T00:00:00Z"], "price": [price]})
        )


def test_parse_timestamp_with_timezone():
    """Bereits zeitzonenbehaftete Werte werden direkt nach UTC konvertiert."""
    timestamp = parse_timestamp("2026-06-15T10:00:00+02:00")

    assert timestamp.strftime("%Y-%m-%dT%H:%M:%SZ") == "2026-06-15T08:00:00Z"


@pytest.mark.parametrize(
    "input_val, expected",
    [
        # Die nicht existente Zeit wird um die DST-Lücke vorgeschoben.
        ("2026-03-29 02:30:00", "2026-03-29T01:30:00Z"),
        # Ohne Reihen-Kontext wird die erste (Sommerzeit-)Instanz gewählt.
        ("2026-10-25 02:30:00", "2026-10-25T00:30:00Z"),
    ],
)
def test_parse_timestamp_dst_edge_cases(input_val, expected):
    """DST-Randzeiten werden nach einer dokumentierten Regel aufgelöst."""
    assert parse_timestamp(input_val).strftime("%Y-%m-%dT%H:%M:%SZ") == expected


def test_prepare_prices_preserves_repeated_autumn_hour():
    """Beide Instanzen einer doppelten lokalen Stunde bleiben erhalten."""
    input_df = pd.DataFrame(
        {
            "timestamp": [
                "2026-10-25 02:00:00",
                "2026-10-25 02:00:00",
            ],
            "price": [10, 20],
        }
    )

    result = prepare_prices(input_df)

    assert result[["timestamp_utc", "electricity_price_eur_mwh"]].values.tolist() == [
        ["2026-10-25T00:00:00Z", 10.0],
        ["2026-10-25T01:00:00Z", 20.0],
    ]


def test_prepare_prices_preserves_nonexistent_spring_time():
    """Eine Zeit in der Frühjahrs-Lücke wird nicht als ungültig verworfen."""
    input_df = pd.DataFrame(
        {
            "timestamp": ["2026-03-29 02:30:00"],
            "price": [30],
        }
    )

    result = prepare_prices(input_df)

    assert result.iloc[0]["timestamp_utc"] == "2026-03-29T01:00:00Z"
    assert result.iloc[0]["electricity_price_eur_mwh"] == 30.0


@pytest.mark.parametrize(
    "input_val, expected",
    [
        ("50,5", "50.5"),
        ("1.234,56", "1234.56"),
        ("1,234.56", "1234.56"),
        (" 100,00 \u00a0", "100.00"),
        (None, None),
    ],
)
def test_normalize_price(input_val, expected):
    """Testet die Normalisierung deutscher und internationaler Zahlenformate."""
    assert normalize_price(input_val) == expected


def test_prepare_prices_quarter_hourly_aggregation():
    """Testet das Zusammenfassen von 15-Minuten-Werten zu Stunden-Mittelwerten."""
    data = {
        "Datum von": [
            "2026-01-10 11:00",
            "2026-01-10 11:15",
            "2026-01-10 11:30",
            "2026-01-10 11:45",
        ],
        "Preis [EUR/MWh]": ["10,0", "20,0", "30,0", "40,0"],
    }
    input_df = pd.DataFrame(data)
    result = prepare_prices(input_df)

    assert len(result) == 1
    # UTC = 11:00 Berlin (Winterzeit) - 1h = 10:00 UTC
    assert result.iloc[0]["timestamp_utc"] == "2026-01-10T10:00:00Z"
    assert result.iloc[0]["market_area"] == "DE-LU"
    # Mittelwert aus 10, 20, 30, 40 ist 25.0
    assert result.iloc[0]["electricity_price_eur_mwh"] == 25.0


def test_prepare_prices_missing_required_columns():
    """Fehlende Pflichtspalten müssen eine ValueError auslösen."""
    invalid_df = pd.DataFrame({"unrelated_column": [1, 2, 3]})
    with pytest.raises(ValueError, match="missing required columns"):
        prepare_prices(invalid_df)


def test_prepare_prices_empty_after_cleaning():
    """DataFrame ohne gültige Zeilen muss abgefangen werden."""
    invalid_df = pd.DataFrame(
        {
            "timestamp": ["invalid"],
            "price": ["invalid"],
        }
    )
    with pytest.raises(ValueError, match="No valid electricity price rows remain"):
        prepare_prices(invalid_df)


def test_prepare_prices_rejects_blank_market_area():
    """Ein leeres Marktgebiet darf keinen gültigen Business-Key erzeugen."""
    invalid_df = pd.DataFrame(
        {
            "timestamp": ["2026-01-10 11:00"],
            "market_area": ["   "],
            "price": ["25,0"],
        }
    )

    with pytest.raises(ValueError, match="No valid electricity price rows remain"):
        prepare_prices(invalid_df)


def test_prepare_prices_sorts_multiple_hours_and_market_areas():
    """Der Output ist nach Stunde und Marktgebiet sortiert und vollständig."""
    input_df = pd.DataFrame(
        {
            "timestamp": [
                "2026-01-10 12:00",
                "2026-01-10 11:00",
                "2026-01-10 11:30",
            ],
            "market_area": ["DE-LU", "FR", "DE-LU"],
            "price": [30, 20, 10],
        }
    )

    result = prepare_prices(input_df)

    assert list(result.columns) == [
        "timestamp_utc",
        "market_area",
        "electricity_price_eur_mwh",
    ]
    assert result[["timestamp_utc", "market_area"]].values.tolist() == [
        ["2026-01-10T10:00:00Z", "DE-LU"],
        ["2026-01-10T10:00:00Z", "FR"],
        ["2026-01-10T11:00:00Z", "DE-LU"],
    ]


def test_read_price_csv_missing_file(tmp_path: Path):
    """Eine nicht vorhandene Eingabedatei erzeugt eine klare Fehlermeldung."""
    missing_file = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError, match="Eingabedatei nicht gefunden"):
        read_price_csv(missing_file)


def test_read_price_csv_handles_semicolon(tmp_path: Path):
    """Prüft, ob die CSV-Einlesefunktion auch Semikolons als Trennzeichen liest."""
    csv_file = tmp_path / "test_prices.csv"
    csv_file.write_text("date;price\n2026-01-01 00:00;50,0", encoding="utf-8")

    df = read_price_csv(csv_file)
    assert "date" in df.columns
    assert "price" in df.columns
    assert len(df) == 1
    assert df.iloc[0]["price"] == "50,0"

def test_prepare_prices_normalizes_market_area_before_dst_handling():
    input_df = pd.DataFrame(
        {
            "timestamp": [
                "2026-10-25 02:00:00",
                "2026-10-25 02:00:00",
            ],
            "market_area": ["DE-LU", " DE-LU "],
            "price": [10, 20],
        }
    )

    result = prepare_prices(input_df)

    assert result[
        ["timestamp_utc", "electricity_price_eur_mwh"]
    ].values.tolist() == [
        ["2026-10-25T00:00:00Z", 10.0],
        ["2026-10-25T01:00:00Z", 20.0],
    ]
