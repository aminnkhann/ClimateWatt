# Project setup guide: Weather and Electricity Pipeline

This guide explains **which files to create**, **which dependencies to install**, and **how to run the project in VS Code or another Python IDE**.

Build the project gradually. Do not create Airflow, PostgreSQL, dbt, Docker, and a dashboard on the first day. First make Level 1 work locally. Then add Level 2 and Level 3.

---

## 1. Tools to install first

Every team member should install:

- **Git**
- **Python 3.11** (recommended common version for the team)
- **VS Code**
- VS Code extensions:
  - Python (Microsoft)
  - Pylance (Microsoft)
  - Docker (Microsoft) — needed from Level 2
  - YAML (Red Hat) — useful for Docker Compose and GitHub Actions
  - PostgreSQL client/extension — optional, useful from Level 2
- **Docker Desktop** on Windows/macOS, or Docker Engine plus Docker Compose on Linux — needed from Level 2

Check the core tools in a terminal:

```bash
python --version
git --version
docker --version
docker compose version
```

Docker commands will not work before Level 2. That is expected.

---

## 2. Create and clone repository

One team member creates the GitHub repository and adds the other two as collaborators.

Suggested repository name:

```text
weather-energy-data-pipeline
```

Each teammate clones it locally:

```bash
git clone https://github.com/YOUR-ORGANISATION-OR-USERNAME/weather-energy-data-pipeline.git
cd weather-energy-data-pipeline
```

Open the folder in VS Code:

```bash
code .
```

If `code .` is not available, open VS Code manually and select **File → Open Folder**.

---

## 3. Final folder structure

This is the target structure after Level 3. Create folders only when they are needed; empty folders can contain a `.gitkeep` file.

```text
weather-energy-data-pipeline/
├── .github/
│   ├── pull_request_template.md
│   └── workflows/
│       └── ci.yml                         # Optional after Level 2
├── .vscode/
│   ├── settings.json
│   └── launch.json
├── dags/
│   └── weather_energy_daily.py             # Level 3
├── data/
│   ├── input/
│   │   └── electricity_prices_sample.csv   # Small public sample only
│   └── output/                             # Generated files; ignored by Git
├── docker/
│   └── airflow/
│       └── Dockerfile                      # Only if a custom image is needed
├── docs/
│   ├── team-agreement.md
│   ├── data-sources.md
│   └── decisions.md
├── scripts/
│   ├── get_weather.py                      # Level 1
│   ├── prepare_prices.py                   # Level 1
│   └── build_dataset.py                    # Level 1
├── sql/
│   └── create_tables.sql                   # Level 2
├── src/
│   └── weather_energy/
│       ├── __init__.py
│       ├── config.py                       # Level 2
│       ├── run_pipeline.py                 # Level 2
│       ├── clients/
│       │   ├── __init__.py
│       │   ├── weather_client.py
│       │   └── price_client.py
│       ├── database/
│       │   ├── __init__.py
│       │   └── loader.py
│       └── transform/
│           ├── __init__.py
│           └── weather_energy.py
├── tests/
│   ├── __init__.py
│   ├── test_transform.py
│   └── test_weather_client.py
├── .env.example
├── .gitignore
├── docker-compose.yml                       # Level 2, extended in Level 3
├── pyproject.toml
├── README.md
└── requirements-airflow.txt                 # Level 3 only
```

### Why `src/weather_energy/`?

Putting reusable code in a package prevents the project from becoming a collection of unrelated scripts. In Level 1, `scripts/` is intentionally simple. In Level 2, move the real logic to `src/weather_energy/` and keep `run_pipeline.py` as the application entry point.

The `dags/` folder contains only Airflow orchestration. It must call functions from `src/weather_energy/`; it must not repeat API, cleaning, or database code.

---

## 4. Files to create now: Level 1

Create these files first:

```text
README.md
.gitignore
pyproject.toml
data/input/electricity_prices_sample.csv
scripts/get_weather.py
scripts/prepare_prices.py
scripts/build_dataset.py
```

### `scripts/get_weather.py`

Responsibility: call Open-Meteo and write a weather CSV.

Input:

- City coordinates
- Start date and end date

Output:

```text
data/output/weather.csv
```

Minimum output columns:

```text
timestamp_utc,city,temperature_c,relative_humidity_percent,wind_speed_kmh,cloud_cover_percent
```

