"""Clean the monthly extracts and load the star schema."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta

import pandas as pd

from pipeline.config import DATE_END, DATE_START, DB_PATH, POWERBI_DIR, RAW, SQL_DIR, WAREHOUSE


def normalize_name(value: str) -> str:
    text = str(value).upper().strip()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    text = re.sub(r"\bCOMPANY\b", "CO", text)
    text = re.sub(r"\bPVT\b", " ", text)
    text = re.sub(r"\bLTD\b", " ", text)
    text = re.sub(r"\bPRIVATE\b", " ", text)
    text = re.sub(r"\bLIMITED\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_MON = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_date(value: str) -> str | None:
    text = str(value).strip()
    named = re.match(r"^(\d{1,2})-([A-Za-z]{3})-(\d{4})$", text)
    if named:
        month = _MON.get(named.group(2).lower())
        if month:
            try:
                return date(int(named.group(3)), month, int(named.group(1))).isoformat()
            except ValueError:
                return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_money(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if text == "":
        return None
    text = text.replace("₹", "").replace("Rs.", "").replace("RS.", "").replace(",", "").strip()
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def parse_number(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _read_folder(folder: str) -> pd.DataFrame:
    paths = sorted((RAW / folder).glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"No extracts in {folder}.")
    frames = [pd.read_csv(path, dtype=str) for path in paths]
    return pd.concat(frames, ignore_index=True)


def _load_masters() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    suppliers = pd.read_csv(RAW / "masters" / "suppliers.csv", dtype=str)
    products = pd.read_csv(RAW / "masters" / "products.csv")
    customers = pd.read_csv(RAW / "masters" / "customers.csv", dtype=str)
    for column in ("payment_terms_days", "contracted_lead_days"):
        suppliers[column] = suppliers[column].astype(int)
    for column in ("standard_cost", "list_price"):
        products[column] = products[column].astype(float)
    return suppliers, products, customers


def _clean_sales(suppliers: pd.DataFrame, products: pd.DataFrame, customers: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    raw = _read_folder("sales")
    stats = {"sales_rows_read": int(len(raw))}
    frame = raw.copy()
    frame["invoice_date"] = frame["invoice_date"].map(parse_date)
    frame["list_price"] = frame["list_price"].map(parse_money)
    frame["unit_price"] = frame["unit_price"].map(parse_money)
    frame["unit_cost"] = frame["unit_cost"].map(parse_money)
    frame["freight_per_unit"] = frame["freight_per_unit"].map(parse_money)
    frame["quantity"] = frame["quantity"].map(parse_number)
    frame["return_qty"] = frame["return_qty"].map(parse_number)
    frame["discount_pct"] = frame["discount_pct"].map(parse_number)
    frame["supplier_key"] = frame["supplier_name"].map(normalize_name)

    before = len(frame)
    frame = frame.drop_duplicates(["invoice_id", "line_no"], keep="first")
    stats["sales_duplicates_removed"] = int(before - len(frame))

    invalid = frame["invoice_date"].isna() | frame["quantity"].isna() | (frame["quantity"] <= 0)
    stats["sales_rows_dropped"] = int(invalid.sum())
    frame = frame.loc[~invalid].copy()

    supplier_map = dict(zip(suppliers["supplier_name"].map(normalize_name), suppliers["supplier_id"]))
    product_map = dict(zip(products["sku"], products["product_id"]))
    frame["supplier_id"] = frame["supplier_key"].map(supplier_map)
    frame["product_id"] = frame["sku"].map(product_map)
    frame["customer_id"] = frame["customer_id"].where(frame["customer_id"].isin(customers["customer_id"]))
    unmatched = frame["supplier_id"].isna() | frame["product_id"].isna() | frame["customer_id"].isna()
    stats["sales_unmatched"] = int(unmatched.sum())
    frame = frame.loc[~unmatched].copy()

    frame["return_qty"] = frame["return_qty"].fillna(0).clip(lower=0)
    frame["return_qty"] = frame[["return_qty", "quantity"]].min(axis=1)
    frame["net_qty"] = frame["quantity"] - frame["return_qty"]
    frame["discount_rate"] = (frame["discount_pct"].fillna(0) / 100).clip(lower=0, upper=0.5)
    frame["date_key"] = frame["invoice_date"].str.replace("-", "", regex=False).astype(int)
    frame["list_revenue"] = frame["net_qty"] * frame["list_price"]
    frame["recognized_revenue"] = frame["net_qty"] * frame["unit_price"]
    frame["discount_amount"] = frame["list_revenue"] - frame["recognized_revenue"]
    frame["cogs"] = frame["net_qty"] * frame["unit_cost"]
    frame["freight_cost"] = frame["net_qty"] * frame["freight_per_unit"]
    frame["gross_profit"] = frame["recognized_revenue"] - frame["cogs"]
    frame["contribution_profit"] = frame["gross_profit"] - frame["freight_cost"]
    frame["sale_id"] = frame["invoice_id"] + "-" + frame["line_no"].astype(str)

    columns = [
        "sale_id",
        "invoice_id",
        "date_key",
        "product_id",
        "customer_id",
        "supplier_id",
        "quantity",
        "return_qty",
        "net_qty",
        "list_price",
        "discount_rate",
        "unit_price",
        "unit_cost",
        "freight_per_unit",
        "list_revenue",
        "discount_amount",
        "recognized_revenue",
        "cogs",
        "freight_cost",
        "gross_profit",
        "contribution_profit",
    ]
    stats["sales_lines_loaded"] = int(len(frame))
    return frame[columns], stats


def _clean_purchases(suppliers: pd.DataFrame, products: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    raw = _read_folder("purchases")
    stats = {"purchase_rows_read": int(len(raw))}
    frame = raw.copy()
    frame["po_date"] = frame["po_date"].map(parse_date)
    frame["unit_cost"] = frame["unit_cost"].map(parse_money)
    for column in ("qty_ordered", "qty_received", "qty_defective", "contracted_lead_days", "actual_lead_days", "on_time_flag"):
        frame[column] = frame[column].map(parse_number)
    frame["supplier_key"] = frame["supplier_name"].map(normalize_name)

    before = len(frame)
    frame = frame.drop_duplicates(["po_id"], keep="first")
    stats["purchase_duplicates_removed"] = int(before - len(frame))

    invalid = (
        frame["po_date"].isna()
        | frame["unit_cost"].isna()
        | frame["qty_ordered"].isna()
        | (frame["qty_ordered"] <= 0)
    )
    stats["purchase_rows_dropped"] = int(invalid.sum())
    frame = frame.loc[~invalid].copy()

    supplier_map = dict(zip(suppliers["supplier_name"].map(normalize_name), suppliers["supplier_id"]))
    product_map = dict(zip(products["sku"], products["product_id"]))
    frame["supplier_id"] = frame["supplier_key"].map(supplier_map)
    frame["product_id"] = frame["sku"].map(product_map)
    unmatched = frame["supplier_id"].isna() | frame["product_id"].isna()
    stats["purchase_unmatched"] = int(unmatched.sum())
    frame = frame.loc[~unmatched].copy()

    frame["qty_received"] = frame["qty_received"].fillna(0).clip(lower=0)
    frame["qty_defective"] = frame["qty_defective"].fillna(0).clip(lower=0)
    frame["qty_defective"] = frame[["qty_defective", "qty_received"]].min(axis=1)
    frame["date_key"] = frame["po_date"].str.replace("-", "", regex=False).astype(int)
    frame["purchase_value"] = frame["qty_received"] * frame["unit_cost"]
    frame["on_time_flag"] = frame["on_time_flag"].fillna(0).astype(int).clip(0, 1)
    frame["purchase_id"] = frame["po_id"]
    columns = [
        "purchase_id",
        "po_id",
        "date_key",
        "supplier_id",
        "product_id",
        "qty_ordered",
        "qty_received",
        "qty_defective",
        "unit_cost",
        "purchase_value",
        "contracted_lead_days",
        "actual_lead_days",
        "on_time_flag",
    ]
    for column in ("contracted_lead_days", "actual_lead_days"):
        frame[column] = frame[column].round().astype(int)
    stats["purchase_lines_loaded"] = int(len(frame))
    return frame[columns], stats


def build_calendar() -> pd.DataFrame:
    start = date.fromisoformat(DATE_START)
    end = date.fromisoformat(DATE_END)
    rows = []
    current = start
    while current <= end:
        fiscal_month = current.month - 3 if current.month >= 4 else current.month + 9
        fy_year = current.year + 1 if current.month >= 4 else current.year
        rows.append(
            {
                "date_key": int(current.strftime("%Y%m%d")),
                "date": current.isoformat(),
                "calendar_year": current.year,
                "quarter": (current.month - 1) // 3 + 1,
                "month": current.month,
                "month_name": current.strftime("%B"),
                "month_start": date(current.year, current.month, 1).isoformat(),
                "fy_year": fy_year,
                "fy_label": f"FY{str(fy_year)[2:]}",
                "fiscal_quarter": (fiscal_month - 1) // 3 + 1,
                "fiscal_month": fiscal_month,
            }
        )
        current += timedelta(days=1)
    return pd.DataFrame(rows)


def load_warehouse() -> dict[str, int]:
    suppliers, products, customers = _load_masters()
    sales, sales_stats = _clean_sales(suppliers, products, customers)
    purchases, purchase_stats = _clean_purchases(suppliers, products)
    calendar = build_calendar()
    stats = {**sales_stats, **purchase_stats}
    if stats["sales_unmatched"] or stats["purchase_unmatched"]:
        raise RuntimeError(f"Unmatched master keys: {stats}")

    WAREHOUSE.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    schema = (SQL_DIR / "schema.sql").read_text()
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(schema)
        calendar.to_sql("dim_date", conn, if_exists="append", index=False)
        suppliers.to_sql("dim_supplier", conn, if_exists="append", index=False)
        products.to_sql("dim_product", conn, if_exists="append", index=False)
        customers.to_sql("dim_customer", conn, if_exists="append", index=False)
        sales.to_sql("fact_sales", conn, if_exists="append", index=False)
        purchases.to_sql("fact_purchases", conn, if_exists="append", index=False)
        conn.execute("ANALYZE")

    POWERBI_DIR.mkdir(parents=True, exist_ok=True)
    calendar.to_csv(POWERBI_DIR / "dim_date.csv", index=False)
    suppliers.to_csv(POWERBI_DIR / "dim_supplier.csv", index=False)
    products.to_csv(POWERBI_DIR / "dim_product.csv", index=False)
    customers.to_csv(POWERBI_DIR / "dim_customer.csv", index=False)
    sales.to_csv(POWERBI_DIR / "fact_sales.csv", index=False)
    purchases.to_csv(POWERBI_DIR / "fact_purchases.csv", index=False)
    stats["suppliers"] = int(len(suppliers))
    stats["products"] = int(len(products))
    stats["customers"] = int(len(customers))
    return stats


if __name__ == "__main__":
    print(load_warehouse())
