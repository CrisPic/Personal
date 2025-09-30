from pathlib import Path
import re
from typing import Optional, List
import pandas as pd
from src import raw_path

# Supported logical table names
TABLES: tuple[str, ...] = ("categories", "customers", "items", "orders", "products", "sellers")

# olistPW_<YEAR>_<table>.csv  e.g. olistPW_2016_products.csv
RAW_NAME_RE = re.compile(rf"^olistPW_(?P<year>\d{{4}})_(?P<table>{'|'.join(TABLES)})\.csv$")

def list_raw(year: Optional[int] = None, table: Optional[str] = None) -> list[Path]:
    """
    List raw CSV files in data/raw, optionally filtered by year and/or table.
    - Enforces canonical name pattern: olistPW_<YEAR>_<table>.csv
    - Skips any files not matching the pattern.
    """
    if table is not None:
        table = table.strip().lower()
        if table not in TABLES:
            raise ValueError(f"Unknown table '{table}'. Expected one of {TABLES}.")

    candidates = sorted(Path(raw_path).glob("olistPW_*.csv"))
    results: list[Path] = []

    for p in candidates:
        m = RAW_NAME_RE.match(p.name)
        if not m:
            continue
        y = int(m.group("year"))
        t = m.group("table")
        if year is not None and y != year:
            continue
        if table is not None and t != table:
            continue
        results.append(p)

    return results

def _ensure_unique_raw(table: str, year: int) -> Path:
    """
    Find exactly one raw file for (table, year); otherwise raise a clear error.
    """
    table = table.strip().lower()
    if table not in TABLES:
        raise ValueError(f"Unknown table '{table}'. Expected one of {TABLES}.")

    matches = list_raw(year=year, table=table)
    if not matches:
        raise FileNotFoundError(
            f"No raw file found for table='{table}', year={year} in '{raw_path}'. "
            f"Expected: olistPW_{year}_{table}.csv"
        )
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        raise RuntimeError(
            f"Multiple raw files found for table='{table}', year={year} in '{raw_path}': {names}. "
            "Ensure only one file matches the canonical name."
        )
    return matches[0]

def read_raw(table: str, year: int) -> pd.DataFrame:
    """
    Read a raw CSV for (table, year) with pandas type inference.
    - Delimiter: comma
    - Header: present (first line)
    - Encoding: UTF-8; on UnicodeDecodeError, retry latin-1
    - NA handling: pandas defaults (no filling here)
    - Column names: preserved as in file
    """
    path = _ensure_unique_raw(table, year)
    try:
        return pd.read_csv(path, sep=",", header=0, encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback per your choice
        print(f"Warning: UTF-8 decode failed for {path.name}; retrying with latin-1.")
        return pd.read_csv(path, sep=",", header=0, encoding="latin-1")