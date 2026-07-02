"""
Synthetic Supply Chain dataset for an end-to-end ADF -> Snowflake -> Power BI project.
Company: "Meridian Industrial Supply Co." - a mid-size distributor of industrial components.

Design goal: data that tells a STORY (not random noise), so the Power BI dashboard
surfaces real, defensible insights you can talk through in an interview:
  - A handful of UNRELIABLE suppliers (long lead times, low inbound OTIF)
  - Chronic STOCKOUTS on certain product/warehouse combos
  - SEASONAL demand spike in Q4
  - FREIGHT cost varying by ship mode & distance

Outputs 9 CSVs: 6 dimensions + 3 facts (star schema).
"""

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
OUT = "/home/claude/data"
import os; os.makedirs(OUT, exist_ok=True)

START = pd.Timestamp("2024-01-01")
END   = pd.Timestamp("2025-12-31")

# ---------------------------------------------------------------------------
# DIM_DATE
# ---------------------------------------------------------------------------
dates = pd.date_range(START, END, freq="D")
dim_date = pd.DataFrame({"DATE_KEY": dates.strftime("%Y%m%d").astype(int),
                         "FULL_DATE": dates})
dim_date["YEAR"]        = dates.year
dim_date["QUARTER"]     = "Q" + dates.quarter.astype(str)
dim_date["MONTH_NUM"]   = dates.month
dim_date["MONTH_NAME"]  = dates.strftime("%B")
dim_date["MONTH_YEAR"]  = dates.strftime("%b %Y")
dim_date["WEEK_OF_YEAR"]= dates.isocalendar().week.values
dim_date["DAY_OF_MONTH"]= dates.day
dim_date["DAY_NAME"]    = dates.strftime("%A")
dim_date["IS_WEEKEND"]  = dates.dayofweek.isin([5, 6])
dim_date.to_csv(f"{OUT}/dim_date.csv", index=False)

# ---------------------------------------------------------------------------
# DIM_SUPPLIER  (some are deliberately unreliable -> the procurement story)
# ---------------------------------------------------------------------------
sup_countries = [("Germany","EMEA"),("India","APAC"),("China","APAC"),
                 ("USA","AMER"),("Italy","EMEA"),("Mexico","AMER"),
                 ("Japan","APAC"),("Poland","EMEA")]
n_sup = 25
sup_rows = []
for i in range(1, n_sup + 1):
    country, region = sup_countries[rng.integers(0, len(sup_countries))]
    # reliability tier distribution: most ok, a few poor
    tier = rng.choice(["A","B","C"], p=[0.45, 0.35, 0.20])
    base_lead = {"A": rng.integers(7,14), "B": rng.integers(14,25),
                 "C": rng.integers(28,45)}[tier]
    base_otif = {"A": rng.uniform(0.93,0.99), "B": rng.uniform(0.80,0.92),
                 "C": rng.uniform(0.55,0.75)}[tier]
    sup_rows.append([f"SUP{i:03d}", f"{country} Components {i:02d}", country, region,
                     tier, base_lead, round(base_otif, 3)])
dim_supplier = pd.DataFrame(sup_rows, columns=[
    "SUPPLIER_KEY","SUPPLIER_NAME","COUNTRY","REGION",
    "RELIABILITY_TIER","BASE_LEAD_TIME_DAYS","TARGET_OTIF"])
dim_supplier.to_csv(f"{OUT}/dim_supplier.csv", index=False)

# ---------------------------------------------------------------------------
# DIM_PRODUCT  (each product sourced from one supplier)
# ---------------------------------------------------------------------------
categories = ["Bearings","Fasteners","Hydraulics","Electronics",
              "Seals & Gaskets","Valves","Motors","Sensors"]
n_prod = 80
prod_rows = []
for i in range(1, n_prod + 1):
    cat = categories[rng.integers(0, len(categories))]
    unit_cost  = round(rng.uniform(5, 400), 2)
    unit_price = round(unit_cost * rng.uniform(1.25, 1.9), 2)   # margin
    abc = rng.choice(["A","B","C"], p=[0.2, 0.3, 0.5])          # value class
    supplier = dim_supplier["SUPPLIER_KEY"].iloc[rng.integers(0, n_sup)]
    prod_rows.append([f"PRD{i:04d}", f"{cat[:3].upper()}-{i:04d}",
                      f"{cat} Item {i:03d}", cat, abc, supplier,
                      unit_cost, unit_price])
