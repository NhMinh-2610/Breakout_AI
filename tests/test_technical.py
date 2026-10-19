from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math

import pytest

from breakout_ai.technical import analyze, rsi_wilder

NOW = datetime(2026, 10, 19, 3, 30, tzinfo=timezone.utc)


def candles(closes=None, *, interval=5):
    closes = closes if closes is not None else [10_000] * 30 + [11_000]
    rows = []
    for index, close in enumerate(closes):
        opened = closes[index - 1] if index else close
        rows.append({
            "time": (NOW - timedelta(minutes=interval * (len(closes) - index))).isoformat(),
            "open": opened, "high": max(opened, close) + 1,
            "low": min(opened, close) - 1, "close": close,
            "volume": 200 if index == len(closes) - 1 else 100,
            "interval_minutes": interval, "complete": True,
        })
    return rows


def quote(last=11_000, **overrides):
    book_price = last if isinstance(last, (int, float)) and math.isfinite(last) else 11_000
    result = {
        "symbol": "VIC", "last": last, "stale": False,
        "source_timestamp": (NOW - timedelta(seconds=2)).isoformat(),
        "depth_timestamp": (NOW - timedelta(seconds=1)).isoformat(),
        "depth_stale": False,
        "bids": [{"price": book_price - i - 1, "volume": 100} for i in range(3)],
        "asks": [{"price": book_price + i + 1, "volume": 200} for i in range(3)],
    }
    result.update(overrides)
    return result


def test_confirmed_breakout_requires_completed_candle_volume_and_live_price():
    report = analyze("vic", candles(), quote(), now=NOW)
    assert report.symbol == "VIC" and report.action == "watch_buy"
    assert report.indicators["relative_volume"] == 2
    assert report.levels["resistance"] == 10_001
    assert report.levels["invalidation"] == 10_001
    assert report.as_of == NOW.isoformat()
    assert report.signal_strength == "4/4 điều kiện quan sát"
    assert not report.blockers
    assert "xác suất" in report.evidence[-1]
    assert report.payload()["condition_checks"] == report.condition_checks


def test_support_resistance_and_volume_comparison_exclude_decision_bar():
    rows = candles()
    rows[-1].update(high=20_000, low=1, volume=10_000)
    report = analyze("VIC", rows, quote(), now=NOW)
    assert report.levels["support"] == 9_999
    assert report.levels["resistance"] == 10_001
    assert report.indicators["relative_volume"] == 100
    assert report.action == "watch_buy"


def test_zero_or_missing_volume_never_manufactures_confirmation():
    for field, value in [("volume", None), ("volume", 0)]:
        rows = candles()
        rows[-1][field] = value
        report = analyze("VIC", rows, quote(), now=NOW)
        assert report.action == "wait"
        if value is None:
            assert report.indicators["relative_volume"] is None
            assert any("khối lượng" in item for item in report.blockers)
        else:
            assert report.indicators["relative_volume"] == 0


def test_missing_any_comparison_volume_disables_confirmation():
    rows = candles()
    rows[-10]["volume"] = None
    report = analyze("VIC", rows, quote(), now=NOW)
    assert report.action == "wait" and report.indicators["relative_volume"] is None


def test_zero_average_volume_is_unavailable_instead_of_infinite():
    rows = candles()
    for row in rows[:-1]:
        row["volume"] = 0
    report = analyze("VIC", rows, quote(), now=NOW)
    assert report.action == "wait" and report.indicators["relative_volume"] is None
    assert all(not isinstance(value, float) or math.isfinite(value)
               for value in report.indicators.values())


def test_intraday_last_price_can_invalidate_an_earlier_breakout():
    report = analyze("VIC", candles(), quote(last=10_000), now=NOW)
    assert report.action == "wait"
    assert not report.condition_checks["Giá khớp còn trên kháng cự"]


