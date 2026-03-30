import os
from dotenv import load_dotenv

load_dotenv()

# snowflake connector is picky about None vs empty string
# learned this the hard way at Nagarro when half our loads failed silently

SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
    "user": os.getenv("SNOWFLAKE_USER"),
    "password": os.getenv("SNOWFLAKE_PASSWORD"),
    "database": os.getenv("SNOWFLAKE_DATABASE", "ANALYTICS_DB"),
    "schema": os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "ETL_WH"),
    "role": os.getenv("SNOWFLAKE_ROLE", "ETL_ROLE"),
}

# strip .snowflakecomputing.com if someone pastes the full url
# this tripped us up so many times
if SNOWFLAKE_CONFIG["account"]:
    SNOWFLAKE_CONFIG["account"] = SNOWFLAKE_CONFIG["account"].replace(
        ".snowflakecomputing.com", ""
    )

POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "source_db"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}

# pipeline settings
CSV_INPUT_DIR = os.getenv("CSV_INPUT_DIR", "./data/input")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 10000))


def validate_config():
    """Quick sanity check before we start the pipeline.
    Trust me you don't want to find out your creds are missing
    halfway through a 2 hour load."""
    required = ["account", "user", "password"]
    missing = [k for k in required if not SNOWFLAKE_CONFIG.get(k)]
    if missing:
        raise ValueError(
            f"Missing Snowflake config: {', '.join(missing)}. "
            f"Check your .env file."
        )
    return True
