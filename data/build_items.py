"""
Defines the 50 ground-truth (question, sql) pairs for the bake-off,
validates every query actually runs against db/data.db, and writes
data/items.jsonl.

Usage:
    python data/build_items.py
"""
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "..", "db", "data.db")
OUT_PATH = os.path.join(HERE, "items.jsonl")

# Each item: id, question (NL), sql (ground truth), difficulty
# difficulty in {easy, medium, hard} roughly maps to:
#   easy   -> single table, simple filter/select
#   medium -> aggregation or single join
#   hard   -> multi-join, group by + having, subquery

ITEMS = [
    # ---- easy (1-15): single table ----
    ("How many customers are there in total?",
     "SELECT COUNT(*) FROM customers;", "easy"),
    ("List the names of all customers from Sfax.",
     "SELECT name FROM customers WHERE city = 'Sfax';", "easy"),
    ("What is the price of the 'Standing Desk'?",
     "SELECT price FROM products WHERE name = 'Standing Desk';", "easy"),
    ("How many products are in the 'Electronics' category?",
     "SELECT COUNT(*) FROM products WHERE category = 'Electronics';", "easy"),
    ("List all distinct product categories.",
     "SELECT DISTINCT category FROM products;", "easy"),
    ("How many orders have the status 'cancelled'?",
     "SELECT COUNT(*) FROM orders WHERE status = 'cancelled';", "easy"),
    ("What is the most expensive product?",
     "SELECT name FROM products ORDER BY price DESC LIMIT 1;", "easy"),
    ("What is the cheapest product in the 'Office' category?",
     "SELECT name FROM products WHERE category = 'Office' ORDER BY price ASC LIMIT 1;", "easy"),
    ("List customer names who signed up before 2025-01-01.",
     "SELECT name FROM customers WHERE signup_date < '2025-01-01';", "easy"),
    ("How many customers are from France?",
     "SELECT COUNT(*) FROM customers WHERE country = 'France';", "easy"),
    ("What are the names of products priced under 15?",
     "SELECT name FROM products WHERE price < 15;", "easy"),
    ("How many orders were placed in total?",
     "SELECT COUNT(*) FROM orders;", "easy"),
    ("List the distinct order statuses that exist.",
     "SELECT DISTINCT status FROM orders;", "easy"),
    ("What is the average price of all products, rounded to 2 decimals?",
     "SELECT ROUND(AVG(price), 2) FROM products;", "easy"),
    ("List product names in the 'Sportswear' category ordered by price ascending.",
     "SELECT name FROM products WHERE category = 'Sportswear' ORDER BY price ASC;", "easy"),

    # ---- medium (16-32): aggregation or single join ----
    ("How many orders does each status have? Show status and the count.",
     "SELECT status, COUNT(*) AS n FROM orders GROUP BY status;", "medium"),
    ("What is the total price of all products in each category?",
     "SELECT category, ROUND(SUM(price), 2) AS total FROM products GROUP BY category;", "medium"),
    ("How many products does each category have?",
     "SELECT category, COUNT(*) AS n FROM products GROUP BY category;", "medium"),
    ("List the name of each customer along with the city they live in, for customers in Tunis.",
     "SELECT name, city FROM customers WHERE city = 'Tunis';", "medium"),
    ("For each order, show the order_id and how many line items it has.",
     "SELECT order_id, COUNT(*) AS n_items FROM order_items GROUP BY order_id;", "medium"),
    ("What is the total quantity sold for each product_id?",
     "SELECT product_id, SUM(quantity) AS total_qty FROM order_items GROUP BY product_id;", "medium"),
    ("List the order_id and order_date for orders placed by the customer named exactly 'Amine Trabelsi', if any exist.",
     "SELECT o.order_id, o.order_date FROM orders o JOIN customers c ON o.customer_id = c.customer_id WHERE c.name = 'Amine Trabelsi';", "medium"),
    ("Show the product name for every item in order number 1.",
     "SELECT p.name FROM order_items oi JOIN products p ON oi.product_id = p.product_id WHERE oi.order_id = 1;", "medium"),
    ("How many customers are there per country?",
     "SELECT country, COUNT(*) AS n FROM customers GROUP BY country;", "medium"),
    ("What is the highest unit_price ever recorded in order_items?",
     "SELECT MAX(unit_price) FROM order_items;", "medium"),
    ("List the order_id of every order that has more than 3 line items.",
     "SELECT order_id FROM order_items GROUP BY order_id HAVING COUNT(*) > 3;", "medium"),
    ("For each order, compute its total value (sum of quantity * unit_price). Show order_id and total.",
     "SELECT order_id, ROUND(SUM(quantity * unit_price), 2) AS total FROM order_items GROUP BY order_id;", "medium"),
    ("How many distinct customers have placed at least one order?",
     "SELECT COUNT(DISTINCT customer_id) FROM orders;", "medium"),
    ("List the city and the number of customers in that city, only for cities with more than 3 customers.",
     "SELECT city, COUNT(*) AS n FROM customers GROUP BY city HAVING COUNT(*) > 3;", "medium"),
    ("What is the average quantity per line item across all order_items?",
     "SELECT ROUND(AVG(quantity), 2) FROM order_items;", "medium"),
    ("Show the order_date and status for every order placed by customer_id 5.",
     "SELECT order_date, status FROM orders WHERE customer_id = 5;", "medium"),
    ("How many orders were placed in the year 2026?",
     "SELECT COUNT(*) FROM orders WHERE order_date >= '2026-01-01' AND order_date < '2027-01-01';", "medium"),

    # ---- hard (33-50): multi-join, group by + having, subqueries ----
    ("List the names of customers who have never placed an order.",
     "SELECT name FROM customers WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders);", "hard"),
    ("What is the name of the customer who has placed the most orders?",
     "SELECT c.name FROM customers c JOIN orders o ON c.customer_id = o.customer_id "
     "GROUP BY c.customer_id ORDER BY COUNT(*) DESC LIMIT 1;", "hard"),
    ("List the top 3 products by total quantity sold, showing product name and total quantity.",
     "SELECT p.name, SUM(oi.quantity) AS total_qty FROM order_items oi "
     "JOIN products p ON oi.product_id = p.product_id "
     "GROUP BY p.product_id ORDER BY total_qty DESC LIMIT 3;", "hard"),
    ("For each customer, show their name and the total amount they've spent across all their orders (quantity * unit_price), ordered from highest spender to lowest.",
     "SELECT c.name, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_spent "
     "FROM customers c JOIN orders o ON c.customer_id = o.customer_id "
     "JOIN order_items oi ON o.order_id = oi.order_id "
     "GROUP BY c.customer_id ORDER BY total_spent DESC;", "hard"),
    ("Which product category generates the highest total revenue (quantity * unit_price)?",
     "SELECT p.category, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue "
     "FROM order_items oi JOIN products p ON oi.product_id = p.product_id "
     "GROUP BY p.category ORDER BY revenue DESC LIMIT 1;", "hard"),
    ("List customers who have spent more than 300 in total across all their orders. Show name and total spent.",
     "SELECT c.name, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_spent "
     "FROM customers c JOIN orders o ON c.customer_id = o.customer_id "
     "JOIN order_items oi ON o.order_id = oi.order_id "
     "GROUP BY c.customer_id HAVING total_spent > 300;", "hard"),
    ("What is the name of the product that has never been ordered?",
     "SELECT name FROM products WHERE product_id NOT IN (SELECT DISTINCT product_id FROM order_items);", "hard"),
    ("For each country, show the total revenue generated by customers from that country.",
     "SELECT c.country, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue "
     "FROM customers c JOIN orders o ON c.customer_id = o.customer_id "
     "JOIN order_items oi ON o.order_id = oi.order_id "
     "GROUP BY c.country ORDER BY revenue DESC;", "hard"),
    ("List the order_id of orders whose total value (quantity * unit_price) exceeds the average order value across all orders.",
     "SELECT order_id FROM ("
     "  SELECT order_id, SUM(quantity * unit_price) AS total FROM order_items GROUP BY order_id"
     ") sub WHERE total > (SELECT AVG(total) FROM ("
     "  SELECT SUM(quantity * unit_price) AS total FROM order_items GROUP BY order_id"
     "));", "hard"),
    ("What is the name of the customer with the earliest signup_date?",
     "SELECT name FROM customers ORDER BY signup_date ASC LIMIT 1;", "hard"),
    ("For each product, show its name and how many distinct orders it appeared in, only for products that appeared in more than 15 orders.",
     "SELECT p.name, COUNT(DISTINCT oi.order_id) AS n_orders "
     "FROM order_items oi JOIN products p ON oi.product_id = p.product_id "
     "GROUP BY p.product_id HAVING n_orders > 15;", "hard"),
    ("List the 2 most recent orders (by order_date) that are still in 'placed' status, showing order_id and order_date.",
     "SELECT order_id, order_date FROM orders WHERE status = 'placed' ORDER BY order_date DESC LIMIT 2;", "hard"),
    ("What is the average order value (quantity * unit_price summed per order), rounded to 2 decimals?",
     "SELECT ROUND(AVG(total), 2) FROM (SELECT SUM(quantity * unit_price) AS total FROM order_items GROUP BY order_id);", "hard"),
    ("List customers who have placed orders in both 'delivered' and 'cancelled' status. Show the customer name.",
     "SELECT c.name FROM customers c "
     "WHERE c.customer_id IN (SELECT customer_id FROM orders WHERE status = 'delivered') "
     "AND c.customer_id IN (SELECT customer_id FROM orders WHERE status = 'cancelled');", "hard"),
    ("For each customer who has placed at least 5 orders, show their name and order count.",
     "SELECT c.name, COUNT(*) AS n_orders FROM customers c JOIN orders o ON c.customer_id = o.customer_id "
     "GROUP BY c.customer_id HAVING n_orders >= 5;", "hard"),
    ("What is the second most expensive product overall?",
     "SELECT name FROM products ORDER BY price DESC LIMIT 1 OFFSET 1;", "hard"),
    ("Show the category with the fewest total units sold (SUM of quantity), including categories with zero if any.",
     "SELECT p.category, COALESCE(SUM(oi.quantity), 0) AS total_qty "
     "FROM products p LEFT JOIN order_items oi ON p.product_id = oi.product_id "
     "GROUP BY p.category ORDER BY total_qty ASC LIMIT 1;", "hard"),
    ("List the name and total spent of the single customer who has spent the most overall.",
     "SELECT c.name, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_spent "
     "FROM customers c JOIN orders o ON c.customer_id = o.customer_id "
     "JOIN order_items oi ON o.order_id = oi.order_id "
     "GROUP BY c.customer_id ORDER BY total_spent DESC LIMIT 1;", "hard"),
]


def validate_and_write():
    assert len(ITEMS) >= 50, f"Need at least 50 items, have {len(ITEMS)}"
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    rows = []
    for i, (question, sql, difficulty) in enumerate(ITEMS, start=1):
        try:
            cur.execute(sql)
            result = cur.fetchall()
        except sqlite3.Error as e:
            raise RuntimeError(f"Item {i} SQL failed: {sql}\n  -> {e}")
        rows.append({
            "id": i,
            "question": question,
            "gold_sql": sql,
            "difficulty": difficulty,
            "n_gold_rows": len(result),
        })

    conn.close()

    with open(OUT_PATH, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    print(f"Wrote {len(rows)} items to {OUT_PATH}")
    empty = [r["id"] for r in rows if r["n_gold_rows"] == 0]
    if empty:
        print(f"WARNING: {len(empty)} items return 0 rows on gold SQL: {empty}")
    diffs = {}
    for r in rows:
        diffs[r["difficulty"]] = diffs.get(r["difficulty"], 0) + 1
    print("Difficulty breakdown:", diffs)


if __name__ == "__main__":
    validate_and_write()
