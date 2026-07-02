# DAX Measures Reference

All measures are grouped into display folders in the Power BI model. Row-level flags
(`IS_OTIF`, `IS_ON_TIME`, `FILL_RATE`, `IS_STOCKOUT`, …) are computed in Snowflake MART;
the DAX below aggregates them, so `AVERAGE` of a 1/0 flag becomes a percentage.

## Procurement KPIs — on `FACT_PURCHASE_ORDERS`

| Measure | DAX | Format |
|---|---|---|
| PO Lines | `COUNTROWS(FACT_PURCHASE_ORDERS)` | `#,0` |
| Procurement Spend | `SUM(FACT_PURCHASE_ORDERS[PO_AMOUNT])` | `#,0` |
| Inbound OTIF % | `AVERAGE(FACT_PURCHASE_ORDERS[IS_OTIF])` | `0.0%` |
| Inbound On-Time % | `AVERAGE(FACT_PURCHASE_ORDERS[IS_ON_TIME])` | `0.0%` |
| Inbound In-Full % | `AVERAGE(FACT_PURCHASE_ORDERS[IS_IN_FULL])` | `0.0%` |
| Avg Lead Time (Days) | `AVERAGE(FACT_PURCHASE_ORDERS[LEAD_TIME_DAYS])` | `0.0` |
| Avg Days Late (Inbound) | `AVERAGE(FACT_PURCHASE_ORDERS[DAYS_LATE])` | `0.0` |

## Fulfillment KPIs — on `FACT_SALES_ORDERS`

| Measure | DAX | Format |
|---|---|---|
| Sales Order Lines | `COUNTROWS(FACT_SALES_ORDERS)` | `#,0` |
| Total Revenue | `SUM(FACT_SALES_ORDERS[REVENUE])` | `#,0` |
| Total Freight Cost | `SUM(FACT_SALES_ORDERS[FREIGHT_COST])` | `#,0` |
| Outbound OTIF % | `AVERAGE(FACT_SALES_ORDERS[IS_OTIF])` | `0.0%` |
| On-Time Delivery % | `AVERAGE(FACT_SALES_ORDERS[IS_ON_TIME])` | `0.0%` |
| Fill Rate % | `AVERAGE(FACT_SALES_ORDERS[FILL_RATE])` | `0.0%` |
| Avg Delivery Days | `AVERAGE(FACT_SALES_ORDERS[DELIVERY_DAYS])` | `0.0` |
| Freight per Unit | `DIVIDE(SUM(FACT_SALES_ORDERS[FREIGHT_COST]), SUM(FACT_SALES_ORDERS[SHIPPED_QTY]))` | `0.00` |

## Inventory KPIs — on `FACT_INVENTORY`

| Measure | DAX | Format |
|---|---|---|
| Stockout Rate % | `AVERAGE(FACT_INVENTORY[IS_STOCKOUT])` | `0.0%` |
| Below Reorder % | `AVERAGE(FACT_INVENTORY[IS_BELOW_REORDER])` | `0.0%` |
| Below Safety Stock % | `AVERAGE(FACT_INVENTORY[IS_BELOW_SAFETY])` | `0.0%` |
| Total Stock Value | `SUM(FACT_INVENTORY[STOCK_VALUE])` | `#,0` |
| Avg On Hand Qty | `AVERAGE(FACT_INVENTORY[ON_HAND_QTY])` | `#,0` |

## Relationships

Single-direction, one-to-many from each fact to its dimensions. Primary date link is
each fact's **order/snapshot date** → `DIM_DATE[DATE_KEY]`. Secondary dates
(delivery, received) are **inactive** role-playing relationships, activated via
`USERELATIONSHIP` inside date-specific measures when needed.
