# Weather and Electricity Price Pipeline

A learning project for **three junior data engineers**. We will build the same small pipeline in three levels:

1. **Level 1 — Basic:** runnable Python scripts and CSV files.
2. **Level 2 — Intermediate:** reusable Python code, PostgreSQL, tests, and Docker.
3. **Level 3 — Semi-professional:** Apache Airflow runs the batch pipeline every day.

The project studies a simple question:

> How do hourly weather values and German electricity prices look when placed in the same hourly dataset?

This is a **batch** project. It is not a Kafka or real-time streaming project. Kafka can be explored later as an optional learning exercise, but it is not needed to deliver this project.

## Current status

Levels 1 and 2 are implemented. The current pipeline can fetch a configurable
city's hourly weather, normalize electricity prices, join both datasets, and
load raw and analytics tables into PostgreSQL. The project is ready for the
Level 3 Airflow orchestration work described below.

## Learning goals

By completing the levels, the team will practice:

- Calling APIs and reading CSV files with Python
- Cleaning and joining time-based data with pandas
- Writing repeatable scripts instead of notebook-only work
- Loading data into PostgreSQL
- Using Git branches, pull requests, and simple tests
- Running local services with Docker Compose
- Scheduling and monitoring a pipeline with Airflow

The goal is not to build a perfect enterprise platform. The goal is to build a small project that works, understand every part, and improve it step by step.

## Final picture

At the end of Level 3, the pipeline will look like this:

```text
Open-Meteo API       SMARD CSV/API
      |                   |
      +---- Python ingestion ----+
                                  |
                         PostgreSQL raw tables
                                  |
                           Python transform
                                  |
                      PostgreSQL analytics table
                                  |
                         Airflow schedule + logs
```

We keep all timestamps in **UTC**. This avoids problems when daylight-saving time changes in Germany.

## Team workflow

Work as a team, but keep each task small enough for one person to finish and explain.

| Person | Main responsibility | Also learns |
|---|---|---|
| Engineer 1 | Weather ingestion | API requests, JSON parsing, CSV output |
| Engineer 2 | Electricity-price ingestion | CSV/API parsing, timestamps, validation |
| Engineer 3 | Transformation and project setup | pandas joins, Git, Docker, Airflow |

Responsibilities rotate after each level. For example, the person who wrote weather ingestion in Level 1 should review or extend the electricity part in Level 2.

### Git rules

- Create one branch per task: `feature/weather-script`, `feature/postgres-load`, etc.
- Make small commits with clear messages.
- Open a pull request before merging into `main`.
- One teammate reviews the pull request.
- Do not commit `.env`, passwords, large downloaded files, or local database files.

## Repository structure

Start small. Create folders only when a level needs them.

```text
.
├── data/
│   ├── input/                 # Small manual/sample input files
│   └── output/                # Generated CSV files; ignored by Git
├── scripts/                   # Level 1 runnable Python scripts
├── src/                       # Level 2 reusable Python modules
├── sql/                       # Database table creation scripts
├── dags/                      # Level 3 Airflow DAGs
├── tests/                     # Automated tests
├── docker-compose.yml         # Added in Level 2
├── requirements.txt
├── .env.example
├── .env.city                  # Local city and weather-range settings
├── .env.city.example          # Safe template for city settings
├── .gitignore
└── README.md
```

## Level 1 — Basic runnable pipeline

**Target:** A new teammate can run three Python scripts and receive one final CSV file.

### What we build

- A script that downloads hourly weather data for Hamburg from Open-Meteo.
- A small electricity-price CSV file stored in `data/input/`.
- A script that cleans both datasets and joins them by UTC hour.
- A final file: `data/output/weather_energy_hourly.csv`.

For Level 1, use a small, known price-data sample covering a few days. It is acceptable to download a public SMARD export manually and save a reduced sample in `data/input/`. This keeps the first version simple and makes debugging easier.

The committed Level 1 sample is a small hand-curated teaching fixture based on the
SMARD-style hourly price format. It is not a live market export and is included only
to make the pipeline reproducible without an external download.

### Deliverables

```text
scripts/
├── get_weather.py
├── prepare_prices.py
└── build_dataset.py

data/input/
└── electricity_prices_sample.csv

data/output/
└── weather_energy_hourly.csv
```

### Required columns

The final dataset must contain at least:

| Column | Meaning |
|---|---|
| `timestamp_utc` | Hour in UTC, for example `2026-01-10T08:00:00Z` |
| `city` | `Hamburg` |
| `temperature_c` | Air temperature in Celsius |
| `electricity_price_eur_mwh` | Day-ahead price in EUR/MWh |

### Step-by-step

