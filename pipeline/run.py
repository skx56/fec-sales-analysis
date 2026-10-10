"""Run the warehouse build, the KPI library, and the dashboard."""

from __future__ import annotations

import json
import sqlite3
import time

import pandas as pd

from pipeline.config import (
    AUTOMATED_REVIEW_MINUTES,
    CATEGORIES,
    DB_PATH,
    KPI_DEFINITIONS,
    MANUAL_CLOSE_MINUTES,
    OUTPUT,
)
from pipeline.dashboard import write_dashboard
from pipeline.generate import generate
from pipeline.narrative import build_catalog, build_insights, inr, pct
from pipeline.powerbi import MEASURES, write_powerbi
from pipeline.queries import run_kpis
from pipeline.transform import load_warehouse


def _records(frame: pd.DataFrame):
    return json.loads(frame.to_json(orient="records", double_precision=6))


def _check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate(stats: dict, results: dict[str, pd.DataFrame], catalog: pd.DataFrame) -> None:
    errors: list[str] = []
    headline = results["headline"].iloc[0]
    category = results["category_fy"]
    oils = category.loc[category["category"] == "Edible Oils"].set_index("fy_label")
    paired = category.loc[category["fy_label"].isin(["FY24", "FY25"])]
    wide = paired.pivot(index="category", columns="fy_label", values="gross_margin")
    worst = (wide["FY25"] - wide["FY24"]).sort_values().index[0]
    suppliers = results["supplier_scorecard"]
    suppliers = suppliers.loc[suppliers["fy_label"] == "ALL"]
    luit = suppliers.loc[suppliers["supplier_name"] == "Luit Packaging Works"].iloc[0]
    cohort = results["cohort"].set_index("cohort")
    regions = results["region_margin"].set_index("region_group")
    snacks = results["brand_margin"]
    snacks = snacks.loc[snacks["category"] == "Snacks"].groupby("brand_type")[["revenue", "gross_profit"]].sum()
    private_margin = snacks.loc["Private Label", "gross_profit"] / snacks.loc["Private Label", "revenue"]
    branded_margin = snacks.loc["Branded", "gross_profit"] / snacks.loc["Branded", "revenue"]
    monthly_revenue = float(results["monthly_sales"]["recognized_revenue"].sum())
    ops = results["monthly_ops"]
    ops_otd = float(ops["on_time_lines"].sum() / ops["po_lines"].sum())
    fy25_suppliers = results["supplier_scorecard"]
    fy25_suppliers = fy25_suppliers.loc[fy25_suppliers["fy_label"] == "FY25"]
    newcomers = fy25_suppliers.loc[fy25_suppliers["cohort"] == "New"]
    incumbents = fy25_suppliers.loc[fy25_suppliers["cohort"] == "Incumbent"]
    new_index = float((newcomers["cost_index"] * newcomers["spend"]).sum() / newcomers["spend"].sum())
    old_index = float((incumbents["cost_index"] * incumbents["spend"]).sum() / incumbents["spend"].sum())

    _check(stats["suppliers"] >= 100, "Need at least 100 suppliers.", errors)
    _check(stats["products"] >= 100, "Need at least 100 SKUs.", errors)
    _check(stats["sales_lines_loaded"] >= 8000, "Sales fact is thinner than expected.", errors)
    _check(stats["sales_unmatched"] == 0 and stats["purchase_unmatched"] == 0, "Master matching left rows unmatched.", errors)
    _check(stats["sales_duplicates_removed"] > 0, "Duplicate cleanup did not fire.", errors)
    _check(5e8 < headline["recognized_revenue"] < 8e9, "Revenue is outside the planned band.", errors)
    _check(0.08 < headline["gross_margin"] < 0.40, "Book gross margin is outside 8–40%.", errors)
    _check(float(oils.loc["FY25", "gross_margin"]) < float(oils.loc["FY24", "gross_margin"]) - 0.03, "Edible-oil margin did not compress by at least 300 bps.", errors)
    _check(worst == "Edible Oils", f"Largest margin drop was {worst}, not edible oils.", errors)
    _check(float(luit["otd"]) < 0.75, "Luit Packaging Works is not late enough to be the service exception.", errors)
    _check(float(luit["spend"]) > 0.005 * float(suppliers["spend"].sum()), "Luit is too small to matter.", errors)
    _check(float(cohort.loc["New", "defect_rate"]) > float(cohort.loc["Incumbent", "defect_rate"]) * 1.5, "New suppliers are not dirtier than incumbents.", errors)
    _check(new_index < old_index - 0.04, f"New suppliers are not cheaper in FY25 ({new_index:.3f} vs {old_index:.3f}).", errors)
    _check(private_margin > branded_margin + 0.025, "Private-label snacks do not out-margin branded snacks.", errors)
    _check(
        float(regions.loc["Hill Northeast", "contribution_margin"])
        < float(regions.loc["Assam Valley", "contribution_margin"]) - 0.008,
        "Hill-state contribution margin is not below the Assam valley.",
        errors,
    )
    _check(0.22 < headline["top10_spend_share"] < 0.62, f"Top-10 spend share is {headline['top10_spend_share']:.1%}.", errors)
    _check(0.05 < headline["single_source_sku_pct"] < 0.45, "Single-source share is outside 5–45%.", errors)
    _check(0.75 < headline["on_time_delivery"] < 0.98, "Book on-time delivery is outside 75–98%.", errors)
    _check(abs(monthly_revenue - float(headline["recognized_revenue"])) / float(headline["recognized_revenue"]) < 0.001, "Monthly sales do not tie to headline revenue.", errors)
    _check(abs(ops_otd - float(headline["on_time_delivery"])) < 0.002, "Monthly operations do not tie to headline on-time delivery.", errors)
    _check(len(catalog) >= 24, "KPI catalog has fewer than 24 measures.", errors)
    _check(len(MEASURES) >= 24, "Power BI measure list has fewer than 24 measures.", errors)
    _check(len(KPI_DEFINITIONS) == len(catalog), "A KPI is missing a definition.", errors)

    if errors:
        print("\nValidation failed:")
        for item in errors:
            print(f"  - {item}")
        print("\nCategory gross margin, FY25 minus FY24:")
        print((wide["FY25"] - wide["FY24"]).sort_values().to_string())
        raise SystemExit(1)


