"""Market structure: swing points, BOS / CHoCH events and order blocks.

Everything here is computed bar by bar with no lookahead:

* A swing high at bar i is a high strictly above the `n` highs before it and at
  or above the `n` highs after it. It only becomes *known* at bar i + n, and
  only from then on can it be broken.
* A break needs a candle CLOSE beyond the swing (wicks do not count).
* A break in the current trend's direction is a BOS. A break against it is a
  CHoCH and flips the trend. The first break sets the trend and counts as a CHoCH.
* Each break records the leg origin (the extreme opposite the break since the
  broken swing, "the peak of the structure" where the stop goes) and the order
  block: the last opposite-colour candle at or before the origin.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Break:
    bar: int  # index of the candle whose close broke the swing
    time: pd.Timestamp  # open time of that candle
    known_at: pd.Timestamp  # close time of that candle: the moment the break is known
    direction: int  # +1 bullish break, -1 bearish break
    kind: str  # "BOS" or "CHoCH"
    level: float  # the swing price that was broken
    origin_bar: int
    origin_price: float  # low of the leg (bullish) or high (bearish): stop goes beyond it
    ob_bar: int
    ob_low: float
    ob_high: float


def swing_points(high: np.ndarray, low: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Boolean arrays marking swing highs and lows (at the swing bar itself)."""
    hs, ls = pd.Series(high), pd.Series(low)
    before_max = hs.rolling(n).max().shift(1)
    after_max = hs[::-1].rolling(n).max()[::-1].shift(-1)
    before_min = ls.rolling(n).min().shift(1)
    after_min = ls[::-1].rolling(n).min()[::-1].shift(-1)
    sh = ((hs > before_max) & (hs >= after_max)).to_numpy()
    sl = ((ls < before_min) & (ls <= after_min)).to_numpy()
    return sh, sl


def find_breaks(df: pd.DataFrame, n: int = 2, ob_lookback: int = 5) -> list[Break]:
    """Walk the candles and return every BOS / CHoCH, in time order."""
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    idx = df.index
    # candle length: the most common gap (the first gap may be a weekend)
    m = min(len(idx), 200)
    step = pd.Series(idx[1:m] - idx[:m - 1]).mode().iloc[0] if m > 1 else pd.Timedelta(minutes=1)
    sh, sl = swing_points(h, l, n)
    sh_l, sl_l, c_l, h_l, l_l = sh.tolist(), sl.tolist(), c.tolist(), h.tolist(), l.tolist()

    trend = 0
    last_high = last_low = None  # (bar, price) of the latest confirmed, unbroken swing
    events: list[Break] = []
    for i in range(len(c_l)):
        j = i - n  # a swing at j is confirmed now
        if j >= 0:
            if sh_l[j]:
                last_high = (j, h_l[j])
            if sl_l[j]:
                last_low = (j, l_l[j])
        ci = c_l[i]
        if last_high is not None and ci > last_high[1]:
            sb = last_high[0]
            ob = sb + int(np.argmin(l[sb:i + 1]))  # lowest low between the swing and the break
            ev = _make(df, idx, step, o, h, l, i, +1, "BOS" if trend == 1 else "CHoCH", last_high[1], ob, ob_lookback)
            events.append(ev)
            trend, last_high = 1, None
        elif last_low is not None and ci < last_low[1]:
            sb = last_low[0]
            ob = sb + int(np.argmax(h[sb:i + 1]))
            ev = _make(df, idx, step, o, h, l, i, -1, "BOS" if trend == -1 else "CHoCH", last_low[1], ob, ob_lookback)
            events.append(ev)
            trend, last_low = -1, None
    return events


def _make(df, idx, step, o, h, l, i, direction, kind, level, origin, lookback) -> Break:
    # Order block: last opposite candle at or before the origin (bearish for a bullish break).
    ob = origin
    close = df["close"].to_numpy()
    for k in range(origin, max(origin - lookback, 0) - 1, -1):
        if (direction == 1 and close[k] < o[k]) or (direction == -1 and close[k] > o[k]):
            ob = k
            break
    lo = min(l[ob], l[origin]) if direction == 1 else l[ob]
    hi = h[ob] if direction == 1 else max(h[ob], h[origin])
    return Break(
        bar=i,
        time=idx[i],
        known_at=idx[i] + step,
        direction=direction,
        kind=kind,
        level=float(level),
        origin_bar=origin,
        origin_price=float(l[origin] if direction == 1 else h[origin]),
        ob_bar=ob,
        ob_low=float(lo),
        ob_high=float(hi),
    )


def breaks_frame(events: list[Break]) -> pd.DataFrame:
    return pd.DataFrame([e.__dict__ for e in events])
