/* ============================================================================
   04 - POWER BI READ-ONLY ACCESS
   Dedicated read-only role + service account + reporting warehouse, scoped to
   the MART layer only. Power BI physically cannot reach RAW/STG or write.
   ============================================================================ */

-- ---------- Role + service user (read-only, MART only) ----------
USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS BI_READER_ROLE
  COMMENT = 'Read-only role for Power BI reporting on the MART layer';

CREATE USER IF NOT EXISTS PBI_SVC
  PASSWORD = '<SET_A_STRONG_PASSWORD>'
  DEFAULT_ROLE = BI_READER_ROLE
  DEFAULT_WAREHOUSE = WH_REPORT
  MUST_CHANGE_PASSWORD = FALSE
  COMMENT = 'Service account for Power BI';

GRANT ROLE BI_READER_ROLE TO USER PBI_SVC;
GRANT ROLE BI_READER_ROLE TO ROLE SYSADMIN;

-- ---------- Dedicated reporting warehouse (isolated from ingestion) ----------
USE ROLE SYSADMIN;
CREATE WAREHOUSE IF NOT EXISTS WH_REPORT
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Compute for Power BI queries';

-- ---------- Grant read-only access to MART (and only MART) ----------
USE ROLE SECURITYADMIN;
GRANT USAGE ON WAREHOUSE WH_REPORT             TO ROLE BI_READER_ROLE;
GRANT USAGE ON DATABASE  SUPPLY_CHAIN          TO ROLE BI_READER_ROLE;
GRANT USAGE ON SCHEMA    SUPPLY_CHAIN.MART     TO ROLE BI_READER_ROLE;
GRANT SELECT ON ALL VIEWS    IN SCHEMA SUPPLY_CHAIN.MART TO ROLE BI_READER_ROLE;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA SUPPLY_CHAIN.MART TO ROLE BI_READER_ROLE;

SHOW GRANTS TO ROLE BI_READER_ROLE;
