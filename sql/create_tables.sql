-- Weather table owned by Engineer 1. Other tables are added separately.
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.weather_hourly (
    timestamp_utc TIMESTAMPTZ NOT NULL,
    city TEXT NOT NULL,
    temperature_c DOUBLE PRECISION NOT NULL,
    relative_humidity_percent DOUBLE PRECISION NOT NULL,
    wind_speed_kmh DOUBLE PRECISION NOT NULL,
    cloud_cover_percent DOUBLE PRECISION NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (timestamp_utc, city)
);
