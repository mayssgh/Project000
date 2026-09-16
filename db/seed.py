"""
Builds db/data.db from db/schema.sql and fills it with deterministic
synthetic data (fixed random seed => same DB every time, no external
dependencies, works from a clean clone).

Usage:
    python db/seed.py
"""
import random
import sqlite3
import os
from datetime import date, timedelta

random.seed(42)

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(HERE, "schema.sql")
DB_PATH = os.path.join(HERE, "data.db")

FIRST_NAMES = ["Amine", "Yasmine", "Sami", "Rania", "Karim", "Nour", "Mehdi",
               "Salma", "Walid", "Ines", "Hedi", "Emna", "Bilel", "Sarra",
               "Ahmed", "Maryem", "Youssef", "Lina", "Omar", "Farah",
               "Anis", "Dorra", "Nizar", "Wafa", "Rayen"]
LAST_NAMES = ["Ben Ali", "Trabelsi", "Gharbi", "Jendoubi", "Mansour",
              "Cherif", "Bouazizi", "Khelifi", "Sassi", "Jaziri",
              "Ayari", "Rekik", "Fakhfakh", "Hammami", "Zouari"]
CITIES = [("Tunis", "Tunisia"), ("Sfax", "Tunisia"), ("Sousse", "Tunisia"),
          ("Bizerte", "Tunisia"), ("Gabes", "Tunisia"), ("Paris", "France"),
          ("Lyon", "France"), ("Milan", "Italy"), ("Berlin", "Germany"),
          ("Madrid", "Spain")]

PRODUCTS = [
    ("Wireless Mouse", "Electronics", 19.90),
    ("Mechanical Keyboard", "Electronics", 64.50),
    ("USB-C Hub", "Electronics", 29.00),
    ("Noise-Cancelling Headphones", "Electronics", 89.90),
    ("27-inch Monitor", "Electronics", 199.00),
    ("Laptop Stand", "Office", 24.90),
    ("Desk Lamp", "Office", 17.50),
    ("Notebook Set", "Office", 8.90),
    ("Ergonomic Chair", "Office", 149.00),
    ("Standing Desk", "Office", 259.00),
    ("Running Shoes", "Sportswear", 54.90),
    ("Yoga Mat", "Sportswear", 22.00),
    ("Water Bottle", "Sportswear", 11.90),
    ("Gym Bag", "Sportswear", 34.90),
    ("Resistance Bands", "Sportswear", 15.00),
    ("Coffee Grinder", "Home", 39.90),
    ("Ceramic Mug Set", "Home", 14.50),
    ("Air Purifier", "Home", 119.00),
    ("Cast Iron Pan", "Home", 44.00),
    ("Throw Blanket", "Home", 27.90),
]

STATUSES = ["placed", "shipped", "delivered", "cancelled"]
STATUS_WEIGHTS = [0.15, 0.20, 0.55, 0.10]

N_CUSTOMERS = 40
N_ORDERS = 220
START_DATE = date(2025, 1, 1)
END_DATE = date(2026, 9, 1)


def random_date(start: date, end: date) -> str:
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).isoformat()


def build():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())

    # Customers
    customers = []
    for cid in range(1, N_CUSTOMERS + 1):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        city, country = random.choice(CITIES)
        signup = random_date(date(2024, 1, 1), date(2026, 6, 1))
        customers.append((cid, name, city, country, signup))
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?)", customers
    )

    # Products
    products = [(i + 1, *p) for i, p in enumerate(PRODUCTS)]
    conn.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?)", products
    )

    # Orders + order_items
    # Reserve a few customers and products that never get an order, so
    # "which X never had an order" test items have a real (non-empty) answer.
    ORDERING_CUSTOMER_MAX = N_CUSTOMERS - 3   # customers > this id never order
    ORDERING_PRODUCT_MAX = len(PRODUCTS) - 2  # products > this id never sell

    orders = []
    items = []
    item_id = 1
    for oid in range(1, N_ORDERS + 1):
        cust_id = random.randint(1, ORDERING_CUSTOMER_MAX)
        odate = random_date(START_DATE, END_DATE)
        status = random.choices(STATUSES, weights=STATUS_WEIGHTS)[0]
        orders.append((oid, cust_id, odate, status))

        n_items = random.randint(1, 4)
        chosen_products = random.sample(range(1, ORDERING_PRODUCT_MAX + 1), n_items)
        for pid in chosen_products:
            qty = random.randint(1, 3)
            base_price = PRODUCTS[pid - 1][2]
            # small price drift to simulate historical pricing
            unit_price = round(base_price * random.uniform(0.9, 1.05), 2)
            items.append((item_id, oid, pid, qty, unit_price))
            item_id += 1

    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?)", orders
    )
    conn.executemany(
        "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", items
    )

    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH}")
    print(f"  customers:   {len(customers)}")
    print(f"  products:    {len(products)}")
    print(f"  orders:      {len(orders)}")
    print(f"  order_items: {len(items)}")


if __name__ == "__main__":
    build()
