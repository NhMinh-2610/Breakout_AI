import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
import sqlite3

import pytest

from breakout_ai.portfolio import Portfolio
from breakout_ai.storage import Store


def today(offset=0):
    return (datetime.now(timezone(timedelta(hours=7))).date() + timedelta(days=offset)).isoformat()


def buy(portfolio, key="buy-1", **changes):
    request = {"market": "US", "symbol": "AAPL", "side": "BUY", "quantity": 10, "price": 100, "idempotency_key": key}
    return portfolio.record_trade(**{**request, **changes})


def test_buy_fees_enter_weighted_average_and_sell_fees_reduce_realized_pnl(store):
    portfolio = Portfolio(store)
    first = buy(portfolio, fees=10)
    assert first["average_cost_before"] is None
    assert first["average_cost_after"] == 101
    assert first["net_cash_flow"] == -1010
    assert first["realized_pnl"] is None
    second = buy(portfolio, "buy-2", quantity=5, price=130, fees=5)
    expected_basis = (1010 + 655) / 15
    assert second["average_cost_before"] == 101
    assert second["average_cost_after"] == pytest.approx(expected_basis)
    sold = portfolio.record_trade("US", "AAPL", "SELL", 6, 140, fees=4, idempotency_key="sell-1")
    assert sold["realized_pnl"] == pytest.approx(840 - 4 - 6 * expected_basis)
    assert sold["net_cash_flow"] == 836
    assert sold["quantity_after"] == 9
    assert sold["average_cost_after"] == expected_basis
    assert portfolio.holdings()[0]["average_cost"] == expected_basis
    assert portfolio.holdings()[0]["quantity"] == 9


def test_current_manual_starting_position_is_not_fabricated_as_a_trade(store):
    portfolio = Portfolio(store)
    portfolio.upsert("VN", "FPT", 100, 95000)
    assert portfolio.trades() == []
    sold = portfolio.record_trade("VN", "FPT", "SELL", 40, 100000, fees=6000, idempotency_key="sell")
    assert sold["currency"] == "VND"
    assert sold["realized_pnl"] == 194000
    assert sold["average_cost_before"] == 95000
    assert len(portfolio.trades()) == 1


def test_closing_and_reopening_a_position_preserves_immutable_journal(store):
    portfolio = Portfolio(store)
    buy(portfolio)
    closed = portfolio.record_trade("US", "AAPL", "SELL", 10, 90, fees=5, idempotency_key="close")
    assert closed["quantity_after"] == 0
    assert closed["average_cost_after"] is None
    assert closed["realized_pnl"] == -105
    assert portfolio.holdings() == []
    assert portfolio.has_trades("US", "aapl")
    reopened = buy(portfolio, "reopen", quantity=2, price=80)
    assert reopened["average_cost_before"] is None
    assert reopened["average_cost_after"] == 80
    assert len(portfolio.trades()) == 3


def test_idempotent_retry_returns_same_fill_and_does_not_double_quantity(store):
    portfolio = Portfolio(store)
    first = buy(portfolio, note="  entered once  ")
    retry = buy(portfolio, note="entered once")
    assert first == retry
    assert len(portfolio.trades()) == 1
    assert portfolio.holdings()[0]["quantity"] == 10
    with pytest.raises(ValueError, match="chống trùng"):
        buy(portfolio, quantity=12)
    assert portfolio.holdings()[0]["quantity"] == 10


def test_workspace_isolation_including_idempotency_and_remove(store, settings):
    local = Portfolio(store)
    other = Portfolio(Store(settings.database_path, "other-ledger"))
    local_trade = buy(local, key="shared-key")
    other_trade = buy(other, key="shared-key", price=80)
    assert local_trade["id"] != other_trade["id"]
    assert len(local.trades()) == len(other.trades()) == 1
    assert local.holdings()[0]["average_cost"] == 100
    assert other.holdings()[0]["average_cost"] == 80
    other.remove(local.holdings()[0]["id"])
    assert len(other.holdings()) == 1
    third = Portfolio(Store(settings.database_path, "third-ledger"))
    assert not third.has_trades("US", "AAPL")
    assert third.trades() == []


