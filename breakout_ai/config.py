"""Explicit, validated configuration. Secrets never belong in the UI."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def default_database_path(root: Path = ROOT) -> Path:
    """Keep the existing local database when upgrading the product name."""
    legacy = root / "data" / "stocklab.sqlite3"
    return legacy if legacy.exists() else root / "data" / "breakout_ai.sqlite3"



def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} phải là số nguyên.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} phải nằm trong [{minimum}, {maximum}].")
    return value


def _base_url(name: str, default: str) -> str:
    value = os.getenv(name, default).rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{name} phải là URL HTTP/HTTPS hợp lệ.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"{name} không được chứa mật khẩu, query hoặc fragment.")
    return value


@dataclass(frozen=True)
class Settings:
    provider: str = "demo"
    model: str = ""
    api_key: str = field(default="", repr=False)
    openai_base_url: str = "https://api.openai.com/v1"
    ollama_base_url: str = "http://localhost:11434"
    database_path: Path = field(default_factory=default_database_path)
    workspace_id: str = "local"
    timeout: int = 45
    max_output_tokens: int = 900
    max_input_chars: int = 2000
    max_history_messages: int = 8
    chat_limit: int = 40
    market_enabled: bool = True
    vn_market_provider: str = "kbs"
    us_market_provider: str = "yahoo"
    market_timeout: int = 15
    market_cache_seconds: int = 300
    market_max_symbols: int = 6
    market_gateway_url: str = ""
    market_gateway_token: str = field(default="", repr=False)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT / ".env", override=False)
        provider = os.getenv("LLM_PROVIDER", "demo").strip().lower()
        if provider not in {"demo", "openai", "ollama"}:
            raise ValueError("LLM_PROVIDER chỉ nhận demo, openai hoặc ollama.")
        path = Path(os.getenv("DATABASE_PATH") or default_database_path())
        workspace = os.getenv("WORKSPACE_ID", "local").strip()
        if not workspace or len(workspace) > 80:
            raise ValueError("WORKSPACE_ID cần có 1–80 ký tự.")
        vn_provider = os.getenv("VN_MARKET_PROVIDER", "kbs").strip().lower()
        us_provider = os.getenv("US_MARKET_PROVIDER", "yahoo").strip().lower()
        if vn_provider not in {"kbs", "gateway"} or us_provider not in {"yahoo", "gateway"}:
            raise ValueError("VN_MARKET_PROVIDER nhận kbs/gateway; US_MARKET_PROVIDER nhận yahoo/gateway.")
        market_flag = os.getenv("MARKET_DATA_ENABLED", "true").strip().lower()
        if market_flag not in {"true", "false"}:
            raise ValueError("MARKET_DATA_ENABLED nhận true hoặc false.")
        gateway_url = os.getenv("MARKET_GATEWAY_URL", "").strip()
        if gateway_url:
            gateway_url = _base_url("MARKET_GATEWAY_URL", "")
        return cls(
            provider=provider,
            model=os.getenv("LLM_MODEL", "").strip(),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=_base_url("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            ollama_base_url=_base_url("OLLAMA_BASE_URL", "http://localhost:11434"),
            database_path=path if path.is_absolute() else ROOT / path,
            workspace_id=workspace,
            timeout=_integer("LLM_TIMEOUT_SECONDS", 45, 5, 180),
            max_output_tokens=_integer("MAX_OUTPUT_TOKENS", 900, 128, 4096),
            max_input_chars=_integer("MAX_INPUT_CHARS", 2000, 100, 10000),
            max_history_messages=_integer("MAX_HISTORY_MESSAGES", 8, 2, 30),
            chat_limit=_integer("CHAT_LIMIT_24H", 40, 1, 10000),
            market_enabled=market_flag == "true",
            vn_market_provider=vn_provider,
            us_market_provider=us_provider,
            market_timeout=_integer("MARKET_TIMEOUT_SECONDS", 15, 3, 60),
            market_cache_seconds=_integer("MARKET_CACHE_SECONDS", 300, 0, 3600),
            market_max_symbols=_integer("MARKET_MAX_SYMBOLS", 6, 1, 10),
            market_gateway_url=gateway_url,
            market_gateway_token=os.getenv("MARKET_GATEWAY_TOKEN", ""),
        )