dim_product = pd.DataFrame(prod_rows, columns=[
    "PRODUCT_KEY","SKU","PRODUCT_NAME","CATEGORY","ABC_CLASS",
    "PRIMARY_SUPPLIER_KEY","UNIT_COST","UNIT_PRICE"])
dim_product.to_csv(f"{OUT}/dim_product.csv", index=False)

# ---------------------------------------------------------------------------
# DIM_WAREHOUSE  (one warehouse runs hot -> stockout story)
# ---------------------------------------------------------------------------
wh = [("WH01","Frankfurt DC","Frankfurt","Germany","EMEA"),
      ("WH02","Hyderabad DC","Hyderabad","India","APAC"),
      ("WH03","Chicago DC","Chicago","USA","AMER"),
      ("WH04","Singapore DC","Singapore","Singapore","APAC"),
      ("WH05","Milan DC","Milan","Italy","EMEA"),
      ("WH06","Monterrey DC","Monterrey","Mexico","AMER")]
dim_warehouse = pd.DataFrame(wh, columns=[
    "WAREHOUSE_KEY","WAREHOUSE_NAME","CITY","COUNTRY","REGION"])
dim_warehouse.to_csv(f"{OUT}/dim_warehouse.csv", index=False)
STOCKOUT_WH = "WH02"  # chronically under-stocked

# ---------------------------------------------------------------------------
# DIM_CUSTOMER
# ---------------------------------------------------------------------------
cust_geo = [("USA","AMER"),("Germany","EMEA"),("India","APAC"),
            ("UK","EMEA"),("France","EMEA"),("Brazil","AMER"),
            ("Australia","APAC"),("Canada","AMER")]
segments = ["OEM","Wholesale","Retail","Government"]
n_cust = 200
cust_rows = []
for i in range(1, n_cust + 1):
    country, region = cust_geo[rng.integers(0, len(cust_geo))]
    seg = rng.choice(segments, p=[0.3, 0.35, 0.25, 0.10])
    cust_rows.append([f"CUST{i:04d}", f"Customer {i:03d}", seg, country, region])
dim_customer = pd.DataFrame(cust_rows, columns=[
    "CUSTOMER_KEY","CUSTOMER_NAME","SEGMENT","COUNTRY","REGION"])
dim_customer.to_csv(f"{OUT}/dim_customer.csv", index=False)

# ---------------------------------------------------------------------------
# DIM_SHIP_MODE
# ---------------------------------------------------------------------------
ship = [("SM1","Air",3,4.0),("SM2","Sea",30,0.8),
        ("SM3","Road",7,1.5),("SM4","Rail",12,1.0)]
dim_ship = pd.DataFrame(ship, columns=[
    "SHIP_MODE_KEY","SHIP_MODE","AVG_TRANSIT_DAYS","COST_FACTOR"])
dim_ship.to_csv(f"{OUT}/dim_ship_mode.csv", index=False)

sup_lookup  = dim_supplier.set_index("SUPPLIER_KEY")
prod_lookup = dim_product.set_index("PRODUCT_KEY")

# ---------------------------------------------------------------------------
# FACT_PURCHASE_ORDERS  (inbound / procurement)
# ---------------------------------------------------------------------------
n_po = 8000
po_dates = START + pd.to_timedelta(rng.integers(0, (END-START).days-50, n_po), "D")
po_rows = []
for i in range(n_po):
    prod = dim_product.iloc[rng.integers(0, n_prod)]
    sup_key = prod["PRIMARY_SUPPLIER_KEY"]
    sup = sup_lookup.loc[sup_key]
    wh_key = dim_warehouse["WAREHOUSE_KEY"].iloc[rng.integers(0, 6)]
    order_date = po_dates[i]
    lead = int(sup["BASE_LEAD_TIME_DAYS"])
    promised = order_date + pd.Timedelta(days=lead)
    # late deliveries: low-tier suppliers run later
    on_time_prob = float(sup["TARGET_OTIF"])
    if rng.random() < on_time_prob:
        delay = rng.integers(-3, 1)            # on or before promised
    else:
        delay = rng.integers(4, 25)            # meaningfully late
    received = promised + pd.Timedelta(days=int(delay))
    order_qty = int(rng.integers(50, 1500))
    # in-full: low-tier suppliers short-ship more often
    if rng.random() < on_time_prob:
        received_qty = order_qty
    else:
        received_qty = int(order_qty * rng.uniform(0.7, 0.97))
    po_rows.append([f"PO{i+1:06d}", sup_key, prod["PRODUCT_KEY"], wh_key,
                    int(order_date.strftime("%Y%m%d")),
                    int(promised.strftime("%Y%m%d")),
                    int(received.strftime("%Y%m%d")),
                    order_qty, received_qty,
                    float(prod["UNIT_COST"]),
                    round(order_qty * float(prod["UNIT_COST"]), 2)])
