import numpy as np
import pandas as pd
import pytest

from tradekit import ftmo, stats
from tradekit.data.instruments import get_instrument
from tradekit.engine import Costs, Order, simulate
from tradekit.strategies import ema_fib, smc
from tradekit.structure import find_breaks, swing_points


def candles(closes, start="2024-01-15 08:00", freq="1min", wick=0.0):
    c = np.asarray(closes, float)
    o = np.r_[c[0], c[:-1]]
    idx = pd.date_range(start, periods=len(c), freq=freq, tz="UTC")
    return pd.DataFrame(
        {"open": o, "high": np.maximum(o, c) + wick, "low": np.minimum(o, c) - wick, "close": c, "volume": 1.0, "spread": 0.0},
        index=idx,
    )


# ---------- structure ----------

def test_swing_points_no_lookahead_shape():
    h = np.array([1, 2, 5, 2, 1, 3, 6, 3, 1], float)
    sh, _ = swing_points(h, h, 2)
    assert list(np.flatnonzero(sh)) == [2, 6]


def test_bos_and_choch_need_a_close():
    # up leg, swing high at 1.10, pullback, then a wick above (no close), then a close above
    closes = [1.00, 1.05, 1.10, 1.07, 1.04, 1.03, 1.06, 1.09, 1.095, 1.12, 1.13]
    df = candles(closes)
    df.iloc[8, df.columns.get_loc("high")] = 1.11  # wick above 1.10, close below
    ev = find_breaks(df, n=2)
    ups = [e for e in ev if e.direction == 1]
    assert ups, "expected a bullish break"
    first = ups[0]
    assert first.bar == 9  # the candle that closed above, not the wick
    assert first.level == pytest.approx(1.10)
    assert first.origin_price == pytest.approx(1.03)  # lowest low between swing and break
    assert first.known_at == df.index[9] + pd.Timedelta(minutes=1)


def test_second_break_same_way_is_bos_opposite_is_choch():
    up = list(np.linspace(1.0, 1.2, 10)) + [1.17, 1.15, 1.18, 1.25, 1.3]
    up += [1.27, 1.24, 1.26, 1.33, 1.36]  # second higher high: BOS
    up += [1.3, 1.22, 1.15, 1.1, 1.05]  # break below the last swing low: CHoCH down
    ev = find_breaks(candles(up), n=2)
    kinds = [(e.direction, e.kind) for e in ev]
    assert (1, "BOS") in kinds
    assert kinds[-1] == (-1, "CHoCH")


# ---------- engine ----------

def test_long_limit_fill_then_target():
    df = candles([1.10, 1.098, 1.095, 1.097, 1.10, 1.105, 1.112, 1.12])
    od = Order(df.index[0], df.index[-1], 1, entry=1.096, stop=1.090, target=1.108)
    tr = simulate(df, [od])
    assert len(tr) == 1
    assert tr.reason[0] == "target" and tr.R[0] == pytest.approx(2.0)


def test_stop_and_target_same_candle_counts_as_stop():
    df = candles([1.10, 1.096, 1.10])
    df.iloc[2, df.columns.get_loc("low")] = 1.085
    df.iloc[2, df.columns.get_loc("high")] = 1.115
    od = Order(df.index[0], df.index[-1], 1, entry=1.097, stop=1.090, target=1.110)
    tr = simulate(df, [od], Costs(stop_slippage=0.0001))
    assert tr.reason[0] == "stop" and tr.R[0] < -1


def test_order_cancelled_when_target_reached_before_fill():
    df = candles([1.10, 1.11, 1.12, 1.09])
    od = Order(df.index[0], df.index[-1], 1, entry=1.095, stop=1.09, target=1.115)
    assert simulate(df, [od]).empty


def test_short_uses_ask_for_exits():
    df = candles([1.10, 1.104, 1.10, 1.095, 1.09])
    df["spread"] = 0.0002
    od = Order(df.index[0], df.index[-1], -1, entry=1.103, stop=1.108, target=1.092)
    tr = simulate(df, [od])
    assert tr.reason[0] == "target"  # ask low 1.0902 <= 1.092


