"""Turn query results into the KPI catalog and the written findings."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.config import KPI_DEFINITIONS


def inr(value: float) -> str:
    sign = "-" if value < 0 else ""
    amount = abs(value)
    if amount >= 1e7:
        return f"{sign}₹{amount / 1e7:.2f} Cr"
    if amount >= 1e5:
        return f"{sign}₹{amount / 1e5:.2f} L"
    return f"{sign}₹{amount:,.0f}"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def bps(value: float) -> str:
    return f"{int(round(value * 10000)):+,} bps"


def build_catalog(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    headline = results["headline"].iloc[0]
    cost_index = float(results["cost_index"].iloc[0]["supplier_cost_index"])
    scored = results["supplier_scorecard"]
    scored = scored.loc[scored["fy_label"] == "ALL", "supplier_score"]
    median_score = float(scored.median())

    values = {
        "Recognized revenue": (float(headline["recognized_revenue"]), "INR", "headline"),
        "COGS": (float(headline["cogs"]), "INR", "headline"),
        "Gross profit": (float(headline["gross_profit"]), "INR", "headline"),
        "Gross margin": (float(headline["gross_margin"]), "ratio", "headline"),
        "Contribution profit": (float(headline["contribution_profit"]), "INR", "headline"),
        "Contribution margin": (float(headline["contribution_margin"]), "ratio", "headline"),
        "Average selling price": (float(headline["average_selling_price"]), "INR per unit", "headline"),
        "Purchase cost per unit": (float(headline["purchase_cost_per_unit"]), "INR per unit", "headline"),
        "Unit margin": (float(headline["unit_margin"]), "INR per unit", "headline"),
        "Discount rate": (float(headline["discount_rate"]), "ratio", "headline"),
        "Price realization": (float(headline["price_realization"]), "ratio", "headline"),
        "Freight per unit": (float(headline["freight_per_unit"]), "INR per unit", "headline"),
        "Return rate": (float(headline["return_rate"]), "ratio", "headline"),
        "On-time delivery": (float(headline["on_time_delivery"]), "ratio", "headline"),
        "Fill rate": (float(headline["fill_rate"]), "ratio", "headline"),
        "Defect rate": (float(headline["defect_rate"]), "ratio", "headline"),
        "Average lead time": (float(headline["average_lead_time"]), "days", "headline"),
        "Top-10 spend share": (float(headline["top10_spend_share"]), "ratio", "headline"),
        "Supplier HHI": (float(headline["supplier_hhi"]), "index", "headline"),
        "Single-source SKU share": (float(headline["single_source_sku_pct"]), "ratio", "headline"),
        "Weighted days payable": (float(headline["weighted_days_payable"]), "days", "headline"),
        "Purchase price variance": (float(headline["purchase_price_variance"]), "ratio", "headline"),
        "Revenue growth": (float(headline["revenue_growth_fy25"]), "ratio", "headline"),
        "Gross margin change": (float(headline["gross_margin_change_fy25"]), "margin points", "headline"),
        "Supplier cost index": (cost_index, "Q1 FY24 = 1", "cost_index"),
        "Private-label margin gap": (float(headline["private_label_margin_gap"]), "margin points", "headline"),
        "Supplier score": (median_score, "median, 0–100", "supplier_scorecard"),
    }
    definitions = {item["name"]: item["formula"] for item in KPI_DEFINITIONS}
    rows = []
    for name, (value, unit, source) in values.items():
        rows.append(
            {
                "kpi": name,
                "value": value,
                "unit": unit,
                "sql_source": source,
                "definition": definitions[name],
            }
        )
    return pd.DataFrame(rows)


def build_insights(results: dict[str, pd.DataFrame]) -> list[dict[str, str]]:
    category = results["category_fy"]
    oils = category.loc[category["category"] == "Edible Oils"].set_index("fy_label")
    bridge = results["oil_bridge"].iloc[0]
    gm24 = float(oils.loc["FY24", "gross_margin"])
    gm25 = float(oils.loc["FY25", "gross_margin"])

    suppliers = results["supplier_scorecard"]
    suppliers = suppliers.loc[suppliers["fy_label"] == "ALL"].copy()
    total_spend = float(suppliers["spend"].sum())
    top = suppliers.sort_values("spend", ascending=False).iloc[0]
    top10 = float(suppliers.nlargest(10, "spend")["spend"].sum() / total_spend)
    hhi = float(((suppliers["spend"] / total_spend) ** 2).sum())
    luit = suppliers.loc[suppliers["supplier_name"] == "Luit Packaging Works"].iloc[0]
    headline = results["headline"].iloc[0]

    snacks = results["brand_margin"]
    snacks = snacks.loc[snacks["category"] == "Snacks"]
    snack_totals = snacks.groupby("brand_type")[["revenue", "gross_profit"]].sum()
    private_margin = float(snack_totals.loc["Private Label", "gross_profit"] / snack_totals.loc["Private Label", "revenue"])
    branded_margin = float(snack_totals.loc["Branded", "gross_profit"] / snack_totals.loc["Branded", "revenue"])

    def weighted_index(frame: pd.DataFrame) -> float:
        return float(np.average(frame["cost_index"], weights=frame["spend"]))

    fy25 = results["supplier_scorecard"]
    fy25 = fy25.loc[fy25["fy_label"] == "FY25"]
    incumbents = fy25.loc[fy25["cohort"] == "Incumbent"]
    newcomers = fy25.loc[fy25["cohort"] == "New"]
    cohort = results["cohort"].set_index("cohort")
    regions = results["region_margin"].set_index("region_group")

    return [
        {
            "title": "Edible-oil prices did not keep up with cost",
            "body": (
                f"Gross margin on edible oils fell from {pct(gm24)} in FY24 to {pct(gm25)} in FY25 "
                f"({bps(gm25 - gm24)}). Unit cost rose {pct(float(bridge['cost_change']))} while the "
                f"average selling price rose {pct(float(bridge['price_change']))}. Holding the FY24 cost "
                f"against the FY25 price, the bridge assigns {bps(float(bridge['price_effect']))} to price "
                f"and {bps(float(bridge['cost_effect']))} to cost."
            ),
        },
        {
            "title": "A short list of suppliers carries the book",
            "body": (
                f"{top['supplier_name']} is {pct(float(top['spend']) / total_spend)} of purchase value "
                f"({inr(float(top['spend']))}). The ten largest suppliers are {pct(top10)} of spend. "
                f"The Herfindahl-Hirschman index is {hhi:.3f}."
            ),
        },
        {
            "title": "Luit Packaging Works is large and late",
            "body": (
                f"On-time delivery at Luit Packaging Works is {pct(float(luit['otd']))} on "
                f"{inr(float(luit['spend']))} of purchases, against {pct(float(headline['on_time_delivery']))} "
                f"for the book. Fill rate is {pct(float(luit['fill_rate']))} and the defect rate is "
                f"{pct(float(luit['defect_rate']))}."
            ),
        },
        {
            "title": "Private-label snacks earn a wider margin",
            "body": (
                f"Private-label snacks run at {pct(private_margin)} gross margin, against "
                f"{pct(branded_margin)} for branded snacks ({bps(private_margin - branded_margin)}). "
                f"The gap comes from a lower standard cost on the private-label SKUs."
            ),
        },
        {
            "title": "Suppliers added since 2024 are cheaper and less clean",
            "body": (
                f"In FY25, when both groups were buying, new suppliers had a spend-weighted cost index of "
                f"{weighted_index(newcomers):.2f}, against {weighted_index(incumbents):.2f} for incumbents, "
                f"where 1.00 is the category median. Across the full extract their defect rate is "
                f"{pct(float(cohort.loc['New', 'defect_rate']))} versus "
                f"{pct(float(cohort.loc['Incumbent', 'defect_rate']))}, and on-time delivery is "
                f"{pct(float(cohort.loc['New', 'otd']))} versus {pct(float(cohort.loc['Incumbent', 'otd']))}."
            ),
        },
        {
            "title": "Hill-state freight narrows contribution margin",
            "body": (
                f"Contribution margin is {pct(float(regions.loc['Hill Northeast', 'contribution_margin']))} "
                f"in the hill states and {pct(float(regions.loc['Assam Valley', 'contribution_margin']))} "
                f"in the Assam valley. Freight per unit is "
                f"₹{float(regions.loc['Hill Northeast', 'freight_per_unit']):.2f} against "
                f"₹{float(regions.loc['Assam Valley', 'freight_per_unit']):.2f}."
            ),
        },
    ]
