from dataclasses import replace
from datetime import datetime, timezone

from breakout_ai.config import Settings
from breakout_ai.market import Bar, MarketError, MarketSnapshot
from breakout_ai.market_view import load_quotes


def snapshot(market="VN", symbol="FPT", stale=False):
    return MarketSnapshot(market, symbol, "VND" if market == "VN" else "USD",
                          "test", "https://example.org/prices", datetime.now(timezone.utc).isoformat(),
                          [Bar("2026-10-15", 100, 1000), Bar("2026-10-16", 101, 1000)], cache_stale=stale)


class Source:
    def __init__(self, settings=None):
        self.settings = settings or Settings()
        self.saved = {}
        self.calls = []
        self.fail = False

    def cached(self, market, symbol):
        return self.saved.get((market, symbol))

    def many(self, pairs, force=False):
        self.calls.append((pairs, force))
        if self.fail:
            raise MarketError("Nguồn thử không phản hồi.")
        results = [snapshot(*pair) for pair in pairs]
        self.saved.update({(item.market, item.symbol): item for item in results})
        return results, []


def test_initial_batch_deduplicates_and_reuses_fresh_cache():
    source, state = Source(), {}
    first = load_quotes(source, [("VN", "fpt"), ("VN", "FPT"), ("US", "AAPL")], state, now=100)
    second = load_quotes(source, [("VN", "FPT"), ("US", "AAPL")], state, now=101)
    assert len(first.snapshots) == 2 and not first.errors
    assert first.attempted and not second.attempted
    assert source.calls == [([("VN", "FPT"), ("US", "AAPL")], False)]


def test_failed_source_has_cooldown_but_manual_refresh_retries():
    source, state = Source(), {}
    source.fail = True
    first = load_quotes(source, [("VN", "FPT")], state, now=100)
    second = load_quotes(source, [("VN", "FPT")], state, now=105)
    manual = load_quotes(source, [("VN", "FPT")], state, force=True, now=106)
    assert first.errors and second.errors and manual.errors
    assert not second.attempted and manual.attempted and len(source.calls) == 2
    load_quotes(source, [("VN", "FPT")], state, now=406)
    assert len(source.calls) == 3


def test_failed_refresh_keeps_stale_price_visible():
    source, state = Source(), {}
    source.saved[("VN", "FPT")] = snapshot(stale=True)
    source.many = lambda pairs, force=False: ([snapshot(stale=True)], [])
    result = load_quotes(source, [("VN", "FPT")], state, force=True, now=100)
    assert result.snapshots[("VN", "FPT")].cache_stale
    assert any("bản lưu cũ" in error for error in result.errors)


def test_scope_and_settings_limit_are_respected():
    state = {}
    first = Source(replace(Settings(), market_max_symbols=1))
    result = load_quotes(first, [("VN", "FPT"), ("US", "AAPL")], state, now=100)
    assert list(result.snapshots) == [("VN", "FPT")]
    second = Source(replace(first.settings, workspace_id="different"))
    load_quotes(second, [("VN", "FPT")], state, now=101)
    assert len(second.calls) == 1
    disabled = Source(replace(Settings(), market_enabled=False))
    load_quotes(disabled, [("VN", "FPT")], state, force=True, now=101)
    assert not disabled.calls