def test_one_position_at_a_time():
    df = candles([1.10, 1.096, 1.097, 1.098, 1.10, 1.11])
    a = Order(df.index[0], df.index[-1], 1, 1.097, 1.09, 1.109)
    b = Order(df.index[2], df.index[-1], 1, 1.099, 1.09, 1.109)
    assert len(simulate(df, [a, b])) == 1


# ---------- FTMO ----------

def _trades(rs, start="2024-01-01 10:00", per_day=1):
    times = [pd.Timestamp(start, tz="UTC") + pd.Timedelta(days=i // per_day, minutes=i % per_day) for i in range(len(rs))]
    return pd.DataFrame({"entry_time": times, "exit_time": times, "R": rs})


def test_ftmo_pass_needs_both_targets_and_min_days():
    tr = _trades([3.0] * 20)  # +1.5% a day at 0.5% risk
    r = ftmo._run(*_args(tr, 0.5), ftmo.FTMORules(daily_stop=None))
    assert r["outcome"] == "pass"


def test_ftmo_daily_loss_fails():
    tr = _trades([-2.0] * 12, per_day=12)  # -12% in one day at 1% risk
    r = ftmo._run(*_args(tr, 1.0), ftmo.FTMORules(daily_stop=None))
    assert r["outcome"] == "fail_daily"


def test_own_daily_stop_prevents_daily_failure():
    tr = _trades([-2.0] * 12, per_day=12)
    r = ftmo._run(*_args(tr, 1.0), ftmo.FTMORules(daily_stop=2.0))
    assert r["outcome"] != "fail_daily"


def _args(tr, risk):
    return (tr.exit_time.dt.tz_convert("Europe/Rome").dt.date.to_numpy(), tr.R.to_numpy() * risk, tr.exit_time.to_numpy())


def test_stats_summary():
    tr = _trades([2, -1, -1, 3, -1])
    s = stats.summary(tr)
    assert s["trades"] == 5 and s["win_rate"] == pytest.approx(0.4)
    assert s["total_R"] == pytest.approx(2) and s["max_dd_R"] == pytest.approx(2)


# ---------- strategies on a random walk: valid orders, no lookahead ----------

@pytest.fixture(scope="module")
def walk():
    rng = np.random.default_rng(7)
    n = 60 * 24 * 30
    c = 1.10 + np.cumsum(rng.normal(0, 0.00012, n))
    df = candles(c, start="2024-03-04 00:00", wick=0.00004)
    df["spread"] = 0.00001
    return df


def _check_orders(orders, df):
    assert orders, "expected some orders on a month of random data"
    for o in orders:
        assert o.placed > df.index[0]
        if o.direction == 1:
            assert o.stop < o.entry < o.target
        else:
            assert o.target < o.entry < o.stop


def test_strategy_a_orders_are_valid(walk):
    inst = get_instrument("EURUSD")
    orders = smc.generate(walk, inst, smc.SMCParams(use_bias=False))
    _check_orders(orders, walk)
    for o in orders:
        assert 7 <= o.placed.tz_convert("Europe/Rome").hour < 12
        assert o.target - o.entry == pytest.approx(3 * (o.entry - o.stop)) if o.direction == 1 else True
    tr = simulate(walk, orders)
    assert set(tr.reason) <= {"stop", "target", "open_at_end"}


def test_strategy_b_orders_and_daily_limits(walk):
    inst = get_instrument("GBPJPY")
    scaled = walk.copy()
    scaled[["open", "high", "low", "close"]] *= 170
    p = ema_fib.EMAFibParams(max_crosses=100)
    orders = ema_fib.generate(scaled, inst, p)
    _check_orders(orders, scaled)
    for o in orders:
        assert 6 <= (o.placed - pd.Timedelta(minutes=3)).tz_convert("Europe/Rome").hour < 9
        # -0.28 target over a 0.62 entry: reward / risk is at most 0.9 / 0.38
        assert 1.2 < abs(o.target - o.entry) / abs(o.entry - o.stop) <= 0.9 / 0.38 + 1e-9  # buffer lowers it
    tr = ema_fib.apply_daily_limits(simulate(scaled, orders), p)
    per_day = tr.groupby(tr.entry_time.dt.tz_convert("Europe/Rome").dt.date).size()
    assert per_day.max() <= 2


# ---------- cost filter, LTF option, sweep grid ----------

def test_cost_filter_drops_tiny_stops():
    from tradekit.engine import cost_filter
    df = candles([1.10] * 10)
    df["spread"] = 0.0001  # 1 pip
    costs = Costs(commission=0.00006, stop_slippage=0.00002)  # total cost 1.8 pips
    tiny = Order(df.index[1], df.index[-1], 1, 1.1000, 1.0995, 1.1015)  # 5 pip risk
    wide = Order(df.index[1], df.index[-1], 1, 1.1000, 1.0980, 1.1060)  # 20 pip risk
    kept = cost_filter(df, [tiny, wide], costs, 5)
    assert kept == [wide]
    assert cost_filter(df, [tiny, wide], costs, 0) == [tiny, wide]


def test_trades_report_gross_r():
    df = candles([1.10, 1.098, 1.095, 1.097, 1.10, 1.105, 1.112, 1.12])
    od = Order(df.index[0], df.index[-1], 1, entry=1.096, stop=1.090, target=1.108)
    tr = simulate(df, [od], Costs(commission=0.0006))
    assert tr.R_gross[0] == pytest.approx(2.0) and tr.R[0] == pytest.approx(1.9)


def test_strategy_a_on_m5_confirmation_has_wider_stops(walk):
    inst = get_instrument("EURUSD")
    m1 = smc.generate(walk, inst, smc.SMCParams(use_bias=False))
    m5 = smc.generate(walk, inst, smc.SMCParams(use_bias=False, ltf="M5"))
    _check_orders(m5, walk)
    med = lambda os: np.median([abs(o.entry - o.stop) for o in os])
    assert med(m5) > med(m1)


def test_sweep_grid_parsing():
    from tradekit.sweep import parse_grid
    g = parse_grid(["ltf=M1,M5", "rr=2,3", "min_cost=0,5"], smc.SMCParams())
    assert len(g) == 8 and g[0] == {"ltf": "M1", "rr": 2.0, "min_cost": 0.0}
    with pytest.raises(SystemExit):
        parse_grid(["nope=1"], smc.SMCParams())


# ---------- Cristian preset and compare ----------

def test_cristian_preset_orders_follow_the_fib(walk):
    inst = get_instrument("EURUSD")
    p = smc.cristian(require_sweep=False)
    orders = smc.generate(walk, inst, p)
    _check_orders(orders, walk)
    for o in orders:
        risk, reward = abs(o.entry - o.stop), abs(o.target - o.entry)
        # entry at 0.705, stop at 1.0, target at -0.5: reward/risk = 1.205 / 0.295
        assert reward / risk == pytest.approx(1.205 / 0.295, rel=1e-6)
        assert o.meta["kind"] == "CHoCH"


def test_require_sweep_only_keeps_swept_setups(walk):
    inst = get_instrument("EURUSD")
    all_ = smc.generate(walk, inst, smc.cristian(require_sweep=False))
    swept = smc.generate(walk, inst, smc.cristian())
    assert 0 < len(swept) < len(all_)
    assert all(o.meta["sweep"] for o in swept)


def test_compare_reads_setups(tmp_path):
    from tradekit.compare import load_setups
    f = tmp_path / "s.csv"
    f.write_text("date,time_utc+2,direction,entry,stop\n2026-11-16,08:57,long,52247,52236\n2026-11-20,~08:47,long (counter-trend),48988,48951.5\n")
    s = load_setups(str(f), 2)
    assert s.when.iloc[0] == pd.Timestamp("2026-11-16 06:57", tz="UTC")
    assert list(s.dir) == [1, 1] and s.instrument.iloc[0] == "US30"
