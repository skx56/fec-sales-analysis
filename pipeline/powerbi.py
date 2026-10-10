"""Build a Power BI project (PBIP) over the exported star schema."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from pipeline.config import PBIP_DIR, POWERBI_DIR

# Stable ids so regenerating the model does not churn the project files.
SEMANTIC_ID = "8f3a1c2e-6b47-4d1a-9c55-2e7b0a91d4f3"
REPORT_ID = "1c9e5a77-0d28-4b6e-a3f1-6b8d2c4e9a10"

SUM_COLUMNS = {
    "recognized_revenue",
    "cogs",
    "freight_cost",
    "gross_profit",
    "contribution_profit",
    "list_revenue",
    "discount_amount",
    "quantity",
    "return_qty",
    "net_qty",
    "qty_ordered",
    "qty_received",
    "qty_defective",
    "purchase_value",
}
INT_COLUMNS = {
    "date_key",
    "calendar_year",
    "quarter",
    "month",
    "fy_year",
    "fiscal_quarter",
    "fiscal_month",
    "payment_terms_days",
    "contracted_lead_days",
    "actual_lead_days",
    "on_time_flag",
}
DATE_COLUMNS = {"date", "month_start", "onboard_date"}

MEASURES = [
    ("Recognized Revenue", "Revenue", "₹ #,0", "SUM ( fact_sales[recognized_revenue] )"),
    ("COGS", "Margin", "₹ #,0", "SUM ( fact_sales[cogs] )"),
    ("Gross Profit", "Margin", "₹ #,0", "[Recognized Revenue] - [COGS]"),
    ("Gross Margin %", "Margin", "0.0%", "DIVIDE ( [Gross Profit], [Recognized Revenue] )"),
    ("Freight Cost", "Margin", "₹ #,0", "SUM ( fact_sales[freight_cost] )"),
    ("Contribution Profit", "Margin", "₹ #,0", "[Gross Profit] - [Freight Cost]"),
    ("Contribution Margin %", "Margin", "0.0%", "DIVIDE ( [Contribution Profit], [Recognized Revenue] )"),
    ("Net Quantity", "Unit economics", "#,0", "SUM ( fact_sales[net_qty] )"),
    ("Average Selling Price", "Unit economics", "₹ #,0.00", "DIVIDE ( [Recognized Revenue], [Net Quantity] )"),
    ("Unit Cost", "Unit economics", "₹ #,0.00", "DIVIDE ( [COGS], [Net Quantity] )"),
    ("Unit Margin", "Unit economics", "₹ #,0.00", "[Average Selling Price] - [Unit Cost]"),
    (
        "Discount Rate",
        "Unit economics",
        "0.0%",
        "DIVIDE ( SUM ( fact_sales[discount_amount] ), SUM ( fact_sales[list_revenue] ) )",
    ),
    (
        "Price Realization",
        "Unit economics",
        "0.0%",
        "DIVIDE ( [Recognized Revenue], SUM ( fact_sales[list_revenue] ) )",
    ),
    (
        "Return Rate",
        "Unit economics",
        "0.0%",
        "DIVIDE ( SUM ( fact_sales[return_qty] ), SUM ( fact_sales[quantity] ) )",
    ),
    ("Purchase Value", "Supplier performance", "₹ #,0", "SUM ( fact_purchases[purchase_value] )"),
    (
        "Purchase Cost per Unit",
        "Unit economics",
        "₹ #,0.00",
        "DIVIDE ( [Purchase Value], SUM ( fact_purchases[qty_received] ) )",
    ),
    (
        "Purchase Price Variance %",
        "Unit economics",
        "0.0%",
        "VAR StandardCost =\n"
        "    SUMX (\n"
        "        fact_purchases,\n"
        "        fact_purchases[qty_received] * RELATED ( dim_product[standard_cost] )\n"
        "    )\n"
        "RETURN\n"
        "    DIVIDE ( [Purchase Value] - StandardCost, StandardCost )",
    ),
    (
        "On-Time Delivery %",
        "Supplier performance",
        "0.0%",
        "DIVIDE ( SUM ( fact_purchases[on_time_flag] ), COUNTROWS ( fact_purchases ) )",
    ),
    (
        "Fill Rate %",
        "Supplier performance",
        "0.0%",
        "DIVIDE ( SUM ( fact_purchases[qty_received] ), SUM ( fact_purchases[qty_ordered] ) )",
    ),
    (
        "Defect Rate %",
        "Supplier performance",
        "0.0%",
        "DIVIDE ( SUM ( fact_purchases[qty_defective] ), SUM ( fact_purchases[qty_received] ) )",
    ),
    (
        "Average Lead Time (days)",
        "Supplier performance",
        "0.0",
        "AVERAGE ( fact_purchases[actual_lead_days] )",
    ),
    (
        "Top 10 Spend Share",
        "Risk",
        "0.0%",
        "VAR BySupplier =\n"
        "    ADDCOLUMNS (\n"
        "        SUMMARIZE ( dim_supplier, dim_supplier[supplier_id] ),\n"
        "        \"@Spend\", [Purchase Value]\n"
        "    )\n"
        "VAR TopSpend =\n"
        "    SUMX ( TOPN ( 10, BySupplier, [@Spend], DESC ), [@Spend] )\n"
        "RETURN\n"
        "    DIVIDE ( TopSpend, [Purchase Value] )",
    ),
    (
        "Spend HHI",
        "Risk",
        "0.000",
        "VAR BySupplier =\n"
        "    ADDCOLUMNS (\n"
        "        FILTER (\n"
        "            SUMMARIZE ( dim_supplier, dim_supplier[supplier_id] ),\n"
        "            [Purchase Value] > 0\n"
        "        ),\n"
        "        \"@Share\", DIVIDE ( [Purchase Value], CALCULATE ( [Purchase Value], ALL ( dim_supplier ) ) )\n"
        "    )\n"
        "RETURN\n"
        "    SUMX ( BySupplier, [@Share] * [@Share] )",
    ),
    (
        "Single-Source SKU %",
        "Risk",
        "0.0%",
        "VAR Products =\n"
        "    SUMMARIZE (\n"
        "        fact_purchases,\n"
        "        fact_purchases[product_id],\n"
        "        \"@Suppliers\", DISTINCTCOUNT ( fact_purchases[supplier_id] )\n"
        "    )\n"
        "RETURN\n"
        "    DIVIDE (\n"
        "        COUNTROWS ( FILTER ( Products, [@Suppliers] = 1 ) ),\n"
        "        COUNTROWS ( Products )\n"
        "    )",
    ),
    (
        "Weighted Days Payable",
        "Risk",
        "0.0",
        "DIVIDE (\n"
        "    SUMX ( dim_supplier, [Purchase Value] * dim_supplier[payment_terms_days] ),\n"
        "    [Purchase Value]\n"
        ")",
    ),
    (
        "Revenue Prior Year",
        "Growth",
        "₹ #,0",
        "VAR MinDate = MIN ( dim_date[date] )\n"
        "VAR MaxDate = MAX ( dim_date[date] )\n"
        "RETURN\n"
        "    CALCULATE (\n"
        "        [Recognized Revenue],\n"
        "        ALL ( dim_date ),\n"
        "        dim_date[date] >= EDATE ( MinDate, -12 ),\n"
        "        dim_date[date] <= EDATE ( MaxDate, -12 )\n"
        "    )",
    ),
    (
        "Revenue YoY %",
        "Growth",
        "0.0%",
        "DIVIDE ( [Recognized Revenue] - [Revenue Prior Year], [Revenue Prior Year] )",
    ),
    (
        "Gross Margin Prior Year",
        "Growth",
        "0.0%",
        "VAR MinDate = MIN ( dim_date[date] )\n"
        "VAR MaxDate = MAX ( dim_date[date] )\n"
        "RETURN\n"
        "    CALCULATE (\n"
        "        [Gross Margin %],\n"
        "        ALL ( dim_date ),\n"
        "        dim_date[date] >= EDATE ( MinDate, -12 ),\n"
        "        dim_date[date] <= EDATE ( MaxDate, -12 )\n"
        "    )",
    ),
    (
        "Gross Margin Change bps",
        "Growth",
        "0",
        "( [Gross Margin %] - [Gross Margin Prior Year] ) * 10000",
    ),
    (
        "Revenue FY25 vs FY24",
        "Growth",
        "0.0%",
        "VAR FY25 = CALCULATE ( [Recognized Revenue], dim_date[fy_label] = \"FY25\" )\n"
        "VAR FY24 = CALCULATE ( [Recognized Revenue], dim_date[fy_label] = \"FY24\" )\n"
        "RETURN DIVIDE ( FY25 - FY24, FY24 )",
    ),
    (
        "Supplier Cost Index",
        "Unit economics",
        "0.00",
        "VAR Categories = VALUES ( dim_product[category] )\n"
        "VAR Numerator =\n"
        "    SUMX (\n"
        "        Categories,\n"
        "        VAR BaseQty =\n"
        "            CALCULATE (\n"
        "                SUM ( fact_purchases[qty_received] ),\n"
        "                DATESBETWEEN ( dim_date[date], DATE ( 2023, 4, 1 ), DATE ( 2023, 6, 30 ) )\n"
        "            )\n"
        "        VAR LatestCost =\n"
        "            CALCULATE (\n"
        "                [Purchase Cost per Unit],\n"
        "                DATESBETWEEN ( dim_date[date], DATE ( 2025, 7, 1 ), DATE ( 2025, 9, 30 ) )\n"
        "            )\n"
        "        RETURN LatestCost * BaseQty\n"
        "    )\n"
        "VAR Denominator =\n"
        "    SUMX (\n"
        "        Categories,\n"
        "        VAR BaseQty =\n"
        "            CALCULATE (\n"
        "                SUM ( fact_purchases[qty_received] ),\n"
        "                DATESBETWEEN ( dim_date[date], DATE ( 2023, 4, 1 ), DATE ( 2023, 6, 30 ) )\n"
        "            )\n"
        "        VAR BaseCost =\n"
        "            CALCULATE (\n"
        "                [Purchase Cost per Unit],\n"
        "                DATESBETWEEN ( dim_date[date], DATE ( 2023, 4, 1 ), DATE ( 2023, 6, 30 ) )\n"
        "            )\n"
        "        RETURN BaseCost * BaseQty\n"
        "    )\n"
        "RETURN DIVIDE ( Numerator, Denominator )",
    ),
    (
        "Private Label Margin Gap bps",
        "Margin",
        "0",
        "VAR PrivateLabel =\n"
        "    CALCULATE (\n"
        "        [Gross Margin %],\n"
        "        dim_product[brand_type] = \"Private Label\",\n"
        "        dim_product[category] = \"Snacks\"\n"
        "    )\n"
        "VAR Branded =\n"
        "    CALCULATE (\n"
        "        [Gross Margin %],\n"
        "        dim_product[brand_type] = \"Branded\",\n"
        "        dim_product[category] = \"Snacks\"\n"
        "    )\n"
        "RETURN ( PrivateLabel - Branded ) * 10000",
    ),
]


def _dtype(column: str, sample: str) -> str:
    if column in INT_COLUMNS:
        return "int64"
    if column in DATE_COLUMNS:
        return "dateTime"
    if column in SUM_COLUMNS or _looks_numeric(sample):
        return "double"
    return "string"


def _looks_numeric(sample: str) -> bool:
    try:
        float(sample)
    except (TypeError, ValueError):
        return False
    return True


def _m_type(dtype: str) -> str:
    return {
        "int64": "Int64.Type",
        "double": "type number",
        "dateTime": "type date",
        "string": "type text",
    }[dtype]


def _table(name: str, csv_path: Path, columns: list[tuple[str, str]], measures: list[dict] | None = None) -> dict:
    pairs = ", ".join(
        '{"' + column + '", ' + _m_type(dtype) + "}" for column, dtype in columns
    )
    # Build the M expression as lines. File.Contents needs a literal path.
    path = str(csv_path).replace("\\", "/")
    expression = [
        "let",
        f'    Source = Csv.Document(File.Contents("{path}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
        f"    Typed = Table.TransformColumnTypes(Promoted, {{{pairs}}})",
        "in",
        "    Typed",
    ]
    table = {
        "name": name,
        "columns": [],
        "partitions": [
            {
                "name": name,
                "mode": "import",
                "source": {"type": "m", "expression": expression},
            }
        ],
    }
    for column, dtype in columns:
        spec = {
            "name": column,
            "dataType": dtype,
            "sourceColumn": column,
            "summarizeBy": "sum" if column in SUM_COLUMNS else "none",
        }
        if name.startswith("dim_") and column in {"supplier_id", "product_id", "customer_id", "date_key"}:
            spec["isKey"] = True
        table["columns"].append(spec)
    if measures:
        table["measures"] = measures
    return table


def _relationship(name: str, fact: str, column: str, dimension: str) -> dict:
    return {
        "name": name,
        "fromTable": fact,
        "fromColumn": column,
        "toTable": dimension,
        "toColumn": column,
        "crossFilteringBehavior": "oneDirection",
    }


def write_powerbi() -> None:
    import pandas as pd

    PBIP_DIR.mkdir(parents=True, exist_ok=True)
    tables = []
    measure_payload = [
        {
            "name": name,
            "displayFolder": folder,
            "formatString": fmt,
            "expression": expression,
        }
        for name, folder, fmt, expression in MEASURES
    ]
    for csv_name in (
        "dim_date",
        "dim_supplier",
        "dim_product",
        "dim_customer",
        "fact_sales",
        "fact_purchases",
    ):
        path = POWERBI_DIR / f"{csv_name}.csv"
        header = pd.read_csv(path, nrows=1)
        columns = [(column, _dtype(column, str(header.iloc[0][column]))) for column in header.columns]
        measures = measure_payload if csv_name == "fact_sales" else None
        tables.append(_table(csv_name, path, columns, measures))

    model = {
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-IN",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-IN",
            "tables": tables,
            "relationships": [
                _relationship("sales_date", "fact_sales", "date_key", "dim_date"),
                _relationship("sales_product", "fact_sales", "product_id", "dim_product"),
                _relationship("sales_customer", "fact_sales", "customer_id", "dim_customer"),
                _relationship("sales_supplier", "fact_sales", "supplier_id", "dim_supplier"),
                _relationship("purchases_date", "fact_purchases", "date_key", "dim_date"),
                _relationship("purchases_product", "fact_purchases", "product_id", "dim_product"),
                _relationship("purchases_supplier", "fact_purchases", "supplier_id", "dim_supplier"),
            ],
        },
    }

    semantic = PBIP_DIR / "FEC_Sales.SemanticModel"
    report = PBIP_DIR / "FEC_Sales.Report"
    semantic.mkdir(parents=True, exist_ok=True)
    report.mkdir(parents=True, exist_ok=True)
    (semantic / "model.bim").write_text(json.dumps(model, indent=2))
    (semantic / "definition.pbism").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
                "version": "4.0",
                "settings": {},
            },
            indent=2,
        )
    )
    (semantic / ".platform").write_text(
        json.dumps(_platform("SemanticModel", "FEC Sales", SEMANTIC_ID), indent=2)
    )
    (report / "definition.pbir").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
                "version": "1.0",
                "datasetReference": {"byPath": {"path": "../FEC_Sales.SemanticModel"}},
            },
            indent=2,
        )
    )
    (report / ".platform").write_text(json.dumps(_platform("Report", "FEC Sales", REPORT_ID), indent=2))
    (report / "report.json").write_text(json.dumps(_report(), indent=2))
    (PBIP_DIR / "FEC_Sales.pbip").write_text(
        json.dumps(
            {
                "version": "1.0",
                "artifacts": [{"report": {"path": "FEC_Sales.Report"}}],
                "settings": {"enableAutoRecovery": True},
            },
            indent=2,
        )
    )
    _write_dax()


def _platform(kind: str, display_name: str, logical_id: str) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": kind, "displayName": display_name},
        "config": {"version": "2.0", "logicalId": logical_id},
    }


def _card(measure: str, x: int, y: int, width: int = 300, height: int = 130) -> dict:
    """A card bound to a measure on fact_sales. Power BI reads `config` as a JSON string."""
    config = {
        "name": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{measure}-{x}-{y}")),
        "layouts": [
            {
                "id": 0,
                "position": {"x": x, "y": y, "z": 0, "width": width, "height": height},
            }
        ],
        "singleVisual": {
            "visualType": "card",
            "projections": {"Values": [{"queryRef": f"fact_sales.{measure}"}]},
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "s", "Entity": "fact_sales", "Type": 0}],
                "Select": [
                    {
                        "Measure": {
                            "Expression": {"SourceRef": {"Source": "s"}},
                            "Property": measure,
                        },
                        "Name": f"fact_sales.{measure}",
                        "NativeReferenceName": measure,
                    }
                ],
            },
        },
    }
    return {
        "config": json.dumps(config),
        "filters": "[]",
        "x": x,
        "y": y,
        "z": 0,
        "width": width,
        "height": height,
    }


def _report() -> dict:
    pages = [
        (
            "Overview",
            [
                "Recognized Revenue",
                "Gross Margin %",
                "Contribution Margin %",
                "Revenue YoY %",
            ],
        ),
        (
            "Unit economics",
            [
                "Average Selling Price",
                "Purchase Cost per Unit",
                "Unit Margin",
                "Purchase Price Variance %",
            ],
        ),
        (
            "Suppliers",
            [
                "On-Time Delivery %",
                "Fill Rate %",
                "Defect Rate %",
                "Average Lead Time (days)",
            ],
        ),
        (
            "Risk",
            [
                "Top 10 Spend Share",
                "Spend HHI",
                "Single-Source SKU %",
                "Weighted Days Payable",
            ],
        ),
    ]
    sections = []
    for ordinal, (title, measures) in enumerate(pages):
        visuals = [
            _card(measure, 24 + (index % 4) * 310, 24, 290, 140)
            for index, measure in enumerate(measures)
        ]
        sections.append(
            {
                "displayName": title,
                "displayOption": 1,
                "height": 720,
                "name": str(uuid.uuid5(uuid.NAMESPACE_URL, title)),
                "ordinal": ordinal,
                "visualContainers": visuals,
                "width": 1280,
            }
        )
    return {
        "config": json.dumps(
            {
                "version": "5.43",
                "activeSectionIndex": 0,
                "defaultDrillFilterOtherVisuals": True,
                "settings": {
                    "useNewFilterPaneExperience": True,
                    "allowChangeFilterTypes": True,
                    "useStylableVisualContainerHeader": True,
                    "exportDataMode": 1,
                    "useDefaultAggregateDisplayName": True,
                },
            }
        ),
        "layoutOptimization": 0,
        "sections": sections,
    }


def _write_dax() -> None:
    lines = [
        "-- DAX measure library for the FEC sales model.",
        "-- The same expressions are embedded in FEC_Sales.SemanticModel/model.bim.",
        "-- Put dim_date[date] on the axis. Mark dim_date as a date table on first open.",
        "",
    ]
    folder = None
    for name, display_folder, fmt, expression in MEASURES:
        if display_folder != folder:
            lines.append(f"// {display_folder}")
            folder = display_folder
        lines.append(f"[{name}] =")
        lines.append(expression)
        lines.append(f"-- format: {fmt}")
        lines.append("")
    (PBIP_DIR / "measures.dax").write_text("\n".join(lines))