fact_po = pd.DataFrame(po_rows, columns=[
    "PO_ID","SUPPLIER_KEY","PRODUCT_KEY","WAREHOUSE_KEY",
    "ORDER_DATE_KEY","PROMISED_DATE_KEY","RECEIVED_DATE_KEY",
    "ORDER_QTY","RECEIVED_QTY","UNIT_COST","PO_AMOUNT"])
fact_po.to_csv(f"{OUT}/fact_purchase_orders.csv", index=False)

# ---------------------------------------------------------------------------
# FACT_INVENTORY  (weekly snapshots; STOCKOUT_WH runs low)
# ---------------------------------------------------------------------------
weeks = pd.date_range(START, END, freq="W-MON")
# assign each product to 2-3 warehouses
inv_rows = []
prod_wh_map = {}
for pk in dim_product["PRODUCT_KEY"]:
    chosen = rng.choice(dim_warehouse["WAREHOUSE_KEY"].values,
                        size=rng.integers(2, 4), replace=False)
    prod_wh_map[pk] = chosen
for pk, whs in prod_wh_map.items():
    base_demand = rng.uniform(20, 120)               # avg weekly units
    for wh_key in whs:
        safety = int(base_demand * rng.uniform(1.0, 2.0))
        reorder = int(safety + base_demand * rng.uniform(0.5, 1.5))
        level = reorder + int(base_demand * rng.uniform(2, 5))
        low = wh_key == STOCKOUT_WH and rng.random() < 0.6   # problem combo
        for wmon in weeks:
            # demand draw with Q4 seasonal lift
            season = 1.5 if wmon.month in (11, 12) else 1.0
            demand = rng.poisson(base_demand * season)
            replenish = rng.poisson(base_demand) if level < reorder else 0
            level = max(0, level - demand + replenish)
            if low:
                level = int(level * rng.uniform(0.2, 0.6))   # keep it thin
            inv_rows.append([int(wmon.strftime("%Y%m%d")), pk, wh_key,
                             int(level), reorder, safety])
fact_inv = pd.DataFrame(inv_rows, columns=[
    "SNAPSHOT_DATE_KEY","PRODUCT_KEY","WAREHOUSE_KEY",
    "ON_HAND_QTY","REORDER_POINT","SAFETY_STOCK"])
fact_inv.to_csv(f"{OUT}/fact_inventory.csv", index=False)

