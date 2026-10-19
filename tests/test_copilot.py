"""Market chat must explain the selected captured analysis, never invent a feed."""
from copy import deepcopy
from dataclasses import replace
import json

import httpx
import pytest

from breakout_ai.books import BookLibrary
from breakout_ai.copilot import MarketCopilot
from breakout_ai.providers import ProviderError
from breakout_ai.storage import QuotaExceeded
from breakout_ai.tutor import chat_turn


@pytest.fixture
def context():
    return {
        "symbols": ["VIC", "FPT", "AAPL"],
        "analysis": {
            "symbol": "VIC", "action": "wait", "title": "Chờ xác nhận",
            "summary": "Chưa đủ dữ liệu mới để cân nhắc điểm mua.",
            "blockers": ["Giá khớp đã cũ, chờ phiên giao dịch mới."],
            "evidence": ["RSI 28 mô tả động lượng yếu, chưa xác nhận tạo đáy."],
            "levels": {"support": 100_000, "resistance": 120_000, "invalidation": 98_000},
            "indicators": {"book_imbalance": 0.25},
            "timeframe": "5 phút", "as_of": "2026-10-19T03:00:00+00:00",
            "owned": False,
        },
        "quote": {
            "symbol": "VIC", "last": 105_000, "stale": True, "currency": "VND",
            "source_timestamp": "2026-10-19T02:59:00+00:00",
            "source": "DNSE public snapshot",
        },
    }


def no_external_call(*args, **kwargs):
    raise AssertionError("The demo copilot must not fetch another feed or call an LLM.")


def test_demo_preserves_wait_and_blockers_without_external_calls(settings, context, monkeypatch):
    monkeypatch.setattr("breakout_ai.copilot.complete", no_external_call)
    monkeypatch.setattr(httpx, "Client", no_external_call)
    original = deepcopy(context)
    reply = MarketCopilot(settings, context).answer("VIC hôm nay nên mua không?", [])
    assert reply.model == "rule-explanation"
    assert context["analysis"]["summary"] in reply.text
    assert context["analysis"]["blockers"][0] in reply.text
    assert reply.screening == [context["analysis"]]
    assert reply.data_errors == context["analysis"]["blockers"]
    assert reply.market_data == [context["quote"]]
    assert context == original


def test_support_and_book_pressure_are_explained_as_conditions(settings, context):
    reply = MarketCopilot(settings, context).answer("VIC chạm đáy RSI và dư mua có nghĩa gì?", [])
    assert "chưa chứng minh đã tạo đáy" in reply.text
    assert "hỗ trợ vẫn có thể bị xuyên thủng" in reply.text
    assert "+25.0%" in reply.text
    assert "không phải giao dịch đã khớp hoặc xác suất giá tăng" in reply.text
    assert "100,000" in reply.text and "120,000" in reply.text
    assert context["analysis"]["as_of"] in reply.text
    assert context["quote"]["source_timestamp"] in reply.text


def test_missing_depth_is_not_interpreted_as_buy_pressure(settings, context):
    context["analysis"]["indicators"]["book_imbalance"] = None
    reply = MarketCopilot(settings, context).answer("Dư mua VIC có mạnh không?", [])
    assert "chưa có sổ giá đủ mới" in reply.text
    assert "+25.0%" not in reply.text


@pytest.mark.parametrize("question", [
    "FPT nên mua không?", "fpt nên mua không?", "VIC và aapl thì sao?",
    "TSLA hiện tại thế nào?",
])
def test_another_ticker_is_blocked_before_provider_or_book_lookup(settings, context, question, monkeypatch):
    monkeypatch.setattr("breakout_ai.copilot.complete", no_external_call)
    class UnusedBooks:
        search = staticmethod(no_external_call)
    reply = MarketCopilot(replace(settings, provider="openai"), context, UnusedBooks()).answer(question, [])
    assert reply.model == "symbol-check"
    assert "**VIC**" in reply.text
    assert reply.sources == [] and reply.market_data == []


@pytest.mark.parametrize("question", [
    "vic có nên mua không?",
    "RSI14 của VIC có báo đáy không?",
    "MA20 của VIC đang nói gì?",
    "SMA20 và EMA20 của VIC khác gì?",
])
def test_selected_ticker_and_common_indicator_names_are_not_other_tickers(settings, context, question):
    reply = MarketCopilot(settings, context).answer(question, [])
    assert reply.model == "rule-explanation"
    assert reply.screening[0]["symbol"] == "VIC"


@pytest.mark.parametrize("question", ["", "   ", "x" * 2001])
def test_invalid_questions_fail_before_any_provider_call(settings, context, question, monkeypatch):
    monkeypatch.setattr("breakout_ai.copilot.complete", no_external_call)
    with pytest.raises(ValueError, match="Câu hỏi"):
        MarketCopilot(settings, context).answer(question, [])


