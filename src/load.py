# src/load.py
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Tuple, Optional

import pandas as pd
import psycopg
from psycopg import sql
from dotenv import load_dotenv

from src import ROOT_DIR, processed_path

load_dotenv()

# ---- DB CONFIG (lowercase env names, with sane defaults) ----
HOST = os.getenv("dbhost", "localhost")
DB   = os.getenv("dbname", "olist")
USER = os.getenv("dbuser", "postgres")
PWD  = os.getenv("dbpw",   "pass123")
PORT = int(os.getenv("dbport", "5432"))

# Supported logical table names
TABLES: Tuple[str, ...] = ("categories", "customers", "items", "orders", "products", "sellers")

# Processed filename patterns
PROCESSED_RE = re.compile(rf"^(?P<table>{'|'.join(TABLES)})_(?P<year>\d{{4}})_.+\.csv$")
MASTER_RE    = re.compile(r"^categories_master_(?P<ts>\d{8}_\d{6})\.csv$")  # categories master file

# ---------- Helpers ----------
def _connect():
    return psycopg.connect(host=HOST, dbname=DB, user=USER, password=PWD, port=PORT)

def _read_processed_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")

def _df_to_rows(df: pd.DataFrame, cols: List[str]) -> list[tuple]:
    """
    Convert a DataFrame to a list of tuples with None for missing values.
    Keeps column order as provided in `cols`.
    """
    sub = df.loc[:, cols].copy()
    # Make missing values become SQL NULLs
    sub = sub.astype(object).where(pd.notna(sub), None)
    return [tuple(row) for row in sub.to_numpy()]

def _infer_from_processed_name(path: Path) -> Tuple[str, int]:
    """
    Extract (table, year) from processed filename pattern: <table>_<year>_<timestamp>.csv
    """
    m = PROCESSED_RE.match(path.name)
    if not m:
        raise ValueError(
            f"Processed filename does not match pattern '<table>_<year>_<timestamp>.csv': {path.name}"
        )
    return m.group("table"), int(m.group("year"))

def _latest_processed_per_table_for_year(year: int) -> dict[str, Path]:
    """
    Pick the lexicographically latest processed file for each table in a given year.
    Assumes filenames carry a sortable timestamp suffix (YYYYMMDD_HHMMSS).
    """
    latest: dict[str, Path] = {}
    for p in sorted(Path(processed_path).glob(f"*_{year}_*.csv")):
        m = PROCESSED_RE.match(p.name)
        if not m:
            continue
        t = m.group("table")
        if t not in latest or p.name > latest[t].name:
            latest[t] = p
    return latest

def _insert_df(conn: psycopg.Connection, table: str, df: pd.DataFrame) -> int:
    """
    Generic loader: INSERT INTO <table> (<df.columns...>) VALUES (%s, %s, ...)
    ON CONFLICT DO NOTHING;
    Assumes DB column names match df.columns exactly.
    Returns number of rows attempted (not number actually inserted).
    """
    if df.empty:
        return 0

    cols = list(df.columns)
    rows = _df_to_rows(df, cols)

    identifiers = [sql.Identifier(c) for c in cols]
    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in cols)

    stmt = sql.SQL(
        "INSERT INTO {table} ({cols}) VALUES ({vals}) ON CONFLICT DO NOTHING"
    ).format(
        table=sql.Identifier(table),
        cols=sql.SQL(", ").join(identifiers),
        vals=placeholders,
    )

    with conn.cursor() as cur:
        for r in rows:
            cur.execute(stmt, r)
        conn.commit()

    return len(rows)

# ---------- Public API (used by main.py) ----------

def drop_and_recreate_all(schema_path: Optional[Path] = None, schema_sql: Optional[str] = None) -> None:
    """
    Drop & recreate the database schema.

    Provide your DDL either as:
      - schema_sql: a single SQL string with DDL, OR
      - schema_path: a Path to a .sql file (default search: ROOT_DIR / 'schema.sql').

    This function intentionally contains NO inline DDL. It executes whatever you provide.
    """
    if schema_sql is None:
        if schema_path is None:
            candidate = ROOT_DIR / "schema.sql"
            schema_path = candidate if candidate.exists() else None

        if schema_path is None or not Path(schema_path).exists():
            raise RuntimeError(
                "DDL not provided. Place 'schema.sql' at the project root or pass schema_sql/schema_path."
            )
        schema_sql = Path(schema_path).read_text(encoding="utf-8")

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(schema_sql)
        conn.commit()

def load_processed_file(path: Path) -> None:
    """
    Load a single processed CSV into its table.
    Accepts both per-year files (<table>_<year>_<ts>.csv) and the master categories file (categories_master_<ts>.csv).
    """
    if isinstance(path, str):
        path = Path(path)

    # Accept master categories without a year
    if path.name.startswith("categories_master_"):
        if not MASTER_RE.match(path.name):
            raise ValueError(f"Invalid master categories filename: {path.name}")
        table, year = "categories", 0
    else:
        table, year = _infer_from_processed_name(path)

    df = _read_processed_csv(path)
    with _connect() as conn:
        n = _insert_df(conn, table, df)

    print(f"[load] OK → {table} ← {path.name} ({n:,} rows attempted)")

def batch_load_year(year: int) -> None:
    """
    Load the latest processed file for each table for the given year.
    Continues on errors and reports a summary at the end.
    """
    latest = _latest_processed_per_table_for_year(year)
    if not latest:
        print(f"No processed files found for year {year}.")
        return

    order = ("categories", "customers", "products", "sellers", "orders", "items")
    results: list[tuple[str, str]] = []

    for table in order:
        p = latest.get(table)
        if p is None:
            results.append((table, "SKIPPED (no processed file)"))
            continue
        try:
            df = _read_processed_csv(p)
            with _connect() as conn:
                n = _insert_df(conn, table, df)
            results.append((table, f"PASSED ({n:,} rows)"))
        except Exception as e:
            results.append((table, f"FAILED ({type(e).__name__}: {e})"))

    print("\n[Batch load summary]")
    for table, status in results:
        print(f"- {table}_{year}: {status}")