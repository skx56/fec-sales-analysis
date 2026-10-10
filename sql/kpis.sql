-- KPI library for the FEC supplier sales warehouse.
-- Each block is named with `-- @name`. The pipeline runs every block.
-- Ratios are fractions (0.18 = 18%). Basis-point gaps are fractions of margin, not already scaled.

-- @name _views
DROP VIEW IF EXISTS vw_sales;
DROP VIEW IF EXISTS vw_purchases;

CREATE VIEW vw_sales AS
SELECT
    fs.sale_id,
    fs.date_key,
    fs.product_id,
    fs.customer_id,
    fs.supplier_id,
    fs.quantity,
    fs.return_qty,
    fs.net_qty,
    fs.list_price,
    fs.discount_rate,
    fs.unit_price,
    fs.unit_cost,
    fs.freight_per_unit,
    fs.list_revenue,
    fs.discount_amount,
    fs.recognized_revenue,
    fs.cogs,
    fs.freight_cost,
    fs.gross_profit,
    fs.contribution_profit,
    d.date,
    d.month_start,
    d.fy_label,
    d.fy_year,
    d.fiscal_month,
    d.month_name,
    p.sku,
    p.product_name,
    p.category,
    p.subcategory,
    p.brand_type,
    p.standard_cost,
    c.channel,
    c.region_group,
    c.state AS customer_state,
    s.supplier_name,
    s.category_focus,
    s.tier,
    s.cohort,
    s.payment_terms_days,
    s.state AS supplier_state,
    s.city AS supplier_city
FROM fact_sales fs
JOIN dim_date d ON d.date_key = fs.date_key
JOIN dim_product p ON p.product_id = fs.product_id
JOIN dim_customer c ON c.customer_id = fs.customer_id
JOIN dim_supplier s ON s.supplier_id = fs.supplier_id;

CREATE VIEW vw_purchases AS
SELECT
    fp.purchase_id,
    fp.date_key,
    fp.supplier_id,
    fp.product_id,
    fp.qty_ordered,
    fp.qty_received,
    fp.qty_defective,
    fp.unit_cost,
    fp.purchase_value,
    fp.contracted_lead_days,
    fp.actual_lead_days,
    fp.on_time_flag,
    d.date,
    d.month_start,
    d.fy_label,
    d.fy_year,
    p.sku,
    p.product_name,
    p.category,
    p.brand_type,
    p.standard_cost,
    s.supplier_name,
    s.category_focus,
    s.tier,
    s.cohort,
    s.payment_terms_days,
    s.state AS supplier_state,
    s.city AS supplier_city
FROM fact_purchases fp
JOIN dim_date d ON d.date_key = fp.date_key
JOIN dim_product p ON p.product_id = fp.product_id
JOIN dim_supplier s ON s.supplier_id = fp.supplier_id;