### `scripts/prepare_prices.py`

Responsibility: read the downloaded SMARD sample, clean names and timestamps, and produce hourly price data.

Input:

```text
data/input/electricity_prices_sample.csv
```

Output:

```text
data/output/prices.csv
```

Minimum output columns:

```text
timestamp_utc,market_area,electricity_price_eur_mwh
```

If the source contains quarter-hourly data, aggregate four values to one hourly value using the mean. Document this rule in `docs/data-sources.md`.

### `scripts/build_dataset.py`

Responsibility: join weather and price data by `timestamp_utc`.

Input:

```text
data/output/weather.csv
data/output/prices.csv
```

Output:

```text
data/output/weather_energy_hourly.csv
```

Required final columns:

```text
timestamp_utc,city,market_area,temperature_c,electricity_price_eur_mwh
```

### `data/input/electricity_prices_sample.csv`

Add a small public sample only: ideally two to seven days of data. Do not put large raw downloads into Git.

The team must record:

- Original source URL or SMARD export name
- Download date
- Original time zone
- Original resolution (hourly or quarter-hourly)
- Unit (`EUR/MWh`)

Put this information in `docs/data-sources.md`.

---

## 5. Python dependency file

Use **one `pyproject.toml`** for the application, developer tools, and tests. Do not create a `requirements.txt` as well; two dependency files often drift apart.

Create `pyproject.toml` with this content:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "weather-energy-data-pipeline"
version = "0.1.0"
description = "Learning batch pipeline for weather and German electricity-price data"
readme = "README.md"
requires-python = ">=3.11,<3.13"
dependencies = [
    "pandas>=2.2,<3.0",
    "requests>=2.32,<3.0",
    "python-dotenv>=1.0,<2.0",
]

[project.optional-dependencies]
database = [
    "psycopg[binary]>=3.2,<4.0",
    "sqlalchemy>=2.0,<3.0",
]
dev = [
    "pytest>=8.0,<9.0",
    "pytest-cov>=5.0,<7.0",
    "ruff>=0.6,<1.0",
]
all = [
    "weather-energy-data-pipeline[database,dev]",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-q"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.coverage.run]
source = ["weather_energy"]
```

### Dependency purpose

| Package | Level | Purpose |
|---|---:|---|
| `requests` | 1 | Calls Open-Meteo and later price-data endpoints |
| `pandas` | 1 | Reads CSV files, cleans timestamps, joins datasets |
| `python-dotenv` | 2 | Reads local environment variables from `.env` |
| `psycopg[binary]` | 2 | Connects Python to PostgreSQL |
| `sqlalchemy` | 2 | Optional database connection and table-loading support |
| `pytest` | 2 | Runs automated tests |
| `pytest-cov` | 2 | Measures test coverage |
| `ruff` | 2 | Checks formatting/import/basic code-quality problems |

Do not add packages “just in case.” Every dependency adds maintenance work.

### Why Airflow is not in `pyproject.toml`

Airflow has strict dependency constraints and is easiest for beginners to run inside Docker in Level 3. Adding it to the normal development environment can cause version conflicts with other packages.

For Level 3, create `requirements-airflow.txt` only if the Airflow container needs project packages:

```text
pandas>=2.2,<3.0
requests>=2.32,<3.0
python-dotenv>=1.0,<2.0
psycopg[binary]>=3.2,<4.0
```

Use the Apache Airflow Docker Compose setup and its documented constraints/version approach when the team reaches Level 3. Do not blindly install Airflow with an unconstrained `pip install apache-airflow` command.

---

## 6. Virtual environment and installation

Run these commands from the repository root.

### Linux/macOS

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

`-e` means editable installation. Python uses the local source code immediately after changes, so developers do not need to reinstall the package after each edit.

When starting Level 2, install database dependencies too:

```bash
pip install -e ".[database,dev]"
```

Check that installation succeeded:

```bash
python -c "import pandas, requests; print('Dependencies are ready')"
pytest
ruff check .
```

---

## 7. VS Code configuration

Create the `.vscode` folder and these files.

### `.vscode/settings.json`

```json
{
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "python.testing.pytestArgs": ["tests"],
  "python.analysis.extraPaths": ["${workspaceFolder}/src"],
  "editor.formatOnSave": true,
  "files.exclude": {
    "**/__pycache__": true,
    "**/.pytest_cache": true
  }
}
```

### `.vscode/launch.json`

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Level 1: Download weather",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/scripts/get_weather.py",
      "console": "integratedTerminal"
    },
    {
      "name": "Level 1: Prepare prices",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/scripts/prepare_prices.py",
      "console": "integratedTerminal"
    },
    {
      "name": "Level 1: Build dataset",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/scripts/build_dataset.py",
      "console": "integratedTerminal"
    },
    {
      "name": "Level 2: Run pipeline",
      "type": "debugpy",
      "request": "launch",
      "module": "weather_energy.run_pipeline",
      "console": "integratedTerminal"
    }
  ]
}
```

### Select the correct interpreter

In VS Code:

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS).
2. Search for **Python: Select Interpreter**.
3. Select the interpreter inside `.venv`.
4. Open a new terminal in VS Code.
5. Confirm the terminal starts with `(.venv)`.

