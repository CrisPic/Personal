"""Instrument definitions loaded from config/instruments.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "instruments.yaml"


@dataclass(frozen=True)
class Instrument:
    name: str
    source: str
    symbol: str
    pip: float
    chart_clock: str
    price_range: tuple[float, float]
    divisor: int | None = None
    spread_pips: float | None = None
    commission_pips: float = 0.0


def load_instruments(path: Path = CONFIG_PATH) -> dict[str, Instrument]:
    raw = yaml.safe_load(path.read_text())
    out = {}
    for name, cfg in raw.items():
        if cfg["source"] not in ("dukascopy", "binance"):
            raise ValueError(f"{name}: unknown source {cfg['source']!r}")
        if cfg["source"] == "dukascopy" and not cfg.get("divisor"):
            raise ValueError(f"{name}: dukascopy instruments need a divisor")
        if cfg["chart_clock"] not in ("fx", "utc"):
            raise ValueError(f"{name}: chart_clock must be fx or utc")
        out[name] = Instrument(
            name=name,
            source=cfg["source"],
            symbol=cfg["symbol"],
            pip=float(cfg["pip"]),
            chart_clock=cfg["chart_clock"],
            price_range=tuple(cfg["price_range"]),
            divisor=cfg.get("divisor"),
            spread_pips=cfg.get("spread_pips"),
            commission_pips=float(cfg.get("commission_pips", 0)),
        )
    return out


def get_instrument(name: str) -> Instrument:
    instruments = load_instruments()
    try:
        return instruments[name]
    except KeyError:
        raise KeyError(f"Unknown instrument {name!r}. Known: {', '.join(instruments)}") from None