-- @name headline
WITH sales AS (
    SELECT
        SUM(recognized_revenue) AS revenue,
        SUM(cogs) AS cogs,
        SUM(gross_profit) AS gross_profit,
        SUM(contribution_profit) AS contribution_profit,
        SUM(freight_cost) AS freight,
        SUM(net_qty) AS net_qty,
        SUM(list_revenue) AS list_revenue,
        SUM(discount_amount) AS discount_amount,
        SUM(return_qty) AS return_qty,
        SUM(quantity) AS quantity
    FROM vw_sales
),
fy AS (
    SELECT
        fy_label,
        SUM(recognized_revenue) AS revenue,
        SUM(gross_profit) AS gross_profit
    FROM vw_sales
    WHERE fy_label IN ('FY24', 'FY25')
    GROUP BY fy_label
),
purch AS (
    SELECT
        SUM(purchase_value) AS spend,
        SUM(qty_received) AS qty_received,
        SUM(qty_ordered) AS qty_ordered,
        SUM(qty_defective) AS qty_defective,
        SUM(on_time_flag) AS on_time_lines,
        COUNT(*) AS lines,
        SUM(actual_lead_days) AS lead_sum,
        SUM(qty_received * standard_cost) AS standard_value
    FROM vw_purchases
),
shares AS (
    SELECT
        supplier_id,
        SUM(purchase_value) AS spend,
        SUM(purchase_value) * 1.0 / SUM(SUM(purchase_value)) OVER () AS share
    FROM vw_purchases
    GROUP BY supplier_id
),
top10 AS (
    SELECT SUM(share) AS top10_share
    FROM (
        SELECT share
        FROM shares
        ORDER BY spend DESC
        LIMIT 10
    )
),
hhi AS (
    SELECT SUM(share * share) AS hhi FROM shares
),
src AS (
    SELECT product_id, COUNT(DISTINCT supplier_id) AS n_suppliers
    FROM vw_purchases
    GROUP BY product_id
),
single AS (
    SELECT AVG(CASE WHEN n_suppliers = 1 THEN 1.0 ELSE 0.0 END) AS single_share
    FROM src
),
dpo AS (
    SELECT SUM(sh.spend * s.payment_terms_days) * 1.0 / SUM(sh.spend) AS dpo
    FROM shares sh
    JOIN dim_supplier s ON s.supplier_id = sh.supplier_id
),
snacks AS (
    SELECT
        brand_type,
        SUM(gross_profit) * 1.0 / SUM(recognized_revenue) AS margin
    FROM vw_sales
    WHERE category = 'Snacks'
    GROUP BY brand_type
)
SELECT
    sales.revenue AS recognized_revenue,
    sales.cogs AS cogs,
    sales.gross_profit AS gross_profit,
    sales.gross_profit * 1.0 / sales.revenue AS gross_margin,
    sales.contribution_profit AS contribution_profit,
    sales.contribution_profit * 1.0 / sales.revenue AS contribution_margin,
    sales.revenue * 1.0 / sales.net_qty AS average_selling_price,
    purch.spend * 1.0 / purch.qty_received AS purchase_cost_per_unit,
    (sales.revenue / sales.net_qty) - (sales.cogs / sales.net_qty) AS unit_margin,
    sales.discount_amount * 1.0 / sales.list_revenue AS discount_rate,
    sales.revenue * 1.0 / sales.list_revenue AS price_realization,
    sales.freight * 1.0 / sales.net_qty AS freight_per_unit,
    sales.return_qty * 1.0 / sales.quantity AS return_rate,
    purch.on_time_lines * 1.0 / purch.lines AS on_time_delivery,
    purch.qty_received * 1.0 / purch.qty_ordered AS fill_rate,
    purch.qty_defective * 1.0 / purch.qty_received AS defect_rate,
    purch.lead_sum * 1.0 / purch.lines AS average_lead_time,
    top10.top10_share AS top10_spend_share,
    hhi.hhi AS supplier_hhi,
    single.single_share AS single_source_sku_pct,
    dpo.dpo AS weighted_days_payable,
    (purch.spend - purch.standard_value) * 1.0 / purch.standard_value AS purchase_price_variance,
    (SELECT revenue FROM fy WHERE fy_label = 'FY25') * 1.0
        / (SELECT revenue FROM fy WHERE fy_label = 'FY24') - 1 AS revenue_growth_fy25,
    (
        (SELECT gross_profit * 1.0 / revenue FROM fy WHERE fy_label = 'FY25')
        - (SELECT gross_profit * 1.0 / revenue FROM fy WHERE fy_label = 'FY24')
    ) AS gross_margin_change_fy25,
    (SELECT margin FROM snacks WHERE brand_type = 'Private Label')
        - (SELECT margin FROM snacks WHERE brand_type = 'Branded') AS private_label_margin_gap
FROM sales, purch, top10, hhi, single, dpo;