If VS Code reports `ModuleNotFoundError`, first check that it is using `.venv`, not a global Python installation.

---

## 8. Git files and secrets

### `.gitignore`

Create this file:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/

# Virtual environments
.venv/
venv/

# Environment variables and secrets
.env

# Tests and tooling
.pytest_cache/
.coverage
htmlcov/
.ruff_cache/

# Generated project data
data/output/*
!data/output/.gitkeep

# Local operating-system and editor files
.DS_Store
.vscode/*.log
.idea/
```

### `.env.example`

Commit this template, but never commit the real `.env` file:

```env
# PostgreSQL settings for local development; needed from Level 2
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=weather_energy
POSTGRES_USER=weather_user
POSTGRES_PASSWORD=change_me

# Application settings
CITY=Hamburg
LATITUDE=53.5511
LONGITUDE=9.9937
MARKET_AREA=DE-LU
```

Every developer creates their local file once:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Do not put passwords, tokens, or any secret in source code, a notebook, a Git commit, a screenshot, or a pull-request comment.

---

## 9. Level 2 files: PostgreSQL and modules

Create these files only after the three Level 1 scripts produce a valid final CSV.

### `docker-compose.yml`

Start with PostgreSQL only:

```yaml
services:
  postgres:
    image: postgres:16
    container_name: weather-energy-postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "${POSTGRES_PORT}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./sql/create_tables.sql:/docker-entrypoint-initdb.d/create_tables.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

Start it:

```bash
docker compose up -d postgres
docker compose ps
```

Stop it:

```bash
docker compose down
```

Delete all local database data only when you intentionally want a clean start:

```bash
docker compose down -v
```

### `sql/create_tables.sql`

Start with three simple tables. All time values are UTC.

```sql
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS raw.weather_hourly (
    timestamp_utc TIMESTAMPTZ NOT NULL,
    city TEXT NOT NULL,
    temperature_c DOUBLE PRECISION,
    relative_humidity_percent DOUBLE PRECISION,
    wind_speed_kmh DOUBLE PRECISION,
    cloud_cover_percent DOUBLE PRECISION,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (timestamp_utc, city)
);

CREATE TABLE IF NOT EXISTS raw.electricity_price_hourly (
    timestamp_utc TIMESTAMPTZ NOT NULL,
    market_area TEXT NOT NULL,
    electricity_price_eur_mwh DOUBLE PRECISION NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (timestamp_utc, market_area)
);

CREATE TABLE IF NOT EXISTS analytics.weather_energy_hourly (
    timestamp_utc TIMESTAMPTZ NOT NULL,
    city TEXT NOT NULL,
    market_area TEXT NOT NULL,
    temperature_c DOUBLE PRECISION,
    electricity_price_eur_mwh DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (timestamp_utc, city, market_area)
);
```

### Python module responsibilities

| File | Responsibility |
|---|---|
| `config.py` | Load and validate environment variables |
| `clients/weather_client.py` | Fetch and parse Open-Meteo data |
| `clients/price_client.py` | Read the price sample, then later fetch price data automatically |
| `transform/weather_energy.py` | Validate, clean, aggregate, and join DataFrames |
| `database/loader.py` | Insert data using PostgreSQL upsert logic |
| `run_pipeline.py` | Call the components in the correct order |

The Level 2 command should be:

```bash
python -m weather_energy.run_pipeline
```

### Tests to add

Create at least these tests:

```text
tests/test_transform.py
tests/test_weather_client.py
```

Start with these cases:

- Weather and price DataFrames join correctly on UTC hour.
- Duplicate timestamps are detected or removed according to a documented rule.
- Missing required columns raise a useful error.
- Open-Meteo response parsing produces the expected columns.

Run them:

```bash
pytest
pytest --cov=weather_energy
ruff check .
```

---

## 10. Level 3 files: Airflow

Add Airflow only after the Level 2 command and tests work.

Create:

```text
dags/weather_energy_daily.py
requirements-airflow.txt
```

The DAG should orchestrate existing functions. It should not contain pandas transformation logic or raw SQL blocks.

Recommended first DAG tasks:

```text
fetch_weather -> load_weather_raw
fetch_prices  -> load_prices_raw
load_weather_raw + load_prices_raw -> build_analytics -> validate_analytics
```

For the very first Airflow version, one task that calls `run_pipeline` is acceptable. Split it only after it succeeds consistently.

Use these initial DAG settings:

```python
schedule="0 2 * * *"
catchup=False
retries=2
```

Airflow should run in Docker. It must use the same project source code and database configuration as Level 2.

---

## 11. Daily developer workflow

Each developer should use this flow:

```bash
# Get current main branch
git checkout main
git pull origin main

# Create one branch for one issue
git checkout -b feature/weather-api

# Install dependencies if this is a new machine
pip install -e ".[dev]"

# Work, test, and check code
pytest
ruff check .

# Save work
git add scripts/get_weather.py tests/test_weather_client.py
git commit -m "feat: add weather download script"
git push -u origin feature/weather-api
```

Then create a Pull Request on GitHub. The pull request description should explain:

- What changed
- How the reviewer can run it
- Test results
- Any known limitation

Example:

```markdown
## What changed
- Added an Open-Meteo client for Hamburg hourly weather data.
- Writes a CSV to `data/output/weather.csv`.

## How to test
python scripts/get_weather.py

## Result
- Output has UTC timestamps and expected weather columns.
```

---

## 12. First team checklist

### Repository and IDE

- [ ] Create a private GitHub repository
- [ ] Invite both teammates as collaborators
- [ ] Protect the `main` branch with pull-request review
- [ ] Clone the repository on every computer
- [ ] Install Python 3.11 and create `.venv`
- [ ] Select `.venv` as the VS Code interpreter
- [ ] Install `pip install -e ".[dev]"`

### Level 1

- [ ] Create `pyproject.toml`, `.gitignore`, and `.env.example`
- [ ] Add data-source documentation
- [ ] Add the weather script
- [ ] Add a small price sample and cleaning script
- [ ] Add the join script
- [ ] Run scripts successfully from a clean clone

### Level 2

- [ ] Add PostgreSQL Docker Compose service
- [ ] Create schemas and tables
- [ ] Refactor scripts into `src/weather_energy/`
- [ ] Add tests and Ruff checks
- [ ] Make database loading idempotent

### Level 3

- [ ] Add Airflow Docker services
- [ ] Create the DAG
- [ ] Trigger a successful manual run
- [ ] Add retries and inspect logs
- [ ] Enable the daily schedule

---

## 13. Troubleshooting

| Problem | First thing to check |
|---|---|
| `ModuleNotFoundError` in VS Code | Select `.venv` with **Python: Select Interpreter**, then run `pip install -e ".[dev]"` |
| `python` command not found | Install Python 3.11 or use `python3` on Linux/macOS |
| `pytest` command not found | Activate `.venv` and reinstall the development dependencies |
| `docker compose` fails | Start Docker Desktop, or check the Docker Engine service |
| PostgreSQL does not start | Check `docker compose logs postgres` and confirm `.env` exists |
| Port 5432 is already in use | Change `POSTGRES_PORT` in `.env`, for example to `5433` |
| Git rejects a push to `main` | This is expected: create a feature branch and open a pull request |
| Price and weather rows do not join | Check both timestamp columns are parsed as UTC and have the same hourly grain |

---

## Rule of progress

Do not proceed because a file exists. Proceed only after the previous level runs successfully:

```text
Level 1: CSV output exists and is correct
Level 2: PostgreSQL loads work and tests pass
Level 3: Airflow DAG runs successfully
```

A small reliable pipeline is a better portfolio project than a large collection of half-configured tools.
