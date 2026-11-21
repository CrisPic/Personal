"""Dukascopy minute candles (forex, indices).

Dukascopy publishes one LZMA-compressed file of 1-minute candles per day and
side (BID / ASK):

    https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{YYYY}/{MM0}/{DD}/{SIDE}_candles_min_1.bi5

MM0 is the month counted from 00. Each record is 24 bytes, big-endian:
seconds from midnight UTC (uint32), open, close, low, high (uint32, price *
divisor) and volume (float32). Note the order: open, close, low, high.

We keep BID prices as the chart (that is what MT5 and cTrader draw) and store
the spread at each candle's open as ASK open - BID open.
"""
from __future__ import annotations

import lzma
import struct
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .http import FetchError, fetch
from .instruments import Instrument

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
RECORD = struct.Struct(">IIIIIf")
COLUMNS = ["open", "high", "low", "close", "volume"]


def day_url(symbol: str, day: date, side: str) -> str:
    return f"{BASE_URL}/{symbol}/{day.year:04d}/{day.month - 1:02d}/{day.day:02d}/{side}_candles_min_1.bi5"


def decode_candles(blob: bytes, day: date, divisor: int) -> pd.DataFrame:
    """Decode one day's .bi5 file into a UTC-indexed OHLCV frame."""
    if not blob:
        return _empty()
    raw = lzma.decompress(blob)
    if len(raw) % RECORD.size:
        raise ValueError(f"{day}: payload of {len(raw)} bytes is not a multiple of {RECORD.size}")
    arr = np.frombuffer(
        raw,
        dtype=np.dtype([("t", ">u4"), ("o", ">u4"), ("c", ">u4"), ("l", ">u4"), ("h", ">u4"), ("v", ">f4")]),
    )
    start = pd.Timestamp(day, tz="UTC")
    index = start + pd.to_timedelta(arr["t"].astype("int64"), unit="s")
    df = pd.DataFrame(
        {
            "open": arr["o"] / divisor,
            "high": arr["h"] / divisor,
            "low": arr["l"] / divisor,
            "close": arr["c"] / divisor,
            "volume": arr["v"].astype("float64"),
        },
        index=pd.DatetimeIndex(index, name="time"),
    )
    # Dukascopy pads closed-market minutes with flat zero-volume candles; drop them.
    return df[df["volume"] > 0]


def download_day(inst: Instrument, day: date) -> pd.DataFrame:
    bid = decode_candles(fetch(day_url(inst.symbol, day, "BID")), day, inst.divisor)
    if bid.empty:
        return _empty()
    ask = decode_candles(fetch(day_url(inst.symbol, day, "ASK")), day, inst.divisor)
    bid["spread"] = (ask["open"].reindex(bid.index) - bid["open"]).clip(lower=0)
    return bid


def download_range(inst: Instrument, start: date, end: date, workers: int = 2) -> tuple[pd.DataFrame, list[date]]:
    """Download [start, end] inclusive, one request pair per day, a few days at a time.

    Returns the candles and the days that still failed after all retries, so the
    caller can skip an incomplete month instead of storing a hole or crashing.
    """
    from concurrent.futures import ThreadPoolExecutor

    days = [start + timedelta(d) for d in range((end - start).days + 1)]
    days = [d for d in days if d.weekday() != 5]  # Saturday: market closed all day

    def one(d):
        try:
            return d, download_day(inst, d)
        except FetchError:
            return d, None

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(one, days))
    failed = [d for d, f in results if f is None]
    frames = [f for _, f in results if f is not None and not f.empty]
    return (pd.concat(frames).sort_index() if frames else _empty()), failed


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS + ["spread"], index=pd.DatetimeIndex([], tz="UTC", name="time"), dtype="float64")
