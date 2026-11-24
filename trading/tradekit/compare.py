"""Check whether Strategy A finds the setups Cristian marked by hand.

    python -m tradekit.compare setups.csv --tz-offset 2
    python -m tradekit.compare setups.csv --preset cristian --window 30

setups.csv needs: date, time (chart time), direction (long/short), entry, stop;
optional: instrument (default US30), target. Prices from another broker's feed
differ by a few points, so matches are judged on time and direction first,
then the entry and stop distance is reported.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace

import pandas as pd

from .data.instruments import get_instrument
from .data.store import load_m1
from .engine import simulate
from .strategies import smc


def load_setups(path: str, tz_offset: float) -> pd.DataFrame:
    s = pd.read_csv(path)
    s.columns = [c.strip().lower() for c in s.columns]
    tcol = next(c for c in s.columns if c.startswith("time"))
    s["when"] = (pd.to_datetime(s["date"].astype(str) + " " + s[tcol].astype(str).str.lstrip("~"))
                 - pd.Timedelta(hours=tz_offset)).dt.tz_localize("UTC")
    s["dir"] = s["direction"].str.lower().str.startswith("long").map({True: 1, False: -1})
    if "instrument" not in s:
        s["instrument"] = "US30"
    s["instrument"] = s["instrument"].str.extract(r"([A-Z0-9]{4,6})", expand=False).fillna("US30")
    for c in ("entry", "stop", "target"):
        if c in s:
            s[c] = pd.to_numeric(s[c].astype(str).str.extract(r"([\d.]+)", expand=False), errors="coerce")
    return s


def compare(setups: pd.DataFrame, params: smc.SMCParams, window_min: int = 30) -> pd.DataFrame:
    rows = []
    for name, grp in setups.groupby("instrument"):
        inst = get_instrument(name)
        lo, hi = grp["when"].min() - pd.Timedelta(days=12), grp["when"].max() + pd.Timedelta(days=1)
        m1 = load_m1(name, lo.strftime("%Y-%m-%d"), hi.strftime("%Y-%m-%d"))
        orders = smc.generate(m1, inst, params)
        trades = simulate(m1, orders)
        for r in grp.itertuples():
            w = pd.Timedelta(minutes=window_min)
            near = [o for o in orders if o.direction == r.dir and abs(o.placed - r.when) <= w]
            row = {"date": r.when.strftime("%Y-%m-%d %H:%M UTC"), "dir": r.dir, "my_entry": r.entry, "my_stop": r.stop}
            if not near:
                any_dir = [o for o in orders if abs(o.placed - r.when) <= w]
                row["found"] = "no" + (" (only opposite direction)" if any_dir else "")
            else:
                o = min(near, key=lambda o: abs(o.placed - r.when))
                tr = trades[trades.placed == o.placed] if not trades.empty else trades
                row.update(
                    found="yes",
                    code_placed=o.placed.strftime("%H:%M"),
                    code_entry=round(o.entry, 1),
                    code_stop=round(o.stop, 1),
                    code_target=round(o.target, 1),
                    risk_mine=round(abs(r.entry - r.stop), 1) if pd.notna(r.stop) else None,
                    risk_code=round(abs(o.entry - o.stop), 1),
                    code_result=(tr.reason.iloc[0] if not tr.empty else "not filled / skipped"),
                    sweep=o.meta.get("sweep"),
                )
            rows.append(row)
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tradekit.compare")
    ap.add_argument("setups")
    ap.add_argument("--tz-offset", type=float, default=2.0, help="hours the chart clock is ahead of UTC")
    ap.add_argument("--preset", choices=["cristian", "default"], default="cristian")
    ap.add_argument("--window", type=int, default=30, help="minutes either side of your time")
    ap.add_argument("--ltf", help="confirming timeframe (M1, M3, M5)")
    ap.add_argument("--no-bias", action="store_true")
    a = ap.parse_args(argv)
    p = smc.cristian() if a.preset == "cristian" else smc.SMCParams()
    if a.ltf:
        p = replace(p, ltf=a.ltf)
    if a.no_bias:
        p = replace(p, use_bias=False)
    res = compare(load_setups(a.setups, a.tz_offset), p, a.window)
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(res.to_string(index=False))
    print(f"\nfound {int((res.found == 'yes').sum())} of {len(res)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
