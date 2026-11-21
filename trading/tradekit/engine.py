"""Order simulation on M1 candles.

Strategies emit limit orders. The engine fills and exits them on M1 bid
candles, with the ask derived from the stored spread:

* Long: fills when the ask low (low + spread) reaches the entry. Exits on the
  bid: stop when low <= stop, target when high >= target.
* Short: fills when the bid high reaches the entry. Exits on the ask:
  stop when high + spread >= stop, target when low + spread <= target.
* Stop and target touched in the same minute = counted as a stop (pessimistic).
* The fill candle itself can hit the stop, never the target (we cannot tell
  the order of prices inside one minute, so we assume the worst).
* An order is cancelled if it is not filled before `expires`, or if price
  reaches the target first (the move left without us).
* One position per instrument: orders arriving while a trade is open are skipped.

Results are in R (multiples of the initial risk), after spread, stop
slippage and commission.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Order:
    placed: pd.Timestamp  # when the order is known (no earlier than the signal close)
    expires: pd.Timestamp
    direction: int  # +1 long, -1 short
    entry: float
    stop: float
    target: float
    tag: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class Costs:
    commission: float = 0.0  # price units per round trip (e.g. 0.6 pip = 0.00006)
    stop_slippage: float = 0.0  # price units added against us on stop exits


def simulate(m1: pd.DataFrame, orders: list[Order], costs: Costs = Costs()) -> pd.DataFrame:
    if not orders:
        return pd.DataFrame()
    t = m1.index.tz_convert("UTC").tz_localize(None).to_numpy() if m1.index.tz is not None else m1.index.to_numpy()
    lo = m1["low"].to_numpy(float)
    hi = m1["high"].to_numpy(float)
    sp = m1["spread"].fillna(0).to_numpy(float) if "spread" in m1 else np.zeros(len(m1))
    ask_lo, ask_hi = lo + sp, hi + sp

    trades = []
    busy_until = np.datetime64("1970-01-01T00:00:00")
    for od in sorted(orders, key=lambda o: o.placed):
        placed = _np(od.placed)
        if placed < busy_until:
            continue
        risk = abs(od.entry - od.stop)
        if risk <= 0:
            continue
        a = int(np.searchsorted(t, placed, side="left"))
        b = int(np.searchsorted(t, _np(od.expires), side="left"))
        if a >= len(t) or b <= a:
            continue
        L = od.direction == 1
        fill_hit = (ask_lo[a:b] <= od.entry) if L else (hi[a:b] >= od.entry)
        tgt_hit = (hi[a:b] >= od.target) if L else (ask_lo[a:b] <= od.target)
        f = _first(fill_hit)
        g = _first(tgt_hit)
        if f is None or (g is not None and g < f):
            continue  # never filled, or price ran to target first
        fi = a + f

        # After the fill: scan forward in chunks until stop or target.
        s = p = None
        start = fi
        while start < len(t) and s is None and p is None:
            end = min(start + 4096, len(t))
            stop_hit = (lo[start:end] <= od.stop) if L else (ask_hi[start:end] >= od.stop)
            tp_hit = (hi[start:end] >= od.target) if L else (ask_lo[start:end] <= od.target)
            if start == fi:
                tp_hit[0] = False  # never credit the target on the fill candle
            s0, p0 = _first(stop_hit), _first(tp_hit)
            s = None if s0 is None else start - fi + s0
            p = None if p0 is None else start - fi + p0
            start = end
        if s is None and p is None:
            exit_i, exit_px, reason = len(t) - 1, (lo[-1] if L else ask_hi[-1]), "open_at_end"
        elif p is None or (s is not None and s <= p):
            exit_i, exit_px, reason = fi + s, od.stop - od.direction * costs.stop_slippage, "stop"
        else:
            exit_i, exit_px, reason = fi + p, od.target, "target"

        gross = (exit_px - od.entry) * od.direction
        net = gross - costs.commission
        trades.append(
            {
                "tag": od.tag,
                "direction": od.direction,
                "placed": od.placed,
                "entry_time": pd.Timestamp(t[fi], tz="UTC"),
                "exit_time": pd.Timestamp(t[exit_i], tz="UTC"),
                "entry": od.entry,
                "stop": od.stop,
                "target": od.target,
                "exit": exit_px,
                "reason": reason,
                "R": net / risk,
                "planned_rr": abs(od.target - od.entry) / risk,
                **od.meta,
            }
        )
        busy_until = t[exit_i]
    return pd.DataFrame(trades)


def _first(mask: np.ndarray):
    if not mask.any():
        return None
    return int(mask.argmax())


def _np(ts: pd.Timestamp):
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return np.datetime64(ts, "ns")
