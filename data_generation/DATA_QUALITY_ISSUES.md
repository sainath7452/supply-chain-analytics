# Data Quality Issues — RAW → STG Cleaning Spec

Synthetic supply-chain landing data (`01_raw_dirty/`) contains deliberate, realistic data-quality issues. This is the spec for your Snowflake **STG** layer: each issue and the technique that fixes it. Validate your cleaned output against `02_clean_reference/`.

## Issue catalogue

### DIM_SUPPLIER

| Issue injected | Snowflake fix |
|---|---|
| Leading/trailing whitespace + mixed case in SUPPLIER_NAME/COUNTRY | `TRIM() + INITCAP()/UPPER()` |
| Lowercase REGION & RELIABILITY_TIER | `UPPER()` |
| Placeholder nulls 'N/A' and '' in COUNTRY | `NULLIF / IFF(... IN ('N/A',''), NULL ...)` |
| Typo 'Gemany' for 'Germany' | `CASE/mapping table standardisation` |
| Duplicate rows | `QUALIFY ROW_NUMBER() OVER(PARTITION BY SUPPLIER_KEY ORDER BY ...) = 1` |

### DIM_PRODUCT

| Issue injected | Snowflake fix |
|---|---|
| Inconsistent CATEGORY variants/typos ('Bearing','bearings','BEARINGS ') | `Mapping table or CASE + INITCAP()` |
| Currency-formatted strings ('$1,234.50') in UNIT_COST/UNIT_PRICE | `REPLACE($ and ,) + TRY_TO_DECIMAL` |
| Blank ABC_CLASS, lowercase classes | `UPPER() + default 'C' / flag` |
| Orphan PRIMARY_SUPPLIER_KEY (SUP999 etc.) | `LEFT JOIN supplier; quarantine or set NULL where no match` |

### DIM_CUSTOMER

| Issue injected | Snowflake fix |
|---|---|
| SEGMENT variants ('oem','O.E.M.','Govt') | `Mapping/CASE standardisation` |
| Blank CUSTOMER_NAME | `COALESCE -> 'Unknown' or flag` |
| Duplicate rows + whitespace/case in COUNTRY | `Dedup QUALIFY + TRIM/INITCAP` |

### DIM_WAREHOUSE

| Issue injected | Snowflake fix |
|---|---|
| Whitespace/case in CITY/COUNTRY + duplicate rows | `TRIM/INITCAP + dedup` |

### FACT_PURCHASE_ORDERS

| Issue injected | Snowflake fix |
|---|---|
| Mixed date formats + blanks (ORDER/PROMISED/RECEIVED) | `TRY_TO_DATE with format list / COALESCE(TRY_TO_DATE(...))` |
| Qty/amount as strings with commas & '$'; blanks | `REPLACE + TRY_TO_NUMBER/TRY_TO_DECIMAL` |
| Negative ORDER_QTY and absurd RECEIVED_QTY=999999 | `Range filter / WHERE qty > 0 AND received <= order*tolerance; quarantine` |
| Orphan SUPPLIER_KEY/PRODUCT_KEY | `Referential check via LEFT JOIN; route to reject table` |
| Duplicate PO lines | `Dedup on PO_ID via QUALIFY ROW_NUMBER()` |

### FACT_SALES_ORDERS

| Issue injected | Snowflake fix |
|---|---|
| Mixed date formats + blanks (4 date columns) | `TRY_TO_DATE format coalescing` |
| Numeric-as-string ($, commas), blanks | `REPLACE + TRY_TO_DECIMAL` |
| SHIPPED_QTY > ORDER_QTY (impossible), negative FREIGHT_COST | `Validation rules; LEAST(shipped,ordered) or quarantine; ABS/flag` |
| Orphan CUSTOMER_KEY/SHIP_MODE_KEY | `Referential integrity check` |
| Duplicate order lines | `Dedup QUALIFY ROW_NUMBER()` |

### FACT_INVENTORY

| Issue injected | Snowflake fix |
|---|---|
| Mixed date formats in SNAPSHOT_DATE | `TRY_TO_DATE coalescing` |
| Negative ON_HAND_QTY; numeric-as-string | `GREATEST(qty,0) or flag; TRY_TO_NUMBER` |
| Orphan PRODUCT_KEY; duplicate snapshots | `Referential check + dedup` |

## Cross-cutting cleaning pattern (use in every STG view)

```sql
-- Example STG pattern for a fact table loaded into RAW as all-VARCHAR
CREATE OR REPLACE VIEW STG.STG_PURCHASE_ORDERS AS
SELECT
    TRIM(PO_ID)                                              AS PO_ID,
    TRIM(SUPPLIER_KEY)                                       AS SUPPLIER_KEY,
    TRIM(PRODUCT_KEY)                                        AS PRODUCT_KEY,
    TRIM(WAREHOUSE_KEY)                                      AS WAREHOUSE_KEY,
    -- multi-format date parsing
    COALESCE(
        TRY_TO_DATE(ORDER_DATE,'YYYY-MM-DD'),
        TRY_TO_DATE(ORDER_DATE,'MM/DD/YYYY'),
        TRY_TO_DATE(ORDER_DATE,'DD-MON-YYYY'),
        TRY_TO_DATE(ORDER_DATE,'YYYY/MM/DD')
    )                                                        AS ORDER_DATE,
    -- numeric cleanup: strip $ and thousands separators, safe-cast
    TRY_TO_NUMBER(REPLACE(REPLACE(ORDER_QTY,',',''),'$','')) AS ORDER_QTY,
    TRY_TO_DECIMAL(REPLACE(REPLACE(PO_AMOUNT,',',''),'$',''),18,2) AS PO_AMOUNT
FROM RAW.PURCHASE_ORDERS
-- drop blanks / impossible values
WHERE TRY_TO_NUMBER(REPLACE(REPLACE(ORDER_QTY,',',''),'$','')) > 0
-- dedup
QUALIFY ROW_NUMBER() OVER (PARTITION BY PO_ID ORDER BY ORDER_DATE) = 1;
```

> Referential integrity: build STG dims first, then `LEFT JOIN` facts to them and route rows with no match (e.g. `SUP999`, `PRD9999`, `CUST9999`, `SM9`) to a `REJECT_*` table — talk about this as your quarantine pattern.
