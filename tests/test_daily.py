from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from breakout_ai.book_rules import learn_rules
from breakout_ai.books import BookLibrary
from breakout_ai.daily import DailyPlanner, closed_snapshot, rules_signature
from breakout_ai.market import Bar, MarketSnapshot
from breakout_ai.portfolio import Portfolio
from breakout_ai.storage import Store, utc_now


class Quotes:
    def __init__(self, samples=()):
        self.samples, self.calls = samples, 0

    def many(self, identities, force=False):
        self.calls += 1
        return [sample for sample in self.samples if (sample.market, sample.symbol) in identities], []


def quote(symbol="AAPL", price=100, days=30, stale=False):
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    bars = [Bar((end - timedelta(days=days - i - 1)).isoformat(), price - days + i + 1, 10000) for i in range(days)]
    return MarketSnapshot("US", symbol, "USD", "fixture", "https://example.org/price", utc_now(), bars, cache_stale=stale)


def planner(settings, store, text="Buy when price is above the 20-day moving average.\nSell when price falls 8% below purchase price.", samples=()):
    library = BookLibrary(store)
    if text:
        library.ingest("rules.txt", text.encode(), "Self-authored test rules")
    portfolio = Portfolio(store)
    portfolio.set_preferences(candidates=[["US", "AAPL"]])
    instance = DailyPlanner(settings, portfolio, library, Quotes(samples))
    portfolio.set_preferences(approved_rules=rules_signature(instance.rules()))
    return instance


def test_owned_positions_separate_from_watchlist_and_scoped(store, settings):
    store.upsert_watch("US", "AAPL", "not owned")
    positions = Portfolio(store)
    assert positions.holdings() == []
    positions.upsert("US", "aapl", 10, 120)
    positions.upsert("US", "AAPL", 12, 110)
    assert len(positions.holdings()) == 1 and positions.holdings()[0]["quantity"] == 12
    other = Portfolio(Store(settings.database_path, "other"))
    other.remove(positions.holdings()[0]["id"])
    assert other.holdings() == [] and len(positions.holdings()) == 1
    for value in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            positions.upsert("US", "AAPL", value, 100)


@pytest.mark.parametrize("sentence,kind,value", [
    ("Mua khi giá nằm trên đường trung bình 20 ngày.", "buy_above_ma", 20),
    ("Bán khi giá giảm 8% so với giá mua.", "stop_loss_pct", 8),
    ("Bán khi giá tăng 20% so với giá vốn.", "take_profit_pct", 20),
    ("Buy when price crosses above the 20-day moving average.", "buy_cross_ma", 20),
    ("Sell when price crosses below MA 50.", "sell_cross_ma", 50),
    ("Mua khi giá thấp hơn giá trị nội tại 30%.", "margin_of_safety_pct", 30),
    ("Sell when price rises 12.5% above purchase price.", "take_profit_pct", 12.5),
])
def test_rules_keep_exact_sentence_and_provenance(store, sentence, kind, value):
    library = BookLibrary(store)
    identifier, _ = library.ingest("rules.md", sentence.encode(), "Book")
    rules = learn_rules(library.passages(identifier))
    assert len(rules) == 1 and rules[0].kind == kind and rules[0].value == value
    assert rules[0].quote == sentence and rules[0].citation["document_id"] == identifier


@pytest.mark.parametrize("text", [
    "For example, sell when price falls 8% below purchase price.",
    "Do not sell when price falls 8% below purchase price.",
    "Don't buy when price crosses above MA 20.",
    "Bán khi giá giảm từ 7 đến 8% so với giá vốn.",
    "Sell if price falls 7 or 8% below purchase price.",
    "Sell if price falls 7 to 8% below purchase price.",
    "Sell if price falls 7-8% below purchase price.",
    "Buy when price is above MA 20 and volume increases.",
    "Buy when price crosses above MA 20 or MA 50.",
    "Buy when volume is above MA 20.",
    "Sell if price falls less than 8% below purchase price.",
    "Buy when price is below intrinsic value.",
    "Margin of safety helps account for uncertainty in valuation.",
])
def test_ambiguous_negated_and_qualitative_sentences_do_not_invent_rules(store, text):
    library = BookLibrary(store)
    library.ingest("rule.txt", text.encode())
    assert learn_rules(library.passages()) == []


def test_no_book_no_rules_and_unreviewed_rules_skip_market(settings, store):
    daily = planner(settings, store, text="")
    assert daily.get_today()["status"] == "needs_book" and daily.market.calls == 0
    daily.books.ingest("knowledge.txt", b"Intrinsic value is an uncertain estimate.")
    assert daily.get_today()["status"] == "needs_measurable_rules" and daily.market.calls == 0
    identifier, _ = daily.books.ingest("rules.txt", b"Buy when price is above MA 20.")
    daily.portfolio.set_preferences(active_book=identifier)
    assert daily.get_today()["status"] == "needs_rule_review" and daily.market.calls == 0


