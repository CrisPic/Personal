"""Strategy A: top-down SMC (spec rules 1-10).

1. H4 structure sets the bias.
2. H1 breaks in the bias direction leave order blocks: the points of interest (POI).
3. When M1 price reaches an active POI, wait for an M1 CHoCH in the POI's
   direction, then an M1 BOS in the same direction (both on candle closes).
4. Entry: limit at the overlap of the M1 order block and the 0.618-0.786
   retracement of the BOS leg, or at the order block's midpoint if they do not overlap.
5. Stop beyond the leg origin plus a buffer; target at a fixed RR.
6. Only orders placed inside the session window (Italian time).
7. A POI dies when an M1 candle closes through it or after `zone_days`;
   it allows 1 + `reentries` setups.

A liquidity sweep is recorded on each trade (the leg origin took out the lows
of the hour before the touch) but is not required.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data.instruments import Instrument
from ..data.resample import TIMEFRAMES, resample
from ..engine import Order
from ..structure import breaks_frame, find_breaks


@dataclass
class SMCParams:
    bias_tf: str = "H4"
    poi_tf: str = "H1"
    swing_n_htf: int = 3
    swing_n_ltf: int = 2
    zone_days: int = 10
    fib_lo: float = 0.618
    fib_hi: float = 0.786
    rr: float = 3.0
    buffer_pips: float = 1.0
    order_minutes: int = 60
    session: tuple[int, int] = (7, 12)  # Italian time, [start, end)
    reentries: int = 1
    use_bias: bool = True


def generate(m1: pd.DataFrame, inst: Instrument, p: SMCParams = SMCParams()) -> list[Order]:
    clock = inst.chart_clock
    poi = resample(m1, p.poi_tf, clock)
    poi_step = pd.Timedelta(TIMEFRAMES[p.poi_tf])
    zones = breaks_frame(find_breaks(poi, p.swing_n_htf))
    if zones.empty:
        return []
    zones["known_at"] = zones["time"] + poi_step

    bias = None
    if p.use_bias:
        b = breaks_frame(find_breaks(resample(m1, p.bias_tf, clock), p.swing_n_htf))
        if not b.empty:
            b["known_at"] = b["time"] + pd.Timedelta(TIMEFRAMES[p.bias_tf])
            bias = b.set_index("known_at")["direction"].sort_index()

    ltf = breaks_frame(find_breaks(m1, p.swing_n_ltf))
    if ltf.empty:
        return []
    ltf_known = ltf["known_at"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy()

    t = m1.index
    tn = t.tz_convert("UTC").tz_localize(None).to_numpy()
    lo, hi, cl = (m1[k].to_numpy(float) for k in ("low", "high", "close"))
    buffer = p.buffer_pips * inst.pip
    orders: list[Order] = []

    for z in zones.itertuples():
        d = z.direction
        start = _idx(tn, z.known_at)
        end = _idx(tn, z.known_at + pd.Timedelta(days=p.zone_days))
        if start >= end:
            continue
        zl, zh = z.ob_low, z.ob_high
        # first touch, and the first close through the zone (it dies there)
        touch = _first((lo[start:end] <= zh) if d == 1 else (hi[start:end] >= zl))
        if touch is None:
            continue
        touch += start
        dead = _first((cl[touch:end] < zl) if d == 1 else (cl[touch:end] > zh))
        stop_i = end if dead is None else touch + dead

        if bias is not None:
            bias_now = bias.asof(t[touch])
            if pd.isna(bias_now) or bias_now != d:
                continue

        # LTF events inside the live window
        a = np.searchsorted(ltf_known, _np(t[touch]))
        b_ = np.searchsorted(ltf_known, _np(t[min(stop_i, len(t) - 1)]))
        window = ltf.iloc[a:b_]
        setups = 0
        seen_choch = False
        for ev in window.itertuples():
            if ev.direction != d:
                seen_choch = False
                continue
            if ev.kind == "CHoCH":
                seen_choch = True
                continue
            if not seen_choch:
                continue
            # CHoCH then BOS in our direction: a setup
            seen_choch = False
            placed = ev.known_at
            hour = placed.tz_convert("Europe/Rome").hour
            if not (p.session[0] <= hour < p.session[1]):
                continue
            od = _order(ev, d, hi, lo, placed, buffer, p, touch, z, lo, hi)
            if od is not None:
                orders.append(od)
                setups += 1
            if setups >= 1 + p.reentries:
                break
    return orders


def _order(ev, d, hi, lo, placed, buffer, p, touch, z, low_arr, high_arr):
    o, b = ev.origin_bar, ev.bar
    if d == 1:
        ext = hi[o:b + 1].max()
        rng = ext - ev.origin_price
        if rng <= 0:
            return None
        f_hi, f_lo = ext - p.fib_lo * rng, ext - p.fib_hi * rng
        top, bot = min(f_hi, ev.ob_high), max(f_lo, ev.ob_low)
        entry = top if top > bot else (ev.ob_low + ev.ob_high) / 2
        stop = ev.origin_price - buffer
        if entry <= stop:
            return None
        target = entry + p.rr * (entry - stop)
        sweep = ev.origin_price < low_arr[max(touch - 60, 0):touch].min() if touch > 0 else False
    else:
        ext = lo[o:b + 1].min()
        rng = ev.origin_price - ext
        if rng <= 0:
            return None
        f_lo, f_hi = ext + p.fib_lo * rng, ext + p.fib_hi * rng
        bot, top = max(f_lo, ev.ob_low), min(f_hi, ev.ob_high)
        entry = bot if top > bot else (ev.ob_low + ev.ob_high) / 2
        stop = ev.origin_price + buffer
        if entry >= stop:
            return None
        target = entry - p.rr * (stop - entry)
        sweep = ev.origin_price > high_arr[max(touch - 60, 0):touch].max() if touch > 0 else False
    return Order(
        placed=placed,
        expires=placed + pd.Timedelta(minutes=p.order_minutes),
        direction=d,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        tag="A",
        meta={"zone_time": z.time, "sweep": bool(sweep)},
    )


def _np(ts):
    ts = pd.Timestamp(ts)
    return np.datetime64(ts.tz_convert("UTC").tz_localize(None) if ts.tzinfo else ts, "ns")


def _idx(tn, ts):
    return int(np.searchsorted(tn, _np(ts)))


def _first(mask):
    return int(mask.argmax()) if mask.any() else None
