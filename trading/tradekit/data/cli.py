"""Command line for the market data pipeline.

    python -m tradekit.data.cli download EURUSD GBPUSD --start 2023-01 --end 2024-12
    python -m tradekit.data.cli download all --start 2024-01 --end 2024-12
    python -m tradekit.data.cli check EURUSD
    python -m tradekit.data.cli show EURUSD H4 --start 2024-03-01 --end 2024-03-08
"""
from __future__ import annotations

import argparse
import calendar
import sys
from datetime import date

import pandas as pd

from . import binance, dukascopy
from .instruments import get_instrument, load_instruments
from .resample import resample
from .store import load_m1, month_path, save_month
from .validate import validate


def months(start: str, end: str):
    y, m = map(int, start.split("-")[:2])
    ey, em = map(int, end.split("-")[:2])
    while (y, m) <= (ey, em):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def download(names: list[str], start: str, end: str, force: bool = False) -> int:
    today = date.today()
    for name in names:
        inst = get_instrument(name)
        for y, m in months(start, end):
            if (y, m) > (today.year, today.month):
                break
            current = (y, m) == (today.year, today.month)
            path = month_path(name, y, m)
            if path.exists() and not force and not current:
                print(f"{name} {y}-{m:02d}: already stored")
                continue
            if inst.source == "dukascopy":
                last = today if current else date(y, m, calendar.monthrange(y, m)[1])
                df = dukascopy.download_range(inst, date(y, m, 1), last)
            else:
                if current:
                    print(f"{name} {y}-{m:02d}: Binance publishes a month after it ends; skipped")
                    continue
                df = binance.download_month(inst, y, m)
            if df.empty:
                print(f"{name} {y}-{m:02d}: no data")
                continue
            rep = validate(df, inst)
            save_month(df, name, y, m)
            status = "ok" if rep.ok else "CHECK"
            print(f"{name} {y}-{m:02d}: {len(df):,} candles [{status}]")
            for line in rep.errors:
                print(f"    ERROR {line}")
    return 0


def check(names: list[str]) -> int:
    failed = False
    for name in names:
        rep = validate(load_m1(name), get_instrument(name))
        print(rep)
        failed |= not rep.ok
    return 1 if failed else 0


def show(name: str, timeframe: str, start: str | None, end: str | None) -> int:
    inst = get_instrument(name)
    df = resample(load_m1(name, start, end), timeframe, inst.chart_clock)
    with pd.option_context("display.max_rows", 40, "display.width", 120):
        print(df)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tradekit.data")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download", help="download M1 history month by month")
    d.add_argument("instruments", nargs="+", help="names from config/instruments.yaml, or 'all'")
    d.add_argument("--start", required=True, help="first month, YYYY-MM")
    d.add_argument("--end", required=True, help="last month, YYYY-MM")
    d.add_argument("--force", action="store_true", help="download months that are already stored")
    c = sub.add_parser("check", help="validate stored data")
    c.add_argument("instruments", nargs="+")
    s = sub.add_parser("show", help="print candles on any timeframe")
    s.add_argument("instrument")
    s.add_argument("timeframe")
    s.add_argument("--start")
    s.add_argument("--end")
    a = p.parse_args(argv)

    def expand(names):
        return list(load_instruments()) if names == ["all"] else names

    if a.cmd == "download":
        return download(expand(a.instruments), a.start, a.end, a.force)
    if a.cmd == "check":
        return check(expand(a.instruments))
    return show(a.instrument, a.timeframe, a.start, a.end)


if __name__ == "__main__":
    sys.exit(main())
