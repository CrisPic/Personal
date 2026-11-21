# Trading toolkit

Research, backtesting and (later) live tools for prop-firm trading (FTMO 2-Step).
The strategy rules live in the spec doc; this folder holds the code.

**Plan**
1. Strategy rules + data foundation (done)
2. Backtester with FTMO rules built in  ← this stage
3. Parameter tuning and walk-forward validation
4. Alerts, then a risk guard and journal, then execution on cTrader

## Data pipeline

M1 candles are downloaded month by month, checked, and stored as Parquet in
`data/market/{INSTRUMENT}/M1/YYYY-MM.parquet` (UTC). Higher timeframes are
built from M1 on demand, cut on the same clock as the broker charts
(New York close = midnight for FX and indices, UTC for crypto).

| Instrument | Source | Notes |
| --- | --- | --- |
| EURUSD, GBPUSD, GBPJPY | Dukascopy | bid candles + real spread from ask candles |
| US30 | Dukascopy (`USA30IDXUSD`) | |
| BTCUSD, ETHUSD | Binance spot archive | fixed spread from config |

```bash
cd trading
pip install -r requirements.txt
python -m tradekit.data.cli download all --start 2023-01 --end 2025-10
python -m tradekit.data.cli check all
python -m tradekit.data.cli show EURUSD H4 --start 2024-03-04 --end 2024-03-09
python -m pytest
```

Network hosts needed: `datafeed.dukascopy.com`, `data.binance.vision`.
Instruments, divisors and sanity ranges are in `config/instruments.yaml`.

**Not covered yet:** historical high-impact news times for the news filter.
The free ForexFactory feed only has the current week, so history needs another source.

## Backtester

```bash
python -m tradekit.backtest A EURUSD GBPUSD US30 BTCUSD ETHUSD --start 2023-01 --end 2025-10
python -m tradekit.backtest B GBPJPY EURUSD GBPUSD --tf M3
python -m tradekit.backtest A all --rr 2.5 --no-bias
```

| Module | What it does |
| --- | --- |
| `structure.py` | swing points, BOS / CHoCH on candle closes, leg origin, order blocks; no lookahead |
| `strategies/smc.py` | Strategy A: H4 bias, H1 order-block POIs, M1 CHoCH then BOS, Fib + OB entry, fixed RR |
| `strategies/ema_fib.py` | Strategy B: EMA 9/14 cross on M2/M3 in the morning window, 0.62 entry, -0.28 target, daily limits |
| `engine.py` | fills limit orders on M1 bid/ask, stop-first when both are hit in one minute, costs in R |
| `ftmo.py` | replays trades against FTMO 2-Step rules from weekly start dates; pass rate and days to pass |
| `stats.py` | win rate, expectancy, profit factor, drawdown, losing streaks, results by year |

Trades are written to `results/` (gitignored). On a random walk both strategies
lose slightly after costs, as they should: a positive result there would mean lookahead.
