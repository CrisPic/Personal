"""Run a strategy over stored data and report results.

    python -m tradekit.backtest A EURUSD GBPUSD US30 --start 2023-01 --end 2025-10
    python -m tradekit.backtest B GBPJPY --tf M2
    python -m tradekit.backtest A all --rr 2.5 --risk 0.5

Writes results/{strategy}_{instrument}_trades.csv and prints a summary with
win rate, R, drawdown and the FTMO 2-Step pass rate from weekly start dates.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

from . import ftmo, stats
from .data.instruments import get_instrument, load_instruments
from .data.store import load_m1
from .engine import Costs, simulate
from .strategies import ema_fib, smc

RESULTS = Path(__file__).resolve().parents[1] / "results"


def run_one(strategy: str, name: str, start: str | None, end: str | None, params) -> pd.DataFrame:
    inst = get_instrument(name)
    m1 = load_m1(name, start, _end_exclusive(end))
    if strategy == "A":
        orders = smc.generate(m1, inst, params)
    else:
        orders = ema_fib.generate(m1, inst, params)
    costs = Costs(commission=inst.commission_pips * inst.pip, stop_slippage=0.2 * inst.pip)
    trades = simulate(m1, orders, costs)
    if strategy == "B":
        trades = ema_fib.apply_daily_limits(trades, params)
    if not trades.empty:
        trades.insert(0, "instrument", name)
    print(f"  {name}: {len(orders)} orders, {len(trades)} trades")
    return trades


def report(trades: pd.DataFrame, risk: float, title: str) -> str:
    lines = [f"\n=== {title} ==="]
    s = stats.summary(trades)
    if not s["trades"]:
        return "\n".join(lines + ["no trades"])
    lines.append(
        f"trades {s['trades']}  ({s['trades_per_week']:.1f}/week)  win rate {s['win_rate']:.1%}  "
        f"avg {s['avg_R']:+.3f}R  total {s['total_R']:+.1f}R  PF {s['profit_factor']:.2f}"
    )
    lines.append(f"max drawdown {s['max_dd_R']:.1f}R  worst losing streak {s['worst_losing_streak']}  avg win {s['avg_win_R']:.2f}R")
    lines.append("by year:\n" + stats.by_year(trades).round(3).to_string())
    f = ftmo.summarize(ftmo.replay(trades, risk_pct=risk))
    lines.append(
        f"FTMO 2-Step at {risk}% risk, weekly starts: pass rate {f['pass_rate']:.0%} of {f['finished']} finished "
        f"(fail daily {f['fail_daily']}, fail max loss {f['fail_max']}), median {f['median_days_to_pass']:.0f} days to pass"
    )
    if "sweep" in trades:
        sw = trades.groupby("sweep")["R"].agg(["count", "mean"]).round(3)
        lines.append("with / without liquidity sweep (count, avg R):\n" + sw.to_string())
    return "\n".join(lines)


def _end_exclusive(end: str | None) -> str | None:
    if not end:
        return None
    y, m = map(int, end.split("-")[:2])
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}-01"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tradekit.backtest")
    ap.add_argument("strategy", choices=["A", "B"])
    ap.add_argument("instruments", nargs="+")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--risk", type=float, default=0.5, help="risk per trade in percent")
    ap.add_argument("--rr", type=float, help="Strategy A: fixed risk-reward")
    ap.add_argument("--tf", help="Strategy B: timeframe of the EMA cross (M2 or M3)")
    ap.add_argument("--no-bias", action="store_true", help="Strategy A: ignore the H4 bias")
    a = ap.parse_args(argv)

    names = list(load_instruments()) if a.instruments == ["all"] else a.instruments
    if a.strategy == "A":
        params = smc.SMCParams()
        if a.rr:
            params = replace(params, rr=a.rr)
        if a.no_bias:
            params = replace(params, use_bias=False)
    else:
        params = ema_fib.EMAFibParams()
        if a.tf:
            params = replace(params, tf=a.tf)

    RESULTS.mkdir(exist_ok=True)
    print(f"Strategy {a.strategy} {params}")
    all_trades = []
    for name in names:
        try:
            t = run_one(a.strategy, name, a.start, a.end, params)
        except FileNotFoundError as exc:
            print(f"  {name}: skipped ({exc})")
            continue
        t.to_csv(RESULTS / f"{a.strategy}_{name}_trades.csv", index=False)
        print(report(t, a.risk, f"Strategy {a.strategy} · {name}"))
        all_trades.append(t)
    if len(all_trades) > 1:
        combined = pd.concat(all_trades).sort_values("entry_time").reset_index(drop=True)
        print(report(combined, a.risk, f"Strategy {a.strategy} · all instruments together"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
