"""Verify chart evidence, units and escaping without a browser or network."""
from datetime import datetime, timedelta, timezone
import math

import pytest

from breakout_ai.intraday import Candle, IntradaySnapshot
from breakout_ai.market_visuals import candle_chart, depth_chart, signal_card


NOW = datetime(2026, 10, 19, 3, 30, tzinfo=timezone.utc)


def snapshot(count=25):
    candles = [
        Candle(
            (NOW - timedelta(minutes=5 * (count - index))).isoformat(),
            100_000 + index, 100_010 + index, 99_990 + index,
            100_005 + index, 1234 + index, complete=True,
        )
        for index in range(count)
    ]
    return IntradaySnapshot("VIC", candles=candles, stale=False)


def chart_spec(*args, **kwargs):
    """Resolve inherited Vega-Lite data, independent of Altair hoisting."""
    spec = candle_chart(*args, **kwargs).to_dict()
    def inherit(node, parent_data=None):
        inherited = node.get("data", parent_data)
        if inherited is not None:
            node.setdefault("data", inherited)
        for group in ("layer", "vconcat"):
            for child in node.get(group, []):
                inherit(child, inherited)
    inherit(spec)
    return spec


def layers(spec):
    return spec["vconcat"][0]["layer"]


def values(node):
    return node.get("data", {}).get("values", [])


def last_price_rules(spec):
    return [layer for layer in layers(spec)
            if any(t.get("title") == "Khớp gần nhất · VND" for t in layer.get("encoding", {}).get("tooltip", []))]


def test_missing_candles_never_creates_a_fake_chart_from_quote_or_levels():
    assert candle_chart(IntradaySnapshot("VIC"), {"symbol": "VIC", "last": 100_000, "stale": False},
                        {"levels": {"support": 90_000, "resistance": 110_000}}) is None


def test_only_real_bars_are_drawn_without_interpolation_or_extra_history():
    source = snapshot(2)
    spec = chart_spec(source)
    plotted = values(layers(spec)[0])
    assert len(plotted) == 2
    assert [row["time"] for row in plotted] == [row.time for row in source.candles]
    assert [row["close"] for row in plotted] == [row.close for row in source.candles]
    assert [row["volume"] for row in plotted] == [1234, 1235]
    assert plotted[-1]["label"] == "19/10 10:25"


def test_ma20_requires_twenty_observations_before_appearing():
    source = snapshot(21)
    plotted = values(layers(chart_spec(source))[0])
    assert all(row["ma20"] is None for row in plotted[:19])
    assert plotted[19]["ma20"] == pytest.approx(sum(c.close for c in source.candles[:20]) / 20)
    assert plotted[20]["ma20"] == pytest.approx(sum(c.close for c in source.candles[1:21]) / 20)


def test_ma20_warmup_uses_source_history_before_display_window():
    source = snapshot(200)
    plotted = values(layers(chart_spec(source))[0])
    assert len(plotted) == 160
    assert plotted[0]["time"] == source.candles[40].time
    assert plotted[0]["ma20"] == pytest.approx(sum(c.close for c in source.candles[21:41]) / 20)


def test_volume_panel_preserves_individual_shares_and_price_preserves_full_vnd():
    spec = chart_spec(snapshot(1))
    volume = spec["vconcat"][1]
    assert values(volume)[0]["volume"] == 1234
    assert values(layers(spec)[0])[0]["close"] == 100_005
    assert volume["encoding"]["y"]["title"] == "KL · CP"
    assert any(t.get("title") == "Cổ phiếu" for t in volume["encoding"]["tooltip"])


def test_incomplete_source_candle_stays_visibly_distinct():
    source = snapshot(1).payload()
    source["candles"][0]["complete"] = False
    spec = chart_spec(source)
    body = next(layer for layer in layers(spec) if layer["mark"]["type"] == "bar")
    assert values(body)[0]["complete"] is False
    assert body["encoding"]["opacity"]["condition"]["test"] == "datum.complete"
    assert body["encoding"]["opacity"]["value"] < 1


