"""
Take the CLEAN supply-chain CSVs and inject realistic, documented data-quality
issues -> produces the *_raw.csv "landing" files that ADF will load into
Snowflake RAW. The clean files remain as the validation "gold" reference.

Every issue injected here is intentional and maps to a specific Snowflake
cleaning technique (see DATA_QUALITY_ISSUES.md).
"""

import numpy as np
import pandas as pd
import os

rng = np.random.default_rng(7)
CLEAN = "/home/claude/data"
RAW   = "/home/claude/data_raw"
os.makedirs(RAW, exist_ok=True)

# ---------- helpers ---------------------------------------------------------
def messy_text(s, r=rng):
    """leading/trailing whitespace + random casing on a minority of values"""
    if not isinstance(s, str):
        return s
    p = r.random()
    if p < 0.78: return s
    if p < 0.86: return "  " + s
    if p < 0.92: return s + "   "
    if p < 0.96: return s.upper()
    return s.lower()

def messy_money(x, r=rng):
    """mix of plain, $-prefixed and comma-grouped numbers; a few blanks"""
    if pd.isna(x): return ""
    p = r.random()
    if p < 0.03: return ""
    if p < 0.83: return f"{x}"
    if p < 0.93: return f"${x:,.2f}"
    return f"{x:,.2f}"

def messy_int(x, r=rng):
    if pd.isna(x): return ""
    p = r.random()
    if p < 0.025: return ""               # blank -> NULL
    if p < 0.90:  return str(int(x))
    return f"{int(x):,}"                   # thousands separator

def messy_date(int_key, r=rng):
    """one date column, several string formats + a few blanks"""
    try:
        d = pd.to_datetime(str(int(int_key)), format="%Y%m%d")
    except Exception:
        return ""
    p = r.random()
    if p < 0.03: return ""                 # missing
    f = r.random()
    if f < 0.68: return d.strftime("%Y-%m-%d")   # ISO (majority)
    if f < 0.80: return d.strftime("%m/%d/%Y")   # US
    if f < 0.91: return d.strftime("%d-%b-%Y")   # 15-Mar-2024
    return d.strftime("%Y/%m/%d")                # slash ISO

def add_dupes(df, frac, r=rng):
    k = int(len(df) * frac)
    dup = df.iloc[r.integers(0, len(df), k)]
    return pd.concat([df, dup], ignore_index=True)

def inject_nulls(col, frac, token="", r=rng):
    mask = r.random(len(col)) < frac
    col = col.copy()
    col[mask] = token
    return col

report = []
def log(table, issue, technique):
    report.append((table, issue, technique))

# ---------- DIM_SUPPLIER ----------------------------------------------------
s = pd.read_csv(f"{CLEAN}/dim_supplier.csv")
s["SUPPLIER_NAME"]    = s["SUPPLIER_NAME"].map(messy_text)
s["COUNTRY"]          = s["COUNTRY"].map(messy_text)
s["REGION"]           = s["REGION"].map(lambda x: x.lower() if rng.random()<0.25 else x)
s["RELIABILITY_TIER"] = s["RELIABILITY_TIER"].map(lambda x: x.lower() if rng.random()<0.3 else x)
# placeholder nulls in COUNTRY
s.loc[s.sample(2, random_state=1).index, "COUNTRY"] = ["N/A", ""]
# one typo'd country variant
s.loc[s.sample(1, random_state=3).index, "COUNTRY"] = "Gemany"
s = add_dupes(s, 0.12)
s.to_csv(f"{RAW}/dim_supplier_raw.csv", index=False)
log("DIM_SUPPLIER","Leading/trailing whitespace + mixed case in SUPPLIER_NAME/COUNTRY","TRIM() + INITCAP()/UPPER()")
log("DIM_SUPPLIER","Lowercase REGION & RELIABILITY_TIER","UPPER()")
log("DIM_SUPPLIER","Placeholder nulls 'N/A' and '' in COUNTRY","NULLIF / IFF(... IN ('N/A',''), NULL ...)")
log("DIM_SUPPLIER","Typo 'Gemany' for 'Germany'","CASE/mapping table standardisation")
log("DIM_SUPPLIER","Duplicate rows","QUALIFY ROW_NUMBER() OVER(PARTITION BY SUPPLIER_KEY ORDER BY ...) = 1")

