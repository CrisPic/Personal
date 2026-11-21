# Trading toolkit

Research, backtesting and (later) live tools for prop-firm trading (FTMO 2-Step).
The strategy rules live in the spec doc; this folder holds the code.

**Plan**
1. Strategy rules + data foundation  ← this stage: the M1 data pipeline
2. Backtester with FTMO rules built in
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