def test_buy_sell_hold_and_revision_invalidation(settings, store):
    daily = planner(settings, store, samples=[quote(), quote("MSFT", 100), quote("GOOGL", 100)])
    daily.portfolio.upsert("US", "MSFT", 10, 120)
    daily.portfolio.upsert("US", "GOOGL", 5, 101)
    report = daily.get_today()
    items = {item["symbol"]: item for item in report["items"]}
    assert items["AAPL"]["action"] == "buy" and not items["AAPL"]["owned"]
    assert items["MSFT"]["action"] == "sell" and items["MSFT"]["owned"]
    assert items["GOOGL"]["action"] == "hold"
    assert items["MSFT"]["pnl"] == -200
    assert items["AAPL"]["checks"][0]["quote"] in daily.books.passages()[0].text
    calls = daily.market.calls
    assert daily.get_today() == report and daily.market.calls == calls
    daily.portfolio.upsert("US", "MSFT", 10, 100)
    assert daily.get_today()["fingerprint"] != report["fingerprint"] and daily.market.calls > calls
    assert daily.portfolio.report(report["day"]) is not None
    other = Portfolio(Store(settings.database_path, "other"))
    assert other.report(report["day"]) is None


def test_stale_short_history_and_missing_quotes_wait(settings, store):
    daily = planner(settings, store, samples=[quote(stale=True)])
    assert daily.get_today()["items"][0]["action"] == "wait"
    daily.market.samples = [quote(days=5)]
    assert daily.get_today(refresh=True)["items"][0]["action"] == "wait"
    daily.market.samples = []
    assert daily.get_today(refresh=True)["items"][0]["action"] == "wait"


def test_margin_of_safety_requires_user_estimate(settings, store):
    daily = planner(settings, store, text="Buy when price is 30% below intrinsic value.", samples=[quote()])
    assert daily.get_today()["items"][0]["action"] == "wait"
    daily.portfolio.set_preferences(estimates={"US:AAPL": 200})
    assert daily.get_today()["items"][0]["action"] == "buy"


def test_known_sell_trigger_survives_an_unavailable_secondary_rule(settings, store):
    daily = planner(settings, store, text="Sell when price falls 8% below purchase price.\nSell when price is below MA 200.", samples=[quote()])
    daily.portfolio.upsert("US", "AAPL", 1, 120)
    assert daily.get_today()["items"][0]["action"] == "sell"


@pytest.mark.parametrize("text,price", [
    ("Sell when price falls 8% below purchase price.", 92),
    ("Sell when price rises 20% above purchase price.", 120),
])
def test_exact_threshold_does_not_miss_due_to_float_rounding(settings, store, text, price):
    daily = planner(settings, store, text=text, samples=[quote(price=price)])
    daily.portfolio.upsert("US", "AAPL", 10, 100)
    assert daily.get_today()["items"][0]["action"] == "sell"


def test_cross_is_a_new_cross_not_merely_above_average(settings, store):
    sample = quote(price=110)
    bars = [replace(bar, close=100) for bar in sample.bars]
    bars[-2], bars[-1] = replace(bars[-2], close=90), replace(bars[-1], close=110)
    daily = planner(settings, store, text="Buy when price crosses above MA 20.", samples=[replace(sample, bars=bars)])
    assert daily.get_today()["items"][0]["action"] == "buy"
    bars[-2] = replace(bars[-2], close=105)
    daily.market.samples = [replace(sample, bars=bars)]
    assert daily.get_today(refresh=True)["items"][0]["action"] == "wait"


def test_selected_book_is_not_mixed_with_other_strategies(settings, store):
    daily = planner(settings, store, samples=[quote()])
    active = daily.active_book()["id"]
    daily.books.ingest("second.txt", b"Buy when price is 50% below intrinsic value.", "Other strategy")
    assert daily.active_book()["id"] == active
    assert {rule.kind for rule in daily.rules()} == {"buy_above_ma", "stop_loss_pct"}


def test_deleting_book_removes_its_report_but_not_other_workspace(settings, store):
    daily = planner(settings, store)
    report = daily.get_today()
    other = BookLibrary(Store(settings.database_path, "other"))
    other.delete(daily.active_book()["id"])
    assert daily.portfolio.report(report["day"])
    daily.books.delete(daily.active_book()["id"])
    assert daily.portfolio.report(report["day"]) is None


def test_session_cutoff_drops_in_progress_us_and_vn_bars():
    sample = replace(quote(), bars=[Bar("2026-10-15", 100, 1000), Bar("2026-10-16", 110, 1000)])
    during = datetime(2026, 10, 16, 18, tzinfo=timezone.utc)
    assert closed_snapshot(sample, during).latest.date == "2026-10-15"
    assert closed_snapshot(sample, during.replace(hour=22)).latest.date == "2026-10-16"
    vn = replace(sample, market="VN", currency="VND")
    assert closed_snapshot(vn, during.replace(hour=8)).latest.date == "2026-10-15"
    assert closed_snapshot(vn, datetime(2026, 10, 17, 0, 30, tzinfo=timezone.utc)).latest.date == "2026-10-16"