# ---------- DIM_PRODUCT -----------------------------------------------------
p = pd.read_csv(f"{CLEAN}/dim_product.csv")
cat_variants = {"Bearings":["Bearings","bearings","BEARINGS ","Bearing"],
                "Fasteners":["Fasteners","fasteners"," Fasteners"],
                "Electronics":["Electronics","ELECTRONICS","electronics "]}
def dirty_cat(c, r=rng):
    if c in cat_variants and r.random() < 0.4:
        opts = cat_variants[c]
        return opts[r.integers(0, len(opts))]
    return c
p["CATEGORY"]   = p["CATEGORY"].map(dirty_cat)
p["SKU"]        = p["SKU"].map(messy_text)
p["ABC_CLASS"]  = p["ABC_CLASS"].map(lambda x: x.lower() if rng.random()<0.3 else x)
p.loc[p.sample(4, random_state=2).index, "ABC_CLASS"] = ""           # missing class
p["UNIT_COST"]  = p["UNIT_COST"].map(messy_money)
p["UNIT_PRICE"] = p["UNIT_PRICE"].map(messy_money)
# orphan supplier keys (FK to nowhere)
p.loc[p.sample(3, random_state=5).index, "PRIMARY_SUPPLIER_KEY"] = ["SUP999","SUP888","SUP777"]
p.to_csv(f"{RAW}/dim_product_raw.csv", index=False)
log("DIM_PRODUCT","Inconsistent CATEGORY variants/typos ('Bearing','bearings','BEARINGS ')","Mapping table or CASE + INITCAP()")
log("DIM_PRODUCT","Currency-formatted strings ('$1,234.50') in UNIT_COST/UNIT_PRICE","REPLACE($ and ,) + TRY_TO_DECIMAL")
log("DIM_PRODUCT","Blank ABC_CLASS, lowercase classes","UPPER() + default 'C' / flag")
log("DIM_PRODUCT","Orphan PRIMARY_SUPPLIER_KEY (SUP999 etc.)","LEFT JOIN supplier; quarantine or set NULL where no match")

# ---------- DIM_CUSTOMER ----------------------------------------------------
c = pd.read_csv(f"{CLEAN}/dim_customer.csv")
seg_map = {"OEM":["OEM","oem","O.E.M.","Oem"],
           "Wholesale":["Wholesale","wholesale","WHOLESALE"],
           "Retail":["Retail","retail "],
           "Government":["Government","Govt","government"]}
c["SEGMENT"] = c["SEGMENT"].map(lambda x: seg_map[x][rng.integers(0,len(seg_map[x]))]
                                if rng.random()<0.45 else x)
c["COUNTRY"] = c["COUNTRY"].map(messy_text)
c.loc[c.sample(5, random_state=4).index, "CUSTOMER_NAME"] = ""        # blank names
c = add_dupes(c, 0.05)
c.to_csv(f"{RAW}/dim_customer_raw.csv", index=False)
log("DIM_CUSTOMER","SEGMENT variants ('oem','O.E.M.','Govt')","Mapping/CASE standardisation")
log("DIM_CUSTOMER","Blank CUSTOMER_NAME","COALESCE -> 'Unknown' or flag")
log("DIM_CUSTOMER","Duplicate rows + whitespace/case in COUNTRY","Dedup QUALIFY + TRIM/INITCAP")