def test_oversell_and_missing_position_leave_holdings_and_journal_unchanged(store):
    portfolio = Portfolio(store)
    buy(portfolio)
    before = portfolio.holdings()
    for symbol, quantity in (("AAPL", 11), ("MSFT", 1)):
        with pytest.raises(ValueError, match="vượt số"):
            portfolio.record_trade("US", symbol, "SELL", quantity, 100, idempotency_key=symbol)
    assert portfolio.holdings() == before
    assert len(portfolio.trades()) == 1


def test_no_direct_position_override_after_journal_entry(store):
    portfolio = Portfolio(store)
    buy(portfolio)
    holding = portfolio.holdings()[0]
    with pytest.raises(ValueError, match="nhật ký"):
        portfolio.upsert("US", "AAPL", 200, 10)
    with pytest.raises(ValueError, match="nhật ký"):
        portfolio.remove(holding["id"])
    assert portfolio.holdings()[0] == holding
    # Initial positions without a journal can still be corrected or removed.
    portfolio.upsert("US", "MSFT", 2, 200)
    manual = next(row for row in portfolio.holdings() if row["symbol"] == "MSFT")
    portfolio.remove(manual["id"])
    assert len(portfolio.holdings()) == 1


def test_database_failure_rolls_back_trade_insert_and_position_mutation(store):
    portfolio = Portfolio(store)
    buy(portfolio)
    original = portfolio.holdings()
    with store.connection() as db:
        db.executescript("CREATE TRIGGER fail_holding_update BEFORE UPDATE ON holdings BEGIN SELECT RAISE(ABORT, 'fixture failure'); END;")
    with pytest.raises(sqlite3.IntegrityError, match="fixture failure"):
        buy(portfolio, "failing-buy", quantity=1)
    assert portfolio.holdings() == original
    assert len(portfolio.trades()) == 1


def test_journal_rejects_sql_update_and_delete(store):
    portfolio = Portfolio(store)
    entry = buy(portfolio)
    for query in ("UPDATE trades SET price=1 WHERE id=?", "DELETE FROM trades WHERE id=?"):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            with store.connection() as db:
                db.execute(query, (entry["id"],))
    assert portfolio.trades()[0] == entry


def test_chronology_rejects_before_initial_snapshot_or_latest_fill(store):
    portfolio = Portfolio(store)
    portfolio.upsert("US", "MSFT", 10, 200)
    with pytest.raises(ValueError, match="thứ tự thời gian"):
        buy(portfolio, symbol="MSFT", trade_date=today(-1))
    buy(portfolio, trade_date=today(-5))
    buy(portfolio, "later", trade_date=today(-2))
    with pytest.raises(ValueError, match="thứ tự thời gian"):
        buy(portfolio, "out-of-order", trade_date=today(-3))
    assert len(portfolio.trades()) == 2
    assert next(row for row in portfolio.holdings() if row["symbol"] == "AAPL")["quantity"] == 20


def test_chronology_remains_enforced_after_full_close(store):
    portfolio = Portfolio(store)
    buy(portfolio, trade_date=today(-5))
    portfolio.record_trade("US", "AAPL", "SELL", 10, 110, trade_date=today(-1), idempotency_key="close")
    with pytest.raises(ValueError, match="thứ tự thời gian"):
        buy(portfolio, "reopen-too-early", trade_date=today(-3))
    assert portfolio.holdings() == []


@pytest.mark.parametrize("changes", [
    {"quantity": 0}, {"quantity": -1}, {"quantity": True}, {"quantity": float("nan")},
    {"quantity": float("inf")}, {"quantity": 1e11}, {"price": 0}, {"price": float("inf")},
    {"price": 1e308}, {"fees": -1}, {"fees": float("nan")}, {"fees": True},
    {"trade_date": "2099-01-01"}, {"trade_date": "2026-02-30"}, {"trade_date": "20260101"},
    {"side": "HOLD"}, {"market": "UK"}, {"symbol": "INVALID SYMBOL"},
    {"note": "x" * 1501}, {"idempotency_key": ""}, {"idempotency_key": " "},
])
def test_invalid_trade_never_creates_history_or_holdings(store, changes):
    portfolio = Portfolio(store)
    with pytest.raises(ValueError):
        buy(portfolio, **changes)
    assert portfolio.trades() == []
    assert portfolio.holdings() == []


