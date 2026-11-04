"""Observe source OHLCV once, retaining units, provenance and readiness gates."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from breakout_ai.intraday import Candle, IntradaySnapshot
from breakout_ai.observation import MAX_CONTEXT_CANDLES, observe_chart


NOW = datetime(2026, 11, 4, 6, 30, tzinfo=timezone.utc)


def source(count=40, *, resolution=5, direction=1):
    rows = []
    for index in range(count):
        close = 100_000 + direction * index * 10
        rows.append(Candle(
            (NOW - timedelta(minutes=resolution * (count-index))).isoformat(),
            close - 5, close + 20, close - 20, close, 1_250,
            interval_minutes=resolution, complete=True,
        ))
    return IntradaySnapshot("VIC", resolution=str(resolution), candles=rows,
                            fetched_at=(NOW-timedelta(seconds=1)).isoformat(), stale=False)


def quote(**changes):
    return {
        "symbol": "VIC", "market": "VN", "currency": "VND", "exchange": "HOSE",
        "last": 100_390, "source_timestamp": (NOW-timedelta(seconds=10)).isoformat(),
        "received_at": NOW.isoformat(), "stale": False, "depth_stale": True,
        "bids": [], "asks": [], **changes,
    }


def observe(chart=None, market_quote=None, **kwargs):
    return observe_chart("VIC", chart or source(), market_quote or quote(),
                         now=NOW, **kwargs)


def fact(observation, identifier):
    return next(item for item in observation.chart["facts"] if item["id"] == identifier)


def test_canonical_context_contains_completed_source_candles_and_traceable_facts():
    snapshot = source()
    observation = observe(snapshot)
    context = observation.context()
    assert set(context) == {"analysis", "quote", "chart", "owned", "captured_at"}
    assert context["captured_at"] == NOW.isoformat()
    assert context["chart"]["symbol"] == "VIC"
    assert context["chart"]["resolution"] == "5"
    assert context["chart"]["currency"] == context["chart"]["price_unit"] == "VND"
    assert context["chart"]["source_url"] == snapshot.source_url
    assert context["chart"]["fetched_at"] == snapshot.fetched_at
    assert context["chart"]["as_of"] == observation.report.as_of
    assert len(context["chart"]["candles"]) == 40
    first = context["chart"]["candles"][0]
    assert first["close"] == snapshot.candles[0].close
    assert first["volume"] == 1250  # Individual shares, not board source lots.
    assert all(row["complete"] for row in context["chart"]["candles"])
    assert all(set(item) == {"id", "label", "text", "role", "values"} for item in context["chart"]["facts"])
    assert len({item["id"] for item in context["chart"]["facts"]}) == len(context["chart"]["facts"])
    assert not observation.report.blockers
    assert fact(observation, "data.readiness")["role"] == "observation"
    json.dumps(context, allow_nan=False)


def test_context_is_bounded_to_last_sixty_and_does_not_mutate_sources():
    snapshot, market_quote = source(90), quote()
    before, quote_before = deepcopy(snapshot.payload()), deepcopy(market_quote)
    observation = observe(snapshot, market_quote)
    assert len(observation.chart["candles"]) == MAX_CONTEXT_CANDLES
    assert observation.chart["candles"][0]["time"] == snapshot.candles[-60].time
    assert observation.chart["candles"][-1]["time"] == snapshot.candles[-1].time
    assert snapshot.payload() == before and market_quote == quote_before


def test_context_has_no_alias_to_source_or_returned_payload():
    snapshot, market_quote = source(), quote()
    observation = observe(snapshot, market_quote)
    captured = observation.context()
    market_quote["last"] = 5
    snapshot.candles.clear()
    captured["chart"]["candles"][0]["close"] = 1
    captured["chart"]["facts"][0]["values"].clear()
    captured["quote"]["last"] = 3
    again = observation.context()
    assert len(again["chart"]["candles"]) == 40
    assert again["chart"]["candles"][0]["close"] == 100_000
    assert again["quote"]["last"] == 100_390
    assert again["chart"]["facts"][0]["values"]


def test_unclosed_and_future_candles_never_leak_into_model_context():
    snapshot = source()
    snapshot.candles.extend([
        Candle((NOW-timedelta(minutes=2)).isoformat(), 1_000_000, 2_000_000,
               500_000, 1_500_000, 999_999, complete=False),
        Candle((NOW+timedelta(minutes=5)).isoformat(), 1_000_000, 2_000_000,
               500_000, 1_500_000, 999_999, complete=True),
    ])
    observation = observe(snapshot)
    assert len(observation.chart["candles"]) == 40
    assert max(row["high"] for row in observation.chart["candles"]) < 101_000
    assert observation.report.action == "wait"
    assert any("tương lai" in item for item in observation.report.blockers)
    assert fact(observation, "data.readiness")["role"] == "blocker"


@pytest.mark.parametrize("field,value", [
    ("symbol", "FPT"), ("resolution", "15"),
    ("asset_type", "index"), ("price_unit", "points"),
])
def test_wrong_chart_identity_never_produces_cross_symbol_or_unit_indicators(field, value):
    snapshot = replace(source(), **{field: value})
    observation = observe(snapshot)
    assert observation.report.action == "wait" and observation.report.blockers
    assert observation.chart["candles"] == []
    assert observation.report.indicators.get("sma20") is None
    assert observation.report.levels["support"] is None
    assert fact(observation, "data.readiness")["role"] == "blocker"
    assert all(scenario["status"] == "blocked" for scenario in observation.chart["scenarios"])


@pytest.mark.parametrize("changes", [
    {"stale": True}, {"errors": ["HTTP 503 from synthetic test"]},
    {"stale": True, "errors": ["source throttled"]},
])
def test_source_failure_blocks_even_recent_cached_candles(changes):
    observation = observe(replace(source(), **changes))
    assert observation.report.action == "wait"
    assert observation.report.blockers
    assert len(observation.chart["candles"]) == 40  # Historical evidence is retained.
    assert fact(observation, "data.readiness")["role"] == "blocker"
    assert all(scenario["status"] == "blocked" for scenario in observation.chart["scenarios"])


@pytest.mark.parametrize("changes", [
    {"symbol": "FPT"}, {"market": "US"}, {"currency": "USD"},
    {"stale": True}, {"source_timestamp": (NOW-timedelta(minutes=4)).isoformat()},
])
def test_wrong_or_old_quote_cannot_qualify_an_opportunity(changes):
    observation = observe(market_quote=quote(**changes))
    assert observation.report.action == "wait" and observation.report.blockers
    assert fact(observation, "data.readiness")["values"]["ready"] is False


def test_zero_range_candle_and_missing_volume_stay_json_safe_and_distinct():
    snapshot = source()
    snapshot.candles[:] = [
        replace(candle, open=100_000, high=100_000, low=100_000,
                close=100_000, volume=None if index == 0 else 0)
        for index, candle in enumerate(snapshot.candles)
    ]
    observation = observe(snapshot)
    latest = fact(observation, "candle.latest")["values"]
    assert latest["body_pct"] is latest["close_position_pct"] is None
    assert observation.chart["candles"][0]["volume"] is None
    assert observation.chart["candles"][1]["volume"] == 0
    assert observation.report.action == "wait"
    json.dumps(observation.context(), allow_nan=False)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), True, -1])
def test_invalid_ohlc_does_not_enter_raw_model_context(bad_value):
    snapshot = source()
    snapshot.candles[-1] = replace(snapshot.candles[-1], high=bad_value)
    observation = observe(snapshot)
    assert len(observation.chart["candles"]) == 39
    assert observation.report.action == "wait" and observation.report.blockers
    json.dumps(observation.context(), allow_nan=False)


def test_nonfinite_quote_is_not_serialized_as_a_number():
    observation = observe(market_quote=quote(last=float("nan")))
    assert observation.report.action == "wait"
    assert observation.quote["last"] is None
    json.dumps(observation.context(), allow_nan=False)


@pytest.mark.parametrize("direction,expected", [(1, "higher"), (-1, "lower"), (0, "mixed")])
def test_structure_uses_two_explicit_nonoverlapping_five_bar_windows(direction, expected):
    snapshot = source(direction=direction)
    observation = observe(snapshot)
    structure = fact(observation, "structure.recent")["values"]
    before, recent = snapshot.candles[-10:-5], snapshot.candles[-5:]
    assert structure["structure"] == expected
    assert structure["window_bars"] == 5
    assert structure["previous_high"] == max(row.high for row in before)
    assert structure["recent_low"] == min(row.low for row in recent)


def test_candle_shape_uses_ohlc_range_without_claiming_a_pattern():
    observation = observe()
    values = fact(observation, "candle.latest")["values"]
    assert values["body_pct"] == 12.5
    assert values["upper_wick_pct"] == 50
    assert values["lower_wick_pct"] == 37.5
    assert values["close_position_pct"] == 50
    assert sum(values[key] for key in ("body_pct", "upper_wick_pct", "lower_wick_pct")) == 100


def test_range_comparison_excludes_the_decision_candle():
    snapshot = source()
    snapshot.candles[-1] = replace(snapshot.candles[-1], high=900_000)
    observation = observe(snapshot)
    values = fact(observation, "structure.range20")["values"]
    assert values["high"] == max(row.high for row in snapshot.candles[-21:-1])
    assert values["high"] < snapshot.candles[-1].high


def test_structural_strength_does_not_create_an_extra_buy_rule():
    snapshot = source()
    snapshot.candles[-1] = replace(snapshot.candles[-1], volume=100)
    observation = observe(snapshot)
    assert fact(observation, "structure.recent")["values"]["structure"] == "higher"
    assert observation.report.action == "wait"
    assert all(scenario["status"] != "qualified" for scenario in observation.chart["scenarios"])


def test_qualified_scenario_matches_existing_rule_and_actual_invalidation():
    snapshot = source(direction=0)
    snapshot.candles[-1] = replace(snapshot.candles[-1], open=100_000,
                                  low=99_900, high=104_000, close=103_000, volume=3000)
    observation = observe(snapshot, quote(last=103_000))
    assert observation.report.action == "watch_buy" and not observation.report.blockers
    scenario = observation.chart["scenarios"][0]
    assert scenario["status"] == "qualified" and scenario["action"] == "watch_buy"
    assert scenario["values"]["invalidation"] == observation.report.levels["invalidation"]
    assert f"{observation.report.levels['invalidation']:,.0f}" in scenario["invalidation"]
    assert isinstance(scenario["confirmation"], str) and isinstance(scenario["invalidation"], str)
    ids = {item["id"] for item in observation.chart["facts"]}
    assert set(scenario["evidence_ids"]) <= ids


def test_empty_history_produces_explicit_blocker_facts_and_blocked_scenarios():
    observation = observe(replace(source(), candles=[]))
    assert observation.report.action == "wait" and observation.report.blockers
    assert not observation.chart["candles"]
    assert fact(observation, "data.readiness")["role"] == "blocker"
    assert fact(observation, "candle.latest")["values"] == {}
    assert all(scenario["status"] == "blocked" for scenario in observation.chart["scenarios"])


def test_capture_is_reproducible_and_excludes_unrelated_quote_fields():
    snapshot, market_quote = source(), quote(api_key="never-forward-this", unrelated=[1, 2])
    first = observe(snapshot, market_quote).context()
    second = observe(snapshot, market_quote).context()
    assert first == second
    assert "api_key" not in first["quote"] and "unrelated" not in first["quote"]
    assert "never-forward-this" not in json.dumps(first)


@pytest.mark.parametrize("resolution", ["1", "5", "15"])
def test_resolution_matches_source_interval_and_context(resolution):
    observation = observe(source(resolution=int(resolution)), resolution=resolution)
    assert observation.chart["resolution"] == resolution
    assert all(row["interval_minutes"] == int(resolution) for row in observation.chart["candles"])


@pytest.mark.parametrize("resolution", ["0", "60", "1D", 5, True])
def test_invalid_resolution_is_rejected(resolution):
    with pytest.raises(ValueError):
        observe(resolution=resolution)