# ---------- DIM_WAREHOUSE ---------------------------------------------------
w = pd.read_csv(f"{CLEAN}/dim_warehouse.csv")
w["CITY"]    = w["CITY"].map(messy_text)
w["COUNTRY"] = w["COUNTRY"].map(messy_text)
w = add_dupes(w, 0.16)
w.to_csv(f"{RAW}/dim_warehouse_raw.csv", index=False)
log("DIM_WAREHOUSE","Whitespace/case in CITY/COUNTRY + duplicate rows","TRIM/INITCAP + dedup")

# ---------- DIM_SHIP_MODE (kept clean - small ref table) --------------------
pd.read_csv(f"{CLEAN}/dim_ship_mode.csv").to_csv(f"{RAW}/dim_ship_mode_raw.csv", index=False)

# ---------- DIM_DATE (kept clean - generated, not landed dirty) -------------
pd.read_csv(f"{CLEAN}/dim_date.csv").to_csv(f"{RAW}/dim_date_raw.csv", index=False)

# ---------- FACT_PURCHASE_ORDERS -------------------------------------------
po = pd.read_csv(f"{CLEAN}/fact_purchase_orders.csv")
for dc in ["ORDER_DATE_KEY","PROMISED_DATE_KEY","RECEIVED_DATE_KEY"]:
    po[dc.replace("_KEY","")] = po[dc].map(messy_date)
po = po.drop(columns=["ORDER_DATE_KEY","PROMISED_DATE_KEY","RECEIVED_DATE_KEY"])
po["ORDER_QTY"]    = po["ORDER_QTY"].map(messy_int)
po["RECEIVED_QTY"] = po["RECEIVED_QTY"].map(messy_int)
po["UNIT_COST"]    = po["UNIT_COST"].map(messy_money)
po["PO_AMOUNT"]    = po["PO_AMOUNT"].map(messy_money)
# impossible values: negative qty, received >> ordered
neg = po.sample(40, random_state=11).index
po.loc[neg, "ORDER_QTY"] = "-100"
big = po.sample(30, random_state=12).index
po.loc[big, "RECEIVED_QTY"] = "999999"
# orphan FKs
po.loc[po.sample(15, random_state=13).index, "SUPPLIER_KEY"] = "SUP999"
po.loc[po.sample(15, random_state=14).index, "PRODUCT_KEY"]  = "PRD9999"
po = add_dupes(po, 0.01)
po.to_csv(f"{RAW}/fact_purchase_orders_raw.csv", index=False)
log("FACT_PURCHASE_ORDERS","Mixed date formats + blanks (ORDER/PROMISED/RECEIVED)","TRY_TO_DATE with format list / COALESCE(TRY_TO_DATE(...))")
log("FACT_PURCHASE_ORDERS","Qty/amount as strings with commas & '$'; blanks","REPLACE + TRY_TO_NUMBER/TRY_TO_DECIMAL")
log("FACT_PURCHASE_ORDERS","Negative ORDER_QTY and absurd RECEIVED_QTY=999999","Range filter / WHERE qty > 0 AND received <= order*tolerance; quarantine")
log("FACT_PURCHASE_ORDERS","Orphan SUPPLIER_KEY/PRODUCT_KEY","Referential check via LEFT JOIN; route to reject table")
log("FACT_PURCHASE_ORDERS","Duplicate PO lines","Dedup on PO_ID via QUALIFY ROW_NUMBER()")

# ---------- FACT_SALES_ORDERS ----------------------------------------------
so = pd.read_csv(f"{CLEAN}/fact_sales_orders.csv")
for dc in ["ORDER_DATE_KEY","SHIP_DATE_KEY","PROMISED_DATE_KEY","DELIVERY_DATE_KEY"]:
    so[dc.replace("_KEY","")] = so[dc].map(messy_date)