1. Create and activate a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows PowerShell
```

2. Install the first dependencies.

```bash
pip install pandas requests
pip freeze > requirements.txt
```

3. Create `scripts/get_weather.py`.

The script should:

- Call Open-Meteo with Hamburg latitude and longitude.
- Request hourly temperature data for a short date range.
- Check that the HTTP response is successful.
- Save `data/output/weather.csv`.

4. Put a small price CSV in `data/input/electricity_prices_sample.csv`.

The file must have one price per hour, or it must be possible to aggregate it to one price per hour.

5. Create `scripts/prepare_prices.py`.

The script should:

- Read the input price CSV with pandas.
- Rename the timestamp and price columns to the required names.
- Convert the timestamp to UTC.
- Save `data/output/prices.csv`.

6. Create `scripts/build_dataset.py`.

The script should:

- Read `weather.csv` and `prices.csv`.
- Join rows using `timestamp_utc`.
- Remove rows with missing required values.
- Save `data/output/weather_energy_hourly.csv`.

7. Run the scripts in order.

```bash
python scripts/get_weather.py
python scripts/prepare_prices.py
python scripts/build_dataset.py
```

8. Check the output manually.

```bash
python -c "import pandas as pd; print(pd.read_csv('data/output/weather_energy_hourly.csv').head())"
```

### Level 1 definition of done

- All three scripts run from the command line without editing code.
- The final CSV exists and has the four required columns.
- No duplicate `timestamp_utc` values exist in the final CSV.
- The README explains where the price sample came from.
- Each teammate can explain one script to the others.

## Level 2 — Intermediate pipeline

**Target:** The pipeline stores data in PostgreSQL and can safely run again without creating duplicate records.

### What we add

- PostgreSQL in Docker Compose.
- Reusable Python functions under `src/`.
- Raw and analytics database tables.
- A simple logging setup.
- Basic pytest tests.
- A single command that runs the full pipeline.

Do not add Airflow yet. First make the Python pipeline reliable when run manually.

### Install and run the current Level 2 pipeline

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate       # Windows PowerShell
pip install -e ".[database,dev]"
cp .env.example .env            # create and edit this local file
cp .env.city.example .env.city  # create and edit this local file
docker compose up -d postgres
python -m weather_energy.run_pipeline
```

The pipeline fetches weather from Open-Meteo, reads the configured price CSV,
creates the database schemas and tables, and upserts weather, price, and joined
analytics records. It can be run repeatedly without creating duplicate business
keys.

### Suggested structure

```text
src/
├── clients/
│   ├── weather_client.py
│   └── price_client.py
├── transform/
│   └── weather_energy.py
├── database/
│   └── load_data.py
└── run_pipeline.py

sql/
└── create_tables.sql

tests/
├── test_weather_client.py
└── test_transform.py
```

### Database tables

Keep the model simple at first.

| Table | Purpose | Natural key |
|---|---|---|
| `raw.weather_hourly` | Weather records as received | `timestamp_utc`, `city` |
| `raw.electricity_price_hourly` | Price records as received | `timestamp_utc`, `market_area` |
| `analytics.weather_energy_hourly` | Joined, analysis-ready rows | `timestamp_utc`, `city`, `market_area` |

Use `INSERT ... ON CONFLICT DO UPDATE` or `INSERT ... ON CONFLICT DO NOTHING` so that rerunning the same date range does not create duplicates.

### Step-by-step

1. Install Docker Desktop or Docker Engine with Docker Compose.

2. Add PostgreSQL to `docker-compose.yml`.

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "${POSTGRES_PORT}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./sql/create_tables.sql:/docker-entrypoint-initdb.d/create_tables.sql

volumes:
  postgres_data:
