import io
import lzma
import struct
import zipfile
from datetime import date

import numpy as np
import pandas as pd
import pytest

from tradekit.data import binance, dukascopy
from tradekit.data.cli import months
from tradekit.data.instruments import get_instrument, load_instruments
from tradekit.data.resample import resample
from tradekit.data.validate import validate


def bi5(records):
    """Build a Dukascopy-style candle file: >IIIIIf records, LZMA 'alone' format."""
    raw = b"".join(struct.pack(">IIIIIf", *r) for r in records)
    return lzma.compress(raw, format=lzma.FORMAT_ALONE)


def test_config_loads_all_agreed_instruments():
    names = set(load_instruments())
    assert {"EURUSD", "GBPUSD", "US30", "BTCUSD", "ETHUSD", "GBPJPY"} <= names


def test_dukascopy_url_uses_zero_based_month():
    url = dukascopy.day_url("EURUSD", date(2024, 1, 2), "BID")
    assert url.endswith("/EURUSD/2024/00/02/BID_candles_min_1.bi5")


def test_dukascopy_decode_field_order_and_scaling():
    # seconds, open, close, low, high, volume
    blob = bi5([(0, 108000, 108010, 107990, 108020, 1.5), (60, 108010, 108005, 108000, 108015, 2.0), (120, 1, 1, 1, 1, 0.0)])
    df = dukascopy.decode_candles(blob, date(2024, 1, 2), 100000)
    assert len(df) == 2  # zero-volume padding dropped
    first = df.iloc[0]
    assert (first.open, first.high, first.low, first.close) == (1.08, 1.0802, 1.0799, 1.0801)
    assert df.index[1] == pd.Timestamp("2024-01-02 00:01", tz="UTC")


def test_dukascopy_empty_day():
    assert dukascopy.decode_candles(b"", date(2024, 1, 6), 100000).empty


def _zip_csv(rows):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("x.csv", "\n".join(",".join(map(str, r)) for r in rows))
    return buf.getvalue()


@pytest.mark.parametrize("scale", [1_000, 1_000_000])  # ms (to 2024) and us (2025 on)
def test_binance_decode_handles_ms_and_us(scale):
    t0 = 1_704_067_200  # 2024-01-01 00:00 UTC
    rows = [[t0 * scale, 42000, 42100, 41900, 42050, 3.2, 0, 0, 0, 0, 0, 0],
            [(t0 + 60) * scale, 42050, 42060, 42000, 42010, 1.1, 0, 0, 0, 0, 0, 0]]
    df = binance.decode_month(_zip_csv(rows), spread=10.0)
    assert df.index[0] == pd.Timestamp("2024-01-01", tz="UTC")
    assert df["close"].tolist() == [42050, 42010]
    assert (df["spread"] == 10.0).all()


def _m1(start, minutes, price=1.1):
    idx = pd.date_range(start, periods=minutes, freq="1min", tz="UTC")
    p = price + np.arange(minutes) * 1e-5
    return pd.DataFrame({"open": p, "high": p + 2e-5, "low": p - 2e-5, "close": p + 1e-5, "volume": 1.0, "spread": 1e-5}, index=idx)


def test_fx_h4_candles_open_at_server_midnight_winter_and_summer():
    # Winter: New York close 17:00 EST = 22:00 UTC. Summer: 17:00 EDT = 21:00 UTC.
    winter = resample(_m1("2024-01-15 20:00", 6 * 60), "H4", "fx")
    assert pd.Timestamp("2024-01-15 22:00", tz="UTC") in winter.index
    summer = resample(_m1("2024-07-15 19:00", 6 * 60), "H4", "fx")
    assert pd.Timestamp("2024-07-15 21:00", tz="UTC") in summer.index


def test_resample_ohlc_aggregation():
    m1 = _m1("2024-01-15 22:00", 15)
    m15 = resample(m1, "M15", "fx")
    assert len(m15) == 1
    row = m15.iloc[0]
    assert row.open == m1.open.iloc[0]
    assert row.close == m1.close.iloc[-1]
    assert row.high == m1.high.max() and row.low == m1.low.min()
    assert row.volume == 15


def test_crypto_d1_cut_at_utc_midnight():
    d1 = resample(_m1("2024-01-01 22:00", 4 * 60, price=42000), "D1", "utc")
    assert list(d1.index) == [pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2024-01-02", tz="UTC")]


def test_validate_flags_wrong_divisor():
    bad = _m1("2024-01-15 08:00", 60) * 10  # as if divided by 10_000 instead of 100_000
    bad.index = _m1("2024-01-15 08:00", 60).index
    rep = validate(bad, get_instrument("EURUSD"))
    assert not rep.ok and "wrong divisor" in rep.errors[0]


def test_validate_flags_broken_candles_and_passes_clean_data():
    inst = get_instrument("EURUSD")
    clean = _m1("2024-01-15 08:00", 60)
    assert validate(clean, inst).ok
    broken = clean.copy()
    broken.iloc[5, broken.columns.get_loc("high")] = 1.0
    assert not validate(broken, inst).ok


def test_months_crosses_year():
    assert list(months("2023-11", "2024-02")) == [(2023, 11), (2023, 12), (2024, 1), (2024, 2)]