def _footer(stats: dict, runtime: float) -> str:
    reduction = 1 - AUTOMATED_REVIEW_MINUTES / MANUAL_CLOSE_MINUTES
    return (
        f"Source: FEC sales warehouse. Synthetic ERP extract of a Northeast India distributor, "
        f"April 2023–September 2025. Pipeline ran in {runtime:.1f}s, read "
        f"{stats['sales_rows_read']:,} sales rows and removed {stats['sales_duplicates_removed']:,} duplicates. "
        f"A manual close of these extracts is about {MANUAL_CLOSE_MINUTES // 60} hours; "
        f"reviewing this pack is about {AUTOMATED_REVIEW_MINUTES} minutes, {reduction:.0%} less analyst time."
    )


def main() -> None:
    started = time.perf_counter()
    print("Generating monthly extracts...")
    generated = generate()
    print(
        f"  {generated['suppliers']} suppliers, {generated['products']} SKUs, "
        f"{generated['sales_lines']:,} sales lines, {generated['purchase_lines']:,} purchase lines"
    )
    print("Cleaning extracts and loading the warehouse...")
    stats = load_warehouse()
    print(
        f"  loaded {stats['sales_lines_loaded']:,} sales and {stats['purchase_lines_loaded']:,} purchases; "
        f"removed {stats['sales_duplicates_removed']:,} duplicate sales rows"
    )
    print("Running the KPI library...")
    with sqlite3.connect(DB_PATH) as conn:
        version = conn.execute("SELECT sqlite_version()").fetchone()[0]
    print(f"  SQLite {version}")
    results = run_kpis(DB_PATH)
    catalog = build_catalog(results)
    insights = build_insights(results)
    validate(stats, results, catalog)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    sql_dir = OUTPUT / "sql"
    sql_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in results.items():
        frame.to_csv(sql_dir / f"{name}.csv", index=False)
    catalog.to_csv(OUTPUT / "kpi_catalog.csv", index=False)
    results["supplier_scorecard"].to_csv(OUTPUT / "supplier_scorecard.csv", index=False)

    runtime = time.perf_counter() - started
    payload = {
        "meta": {
            "suppliers": stats["suppliers"],
            "products": stats["products"],
            "customers": stats["customers"],
            "footer": _footer(stats, runtime),
        },
        "categories": list(CATEGORIES.keys()),
        "monthly": _records(results["monthly_sales"]),
        "ops": _records(results["monthly_ops"]),
        "suppliers": _records(results["supplier_scorecard"]),
        "bridge": _records(results["oil_bridge"])[0],
        "insights": insights,
        "singleSource": _records(results["single_source"]),
        "definitions": KPI_DEFINITIONS,
    }
    write_dashboard(payload)
    write_powerbi()

    log = {
        "runtime_seconds": round(runtime, 2),
        "sqlite": version,
        "manual_close_minutes": MANUAL_CLOSE_MINUTES,
        "automated_review_minutes": AUTOMATED_REVIEW_MINUTES,
        "analyst_time_reduction": 1 - AUTOMATED_REVIEW_MINUTES / MANUAL_CLOSE_MINUTES,
        "extracts": generated,
        "warehouse": stats,
        "kpis": {row.kpi: row.value for row in catalog.itertuples()},
    }
    (OUTPUT / "run_log.json").write_text(json.dumps(log, indent=2))

    headline = results["headline"].iloc[0]
    oils = results["category_fy"]
    oils = oils.loc[oils["category"] == "Edible Oils"].set_index("fy_label")
    print()
    print("FEC supplier sales warehouse")
    print(f"  Recognized revenue     {inr(float(headline['recognized_revenue']))}")
    print(f"  Gross margin           {pct(float(headline['gross_margin']))}")
    print(f"  FY25 vs FY24 revenue   {pct(float(headline['revenue_growth_fy25']))}")
    print(f"  FY25 vs FY24 margin    {float(headline['gross_margin_change_fy25']) * 10000:+.0f} bps")
    print(
        f"  Edible oils margin     {pct(float(oils.loc['FY24', 'gross_margin']))} → "
        f"{pct(float(oils.loc['FY25', 'gross_margin']))}"
    )
    print(f"  On-time delivery       {pct(float(headline['on_time_delivery']))}")
    print(f"  Top-10 spend share     {pct(float(headline['top10_spend_share']))}")
    print(f"  KPIs                   {len(catalog)} in SQL, {len(MEASURES)} DAX measures")
    print(f"  Runtime                {runtime:.1f}s")
    print("  Dashboard              dashboard/index.html")
    print("  Power BI               powerbi/FEC_Sales.pbip")


if __name__ == "__main__":
    main()