so = so.drop(columns=["ORDER_DATE_KEY","SHIP_DATE_KEY","PROMISED_DATE_KEY","DELIVERY_DATE_KEY"])
so["ORDER_QTY"]    = so["ORDER_QTY"].map(messy_int)
so["SHIPPED_QTY"]  = so["SHIPPED_QTY"].map(messy_int)
so["FREIGHT_COST"] = so["FREIGHT_COST"].map(messy_money)
so["REVENUE"]      = so["REVENUE"].map(messy_money)
# impossible: shipped > ordered, negative freight
so.loc[so.sample(60, random_state=21).index, "SHIPPED_QTY"] = "100000"
so.loc[so.sample(40, random_state=22).index, "FREIGHT_COST"] = "-50.00"
# orphan FKs
so.loc[so.sample(25, random_state=23).index, "CUSTOMER_KEY"]  = "CUST9999"
so.loc[so.sample(20, random_state=24).index, "SHIP_MODE_KEY"] = "SM9"
so = add_dupes(so, 0.008)
so.to_csv(f"{RAW}/fact_sales_orders_raw.csv", index=False)
log("FACT_SALES_ORDERS","Mixed date formats + blanks (4 date columns)","TRY_TO_DATE format coalescing")
log("FACT_SALES_ORDERS","Numeric-as-string ($, commas), blanks","REPLACE + TRY_TO_DECIMAL")
log("FACT_SALES_ORDERS","SHIPPED_QTY > ORDER_QTY (impossible), negative FREIGHT_COST","Validation rules; LEAST(shipped,ordered) or quarantine; ABS/flag")
log("FACT_SALES_ORDERS","Orphan CUSTOMER_KEY/SHIP_MODE_KEY","Referential integrity check")
log("FACT_SALES_ORDERS","Duplicate order lines","Dedup QUALIFY ROW_NUMBER()")

# ---------- FACT_INVENTORY --------------------------------------------------
inv = pd.read_csv(f"{CLEAN}/fact_inventory.csv")
inv["SNAPSHOT_DATE"] = inv["SNAPSHOT_DATE_KEY"].map(messy_date)
inv = inv.drop(columns=["SNAPSHOT_DATE_KEY"])
inv["ON_HAND_QTY"]   = inv["ON_HAND_QTY"].map(messy_int)
inv["REORDER_POINT"] = inv["REORDER_POINT"].map(messy_int)
inv["SAFETY_STOCK"]  = inv["SAFETY_STOCK"].map(messy_int)
inv.loc[inv.sample(120, random_state=31).index, "ON_HAND_QTY"] = "-25"   # impossible negative
inv.loc[inv.sample(20, random_state=33).index, "PRODUCT_KEY"]  = "PRD9999"
inv = add_dupes(inv, 0.005)
inv.to_csv(f"{RAW}/fact_inventory_raw.csv", index=False)
log("FACT_INVENTORY","Mixed date formats in SNAPSHOT_DATE","TRY_TO_DATE coalescing")
log("FACT_INVENTORY","Negative ON_HAND_QTY; numeric-as-string","GREATEST(qty,0) or flag; TRY_TO_NUMBER")
log("FACT_INVENTORY","Orphan PRODUCT_KEY; duplicate snapshots","Referential check + dedup")

# ---------- write report ----------------------------------------------------
rep = pd.DataFrame(report, columns=["TABLE","ISSUE_INJECTED","SNOWFLAKE_FIX"])
rep.to_csv(f"{RAW}/_data_quality_manifest.csv", index=False)

print("RAW (dirty) files written to data_raw/:\n")
for f in sorted(os.listdir(RAW)):
    n = len(pd.read_csv(f"{RAW}/{f}", dtype=str))
    print(f"  {f:34s} {n:>7,} rows")

print(f"\nTotal distinct issue types injected: {len(report)}")
print("\nSample of dirty supplier rows:")
print(pd.read_csv(f'{RAW}/dim_supplier_raw.csv', dtype=str).head(6).to_string(index=False))
print("\nSample of dirty PO date/qty columns:")
print(pd.read_csv(f'{RAW}/fact_purchase_orders_raw.csv', dtype=str)
      [["PO_ID","ORDER_DATE","RECEIVED_DATE","ORDER_QTY","RECEIVED_QTY","PO_AMOUNT"]].head(8).to_string(index=False))
