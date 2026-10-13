from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from breakout_ai.market import Bar, MarketSnapshot
from breakout_ai.screening import Criteria, indicators, rank_candidates, render_candidates
from breakout_ai.storage import utc_now


def snapshot(count=80):
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    bars = [Bar((end - timedelta(days=count - 1 - i)).isoformat(), 100 + i, 10000) for i in range(count)]
    return MarketSnapshot("US", "AAPL", "USD", "test", "https://example.org/AAPL", utc_now(), bars)


def test_increasing_series_has_transparent_score_and_declared_limits():
    row = rank_candidates([snapshot()])[0]
    assert row["eligible"] and row["score"] == 100
    assert row["momentum60_pct"] == pytest.approx((179 / 119 - 1) * 100)
    assert row["max_drawdown60_pct"] == 0
    assert any("Chưa đánh giá" in risk for risk in row["risks"])


def test_adjusted_series_is_used_consistently_for_indicators():
    raw = snapshot()
    bars = [replace(bar, close=1000 - i, adjusted_close=100 + i) for i, bar in enumerate(raw.bars)]
    stats = indicators(replace(raw, bars=bars))
    assert stats["analysis_price"] == 179
    assert stats["analysis_basis"] == "adjusted-by-provider"


@pytest.mark.parametrize("case", ["short", "stale_cache", "old_date", "zero_volume"])
def test_incomplete_or_stale_data_are_not_ranked(case):
    data = snapshot()
    if case == "short": data = snapshot(20)
    if case == "stale_cache": data = replace(data, cache_stale=True)
    if case == "old_date": data = replace(data, bars=[replace(bar, date=(datetime.fromisoformat(bar.date) - timedelta(days=30)).date().isoformat()) for bar in data.bars])
    if case == "zero_volume": data = replace(data, bars=[*data.bars[:-1], replace(data.latest, volume=0)])
    row = rank_candidates([data])[0]
    assert not row["eligible"] and row["score"] is None


def test_criteria_ranges_are_validated():
    with pytest.raises(ValueError):
        Criteria(volatility_cap=0)


def test_output_groups_markets_and_does_not_claim_return_probability():
    rows = rank_candidates([snapshot(), replace(snapshot(), market="VN", symbol="FPT", currency="VND")])
    text = render_candidates(rows)
    assert "**US ·" in text and "**VN ·" in text
    assert "không phải xác suất" in text


def test_filter_can_return_no_priority_candidate():
    data = snapshot()
    descending = replace(data, bars=[replace(bar, close=200 - i) for i, bar in enumerate(data.bars)])
    rows = rank_candidates([descending])
    assert not rows[0]["meets_screen"]
    assert "Chưa có mã đạt ngưỡng" in render_candidates(rows)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), 0])
def test_bad_prices_cannot_be_used_as_indicators(invalid):
    data = snapshot()
    data = replace(data, bars=[*data.bars[:-1], replace(data.latest, close=invalid)])
    with pytest.raises(ValueError):
        indicators(data)