-- @name cost_index
WITH cat AS (
    SELECT
        category,
        CASE
            WHEN month_start BETWEEN '2023-04-01' AND '2023-06-01' THEN 'base'
            WHEN month_start BETWEEN '2025-07-01' AND '2025-09-01' THEN 'latest'
        END AS period,
        SUM(purchase_value) AS spend,
        SUM(qty_received) AS qty
    FROM vw_purchases
    GROUP BY category, period
),
wide AS (
    SELECT
        category,
        MAX(CASE WHEN period = 'base' THEN spend * 1.0 / qty END) AS base_cost,
        MAX(CASE WHEN period = 'base' THEN qty END) AS base_qty,
        MAX(CASE WHEN period = 'latest' THEN spend * 1.0 / qty END) AS latest_cost
    FROM cat
    WHERE period IS NOT NULL
    GROUP BY category
)
SELECT
    SUM(latest_cost * base_qty) * 1.0 / SUM(base_cost * base_qty) AS supplier_cost_index
FROM wide
WHERE base_cost IS NOT NULL AND latest_cost IS NOT NULL AND base_qty > 0;

-- @name monthly_sales
SELECT
    month_start,
    fy_label,
    category,
    channel,
    region_group,
    SUM(recognized_revenue) AS recognized_revenue,
    SUM(cogs) AS cogs,
    SUM(freight_cost) AS freight_cost,
    SUM(gross_profit) AS gross_profit,
    SUM(contribution_profit) AS contribution_profit,
    SUM(net_qty) AS net_qty,
    SUM(list_revenue) AS list_revenue,
    SUM(discount_amount) AS discount_amount,
    SUM(return_qty) AS return_qty,
    SUM(quantity) AS quantity
FROM vw_sales
GROUP BY month_start, fy_label, category, channel, region_group
ORDER BY month_start, category, channel, region_group;

-- @name monthly_ops
SELECT
    month_start,
    fy_label,
    category,
    SUM(purchase_value) AS purchase_value,
    SUM(qty_received) AS qty_received,
    SUM(qty_ordered) AS qty_ordered,
    SUM(qty_defective) AS qty_defective,
    SUM(on_time_flag) AS on_time_lines,
    COUNT(*) AS po_lines,
    SUM(actual_lead_days) AS lead_time_sum
FROM vw_purchases
GROUP BY month_start, fy_label, category
ORDER BY month_start, category;

-- @name category_fy
SELECT
    category,
    fy_label,
    SUM(recognized_revenue) AS revenue,
    SUM(gross_profit) AS gross_profit,
    SUM(contribution_profit) AS contribution_profit,
    SUM(net_qty) AS net_qty,
    SUM(cogs) AS cogs,
    SUM(gross_profit) * 1.0 / SUM(recognized_revenue) AS gross_margin,
    SUM(contribution_profit) * 1.0 / SUM(recognized_revenue) AS contribution_margin,
    SUM(recognized_revenue) * 1.0 / SUM(net_qty) AS asp,
    SUM(cogs) * 1.0 / SUM(net_qty) AS unit_cost
FROM vw_sales
GROUP BY category, fy_label
ORDER BY category, fy_label;

-- @name oil_bridge
WITH u AS (
    SELECT
        fy_label AS fy,
        SUM(recognized_revenue) * 1.0 / SUM(net_qty) AS p,
        SUM(cogs) * 1.0 / SUM(net_qty) AS c,
        SUM(recognized_revenue) AS revenue,
        SUM(gross_profit) * 1.0 / SUM(recognized_revenue) AS gm
    FROM vw_sales
    WHERE category = 'Edible Oils'
      AND fy_label IN ('FY24', 'FY25')
    GROUP BY fy_label
),
a AS (SELECT * FROM u WHERE fy = 'FY24'),
b AS (SELECT * FROM u WHERE fy = 'FY25')
SELECT
    a.gm AS gm_fy24,
    b.gm AS gm_fy25,
    ((b.p - a.c) / b.p) - ((a.p - a.c) / a.p) AS price_effect,
    ((b.p - b.c) / b.p) - ((b.p - a.c) / b.p) AS cost_effect,
    b.p / a.p - 1 AS price_change,
    b.c / a.c - 1 AS cost_change,
    a.p AS price_fy24,
    a.c AS cost_fy24,
    b.p AS price_fy25,
    b.c AS cost_fy25,
    a.revenue AS revenue_fy24,
    b.revenue AS revenue_fy25
