import json

import httpx
import pytest

from breakout_ai.config import Settings
from breakout_ai.providers import ProviderError, complete


def test_openai_responses_request_and_output_contract():
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path == "/v1/responses"
        assert payload["store"] is False and payload["max_output_tokens"] == 900
        assert payload["instructions"] == "Tutor instructions"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "Answer [K02]"}]}], "usage": {"input_tokens": 80, "output_tokens": 10}})
    result = complete(Settings(provider="openai", model="test-model", api_key="test-key"), "Tutor instructions", [{"role": "user", "content": "P/E?"}], httpx.MockTransport(handler))
    assert result.text == "Answer [K02]" and result.output_tokens == 10


def test_ollama_request_contract():
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert payload["stream"] is False
        assert payload["messages"][0]["role"] == "system"
        return httpx.Response(200, json={"done": True, "message": {"content": "Local answer"}, "prompt_eval_count": 10, "eval_count": 4})
    result = complete(Settings(provider="ollama", model="local-test"), "Instructions", [], httpx.MockTransport(handler))
    assert result.input_tokens == 10


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_provider_errors_never_echo_response_body_or_api_key(status):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, text="SECRET-BODY test-key"))
    with pytest.raises(ProviderError) as error:
        complete(Settings(provider="openai", model="test", api_key="test-key"), "", [], transport)
    assert "SECRET" not in str(error.value) and "test-key" not in str(error.value)


@pytest.mark.parametrize("payload", [[], {"done": True, "message": {}}, {"done": True, "message": {"content": ""}}])
def test_malformed_or_empty_provider_output_fails_cleanly(payload):
    with pytest.raises(ProviderError):
        complete(Settings(provider="ollama", model="test"), "", [], httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))


def test_missing_config_fails_before_network():
    with pytest.raises(ProviderError, match="LLM_MODEL"):
        complete(Settings(provider="openai"), "", [])
