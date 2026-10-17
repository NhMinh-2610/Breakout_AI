from dataclasses import replace
from datetime import date, timedelta

import pytest

from breakout_ai.dashboard import allocation_chart, allocation_records, price_chart, price_records, price_summary, workflow_diagram
from breakout_ai.market import Bar, MarketSnapshot


def snapshot(bars=None, **kwargs):
    return MarketSnapshot("US", "AAPL", "USD", "fixture", "https://example.org/AAPL", "2026-10-18T00:00:00+00:00", bars or [], **kwargs)


def test_price_window_uses_calendar_days_without_inventing_weekend_sessions():
    source = snapshot([Bar("2026-10-16", 101, 1000), Bar("2026-10-12", 100, 900), Bar("2026-10-15", 99, 950)])
    rows = price_records(source, days=3)
    assert [row["date"] for row in rows] == ["2026-10-15", "2026-10-16"]
    assert rows[-1]["volume"] == 1000
    assert rows[-1]["basis"] == "Giá đóng cửa"


def test_moving_average_uses_observations_before_visible_date_window():
    bars = [Bar((date(2026, 9, 1) + timedelta(days=i)).isoformat(), float(i + 1), 100) for i in range(25)]
    rows = price_records(snapshot(bars), days=2)
    assert len(rows) == 2
    assert rows[0]["ma20"] == pytest.approx(sum(range(5, 25)) / 20)
    assert rows[1]["ma20"] == pytest.approx(sum(range(6, 26)) / 20)


def test_complete_adjusted_series_is_explicit_and_raw_quote_remains_separate():
    source = snapshot([Bar("2026-10-15", 100, 1000, 50), Bar("2026-10-16", 52, 1500, 52)], price_basis="adjusted-by-provider")
    rows, summary = price_records(source), price_summary(source)
    assert [row["price"] for row in rows] == [50, 52]
    assert rows[0]["raw_close"] == 100
    assert summary["basis_label"] == "Giá điều chỉnh"
    assert summary["latest_close"] == 52
    assert summary["change_pct"] == pytest.approx(-48)
    assert summary["period_change_pct"] == pytest.approx(4)


def test_incomplete_adjustment_never_mixes_raw_and_adjusted_prices():
    source = snapshot([Bar("2026-10-15", 100, 1000, 50), Bar("2026-10-16", 52, 1500)], price_basis="adjusted-by-provider")
    assert [row["price"] for row in price_records(source)] == [100, 52]
    assert price_summary(source)["basis_label"] == "Giá đóng cửa"


def test_unknown_adjustment_basis_keeps_raw_series_even_if_values_exist():
    source = snapshot([Bar("2026-10-16", 100, 1000, 50)])
    assert price_records(source)[0]["price"] == 100


def test_price_summary_drawdown_is_observed_price_drawdown():
    source = snapshot([Bar("2026-10-14", 100, 10), Bar("2026-10-15", 120, 20), Bar("2026-10-16", 90, 30)])
    summary = price_summary(source)
    assert summary["max_drawdown_pct"] == pytest.approx(-25)
    assert summary["latest_drawdown_pct"] == pytest.approx(-25)
    assert summary["observations"] == 3
    assert "profit" not in summary


def test_missing_and_invalid_price_rows_do_not_create_a_chart():
    assert price_chart(snapshot()) is None
    assert price_summary(snapshot()) is None
    invalid = snapshot([Bar("invalid", 100, 10), Bar("2026-10-16", float("nan"), 10)])
    assert price_records(invalid) == []


def test_single_observation_has_no_fabricated_price_return():
    summary = price_summary(snapshot([Bar("2026-10-16", 100, 10)]))
    assert summary["change_pct"] is summary["period_change_pct"] is None
    assert summary["max_drawdown_pct"] == 0


def holdings():
    return [
        {"market": "VN", "symbol": "FPT", "quantity": 10, "average_cost": 50_000},
        {"market": "US", "symbol": "AAPL", "quantity": 2, "average_cost": 100},
        {"market": "US", "symbol": "MSFT", "quantity": 1, "average_cost": 200},
    ]


def test_allocations_never_combine_currencies_and_use_full_amounts():
    groups = allocation_records(holdings())
    assert set(groups) == {"VND", "USD"}
    assert groups["VND"][0]["value"] == 500_000
    assert groups["VND"][0]["share"] == 1
    assert [row["share"] for row in groups["USD"]] == [.5, .5]
    assert all(row["valuation_basis"] == "Vốn đã nhập" for group in groups.values() for row in group)


def test_partial_quote_group_falls_back_to_cost_basis_for_every_position():
    groups = allocation_records(holdings(), [{"market": "US", "symbol": "AAPL", "currency": "USD", "close": 300}])
    assert [row["share"] for row in groups["USD"]] == [.5, .5]
    assert all(row["valuation_basis"] == "Vốn đã nhập" for row in groups["USD"])


def test_complete_quotes_allow_explicit_market_valuation_per_currency():
    quotes = {
        "US:AAPL": {"market": "US", "symbol": "AAPL", "currency": "USD", "close": 300},
        "US:MSFT": {"market": "US", "symbol": "MSFT", "currency": "USD", "close": 200},
    }
    groups = allocation_records(holdings(), quotes)
    assert [row["share"] for row in groups["USD"]] == [.75, .25]
    assert groups["USD"][0]["valuation_basis"] == "Giá trị theo giá gần nhất"
    assert groups["VND"][0]["valuation_basis"] == "Vốn đã nhập"


def test_wrong_currency_or_stale_quotes_cannot_change_allocation_values():
    quote = {"market": "US", "symbol": "AAPL", "currency": "VND", "close": 500_000}
    assert allocation_records(holdings(), [quote])["USD"][0]["share"] == .5
    quote.update(currency="USD", cache_stale=True)
    assert allocation_records(holdings(), [quote])["USD"][0]["share"] == .5


def test_chart_specs_compile_on_installed_altair_and_contain_provenance_labels():
    source = snapshot([Bar("2026-10-15", 100, 100), Bar("2026-10-16", 101, 110)])
    spec = price_chart(source).to_dict()
    assert spec["encoding"]["y"]["title"] == "Giá đóng cửa (USD)"
    assert spec["width"] == "container"
    assert set(allocation_chart(holdings())) == {"VND", "USD"}
    for chart in allocation_chart(holdings()).values():
        assert chart.to_dict()["encoding"]["x"]["scale"]["domain"] == [0, 1]


def test_empty_allocations_and_invalid_positions_stay_empty():
    assert allocation_chart([]) == {}
    assert allocation_records([{"market": "US", "symbol": "AAPL", "quantity": float("inf"), "average_cost": 10}]) == {}


def test_workflow_is_accessible_static_svg():
    svg = workflow_diagram()
    assert 'role="img"' in svg and 'aria-labelledby=' in svg
    assert "Sách bạn chọn" in svg and "Gợi ý có giải thích" in svg
    assert "<script" not in svg and "http://" not in svg.replace('xmlns="http://www.w3.org/2000/svg"', "")
