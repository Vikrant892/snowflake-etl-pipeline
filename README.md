# Snowflake ETL Pipeline

A production-style ETL pipeline that standardises data loading from CSV files and Postgres databases into Snowflake. Built as a personal project to replace manual UI-based imports with an automated workflow covering extraction, cleaning, deduplication, and proper dimensional modelling.

## Architecture

```
Source Systems          ETL Pipeline              Snowflake
+-----------+       +----------------+       +------------------+
| CSV Files |------>|                |       |  Staging Tables  |
+-----------+       |   Extract      |       |  (STG_*)         |
                    |      |         |       +--------+---------+
+-----------+       |   Transform    |                |
| Postgres  |------>|      |         |       +--------v---------+
+-----------+       |   Stage & Load |------>|  Star Schema     |
                    |      |         |       |  - DIM_CUSTOMER  |
                    |   MERGE        |       |  - DIM_PRODUCT   |
                    +----------------+       |  - DIM_DATE      |
                                             |  - FACT_SALES    |
                                             +------------------+
```

**Flow:** Source → Extract (pandas/psycopg2) → Transform (clean, dedupe, SCD) → Stage (PUT/COPY) → Load (MERGE) → Snowflake

## Star Schema

The warehouse uses a classic star schema:

- **DIM_CUSTOMER** - SCD Type 2, tracks changes to email, address, segment over time with `effective_date`, `expiry_date`, and `is_current` flags
- **DIM_PRODUCT** - Simple overwrite, no history tracking (products don't change that often for our use case)
- **DIM_DATE** - Pre-populated calendar dimension (2020-2026), includes Australian fiscal year/quarter because most of our clients were AU-based
- **FACT_SALES** - Grain is one row per order line item, references all three dimensions

## Setup

1. Clone the repo and create a virtual env:

```bash
git clone https://github.com/Vikrant892/snowflake-etl-pipeline.git
cd snowflake-etl-pipeline
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

2. Copy the env file and fill in your Snowflake creds:

```bash
cp .env.example .env
# edit .env with your actual credentials
```

3. Run the SQL scripts in Snowflake to set up the schema:

```sql
-- Run these in order in Snowflake worksheet
-- 1. Create the star schema tables
@sql/create_tables.sql

-- 2. Set up staging tables and file format
@sql/staging.sql
```

4. Run the pipeline:

```bash
# Load from CSV
python -m etl.pipeline --source csv --file data/input/orders.csv --target orders

# Load from Postgres
python -m etl.pipeline --source postgres --table public.customers --target customers

# With merge (upsert) into final table
python -m etl.pipeline --source csv --file data/input/customers.csv --target customers --keys customer_id --merge

# Or use the shell script
./scripts/run_pipeline.sh csv data/input/orders.csv orders
```

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
snowflake-etl-pipeline/
├── config/settings.py       # Snowflake + Postgres connection config from env vars
├── etl/
│   ├── extract.py           # CSV reader, Postgres connector
│   ├── transform.py         # Clean columns, handle nulls, dedupe, SCD Type 2
│   ├── load.py              # Snowflake PUT/COPY, staging tables, MERGE
│   └── pipeline.py          # Orchestrator - ties E, T, L together with timing
├── sql/
│   ├── create_tables.sql    # Star schema DDL (dims + fact)
│   ├── staging.sql          # Staging table DDL + file format
│   └── quality_checks.sql   # Post-load data quality queries
├── tests/
│   └── test_transform.py    # Unit tests for transform functions
└── scripts/
    └── run_pipeline.sh      # Convenience wrapper script
```

## Lessons Learned

Some Snowflake quirks that bit us:

1. **Account format** - Don't include `.snowflakecomputing.com` in the account name. The connector adds it automatically. We had this wrong for weeks.

2. **PUT file paths on Windows** - Need forward slashes even on Windows. The connector doesn't handle backslashes. Cost me a whole afternoon debugging.

3. **NULL handling in COPY** - Snowflake treats empty strings and the literal `NULL` differently. Our `NULL_IF` list in the file format covers the common cases but you might need to add more depending on your source data.

4. **SCD Type 2 at scale** - The pandas-based SCD logic works fine for dimensions under ~500k rows. For larger dimensions you'd want to push the SCD logic into Snowflake SQL with MERGE + window functions. We hit this limit with one client's customer table.

5. **Staging table cleanup** - We `CREATE OR REPLACE` staging tables each run so they don't pile up. Some teams use `TRANSIENT` tables instead to save on Time Travel storage costs.

6. **Date formats** - Snowflake connector is picky about date formats. If your CSV has dates in weird formats, handle the parsing in Python first before loading. We spent ages debugging `TIMESTAMP_FORMAT` mismatches.

## What I'd Do Differently

- Add Airflow/Prefect for scheduling instead of cron + shell scripts
- Use Snowflake tasks for the quality checks instead of running them manually
- Add Slack notifications for pipeline failures (we were checking logs manually which is not great)
- Consider dbt for the transformation layer if the SQL logic gets complex
