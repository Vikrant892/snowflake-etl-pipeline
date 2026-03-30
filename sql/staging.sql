-- Staging tables for the ETL pipeline
-- These get CREATE OR REPLACE'd every run so they're always fresh
-- Kept here mostly for documentation, the actual DDL is generated in load.py

-- ============================================
-- STAGING TABLES
-- ============================================

CREATE OR REPLACE TABLE STG_CUSTOMERS (
    customer_id          VARCHAR(50),
    first_name           VARCHAR(100),
    last_name            VARCHAR(100),
    email                VARCHAR(200),
    phone                VARCHAR(50),
    address              VARCHAR(500),
    city                 VARCHAR(100),
    state                VARCHAR(50),
    country              VARCHAR(50),
    customer_segment     VARCHAR(50),
    loaded_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE STG_PRODUCTS (
    product_id           VARCHAR(50),
    product_name         VARCHAR(300),
    category             VARCHAR(100),
    sub_category         VARCHAR(100),
    brand                VARCHAR(100),
    unit_price           FLOAT,
    unit_cost            FLOAT,
    loaded_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE STG_ORDERS (
    order_id             VARCHAR(50),
    customer_id          VARCHAR(50),
    product_id           VARCHAR(50),
    order_date           VARCHAR(50),   -- keep as string initially, cast during transform
    quantity             NUMBER,
    unit_price           FLOAT,
    discount_pct         FLOAT,
    total_amount         FLOAT,
    tax_amount           FLOAT,
    shipping_cost        FLOAT,
    order_status         VARCHAR(50),
    payment_method       VARCHAR(50),
    loaded_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================
-- FILE FORMAT
-- ============================================
-- reusable file format so we don't repeat ourselves in every COPY INTO
-- snowflake is picky about date formats in CSVs, the TIMESTAMP_FORMAT
-- here saved us a lot of headaches

CREATE OR REPLACE FILE FORMAT CSV_ETL_FORMAT
    TYPE = 'CSV'
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('', 'NULL', 'null', 'None', 'N/A')
    TRIM_SPACE = TRUE
    ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
    TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS';

-- ============================================
-- INTERNAL STAGE
-- ============================================

CREATE OR REPLACE STAGE ETL_INTERNAL_STAGE
    FILE_FORMAT = CSV_ETL_FORMAT;
