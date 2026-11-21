"""FTMO 2-Step challenge replay.

Trades are replayed in time order from many start dates, with a fixed risk per
trade, against the FTMO 2-Step rules (check the current rules before trading):

    Phase 1: +10% target    Phase 2: +5% target
    Max daily loss: 5% of the initial balance (day = Prague/Rome midnight)
    Max loss: 10% of the initial balance
    At least 4 trading days per phase; no time limit

Approximation: losses are counted when trades close, so a large floating loss
inside a trade that later recovers is not seen. With one open trade at a time
and 0.5% risk this barely matters; with larger risk it flatters the result.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class FTMORules:
    targets: tuple[float, ...] = (10.0, 5.0)
    max_daily_loss: float = 5.0
    max_loss: float = 10.0
    min_days: int = 4
    daily_stop: float | None = 2.0  # our own rule: stop trading for the day at -2%


def replay(trades: pd.DataFrame, risk_pct: float = 0.5, rules: FTMORules = FTMORules(), start_every: str = "7D") -> pd.DataFrame:
    """One row per start date: outcome ('pass', 'fail_daily', 'fail_max', 'unfinished') and days taken."""
    if trades.empty:
        return pd.DataFrame()
    tr = trades.sort_values("exit_time").reset_index(drop=True)
    times = tr["exit_time"]
    days = times.dt.tz_convert("Europe/Rome").dt.date.to_numpy()
    pnl = tr["R"].to_numpy(float) * risk_pct
    tn = times.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy()
    starts = pd.date_range(times.iloc[0].floor("D"), times.iloc[-1], freq=start_every)
    rows = []
    for s in starts:
        i0 = int(np.searchsorted(tn, np.datetime64(s.tz_convert("UTC").tz_localize(None), "ns")))
        rows.append({"start": s, **_run(days[i0:], pnl[i0:], tn[i0:], rules)})
    return pd.DataFrame(rows)


def _run(days, pnl, times, rules):
    i, n = 0, len(pnl)
    t0 = times[0] if n else None
    for phase, target in enumerate(rules.targets, 1):
        bal, traded_days, day, day_pnl, day_stopped = 0.0, set(), None, 0.0, False
        while i < n:
            if days[i] != day:
                day, day_pnl, day_stopped = days[i], 0.0, False
            if day_stopped:
                i += 1
                continue
            bal += pnl[i]
            day_pnl += pnl[i]
            traded_days.add(day)
            i += 1
            if day_pnl <= -rules.max_daily_loss:
                return {"outcome": "fail_daily", "phase": phase, "days": _days(t0, times[i - 1])}
            if bal <= -rules.max_loss:
                return {"outcome": "fail_max", "phase": phase, "days": _days(t0, times[i - 1])}
            if rules.daily_stop is not None and day_pnl <= -rules.daily_stop:
                day_stopped = True
            if bal >= target and len(traded_days) >= rules.min_days:
                break
        else:
            return {"outcome": "unfinished", "phase": phase, "days": _days(t0, times[-1]) if n else 0}
    return {"outcome": "pass", "phase": len(rules.targets), "days": _days(t0, times[i - 1])}


def _days(a, b):
    return int((pd.Timestamp(b) - pd.Timestamp(a)) / pd.Timedelta(days=1))


def summarize(replays: pd.DataFrame) -> dict:
    if replays.empty:
        return {"starts": 0}
    finished = replays[replays.outcome != "unfinished"]
    passed = replays[replays.outcome == "pass"]
    return {
        "starts": len(replays),
        "finished": len(finished),
        "pass_rate": len(passed) / len(finished) if len(finished) else float("nan"),
        "median_days_to_pass": float(passed["days"].median()) if len(passed) else float("nan"),
        "fail_daily": int((replays.outcome == "fail_daily").sum()),
        "fail_max": int((replays.outcome == "fail_max").sum()),
    }
