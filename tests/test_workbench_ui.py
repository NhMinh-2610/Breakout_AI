"""Offline integration coverage for chart, signal scan and contextual market chat."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import httpx
import pytest

from breakout_ai.intraday import Candle, IntradayService, IntradaySnapshot, SUPPORTED_INDICES
from breakout_ai.realtime import BoardSnapshot, RealtimeService
from breakout_ai.storage import Store
from test_app import app, button
from test_priceboard_ui import quote


def signal_markup(at):
    return [item.value for item in at.markdown if item.value.startswith('<section class="signal-card">')]


@pytest.fixture
def workbench(monkeypatch, tmp_path):
    symbols = ["VIC", "FPT", "VCB", "HPG", "SSI", "MBB", "TCB"]
    now = datetime.now(timezone.utc)
    end = now.replace(minute=now.minute // 5 * 5, second=0, microsecond=0)
    stamp = now.isoformat()
    store = Store(tmp_path / "ui.sqlite3", "test-ui")
    with store.connection() as db:
        db.execute("CREATE TABLE board_preferences (workspace TEXT PRIMARY KEY, symbols TEXT NOT NULL)")
        db.execute("INSERT INTO board_preferences VALUES (?,?)", ("test-ui", json.dumps(symbols)))
    quotes = [replace(quote(symbol, "HOSE"), source_timestamp=stamp, received_at=stamp,
                      depth_timestamp=stamp) for symbol in symbols]
    state = SimpleNamespace(mode="fresh", store=store, symbols=symbols, quotes=quotes,
                            calls={"quotes": [], "quote_cache": [], "candles": [], "candle_cache": []})

    def chart(symbol, resolution):
        if state.mode == "failure":
            return IntradaySnapshot(symbol, resolution=resolution, errors=["Nguồn nến tạm thời lỗi."])
        minutes = int(resolution)
        latest_end = end if minutes == 5 else now.replace(second=0, microsecond=0)
        if state.mode == "stale":
            latest_end -= timedelta(days=1)
        rows = []
        for index in range(40):
            close = 101_500 if index == 39 else 100_000
            opened = 100_000
            rows.append(Candle(
                time=(latest_end - timedelta(minutes=minutes * (40 - index))).isoformat(),
                open=opened, high=max(opened, close) + 1, low=min(opened, close) - 1,
                close=close, volume=200 if index == 39 else 100,
                interval_minutes=minutes, complete=True,
            ))
        return IntradaySnapshot(symbol, resolution=resolution, candles=rows, fetched_at=stamp,
                                stale=state.mode in ("stale", "cached_error"),
                                errors=["Lỗi tải lại; đang xem cache."] if state.mode == "cached_error" else [],
                                asset_type="index" if symbol in SUPPORTED_INDICES else "equity",
                                price_unit="points" if symbol in SUPPORTED_INDICES else "VND")

    def fetch_chart(self, symbol, resolution="5", force=False):
        state.calls["candles"].append((symbol, resolution, force))
        return chart(symbol, resolution)

    def cached_chart(self, symbol, resolution="5"):
        state.calls["candle_cache"].append((symbol, resolution))
        return chart(symbol, resolution)

    def snapshot(selected, interval):
        return BoardSnapshot(quotes=[row for row in state.quotes if row.symbol in selected],
                             fetched_at=stamp, poll_seconds=interval)

    def fetch_quotes(self, selected, force=False):
        state.calls["quotes"].append((list(selected), force))
        return snapshot(selected, self.poll_seconds)

    def cached_quotes(self, selected):
        state.calls["quote_cache"].append(list(selected))
        return snapshot(selected, self.poll_seconds)

    def forbid_network(*args, **kwargs):
        raise AssertionError("Workbench UI tests must not access an external network.")

    monkeypatch.setattr(IntradayService, "fetch", fetch_chart)
    monkeypatch.setattr(IntradayService, "cached", cached_chart)
    monkeypatch.setattr(RealtimeService, "fetch", fetch_quotes)
    monkeypatch.setattr(RealtimeService, "cached", cached_quotes)
    monkeypatch.setattr(httpx.Client, "send", forbid_network)
    monkeypatch.setenv("MARKET_DATA_ENABLED", "true")

    def open_board():
        at = app(monkeypatch, tmp_path)
        at.sidebar.radio[0].set_value("Thị trường").run()
        assert not at.exception
        return at

    state.open = open_board
    return state


def test_board_contains_candles_depth_analysis_chat_and_scan_in_one_workspace(workbench):
    at = workbench.open()
    assert at.radio(key="market_view").value == "Bảng điện Việt Nam"
    assert len(at.get("arrow_vega_lite_chart")) >= 2
    assert {tab.label for tab in at.tabs} >= {
        "Thông tin phiên", "Cung cầu 3 mức", "Phân tích", "Chat theo mã", "Cơ hội hôm nay",
    }
    assert signal_markup(at)
    assert at.text_input(key="market_chat_question")
    assert at.multiselect(key="market_scan_choices").max_selections == 6
    assert at.button(key="market_scan_run")
    assert any("SMA20" in item.value for item in at.caption)
    assert len([call for call in workbench.calls["candles"] if call[0] in workbench.symbols]) == 1


def test_changing_selected_symbol_updates_chart_signal_and_question_context(workbench):
    at = workbench.open()
    at.selectbox(key="board_selected").set_value("VIC").run()
    assert not at.exception
    assert any("VIC · Biểu đồ nến 5 phút" in item.value for item in at.markdown)
    assert "<strong>VIC</strong>" in signal_markup(at)[0]
    assert at.text_input(key="market_chat_question").label == "Hỏi về VIC"
    assert workbench.calls["candles"][-1][0] == "VIC"
    at.selectbox(key="board_selected").set_value("FPT").run()
    assert not at.exception
    assert any("FPT · Biểu đồ nến 5 phút" in item.value for item in at.markdown)
    assert "<strong>FPT</strong>" in signal_markup(at)[0]
    assert at.text_input(key="market_chat_question").label == "Hỏi về FPT"


def test_sending_chat_saves_one_captured_turn_and_does_not_repeat_on_refresh(workbench):
    at = workbench.open()
    selected = at.selectbox(key="board_selected").value
    at.text_input(key="market_chat_question").set_value("Hỗ trợ có phải đáy không?")
    button(at, "Gửi").click().run()
    assert not at.exception
    conversations = workbench.store.conversations()
    assert len(conversations) == 1
    messages = workbench.store.messages(conversations[0]["id"])
    assert len(messages) == 2
    answer = messages[1]
    assert answer["metadata"]["provider"] == "market-copilot"
    assert answer["metadata"]["screening"][0]["symbol"] == selected
    assert answer["metadata"]["screening"][0]["as_of"]
    assert answer["metadata"]["market_data"][0]["symbol"] == selected
    captured_time = answer["metadata"]["market_data"][0]["source_timestamp"]
    assert "chưa chứng minh đã tạo đáy" in answer["content"]
    at.run()
    assert not at.exception and len(at.chat_message) == 2
    assert len(workbench.store.messages(conversations[0]["id"])) == 2
    # A later quote must not rewrite evidence already stored with the answer.
    workbench.quotes[:] = [replace(row, last=102_000) for row in workbench.quotes]
    at.run()
    stored = workbench.store.messages(conversations[0]["id"])[1]
    assert stored["metadata"]["market_data"][0]["last"] == pytest.approx(101_500)
    assert stored["metadata"]["market_data"][0]["source_timestamp"] == captured_time


def test_chat_refuses_to_reuse_selected_symbol_data_for_another_security(workbench):
    at = workbench.open()
    at.selectbox(key="board_selected").set_value("VIC").run()
    at.text_input(key="market_chat_question").set_value("Có nên mua FPT không?")
    button(at, "Gửi").click().run()
    assert not at.exception
    messages = workbench.store.messages(workbench.store.conversations()[0]["id"])
    assert messages[1]["metadata"]["model"] == "symbol-check"
    assert "gắn với **VIC**" in messages[1]["content"]
    assert "chọn mã FPT" in messages[1]["content"]
    assert messages[1]["metadata"]["market_data"] == []


def test_scan_is_opt_in_and_bounded_to_six_watchlist_symbols(workbench):
    at = workbench.open()
    assert len([call for call in workbench.calls["candles"] if call[0] in workbench.symbols]) == 1
    chosen = workbench.symbols[:6]
    at.multiselect(key="market_scan_choices").set_value(chosen).run()
    workbench.calls["candles"].clear()
    at.button(key="market_scan_run").click().run()
    assert not at.exception
    forced = [call for call in workbench.calls["candles"] if call[2]]
    assert len(forced) == 6 and {call[0] for call in forced} == set(chosen)
    assert len(signal_markup(at)) == 7  # selected detail plus six scan cards


def test_previous_session_scan_never_presents_an_active_buy_or_sell(workbench):
    workbench.mode = "stale"
    at = workbench.open()
    at.button(key="market_scan_run").click().run()
    assert not at.exception
    cards = signal_markup(at)
    assert len(cards) == 7
    assert all('class="signal-tag wait"' in card for card in cards)
    assert all('class="signal-tag watch_buy"' not in card and 'class="signal-tag watch_sell"' not in card
               for card in cards)
    assert any("ngoài phiên" in item.value for item in at.caption)


def test_pause_uses_intraday_cache_and_manual_chart_refresh_fetches_once(workbench):
    at = workbench.open()
    before = len(workbench.calls["candles"])
    at.checkbox(key="board_auto").uncheck().run()
    assert not at.exception and len(workbench.calls["candles"]) == before
    assert workbench.calls["candle_cache"]
    at.selectbox(key="board_selected").set_value("VIC").run()
    assert len(workbench.calls["candles"]) == before
    at.button(key="market_chart_refresh").click().run()
    assert not at.exception and len(workbench.calls["candles"]) == before + 1
    assert workbench.calls["candles"][-1] == ("VIC", "5", True)
    assert not at.checkbox(key="board_auto").value
    at.run()
    assert len(workbench.calls["candles"]) == before + 1


def test_source_failure_preserves_chat_and_explains_wait_instead_of_fake_candles(workbench):
    workbench.mode = "failure"
    at = workbench.open()
    assert any("Nguồn chưa trả đủ nến" in item.value for item in at.info)
    assert 'class="signal-tag wait"' in signal_markup(at)[0]
    assert at.text_input(key="market_chat_question")
    at.text_input(key="market_chat_question").set_value("Hôm nay có nên mua không?")
    button(at, "Gửi").click().run()
    assert not at.exception
    messages = workbench.store.messages(workbench.store.conversations()[0]["id"])
    assert messages[1]["metadata"]["screening"][0]["action"] == "wait"
    assert messages[1]["metadata"]["data_errors"]


def test_cached_recent_candles_after_source_error_cannot_create_active_signal(workbench):
    workbench.mode = "cached_error"
    at = workbench.open()
    assert 'class="signal-tag wait"' in signal_markup(at)[0]
    at.button(key="market_scan_run").click().run()
    assert not at.exception
    assert all('class="signal-tag wait"' in card for card in signal_markup(at))
    at.text_input(key="market_chat_question").set_value("Vì sao cần chờ?")
    button(at, "Gửi").click().run()
    assert not at.exception
    messages = workbench.store.messages(workbench.store.conversations()[0]["id"])
    analysis = messages[1]["metadata"]["screening"][0]
    assert analysis["action"] == "wait" and analysis["blockers"]


def test_conversations_follow_each_selected_symbol_without_mixing_history(workbench):
    at = workbench.open()
    at.selectbox(key="board_selected").set_value("VIC").run()
    at.text_input(key="market_chat_question").set_value("Vùng hỗ trợ hiện tại?")
    button(at, "Gửi").click().run()
    assert not at.exception and len(at.chat_message) == 2
    at.selectbox(key="board_selected").set_value("FPT").run()
    assert not at.exception and not at.chat_message
    at.selectbox(key="board_selected").set_value("VIC").run()
    assert not at.exception and len(at.chat_message) == 2
    assert len(workbench.store.conversations()) == 1