FROM a, b;

-- @name supplier_scorecard
WITH purch_fy AS (
    SELECT
        supplier_id,
        fy_label,
        SUM(purchase_value) AS spend,
        SUM(qty_received) AS qty_received,
        SUM(qty_ordered) AS qty_ordered,
        SUM(qty_defective) AS qty_defective,
        SUM(on_time_flag) AS on_time_lines,
        COUNT(*) AS po_lines,
        SUM(actual_lead_days) AS lead_sum
    FROM vw_purchases
    GROUP BY supplier_id, fy_label
),
purch_all AS (
    SELECT
        supplier_id,
        'ALL' AS fy_label,
        SUM(spend) AS spend,
        SUM(qty_received) AS qty_received,
        SUM(qty_ordered) AS qty_ordered,
        SUM(qty_defective) AS qty_defective,
        SUM(on_time_lines) AS on_time_lines,
        SUM(po_lines) AS po_lines,
        SUM(lead_sum) AS lead_sum
    FROM purch_fy
    GROUP BY supplier_id
),
purch AS (
    SELECT * FROM purch_fy
    UNION ALL
    SELECT * FROM purch_all
),
sales_fy AS (
    SELECT
        supplier_id,
        fy_label,
        SUM(recognized_revenue) AS revenue,
        SUM(gross_profit) AS gross_profit,
        SUM(net_qty) AS net_qty
    FROM vw_sales
    GROUP BY supplier_id, fy_label
),
sales_all AS (
    SELECT
        supplier_id,
        'ALL' AS fy_label,
        SUM(revenue) AS revenue,
        SUM(gross_profit) AS gross_profit,
        SUM(net_qty) AS net_qty
    FROM sales_fy
    GROUP BY supplier_id
),
sales AS (
    SELECT * FROM sales_fy
    UNION ALL
    SELECT * FROM sales_all
),
base AS (
    SELECT
        p.supplier_id,
        s.supplier_name,
        s.category_focus,
        s.tier,
        s.cohort,
        s.state,
        s.city,
        s.payment_terms_days,
        p.fy_label,
        p.spend,
        p.spend * 1.0 / NULLIF(p.qty_received, 0) AS cost_per_unit,
        p.on_time_lines * 1.0 / p.po_lines AS otd,
        p.qty_received * 1.0 / NULLIF(p.qty_ordered, 0) AS fill_rate,
        p.qty_defective * 1.0 / NULLIF(p.qty_received, 0) AS defect_rate,
        p.lead_sum * 1.0 / p.po_lines AS lead_time,
        COALESCE(sa.revenue, 0) AS revenue,
        COALESCE(sa.gross_profit, 0) AS gross_profit,
        COALESCE(sa.gross_profit, 0) * 1.0 / NULLIF(sa.revenue, 0) AS gross_margin
    FROM purch p
    JOIN dim_supplier s ON s.supplier_id = p.supplier_id
    LEFT JOIN sales sa
        ON sa.supplier_id = p.supplier_id
       AND sa.fy_label = p.fy_label
    WHERE p.qty_received > 0
),
ordered AS (
    SELECT
        category_focus,
        fy_label,
        cost_per_unit,
        ROW_NUMBER() OVER (
            PARTITION BY category_focus, fy_label
            ORDER BY cost_per_unit
        ) AS rn,
        COUNT(*) OVER (PARTITION BY category_focus, fy_label) AS n
    FROM base
),
medians AS (
    SELECT category_focus, fy_label, AVG(cost_per_unit) AS median_cost
    FROM ordered
    WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
    GROUP BY category_focus, fy_label
),
ranked AS (
    SELECT
        b.*,
        b.cost_per_unit / m.median_cost AS cost_index,
        PERCENT_RANK() OVER (
            PARTITION BY b.category_focus, b.fy_label
            ORDER BY b.cost_per_unit
        ) AS cost_rank,
        PERCENT_RANK() OVER (
            PARTITION BY b.category_focus, b.fy_label
            ORDER BY COALESCE(b.gross_margin, 0)
        ) AS margin_rank,
        CASE
            WHEN b.defect_rate / 0.05 > 1 THEN 0.0
            ELSE 1.0 - (b.defect_rate / 0.05)
        END AS quality
    FROM base b
    JOIN medians m
        ON m.category_focus = b.category_focus
       AND m.fy_label = b.fy_label
)
SELECT
    supplier_id,
    supplier_name,
    category_focus,
    tier,
    cohort,
    state,
    city,
    payment_terms_days,
    fy_label,
    spend,
    revenue,
    gross_profit,
    gross_margin,
    cost_per_unit,
    cost_index,
    otd,
    fill_rate,
    defect_rate,
    lead_time,
    100.0 * (
        0.30 * (1.0 - cost_rank)
        + 0.25 * otd
        + 0.20 * fill_rate
        + 0.15 * quality
        + 0.10 * margin_rank
    ) AS supplier_score
