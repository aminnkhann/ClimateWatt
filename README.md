# Weather-Energy Analytics Pipeline

A robust, automated ETL (Extract, Transform, Load) system designed to integrate high-resolution meteorological data with German electricity market pricing for cross-domain analytics.

## Project Goal
The objective of this pipeline is to synthesize hourly weather observations and German electricity spot-market prices into a unified dataset. This enables stakeholders to conduct granular analysis, such as identifying correlations between temperature fluctuations and price volatility, specifically focused on the city of **Hamburg**.

## System Architecture

The system utilizes Apache Airflow for robust orchestration, ensuring reliable daily execution of the data pipeline.

```mermaid
graph LR
    subgraph Sources [Data Ingestion]
        API[Open-Meteo API]
        CSV[SMARD Market Data]
    end

    subgraph Orchestration [Automation]
        AF[Airflow Scheduler]
    end

    subgraph Storage [Persistence]
        RAW[(PostgreSQL: Raw Schema)]
        ANALYTICS[(PostgreSQL: Analytics Schema)]
    end

    API -->|Fetch| AF
    CSV -->|Fetch| AF
    AF -->|Load| RAW
    RAW -->|Transform & Join| ANALYTICS
```

## Data Pipeline Flow

The ETL process is broken into idempotent, task-oriented stages managed by the Airflow DAG `weather_energy_daily`.

```mermaid
graph TD
    A([Start]) --> B[Fetch Weather API]
    A --> C[Fetch Price CSV]
    B --> D[Load to raw.weather_hourly]
    C --> E[Load to raw.electricity_price_hourly]
    D --> F{Join Data}
    E --> F
    F --> G[Upsert to analytics.weather_energy_hourly]
    G --> H([End/Validate])
```

## Technical Stack

- **Orchestration:** Apache Airflow 2
- **Language:** Python 3.12
- **Data Engineering:** pandas (transformation & normalization)
- **Database:** PostgreSQL 16
- **Containerization:** Docker & Docker Compose

## Core Configuration (Hamburg)

The pipeline is pre-configured to process data for Hamburg.

| Parameter | Value |
| :--- | :--- |
| **City** | Hamburg |
| **Latitude** | 53.5511 |
| **Longitude** | 9.9937 |
| **Timezone** | UTC |

## Deployment & Setup

This project uses Docker Compose for environment provisioning. Ensure Docker is installed on your host system.

### 1. Initialize Infrastructure

```bash
# Start PostgreSQL container
docker compose up -d postgres

# Initialize Airflow Environment
docker compose --profile airflow up airflow-init
docker compose --profile airflow up -d airflow-webserver airflow-scheduler
```

### 2. Configuration
Create `.env` and `.env.city` files in the repository root based on the provided examples. These files store database credentials, API endpoints, and location-specific parameters.

---

*This project provides a reliable foundation for energy-market data analysis, supporting incremental data loading and ensuring high data integrity through strict validation rules.*
