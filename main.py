# src/main.py
from pathlib import Path
from datetime import datetime
import pandas as pd
from tqdm import tqdm

from src import processed_path
import src.transform as tr
import src.extract as ex


TABLES = ("categories", "customers", "items", "orders", "products", "sellers")

def _parse_table_year(name: str) -> tuple[str, int] | None:
    m = ex.RAW_NAME_RE.match(name)
    if not m:
        return None
    return m.group("table"), int(m.group("year"))

def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _processed_filename(table: str, year: int, ts: str) -> Path:
    return Path(processed_path) / f"{table}_{year}_{ts}.csv"

def _delete_existing_processed_for(table: str, year: int) -> None:
    for p in Path(processed_path).glob(f"{table}_{year}_*.csv"):
        try:
            p.unlink()
        except Exception as e:
            print(f"Warning: could not delete {p.name}: {e}")

def _load_latest_master_categories() -> pd.DataFrame | None:
    candidates = sorted(Path(processed_path).glob("categories_master_*.csv"))
    if not candidates:
        return None
    latest = candidates[-1]
    try:
        return pd.read_csv(latest)
    except Exception as e:
        print(f"Warning: failed reading {latest.name} (master categories): {e}")
        return None

def build_master_categories(years: list[int]) -> Path:
    """Create a single, stable categories map across the given years' RAW files."""
    import src.extract as ex
    frames: list[pd.DataFrame] = []

    for y in years:
        paths = ex.list_raw(year=y, table="categories")
        if not paths:
            print(f"Note: no RAW categories file found for {y}; skipping.")
            continue
        df = ex.read_raw("categories", y)
        # Be defensive about column names
        required = ["product_category_name_english", "product_category_name_italian"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise RuntimeError(f"{paths[0].name}: missing columns {missing}")
        frames.append(df[required].copy())

    if not frames:
        raise RuntimeError("No categories data found to build master mapping.")

    cat = pd.concat(frames, ignore_index=True)

    # Deduplicate on both names (treat missing as empty for dedup only)
    cat["_key"] = (
        cat["product_category_name_english"].fillna("").str.strip().str.lower()
        + "||" +
        cat["product_category_name_italian"].fillna("").str.strip().str.lower()
    )
    cat = cat.drop_duplicates(subset=["_key"]).drop(columns=["_key"])

    # Stable order → stable IDs
    cat = cat.sort_values(
        ["product_category_name_english", "product_category_name_italian"],
        na_position="last"
    ).reset_index(drop=True)

    # Assign deterministic surrogate keys
    cat.insert(0, "category_id", cat.index + 1)

    out = Path(processed_path) / f"categories_master_{_timestamp()}.csv"
    cat.to_csv(out, index=False)
    print(f"[build] Master categories → {out.name} ({len(cat):,} rows)")
    return out

def _load_latest_processed_categories(year: int) -> pd.DataFrame | None:
    candidates = sorted(Path(processed_path).glob(f"categories_{year}_*.csv"))
    if not candidates:
        return None
    latest = candidates[-1]
    try:
        return pd.read_csv(latest)
    except Exception as e:
        print(f"Warning: failed reading {latest.name} for category mapping: {e}")
        return None

def _preview_raw():
    files = ex.list_raw()
    if not files:
        print("No raw files found.")
        return
    print("\n[RAW files]")
    for i, p in enumerate(files, 1):
        print(f"{i}. {p.name}")
    choice = input("Select a file number to preview (or Enter to cancel): ").strip()
    if not choice:
        return
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(files):
            print("Invalid selection.")
            return
        name = files[idx].name
        parsed = _parse_table_year(name)
        if not parsed:
            print("Filename does not match expected pattern.")
            return
        table, year = parsed
        print(f"\n[Preview] {name}")
        df = ex.read_raw(table, year)  # uses UTF-8 with latin-1 fallback
        print(df.head(10).to_string(index=False))
        print("\n[Schema]")
        print(df.dtypes)
        print(f"\nRows: {len(df):,}")
    except Exception:
        # clean error + traceback (propagate)
        raise

def _transform_one_to_processed():
    files = ex.list_raw()
    if not files:
        print("No raw files found.")
        return
    print("\n[RAW files]")
    for i, p in enumerate(files, 1):
        print(f"{i}. {p.name}")
    choice = input("Select a file number to transform (or Enter to cancel): ").strip()
    if not choice:
        return
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(files):
            print("Invalid selection.")
            return
        name = files[idx].name
        parsed = _parse_table_year(name)
        if not parsed:
            print("Filename does not match expected pattern.")
            return
        table, year = parsed

        steps = ["read", "transform", "write"]
        pbar = tqdm(total=len(steps), desc=f"{table}_{year}", unit="step")

        # Read via extract
        df = ex.read_raw(table, year)
        pbar.update(1)

        # Transform (products may map categories)
        categories_df = None
        if table == "products":
            # Prefer global master; fall back to per-year categories if master missing
            categories_df = _load_latest_master_categories()
            if categories_df is None:
                categories_df = _load_latest_processed_categories(year)
        df_t = tr.transform_table(table, df, categories_df=categories_df)
        pbar.update(1)

        # Write (overwrite policy by table_year)
        _delete_existing_processed_for(table, year)
        out = _processed_filename(table, year, _timestamp())
        df_t.to_csv(out, index=False)
        pbar.update(1)
        pbar.close()

        print(f"[OK] {table}_{year}: {len(df):,} → {len(df_t):,} rows written to {out.name}")

    except Exception:
        raise

def _batch_transform_year():
    year_s = input("Enter year to transform all tables for (e.g., 2016): ").strip()
    if not year_s.isdigit():
        print("Invalid year.")
        return
    year = int(year_s)

    # Detect which tables exist for the chosen year using extract
    files = ex.list_raw(year=year)
    if not files:
        print(f"No raw files found for year {year}.")
        return

    present_tables: set[str] = set()
    for p in files:
        parsed = _parse_table_year(p.name)
        if parsed:
            t, _ = parsed
            present_tables.add(t)

    # Stable load order (categories before products)
    order = ("categories", "customers", "products", "sellers", "orders", "items")
    results: list[tuple[str, str]] = []

    with tqdm(total=len(order), desc=f"year {year}", unit="table") as pbar:
        for table in order:
            if table not in present_tables:
                results.append((table, "SKIPPED (missing raw file)"))
                pbar.update(1)
                continue
            try:
                df = ex.read_raw(table, year)

                categories_df = _load_latest_processed_categories(year) if table == "products" else None
                df_t = tr.transform_table(table, df, categories_df=categories_df)

                _delete_existing_processed_for(table, year)
                out = _processed_filename(table, year, _timestamp())
                df_t.to_csv(out, index=False)

                results.append((table, f"PASSED ({len(df):,} → {len(df_t):,} rows)"))
            except Exception as e:
                results.append((table, f"FAILED ({type(e).__name__}: {e})"))
            finally:
                pbar.update(1)

    print("\n[Batch summary]")
    for table, status in results:
        print(f"- {table}_{year}: {status}")

def _delete_all_processed():
    confirm = input("Delete ALL files in data/processed/? Type YES to confirm: ").strip()
    if confirm != "YES":
        print("Cancelled.")
        return
    count = 0
    for p in Path(processed_path).glob("*.csv"):
        try:
            p.unlink()
            count += 1
        except Exception as e:
            print(f"Warning: could not delete {p.name}: {e}")
    print(f"Deleted {count} file(s) from processed.")

def _clear_database_drop_recreate():
    try:
        from src.load import drop_and_recreate_all
    except Exception:
        print("Database reset not implemented yet (src.load.drop_and_recreate_all missing).")
        return
    drop_and_recreate_all()
    print("Database dropped and recreated.")

def _load_one_processed():
    try:
        from src.load import load_processed_file
    except Exception:
        print("Load operation not implemented yet (src.load.load_processed_file missing).")
        return
    files = sorted(Path(processed_path).glob("*.csv"))
    if not files:
        print("No processed files to load.")
        return
    print("\n[Processed files]")
    for i, p in enumerate(files, 1):
        print(f"{i}. {p.name}")
    choice = input("Select a file number to load (or Enter to cancel): ").strip()
    if not choice:
        return
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(files):
            print("Invalid selection.")
            return
        load_processed_file(files[idx])
    except Exception:
        raise

def _batch_load_subset():
    try:
        from src.load import batch_load_year
    except Exception:
        print("Batch load not implemented yet (src.load.batch_load_year missing).")
        return
    year_s = input("Enter year to load all processed tables for (e.g., 2016): ").strip()
    if not year_s.isdigit():
        print("Invalid year.")
        return
    year = int(year_s)
    batch_load_year(year)

def main():
    loop = True
    while loop:
        print("\nSelect an option:")
        print("1 - Preview a RAW file")
        print("2 - Transform ONE RAW file → processed")
        print("3 - Batch transform (all tables) for a chosen year → processed")
        print("4 - Load ONE processed file")
        print("5 - Batch load (chosen year) from processed")
        print("6 - Delete ALL from processed")
        print("7 - Clear the PostgreSQL database (drop & recreate)")
        print("0 - Exit")
        choice = input("... ").strip()

        if choice == "1":
            _preview_raw()
        elif choice == "2":
            _transform_one_to_processed()
        elif choice == "3":
            _batch_transform_year()
        elif choice == "4":
            _load_one_processed()
        elif choice == "5":
            _batch_load_subset()
        elif choice == "6":
            _delete_all_processed()
        elif choice == "7":
            _clear_database_drop_recreate()
        elif choice == "0":
            loop = False
        else:
            print("Invalid choice.")



if __name__ == "__main__":
    main()