"""Binance spot 1-minute klines from the public archive (crypto).

    https://data.binance.vision/data/spot/monthly/klines/{SYMBOL}/1m/{SYMBOL}-1m-{YYYY}-{MM}.zip

Each zip holds one CSV: open_time, open, high, low, close, volume, close_time,
... Open times are milliseconds, or microseconds in files from 2025 onward.
Binance has no ask price in the archive, so the instrument's spread_pips is
used as a fixed spread.
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd

from .http import fetch
from .instruments import Instrument

BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"


def month_url(symbol: str, year: int, month: int) -> str:
    return f"{BASE_URL}/{symbol}/1m/{symbol}-1m-{year:04d}-{month:02d}.zip"


def decode_month(blob: bytes, spread: float) -> pd.DataFrame:
    if not blob:
        return pd.DataFrame()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        with zf.open(zf.namelist()[0]) as fh:
            df = pd.read_csv(fh, header=None, usecols=range(6))
    df.columns = ["open_time", "open", "high", "low", "close", "volume"]
    df = df[pd.to_numeric(df["open_time"], errors="coerce").notna()]  # drop a header row if present
    t = df["open_time"].astype("int64")
    unit = "us" if t.iloc[0] > 10**14 else "ms"
    df.index = pd.DatetimeIndex(pd.to_datetime(t, unit=unit, utc=True), name="time")
    df = df[["open", "high", "low", "close", "volume"]].astype("float64")
    df["spread"] = spread
    return df


def download_month(inst: Instrument, year: int, month: int) -> pd.DataFrame:
    spread = (inst.spread_pips or 0) * inst.pip
    return decode_month(fetch(month_url(inst.symbol, year, month)), spread)
