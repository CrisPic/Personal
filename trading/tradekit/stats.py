"""Trade statistics in R."""
from __future__ import annotations

import numpy as np
import pandas as pd


def summary(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0}
    r = trades["R"].to_numpy(float)
    eq = np.cumsum(r)
    dd = eq - np.maximum.accumulate(np.r_[0, eq])[1:]
    wins, losses = r[r > 0], r[r <= 0]
    streak = worst = 0
    for x in r:
        streak = streak + 1 if x <= 0 else 0
        worst = max(worst, streak)
    days = trades["entry_time"].dt.tz_convert("Europe/Rome").dt.date.nunique()
    return {
        "trades": len(r),
        "win_rate": len(wins) / len(r),
        "avg_R": float(r.mean()),
        "total_R": float(r.sum()),
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
        "max_dd_R": float(-dd.min()),
        "worst_losing_streak": worst,
        "avg_win_R": float(wins.mean()) if len(wins) else 0.0,
        "trades_per_week": len(r) / max(days / 5, 1),
    }


def by_year(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    y = trades["entry_time"].dt.year
    return trades.groupby(y)["R"].agg(trades="count", win_rate=lambda s: (s > 0).mean(), total_R="sum", avg_R="mean")
