"""
Main pipeline orchestrator.
Runs extract -> transform -> load in sequence with timing and error handling.

Usage:
    python -m etl.pipeline --source csv --file data/orders.csv --target orders
    python -m etl.pipeline --source postgres --table public.customers --target customers
"""

import argparse
import time
import sys
from datetime import datetime

from etl.extract import extract_csv, extract_postgres_table
from etl.transform import (
    clean_column_names,
    handle_nulls,
    deduplicate,
    cast_types,
    validate_dataframe,
)
from etl.load import load_dataframe


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] PIPELINE | {msg}")


def run_pipeline(source_type, target_table, **kwargs):
    """Run the full ETL pipeline.

    This is the main function that ties everything together.
    We time each step because when something takes forever in prod
    you want to know which part is slow.
    """
    pipeline_start = time.time()
    stats = {"source": source_type, "target": target_table}

    log(f"Starting pipeline: {source_type} -> {target_table}")
    log("=" * 60)

    # ---- EXTRACT ----
    log("STEP 1: Extract")
    extract_start = time.time()

    try:
        if source_type == "csv":
            filepath = kwargs.get("file")
            if not filepath:
                raise ValueError("--file required for csv source")
            df = extract_csv(filepath)

        elif source_type == "postgres":
            table = kwargs.get("table")
            where = kwargs.get("where")
            if not table:
                raise ValueError("--table required for postgres source")
            df = extract_postgres_table(table, where)

        else:
            raise ValueError(f"Unknown source type: {source_type}")

    except Exception as e:
        log(f"EXTRACT FAILED: {e}")
        return {"success": False, "error": str(e), "step": "extract"}

    extract_time = time.time() - extract_start
    stats["extract_rows"] = len(df)
    stats["extract_time"] = round(extract_time, 2)
    log(f"Extract complete: {len(df)} rows in {extract_time:.2f}s")

    # ---- TRANSFORM ----
    log("STEP 2: Transform")
    transform_start = time.time()

    try:
        df = clean_column_names(df)
        df = handle_nulls(df, strategy="fill")

        # deduplicate if key columns specified
        key_cols = kwargs.get("key_columns")
        if key_cols:
            df = deduplicate(df, key_cols)

        # type casting if specified
        type_map = kwargs.get("type_map")
        if type_map:
            df = cast_types(df, type_map)

    except Exception as e:
        log(f"TRANSFORM FAILED: {e}")
        return {"success": False, "error": str(e), "step": "transform"}

    transform_time = time.time() - transform_start
    stats["transform_rows"] = len(df)
    stats["transform_time"] = round(transform_time, 2)
    log(f"Transform complete: {len(df)} rows in {transform_time:.2f}s")

    # ---- LOAD ----
    log("STEP 3: Load")
    load_start = time.time()

    try:
        merge = kwargs.get("merge", False)
        rows_loaded = load_dataframe(
            df, target_table,
            key_columns=key_cols,
            merge=merge
        )
    except Exception as e:
        log(f"LOAD FAILED: {e}")
        return {"success": False, "error": str(e), "step": "load"}

    load_time = time.time() - load_start
    stats["load_rows"] = rows_loaded
    stats["load_time"] = round(load_time, 2)
    log(f"Load complete: {rows_loaded} rows in {load_time:.2f}s")

    # ---- SUMMARY ----
    total_time = time.time() - pipeline_start
    stats["total_time"] = round(total_time, 2)
    stats["success"] = True

    log("=" * 60)
    log("PIPELINE COMPLETE")
    log(f"  Source:     {source_type}")
    log(f"  Target:     {target_table}")
    log(f"  Extracted:  {stats['extract_rows']} rows ({stats['extract_time']}s)")
    log(f"  Loaded:     {stats.get('load_rows', 'N/A')} rows ({stats['load_time']}s)")
    log(f"  Total time: {total_time:.2f}s")
    log("=" * 60)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Snowflake ETL Pipeline")
    parser.add_argument("--source", required=True, choices=["csv", "postgres"],
                        help="Data source type")
    parser.add_argument("--target", required=True, help="Target table name in Snowflake")
    parser.add_argument("--file", help="CSV file path (for csv source)")
    parser.add_argument("--table", help="Postgres table name (for postgres source)")
    parser.add_argument("--where", help="Optional WHERE clause for postgres")
    parser.add_argument("--keys", help="Comma-separated key columns for dedup/merge")
    parser.add_argument("--merge", action="store_true", help="Merge into final table")

    args = parser.parse_args()

    key_cols = args.keys.split(",") if args.keys else None

    result = run_pipeline(
        source_type=args.source,
        target_table=args.target,
        file=args.file,
        table=args.table,
        where=args.where,
        key_columns=key_cols,
        merge=args.merge,
    )

    if not result.get("success"):
        log(f"Pipeline failed at step: {result.get('step')}")
        log(f"Error: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
