# Supplier sales analysis

Finance & Economics Club, IIT Guwahati.

A wholesale book for a Northeast India distributor: 120 suppliers, about 150 SKUs, and thirty months of sales and purchases from April 2023 through September 2025. The pipeline turns messy monthly ERP extracts into a star schema, a SQL KPI library, a Power BI model, and an interactive dashboard.

The invoices are synthetic. They are shaped like a real extract — Assam tea, edible oils, staples, hill-state freight — so the warehouse, the measures, and the dashboard can be re-run and reviewed without using a live supplier’s data.

The dashboard is public: [skx56.github.io/fec-sales-analysis](https://skx56.github.io/fec-sales-analysis/).

## What the book shows

On the seeded run, recognized revenue is ₹192.96 Cr and gross margin is 22.5%. FY25 revenue is 6.8% above FY24, while book gross margin is 27 bps lower. The damage is in one category.

- Edible-oil gross margin falls from 13.0% in FY24 to 8.8% in FY25. Unit cost rises 11.2% and the selling price rises 6.1%. The bridge assigns +504 bps to price and −923 bps to cost.
- Dispur Grain Merchants is 15.6% of purchase value. The ten largest suppliers are 58.4% of spend (HHI 0.060).
- Luit Packaging Works delivers on time 65.3% of the time, against 92.2% for the book, on ₹3.37 Cr of purchases.
- Private-label snacks earn a 35.2% gross margin, against 30.4% for branded snacks.
- In FY25, suppliers onboarded from January 2024 have a cost index of 0.89 against 1.00 for incumbents. Their defect rate is 2.0% against 0.6%.
- Contribution margin is 17.5% in the hill states and 21.4% in the Assam valley. Freight per unit is ₹3.60 against ₹1.10.

Fiscal years start in April. FY24 is April 2023–March 2024. FY26 in this extract is the first half only, through September 2025.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pipeline
```

That writes:

| Output | What it is |
| --- | --- |
| `dashboard/index.html` | Interactive dashboard. Open it in a browser. |
| `data/warehouse/sales.sqlite` | Star schema. |
| `data/powerbi/*.csv` | The same tables, for Power BI. |
| `sql/kpis.sql` | The KPI queries the pipeline actually runs. |
| `output/kpi_catalog.csv` | One row per KPI, with definition and value. |
| `output/supplier_scorecard.csv` | Supplier score by fiscal year. |
| `powerbi/FEC_Sales.pbip` | Power BI project. Desktop is Windows-only. |
| `powerbi/measures.dax` | The same measures, readable without Desktop. |

The dashboard filters by fiscal year and category. Cost per unit is shown inside a category. Across the whole book the cost tile is a Laspeyres index (April–June 2023 = 100), because a kilo of tea and a carton are not the same unit.

## Warehouse

`sql/schema.sql` is a star schema.

- `dim_date`, `dim_supplier`, `dim_product`, `dim_customer`
- `fact_sales` at invoice-line grain
- `fact_purchases` at purchase-order-line grain

Sales measures (recognized revenue, COGS, gross profit, contribution profit) are computed in the load step from quantity, returns, price, cost, and freight. The SQL library only aggregates them.

Raw files land in `data/raw/`. Sales and purchases are one file per month, with mixed date formats, rupee strings, supplier-name variants, duplicate lines, and the odd blank quantity. `pipeline/transform.py` parses and reconciles them against the master files. Supplier names are matched after normalization (`Pvt Ltd`, case, extra spaces). Unmatched rows fail the run.

## KPIs

Twenty-seven measures are defined in `sql/kpis.sql` and listed in `pipeline/config.py`. Ratios in SQL are fractions.

| KPI | Definition |
| --- | --- |
| Recognized revenue | Net quantity × net selling price, after returns |
| COGS | Net quantity × unit purchase cost of that lot |
| Gross profit | Recognized revenue − COGS |
| Gross margin | Gross profit / recognized revenue |
| Contribution profit | Gross profit − outbound freight |
| Contribution margin | Contribution profit / recognized revenue |
| Average selling price | Recognized revenue / net quantity, read inside a category |
| Purchase cost per unit | Purchase value / quantity received, read inside a category |
| Unit margin | Average selling price − unit cost, inside one category |
| Discount rate | Discount amount / list revenue |
| Price realization | Recognized revenue / list revenue |
| Freight per unit | Outbound freight / net quantity |
| Return rate | Returned quantity / quantity invoiced |
| On-time delivery | Lines received inside contracted lead time / lines |
| Fill rate | Quantity received / quantity ordered |
| Defect rate | Quantity rejected / quantity received |
| Average lead time | Mean days from PO to receipt |
| Top-10 spend share | Purchase value of the ten largest suppliers / total |
| Supplier HHI | Sum of squared supplier spend shares |
| Single-source SKU share | SKUs with one supplier / SKUs purchased |
| Weighted days payable | Spend-weighted contractual payment terms |
| Purchase price variance | (Actual purchase value − standard × qty) / standard value |
| Revenue growth | FY25 revenue / FY24 revenue − 1 |
| Gross margin change | FY25 gross margin − FY24 gross margin |
| Supplier cost index | Laspeyres index of category unit costs, Q1 FY24 = 1 |
| Private-label margin gap | Snacks: private-label gross margin − branded gross margin |
| Supplier score | Median of the peer score below |

Supplier score, against others in the same category and period:

`100 × (30% cost position + 25% on-time + 20% fill + 15% quality + 10% margin position)`

Cost position and margin position are percentile ranks. Quality falls from 1 to 0 as the defect rate rises from 0 to 5%.

Book-level average selling price and book-level cost per unit are in the catalog because they are standard totals. They mix units. Decisions use the category table.

## Automation

The manual close this replaces: collect the monthly sales and purchase files, repair supplier names, strip currency formatting, drop duplicate lines, rebuild the pivots, and paste the pack. That is about five hours.

The automated close is `python -m pipeline`, then a review of the exception list (on-time below 80%, defect rate above 1.5%, score below 58, single-source SKUs). That review is about one hour, which is 80% less analyst time. The pipeline’s own runtime is a few seconds and is reported separately in `output/run_log.json`. It is not the 80%.

## Power BI

Open `powerbi/FEC_Sales.pbip` in Power BI Desktop (Windows). On first refresh, approve the local CSV folder. The path is written when the pipeline runs, so re-run `python -m pipeline` on the machine where Desktop will open the file.

Then:

1. Mark `dim_date` as a date table on `date`.
2. The model already has the relationships and the measure library (Revenue, Margin, Unit economics, Supplier performance, Risk, Growth).
3. Build four pages that match the dashboard: Overview, Unit economics, Suppliers, Risk. Drag `fy_label` and `category` in as slicers.

`powerbi/measures.dax` is the same library in plain text. On a Mac, use `dashboard/index.html`; it reads the same queries.

## Layout

```
pipeline/          generate, clean, SQL runner, dashboard, Power BI model
sql/schema.sql     star schema
sql/kpis.sql       named KPI queries
data/raw/          monthly extracts and masters
data/warehouse/    sales.sqlite
data/powerbi/      CSV star schema
dashboard/         index.html
powerbi/           PBIP project and measures.dax
output/            KPI catalog, scorecard, run log
```
