from dataclasses import replace

import pytest

from breakout_ai.providers import ProviderError
from breakout_ai.tutor import Tutor, chat_turn, requires_live_data


def test_demo_answer_has_a_real_retrieved_reference(settings):
    reply = Tutor(settings).answer("P/E là gì?", [])
    assert reply.provider == "demo" and "[K02]" in reply.text
    assert reply.sources[0]["id"] == "K02"


def test_followup_uses_previous_user_topic(settings):
    reply = Tutor(settings).answer("Cho ví dụ khác", [{"role": "user", "content": "P/E là gì"}])
    assert reply.sources[0]["id"] == "K02"


@pytest.mark.parametrize("question", ["Giá FPT hôm nay?", "AAPL current price?", "Tin tức mới nhất về chứng khoán", "Giá AAPL bao nhiêu?", "TSLA price?", "P/E FPT là bao nhiêu?"])
def test_time_sensitive_queries_do_not_invent_quotes(settings, question):
    assert requires_live_data(question)
    reply = Tutor(settings).answer(question, [])
    assert "chưa kết nối" in reply.text and reply.sources == []


def test_unrelated_query_does_not_call_a_provider(settings):
    reply = Tutor(replace(settings, provider="openai")).answer("Recipe chocolate pancakes", [])
    assert reply.model == "scope-check"


@pytest.mark.parametrize("question", ["Current ratio là gì?", "P/E và EPS là gì?", "Giá trị sổ sách là gì?"])
def test_educational_definitions_are_not_quote_requests(question):
    assert not requires_live_data(question)


def test_unknown_conversation_is_rejected_before_provider(settings, store):
    tutor = Tutor(replace(settings, provider="openai", model="test"))
    with pytest.raises(ValueError, match="cuộc trò chuyện"):
        chat_turn(store, tutor, "P/E?", "non-existent", "US", "Giải thích dễ hiểu")


def test_failed_llm_call_does_not_save_a_half_turn(settings, store):
    tutor = Tutor(replace(settings, provider="openai", model="test"))
    with pytest.raises(ProviderError):
        chat_turn(store, tutor, "P/E là gì?", None, "BOTH", "Giải thích dễ hiểu")
    assert store.conversations() == [] and store.usage() == 0


def test_empty_and_oversized_messages_are_rejected(settings):
    tutor = Tutor(settings)
    for question in [" ", "x" * (settings.max_input_chars + 1)]:
        with pytest.raises(ValueError):
            tutor.answer(question, [])
