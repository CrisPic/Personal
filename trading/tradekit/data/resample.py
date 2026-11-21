"""Build higher timeframes from M1 so they match what the broker charts show.

Forex and index brokers (FTMO's MT5 and cTrader included) run their server
clock so that New York 17:00 is midnight: UTC+2 in winter, UTC+3 in summer.
Daily and H4 candles are cut on that clock. Crypto is cut on plain UTC.
"""
from __future__ import annotations

import pandas as pd

TIMEFRAMES = {"M1": "1min", "M3": "3min", "M5": "5min", "M15": "15min", "H1": "1h", "H4": "4h", "D1": "1D"}

AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "spread": "first"}


def to_chart_clock(index: pd.DatetimeIndex, clock: str) -> pd.DatetimeIndex:
    """Convert UTC timestamps to naive chart-clock timestamps."""
    if clock == "utc":
        return index.tz_convert("UTC").tz_localize(None)
    # New York wall time + 7h = broker server time, DST handled by the New York zone.
    return index.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)


def from_chart_clock(index: pd.DatetimeIndex, clock: str) -> pd.DatetimeIndex:
    if clock == "utc":
        return index.tz_localize("UTC")
    ny = (index - pd.Timedelta(hours=7)).tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
    return ny.tz_convert("UTC")


def resample(m1: pd.DataFrame, timeframe: str, clock: str) -> pd.DataFrame:
    """Aggregate M1 candles to `timeframe`. Index = candle open time in UTC."""
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"Unknown timeframe {timeframe!r}; use one of {', '.join(TIMEFRAMES)}")
    if timeframe == "M1":
        return m1.copy()
    local = m1.copy()
    local.index = to_chart_clock(m1.index, clock)
    agg = {k: v for k, v in AGG.items() if k in local.columns}
    out = local.resample(TIMEFRAMES[timeframe], label="left", closed="left").agg(agg).dropna(subset=["open"])
    out.index = from_chart_clock(out.index, clock)
    out.index.name = "time"
    return out[out.index.notna()]
