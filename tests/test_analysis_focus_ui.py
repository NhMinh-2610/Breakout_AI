"""The primary application flow observes one sourced chart before anything else."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import httpx
import pytest

from breakout_ai.config import Settings
from breakout_ai.daily import DailyPlanner
from breakout_ai.intraday import Candle, IntradayService, IntradaySnapshot, SUPPORTED_INDICES
from breakout_ai.providers import Completion
from breakout_ai.realtime import BoardSnapshot, PriceLevel, RealtimeService
from breakout_ai.storage import Store
from test_app import app
from test_priceboard_ui import quote


@pytest.fixture
def focus(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    end = now.replace(minute=now.minute // 5 * 5, second=0, microsecond=0)
    stamp = now.isoformat()
    symbols = ["VIC", "FPT", "VCB"]
    store = Store(tmp_path / "ui.sqlite3", "test-ui")
    with store.connection() as db:
        db.execute("CREATE TABLE board_preferences (workspace TEXT PRIMARY KEY, symbols TEXT NOT NULL)")
        db.execute("INSERT INTO board_preferences VALUES (?,?)", ("test-ui", json.dumps(symbols)))
    state = SimpleNamespace(
        store=store, symbols=symbols, now=now, end=end, mode="fresh",
        calls={"quotes": [], "quote_cache": [], "candles": [], "candle_cache": [], "model": []},
    )
    bases = {"VIC": 200_000, "FPT": 100_000, "VCB": 80_000}
    quotes = [
        replace(
            quote(symbol, "HOSE"), reference=base, ceiling=base * 1.07, floor=base * .93,
            last=base * 1.015, change=base * .015, open=base, high=base * 1.015,
            low=base, average=base * 1.005,
            bids=[PriceLevel(base - 100 * (index + 1), 1000) for index in range(3)],
            asks=[PriceLevel(base + 100 * (index + 1), 800) for index in range(3)],
            source_timestamp=stamp, received_at=stamp, depth_timestamp=stamp,
        )
        for symbol, base in bases.items()
    ]
    state.quotes = quotes

    def board(selected, interval):
        return BoardSnapshot(quotes=[item for item in state.quotes if item.symbol in selected],
                             fetched_at=stamp, poll_seconds=interval)

    def fetch_quotes(self, selected, force=False):
        state.calls["quotes"].append((list(selected), force))
        return board(selected, self.poll_seconds)

    def cached_quotes(self, selected):
        state.calls["quote_cache"].append(list(selected))
        return board(selected, self.poll_seconds)

    def chart(symbol, resolution):
        if state.mode == "source_error" and symbol not in SUPPORTED_INDICES:
            return IntradaySnapshot(symbol, resolution=resolution,
                                    errors=["Nguồn nến chưa sẵn sàng."])
        minutes = int(resolution)
        base = bases.get(symbol, 1_500)
        finish = end if minutes == 5 else now.replace(second=0, microsecond=0)
        rows = [
            Candle(
                time=(finish - timedelta(minutes=minutes * (40 - index))).isoformat(),
                open=base, high=(base * 1.015 if index == 39 else base) + 1,
                low=base - 1, close=base * 1.015 if index == 39 else base,
                volume=200 if index == 39 else 100, interval_minutes=minutes,
                complete=True,
            )
            for index in range(40)
        ]
        # Visible on the chart, but not eligible for a completed-bar AI context.
        rows.append(Candle(finish.isoformat(), base, base * 1.02, base - 1,
                           base * 1.01, 999_999, minutes, False))
        is_index = symbol in SUPPORTED_INDICES
        return IntradaySnapshot(
            symbol, resolution=resolution, candles=rows, fetched_at=stamp, stale=False,
            asset_type="index" if is_index else "equity",
            price_unit="points" if is_index else "VND",
        )

    def fetch_chart(self, symbol, resolution="5", force=False):
        state.calls["candles"].append((symbol, resolution, force))
        return chart(symbol, resolution)

    def cached_chart(self, symbol, resolution="5"):
        state.calls["candle_cache"].append((symbol, resolution))
        return chart(symbol, resolution)

    def forbid_network(*args, **kwargs):
        raise AssertionError("Analysis-focus UI tests must not access external HTTP.")

    def forbid_planner(*args, **kwargs):
        raise AssertionError("Opening chart analysis must not run the daily book planner.")

    def forbid_model(*args, **kwargs):
        raise AssertionError("Market polling and demo mode must not call an LLM.")

    monkeypatch.setattr(RealtimeService, "fetch", fetch_quotes)
    monkeypatch.setattr(RealtimeService, "cached", cached_quotes)
    monkeypatch.setattr(IntradayService, "fetch", fetch_chart)
    monkeypatch.setattr(IntradayService, "cached", cached_chart)
    monkeypatch.setattr(httpx.Client, "send", forbid_network)
    monkeypatch.setattr(DailyPlanner, "get_today", forbid_planner)
    monkeypatch.setattr("breakout_ai.copilot.complete", forbid_model)
    monkeypatch.setenv("MARKET_DATA_ENABLED", "true")

    def open_app():
        result = app(monkeypatch, tmp_path, initial_page=None)
        assert not result.exception
        return result

    def configure_model():
        from_env = Settings.from_env
        monkeypatch.setattr(Settings, "from_env", classmethod(
            lambda cls: replace(from_env(), provider="openai", model="ui-chart-test",
                                api_key="not-a-real-key")))
        def complete(settings, instructions, messages, transport=None):
            context = json.loads(instructions.split("CONTEXT_JSON:\n", 1)[1])
            state.calls["model"].append(context)
            facts = context["chart"]["facts"]
            risks = [fact["id"] for fact in facts if fact["role"] in {"risk", "blocker"}]
            return Completion(json.dumps({
                "action": context["analysis"]["action"],
                "focus_fact_ids": [facts[0]["id"]],
                "risk_fact_ids": risks[:5],
                "scenario_id": None,
            }))
        monkeypatch.setattr("breakout_ai.copilot.complete", complete)

    state.open = open_app
    state.configure_model = configure_model
    return state


def _review(at):
    return at.button(key="market_ai_review").click().run()


def _saved_reply(state):
    conversation = state.store.conversations()[0]
    return state.store.messages(conversation["id"])[-1]


def test_real_default_home_starts_with_one_chart_and_never_runs_book_planner(focus):
    at = focus.open()
    assert at.sidebar.radio[0].value == "Thị trường"
    assert at.radio(key="market_view").value == "Phân tích biểu đồ"
    assert at.selectbox(key="analysis_symbol").value == "VIC"
    assert at.get("arrow_vega_lite_chart")
    assert at.button(key="market_ai_review")
    assert at.text_input(key="market_chat_question")
    assert not any('class="priceboard-table"' in item.value or 'class="market-index-card"' in item.value
                   for item in at.markdown)
    assert not any(item.key == "board_selected" for item in at.selectbox)
    assert focus.calls["quotes"] == [(["VIC"], False)]
    assert focus.calls["candles"] == [("VIC", "5", False)]
    assert focus.store.usage() == 0 and not focus.store.conversations()
    at.run()
    assert not at.exception and focus.store.usage() == 0


def test_primary_pause_and_refresh_request_only_the_selected_symbol(focus):
    at = focus.open()
    quote_count = len(focus.calls["quotes"])
    candle_count = len(focus.calls["candles"])
    at.checkbox(key="analysis_auto").uncheck().run()
    assert len(focus.calls["quotes"]) == quote_count
    assert len(focus.calls["candles"]) == candle_count
    assert focus.calls["quote_cache"][-1] == ["VIC"]
    at.selectbox(key="analysis_symbol").set_value("FPT").run()
    assert not at.exception and focus.calls["quote_cache"][-1] == ["FPT"]
    assert focus.calls["candle_cache"][-1] == ("FPT", "5")
    assert len(focus.calls["quotes"]) == quote_count
    at.button(key="analysis_refresh").click().run()
    assert not at.exception
    assert len(focus.calls["quotes"]) == quote_count + 1
    assert len(focus.calls["candles"]) == candle_count + 1
    assert focus.calls["quotes"][-1] == (["FPT"], True)
    assert focus.calls["candles"][-1] == ("FPT", "5", True)
    assert not at.checkbox(key="analysis_auto").value
    at.run()
    assert len(focus.calls["quotes"]) == quote_count + 1


def test_explicit_model_review_saves_completed_candles_and_validated_facts_once(focus):
    focus.configure_model()
    at = focus.open()
    assert not focus.calls["model"]
    at = _review(at)
    assert not at.exception and len(focus.calls["model"]) == 1
    saved = _saved_reply(focus)
    metadata = saved["metadata"]
    assert metadata["provider"] == "openai" and metadata["model"] == "ui-chart-test"
    assert metadata["interpretation"]["mode"] == "model"
    assert metadata["interpretation"]["validated"] is True
    chart = metadata["chart_context"]
    assert chart["symbol"] == "VIC" and chart["resolution"] == "5"
    assert len(chart["candles"]) == 40
    assert all(row["complete"] and row["volume"] != 999_999 for row in chart["candles"])
    assert chart["facts"] and chart["scenarios"]
    fact_ids = {fact["id"] for fact in chart["facts"]}
    assert set(metadata["interpretation"]["focus_fact_ids"]) <= fact_ids
    assert focus.store.usage() == 1
    frozen = json.dumps(chart, sort_keys=True)
    focus.quotes[:] = [replace(item, last=item.last + 1000) for item in focus.quotes]
    at.run()
    assert not at.exception and len(focus.calls["model"]) == 1
    assert focus.store.usage() == 1
    assert json.dumps(_saved_reply(focus)["metadata"]["chart_context"], sort_keys=True) == frozen


def test_demo_review_is_explicit_about_rules_and_never_claims_a_loaded_model(focus):
    at = focus.open()
    assert any("Đang dùng bộ quy tắc" in item.value for item in at.caption)
    at = _review(at)
    assert not at.exception
    saved = _saved_reply(focus)["metadata"]
    assert saved["provider"] == "market-copilot" and saved["model"] == "rule-explanation"
    assert saved["interpretation"] == {"mode": "rules", "validated": True}
    assert saved["chart_context"]["candles"] and saved["chart_context"]["facts"]
    assert not focus.calls["model"] and focus.store.usage() == 1


def test_changing_primary_symbol_keeps_reviews_and_chat_history_separate(focus):
    at = _review(focus.open())
    assert not at.exception and len(at.chat_message) == 2
    assert any("Nhận định đã lưu" in item.value for item in at.caption)
    at.selectbox(key="analysis_symbol").set_value("FPT").run()
    assert not at.exception and not at.chat_message
    assert not any("Nhận định đã lưu" in item.value for item in at.caption)
    assert at.text_input(key="market_chat_question").label == "Hỏi về FPT"
    at.selectbox(key="analysis_symbol").set_value("VIC").run()
    assert not at.exception and len(at.chat_message) == 2
    assert any("Nhận định đã lưu" in item.value for item in at.caption)
    assert len(focus.store.conversations()) == 1 and focus.store.usage() == 1


def test_secondary_board_and_shared_history_remain_accessible(focus):
    at = _review(focus.open())
    conversation_id = focus.store.conversations()[0]["id"]
    at.radio(key="market_view").set_value("Bảng điện Việt Nam").run()
    assert not at.exception
    assert any('class="priceboard-table"' in item.value for item in at.markdown)
    assert any('class="market-index-card"' in item.value for item in at.markdown)
    at.sidebar.radio[0].set_value("Trợ lý AI").run()
    assert not at.exception
    at.button(key=f"conversation_{conversation_id}").click().run()
    assert not at.exception and len(at.chat_message) == 2
    assert focus.store.usage() == 1


def test_primary_source_failure_review_stays_wait_with_auditable_blockers(focus):
    focus.mode = "source_error"
    at = _review(focus.open())
    assert not at.exception
    metadata = _saved_reply(focus)["metadata"]
    assert metadata["screening"][0]["action"] == "wait"
    assert metadata["screening"][0]["blockers"]
    assert metadata["chart_context"]["candles"] == []
    assert any(fact["role"] == "blocker" for fact in metadata["chart_context"]["facts"])
    assert metadata["interpretation"]["mode"] == "rules"
