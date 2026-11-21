"""Small HTTP helper with retries. A 404 means "no data for that period"."""
from __future__ import annotations

import time

import requests

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "tradekit-data/0.1"


def fetch(url: str, retries: int = 4, timeout: float = 30) -> bytes:
    """Return the body, b"" on 404, and raise after `retries` failed attempts."""
    delay = 1.0
    for attempt in range(retries + 1):
        try:
            resp = SESSION.get(url, timeout=timeout)
            if resp.status_code == 404:
                return b""
            if resp.status_code == 200:
                return resp.content
            if resp.status_code not in (429, 500, 502, 503, 504):
                resp.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            if attempt == retries:
                raise
        if attempt == retries:
            raise RuntimeError(f"Giving up on {url} after {retries + 1} attempts")
        time.sleep(delay)
        delay *= 2
    raise AssertionError("unreachable")
