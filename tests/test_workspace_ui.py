"""Exercise the workspace's real state transitions without external requests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from breakout_ai.market import Bar, MarketService, MarketSnapshot
from breakout_ai.news import Article, NewsResult, NewsService
from breakout_ai.portfolio import Portfolio
from breakout_ai.storage import Store, utc_now
from test_app import app, button


def field(at, kind, label):
    return next(item for item in getattr(at, kind) if item.label == label)


def ledger(tmp_path):
    return Portfolio(Store(tmp_path / "ui.sqlite3", "test-ui"))


def test_trade_buy_sell_and_invalid_oversell_update_the_visible_ledger(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path)
    at.sidebar.radio[0].set_value("Danh mục").run()
    at.radio(key="portfolio_view").set_value("Ghi giao dịch").run()
    at.selectbox(key="trade_market").set_value("US")
    at.text_input(key="trade_symbol").set_value("AAPL")
    at.number_input(key="trade_quantity").set_value(10)
    at.number_input(key="trade_price").set_value(100)
    at.number_input(key="trade_fees").set_value(10)
    at.text_area(key="trade_note").set_value("Initial research position")
    button(at, "Lưu giao dịch").click().run()
    assert not at.exception and any("Đã ghi mua" in item.value for item in at.success)
    assert ledger(tmp_path).holdings()[0]["quantity"] == 10
    assert ledger(tmp_path).holdings()[0]["average_cost"] == 101
    assert any(item.label == "Mã đang sở hữu" and item.value == "1" for item in at.metric)
    at.radio(key="portfolio_view").set_value("Lịch sử giao dịch").run()
    assert any("Initial research position" in frame.value.to_string() for frame in at.dataframe)
    at.radio(key="portfolio_view").set_value("Ghi giao dịch").run()
    at.selectbox(key="trade_market").set_value("US")
    at.text_input(key="trade_symbol").set_value("AAPL")
    at.selectbox(key="trade_side").set_value("SELL")
    at.number_input(key="trade_quantity").set_value(4)
    at.number_input(key="trade_price").set_value(120)
    at.number_input(key="trade_fees").set_value(2)
    button(at, "Lưu giao dịch").click().run()
    assert not at.exception and ledger(tmp_path).holdings()[0]["quantity"] == 6
    assert len(ledger(tmp_path).trades()) == 2
    at.radio(key="portfolio_view").set_value("Lịch sử giao dịch").run()
    assert any(item.label == "Lãi/lỗ đã chốt · USD" and item.value == "+74.00" for item in at.metric)
    at.radio(key="portfolio_view").set_value("Ghi giao dịch").run()
    at.selectbox(key="trade_market").set_value("US")
    at.selectbox(key="trade_side").set_value("SELL")
    at.text_input(key="trade_symbol").set_value("AAPL")
    at.number_input(key="trade_quantity").set_value(7)
    button(at, "Lưu giao dịch").click().run()
    assert not at.exception and any("vượt số cổ phiếu" in item.value for item in at.error)
    assert ledger(tmp_path).holdings()[0]["quantity"] == 6 and len(ledger(tmp_path).trades()) == 2
    at.radio(key="portfolio_view").set_value("Lịch sử giao dịch").run()
    yesterday = datetime.now(timezone(timedelta(hours=7))).date() - timedelta(days=1)
    at.date_input(key="trade_filter_start").set_value(yesterday)
    at.date_input(key="trade_filter_end").set_value(yesterday)
    at.checkbox(key="trade_filter_dates").check().run()
    assert not at.exception and any("Chưa có giao dịch phù hợp" in item.value for item in at.info)
    assert len(ledger(tmp_path).trades()) == 2


def test_chat_search_reopen_new_conversation_and_persist_rename(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path)
    store = Store(tmp_path / "ui.sqlite3", "test-ui")
    first = store.save_turn("Research price multiples", "An answer", {}, "BOTH", None, 100)
    second = store.save_turn("Risk management notes", "Another answer", {}, "BOTH", None, 100)
    at.sidebar.radio[0].set_value("Trợ lý AI").run()
    assert at.sidebar.text_input(key="chat_history_search")
    at.text_input(key="chat_history_search").set_value("multiples").run()
    visible = [item for item in at.button if item.key and item.key.startswith("conversation_")]
    assert len(visible) == 1 and visible[0].key == f"conversation_{first}"
    visible[0].click().run()
    assert not at.exception and len(at.chat_message) == 2
    field(at, "text_input", "Tên cuộc trò chuyện").set_value("Value investing journal")
    button(at, "Lưu tên cuộc trò chuyện").click().run()
    assert not at.exception and next(row for row in store.conversations() if row["id"] == first)["title"] == "Value investing journal"
    button(at, "＋ Trò chuyện mới").click().run()
    assert not at.exception and not at.chat_message
    at.text_input(key="chat_history_search").set_value("journal").run()
    at.button(key=f"conversation_{first}").click().run()
    assert len(at.chat_message) == 2
    assert len(store.conversations()) == 2 and store.messages(second)


def test_overview_shortcuts_open_the_requested_portfolio_view(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path)
    button(at, "Ghi giao dịch mua / bán").click().run()
    assert not at.exception and at.sidebar.radio[0].value == "Danh mục"
    assert at.radio(key="portfolio_view").value == "Ghi giao dịch"
    assert at.text_input(key="trade_symbol")
    at.sidebar.radio[0].set_value("Tổng quan").run()
    button(at, "Xem sổ giao dịch").click().run()
    assert not at.exception and at.radio(key="portfolio_view").value == "Lịch sử giao dịch"
    assert at.text_input(key="trade_filter_symbol")


def test_chat_prompt_chip_saves_one_turn_and_switching_pages_keeps_history(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path)
    at.sidebar.radio[0].set_value("Trợ lý AI").run()
    button(at, "Biên an toàn là gì?").click().run()
    assert not at.exception and len(at.chat_message) == 2
    store = Store(tmp_path / "ui.sqlite3", "test-ui")
    assert len(store.conversations()) == 1
    identifier = store.conversations()[0]["id"]
    at.sidebar.radio[0].set_value("Tin tức").run()
    at.sidebar.radio[0].set_value("Trợ lý AI").run()
    assert not at.exception and len(at.chat_message) == 2
    assert len(store.messages(identifier)) == 2
    assert at.sidebar.button(key=f"conversation_{identifier}")


def test_archived_report_keeps_historical_price_source_date(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path)
    old_day = (datetime.now(timezone(timedelta(hours=7))).date() - timedelta(days=5)).isoformat()
    report = {
        "day": old_day, "fingerprint": "test-archive", "created_at": old_day + "T00:30:00+00:00", "items": [{
            "market": "US", "symbol": "AAPL", "action": "wait", "title": "Cần xem thêm", "owned": False,
            "reason": "Historical fixture", "checks": [], "quote": {"close": 123, "currency": "USD", "as_of": old_day,
            "provider": "test publisher", "source_url": "https://example.org/historical-price", "fetched_at": old_day + "T00:00:00+00:00"},
        }],
    }
    ledger(tmp_path).save_report(report)
    at.run()
    at.selectbox(key="report_day").set_value(old_day).run()
    assert not at.exception
    assert any(f"Giá đóng cửa {old_day}" in item.value for item in at.caption)
    assert any("thời điểm của bản tin" in item.value for item in at.caption)
    assert any("https://example.org/historical-price" in item.value for item in at.markdown)


def test_market_form_renders_real_fixture_chart_with_currency_and_source(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path)
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    bars = [Bar((end - timedelta(days=24 - index)).isoformat(), 100 + index, 1000 + index) for index in range(25)]
    quote = MarketSnapshot("US", "AAPL", "USD", "test-feed", "https://example.org/AAPL", utc_now(), bars)
    calls = []
    def get(self, market, symbol, force=False):
        calls.append((market, symbol, force))
        return quote
    monkeypatch.setattr(MarketService, "get", get)
    at.sidebar.radio[0].set_value("Thị trường").run()
    at.selectbox(key="chart_market").set_value("US")
    at.text_input(key="chart_symbol").set_value("AAPL")
    button(at, "Xem và cập nhật biểu đồ").click().run()
    assert not at.exception and calls == [("US", "AAPL", True)]
    assert len(at.get("arrow_vega_lite_chart")) == 1
    assert any(item.label == "AAPL · USD" and item.value == "124.00" for item in at.metric)
    assert any("test-feed" in item.value and end.isoformat() in item.value for item in at.caption)
    assert any("chưa phải hiệu suất tài khoản" in item.value for item in at.caption)


def test_overview_refresh_displays_stale_return_instead_of_fresh_cache(monkeypatch, tmp_path):
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    bars = [Bar((end - timedelta(days=1)).isoformat(), 58000, 1000), Bar(end.isoformat(), 58200, 1200)]
    fresh = MarketSnapshot("VN", "FPT", "VND", "test-feed", "https://example.org/FPT", utc_now(), bars)
    stale = replace(fresh, cache_stale=True, from_cache=True)
    monkeypatch.setattr(MarketService, "cached", lambda self, market, symbol: fresh)
    calls = []
    def get(self, market, symbol, force=False):
        calls.append((market, symbol, force))
        return stale
    monkeypatch.setattr(MarketService, "get", get)
    at = app(monkeypatch, tmp_path)
    assert not at.exception and not any("Đang xem bản lưu" in item.value for item in at.caption)
    button(at, "Cập nhật biểu đồ").click().run()
    assert not at.exception and calls == [("VN", "FPT", True)]
    assert any("Đang xem bản lưu" in item.value and "chưa thành công" in item.value for item in at.caption)
    assert len(at.get("arrow_vega_lite_chart")) == 1


def test_news_title_source_and_search_without_external_requests(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path)
    now = utc_now()
    article = Article("Vietnam earnings outlook", "https://vnexpress.net/test-article", "Fixture newsroom", "VN", now, now, "https://vnexpress.net/rss/kinh-doanh.rss")
    calls = []
    def fetch(self, market="BOTH", force=False):
        calls.append((market, force))
        return NewsResult([article] if market in {"BOTH", "VN"} else [], [], now)
    monkeypatch.setattr(NewsService, "fetch", fetch)
    at.sidebar.radio[0].set_value("Tin tức").run()
    assert not at.exception and calls[-1] == ("BOTH", False)
    assert any("Vietnam earnings outlook" in item.value and "Fixture newsroom" in item.value for item in at.markdown)
    at.text_input(key="news_search").set_value("no-match-keyword").run()
    assert not at.exception and any("Chưa có tin phù hợp" in item.value for item in at.info)
    assert not any("Vietnam earnings outlook" in item.value for item in at.markdown)
    at.text_input(key="news_search").set_value("")
    at.selectbox(key="news_market").set_value("US").run()
    assert calls[-1] == ("US", False) and any("Chưa có tin phù hợp" in item.value for item in at.info)


def test_overview_auto_load_and_manual_batch_refresh_update_chart(monkeypatch, tmp_path):
    saved, calls = {}, []
    day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    def many(self, pairs, force=False):
        calls.append((list(pairs), force))
        for market, symbol in pairs:
            saved[(market, symbol)] = MarketSnapshot(market, symbol, "VND" if market == "VN" else "USD",
                "test-feed", "https://example.org/prices", utc_now(),
                [Bar(day, 100 if not force else 120, 1000)])
        return [saved[pair] for pair in pairs], []
    monkeypatch.setattr(MarketService, "many", many)
    monkeypatch.setattr(MarketService, "cached", lambda self, market, symbol: saved.get((market, symbol)))
    at = app(monkeypatch, tmp_path)
    assert not at.exception and len(calls) == 1 and len(calls[0][0]) == 6
    assert any("6/6 mã đã cập nhật" in item.value for item in at.caption)
    button(at, "Cập nhật giá theo dõi").click().run()
    assert not at.exception and len(calls) == 2 and calls[-1][1] is True
    assert any(item.label == "FPT · VND" and item.value == "120.00" for item in at.metric)
    at.run()
    assert len(calls) == 2


def test_overview_failed_batch_refresh_preserves_stale_labels(monkeypatch, tmp_path):
    day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    saved, calls = {}, []
    for market, symbol in (("VN", "FPT"), ("VN", "VCB"), ("VN", "VNM"), ("US", "AAPL"), ("US", "MSFT"), ("US", "GOOGL")):
        saved[(market, symbol)] = MarketSnapshot(market, symbol, "VND" if market == "VN" else "USD",
            "test-feed", "https://example.org/prices", utc_now(), [Bar(day, 100, 1000)])
    def many(self, pairs, force=False):
        calls.append(force)
        for pair in pairs:
            saved[pair] = replace(saved[pair], cache_stale=True)
        return [saved[pair] for pair in pairs], []
    monkeypatch.setattr(MarketService, "many", many)
    monkeypatch.setattr(MarketService, "cached", lambda self, market, symbol: saved.get((market, symbol)))
    at = app(monkeypatch, tmp_path)
    assert not at.exception and not calls
    button(at, "Cập nhật giá theo dõi").click().run()
    assert not at.exception and calls == [True]
    assert any("chưa cập nhật được" in item.value for item in at.warning)
    assert any("0/6 mã đã cập nhật" in item.value for item in at.caption)
    assert any("Đang xem bản lưu" in item.value for item in at.caption)
