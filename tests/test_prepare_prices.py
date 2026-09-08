"""Tests for the Level 1 prepare_prices script."""

import pandas as pd

from scripts import prepare_prices


def test_main_reads_prepares_and_writes_csv(tmp_path, monkeypatch, capsys):
    """main() should prepare price data and save it as a CSV file."""
    input_path = tmp_path / "electricity_prices_sample.csv"
    output_path = tmp_path / "output" / "prices.csv"

    input_df = pd.DataFrame(
        {
            "timestamp_utc": [
                "2026-09-01T10:00:00Z",
                "2026-09-01T10:30:00Z",
            ],
            "market_area": ["DE-LU", "DE-LU"],
            "electricity_price_eur_mwh": [50.0, 70.0],
        }
    )
    input_df.to_csv(input_path, index=False)

    monkeypatch.setattr(prepare_prices, "INPUT_PATH", input_path)
    monkeypatch.setattr(prepare_prices, "OUTPUT_PATH", output_path)

    prepare_prices.main()

    assert output_path.exists()

    result = pd.read_csv(output_path)

    assert len(result) == 1
    assert list(result.columns) == [
        "timestamp_utc",
        "market_area",
        "electricity_price_eur_mwh",
    ]
    assert result.loc[0, "timestamp_utc"] == "2026-09-01T10:00:00Z"
    assert result.loc[0, "market_area"] == "DE-LU"
    assert result.loc[0, "electricity_price_eur_mwh"] == 60.0

    captured = capsys.readouterr()
    assert "Erfolgreich gespeichert:" in captured.out
    assert "(1 Zeilen)" in captured.out