def test_nonfinite_weighted_cost_and_realized_pnl_fail_atomically(store):
    portfolio = Portfolio(store)
    buy(portfolio, quantity=1, price=9e307)
    with pytest.raises(ValueError, match="phạm vi"):
        buy(portfolio, "overflow-buy", quantity=1, price=9e307)
    with pytest.raises(ValueError, match="phạm vi"):
        portfolio.record_trade("US", "AAPL", "SELL", 1, 1, fees=1e308, idempotency_key="overflow-loss")
    assert len(portfolio.trades()) == 1
    assert portfolio.holdings()[0]["quantity"] == 1


def test_twenty_position_limit_is_atomic_and_workspace_scoped(store):
    portfolio = Portfolio(store)
    for index in range(20):
        portfolio.upsert("US", f"T{index}", 1, 100)
    with pytest.raises(ValueError, match="20"):
        buy(portfolio)
    assert len(portfolio.holdings()) == 20
    assert portfolio.trades() == []


def test_filters_and_csv_keep_currencies_separate_and_neutralize_formula_notes(store):
    portfolio = Portfolio(store)
    buy(portfolio, trade_date=today(-5), note="=HYPERLINK(\"malicious\")")
    buy(portfolio, "vn", market="VN", symbol="FPT", price=100000, trade_date=today(-3))
    portfolio.record_trade("US", "AAPL", "SELL", 2, 120, trade_date=today(-1), idempotency_key="sell")
    assert [row["side"] for row in portfolio.trades("US", "aapl")] == ["SELL", "BUY"]
    assert len(portfolio.trades(side="BUY")) == 2
    assert portfolio.trades(start_date=today(-4), end_date=today(-2))[0]["symbol"] == "FPT"
    assert len(portfolio.trades(limit=1)) == 1
    rows = list(csv.DictReader(StringIO(portfolio.export_trades_csv("US"))))
    assert len(rows) == 2
    assert rows[1]["note"].startswith("'=HYPERLINK")
    assert {row["currency"] for row in rows} == {"USD"}
    assert portfolio.trade_count() == 3
    assert portfolio.trade_count("US", "aapl") == 2
    assert portfolio.trade_count("VN") == 1
    assert "workspace" not in rows[0] and "idempotency_key" not in rows[0]
    with pytest.raises(ValueError):
        portfolio.trades(start_date=today(), end_date=today(-1))


def test_duplicate_submission_after_other_trades_returns_original_receipt(store):
    portfolio = Portfolio(store)
    original = buy(portfolio)
    buy(portfolio, "next-buy", quantity=2)
    assert buy(portfolio) == original
    assert portfolio.holdings()[0]["quantity"] == 12
    assert len(portfolio.trades()) == 2


@pytest.mark.parametrize("first,second,total", [(0.1, 0.2, 0.3), (0.1, 0.7, 0.8)])
def test_fractional_positions_close_without_rounding_oversell_or_residual(store, first, second, total):
    portfolio = Portfolio(store)
    buy(portfolio, quantity=first)
    buy(portfolio, "fractional-second", quantity=second)
    assert portfolio.holdings()[0]["quantity"] == total
    closed = portfolio.record_trade("US", "AAPL", "SELL", total, 110, idempotency_key="fractional-close")
    assert closed["quantity_after"] == 0
    assert portfolio.holdings() == []


def test_large_position_does_not_allow_material_oversell_by_relative_tolerance(store):
    portfolio = Portfolio(store)
    buy(portfolio, quantity=1e9, price=1)
    with pytest.raises(ValueError, match="vượt số"):
        portfolio.record_trade("US", "AAPL", "SELL", 1e9 + 0.1, 1, idempotency_key="oversell")
    assert portfolio.holdings()[0]["quantity"] == 1e9
