from datetime import datetime
from pathlib import Path
import pandas as pd
from src import raw_path, processed_path


# ___ TRANSFORMATIONS ___

# Transform categories
def transform_categories(df):
    df = df.copy()
    key_cols = ['product_category_name_english', 'product_category_name_italian']
    # Treat missing names as equal for dedup, then restore proper null semantics
    df = (df
          .assign(_key=df[key_cols].fillna('').agg('||'.join, axis=1))
          .drop_duplicates(subset=['_key'])
          .drop(columns=['_key']))
    # Stable order → stable surrogate keys
    df = df.sort_values(key_cols, na_position='last').reset_index(drop=True)
    df['category_id'] = df.index + 1
    # Use pandas nullable string dtype (avoids "nan" strings)
    df['product_category_name_english'] = df['product_category_name_english'].astype('string')
    df['product_category_name_italian']  = df['product_category_name_italian'].astype('string')
    return df

# Transform Customers
def transform_customers(df):
    df = df.drop_duplicates(subset=['customer_id']).copy()
    # Extract digits, pad to 5; preserves leading zeros and handles NaNs/strings/floats
    cap_digits = df['cap'].astype('string').str.extract(r'(\d+)', expand=False)
    df['cap'] = cap_digits.fillna('').str.zfill(5)
    return df

# Transform Products
def transform_products(df, categories_df=None):
    df = df.copy()
    # Keep a textual category when no mapping is provided
    df['category'] = df['category'].astype('string').fillna('unknown')

    if categories_df is not None:
        # Use a local ref to avoid rebinding the parameter name
        cat_ref = categories_df[['category_id', 'product_category_name_english']].copy()
        df = df.merge(
            cat_ref,
            left_on='category',
            right_on='product_category_name_english',
            how='left'
        )
        # Remove join helpers; keep only the mapped id
        df.drop(columns=['category', 'product_category_name_english'], inplace=True, errors='ignore')
        # Nullable integer for SQL NULL compatibility
        df['category_id'] = df['category_id'].astype('Int32')
    else:
        print("Warning: No categories DataFrame provided for mapping. Keeping category as string.")

    # Deduplicate by product_id
    df = df.drop_duplicates(subset=['product_id'])

    # Ensure numeric types (nullable integers)
    df['product_name_length']        = pd.to_numeric(df['product_name_length'], errors='coerce').astype('Int16')
    df['product_description_length'] = pd.to_numeric(df['product_description_length'], errors='coerce').astype('Int16')
    df['product_photos_qty']         = pd.to_numeric(df['product_photos_qty'], errors='coerce').astype('Int16')
    return df

# Transform Sellers
def transform_sellers(df):
    df = df.drop_duplicates(subset=['seller_id'])
    return df

# Transform Orders
def transform_orders(df):
    df = df.copy()
    # Be tolerant to bad timestamps; keep NULLs for review
    df["order_purchase_timestamp"]      = pd.to_datetime(df["order_purchase_timestamp"], errors='coerce')
    df["order_delivered_customer_date"] = pd.to_datetime(df["order_delivered_customer_date"], errors='coerce')
    df["order_estimated_delivery_date"] = pd.to_datetime(df["order_estimated_delivery_date"], errors='coerce').dt.date
    df['order_status'] = df['order_status'].astype('string')
    df = df.drop_duplicates(subset=['order_id'])
    return df

# Transform Items
def transform_items(df):
    df = df.copy()
    df['price']      = pd.to_numeric(df['price'], errors='coerce')
    df['freight']    = pd.to_numeric(df['freight'], errors='coerce')
    # Cast to nullable int before stringifying to avoid "1.0"
    df["order_item"] = pd.to_numeric(df["order_item"], errors="coerce").astype('Int16')
    df['item_id']    = df['order_id'].astype('string') + '_' + df['order_item'].astype('string')
    df = df.drop_duplicates(subset=['item_id'])
    return df

# ___ EXECUTION ___

TRANSFORMERS = {
    'categories': transform_categories,
    'customers':  transform_customers,
    'products':   transform_products,   # needs categories_df optionally
    'sellers':    transform_sellers,
    'orders':     transform_orders,
    'items':      transform_items,
}

def transform_table(table_name: str, df: pd.DataFrame, categories_df: pd.DataFrame | None = None) -> pd.DataFrame:
    fn = TRANSFORMERS.get(table_name)
    if fn is None:
        raise ValueError(f"Unknown table: {table_name}")
    if table_name == 'products':
        return fn(df, categories_df=categories_df)
    return fn(df)