```

Use an `.env` file instead of committing real passwords. The values above are acceptable only for local learning.

3. Start the database.

```bash
docker compose up -d postgres
```

The local Compose file maps PostgreSQL to host port `5442`. pgAdmin or another
SQL client should connect to `localhost:5442`, database `weather_energy`, using
the credentials in `.env`.

4. Move code from `scripts/` into small functions in `src/`.

Examples:

- `fetch_weather(start_date, end_date)` returns a pandas DataFrame.
- `read_prices(file_path)` returns a pandas DataFrame.
- `build_hourly_dataset(weather_df, price_df)` returns a pandas DataFrame.
- `load_dataframe(connection, dataframe, table_name)` loads data.

5. Create `src/run_pipeline.py` to call the functions in this order:

```text
fetch weather -> read/fetch prices -> validate -> load raw tables -> transform -> load analytics table
```

6. Add validation before loading:

- Required columns exist.
- Timestamps can be converted to UTC.
- Prices and temperatures are numeric.
- No duplicate business keys exist in the DataFrame.

7. Add at least two tests.

```bash
pip install pytest psycopg[binary]
pytest -q
```

Good first tests:

- `build_hourly_dataset()` joins two small example DataFrames correctly.
- Invalid or duplicate timestamps raise a clear error.

8. Run the full pipeline.

```bash
python -m weather_energy.run_pipeline
```

9. Verify table contents with a SQL client or `psql`.

```sql
SELECT COUNT(*) FROM analytics.weather_energy_hourly;
SELECT * FROM analytics.weather_energy_hourly ORDER BY timestamp_utc DESC LIMIT 10;
```

In pgAdmin, query the table with its schema-qualified name:

```sql
SELECT * FROM analytics.weather_energy_hourly;
```

### Level 2 definition of done

- `docker compose up -d postgres` starts PostgreSQL.
- `python -m weather_energy.run_pipeline` loads raw and analytics tables.
- Running the command twice does not create duplicate keys.
- At least two automated tests pass.
- Errors are logged with useful messages.
- The team can delete the Docker volume, start again, and rebuild the data successfully.

### Runtime configuration

The application loads general settings from `.env` and city-specific settings
from `.env.city`. The city file keeps location and date-range configuration
separate from database credentials:

```env
CITY_NAME=Hamburg
CITY_LATITUDE=53.5511
CITY_LONGITUDE=9.9937
WEATHER_START_DATE=2025-01-01
WEATHER_DAYS=180
```

`WEATHER_DAYS=180` requests an inclusive six-month weather range (approximately
4,320 hourly rows). The final analytics table can only contain timestamps that
also exist in the electricity-price input, so the price data must cover the
same period to produce six months of joined results. `DATABASE_URL` should use
the Docker host port configured in Compose (`5442` in the local setup).
The runner logs a warning when the price range does not cover the requested
weather range.

The committed price CSV is intentionally a very small teaching fixture. It is
enough to test parsing and joins, but it does not contain six months of prices.
For a complete six-month analytics dataset, replace it with a matching
six-month electricity-price export before running the pipeline. The warning in
the logs makes a mismatch visible, while the inner join keeps only timestamps
available in both sources.

## Level 3 — Semi-professional Airflow pipeline

**Target:** Airflow schedules the existing Python pipeline daily and shows task status and logs.

Airflow is an orchestrator. It should call the tested Python functions from Level 2; it should not contain all business logic inside one large DAG file.

### What we add

- Airflow webserver and scheduler in Docker Compose.
- One DAG: `weather_energy_daily`.
- Separate tasks for weather, prices, raw loading, transformation, and validation.
- Daily scheduling, retries, and logs.
- A manual trigger for testing.
- A clear separation between orchestration and business logic.

### DAG design

```text
fetch_weather ----> load_weather_raw ----+
                                          +--> build_analytics --> validate_analytics
fetch_prices -----> load_prices_raw -----+
```

For very junior engineers, it is also acceptable to begin with a single `run_pipeline` Airflow task. Split it into several tasks only after the single task works reliably.

### Suggested DAG settings

```python
schedule="0 2 * * *"
start_date=...
catchup=False
retries=2
retry_delay=5 minutes
```

The schedule means: run every day at 02:00. Store timestamps in UTC and document the Airflow timezone used by the team.

### How Level 3 will use Level 2

The DAG should calculate the processing date or date range, then call the same
tested functions already used by the manual runner. Airflow should coordinate
tasks, retries, dependencies, and logs; it should not reimplement HTTP calls,
timestamp normalization, joins, or SQL loading.

The preferred first DAG is:

```text
fetch_weather -> load_weather_raw ----+
                                      +-> build_analytics -> validate_analytics
fetch_prices  -> load_prices_raw -----+
```

Each task should report its input range and row count without logging passwords
or full connection URLs. A failed upstream task should prevent downstream data
loading, and retries should be limited to transient API or database failures.

### Step-by-step

1. Keep the Level 2 pipeline working before adding Airflow.

2. Add Airflow services to `docker-compose.yml` using an official Airflow Docker Compose example as the starting point. Mount these folders into the Airflow containers:

```text
./dags
./src
./sql
```

3. Create `dags/weather_energy_daily.py`.

The DAG should import functions from `src/`. Do not duplicate API and transformation code in the DAG.

4. Start the services.

```bash
docker compose up -d
```

5. Open Airflow at `http://localhost:8080` and log in with the local credentials defined in your Compose configuration.

6. Confirm that the DAG appears without import errors.

7. Trigger `weather_energy_daily` manually.

8. Read task logs in the Airflow UI. Fix failures before adding more features.

9. Turn the DAG on only after manual runs work.

### Level 3 definition of done

