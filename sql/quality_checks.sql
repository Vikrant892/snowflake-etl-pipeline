-- Data quality checks
-- Run these after each pipeline load to catch issues early
-- I usually schedule these as a separate task in Snowflake

-- ============================================
-- NULL CHECKS
-- ============================================

-- Check for null business keys — these should never be null
SELECT 'DIM_CUSTOMER' as table_name, 'customer_id' as column_name,
       COUNT(*) as null_count
FROM DIM_CUSTOMER
WHERE customer_id IS NULL

UNION ALL

SELECT 'DIM_PRODUCT', 'product_id',
       COUNT(*)
FROM DIM_PRODUCT
WHERE product_id IS NULL

UNION ALL

SELECT 'FACT_SALES', 'order_id',
       COUNT(*)
FROM FACT_SALES
WHERE order_id IS NULL;


-- ============================================
-- DUPLICATE CHECKS
-- ============================================

-- Check for duplicate current records in SCD Type 2 dimension
-- if this returns rows, something went wrong with the SCD logic
SELECT customer_id, COUNT(*) as duplicate_count
FROM DIM_CUSTOMER
WHERE is_current = TRUE
GROUP BY customer_id
HAVING COUNT(*) > 1;

-- Duplicate orders — shouldn't happen
SELECT order_id, COUNT(*) as duplicate_count
FROM FACT_SALES
GROUP BY order_id
HAVING COUNT(*) > 1;


-- ============================================
-- REFERENTIAL INTEGRITY
-- ============================================

-- Sales pointing to non-existent customers
-- snowflake doesn't enforce FKs so we have to check manually
SELECT f.sale_id, f.customer_sk
FROM FACT_SALES f
LEFT JOIN DIM_CUSTOMER c ON f.customer_sk = c.customer_sk
WHERE c.customer_sk IS NULL
  AND f.customer_sk IS NOT NULL;

-- Sales pointing to non-existent products
SELECT f.sale_id, f.product_sk
FROM FACT_SALES f
LEFT JOIN DIM_PRODUCT p ON f.product_sk = p.product_sk
WHERE p.product_sk IS NULL
  AND f.product_sk IS NOT NULL;

-- Sales with invalid date keys
SELECT f.sale_id, f.order_date_key
FROM FACT_SALES f
LEFT JOIN DIM_DATE d ON f.order_date_key = d.date_key
WHERE d.date_key IS NULL
  AND f.order_date_key IS NOT NULL;


-- ============================================
-- DATA FRESHNESS
-- ============================================

-- When was the last load? If it's more than 24hrs something might be stuck
SELECT
    'DIM_CUSTOMER' as table_name,
    MAX(effective_date) as last_load,
    DATEDIFF('hour', MAX(effective_date), CURRENT_TIMESTAMP()) as hours_since_load
FROM DIM_CUSTOMER

UNION ALL

SELECT
    'FACT_SALES',
    MAX(loaded_at),
    DATEDIFF('hour', MAX(loaded_at), CURRENT_TIMESTAMP())
FROM FACT_SALES;


-- ============================================
-- ROW COUNT SUMMARY
-- ============================================
-- quick sanity check — if counts drop dramatically something is wrong

SELECT 'DIM_CUSTOMER' as table_name, COUNT(*) as row_count FROM DIM_CUSTOMER
UNION ALL
SELECT 'DIM_PRODUCT', COUNT(*) FROM DIM_PRODUCT
UNION ALL
SELECT 'DIM_DATE', COUNT(*) FROM DIM_DATE
UNION ALL
SELECT 'FACT_SALES', COUNT(*) FROM FACT_SALES;
