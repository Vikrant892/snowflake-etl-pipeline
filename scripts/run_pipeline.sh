#!/bin/bash
# Run the ETL pipeline
# Usage:
#   ./scripts/run_pipeline.sh csv data/orders.csv orders
#   ./scripts/run_pipeline.sh postgres public.customers customers

set -e

SOURCE_TYPE=${1:-csv}
SOURCE_PATH=${2:-data/input/orders.csv}
TARGET=${3:-orders}

echo "============================================"
echo "Snowflake ETL Pipeline"
echo "============================================"
echo "Source type:  $SOURCE_TYPE"
echo "Source path:  $SOURCE_PATH"
echo "Target table: $TARGET"
echo "Started at:   $(date)"
echo "============================================"

# check .env exists
if [ ! -f .env ]; then
    echo "WARNING: .env file not found. Copy .env.example and fill in your creds."
    echo "  cp .env.example .env"
    exit 1
fi

# activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# run based on source type
if [ "$SOURCE_TYPE" == "csv" ]; then
    python -m etl.pipeline --source csv --file "$SOURCE_PATH" --target "$TARGET"
elif [ "$SOURCE_TYPE" == "postgres" ]; then
    python -m etl.pipeline --source postgres --table "$SOURCE_PATH" --target "$TARGET"
else
    echo "Unknown source type: $SOURCE_TYPE"
    echo "Use 'csv' or 'postgres'"
    exit 1
fi

echo ""
echo "Pipeline finished at: $(date)"
