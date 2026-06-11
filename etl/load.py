import snowflake.connector
import pandas as pd
import os
import tempfile
from datetime import datetime
from config.settings import SNOWFLAKE_CONFIG


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] LOAD | {msg}")


import re


def _validate_identifier(name):
    """Validate Snowflake identifier to prevent SQL injection."""
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"Invalid Snowflake identifier: {name}")
    return name


def get_connection():
    """Get snowflake connection.
    Snowflake connector is picky about None values in the config dict -
    it throws these cryptic errors if you pass None for optional fields.
    """
    # filter out None values before connecting
    config = {k: v for k, v in SNOWFLAKE_CONFIG.items() if v is not None}

    log(f"Connecting to Snowflake ({config.get('account', 'unknown')})")
    conn = snowflake.connector.connect(**config)
    return conn


def create_staging_table(conn, table_name, df):
    """Create a staging table based on dataframe schema.
    We prefix staging tables with STG_ so they're easy to identify and cleanup.
    """
    _validate_identifier(table_name)
    stg_name = f"STG_{table_name.upper()}"

    # map pandas dtypes to snowflake types
    # this mapping isn't perfect but works for 90% of cases
    type_map = {
        "int64": "NUMBER",
        "float64": "FLOAT",
        "object": "VARCHAR(500)",
        "datetime64[ns]": "TIMESTAMP",
        "bool": "BOOLEAN",
    }

    columns = []
    for col_name, dtype in df.dtypes.items():
        sf_type = type_map.get(str(dtype), "VARCHAR(500)")
        columns.append(f'"{col_name.upper()}" {sf_type}')

    cols_sql = ",\n    ".join(columns)
    ddl = f"""
    CREATE OR REPLACE TABLE {stg_name} (
        {cols_sql}
    )
    """

    cur = conn.cursor()
    try:
        cur.execute(ddl)
        log(f"Created staging table {stg_name}")
    finally:
        cur.close()

    return stg_name


def put_and_copy(conn, df, stage_table):
    """Load data into snowflake using PUT + COPY.
    This is way faster than INSERT for anything over ~1000 rows.
    We write to a temp CSV, PUT it to a snowflake internal stage,
    then COPY INTO the table.
    """
    # write df to temp csv
    tmp_dir = tempfile.mkdtemp()
    tmp_file = os.path.join(tmp_dir, f"{stage_table}.csv")
    df.to_csv(tmp_file, index=False, header=False)

    log(f"Wrote {len(df)} rows to temp file")

    cur = conn.cursor()
    try:
        stage_name = f"@%{stage_table}"

        # PUT file to stage
        # the file:// prefix is required on all platforms
        # on windows you need forward slashes - snowflake connector is picky about this
        put_path = tmp_file.replace("\\", "/")
        put_sql = f"PUT 'file://{put_path}' {stage_name} AUTO_COMPRESS=TRUE"
        cur.execute(put_sql)
        log(f"PUT file to stage {stage_name}")

        # COPY INTO table
        copy_sql = f"""
        COPY INTO {stage_table}
        FROM {stage_name}
        FILE_FORMAT = (
            TYPE = 'CSV'
            SKIP_HEADER = 0
            FIELD_OPTIONALLY_ENCLOSED_BY = '"'
            NULL_IF = ('', 'NULL', 'null')
        )
        ON_ERROR = 'CONTINUE'
        """
        cur.execute(copy_sql)
        log(f"COPY INTO {stage_table} complete")

        # check how many rows loaded
        cur.execute(f"SELECT COUNT(*) FROM {stage_table}")
        count = cur.fetchone()[0]
        log(f"Loaded {count} rows into {stage_table}")

        return count
    finally:
        cur.close()
        # cleanup temp file
        if os.path.exists(tmp_file):
            os.remove(tmp_file)


def merge_into_final(conn, stage_table, target_table, key_columns):
    """Merge staged data into final table.
    MERGE is the cleanest way to do upserts in Snowflake.
    Way better than DELETE + INSERT which I've seen people do...
    """
    key_conditions = " AND ".join(
        [f'target."{k.upper()}" = source."{k.upper()}"' for k in key_columns]
    )

    # get column list from staging table
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {stage_table} LIMIT 0")
        columns = [desc[0] for desc in cur.description]

        update_cols = ", ".join(
            [f'target."{c}" = source."{c}"' for c in columns
             if c.upper() not in [k.upper() for k in key_columns]]
        )
        insert_cols = ", ".join([f'"{c}"' for c in columns])
        source_cols = ", ".join([f'source."{c}"' for c in columns])

        merge_sql = f"""
        MERGE INTO {target_table} AS target
        USING {stage_table} AS source
        ON {key_conditions}
        WHEN MATCHED THEN
            UPDATE SET {update_cols}
        WHEN NOT MATCHED THEN
            INSERT ({insert_cols})
            VALUES ({source_cols})
        """

        cur.execute(merge_sql)
        log(f"Merged {stage_table} -> {target_table}")

    finally:
        cur.close()


def load_dataframe(df, table_name, key_columns=None, merge=False):
    """Main entry point for loading a dataframe into Snowflake.
    If merge=True and key_columns provided, does a MERGE into final table.
    Otherwise just loads into staging.
    """
    conn = get_connection()
    try:
        stg_table = create_staging_table(conn, table_name, df)
        rows_loaded = put_and_copy(conn, df, stg_table)

        if merge and key_columns:
            target = table_name.upper()
            merge_into_final(conn, stg_table, target, key_columns)
            log(f"Merge complete for {target}")

        return rows_loaded
    finally:
        conn.close()
