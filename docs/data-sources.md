# Data sources and assumptions

## Weather

- Source: Open-Meteo Archive API (`https://archive-api.open-meteo.com/v1/archive`)
- Location: Hamburg, Germany (`53.5511, 9.9937`)
- Time zone returned/requested: UTC (`GMT`)
- Resolution: hourly
- Temperature unit: degrees Celsius
- Wind-speed unit: kilometres per hour

## Electricity prices

- Source: the committed hand-curated teaching fixture in `data/input/electricity_prices_sample.csv`
- Purpose: deterministic local development and tests; it is not a live market export
- Time zone: UTC
- Resolution: half-hourly input, aggregated to hourly means
- Unit: EUR/MWh
