import pandas as pd
import psycopg2
import os
from datetime import datetime
from config.settings import POSTGRES_CONFIG, CSV_INPUT_DIR


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] EXTRACT | {msg}")


def extract_csv(filepath):
    """Read a CSV into a dataframe. Nothing fancy."""
    log(f"Reading CSV: {filepath}")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"CSV not found: {filepath}")

    df = pd.read_csv(filepath)
    log(f"Got {len(df)} rows, {len(df.columns)} columns")
    return df


def extract_all_csvs(directory=None):
    """Read all CSVs from a directory and return dict of dataframes.
    We typically dump exports from upstream systems into a folder
    and this picks them all up.
    """
    dir_path = directory or CSV_INPUT_DIR
    if not os.path.isdir(dir_path):
        raise FileNotFoundError(f"Input directory not found: {dir_path}")

    csv_files = [f for f in os.listdir(dir_path) if f.endswith(".csv")]
    log(f"Found {len(csv_files)} CSV files in {dir_path}")

    results = {}
    for fname in csv_files:
        table_name = fname.replace(".csv", "").lower()
        full_path = os.path.join(dir_path, fname)
        results[table_name] = extract_csv(full_path)

    return results


def extract_postgres(query, table_name=None):
    """Pull data from postgres source.
    We used this a lot at Nagarro when clients had their transactional
    data sitting in RDS postgres and needed it in Snowflake for reporting.
    """
    if not POSTGRES_CONFIG.get("password"):
        raise ValueError("POSTGRES_PASSWORD not set in env")

    log(f"Connecting to Postgres ({POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']})")
    conn = psycopg2.connect(**POSTGRES_CONFIG)

    try:
        df = pd.read_sql(query, conn)
        name = table_name or "query"
        log(f"Extracted {len(df)} rows from {name}")
        return df
    finally:
        conn.close()


def _validate_table_name(table_name):
    """Validate table name to prevent SQL injection."""
    import re
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    return table_name


def extract_postgres_table(table_name, where_clause=None):
    """Convenience wrapper - most of the time we just want the whole table.
    Be careful with big tables though, no LIMIT here on purpose because
    we usually want everything for the warehouse.
    """
    safe_name = _validate_table_name(table_name)
    query = f"SELECT * FROM {safe_name}"
    if where_clause:
        query += f" WHERE {where_clause}"
    return extract_postgres(query, table_name)
