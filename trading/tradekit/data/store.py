"""Parquet store: data/market/{INSTRUMENT}/M1/{YYYY-MM}.parquet (UTC index)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "market"


def month_path(instrument: str, year: int, month: int, root: Path = DATA_DIR) -> Path:
    return root / instrument / "M1" / f"{year:04d}-{month:02d}.parquet"


def save_month(df: pd.DataFrame, instrument: str, year: int, month: int, root: Path = DATA_DIR) -> Path:
    path = month_path(instrument, year, month, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return path


def load_m1(instrument: str, start: str | None = None, end: str | None = None, root: Path = DATA_DIR) -> pd.DataFrame:
    """Load stored M1 candles, optionally limited to [start, end) (UTC date strings)."""
    files = sorted((root / instrument / "M1").glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No M1 data for {instrument} in {root}. Run the download first.")
    if start:
        files = [f for f in files if f.stem >= start[:7]]
    if end:
        files = [f for f in files if f.stem <= end[:7]]
    df = pd.concat(pd.read_parquet(f) for f in files).sort_index()
    if start:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    if end:
        df = df[df.index < pd.Timestamp(end, tz="UTC")]
    return df
