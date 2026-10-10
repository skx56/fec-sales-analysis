"""Build messy monthly ERP extracts for a Northeast India wholesale book.

The generator writes master data and month-level sales and purchase files.
Cleaning, the star schema, and the KPIs are downstream of those files.
"""

from __future__ import annotations

import calendar
import shutil
from datetime import date, datetime

import numpy as np
import pandas as pd

from pipeline.config import (
    CATEGORIES,
    CHANNEL_DISCOUNT,
    CUSTOMER_MARKETS,
    DATE_END,
    DATE_START,
    FESTIVE_CATEGORIES,
    FREIGHT_PER_UNIT,
    INSTITUTIONAL,
    NEW_ONBOARD,
    PACKS,
    PRIVATE_LABEL_CATEGORIES,
    RAW,
    SEED,
    STEMS,
    SUPPLIERS,
)


def _month_starts(start: date, end: date) -> list[date]:
    cursor = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    months = []
    while cursor <= last:
        months.append(cursor)
        year = cursor.year + (1 if cursor.month == 12 else 0)
        month = 1 if cursor.month == 12 else cursor.month + 1
        cursor = date(year, month, 1)
    return months


def _month_end(month_start: date) -> date:
    return date(
        month_start.year,
        month_start.month,
        calendar.monthrange(month_start.year, month_start.month)[1],
    )


def _months_since_start(month_start: date) -> int:
    return (month_start.year - 2023) * 12 + month_start.month - 4


def category_cost_index(category: str, month_start: date) -> float:
    """Edible oils spike through FY25. Packaging inflates faster than the rest."""
    if category == "Edible Oils":
        if month_start < date(2024, 4, 1):
            return 1.0
        if month_start >= date(2024, 10, 1):
            return 1.18
        step = (month_start.year - 2024) * 12 + month_start.month - 4
        return 1.0 + 0.18 * (step + 1) / 6
    elapsed = _months_since_start(month_start) / 12
    rate = 1.06 if category == "Packaging" else 1.03
    return rate**elapsed


def category_price_index(category: str, month_start: date) -> float:
    """Selling prices lag the oil spike. Beverages reprice in January 2025."""
    if category == "Edible Oils":
        if month_start < date(2024, 4, 1):
            return 1.0
        if month_start >= date(2024, 10, 1):
            return 1.08
        step = (month_start.year - 2024) * 12 + month_start.month - 4
        return 1.0 + 0.08 * (step + 1) / 6
    elapsed = _months_since_start(month_start) / 12
    index = (1.02) ** elapsed
    if category == "Beverages" and month_start >= date(2025, 1, 1):
        index *= 1.07
    return index


def seasonality(kind: str, month: int) -> float:
    if kind == "festive":
        return {9: 1.12, 10: 1.48, 11: 1.32, 12: 1.08}.get(month, 0.92)
    if kind == "summer":
        return {4: 1.22, 5: 1.34, 6: 1.28, 7: 1.08}.get(month, 0.90)
    if kind == "mild":
        return {10: 1.16, 11: 1.08}.get(month, 1.0)
    return 1.0


def _lead_days(state: str) -> int:
    if state == "Gujarat":
        return 18
    if state in {"Meghalaya", "Manipur", "Nagaland", "Tripura", "Mizoram", "Arunachal Pradesh"}:
        return 14
    if state == "West Bengal":
        return 12
    return 8


def _service_profile(name: str, cohort: str) -> tuple[float, float, float]:
    """Return on-time probability, fill rate, and defect rate."""
    if name == "Luit Packaging Works":
        return 0.62, 0.90, 0.018
    if name == "Azara Private Label Kitchen":
        return 0.92, 0.975, 0.007
    if cohort == "New":
        return 0.84, 0.94, 0.022
    return 0.945, 0.986, 0.0045


