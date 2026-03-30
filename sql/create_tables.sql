-- Star schema for analytics
-- Designed for a typical e-commerce / retail use case
-- We used this exact pattern at Nagarro for multiple client projects

-- ============================================
-- DIMENSION TABLES
-- ============================================

CREATE TABLE IF NOT EXISTS DIM_CUSTOMER (
    customer_sk          NUMBER AUTOINCREMENT PRIMARY KEY,
    customer_id          VARCHAR(50) NOT NULL,        -- business key
    first_name           VARCHAR(100),
    last_name            VARCHAR(100),
    email                VARCHAR(200),
    phone                VARCHAR(50),
    address              VARCHAR(500),
    city                 VARCHAR(100),
    state                VARCHAR(50),
    country              VARCHAR(50) DEFAULT 'AU',
    customer_segment     VARCHAR(50),                 -- retail, wholesale, etc
    -- SCD Type 2 columns
    effective_date       TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    expiry_date          TIMESTAMP DEFAULT '9999-12-31',
    is_current           BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS DIM_PRODUCT (
    product_sk           NUMBER AUTOINCREMENT PRIMARY KEY,
    product_id           VARCHAR(50) NOT NULL,
    product_name         VARCHAR(300),
    category             VARCHAR(100),
    sub_category         VARCHAR(100),
    brand                VARCHAR(100),
    unit_price           FLOAT,
    unit_cost            FLOAT,
    -- not doing SCD on products for now, just overwrite
    last_updated         TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS DIM_DATE (
    date_key             NUMBER PRIMARY KEY,           -- YYYYMMDD format
    full_date            DATE NOT NULL,
    day_of_week          NUMBER,
    day_name             VARCHAR(10),
    month_number         NUMBER,
    month_name           VARCHAR(10),
    quarter              NUMBER,
    year                 NUMBER,
    is_weekend           BOOLEAN,
    fiscal_year          NUMBER,                       -- some clients have different fiscal years
    fiscal_quarter       NUMBER
);

-- populate dim_date for 2020-2026
-- we generate this once and forget about it
INSERT INTO DIM_DATE
SELECT
    TO_NUMBER(TO_CHAR(d.date_val, 'YYYYMMDD')) as date_key,
    d.date_val as full_date,
    DAYOFWEEK(d.date_val) as day_of_week,
    DAYNAME(d.date_val) as day_name,
    MONTH(d.date_val) as month_number,
    MONTHNAME(d.date_val) as month_name,
    QUARTER(d.date_val) as quarter,
    YEAR(d.date_val) as year,
    CASE WHEN DAYOFWEEK(d.date_val) IN (0, 6) THEN TRUE ELSE FALSE END as is_weekend,
    -- Australian fiscal year runs Jul-Jun
    CASE WHEN MONTH(d.date_val) >= 7 THEN YEAR(d.date_val) + 1 ELSE YEAR(d.date_val) END as fiscal_year,
    CASE
        WHEN MONTH(d.date_val) IN (7,8,9) THEN 1
        WHEN MONTH(d.date_val) IN (10,11,12) THEN 2
        WHEN MONTH(d.date_val) IN (1,2,3) THEN 3
        ELSE 4
    END as fiscal_quarter
FROM (
    SELECT DATEADD(day, SEQ4(), '2020-01-01'::DATE) as date_val
    FROM TABLE(GENERATOR(ROWCOUNT => 2557))  -- ~7 years
) d
WHERE d.date_val <= '2026-12-31';


-- ============================================
-- FACT TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS FACT_SALES (
    sale_id              NUMBER AUTOINCREMENT PRIMARY KEY,
    order_id             VARCHAR(50) NOT NULL,
    order_date_key       NUMBER REFERENCES DIM_DATE(date_key),
    customer_sk          NUMBER REFERENCES DIM_CUSTOMER(customer_sk),
    product_sk           NUMBER REFERENCES DIM_PRODUCT(product_sk),
    quantity             NUMBER,
    unit_price           FLOAT,
    discount_pct         FLOAT DEFAULT 0,
    total_amount         FLOAT,                        -- quantity * unit_price * (1 - discount_pct)
    tax_amount           FLOAT,
    shipping_cost        FLOAT DEFAULT 0,
    order_status         VARCHAR(50),                  -- pending, shipped, delivered, returned
    payment_method       VARCHAR(50),
    loaded_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- index on commonly queried columns
-- snowflake doesn't use traditional indexes but clustering keys help
ALTER TABLE FACT_SALES CLUSTER BY (order_date_key, customer_sk);