# ---------------------------------------------------------------------------
# FACT_SALES_ORDERS  (outbound / fulfillment; seasonal + late deliveries)
# ---------------------------------------------------------------------------
n_so = 22000
# seasonal date sampling: weight Nov/Dec heavier
day_index = pd.date_range(START, END - pd.Timedelta(days=40), freq="D")
weights = np.where(day_index.month.isin([11, 12]), 2.2, 1.0)
weights = weights / weights.sum()
so_dates = rng.choice(day_index, size=n_so, p=weights)
so_rows = []
for i in range(n_so):
    cust = dim_customer.iloc[rng.integers(0, n_cust)]
    prod = dim_product.iloc[rng.integers(0, n_prod)]
    wh_key = prod_wh_map[prod["PRODUCT_KEY"]][rng.integers(0, len(prod_wh_map[prod["PRODUCT_KEY"]]))]
    sm = dim_ship.iloc[rng.integers(0, 4)]
    order_date = pd.Timestamp(so_dates[i])
    handling = rng.integers(1, 4)
    ship_date = order_date + pd.Timedelta(days=int(handling))
    transit = int(sm["AVG_TRANSIT_DAYS"])
    promised = order_date + pd.Timedelta(days=int(handling + transit + 2))
    # warehouse WH02 fulfils late more often (ties to stockout story)
    late_prob = 0.32 if wh_key == STOCKOUT_WH else 0.14
    if rng.random() < late_prob:
        delivery = promised + pd.Timedelta(days=int(rng.integers(2, 12)))
    else:
        delivery = ship_date + pd.Timedelta(days=int(transit + rng.integers(-1, 2)))
    order_qty = int(rng.integers(5, 300))
    # fill rate: short-ship more from the under-stocked warehouse
    if wh_key == STOCKOUT_WH and rng.random() < 0.25:
        shipped_qty = int(order_qty * rng.uniform(0.5, 0.9))
    elif rng.random() < 0.08:
        shipped_qty = int(order_qty * rng.uniform(0.8, 0.98))
    else:
        shipped_qty = order_qty
    freight = round(shipped_qty * float(sm["COST_FACTOR"]) * rng.uniform(0.8, 1.3), 2)
    revenue = round(shipped_qty * float(prod["UNIT_PRICE"]), 2)
    so_rows.append([f"SO{i+1:07d}", cust["CUSTOMER_KEY"], prod["PRODUCT_KEY"],
                    wh_key, sm["SHIP_MODE_KEY"],
                    int(order_date.strftime("%Y%m%d")),
                    int(ship_date.strftime("%Y%m%d")),
                    int(promised.strftime("%Y%m%d")),
                    int(delivery.strftime("%Y%m%d")),
                    order_qty, shipped_qty, freight, revenue])
fact_so = pd.DataFrame(so_rows, columns=[
    "SO_ID","CUSTOMER_KEY","PRODUCT_KEY","WAREHOUSE_KEY","SHIP_MODE_KEY",
    "ORDER_DATE_KEY","SHIP_DATE_KEY","PROMISED_DATE_KEY","DELIVERY_DATE_KEY",
    "ORDER_QTY","SHIPPED_QTY","FREIGHT_COST","REVENUE"])
fact_so.to_csv(f"{OUT}/fact_sales_orders.csv", index=False)

# ---------------------------------------------------------------------------
# Quick sanity / story check
# ---------------------------------------------------------------------------
print("ROW COUNTS")
for f in sorted(os.listdir(OUT)):
    print(f"  {f:30s} {len(pd.read_csv(f'{OUT}/{f}')):>7,}")

print("\nSTORY CHECKS")
# inbound OTIF by tier
po = fact_po.merge(dim_supplier[["SUPPLIER_KEY","RELIABILITY_TIER"]], on="SUPPLIER_KEY")
po["on_time"] = po["RECEIVED_DATE_KEY"] <= po["PROMISED_DATE_KEY"]
po["in_full"] = po["RECEIVED_QTY"] >= po["ORDER_QTY"]
po["otif"] = po["on_time"] & po["in_full"]
print("  Inbound OTIF by supplier tier:")
print(po.groupby("RELIABILITY_TIER")["otif"].mean().round(3).to_string().replace("\n","\n    "))

# outbound on-time by warehouse
so = fact_so.copy()
so["on_time"] = so["DELIVERY_DATE_KEY"] <= so["PROMISED_DATE_KEY"]
print("\n  Outbound on-time delivery by warehouse:")
print(so.groupby("WAREHOUSE_KEY")["on_time"].mean().round(3).to_string().replace("\n","\n    "))

# stockout rate by warehouse
inv = fact_inv.copy(); inv["stockout"] = inv["ON_HAND_QTY"] <= 0
print("\n  Stockout rate by warehouse:")
print(inv.groupby("WAREHOUSE_KEY")["stockout"].mean().round(3).to_string().replace("\n","\n    "))

# seasonal revenue
so2 = so.merge(dim_date[["DATE_KEY","MONTH_NUM"]], left_on="ORDER_DATE_KEY", right_on="DATE_KEY")
print("\n  Revenue Q4 vs rest (monthly avg):")
q4 = so2[so2.MONTH_NUM.isin([11,12])]["REVENUE"].sum()/2
rest = so2[~so2.MONTH_NUM.isin([11,12])]["REVENUE"].sum()/10
print(f"    Q4 monthly avg: {q4:,.0f}   |   Other months avg: {rest:,.0f}")