def test_in_progress_spike_is_ignored_even_when_complete_flag_incorrect():
    rows = candles([10_000] * 31)
    spike = dict(rows[-1], time=(NOW - timedelta(minutes=1)).isoformat(),
                 high=20_001, close=20_000, volume=50_000, complete=True)
    rows.append(spike)
    report = analyze("VIC", rows, quote(last=20_000), now=NOW)
    assert report.action == "wait"
    assert report.indicators["latest_close"] == 10_000
    assert report.indicators["completed_bars"] == 31


def test_explicit_incomplete_bar_is_not_a_confirmation():
    rows = candles()
    rows[-1]["complete"] = False
    report = analyze("VIC", rows, quote(), now=NOW)
    assert report.action == "wait" and report.indicators["latest_close"] == 10_000


def test_less_than_thirty_closed_bars_has_no_action():
    report = analyze("VIC", candles()[-29:], quote(), now=NOW)
    assert report.action == "wait" and any("30 nến" in item for item in report.blockers)


@pytest.mark.parametrize("bad", [
    {"stale": True}, {"source_timestamp": None},
    {"source_timestamp": (NOW - timedelta(seconds=181)).isoformat()},
    {"source_timestamp": (NOW + timedelta(seconds=31)).isoformat()},
    {"source_timestamp": NOW.replace(tzinfo=None).isoformat()},
    {"last": math.nan}, {"last": None}, {"symbol": "FPT"}, {"symbol": None},
])
def test_missing_stale_future_or_wrong_quote_blocks_actions(bad):
    report = analyze("VIC", candles(), quote(**bad), now=NOW)
    assert report.action == "wait" and report.blockers


def test_quote_exact_freshness_boundary_is_accepted():
    report = analyze("VIC", candles(), quote(source_timestamp=(NOW - timedelta(seconds=180)).isoformat()), now=NOW)
    assert report.action == "watch_buy"


def test_stale_candles_are_only_historical_context():
    rows = candles()
    for row in rows:
        row["time"] = (datetime.fromisoformat(row["time"]) - timedelta(minutes=11)).isoformat()
    report = analyze("VIC", rows, quote(), now=NOW)
    assert report.action == "wait" and any("Nến đã đóng" in value for value in report.blockers)


def test_previous_day_candles_are_not_todays_signal():
    rows = candles()
    for row in rows:
        row["time"] = (datetime.fromisoformat(row["time"]) - timedelta(days=1)).isoformat()
    report = analyze("VIC", rows, quote(), now=NOW)
    assert report.action == "wait" and report.indicators["relative_volume"] == 2


@pytest.mark.parametrize("change", [
    {"close": math.inf}, {"low": 50_000}, {"high": 1},
    {"interval_minutes": 1}, {"time": "2026-10-19T10:25:00"},
    {"time": (NOW + timedelta(minutes=5)).isoformat()},
])
def test_malformed_bars_block_active_signal_even_if_remaining_history_sufficient(change):
    rows = candles()
    rows[0].update(change)
    report = analyze("VIC", rows, quote(), now=NOW)
    assert report.action == "wait" and report.blockers


def test_duplicate_timestamps_block_action():
    rows = candles()
    rows[0]["time"] = rows[1]["time"]
    report = analyze("VIC", rows, quote(), now=NOW)
    assert report.action == "wait" and any("trùng lặp" in value for value in report.blockers)


def test_unsorted_bars_are_sorted_without_changing_result():
    rows = list(reversed(candles()))
    assert analyze("VIC", rows, quote(), now=NOW).action == "watch_buy"


def test_oversold_alone_never_qualifies_a_buy():
    rows = candles([10_000 - i * 10 for i in range(31)])
    report = analyze("VIC", rows, quote(last=9_700), now=NOW)
    assert report.indicators["rsi14"] == 0
    assert report.action == "wait"
    assert any("tiếp tục giảm" in value for value in report.evidence)


