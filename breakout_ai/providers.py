"""Provider adapters with bounded output and sanitized errors."""

from dataclasses import dataclass
import httpx

from breakout_ai.config import Settings


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


def complete(settings: Settings, instructions: str, messages: list[dict], transport=None) -> Completion:
    if not settings.model:
        raise ProviderError("Hãy đặt LLM_MODEL trong .env theo mô hình bạn có quyền sử dụng.")
    if settings.provider == "openai" and not settings.api_key:
        raise ProviderError("Thiếu OPENAI_API_KEY. Thêm key vào .env hoặc chuyển LLM_PROVIDER=demo.")
    try:
        with httpx.Client(timeout=settings.timeout, transport=transport, follow_redirects=False) as client:
            if settings.provider == "openai":
                response = client.post(settings.openai_base_url + "/responses", headers={"Authorization": f"Bearer {settings.api_key}"}, json={
                    "model": settings.model, "instructions": instructions, "input": messages,
                    "max_output_tokens": settings.max_output_tokens, "store": False,
                })
            elif settings.provider == "ollama":
                response = client.post(settings.ollama_base_url + "/api/chat", json={
                    "model": settings.model, "messages": [{"role": "system", "content": instructions}, *messages],
                    "stream": False, "options": {"num_predict": settings.max_output_tokens},
                })
            else:
                raise ProviderError("Nhà cung cấp không hỗ trợ yêu cầu này.")
            response.raise_for_status()
            data = response.json()
        if settings.provider == "openai":
            if data.get("status") != "completed":
                raise ProviderError("Mô hình chưa hoàn thành câu trả lời. Thử câu hỏi ngắn hơn hoặc tăng giới hạn đầu ra.")
            text = "\n".join(part["text"] for item in data.get("output", []) if item.get("type") == "message" for part in item.get("content", []) if part.get("type") == "output_text")
            usage = data.get("usage") or {}
            result = Completion(text.strip(), usage.get("input_tokens"), usage.get("output_tokens"))
        else:
            if data.get("done") is not True:
                raise ProviderError("Mô hình cục bộ chưa hoàn thành câu trả lời.")
            result = Completion(data["message"]["content"].strip(), data.get("prompt_eval_count"), data.get("eval_count"))
        if not result.text:
            raise ProviderError("Mô hình không trả về nội dung văn bản.")
        return result
    except httpx.TimeoutException as exc:
        raise ProviderError("Kết nối mô hình quá thời gian chờ. Kiểm tra dịch vụ và thử lại.") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        hints = {401: "API key không hợp lệ.", 403: "Tài khoản chưa có quyền truy cập mô hình.", 404: "Không tìm thấy mô hình hoặc endpoint.", 429: "Dịch vụ đã đạt hạn mức. Kiểm tra quota của nhà cung cấp."}
        raise ProviderError(hints.get(status, f"Dịch vụ mô hình gặp lỗi HTTP {status}.")) from exc
    except httpx.HTTPError as exc:
        raise ProviderError("Không kết nối được dịch vụ mô hình. Kiểm tra địa chỉ và kết nối mạng.") from exc
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ProviderError("Dịch vụ mô hình trả về dữ liệu không đúng định dạng.") from exc
