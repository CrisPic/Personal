"""Make a review page of every setup the code finds, for Cristian to label.

    python -m tradekit.review US30 --start 2026-11-16 --end 2026-11-20
    python -m tradekit.review EURUSD --start 2025-03-03 --end 2025-03-07 --poi M15,H1

For each candidate the page shows the M1 chart up to the moment the order
would be placed (nothing after it, so no hindsight), the zone it reacted
from, the broken level and the planned entry / stop / target. Mark each one
Take or Skip and press "Download labels": that saves a CSV to send back.
The outcome of each candidate is in the CSV next to the page, not on the page.
Times on the page are Italian time.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .backtest import RESULTS, costs_for
from .data.instruments import get_instrument
from .data.store import load_m1
from .engine import simulate
from .strategies import smc

W, H, PAD = 760, 300, 40


def candidates(name: str, start: str, end: str, pois: list[str], p: smc.SMCParams):
    inst = get_instrument(name)
    lo = (pd.Timestamp(start) - pd.Timedelta(days=12)).strftime("%Y-%m-%d")
    hi = (pd.Timestamp(end) + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    m1 = load_m1(name, lo, hi)
    s, e = pd.Timestamp(start, tz="Europe/Rome"), pd.Timestamp(end, tz="Europe/Rome") + pd.Timedelta(days=1)
    orders = []
    for tf in pois:
        for o in smc.generate(m1, inst, replace(p, poi_tf=tf)):
            if s <= o.placed < e:
                o.meta["poi_tf"] = tf
                orders.append(o)
    # same setup found from two zone timeframes: keep one
    seen, uniq = set(), []
    for o in sorted(orders, key=lambda o: o.placed):
        k = (o.placed, o.direction, round(o.entry, 5))
        if k not in seen:
            seen.add(k)
            uniq.append(o)
    outcome = {}
    for o in uniq:
        tr = simulate(m1, [o], costs_for(inst))
        outcome[id(o)] = (tr.reason.iloc[0], round(float(tr.R.iloc[0]), 2)) if not tr.empty else ("not filled", 0.0)
    return m1, uniq, outcome


def svg(m1: pd.DataFrame, o, minutes: int = 120) -> str:
    end = o.placed
    bars = m1[(m1.index >= end - pd.Timedelta(minutes=minutes)) & (m1.index < end)]
    if bars.empty:
        return "<p>no data</p>"
    levels = [o.entry, o.stop, o.target, o.meta["level"]]
    top = max(bars.high.max(), *levels)
    bot = min(bars.low.min(), *levels)
    span = (top - bot) or 1
    y = lambda v: PAD / 2 + (top - v) / span * (H - PAD)
    n = len(bars)
    cw = (W - 70) / max(n, 1)
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img">']
    zl, zh = o.meta["zone_low"], o.meta["zone_high"]
    z1, z2 = max(min(y(zh), H - PAD / 2), PAD / 2), max(min(y(zl), H - PAD / 2), PAD / 2)
    if z2 - z1 > 1:  # the zone, clipped to the chart; it may sit off-screen
        parts.append(f'<rect x="0" y="{z1:.1f}" width="{W-70}" height="{z2-z1:.1f}" class="zone"/>')
    for i, (t, r) in enumerate(bars.iterrows()):
        x = i * cw + cw / 2
        up = r.close >= r.open
        parts.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y(r.high):.1f}" y2="{y(r.low):.1f}" class="wick"/>')
        b1, b2 = y(max(r.open, r.close)), y(min(r.open, r.close))
        parts.append(f'<rect x="{x-cw*0.35:.1f}" y="{b1:.1f}" width="{cw*0.7:.1f}" height="{max(b2-b1,0.8):.1f}" class="{"up" if up else "dn"}"/>')
    for v, cls, lab in ((o.meta["level"], "lvl", "CoC"), (o.entry, "ent", "entry"), (o.stop, "stp", "stop"), (o.target, "tgt", "target")):
        parts.append(f'<line x1="0" x2="{W-70}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="{cls}"/>')
        parts.append(f'<text x="{W-66}" y="{y(v)+4:.1f}" class="{cls}t">{lab} {v:.5g}</text>')
    t0 = bars.index[0].tz_convert("Europe/Rome").strftime("%H:%M")
    parts.append(f'<text x="2" y="{H-4}" class="ax">{t0}</text><text x="{W-110}" y="{H-4}" class="ax">order {end.tz_convert("Europe/Rome"):%H:%M}</text>')
    parts.append("</svg>")
    return "".join(parts)


def page(name, m1, orders) -> str:
    cards = []
    for i, o in enumerate(orders):
        when = o.placed.tz_convert("Europe/Rome")
        rr = abs(o.target - o.entry) / abs(o.entry - o.stop)
        cards.append(f"""
