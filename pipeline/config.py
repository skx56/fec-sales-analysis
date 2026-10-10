"""Paths, category economics, and the supplier master used by the generator."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
WAREHOUSE = DATA / "warehouse"
DB_PATH = WAREHOUSE / "sales.sqlite"
POWERBI_DIR = DATA / "powerbi"
OUTPUT = ROOT / "output"
DASHBOARD_PATH = ROOT / "dashboard" / "index.html"
SQL_DIR = ROOT / "sql"
PBIP_DIR = ROOT / "powerbi"

SEED = 42
DATE_START = "2023-04-01"
DATE_END = "2025-09-30"

# Operating model for the month-end close this pipeline replaces.
# Manual: collect monthly ERP extracts, fix supplier names, rebuild pivots, paste into the pack.
# Automated: run the pipeline and review the exception list.
MANUAL_CLOSE_MINUTES = 300
AUTOMATED_REVIEW_MINUTES = 60

# name, city, state
SUPPLIERS: dict[str, list[tuple[str, str, str]]] = {
    "Tea": [
        ("Brahmaputra Leaf Co", "Dibrugarh", "Assam"),
        ("Kaziranga Tea Estate", "Golaghat", "Assam"),
        ("Jorhat Gold Leaf", "Jorhat", "Assam"),
        ("Dibrugarh Highlands Tea", "Dibrugarh", "Assam"),
        ("Tezpur Garden Packers", "Tezpur", "Assam"),
        ("Majuli River Tea", "Majuli", "Assam"),
        ("Sivasagar Orthodox Traders", "Sivasagar", "Assam"),
        ("Numaligarh Tea House", "Numaligarh", "Assam"),
        ("Tinsukia Second Flush", "Tinsukia", "Assam"),
        ("Sonari Valley Tea", "Sonari", "Assam"),
        ("Golaghat Leaf Co", "Golaghat", "Assam"),
        ("Bokakhat Garden Supplies", "Bokakhat", "Assam"),
        ("North Bank Tea Co", "Lakhimpur", "Assam"),
        ("Naharkatia Packers", "Naharkatia", "Assam"),
        ("Digboi Hills Tea", "Digboi", "Assam"),
        ("Margherita CTC House", "Margherita", "Assam"),
        ("Moran Small Growers", "Moran", "Assam"),
        ("Amguri Tea Works", "Amguri", "Assam"),
    ],
    "Edible Oils": [
        ("Kamrup Agro Foods", "Guwahati", "Assam"),
        ("Barak Valley Refinery", "Silchar", "Assam"),
        ("Noonmati Oil Mills", "Guwahati", "Assam"),
        ("Saurashtra Seed Oil", "Rajkot", "Gujarat"),
        ("Nagaon Mustard Mill", "Nagaon", "Assam"),
        ("Goalpara Oil Traders", "Goalpara", "Assam"),
        ("Bongaigaon Refiners", "Bongaigaon", "Assam"),
        ("Silchar Edible Oils", "Silchar", "Assam"),
        ("Dhubri Oil Depot", "Dhubri", "Assam"),
        ("Fancy Bazar Oils", "Guwahati", "Assam"),
        ("Athgaon Vanaspati", "Guwahati", "Assam"),
        ("Rajkot Groundnut Co", "Rajkot", "Gujarat"),
    ],
    "Staples": [
        ("Dispur Grain Merchants", "Guwahati", "Assam"),
        ("Maligaon Rice Mills", "Guwahati", "Assam"),
        ("Barpeta Atta Works", "Barpeta", "Assam"),
        ("Mangaldoi Dal House", "Mangaldoi", "Assam"),
        ("Rangia Staple Supply", "Rangia", "Assam"),
        ("Nalbari Farm Produce", "Nalbari", "Assam"),
        ("Siliguri Grain Link", "Siliguri", "West Bengal"),
        ("Dhekiajuli Rice Co", "Dhekiajuli", "Assam"),
        ("Morigaon Atta Mill", "Morigaon", "Assam"),
        ("Kokrajhar Grain Co", "Kokrajhar", "Assam"),
        ("Biswanath Paddy House", "Biswanath", "Assam"),
        ("Lakhimpur Staples", "Lakhimpur", "Assam"),
        ("Hojai Pulse Traders", "Hojai", "Assam"),
        ("Bilasipara Rice Depot", "Bilasipara", "Assam"),
    ],
    "Spices": [
        ("Barak Spice Collective", "Silchar", "Assam"),
        ("Fancy Bazar Masala", "Guwahati", "Assam"),
        ("Shillong Hill Spices", "Shillong", "Meghalaya"),
        ("Imphal Chilli House", "Imphal", "Manipur"),
        ("Silchar Ginger Co", "Silchar", "Assam"),
        ("Tezpur Pepper Traders", "Tezpur", "Assam"),
        ("Guwahati Haldi Mills", "Guwahati", "Assam"),
        ("Agartala Spice Route", "Agartala", "Tripura"),
        ("Kohima Dry Ginger", "Kohima", "Nagaland"),
        ("Panbazar Grinders", "Guwahati", "Assam"),
        ("Diphu Hill Masala", "Diphu", "Assam"),
        ("Aizawl Leaf Spice", "Aizawl", "Mizoram"),
    ],
    "Snacks": [
        ("Nilachal Snacks", "Guwahati", "Assam"),
        ("Umananda Foods", "Guwahati", "Assam"),
        ("Deepor Bites", "Guwahati", "Assam"),
        ("Chandubi Namkeen", "Chandubi", "Assam"),
        ("Palashbari Snacks", "Palashbari", "Assam"),
        ("Mirza Crunch Works", "Mirza", "Assam"),
        ("Chaygaon Savouries", "Chaygaon", "Assam"),
        ("Basistha Foods", "Guwahati", "Assam"),
        ("Sonapur Namkeen", "Sonapur", "Assam"),
        ("Rangiya Snack Co", "Rangiya", "Assam"),
        ("Jagiroad Bakers", "Jagiroad", "Assam"),
        ("Khanapara Munch", "Guwahati", "Assam"),
        ("Azara Private Label Kitchen", "Azara", "Assam"),
        ("Beltola Bite Co", "Guwahati", "Assam"),
    ],
    "Beverages": [
        ("Brahmaputra Beverages", "Guwahati", "Assam"),
        ("Kaziranga Drinks", "Golaghat", "Assam"),
        ("Jorhat Juice Works", "Jorhat", "Assam"),
        ("Guwahati Soda Co", "Guwahati", "Assam"),
        ("Siliguri Beverage Hub", "Siliguri", "West Bengal"),
        ("Shillong Spring Drinks", "Shillong", "Meghalaya"),
        ("Tezpur Nectar", "Tezpur", "Assam"),
        ("Dibrugarh Cold Drinks", "Dibrugarh", "Assam"),
        ("Nagaon Juice Traders", "Nagaon", "Assam"),
        ("Goalpara Beverages", "Goalpara", "Assam"),
        ("Tinsukia Refreshments", "Tinsukia", "Assam"),
        ("Dispur Drink House", "Guwahati", "Assam"),
    ],
    "Personal Care": [
        ("Kamakhya Personal Care", "Guwahati", "Assam"),
        ("Nilachal Care", "Guwahati", "Assam"),
        ("Kolkata Care Labs", "Kolkata", "West Bengal"),
        ("Guwahati Hygiene Co", "Guwahati", "Assam"),
        ("Silchar Care Products", "Silchar", "Assam"),
        ("Shillong Glow House", "Shillong", "Meghalaya"),
        ("Imphal Care Works", "Imphal", "Manipur"),
        ("Jorhat Hygiene", "Jorhat", "Assam"),
        ("Tezpur Care Traders", "Tezpur", "Assam"),
        ("Agartala Personal Care", "Agartala", "Tripura"),
    ],
    "Home Care": [
        ("Kapili Clean Co", "Guwahati", "Assam"),
        ("Basistha Home Products", "Guwahati", "Assam"),
        ("Maligaon Detergent Works", "Guwahati", "Assam"),
        ("Noonmati Home Care", "Guwahati", "Assam"),
        ("Siliguri Clean Hub", "Siliguri", "West Bengal"),
        ("Nalbari Wash Co", "Nalbari", "Assam"),
        ("Barpeta Home Care", "Barpeta", "Assam"),
        ("Mangaldoi Cleaners", "Mangaldoi", "Assam"),
        ("Luit Home Care", "Guwahati", "Assam"),
        ("Dibrugarh Home Products", "Dibrugarh", "Assam"),
    ],
    "Dairy": [
        ("Khanapara Dairy", "Guwahati", "Assam"),
        ("Rani Dairy Cooperative", "Rani", "Assam"),
        ("Mirza Milk Supply", "Mirza", "Assam"),
        ("Changsari Dairy", "Changsari", "Assam"),
        ("Jagiroad Milk Products", "Jagiroad", "Assam"),
        ("Rangia Dairy House", "Rangia", "Assam"),
        ("Nagaon Milk Traders", "Nagaon", "Assam"),
        ("Bokakhat Dairy", "Bokakhat", "Assam"),
    ],
    "Packaging": [
        ("Amingaon Cartons", "Amingaon", "Assam"),
        ("Changsari Polyfilms", "Changsari", "Assam"),
        ("Lokhra Pack Co", "Guwahati", "Assam"),
        ("Pamohi Packaging", "Guwahati", "Assam"),
        ("Boragaon Packs", "Guwahati", "Assam"),
        ("Luit Packaging Works", "Guwahati", "Assam"),
        ("Sarusajai Carton Co", "Guwahati", "Assam"),
        ("Beltola Flexible Pack", "Guwahati", "Assam"),
        ("Azara Corrugators", "Azara", "Assam"),
        ("Khanapara Wraps", "Guwahati", "Assam"),
    ],
}

# Onboarded from 2024. Cheaper quotes, weaker quality, except Azara which runs a tighter plant.
NEW_ONBOARD: dict[str, str] = {
    "Moran Small Growers": "2024-06-01",
    "Amguri Tea Works": "2024-02-01",
    "Athgaon Vanaspati": "2024-08-01",
    "Rajkot Groundnut Co": "2024-03-01",
    "Hojai Pulse Traders": "2024-01-15",
    "Bilasipara Rice Depot": "2024-05-01",
    "Diphu Hill Masala": "2024-07-01",
    "Aizawl Leaf Spice": "2024-04-01",
    "Azara Private Label Kitchen": "2024-02-01",
    "Beltola Bite Co": "2024-09-01",
    "Tinsukia Refreshments": "2024-03-01",
    "Dispur Drink House": "2024-11-01",
    "Agartala Personal Care": "2024-04-01",
    "Dibrugarh Home Products": "2024-06-01",
    "Bokakhat Dairy": "2024-01-20",
    "Khanapara Wraps": "2024-05-01",
}

# annual_rev is the planning target in rupees, before mix, discount, and growth.
CATEGORIES: dict[str, dict] = {
    "Tea": {
        "prefix": "TEA",
        "n_sku": 16,
        "cost": 240.0,
        "price": 340.0,
        "annual_rev": 10.0e7,
        "season": "festive",
        "uom": "kg",
    },
    "Edible Oils": {
        "prefix": "OIL",
        "n_sku": 14,
        "cost": 142.0,
        "price": 171.0,
        "annual_rev": 14.0e7,
        "season": "mild",
        "uom": "L",
    },
    "Staples": {
        "prefix": "STP",
        "n_sku": 18,
        "cost": 48.0,
        "price": 58.0,
        "annual_rev": 18.0e7,
        "season": "flat",
        "uom": "kg",
    },
    "Spices": {
        "prefix": "SPC",
        "n_sku": 16,
        "cost": 260.0,
        "price": 390.0,
        "annual_rev": 4.0e7,
        "season": "festive",
        "uom": "kg",
    },
    "Snacks": {
        "prefix": "SNK",
        "n_sku": 20,
        "cost": 36.0,
        "price": 54.0,
        "annual_rev": 8.0e7,
        "season": "festive",
        "uom": "kg",
    },
    "Beverages": {
        "prefix": "BEV",
        "n_sku": 14,
        "cost": 28.0,
        "price": 44.0,
        "annual_rev": 6.0e7,
        "season": "summer",
        "uom": "L",
    },
    "Personal Care": {
        "prefix": "PCE",
        "n_sku": 14,
        "cost": 95.0,
        "price": 142.0,
        "annual_rev": 5.0e7,
        "season": "festive",
        "uom": "L",
    },
    "Home Care": {
        "prefix": "HMC",
        "n_sku": 12,
        "cost": 62.0,
        "price": 92.0,
        "annual_rev": 3.0e7,
        "season": "mild",
        "uom": "L",
    },
    "Dairy": {
        "prefix": "DRY",
        "n_sku": 10,
        "cost": 58.0,
        "price": 74.0,
        "annual_rev": 4.0e7,
        "season": "summer",
        "uom": "kg",
    },
    "Packaging": {
        "prefix": "PKG",
        "n_sku": 12,
        "cost": 15.0,
        "price": 21.0,
        "annual_rev": 3.0e7,
        "season": "flat",
        "uom": "unit",
    },
}

STEMS: dict[str, list[str]] = {
    "Tea": [
        "Assam CTC Dust",
        "Orthodox Gold",
        "Second Flush Leaf",
        "Gold Blend",
        "Premium Dust",
        "Green Assam",
        "Masala Premix",
        "Broken Orange Pekoe",
    ],
    "Edible Oils": [
        "Mustard Oil",
        "Refined Soybean",
        "Sunflower Oil",
        "Rice Bran Oil",
        "Groundnut Oil",
        "Vanaspati",
        "Blended Veg Oil",
    ],
    "Staples": [
        "Parboiled Rice",
        "Raw Rice",
        "Atta",
        "Maida",
        "Masoor Dal",
        "Moong Dal",
        "Toor Dal",
        "Poha",
        "Suji",
    ],
    "Spices": [
        "Turmeric Powder",
        "Red Chilli",
        "Cumin",
        "Coriander",
        "Ginger Powder",
        "Black Pepper",
        "Garam Masala",
        "Mustard Seed",
    ],
    "Snacks": [
        "Bhujia",
        "Mixture",
        "Potato Chips",
        "Roasted Chana",
        "Cookies",
        "Puffs",
        "Sev",
        "Namkeen Combo",
        "Protein Puffs",
        "Baked Mathri",
    ],
    "Beverages": [
        "Mango Drink",
        "Litchi Drink",
        "Orange Squash",
        "Packaged Water",
        "Iced Tea",
        "Jeera Soda",
        "Glucose Drink",
    ],
    "Personal Care": [
        "Bathing Soap",
        "Shampoo",
        "Hair Oil",
        "Toothpaste",
        "Face Wash",
        "Hand Wash",
        "Talcum",
    ],
    "Home Care": [
        "Detergent Powder",
        "Dishwash Liquid",
        "Floor Cleaner",
        "Toilet Cleaner",
        "Glass Cleaner",
        "Fabric Softener",
    ],
    "Dairy": [
        "Toned Milk",
        "Curd",
        "Paneer",
        "Ghee",
        "Butter",
    ],
    "Packaging": [
        "Corrugated Carton",
        "LDPE Pouch Roll",
        "PET Jar",
        "Shrink Film",
        "BOPP Tape",
        "Mono Carton",
    ],
}

PACKS: dict[str, list[str]] = {
    "Tea": ["250 g", "500 g", "1 kg"],
    "Edible Oils": ["1 L", "5 L", "15 L"],
    "Staples": ["1 kg", "5 kg", "10 kg", "25 kg"],
    "Spices": ["100 g", "200 g", "500 g"],
    "Snacks": ["40 g", "150 g", "400 g"],
    "Beverages": ["250 ml", "750 ml", "2 L"],
    "Personal Care": ["75 ml", "200 ml", "500 ml"],
    "Home Care": ["500 ml", "1 L", "2 L"],
    "Dairy": ["200 g", "500 g", "1 kg"],
    "Packaging": ["unit", "100-pack", "500-pack"],
}

PRIVATE_LABEL_CATEGORIES = {"Snacks", "Staples", "Home Care"}

CHANNEL_DISCOUNT = {
    "General Trade": 0.03,
    "Modern Trade": 0.09,
    "HoReCa": 0.05,
    "Institutional": 0.11,
}

FREIGHT_PER_UNIT = {
    "Assam Valley": 1.10,
    "Hill Northeast": 3.60,
    "West Bengal": 2.10,
}

FESTIVE_CATEGORIES = {"Tea", "Snacks", "Personal Care", "Spices"}

CUSTOMER_MARKETS: list[tuple[str, str, list[str]]] = [
    ("Assam", "Assam Valley", ["Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Tezpur", "Nagaon", "Tinsukia"]),
    ("Meghalaya", "Hill Northeast", ["Shillong", "Tura"]),
    ("Manipur", "Hill Northeast", ["Imphal"]),
    ("Nagaland", "Hill Northeast", ["Dimapur", "Kohima"]),
    ("Tripura", "Hill Northeast", ["Agartala"]),
    ("Mizoram", "Hill Northeast", ["Aizawl"]),
    ("Arunachal Pradesh", "Hill Northeast", ["Itanagar"]),
    ("West Bengal", "West Bengal", ["Siliguri", "Alipurduar"]),
]

INSTITUTIONAL = [
    ("Campus Hospitality Services", "Guwahati", "Assam", "Assam Valley"),
    ("Guwahati Medical Stores", "Guwahati", "Assam", "Assam Valley"),
    ("Assam Secretariat Canteen", "Guwahati", "Assam", "Assam Valley"),
    ("Siliguri Institutional Supply", "Siliguri", "West Bengal", "West Bengal"),
]

KPI_DEFINITIONS: list[dict[str, str]] = [
    {"name": "Recognized revenue", "formula": "Net quantity × net selling price, after returns."},
    {"name": "COGS", "formula": "Net quantity × unit purchase cost of the supplying lot."},
    {"name": "Gross profit", "formula": "Recognized revenue − COGS."},
    {"name": "Gross margin", "formula": "Gross profit / recognized revenue."},
    {"name": "Contribution profit", "formula": "Gross profit − outbound freight."},
    {"name": "Contribution margin", "formula": "Contribution profit / recognized revenue."},
    {"name": "Average selling price", "formula": "Recognized revenue / net quantity. Compare inside a category."},
    {"name": "Purchase cost per unit", "formula": "Purchase value / quantity received. Compare inside a category."},
    {"name": "Unit margin", "formula": "Average selling price − unit cost, inside one category."},
    {"name": "Discount rate", "formula": "Discount amount / list revenue."},
    {"name": "Price realization", "formula": "Recognized revenue / list revenue."},
    {"name": "Freight per unit", "formula": "Outbound freight / net quantity."},
    {"name": "Return rate", "formula": "Returned quantity / quantity invoiced."},
    {"name": "On-time delivery", "formula": "Purchase lines received within the contracted lead time / purchase lines."},
    {"name": "Fill rate", "formula": "Quantity received / quantity ordered."},
    {"name": "Defect rate", "formula": "Quantity rejected / quantity received."},
    {"name": "Average lead time", "formula": "Mean actual days from PO to receipt."},
    {"name": "Top-10 spend share", "formula": "Purchase value of the ten largest suppliers / total purchase value."},
    {"name": "Supplier HHI", "formula": "Sum of squared supplier spend shares. Higher means a more concentrated book."},
    {"name": "Single-source SKU share", "formula": "SKUs bought from only one supplier / SKUs purchased."},
    {"name": "Weighted days payable", "formula": "Spend-weighted contractual payment terms."},
    {"name": "Purchase price variance", "formula": "(Actual purchase value − standard cost × qty) / standard value."},
    {"name": "Revenue growth", "formula": "FY25 recognized revenue / FY24 recognized revenue − 1."},
    {"name": "Gross margin change", "formula": "FY25 gross margin − FY24 gross margin, in basis points."},
    {"name": "Supplier cost index", "formula": "Laspeyres index of category unit costs. Apr–Jun 2023 = 100."},
    {"name": "Private-label margin gap", "formula": "Private-label gross margin − branded gross margin, in basis points."},
    {
        "name": "Supplier score",
        "formula": "100 × (30% cost position + 25% on-time + 20% fill + 15% quality + 10% margin position), scored against category peers.",
    },
]
