from datetime import date

import pandas as pd
import pytest

from tradekit.data import dukascopy, http
from tradekit.data.instruments import get_instrument


class FakeResp:
    def __init__(self, status, content=b"x"):
        self.status_code, self.content = status, content


def test_fetch_retries_through_503_then_succeeds(monkeypatch):
    replies = iter([FakeResp(503), FakeResp(503), FakeResp(200, b"ok")])
    monkeypatch.setattr(http.SESSION, "get", lambda url, timeout: next(replies))
    waits = []
    assert http.fetch("u", sleep=waits.append) == b"ok"
    assert len(waits) == 2 and waits[1] > waits[0] * 1.0  # backs off


def test_fetch_gives_up_with_fetch_error(monkeypatch):
    monkeypatch.setattr(http.SESSION, "get", lambda url, timeout: FakeResp(503))
    with pytest.raises(http.FetchError, match="503"):
        http.fetch("u", retries=3, sleep=lambda s: None)


def test_fetch_404_means_no_data(monkeypatch):
    monkeypatch.setattr(http.SESSION, "get", lambda url, timeout: FakeResp(404))
    assert http.fetch("u", sleep=lambda s: None) == b""


def test_failed_days_are_reported_not_raised(monkeypatch):
    inst = get_instrument("EURUSD")
    bad_day = date(2024, 1, 3)

    def fake_day(_inst, d):
        if d == bad_day:
            raise http.FetchError("busy")
        idx = pd.DatetimeIndex([pd.Timestamp(d, tz="UTC")], name="time")
        return pd.DataFrame({"open": 1.1, "high": 1.1, "low": 1.1, "close": 1.1, "volume": 1.0, "spread": 0.0}, index=idx)

    monkeypatch.setattr(dukascopy, "download_day", fake_day)
    df, failed = dukascopy.download_range(inst, date(2024, 1, 1), date(2024, 1, 5))
    assert failed == [bad_day]
    assert len(df) == 4
