-- Drop in dependency-safe order (CASCADE keeps this simple)
DROP TABLE IF EXISTS items     CASCADE;
DROP TABLE IF EXISTS orders    CASCADE;
DROP TABLE IF EXISTS products  CASCADE;
DROP TABLE IF EXISTS sellers   CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS categories CASCADE;

-- === Dimension: categories ===
-- Matches transform_categories:
--   category_id (surrogate), product_category_name_english, product_category_name_italian
CREATE TABLE categories (
  category_id INTEGER PRIMARY KEY,
  product_category_name_english  TEXT UNIQUE,
  product_category_name_italian  TEXT
);

-- === Dimension: customers ===
-- Matches transform_customers:
--   customer_id, region, city, cap (5 chars, no extra constraints per your "no DQ checks now")
CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY,
  region      TEXT,
  city        TEXT,
  cap         CHAR(5)
);

-- === Dimension: sellers ===
-- Matches transform_sellers:
--   seller_id, region
CREATE TABLE sellers (
  seller_id TEXT PRIMARY KEY,
  region    TEXT
);

-- === Dimension: products ===
-- Matches transform_products:
--   product_id, product_name_length, product_description_length, product_photos_qty
--   EITHER category_id (when mapped) OR raw category text when mapping isn't available.
CREATE TABLE products (
  product_id                   TEXT PRIMARY KEY,
  category_id                  INTEGER NULL,
  category                     TEXT NULL,
  product_name_length          SMALLINT,
  product_description_length   SMALLINT,
  product_photos_qty           SMALLINT,
  CONSTRAINT fk_products_category_id
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

-- === Fact: orders ===
-- Matches transform_orders:
--   order_id, customer_id, order_status, order_purchase_timestamp,
--   order_delivered_customer_date, order_estimated_delivery_date
CREATE TABLE orders (
  order_id                      TEXT PRIMARY KEY,
  customer_id                   TEXT NOT NULL,
  order_status                  TEXT,
  order_purchase_timestamp      TIMESTAMP WITHOUT TIME ZONE,
  order_delivered_customer_date TIMESTAMP WITHOUT TIME ZONE,
  order_estimated_delivery_date DATE,
  CONSTRAINT fk_orders_customer
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- === Fact: items ===
-- Matches transform_items:
--   item_id (composite key as string), order_id, order_item, product_id, seller_id,
--   price, freight
CREATE TABLE items (
  item_id    TEXT PRIMARY KEY,
  order_id   TEXT NOT NULL,
  order_item SMALLINT NOT NULL,
  product_id TEXT NOT NULL,
  seller_id  TEXT NOT NULL,
  price      NUMERIC(10,2),
  freight    NUMERIC(10,2),
  CONSTRAINT uq_items_order_item UNIQUE (order_id, order_item),
  CONSTRAINT fk_items_order   FOREIGN KEY (order_id)  REFERENCES orders(order_id),
  CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products(product_id),
  CONSTRAINT fk_items_seller  FOREIGN KEY (seller_id)  REFERENCES sellers(seller_id)
);