def test_demo_book_citations_correspond_to_real_retrieved_passages(settings, store, context):
    books = BookLibrary(store)
    document, _ = books.ingest(
        "technical.md",
        b"Relative strength index RSI measures momentum. Support and resistance are observation zones. Trading volume may confirm a moving average breakout.",
        "Technical notes", "Test author",
    )
    books.ingest("unrelated.txt", b"Chocolate pancakes require flour cocoa butter milk.", "Cooking notes")
    reply = MarketCopilot(settings, context, books).answer("RSI và hỗ trợ VIC có nghĩa gì?", [])
    retrieved = {p.id: p for p in books.passages(document)}
    assert reply.sources
    assert all(source["id"] in retrieved for source in reply.sources)
    for source in reply.sources:
        passage = retrieved[source["id"]]
        assert f"[{passage.id}]" in reply.text
        assert passage.text[:420] in reply.text
        assert source["document_id"] == document
    assert "Cooking notes" not in reply.text
    assert "chưa tự biến toàn bộ sách thành chiến lược" in reply.text


def test_absent_books_do_not_create_citations_or_claim_book_training(settings, context):
    reply = MarketCopilot(settings, context).answer("Giải thích VIC", [])
    assert reply.sources == []
    assert "Đoạn sách để đối chiếu" not in reply.text
    assert "[B" not in reply.text


def test_provider_receives_captured_data_real_book_passages_and_bounded_history(settings, store, context):
    books = BookLibrary(store)
    books.ingest("support.md", b"Support resistance and moving average can describe price trends.", "Source notes")
    captured = []
    def respond(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "Cần chờ dữ liệu mới."}]}],
            "usage": {"input_tokens": 123, "output_tokens": 17},
        })
    configured = replace(settings, provider="openai", model="test-model", api_key="test-only-key", max_history_messages=4)
    history = [
        {"role": "user", "content": "Earlier turn must be dropped"},
        {"role": "assistant", "content": "a" * 2200},
        {"role": "user", "content": "b" * 2200},
        {"role": "tool", "content": "Untrusted tool turn"},
        {"role": "assistant", "content": "Most recent explanation"},
    ]
    reply = MarketCopilot(configured, context, books, httpx.MockTransport(respond)).answer("VIC chạm hỗ trợ chưa?", history)
    assert len(captured) == 1
    request = captured[0]
    assert request["store"] is False
    assert request["model"] == "test-model"
    assert [m["role"] for m in request["input"]] == ["assistant", "user", "assistant", "user"]
    assert len(request["input"][0]["content"]) == 1800
    assert len(request["input"][1]["content"]) == 1800
    assert request["input"][-1]["content"] == "VIC chạm hỗ trợ chưa?"
    assert "Earlier turn" not in str(request["input"]) and "Untrusted tool turn" not in str(request["input"])
    sent_context = json.loads(request["instructions"].split("CONTEXT_JSON:\n", 1)[1])
    assert sent_context["quote"] == context["quote"]
    assert sent_context["analysis"] == context["analysis"]
    assert sent_context["books"]
    assert {p["id"] for p in sent_context["books"]} == {s["id"] for s in reply.sources}
    assert "không nâng wait/hold" in request["instructions"]
    assert "chỉ nói bán vị thế khi owned=true" in request["instructions"]
    assert context["analysis"]["summary"] in reply.text
    assert reply.text.endswith("Cần chờ dữ liệu mới.")
    assert reply.input_tokens == 123 and reply.output_tokens == 17
    assert len(history[1]["content"]) == 2200


def test_copilot_chat_turn_respects_quota_and_keeps_a_complete_turn(settings, store, context):
    limited = replace(settings, chat_limit=1)
    copilot = MarketCopilot(limited, context)
    conversation = chat_turn(store, copilot, "VIC nên mua không?", None, "VN", "Giải thích dễ hiểu")
    assert len(store.messages(conversation)) == 2
    assert store.usage() == 1
    with pytest.raises(QuotaExceeded):
        chat_turn(store, copilot, "Giải thích thêm VIC", conversation, "VN", "Giải thích dễ hiểu")
    assert len(store.messages(conversation)) == 2 and store.usage() == 1


def test_provider_failure_does_not_store_a_half_chat_or_charge_usage(settings, store, context):
    configured = replace(settings, provider="openai", model="test-model", api_key="test-only-key")
    transport = httpx.MockTransport(lambda request: httpx.Response(429, text="secret upstream debug"))
    with pytest.raises(ProviderError, match="hạn mức"):
        chat_turn(store, MarketCopilot(configured, context, transport=transport),
                  "VIC đang có gì?", None, "VN", "Giải thích dễ hiểu")
    assert store.conversations() == [] and store.usage() == 0
