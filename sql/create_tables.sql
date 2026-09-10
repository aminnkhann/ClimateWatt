CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS raw.weather_hourly (
    timestamp_utc TIMESTAMPTZ NOT NULL,
    city TEXT NOT NULL,
    temperature_c DOUBLE PRECISION NOT NULL,
    relative_humidity_percent DOUBLE PRECISION,
    wind_speed_kmh DOUBLE PRECISION,
    cloud_cover_percent DOUBLE PRECISION,
    PRIMARY KEY (timestamp_utc, city)
);

CREATE TABLE IF NOT EXISTS raw.electricity_price_hourly (
    timestamp_utc TIMESTAMPTZ NOT NULL,
    market_area TEXT NOT NULL,
    electricity_price_eur_mwh DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (timestamp_utc, market_area)
);

CREATE TABLE IF NOT EXISTS analytics.weather_energy_hourly (
    timestamp_utc TIMESTAMPTZ NOT NULL,
    city TEXT NOT NULL,
    market_area TEXT NOT NULL,
    temperature_c DOUBLE PRECISION NOT NULL,
    electricity_price_eur_mwh DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (timestamp_utc, city, market_area)
);
