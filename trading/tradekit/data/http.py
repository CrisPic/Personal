"""Small HTTP helper with retries. A 404 means "no data for that period".

Dukascopy answers 503 when it is busy or throttling, sometimes for many
minutes, so retries back off up to about 5 minutes per request with jitter.
"""
from __future__ import annotations

import random
import time

import requests

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "tradekit-data/0.1"

RETRY_STATUS = (429, 500, 502, 503, 504)


class FetchError(RuntimeError):
    """A URL still failed after every retry."""


def fetch(url: str, retries: int = 8, timeout: float = 30, max_delay: float = 60, sleep=time.sleep) -> bytes:
    """Return the body, b"" on 404, and raise FetchError after `retries` retries."""
    delay = 2.0
    last = ""
    for attempt in range(retries + 1):
        try:
            resp = SESSION.get(url, timeout=timeout)
            if resp.status_code == 404:
                return b""
            if resp.status_code == 200:
                return resp.content
            if resp.status_code not in RETRY_STATUS:
                raise FetchError(f"{url}: HTTP {resp.status_code}")
            last = f"HTTP {resp.status_code}"
        except (requests.ConnectionError, requests.Timeout) as exc:
            last = type(exc).__name__
        if attempt < retries:
            sleep(delay * random.uniform(0.7, 1.3))
            delay = min(delay * 2, max_delay)
    raise FetchError(f"{url}: gave up after {retries + 1} attempts ({last})")
