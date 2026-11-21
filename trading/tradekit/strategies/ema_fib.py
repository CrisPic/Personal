"""Strategy B: EMA 9/14 crossover with a Fibonacci entry (FibsDontLie-style).

1. Window: crosses from `window[0]` to `window[1]` Italian time.
2. Signal: EMA fast crosses EMA slow on `tf` (M2 or M3); the cross direction
   is the trade direction. The cross is known when that candle closes.
3. Leg: from the lowest low (long) / highest high (short) of the last
   `leg_bars` candles to the extreme reached since.
4. Entry: limit at the 0.62 retracement of the leg. Stop beyond the leg origin.
   Target: the -0.28 extension (past the leg extreme by 0.28 of the leg).
5. Chop filter: skip if the EMAs crossed more than `max_crosses` times in the
   last `chop_bars` candles.
6. Daily limits (applied after simulation): at most `max_trades` per day,
   and none after the first win.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data.instruments import Instrument
from ..data.resample import TIMEFRAMES, resample
from ..engine import Order


@dataclass
class EMAFibParams:
    tf: str = "M3"
    fast: int = 9
    slow: int = 14
    window: tuple[int, int] = (6, 9)
    leg_bars: int = 20
    entry_fib: float = 0.62
    tp_ext: float = 0.28
    buffer_pips: float = 0.5
    order_bars: int = 10
    chop_bars: int = 60
    max_crosses: int = 3
    max_trades: int = 2
    stop_after_win: bool = True


def generate(m1: pd.DataFrame, inst: Instrument, p: EMAFibParams = EMAFibParams()) -> list[Order]:
    df = resample(m1, p.tf, inst.chart_clock)
    step = pd.Timedelta(TIMEFRAMES[p.tf])
    c = df["close"]
    fast = c.ewm(span=p.fast, adjust=False).mean()
    slow = c.ewm(span=p.slow, adjust=False).mean()
    above = (fast > slow).to_numpy()
    cross = np.zeros(len(df), int)
    cross[1:] = np.where(above[1:] & ~above[:-1], 1, np.where(~above[1:] & above[:-1], -1, 0))
    crosses_recent = pd.Series(cross != 0).rolling(p.chop_bars, min_periods=1).sum().to_numpy()

    hours = df.index.tz_convert("Europe/Rome").hour
    hi, lo = df["high"].to_numpy(float), df["low"].to_numpy(float)
    buffer = p.buffer_pips * inst.pip
    orders = []
    for i in np.flatnonzero(cross):
        if i < p.leg_bars or not (p.window[0] <= hours[i] < p.window[1]):
            continue
        if crosses_recent[i] > p.max_crosses:
            continue
        d = int(cross[i])
        seg_lo, seg_hi = lo[i - p.leg_bars:i + 1], hi[i - p.leg_bars:i + 1]
        if d == 1:
            o = int(seg_lo.argmin())
            origin, ext = seg_lo[o], seg_hi[o:].max()
            rng = ext - origin
            entry, stop, target = ext - p.entry_fib * rng, origin - buffer, ext + p.tp_ext * rng
        else:
            o = int(seg_hi.argmax())
            origin, ext = seg_hi[o], seg_lo[o:].min()
            rng = origin - ext
            entry, stop, target = ext + p.entry_fib * rng, origin + buffer, ext - p.tp_ext * rng
        if rng <= 0:
            continue
        placed = df.index[i] + step
        orders.append(
            Order(
                placed=placed,
                expires=placed + p.order_bars * step,
                direction=d,
                entry=float(entry),
                stop=float(stop),
                target=float(target),
                tag="B",
                meta={"leg_pips": rng / inst.pip},
            )
        )
    return orders


def apply_daily_limits(trades: pd.DataFrame, p: EMAFibParams = EMAFibParams()) -> pd.DataFrame:
    """Keep at most max_trades per Italian day, and stop after the first win."""
    if trades.empty:
        return trades
    day = trades["entry_time"].dt.tz_convert("Europe/Rome").dt.date
    keep = []
    for _, g in trades.groupby(day, sort=True):
        n = 0
        for idx, r in g.sort_values("entry_time").iterrows():
            if n >= p.max_trades:
                break
            keep.append(idx)
            n += 1
            if p.stop_after_win and r["R"] > 0:
                break
    return trades.loc[keep].sort_values("entry_time").reset_index(drop=True)