FROM ranked
ORDER BY fy_label, spend DESC;

-- @name brand_margin
SELECT
    category,
    brand_type,
    fy_label,
    SUM(recognized_revenue) AS revenue,
    SUM(gross_profit) AS gross_profit,
    SUM(gross_profit) * 1.0 / NULLIF(SUM(recognized_revenue), 0) AS gross_margin
FROM vw_sales
GROUP BY category, brand_type, fy_label;

-- @name cohort
SELECT
    cohort,
    SUM(purchase_value) AS spend,
    SUM(on_time_flag) * 1.0 / COUNT(*) AS otd,
    SUM(qty_defective) * 1.0 / SUM(qty_received) AS defect_rate,
    SUM(qty_received) * 1.0 / SUM(qty_ordered) AS fill_rate
FROM vw_purchases
GROUP BY cohort;

-- @name region_margin
SELECT
    region_group,
    SUM(recognized_revenue) AS revenue,
    SUM(gross_profit) * 1.0 / SUM(recognized_revenue) AS gross_margin,
    SUM(contribution_profit) * 1.0 / SUM(recognized_revenue) AS contribution_margin,
    SUM(freight_cost) * 1.0 / SUM(net_qty) AS freight_per_unit
FROM vw_sales
GROUP BY region_group;

-- @name single_source
WITH src AS (
    SELECT
        product_id,
        category,
        product_name,
        sku,
        COUNT(DISTINCT supplier_id) AS supplier_count,
        SUM(purchase_value) AS spend
    FROM vw_purchases
    GROUP BY product_id, category, product_name, sku
),
cat AS (
    SELECT category, SUM(spend) AS category_spend
    FROM src
    GROUP BY category
),
winner AS (
    SELECT product_id, supplier_name
    FROM (
        SELECT
            product_id,
            supplier_name,
            ROW_NUMBER() OVER (
                PARTITION BY product_id
                ORDER BY SUM(purchase_value) DESC
            ) AS rn
        FROM vw_purchases
        GROUP BY product_id, supplier_name
    )
    WHERE rn = 1
)
SELECT
    src.sku,
    src.product_name,
    src.category,
    winner.supplier_name,
    src.spend,
    src.spend * 1.0 / cat.category_spend AS category_spend_share
FROM src
JOIN cat ON cat.category = src.category
JOIN winner ON winner.product_id = src.product_id
WHERE src.supplier_count = 1
ORDER BY src.spend DESC;

-- @name sku_leaders
SELECT
    sku,
    product_name,
    category,
    brand_type,
    SUM(recognized_revenue) AS revenue,
    SUM(gross_profit) * 1.0 / SUM(recognized_revenue) AS gross_margin,
    SUM(net_qty) AS net_qty
FROM vw_sales
GROUP BY sku, product_name, category, brand_type
ORDER BY revenue DESC
LIMIT 15;