<section class="card" id="c{i}">
  <h2>#{i+1} · {when:%a %d %b %H:%M} · {"LONG" if o.direction == 1 else "SHORT"}</h2>
  <p class="meta">{o.meta['poi_tf']} zone {o.meta['zone_low']:.5g}–{o.meta['zone_high']:.5g} · sweep {"yes" if o.meta['sweep'] else "no"} · risk {abs(o.entry-o.stop):.4g} · RR {rr:.1f}</p>
  {svg(m1, o)}
  <div class="pick">
    <label><input type="radio" name="c{i}" value="take"> Take</label>
    <label><input type="radio" name="c{i}" value="skip"> Skip</label>
    <input type="text" name="n{i}" placeholder="why (optional)">
  </div>
</section>""")
    rows = [{"id": i + 1, "placed": o.placed.isoformat(), "direction": o.direction, "entry": o.entry, "stop": o.stop} for i, o in enumerate(orders)]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(name)} setup review</title>
<style>
:root{{--bg:#fafaf7;--fg:#1d1d1b;--mut:#6b6b66;--card:#fff;--line:#e3e2dc;--up:#2f8f5b;--dn:#c2453d;--zone:rgba(120,120,200,.15)}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151513;--fg:#ecebe6;--mut:#9a9a93;--card:#1e1e1b;--line:#33332f;--zone:rgba(140,140,230,.18)}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;margin:0;padding:16px;max-width:820px;margin:auto}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:14px 0}}
h1{{font-size:20px}} h2{{font-size:16px;margin:0 0 4px}} .meta{{color:var(--mut);margin:0 0 6px;font-size:13px}}
.zone{{fill:var(--zone)}} .wick{{stroke:var(--mut);stroke-width:1}} .up{{fill:var(--up)}} .dn{{fill:var(--dn)}}
.lvl{{stroke:var(--mut);stroke-dasharray:4 3}} .ent{{stroke:#2a6fdb}} .stp{{stroke:var(--dn)}} .tgt{{stroke:var(--up)}}
text{{font-size:10px;fill:var(--mut)}} .entt{{fill:#2a6fdb}} .stpt{{fill:var(--dn)}} .tgtt{{fill:var(--up)}}
.pick{{display:flex;gap:14px;align-items:center;flex-wrap:wrap}} .pick input[type=text]{{flex:1;min-width:160px;padding:4px 6px}}
button{{position:sticky;bottom:12px;padding:10px 16px;font-size:15px;border-radius:8px;border:0;background:#2a6fdb;color:#fff}}
</style></head><body>
<h1>{html.escape(name)}: {len(orders)} setups the code found</h1>
<p class="meta">Each chart stops when the order would be placed. Mark Take if you would have placed this order, Skip if not. Italian time.</p>
{''.join(cards)}
<button onclick="dl()">Download labels</button>
<script>
const rows={json.dumps(rows)};
function dl(){{let out="id,placed,direction,entry,stop,label,note\\n";
 rows.forEach((r,i)=>{{const c=document.querySelector('input[name=c'+i+']:checked');const n=document.querySelector('input[name=n'+i+']').value.replace(/[",\\n]/g,' ');
 out+=[r.id,r.placed,r.direction,r.entry,r.stop,c?c.value:"",n].join(",")+"\\n"}});
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([out],{{type:"text/csv"}}));a.download="{name}_labels.csv";a.click()}}
</script></body></html>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tradekit.review")
    ap.add_argument("instrument")
    ap.add_argument("--start", required=True, help="first day, YYYY-MM-DD (Italian time)")
    ap.add_argument("--end", required=True, help="last day, YYYY-MM-DD")
    ap.add_argument("--poi", default="M15,H1", help="zone timeframes, comma-separated")
    ap.add_argument("--swing", type=int, default=3, help="M1 swing size for the CoC")
    ap.add_argument("--sweep", action="store_true", help="only setups with a liquidity sweep")
    ap.add_argument("--out", default=str(RESULTS / "review"))
    a = ap.parse_args(argv)
    p = smc.cristian(require_sweep=a.sweep, swing_n_ltf=a.swing)
    m1, orders, outcome = candidates(a.instrument, a.start, a.end, a.poi.split(","), p)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{a.instrument}_{a.start}_{a.end}"
    (out / f"{stem}.html").write_text(page(a.instrument, m1, orders), encoding="utf-8")
    pd.DataFrame([{"id": i + 1, "placed": o.placed, "direction": o.direction, "entry": o.entry, "stop": o.stop,
                   "target": o.target, "poi_tf": o.meta["poi_tf"], "sweep": o.meta["sweep"],
                   "outcome": outcome[id(o)][0], "R": outcome[id(o)][1]} for i, o in enumerate(orders)]
                 ).to_csv(out / f"{stem}_outcomes.csv", index=False)
    print(f"{len(orders)} candidates -> {out / (stem + '.html')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
