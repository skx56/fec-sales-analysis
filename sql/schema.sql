-- Star schema for the FEC supplier sales warehouse.
-- Grain: one row per sales invoice line, one row per purchase-order line.
-- Fiscal year starts in April (FY24 = Apr 2023–Mar 2024).

DROP VIEW IF EXISTS vw_purchases;
DROP VIEW IF EXISTS vw_sales;
DROP TABLE IF EXISTS fact_purchases;
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_supplier;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_date (
    date_key        INTEGER PRIMARY KEY,
    date            TEXT NOT NULL,
    calendar_year   INTEGER NOT NULL,
    quarter         INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    month_name      TEXT NOT NULL,
    month_start     TEXT NOT NULL,
    fy_year         INTEGER NOT NULL,
    fy_label        TEXT NOT NULL,
    fiscal_quarter  INTEGER NOT NULL,
    fiscal_month    INTEGER NOT NULL
);

CREATE TABLE dim_supplier (
    supplier_id            TEXT PRIMARY KEY,
    supplier_name          TEXT NOT NULL,
    category_focus         TEXT NOT NULL,
    city                   TEXT NOT NULL,
    state                  TEXT NOT NULL,
    payment_terms_days     INTEGER NOT NULL,
    contracted_lead_days   INTEGER NOT NULL,
    tier                   TEXT NOT NULL,
    onboard_date           TEXT NOT NULL,
    cohort                 TEXT NOT NULL
);

CREATE TABLE dim_product (
    product_id      TEXT PRIMARY KEY,
    sku             TEXT NOT NULL UNIQUE,
    product_name    TEXT NOT NULL,
    category        TEXT NOT NULL,
    subcategory     TEXT NOT NULL,
    brand_type      TEXT NOT NULL,
    uom             TEXT NOT NULL,
    standard_cost   REAL NOT NULL,
    list_price      REAL NOT NULL
);

CREATE TABLE dim_customer (
    customer_id     TEXT PRIMARY KEY,
    customer_name   TEXT NOT NULL,
    channel         TEXT NOT NULL,
    city            TEXT NOT NULL,
    state           TEXT NOT NULL,
    region_group    TEXT NOT NULL
);

CREATE TABLE fact_sales (
    sale_id               TEXT PRIMARY KEY,
    invoice_id            TEXT NOT NULL,
    date_key              INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_id            TEXT NOT NULL REFERENCES dim_product(product_id),
    customer_id           TEXT NOT NULL REFERENCES dim_customer(customer_id),
    supplier_id           TEXT NOT NULL REFERENCES dim_supplier(supplier_id),
    quantity              REAL NOT NULL,
    return_qty            REAL NOT NULL,
    net_qty               REAL NOT NULL,
    list_price            REAL NOT NULL,
    discount_rate         REAL NOT NULL,
    unit_price            REAL NOT NULL,
    unit_cost             REAL NOT NULL,
    freight_per_unit      REAL NOT NULL,
    list_revenue          REAL NOT NULL,
    discount_amount       REAL NOT NULL,
    recognized_revenue    REAL NOT NULL,
    cogs                  REAL NOT NULL,
    freight_cost          REAL NOT NULL,
    gross_profit          REAL NOT NULL,
    contribution_profit   REAL NOT NULL
);

CREATE TABLE fact_purchases (
    purchase_id            TEXT PRIMARY KEY,
    po_id                  TEXT NOT NULL,
    date_key               INTEGER NOT NULL REFERENCES dim_date(date_key),
    supplier_id            TEXT NOT NULL REFERENCES dim_supplier(supplier_id),
    product_id             TEXT NOT NULL REFERENCES dim_product(product_id),
    qty_ordered            REAL NOT NULL,
    qty_received           REAL NOT NULL,
    qty_defective          REAL NOT NULL,
    unit_cost              REAL NOT NULL,
    purchase_value         REAL NOT NULL,
    contracted_lead_days   INTEGER NOT NULL,
    actual_lead_days       INTEGER NOT NULL,
    on_time_flag           INTEGER NOT NULL
);

CREATE INDEX idx_sales_date ON fact_sales(date_key);
CREATE INDEX idx_sales_product ON fact_sales(product_id);
CREATE INDEX idx_sales_supplier ON fact_sales(supplier_id);
CREATE INDEX idx_sales_customer ON fact_sales(customer_id);
CREATE INDEX idx_purch_date ON fact_purchases(date_key);
CREATE INDEX idx_purch_supplier ON fact_purchases(supplier_id);
CREATE INDEX idx_purch_product ON fact_purchases(product_id);
