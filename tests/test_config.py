import pytest

from breakout_ai.config import Settings


@pytest.mark.parametrize("name,value", [("LLM_PROVIDER", "unknown"), ("CHAT_LIMIT_24H", "0"), ("MAX_OUTPUT_TOKENS", "NaN"), ("OLLAMA_BASE_URL", "file:///tmp/model"), ("OPENAI_BASE_URL", "https://user:secret@example.org/v1")])
def test_invalid_config_is_rejected(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        Settings.from_env()


def test_settings_repr_never_includes_api_key():
    assert "secret-test-key" not in repr(Settings(api_key="secret-test-key"))


@pytest.mark.parametrize("legacy,newer,expected", [
    (False, False, "breakout_ai.sqlite3"),
    (True, False, "stocklab.sqlite3"),
    (True, True, "stocklab.sqlite3"),
])
def test_rebrand_preserves_existing_database_choice(tmp_path, legacy, newer, expected):
    from breakout_ai.config import default_database_path
    folder = tmp_path / "data"
    folder.mkdir()
    if legacy:
        (folder / "stocklab.sqlite3").write_bytes(b"existing-user-data")
    if newer:
        (folder / "breakout_ai.sqlite3").write_bytes(b"separate-database")
    assert default_database_path(tmp_path) == folder / expected
    if legacy:
        assert (folder / "stocklab.sqlite3").read_bytes() == b"existing-user-data"