def test_fresh_matching_quote_draws_exact_source_last_price():
    quote = {"symbol": "VIC", "last": 101_250, "stale": False}
    rules = last_price_rules(chart_spec(snapshot(), quote))
    assert len(rules) == 1 and values(rules[0]) == [{"value": 101_250}]


@pytest.mark.parametrize("quote", [
    {"symbol": "VIC", "last": 101_250, "stale": True},
    {"symbol": "VIC", "last": 101_250},
    {"symbol": "FPT", "last": 101_250, "stale": False},
    {"symbol": "VIC", "last": None, "stale": False},
    {"symbol": "VIC", "last": True, "stale": False},
    {"symbol": "VIC", "last": math.nan, "stale": False},
    {"symbol": "VIC", "last": math.inf, "stale": False},
    {"symbol": "VIC", "last": 0, "stale": False},
])
def test_stale_wrong_symbol_or_invalid_quote_does_not_draw_a_current_price(quote):
    assert last_price_rules(chart_spec(snapshot(), quote)) == []


def test_support_resistance_lines_use_only_explicit_report_values():
    report = {"symbol": "VIC", "levels": {"support": 98_000, "resistance": 105_000, "invalidation": 97_000}}
    spec = chart_spec(snapshot(), report=report)
    observed = [row for layer in layers(spec) for row in values(layer) if "name" in row]
    assert {row["name"]: row["value"] for row in observed} == {
        "Hỗ trợ 20 nến": 98_000, "Kháng cự 20 nến": 105_000,
    }
    assert all(row["value"] != 97_000 for row in observed)
    assert not [row for layer in layers(chart_spec(snapshot()))
                for row in values(layer) if "name" in row]


@pytest.mark.parametrize("bad", [True, None, math.nan, math.inf, -10, 0, "unavailable"])
def test_invalid_levels_do_not_create_chart_overlays(bad):
    spec = chart_spec(snapshot(), report={"levels": {"support": bad, "resistance": bad}})
    assert not [row for layer in layers(spec) for row in values(layer) if "name" in row]


def test_depth_is_hidden_when_stale_or_empty():
    assert depth_chart({"depth_stale": True, "bids": [{"price": 10_000, "volume": 500}]}) is None
    assert depth_chart({"bids": [{"price": 10_000, "volume": 500}]}) is None
    assert depth_chart({"depth_stale": False, "bids": [], "asks": []}) is None


def test_depth_chart_keeps_waiting_order_units_and_limits_three_levels():
    quote = {
        "depth_stale": False,
        "bids": [{"price": 100_000 - i * 100, "volume": 1000 + i} for i in range(4)],
        "asks": [{"price": 100_100 + i * 100, "volume": 2000 + i} for i in range(4)],
    }
    spec = depth_chart(quote).to_dict()
    plotted = values(spec)
    assert len(plotted) == 6
    assert [row["volume"] for row in plotted] == [1000, 1001, 1002, 2000, 2001, 2002]
    assert plotted[0]["price"] == 100_000
    assert spec["encoding"]["x"]["title"] == "Lệnh chờ · CP"


def test_signal_card_escapes_all_text_and_never_allows_action_attribute_injection():
    malicious = '<img src=x onerror="alert(1)">'
    report = {
        "symbol": malicious, "title": malicious, "summary": malicious,
        "action": 'watch_buy" onclick="alert(1)', "evidence": [malicious],
        "blockers": [malicious], "signal_strength": malicious,
        "timeframe": malicious, "as_of": "2026-10-19T03:00:00+00:00",
        "levels": {"support": 100_000},
    }
    html = signal_card(report)
    assert "<img" not in html and 'onclick="alert' not in html
    assert html.count("&lt;img") >= 7
    assert 'class="signal-tag wait"' in html
    assert "100,000" in html
    assert "19/10" in html
