# From Three Scripts to a Pipeline

## Why this project exists

The project began with a simple question: how do hourly weather observations and
German electricity prices look when placed on the same UTC timeline?

The answer was built incrementally. The team started with CSV scripts, added tests
and continuous integration, refactored the scripts into reusable Python modules,
and then introduced PostgreSQL and Docker as the Level 2 foundation.

The most important lesson is that a data pipeline is more than transformation code.
It also depends on shared contracts for timestamps, columns, business keys,
configuration, transactions, tests, and documented commands.

## The roadmap

The project is organized into three levels:

1. **Level 1 — Basic:** runnable scripts and CSV files.
2. **Level 2 — Intermediate:** reusable Python, PostgreSQL, tests, and Docker.
3. **Level 3 — Semi-professional:** Airflow scheduling, retries, logs, and daily runs.

The intended architecture is:

```text
Open-Meteo API       Electricity-price CSV/API
      |                       |
      +---- reusable Python clients ----+
                                      |
                              PostgreSQL raw tables
                                      |
                              pandas transformation
                                      |
                         analytics.weather_energy_hourly
                                      |
                             Airflow orchestration
```

UTC is the shared language between both sources. The current example uses Hamburg
weather data and the German/Luxembourg electricity market area `DE-LU`.

## The PR story

### PR #1 — The first join

PR #1 introduced `scripts/build_dataset.py`. It read `weather.csv` and `prices.csv`,
joined them on `timestamp_utc`, selected the analytics columns, removed invalid
rows, and formatted the final timestamps as UTC `Z` strings.

The follow-up commits hardened input validation and duplicate handling. This taught
the team that the join step depends on clear upstream file and timestamp contracts.

### PRs #2 and #3 — Price-processing experiments

PR #2 was an early, closed attempt combining the price script, tests, CI, and join
work. PR #3 was another closed attempt that explored the reusable price-client
design. Although neither branch was merged, both contributed ideas later used in
the final implementation: UTC conversion, decimal normalization, hourly
aggregation, validation, and tests.

### PR #4 — Weather ingestion

PR #4 made weather ingestion runnable. The Open-Meteo script accepts coordinates
and a date range, requests hourly data, validates the response, checks duplicate
weather keys, and writes `data/output/weather.csv`.

The UTC correction in its history was important: weather and price timestamps must
mean the same hour before a join can be trusted.

### PR #5 — Continuous integration

PR #5 added GitHub Actions for automated tests. Pull requests now receive a
repeatable quality check instead of relying only on a developer’s local machine.

### PR #6 — Level 1 price preparation

PR #6 completed the Level 1 price path. It reads the input sample, validates and
cleans values, converts timestamps to UTC, aggregates sub-hourly data, preserves
the market area, and writes `data/output/prices.csv`.

### PR #7 — A closed Level 2 price attempt

PR #7 described the intended Level 2 price client and PostgreSQL loading behavior:
reusable functions, business keys, idempotency, and database tests. It was closed,
but its design ideas were retained in the later merged price work.

### PR #8 — Reproducible Level 1

PR #8 added a small committed electricity-price fixture, documented that it is a
hand-curated teaching sample, and fixed the final lint issue in the join script.

The Level 1 workflow became:

```bash
python scripts/get_weather.py
python scripts/prepare_prices.py
python scripts/build_dataset.py
```

It produces:

```text
data/output/weather.csv
data/output/prices.csv
data/output/weather_energy_hourly.csv
```

Generated output remains ignored by Git; the small input fixture is committed for
reproducibility.

### PR #9 — Reusable weather client

PR #9 moved weather logic into `src/weather_energy/clients/weather_client.py`.
The client returns a DataFrame and validates API structure, fields, measurements,
hour alignment, coordinates, date ranges, and duplicate `(timestamp_utc, city)`
keys. The Level 1 script became a thin command-line wrapper.

### PR #10 — Engineer 3’s Level 2 foundation

PR #10 added the central Level 2 infrastructure:

- reusable transformation in `weather_energy.transform`;
- raw and analytics PostgreSQL tables;
- idempotent database loaders;
- Docker Compose for local PostgreSQL;
- the `weather_energy.run_pipeline` entry point;
- environment configuration and data-source documentation;
- transformation and integration tests.

Review caught several integration problems during this PR: an outdated weather
function signature, partial schema conflicts, embedded database credentials,
single-city join assumptions, and inefficient row materialization. Resolving them
was part of the learning: integration contracts must be tested across modules, not
only inside each branch.

### PR #11 — Level 2 price client

PR #11 completed the reusable price client. It supports comma- and semicolon-
separated files, source-column normalization, German and ISO dates, Europe/Berlin
to UTC conversion, daylight-saving transitions, German and international number
formats, invalid-value rejection, hourly aggregation, market-area normalization,
sorting, and unique price business keys.

Its tests cover the difficult time-series cases, especially repeated and
nonexistent local hours.

### PR #12 — Final cleanup

PR #12 corrected the README command for the `src/` package layout and fixed the
remaining Ruff import-order issue. It was small, but it reinforced that
documentation and quality checks are part of the deliverable.

## What exists now

### Reusable source clients

```text
src/weather_energy/clients/
├── weather_client.py
└── price_client.py
```

