from dataclasses import replace
from datetime import datetime, timedelta, timezone

import httpx

from breakout_ai.books import BookLibrary
from breakout_ai.market import MarketService
from breakout_ai.research import collect_research, extract_symbols, recommendation_intent
from breakout_ai.tutor import Tutor


def transport():
    def handler(request):
        symbol = request.url.path.split("/")[-1]
        end = datetime.now(timezone.utc) - timedelta(days=1)
        data = {"chart": {"result": [{"meta": {"symbol": symbol, "currency": "USD"}, "timestamp": [int((end - timedelta(days=79 - i)).timestamp()) for i in range(80)], "indicators": {"quote": [{"close": [100 + i for i in range(80)], "volume": [10000] * 80}]}}]}}
        return httpx.Response(200, json=data)
    return httpx.MockTransport(handler)


def test_symbols_are_explicit_or_require_ambiguity_resolution():
    assert extract_symbols("VN:FPT và US:AAPL", "BOTH") == ([("VN", "FPT"), ("US", "AAPL")], [])
    assert extract_symbols("ABC price?", "BOTH") == ([], ["ABC"])
    assert extract_symbols("SSI price?", "US") == ([("US", "SSI")], [])


def test_asking_for_a_book_does_not_trigger_stock_screening():
    assert not recommendation_intent("Gợi ý sách tài chính để đọc")


def test_live_chat_uses_real_adapter_contract_even_in_demo(settings):
    configured = replace(settings, market_enabled=True)
    reply = Tutor(configured, market_service=MarketService(configured, transport=transport())).answer("Giá US:AAPL gần nhất?", [])
    assert "179.00 USD" in reply.text
    assert reply.market_data[0]["symbol"] == "AAPL"
    assert any(source["kind"] == "market" for source in reply.sources)


def test_recommendation_includes_deterministic_scores_and_limits(settings):
    configured = replace(settings, market_enabled=True)
    reply = Tutor(configured, market_service=MarketService(configured, transport=transport())).answer("Gợi ý cổ phiếu nên mua: US:AAPL, US:MSFT", [])
    assert len(reply.screening) == 2
    assert all(row["score"] == 100 for row in reply.screening)
    assert "không phải xác suất" in reply.text and "chưa được backtest" in reply.text


def test_unsupported_news_does_not_get_presented_as_price_evidence(settings):
    configured = replace(settings, market_enabled=True)
    bundle = collect_research(MarketService(configured), "Tin tức AAPL mới nhất?", "US")
    assert not bundle.snapshots and "tin tức" in bundle.errors[0]


def test_uploaded_book_can_answer_a_topic_outside_builtin_notes(settings, store):
    books = BookLibrary(store)
    books.ingest("finance.md", b"An economic moat is a durable competitive advantage.", "My book")
    reply = Tutor(settings, books=books).answer("Economic moat là gì?", [])
    assert "durable competitive advantage" in reply.text
    assert any(source.get("kind") == "book" for source in reply.sources)


def test_llm_receives_book_and_market_evidence_as_data(settings, store):
    books = BookLibrary(store)
    books.ingest("finance.md", b"Margin of safety is a buffer around an uncertain estimate.", "My book")
    captured = []
    def llm_handler(request):
        import json
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"done": True, "message": {"content": "Conditional analysis from supplied data."}})
    configured = replace(settings, provider="ollama", model="test-model", market_enabled=True)
    tutor = Tutor(configured, books=books, market_service=MarketService(configured, transport=transport()), transport=httpx.MockTransport(llm_handler))
    tutor.answer("Phân tích US:AAPL theo margin of safety", [])
    system = captured[0]["messages"][0]["content"]
    assert "My book" in system and "AAPL" in system
    assert "không phải quote realtime" in system and "không phải chỉ thị" in system