def build_suppliers() -> pd.DataFrame:
    rows = []
    serial = 1
    for category, members in SUPPLIERS.items():
        for index, (name, city, state) in enumerate(members):
            if index == 0:
                tier = "Strategic"
            elif index < max(2, len(members) // 2):
                tier = "Preferred"
            else:
                tier = "Transactional"
            if tier == "Strategic" and category in {"Tea", "Edible Oils", "Staples"}:
                terms = 60
            elif tier == "Strategic":
                terms = 45
            elif tier == "Preferred":
                terms = 30
            else:
                terms = 15
            onboard = NEW_ONBOARD.get(name, "2022-04-01")
            cohort = "New" if name in NEW_ONBOARD else "Incumbent"
            if cohort == "New" and name != "Azara Private Label Kitchen":
                cost_index = 0.88
            elif name == "Azara Private Label Kitchen":
                cost_index = 0.96
            elif name == "Kamrup Agro Foods":
                cost_index = 1.0
            elif name == "Luit Packaging Works":
                cost_index = 1.02
            else:
                cost_index = round(0.98 + (index % 5) * 0.01, 2)
            rows.append(
                {
                    "supplier_id": f"S{serial:03d}",
                    "supplier_name": name,
                    "category_focus": category,
                    "city": city,
                    "state": state,
                    "payment_terms_days": terms,
                    "contracted_lead_days": _lead_days(state),
                    "tier": tier,
                    "onboard_date": onboard,
                    "cohort": cohort,
                    "cost_index": cost_index,
                }
            )
            serial += 1
    frame = pd.DataFrame(rows)
    if frame["supplier_name"].duplicated().any():
        raise RuntimeError("Supplier names must be unique.")
    if len(frame) < 100:
        raise RuntimeError("Expected at least 100 suppliers.")
    return frame


def build_products(suppliers: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    rows = []
    links: dict[str, list[str]] = {}
    serial = 1
    rng = np.random.default_rng(SEED + 7)
    by_category = {
        category: suppliers.loc[suppliers["category_focus"] == category, "supplier_id"].tolist()
        for category in suppliers["category_focus"].unique()
    }
    names = dict(zip(suppliers["supplier_id"], suppliers["supplier_name"]))

    for category, spec in CATEGORIES.items():
        stems = STEMS[category]
        packs = PACKS[category]
        combos = [(stem, pack) for stem in stems for pack in packs]
        if len(combos) < spec["n_sku"]:
            raise RuntimeError(f"Not enough name stems for {category}.")
        pool = by_category[category]
        supplier_rows = suppliers.set_index("supplier_id")
        for index in range(spec["n_sku"]):
            stem, pack = combos[index]
            wobble = 1 + ((index % 5) - 2) * 0.015
            cost = round(spec["cost"] * wobble, 2)
            price = round(spec["price"] * wobble, 2)
            brand = "Branded"
            if category in PRIVATE_LABEL_CATEGORIES and index % 3 == 0:
                brand = "Private Label"
                cost = round(cost * 0.90, 2)
                price = round(price * 0.97, 2)
            product_id = f"P{serial:03d}"
            sku = f"{spec['prefix']}-{index + 1:03d}"
            rows.append(
                {
                    "product_id": product_id,
                    "sku": sku,
                    "product_name": f"{stem} {pack}",
                    "category": category,
                    "subcategory": stem,
                    "brand_type": brand,
                    "uom": spec["uom"],
                    "standard_cost": cost,
                    "list_price": price,
                }
            )
            links[product_id] = _choose_suppliers(category, pool, names, supplier_rows, rng)
            serial += 1
    return pd.DataFrame(rows), links


def _choose_suppliers(category, pool, names, supplier_rows, rng) -> list[str]:
    luit = [sid for sid in pool if names[sid] == "Luit Packaging Works"]
    if category == "Packaging" and luit:
        others = [sid for sid in pool if sid not in luit]
        if rng.random() < 0.8:
            return [luit[0], str(rng.choice(others))]
        return [str(rng.choice(others))]

    strategic = [
        sid
        for sid in pool
        if supplier_rows.loc[sid, "tier"] == "Strategic"
    ]
    if category == "Spices" and rng.random() < 0.45:
        return [str(rng.choice(pool))]
    if rng.random() < 0.12:
        return [str(rng.choice(strategic or pool))]

    primary = str(rng.choice(strategic or pool))
    rest = [sid for sid in pool if sid != primary]
    extra_n = 2 if len(rest) > 1 else 1
    extras = [str(sid) for sid in rng.choice(rest, size=min(extra_n, len(rest)), replace=False)]
    chosen = [primary, *extras]
    newcomers = [sid for sid in pool if supplier_rows.loc[sid, "cohort"] == "New" and sid not in chosen]
    if newcomers and rng.random() < 0.7:
        chosen[-1] = str(rng.choice(newcomers))
    return chosen


def build_customers() -> pd.DataFrame:
    rows = []
    serial = 1
    for state, region, cities in CUSTOMER_MARKETS:
        for city in cities:
            for label, channel in (
                (f"{city} Wholesale Mart", "General Trade"),
                (f"{city} Kirana Supply", "General Trade"),
            ):
                rows.append((f"C{serial:03d}", label, channel, city, state, region))
                serial += 1
        primary = cities[0]
        rows.append((f"C{serial:03d}", f"{primary} Modern Bazaar", "Modern Trade", primary, state, region))
        serial += 1
        rows.append((f"C{serial:03d}", f"{primary} Hospitality Group", "HoReCa", primary, state, region))
        serial += 1
    for name, city, state, region in INSTITUTIONAL:
        rows.append((f"C{serial:03d}", name, "Institutional", city, state, region))
        serial += 1
    frame = pd.DataFrame(
        rows,
        columns=["customer_id", "customer_name", "channel", "city", "state", "region_group"],
    )
    if frame["customer_name"].duplicated().any():
        raise RuntimeError("Customer names must be unique.")
    return frame


def _business_day(rng: np.random.Generator, month_start: date) -> date:
    last = calendar.monthrange(month_start.year, month_start.month)[1]
    for _ in range(8):
        day = int(rng.integers(1, last + 1))
        current = date(month_start.year, month_start.month, day)
        if current.weekday() != 6:
            return current
    return month_start


def _size_weight(name: str, tier: str) -> float:
    if name == "Kamrup Agro Foods":
        return 3.1
    if name == "Luit Packaging Works":
        return 2.6
    if tier == "Strategic":
        return 1.75
    if tier == "Preferred":
        return 1.30
    return 0.95


def simulate(
    suppliers: pd.DataFrame,
    products: pd.DataFrame,
    customers: pd.DataFrame,
    links: dict[str, list[str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    supplier_ix = suppliers.set_index("supplier_id")
    sales_rows: list[dict] = []
    purchase_rows: list[dict] = []
    sale_serial = 1
    months = _month_starts(date.fromisoformat(DATE_START), date.fromisoformat(DATE_END))
    customer_ids = customers["customer_id"].tolist()
    channels = dict(zip(customers["customer_id"], customers["channel"]))
    regions = dict(zip(customers["customer_id"], customers["region_group"]))

    for month_start in months:
        month_end = _month_end(month_start)
        growth = (1.04) ** (_months_since_start(month_start) / 12)
        for product in products.itertuples(index=False):
            spec = CATEGORIES[product.category]
            active = []
            for supplier_id in links[product.product_id]:
                onboard = date.fromisoformat(supplier_ix.loc[supplier_id, "onboard_date"])
                if onboard <= month_end:
                    active.append(supplier_id)
            if not active:
                continue
            monthly_qty = (spec["annual_rev"] / spec["n_sku"]) / product.list_price / 12
            factor = seasonality(spec["season"], month_start.month) * growth
            factor *= float(rng.uniform(0.90, 1.10))
            if product.category == "Beverages" and month_start >= date(2025, 1, 1):
                factor *= 0.96
            desired = monthly_qty * factor
            weights = []
            for supplier_id in active:
                info = supplier_ix.loc[supplier_id]
                weight = _size_weight(info["supplier_name"], info["tier"])
                if info["cohort"] == "New":
                    weight *= 1.65
                weights.append(weight)
            shares = np.array(weights, dtype=float)
            shares = shares / shares.sum()
            for supplier_id, share in zip(active, shares):
                info = supplier_ix.loc[supplier_id]
                wanted = desired * float(share)
                if wanted < 8:
                    continue
                ordered = int(round(wanted * float(rng.uniform(1.05, 1.12))))
                otd_p, fill_p, defect_p = _service_profile(info["supplier_name"], info["cohort"])
                fill = float(np.clip(rng.normal(fill_p, 0.012), 0.72, 1.0))
                received = int(round(ordered * fill))
                if received <= 0:
                    continue
                defective = int(round(received * defect_p * float(rng.uniform(0.85, 1.15))))
                defective = min(defective, received)
                if rng.random() < otd_p:
                    actual_lead = int(info["contracted_lead_days"])
                    if rng.random() < 0.3:
                        actual_lead = max(1, actual_lead - 1)
                    on_time = 1
                else:
                    actual_lead = int(info["contracted_lead_days"]) + int(rng.integers(4, 15))
                    on_time = 0
                unit_cost = round(
                    product.standard_cost
                    * float(info["cost_index"])
                    * category_cost_index(product.category, month_start)
                    * float(rng.uniform(0.995, 1.005)),
                    2,
                )
                po_day = _business_day(rng, month_start)
                po_id = f"PO-{month_start:%Y%m}-{supplier_id}-{product.sku}"
                purchase_rows.append(
                    {
                        "po_id": po_id,
                        "po_date": po_day.isoformat(),
                        "supplier_name": info["supplier_name"],
                        "sku": product.sku,
                        "qty_ordered": ordered,
                        "qty_received": received,
                        "qty_defective": defective,
                        "unit_cost": unit_cost,
                        "contracted_lead_days": int(info["contracted_lead_days"]),
                        "actual_lead_days": actual_lead,
                        "on_time_flag": on_time,
                    }
                )
                sell_qty = min(int(round(wanted)), received)
                if sell_qty < 5:
                    continue
                n_cust = 3 if sell_qty >= 40 else 2
                chosen = rng.choice(customer_ids, size=n_cust, replace=False)
                raw_shares = rng.dirichlet(np.ones(n_cust))
                remaining = sell_qty
                for offset, (customer_id, cust_share) in enumerate(zip(chosen, raw_shares)):
                    if offset == n_cust - 1:
                        qty = remaining
                    else:
                        qty = max(1, int(round(sell_qty * float(cust_share))))
                        qty = min(qty, remaining)
                    remaining -= qty
                    if qty <= 0:
                        continue
                    channel = channels[customer_id]
                    discount = CHANNEL_DISCOUNT[channel]
                    if month_start.month in {10, 11} and product.category in FESTIVE_CATEGORIES:
                        discount += 0.045
                    discount = round(min(0.22, discount + float(rng.uniform(-0.004, 0.004))), 4)
                    list_price = round(product.list_price * category_price_index(product.category, month_start), 2)
                    unit_price = round(list_price * (1 - discount), 2)
                    freight = round(FREIGHT_PER_UNIT[regions[customer_id]], 2)
                    profile_name = info["supplier_name"]
                    if profile_name == "Luit Packaging Works":
                        return_rate = 0.012
                    elif info["cohort"] == "New" and profile_name != "Azara Private Label Kitchen":
                        return_rate = 0.016
                    else:
                        return_rate = 0.004
                    expected_returns = qty * return_rate
                    return_qty = int(expected_returns) + (1 if rng.random() < expected_returns % 1 else 0)
                    return_qty = min(return_qty, max(0, qty // 5))
                    invoice_day = _business_day(rng, month_start)
                    invoice_id = f"INV-{month_start:%Y%m}-{sale_serial:06d}"
                    sales_rows.append(
                        {
                            "invoice_id": invoice_id,
                            "line_no": 1,
                            "invoice_date": invoice_day.isoformat(),
                            "sku": product.sku,
                            "product_name": product.product_name,
                            "customer_id": customer_id,
                            "supplier_name": profile_name,
                            "quantity": qty,
                            "list_price": list_price,
                            "discount_pct": round(discount * 100, 2),
                            "unit_price": unit_price,
                            "unit_cost": unit_cost,
                            "freight_per_unit": freight,
                            "return_qty": return_qty,
                        }
                    )
                    sale_serial += 1
    return pd.DataFrame(sales_rows), pd.DataFrame(purchase_rows)


def _mess_name(name: str, rng: np.random.Generator) -> str:
    roll = float(rng.random())
    if roll < 0.18:
        return f"  {name.upper()} "
    if roll < 0.32:
        return name.lower()
    if roll < 0.42:
        return name.replace(" Co", " Company") if name.endswith(" Co") else f"{name} Pvt Ltd"
    if roll < 0.50:
        return name.replace(" ", "  ")
    return name


_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _mess_date(iso_day: str, rng: np.random.Generator) -> str:
    current = datetime.strptime(iso_day, "%Y-%m-%d")
    roll = float(rng.random())
    if roll < 0.46:
        return current.strftime("%d/%m/%Y")
    if roll < 0.62:
        return f"{current.day:02d}-{_MON[current.month - 1]}-{current.year}"
    return iso_day


def _mess_money(value: float, rng: np.random.Generator) -> str:
    roll = float(rng.random())
    if roll < 0.28:
        return f"₹ {value:,.2f}"
    if roll < 0.40:
        return f"Rs. {value:.2f}"
    return f"{value:.2f}"


def _write_messy_months(sales: pd.DataFrame, purchases: pd.DataFrame) -> dict[str, int]:
    rng = np.random.default_rng(SEED + 99)
    sales_dir = RAW / "sales"
    purchase_dir = RAW / "purchases"
    sales_dir.mkdir(parents=True, exist_ok=True)
    purchase_dir.mkdir(parents=True, exist_ok=True)
    duplicate_rows = 0
    blank_qty_rows = 0

    sales = sales.copy()
    sales["month"] = sales["invoice_date"].str.slice(0, 7)
    purchases = purchases.copy()
    purchases["month"] = purchases["po_date"].str.slice(0, 7)

    for month, frame in sales.groupby("month"):
        out = frame.drop(columns=["month"]).copy()
        out["supplier_name"] = [_mess_name(value, rng) for value in out["supplier_name"]]
        out["invoice_date"] = [_mess_date(value, rng) for value in out["invoice_date"]]
        for column in ("list_price", "unit_price", "unit_cost", "freight_per_unit"):
            out[column] = [_mess_money(float(value), rng) for value in out[column]]
        n_dup = max(1, int(round(len(out) * 0.02)))
        duplicated = out.sample(n=n_dup, random_state=int(rng.integers(0, 10_000)))
        duplicate_rows += len(duplicated)
        out = pd.concat([out, duplicated], ignore_index=True)
        blank_at = int(rng.integers(0, len(out)))
        out["quantity"] = out["quantity"].astype(object)
        out.loc[blank_at, "quantity"] = ""
        blank_qty_rows += 1
        path = sales_dir / f"sales_{month.replace('-', '')}.csv"
        out.to_csv(path, index=False)

    for month, frame in purchases.groupby("month"):
        out = frame.drop(columns=["month"]).copy()
        out["supplier_name"] = [_mess_name(value, rng) for value in out["supplier_name"]]
        out["po_date"] = [_mess_date(value, rng) for value in out["po_date"]]
        out["unit_cost"] = [_mess_money(float(value), rng) for value in out["unit_cost"]]
        n_dup = max(1, int(round(len(out) * 0.015)))
        duplicated = out.sample(n=n_dup, random_state=int(rng.integers(0, 10_000)))
        duplicate_rows += len(duplicated)
        out = pd.concat([out, duplicated], ignore_index=True)
        path = purchase_dir / f"purchases_{month.replace('-', '')}.csv"
        out.to_csv(path, index=False)

    return {"duplicate_rows_planted": duplicate_rows, "blank_qty_rows_planted": blank_qty_rows}


def generate() -> dict[str, int]:
    if RAW.exists():
        shutil.rmtree(RAW)
    master_dir = RAW / "masters"
    master_dir.mkdir(parents=True, exist_ok=True)

    suppliers = build_suppliers()
    products, links = build_products(suppliers)
    customers = build_customers()
    public_suppliers = suppliers.drop(columns=["cost_index"])
    public_suppliers.to_csv(master_dir / "suppliers.csv", index=False)
    products.to_csv(master_dir / "products.csv", index=False)
    customers.to_csv(master_dir / "customers.csv", index=False)

    sales, purchases = simulate(suppliers, products, customers, links)
    planted = _write_messy_months(sales, purchases)
    return {
        "suppliers": int(len(suppliers)),
        "products": int(len(products)),
        "customers": int(len(customers)),
        "sales_lines": int(len(sales)),
        "purchase_lines": int(len(purchases)),
        **planted,
    }


if __name__ == "__main__":
    print(generate())
