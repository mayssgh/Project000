-- Bake-Off schema: small e-commerce store
-- Deliberately has enough breadth (4 tables, FKs, dates, categories, prices)
-- to support simple selects, aggregations, joins, group-by/having, and subqueries.

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    city         TEXT NOT NULL,
    country      TEXT NOT NULL,
    signup_date  TEXT NOT NULL      -- ISO date 'YYYY-MM-DD'
);

CREATE TABLE products (
    product_id   INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    category     TEXT NOT NULL,
    price        REAL NOT NULL      -- unit list price
);

CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date   TEXT NOT NULL,     -- ISO date 'YYYY-MM-DD'
    status       TEXT NOT NULL      -- 'placed' | 'shipped' | 'delivered' | 'cancelled'
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    quantity      INTEGER NOT NULL,
    unit_price    REAL NOT NULL     -- price at time of order (may differ from products.price)
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_items_order ON order_items(order_id);
CREATE INDEX idx_items_product ON order_items(product_id);
