"""Grid search with an in-sample / out-of-sample split.

    python -m tradekit.sweep A EURUSD GBPUSD --grid ltf=M1,M3,M5 rr=2,3 min_cost=0,5,10
    python -m tradekit.sweep B all --grid tf=M2,M3 min_cost=0,5 --split 2025-01

Each combination runs over all stored data. Results are split at --split:
pick settings on the in-sample part (before), then check them on the
out-of-sample part (after), which the choice never saw. A setting that only
works in-sample is noise. Writes results/sweep_{strategy}[_{tag}].csv.

`min_cost` is not a strategy parameter: it skips setups whose risk is under
N times the trading cost (see engine.cost_filter).
"""
from __future__ import annotations

import argparse
import itertools
import sys
from dataclasses import fields, replace

import pandas as pd

from .backtest import RESULTS, _end_exclusive, costs_for
from .data.instruments import get_instrument, load_instruments
from .data.store import load_m1
from .engine import cost_filter, simulate
from .strategies import ema_fib, smc

STRATS = {"A": (smc, smc.SMCParams), "B": (ema_fib, ema_fib.EMAFibParams)}


def _parse_value(v: str, current):
    if isinstance(current, bool):
        return v.lower() in ("1", "true", "yes")
    if isinstance(current, int):
        return int(v)
    if isinstance(current, float):
        return float(v)
    return v


def parse_grid(items: list[str], base) -> list[dict]:
    names = {f.name for f in fields(base)} | {"min_cost"}
    keys, values = [], []
    for it in items:
        k, _, vs = it.partition("=")
        if k not in names:
            raise SystemExit(f"unknown parameter {k!r}; choose from {sorted(names)}")
        cur = 0.0 if k == "min_cost" else getattr(base, k)
        keys.append(k)
        values.append([_parse_value(v, cur) for v in vs.split(",")])
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _stats(r: pd.Series) -> dict:
    if r.empty:
        return {"n": 0, "avg_R": float("nan"), "win": float("nan"), "pf": float("nan"), "total_R": 0.0}
    w, l = r[r > 0].sum(), -r[r <= 0].sum()
    return {"n": len(r), "avg_R": r.mean(), "win": (r > 0).mean(), "pf": w / l if l > 0 else float("inf"), "total_R": r.sum()}


def run(strategy: str, names: list[str], grid: list[dict], split: str, start=None, end=None) -> pd.DataFrame:
    mod, P = STRATS[strategy]
    cut = pd.Timestamp(split, tz="UTC")
    rows = []
    for name in names:
        inst = get_instrument(name)
        m1 = load_m1(name, start, _end_exclusive(end))
        costs = costs_for(inst)
        cache: dict = {}
        for combo in grid:
            params = replace(P(), **{k: v for k, v in combo.items() if k != "min_cost"})
            key = repr(params)
            if key not in cache:
                cache[key] = mod.generate(m1, inst, params)
            orders = cost_filter(m1, cache[key], costs, combo.get("min_cost", 0.0))
            tr = simulate(m1, orders, costs)
            if strategy == "B":
                tr = ema_fib.apply_daily_limits(tr, params)
            for part, sel in (("in", lambda t: t.entry_time < cut), ("out", lambda t: t.entry_time >= cut)):
                sub = tr[sel(tr)] if not tr.empty else tr
                s = _stats(sub["R"] if not sub.empty else pd.Series(dtype=float))
                s["avg_R_gross"] = sub["R_gross"].mean() if not sub.empty else float("nan")
                rows.append({"instrument": name, **combo, "sample": part, **s})
            print(f"  {name} {combo}: {len(tr)} trades", flush=True)
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tradekit.sweep")
    ap.add_argument("strategy", choices=list(STRATS))
    ap.add_argument("instruments", nargs="+")
    ap.add_argument("--grid", nargs="+", required=True, help="param=v1,v2 ...")
    ap.add_argument("--split", default="2025-01-01", help="out-of-sample starts here")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    names = list(load_instruments()) if a.instruments == ["all"] else a.instruments
    grid = parse_grid(a.grid, STRATS[a.strategy][1]())
    print(f"{len(grid)} combinations x {len(names)} instruments")
    res = run(a.strategy, names, grid, a.split, a.start, a.end)
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / (f"sweep_{a.strategy}_{a.tag}.csv" if a.tag else f"sweep_{a.strategy}.csv")
    res.to_csv(out, index=False)

    keys = [k for k in res.columns if k not in ("instrument", "sample", "n", "avg_R", "win", "pf", "total_R", "avg_R_gross")]
    wide = res.pivot_table(index=["instrument", *keys], columns="sample", values=["n", "avg_R", "avg_R_gross", "pf"])
    wide.columns = [f"{v}_{s}" for v, s in wide.columns]
    wide = wide.reset_index().sort_values(["instrument", "avg_R_in"], ascending=[True, False])
    with pd.option_context("display.width", 200, "display.max_rows", 500):
        print(wide.round(3).to_string(index=False))
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