def test_rebound_requires_rsi_recovery_green_candle_volume_and_support():
    closes = [1_000 - i for i in range(30)] + [977]
    report = analyze("VIC", candles(closes), quote(last=977), now=NOW)
    assert report.action == "watch_buy"
    assert report.indicators["rsi14_previous"] == 0
    assert report.indicators["rsi14"] > 30
    assert report.signal_strength.startswith("5/5")
    # A live price far above support should not masquerade as buying near it.
    assert analyze("VIC", candles(closes), quote(last=1_100), now=NOW).action == "wait"


def test_owned_gate_prevents_sell_suggestion_for_unowned_asset():
    rows = candles([10_000] * 30 + [9_000])
    unowned = analyze("VIC", rows, quote(last=9_000), now=NOW)
    owned = analyze("VIC", rows, quote(last=9_000), owned=True, now=NOW)
    assert unowned.action == "wait"
    assert owned.action == "watch_sell" and not owned.blockers
    assert owned.levels["invalidation"] == owned.levels["support"]


def test_quiet_owned_asset_has_observation_instead_of_sell():
    report = analyze("VIC", candles([10_000] * 31), quote(last=10_000), owned=True, now=NOW)
    assert report.action == "hold"
    assert report.indicators["rsi14"] == 50


def test_book_pressure_is_descriptive_and_does_not_trigger_buy():
    report = analyze("VIC", candles([10_000] * 31),
                     quote(last=10_000, bids=[{"price": 9_999 - i, "volume": 1_000_000} for i in range(3)]),
                     now=NOW)
    assert report.action == "wait"
    assert report.indicators["bid_share_pct"] > 99
    assert any("sửa/hủy" in text for text in report.evidence)


def test_stale_or_incomplete_book_does_not_leak_fresh_imbalance():
    for overrides in [{"depth_stale": True}, {"depth_timestamp": None}, {"asks": []},
                      {"asks": [{"price": None, "volume": 10}] * 3}]:
        report = analyze("VIC", candles(), quote(**overrides), now=NOW)
        assert "book_imbalance" not in report.indicators
        # Book depth is optional context, not a price-volume signal gate.
        assert report.action == "watch_buy"


def test_rsi_known_wilder_seed_and_smoothing():
    # Wilder's widely published worked example, first RSI after 14 changes.
    closes = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
              45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00]
    result = rsi_wilder(closes)
    assert result[13] is None
    assert result[14] == pytest.approx(70.4641350211)
    assert result[15] == pytest.approx(66.2496185536)


def test_rsi_one_way_flat_and_missing_inputs_are_finite_or_unavailable():
    assert rsi_wilder(list(range(1, 31)))[-1] == 100
    assert rsi_wilder(list(range(30, 0, -1)))[-1] == 0
    assert rsi_wilder([10] * 30)[-1] == 50
    assert rsi_wilder([10] * 14) == [None] * 14
    assert rsi_wilder([10] * 20 + [math.nan]) == [None] * 21


def test_dataclass_candles_quotes_and_levels_are_accepted_without_mutation():
    @dataclass
    class Row:
        time: str
        open: float
        high: float
        low: float
        close: float
        volume: float
        interval_minutes: int
        complete: bool
    rows = [Row(**row) for row in candles()]
    original = deepcopy(rows)
    report = analyze("VIC", rows, quote(), now=NOW)
    assert report.action == "watch_buy" and rows == original


@pytest.mark.parametrize("resolution", [1, 15])
def test_each_supported_interval_has_own_closed_bar_horizon(resolution):
    report = analyze("VIC", candles(interval=resolution), quote(), now=NOW, resolution_minutes=resolution)
    assert report.action == "watch_buy" and report.timeframe == f"Nến {resolution} phút"


def test_invalid_resolution_and_naive_clock_fail_explicitly():
    with pytest.raises(ValueError):
        analyze("VIC", candles(), quote(), now=NOW, resolution_minutes=0)
    with pytest.raises(ValueError):
        analyze("VIC", candles(), quote(), now=NOW.replace(tzinfo=None))