- Airflow starts locally with Docker Compose.
- The `weather_energy_daily` DAG appears in the UI.
- A manual run finishes successfully.
- A failed API request retries at least once.
- Task logs show the date range processed and record counts, but never secrets.
- The analytics table has no duplicate business keys after repeated DAG runs.
- The README includes one screenshot of a successful DAG run after it is implemented.

### Level 3 implementation order

1. Add Airflow services and health checks to a separate Compose profile.
2. Add a minimal DAG that calls the existing pipeline once.
3. Split the DAG into weather, price, load, transform, and validation tasks.
4. Add retries, task timeouts, `catchup=False`, and a documented schedule.
5. Test a manual run, an intentional failure, and a repeated run.
6. Add the successful-run screenshot and operating instructions to this README.

## Nice-to-have ideas

Only start these after all Level 3 definition-of-done items work.

- Add a Streamlit dashboard reading `analytics.weather_energy_hourly`.
- Add dbt models and dbt tests.
- Add GitHub Actions for `pytest` and formatting checks.
- Fetch price data directly from a documented SMARD endpoint instead of using a manual sample.
- Add another city and compare locations.
- Add data freshness checks.
- Add a simple data-quality report.

## Near-term project vision

After Level 3, this project can become a small but realistic energy analytics
portfolio project. The next useful iteration would download price data through
a documented source instead of relying on a hand-curated CSV, retain the raw
source files for reproducibility, and add freshness and completeness checks.
Once those foundations are stable, a Streamlit dashboard could show price and
weather trends, compare cities, and expose simple relationships such as price
changes during cold or windy periods. The dashboard should read from the
analytics table rather than contain pipeline logic.

Longer term, the team could add a forecast or anomaly-detection experiment,
containerize the application for deployment, and use CI/CD to run tests and
data-quality checks automatically. These ideas should follow a reliable,
observable batch pipeline; they are not prerequisites for Level 3.

## Common rules

- Keep each task small and runnable.
- Prefer clear code over clever code.
- Add type hints and documentation only where they help understanding.
- Use UTC consistently.
- Never put secrets in Git.
- Validate input data before loading it.
- Do not call an implementation complete until it works from a clean clone.

## Roadmap checklist

### Level 1

- [ ] Create virtual environment and dependencies
- [ ] Download weather data to CSV
- [ ] Add a small electricity-price sample
- [ ] Clean prices to hourly UTC data
- [ ] Create final joined CSV
- [ ] Review code as a team

### Level 2

- [ ] Add PostgreSQL with Docker Compose
- [ ] Create raw and analytics tables
- [ ] Refactor scripts into Python modules
- [ ] Add idempotent loads
- [ ] Add validation and logging
- [ ] Add at least two pytest tests

### Level 3

- [ ] Add Airflow locally
- [ ] Create and parse the DAG
- [ ] Trigger a successful manual run
- [ ] Add retries and useful task logs
- [ ] Turn on the daily schedule
- [ ] Add a screenshot and clean-clone test

## License

Choose a license before publishing the repository. MIT is a simple option for a learning portfolio project.

## Engineer 1 — Level 2 weather component

The implemented package follows the structure in `PROJECT_SETUP_GUIDE.md`:
`src/weather_energy/`. Install it from the repository root:

```bash
uv sync --extra dev --extra database
source .venv/bin/activate
```

`clients/weather_client.py` now provides `fetch_weather(start_date, end_date)`
with Hamburg as the default city. It returns the six weather columns from the
Level 1 script, with timezone-aware UTC datetimes and numeric measurements.
It rejects missing fields, invalid values, non-hourly timestamps, and duplicate
`(timestamp_utc, city)` keys. Requests use a 30-second timeout; logs include the
requested dates, city, row count, and request failures.

The existing CSV command still works and writes timestamps ending in `Z`:

```bash
python scripts/get_weather.py --start-date 2025-01-01 --end-date 2025-06-29
pytest
ruff check .
```

For the teammate integrating PostgreSQL, apply `sql/create_tables.sql` to the
configured database first. It currently creates only `raw.weather_hourly`.
Then use the weather functions inside a caller-managed transaction:

```python
import os
from datetime import date

import psycopg

from weather_energy.clients.weather_client import fetch_weather
from weather_energy.database.loader import load_weather

weather = fetch_weather(date(2025, 1, 1), date(2025, 1, 7))
# Set DATABASE_URL in your environment; never commit credentials.
with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
    load_weather(connection, weather)
```

The connection context commits on success and rolls back on failure. The loader
validates again before SQL and uses `ON CONFLICT (timestamp_utc, city) DO UPDATE`,
so existing hours are updated rather than inserted twice.

This completes the weather component's implementation. Shared Docker setup,
price/analytics database tables, and the full Level 2 pipeline entry point still
need team integration. Unit tests mock HTTP and database connections; they do
not establish that a live API request or PostgreSQL deployment works.
