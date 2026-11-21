"""Data checks run after every download. A backtest is only as good as its candles."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .instruments import Instrument


@dataclass
class Report:
    instrument: str
    rows: int
    first: pd.Timestamp | None
    last: pd.Timestamp | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def __str__(self) -> str:
        lines = [f"{self.instrument}: {self.rows:,} M1 candles, {self.first} to {self.last}"]
        lines += [f"  ERROR   {e}" for e in self.errors]
        lines += [f"  warning {w}" for w in self.warnings]
        if self.ok and not self.warnings:
            lines.append("  all checks passed")
        return "\n".join(lines)


def validate(df: pd.DataFrame, inst: Instrument, max_gap_minutes: int = 30) -> Report:
    rep = Report(inst.name, len(df), df.index.min() if len(df) else None, df.index.max() if len(df) else None)
    if df.empty:
        rep.errors.append("no data")
        return rep

    if not df.index.is_monotonic_increasing:
        rep.errors.append("timestamps are not sorted")
    dupes = int(df.index.duplicated().sum())
    if dupes:
        rep.errors.append(f"{dupes} duplicate timestamps")

    bad_ohlc = (df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1))
    if bad_ohlc.any():
        rep.errors.append(f"{int(bad_ohlc.sum())} candles where high/low do not contain open/close")

    lo, hi = inst.price_range
    out_of_range = (df["close"] < lo) | (df["close"] > hi)
    if out_of_range.any():
        rep.errors.append(
            f"{int(out_of_range.sum())} closes outside {lo}-{hi} "
            f"(e.g. {df.loc[out_of_range, 'close'].iloc[0]}): wrong divisor or bad data?"
        )

    if "spread" in df and df["spread"].notna().any():
        med = df["spread"].median() / inst.pip
        if med <= 0:
            rep.warnings.append("median spread is zero")
        elif med > 5 and inst.source == "dukascopy":
            rep.warnings.append(f"median spread is {med:.2f} pips, unusually wide")

    gaps = df.index.to_series().diff().dt.total_seconds().div(60)
    # Weekend closes are normal for FX and indices; only flag gaps on weekdays.
    weekday_gaps = gaps[(gaps > max_gap_minutes) & (df.index.dayofweek < 5) & (gaps < 60 * 40)]
    if inst.source == "binance":
        weekday_gaps = gaps[gaps > max_gap_minutes]
    if len(weekday_gaps):
        worst = weekday_gaps.sort_values(ascending=False).head(3)
        listed = ", ".join(f"{int(m)} min before {t:%Y-%m-%d %H:%M}" for t, m in worst.items())
        rep.warnings.append(f"{len(weekday_gaps)} gaps over {max_gap_minutes} min (largest: {listed})")
    return rep
