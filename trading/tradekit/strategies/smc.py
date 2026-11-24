"""Strategy A: top-down SMC (spec rules 1-10).

1. H4 structure sets the bias.
2. H1 breaks in the bias direction leave order blocks: the points of interest (POI).
3. When M1 price reaches an active POI, wait for a CHoCH on the confirming
   timeframe (`ltf`, M1 by default) in the POI's direction, then a BOS in the
   same direction (both on candle closes).
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
    ltf: str = "M1"  # timeframe of the confirming CHoCH/BOS (M1, M3 or M5)
    zone_days: int = 10
    fib_lo: float = 0.618
    fib_hi: float = 0.786
    rr: float = 3.0
    buffer_pips: float = 1.0
    order_minutes: int = 60
    session: tuple[int, int] = (7, 12)  # Italian time, [start, end)
    reentries: int = 1
    use_bias: bool = True
    # How Cristian marks his setups (Nov 2026 US30 markups):
    trigger: str = "choch_bos"  # "choch": enter after the CoC alone; "choch_bos": wait for a BOS too
    entry_mode: str = "ob_fib"  # "fib": limit at entry_fib of the leg; "ob_fib": OB / fib-zone overlap
    entry_fib: float = 0.705
    target_mode: str = "rr"  # "rr": fixed RR; "fib_ext": the -tp_ext extension of the leg
    tp_ext: float = 0.5
    require_sweep: bool = False  # the leg origin must take out the lows/highs of sweep_minutes before it
    sweep_minutes: int = 60


def cristian(**kw) -> "SMCParams":
    """The rules as drawn in Cristian's Nov 2026 markups: POI -> sweep -> M1 CoC ->
    fib on the CoC leg, entry 0.705, stop at the 1.0 anchor, target at the -0.5 extension."""
    base = dict(trigger="choch", entry_mode="fib", entry_fib=0.705, target_mode="fib_ext",
                tp_ext=0.5, require_sweep=True, buffer_pips=0.0, session=(7, 15),
                use_bias=False)  # he also takes counter-trend setups (target capped at the next POI)
    base.update(kw)
    return SMCParams(**base)


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

    ltf_df = m1 if p.ltf == "M1" else resample(m1, p.ltf, clock)
    ltf = breaks_frame(find_breaks(ltf_df, p.swing_n_ltf))
    if ltf.empty:
        return []
    ltf_known = ltf["known_at"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy()

    t = m1.index
    tn = t.tz_convert("UTC").tz_localize(None).to_numpy()
    lo, hi, cl = (m1[k].to_numpy(float) for k in ("low", "high", "close"))
    llo, lhi = ltf_df["low"].to_numpy(float), ltf_df["high"].to_numpy(float)
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
            if p.trigger == "choch":
                if ev.kind != "CHoCH":
                    continue
            else:
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
            od = _order(ev, d, lhi, llo, placed, buffer, p, _idx(tn, ev.time), z, lo, hi)
            if od is not None:
                orders.append(od)
                setups += 1
            if setups >= 1 + p.reentries:
                break
    return orders


def _order(ev, d, hi, lo, placed, buffer, p, at, z, low_arr, high_arr):
    """`hi`/`lo` are on the confirming timeframe; `low_arr`/`high_arr` are M1, `at` is the M1 index of the break."""
    o, b = ev.origin_bar, ev.bar
    o_m1 = at - (b - o) * _ratio(p.ltf)  # M1 index of the leg origin, approx.
    look = slice(max(o_m1 - p.sweep_minutes, 0), max(o_m1 - 2, 0))
    if d == 1:
        ext = hi[o:b + 1].max()
        rng = ext - ev.origin_price
        if rng <= 0:
            return None
        if p.entry_mode == "fib":
            entry = ext - p.entry_fib * rng
        else:
            f_hi, f_lo = ext - p.fib_lo * rng, ext - p.fib_hi * rng
            top, bot = min(f_hi, ev.ob_high), max(f_lo, ev.ob_low)
            entry = top if top > bot else (ev.ob_low + ev.ob_high) / 2
        stop = ev.origin_price - buffer
        if entry <= stop:
            return None
        target = ext + p.tp_ext * rng if p.target_mode == "fib_ext" else entry + p.rr * (entry - stop)
        prior = low_arr[look]
        sweep = bool(prior.size) and ev.origin_price < prior.min()
    else:
        ext = lo[o:b + 1].min()
        rng = ev.origin_price - ext
        if rng <= 0:
            return None
        if p.entry_mode == "fib":
            entry = ext + p.entry_fib * rng
        else:
            f_lo, f_hi = ext + p.fib_lo * rng, ext + p.fib_hi * rng
            bot, top = max(f_lo, ev.ob_low), min(f_hi, ev.ob_high)
            entry = bot if top > bot else (ev.ob_low + ev.ob_high) / 2
        stop = ev.origin_price + buffer
        if entry >= stop:
            return None
        target = ext - p.tp_ext * rng if p.target_mode == "fib_ext" else entry - p.rr * (stop - entry)
        prior = high_arr[look]
        sweep = bool(prior.size) and ev.origin_price > prior.max()
    if p.require_sweep and not sweep:
        return None
    return Order(
        placed=placed,
        expires=placed + pd.Timedelta(minutes=p.order_minutes),
        direction=d,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        tag="A",
        meta={"zone_time": z.time, "sweep": bool(sweep), "kind": ev.kind},
    )


def _ratio(tf: str) -> int:
    return int(pd.Timedelta(TIMEFRAMES[tf]) / pd.Timedelta(minutes=1))


def _np(ts):
    ts = pd.Timestamp(ts)
    return np.datetime64(ts.tz_convert("UTC").tz_localize(None) if ts.tzinfo else ts, "ns")


def _idx(tn, ts):
    return int(np.searchsorted(tn, _np(ts)))


def _first(mask):
    return int(mask.argmax()) if mask.any() else None