The weather client fetches and validates Open-Meteo data. The price client reads,
normalizes, validates, and aggregates price data. Both return pandas DataFrames.

### Transformation

`src/weather_energy/transform/weather_energy.py` converts timestamps to UTC,
validates required values, joins the sources, and checks the analytics key:

```text
timestamp_utc + city + market_area
```

The join supports multiple cities and market areas while preventing duplicate
analytics business keys.

### Database model

`sql/create_tables.sql` creates:

```text
raw.weather_hourly
raw.electricity_price_hourly
analytics.weather_energy_hourly
```

The raw tables preserve source-oriented records. The analytics table stores joined
records. PostgreSQL primary keys protect the natural business keys during reruns.

### Loading and orchestration

The Level 2 runner follows this sequence:

```text
fetch weather
  → read and prepare prices
  → validate and join
  → initialize database
  → load raw weather
  → load raw prices
  → load analytics data
```

Database writes use conflict-aware upserts. The caller owns the transaction, so a
pipeline run can commit all related writes together.

## What we expect when running it

### Level 1

From the repository root:

```bash
python scripts/get_weather.py
python scripts/prepare_prices.py
python scripts/build_dataset.py
```

The first command downloads hourly weather, the second produces hourly UTC prices,
and the third creates the final joined CSV.

### Level 2

Install database dependencies and start PostgreSQL:

```bash
pip install -e ".[database,dev]"
docker compose up -d postgres
python -m weather_energy.run_pipeline
```

The runner fetches the configured weather range, prepares prices, creates the
database objects if needed, and upserts raw and analytics records. Running it again
with the same business keys should update existing rows rather than duplicate them.

The date range is configured in `.env.city`. For example,
`WEATHER_START_DATE=2025-01-01` and `WEATHER_DAYS=180` fetch an inclusive
180-day weather period. The price source must cover the same period; otherwise
the inner join produces analytics rows only for overlapping timestamps.

Useful verification queries are:

```sql
SELECT COUNT(*) FROM raw.weather_hourly;
SELECT COUNT(*) FROM raw.electricity_price_hourly;
SELECT COUNT(*) FROM analytics.weather_energy_hourly;

SELECT timestamp_utc, city, market_area
FROM analytics.weather_energy_hourly
ORDER BY timestamp_utc DESC
LIMIT 10;
```

The project is still a manually run batch pipeline. It is not yet an Airflow job,
streaming service, dashboard, or production deployment.

## Lessons for future projects

### Define interfaces before parallel development

The most expensive integration problems came from small differences in function
signatures, timestamp types, table columns, and transaction ownership. Agree on
these contracts before branches diverge.

### Treat time zones as part of the data model

UTC is not merely a display format. It determines whether records join correctly
and whether daylight-saving transitions create missing or duplicate hours.

### Enforce keys in code and in the database

DataFrame validation catches bad input early. Database primary keys and conflict
handling protect reruns and concurrent writes. Both layers are necessary.

### Keep scripts thin and modules reusable

Scripts are convenient user-facing entry points. Modules are the reusable units
for tests, pipeline runners, and future Airflow tasks. Duplicating logic between
them would make every future change riskier.

### Test failure behavior

The strongest tests describe malformed API responses, invalid timestamps, missing
columns, DST transitions, invalid prices, duplicate keys, and database behavior—not
only the happy path.

### Review is a design tool

The review history caught stale signatures, schema conflicts, embedded credentials,
join-cardinality assumptions, and memory inefficiencies. Review comments improved
the architecture rather than merely checking formatting.

## Next stage: Level 3 Airflow orchestration

Level 3 should begin only after the Level 2 pipeline has been run from a clean
Docker volume and run twice without duplicate business keys.

The first DAG should be named:

```text
weather_energy_daily
```

It should call the tested functions in `src/weather_energy/`; it should not copy
API, cleaning, transformation, or database logic into the DAG.

Suggested flow:

```text
fetch_weather  ──────> load_weather_raw ────┐
                                             ├──> build_analytics ──> validate_analytics
fetch_prices   ──────> load_prices_raw  ────┘
```

Level 3 activities are:

1. Add Airflow services using a versioned official Docker setup.
2. Mount `dags/`, `src/`, and `sql/` into the Airflow containers.
3. Create `dags/weather_energy_daily.py`.
4. Configure a daily 02:00 UTC schedule, retries, and `catchup=False`.
5. Confirm the DAG appears without import errors.
6. Trigger and inspect a manual run.
7. Log dates and row counts without exposing secrets.
8. Verify repeated scheduled runs preserve database keys.

Level 3 is complete when Airflow starts, the DAG appears, a manual run succeeds,
failed API requests retry, logs are useful and safe, and repeated runs do not create
duplicates.

## Handoff checklist

- [ ] `pytest -q` passes.
- [ ] `ruff check .` passes.
- [ ] `docker compose config` passes.
- [ ] PostgreSQL starts locally.
- [ ] The schema initializes from an empty volume.
- [ ] The Level 2 runner completes once.
- [ ] The Level 2 runner completes twice without duplicate keys.
- [ ] `.env` remains local and credentials are not committed.
- [ ] The next contributor understands that Airflow is the next stage.

The project has moved from “make one script run” to “operate a tested batch
pipeline.” The next chapter is about scheduling, observability, retries, recovery,
and confidence that tomorrow’s run is as safe as today’s.
