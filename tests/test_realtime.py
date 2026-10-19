from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
from threading import Event

import httpx
import pytest

from breakout_ai.realtime import (
    MAX_RESPONSE_BYTES, SOURCE_URL, RealtimeError, RealtimeService,
)
from breakout_ai.storage import Store


NOW = datetime(2026, 10, 19, 3, 30, tzinfo=timezone.utc)


def source(symbol="FPT", market_id=6):
    return {
        "data": {
            "GetKrxStockInfoBySymbols": {"si": [{
                "symbol": symbol, "marketId": market_id, "securityGroupId": 7,
                "referencePrice": 58.2, "highLimitPrice": 62.2, "lowLimitPrice": 54.2,
                "matchPrice": 57.8, "matchQuantity": 30, "totalVolumeTraded": 143800,
                "grossTradeAmount": 83.42787, "openPrice": 58.6,
                "highestPrice": 58.6, "lowestPrice": 57.6, "averagePrice": 58.017,
                "buyForeignQuantity": 10266, "sellForeignQuantity": 64190,
                "tradingTime": "2026-10-19T03:29:55Z", "tradingSessionId": 7,
            }]},
            "GetTopPriceOfSymbols": {"data": {"tp": [{
                "symbol": symbol, "bidPrice1": 57.7, "bidQtty1": 2170,
                "bidPrice2": 57.6, "bidQtty2": 10660, "bidPrice3": 57.5, "bidQtty3": 19990,
                "offerPrice1": 57.8, "offerQtty1": 2700,
                "offerPrice2": 57.9, "offerQtty2": 390, "offerPrice3": 58, "offerQtty3": 4690,
                "time": "2026-10-19T03:29:58Z",
            }]}},
        }
    }


def service(data=None, store=None, clock=None):
    payload = data if data is not None else source()
    return RealtimeService(store, clock=clock or (lambda: NOW),
                           transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))


def info(payload):
    return payload["data"]["GetKrxStockInfoBySymbols"]["si"][0]


def depth(payload):
    return payload["data"]["GetTopPriceOfSymbols"]["data"]["tp"][0]


def test_batched_public_request_has_no_secret_and_normalizes_units():
    calls = []
    def handler(request):
        calls.append(request)
        assert str(request.url) == SOURCE_URL
        assert request.method == "POST"
        assert request.headers["User-Agent"].startswith("BreakoutAI/0.7 ")
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        query = json.loads(request.content)["query"]
        assert '"FPT"' in query and "board:2" in query
        assert "GetKrxStockInfoBySymbols" in query and "GetTopPriceOfSymbols" in query
        return httpx.Response(200, json=source())
    reader = RealtimeService(clock=lambda: NOW, transport=httpx.MockTransport(handler))
    assert calls == []
    snapshot = reader.fetch([" fpt ", "FPT"])
    assert len(calls) == 1
    assert snapshot.mode == "polling" and snapshot.errors == [] and not snapshot.stale
    quote = snapshot.quotes[0]
    assert (quote.symbol, quote.exchange, quote.currency, quote.market) == ("FPT", "HOSE", "VND", "VN")
    assert quote.reference == 58200 and quote.last == 57800
    assert quote.ceiling == 62200 and quote.floor == 54200
    assert quote.change == -400 and quote.change_pct == pytest.approx(-400 / 58200 * 100)
    assert quote.match_volume == 300 and quote.total_volume == 1438000
    assert quote.total_value == pytest.approx(83427870000)
    assert quote.average == 58017 and quote.foreign_buy_volume == 102660
    assert quote.foreign_sell_volume == 641900
    assert quote.bids[0].price == 57700 and quote.bids[0].volume == 21700
    assert quote.asks[2].price == 58000 and quote.asks[2].volume == 46900
    assert quote.source_timestamp == "2026-10-19T03:29:55+00:00"
    assert quote.depth_timestamp == "2026-10-19T03:29:58+00:00"
    assert quote.received_at == NOW.isoformat() and not quote.depth_stale


@pytest.mark.parametrize("market_id,exchange", [(6, "HOSE"), (7, "HNX"), (8, "UPCOM")])
def test_exchange_comes_from_provider_not_symbol_heuristic(market_id, exchange):
    result = service(source("ABC", market_id)).fetch(["ABC"])
    assert result.quotes[0].exchange == exchange


@pytest.mark.parametrize("symbols", ["FPT", ["FPT/ABC"], ["AAPL;DROP"], [True], ["F"], ["A" + "1" * 10], [f"A{i}" for i in range(31)]])
def test_invalid_identity_never_calls_network(symbols):
    reader = RealtimeService(transport=httpx.MockTransport(lambda _: pytest.fail("network")))
    with pytest.raises(RealtimeError):
        reader.fetch(symbols)


def test_empty_list_has_no_network():
    result = RealtimeService(transport=httpx.MockTransport(lambda _: pytest.fail("network"))).fetch([])
    assert result.quotes == [] and result.errors == [] and result.fetched_at is None


def test_missing_fields_never_fabricate_market_data():
    data = source()
    for name in ["matchPrice", "grossTradeAmount", "buyForeignQuantity", "openPrice", "tradingTime"]:
        info(data).pop(name)
    data["data"].pop("GetTopPriceOfSymbols")
    snapshot = service(data).fetch(["FPT"])
    quote = snapshot.quotes[0]
    assert quote.last is None and quote.change is None and quote.change_pct is None
    assert quote.total_value is None and quote.open is None and quote.foreign_buy_volume is None
    assert quote.source_timestamp is None and quote.stale and quote.depth_stale
    assert all(level.price is None and level.volume is None for level in quote.bids + quote.asks)
    assert snapshot.errors


def test_zero_match_price_is_not_zero_value_stock():
    data = source()
    info(data)["matchPrice"] = 0
    info(data)["matchQuantity"] = 0
    quote = service(data).fetch(["FPT"]).quotes[0]
    assert quote.last is None and quote.change is None and quote.match_volume == 0


@pytest.mark.parametrize("name,value", [("matchPrice", -1), ("totalVolumeTraded", True), ("grossTradeAmount", "NaN"), ("marketId", 3), ("highestPrice", 1), ("referencePrice", 900)])
def test_invalid_numbers_or_inconsistent_limits_are_rejected(name, value):
    data = source()
    info(data)[name] = value
    result = service(data).fetch(["FPT"])
    assert not result.quotes and result.stale and result.errors


def test_invalid_depth_keeps_valid_quote_with_empty_depth():
    data = source()
    depth(data)["bidQtty1"] = -5
    result = service(data).fetch(["FPT"])
    assert result.quotes[0].last == 57800
    assert all(level.price is None for level in result.quotes[0].bids)
    assert result.quotes[0].depth_stale and result.errors


def test_independent_trade_and_depth_timestamps():
    data = source()
    info(data)["tradingTime"] = (NOW - timedelta(minutes=20)).isoformat()
    quote = service(data).fetch(["FPT"]).quotes[0]
    assert quote.stale and not quote.depth_stale
    info(data)["tradingTime"] = NOW.isoformat()
    depth(data)["time"] = (NOW - timedelta(minutes=20)).isoformat()
    quote = service(data).fetch(["FPT"]).quotes[0]
    assert not quote.stale and quote.depth_stale


@pytest.mark.parametrize("timestamp", ["2026-10-19T03:29:58", "2030-01-01T00:00:00Z", 1234, "invalid"])
def test_invalid_or_future_source_time_is_not_current(timestamp):
    data = source()
    info(data)["tradingTime"] = timestamp
    snapshot = service(data).fetch(["FPT"])
    assert snapshot.quotes == [] and snapshot.errors


def test_poll_cache_is_reused_across_service_instances_and_respects_workspace(tmp_path):
    store = Store(tmp_path / "quotes.sqlite3", "one")
    service(store=store).fetch(["FPT"])
    def no_network(_):
        pytest.fail("fresh cache should prevent network")
    second = RealtimeService(store, clock=lambda: NOW + timedelta(seconds=4), transport=httpx.MockTransport(no_network))
    assert second.fetch(["FPT"]).from_cache
    other = Store(store.path, "two")
    assert RealtimeService(other, clock=lambda: NOW).cached(["FPT"]) is None


def test_expiry_and_force_refresh_network():
    calls, current = [], [NOW]
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=source())
    reader = RealtimeService(clock=lambda: current[0], transport=httpx.MockTransport(handler))
    reader.fetch(["FPT"])
    reader.fetch(["FPT"])
    assert len(calls) == 1
    reader.fetch(["FPT"], force=True)
    assert len(calls) == 2
    current[0] += timedelta(seconds=5)
    reader.fetch(["FPT"])
    assert len(calls) == 3


def test_failed_refresh_preserves_time_and_marks_quote_and_depth_stale(tmp_path):
    store = Store(tmp_path / "quotes.sqlite3")
    initial = service(store=store).fetch(["FPT"])
    reader = RealtimeService(store, clock=lambda: NOW, transport=httpx.MockTransport(lambda _: httpx.Response(429)))
    result = reader.fetch(["FPT"], force=True)
    assert result.from_cache and result.stale and result.errors
    assert result.quotes[0].stale and result.quotes[0].depth_stale
    assert result.fetched_at == initial.fetched_at
    assert result.quotes[0].source_timestamp == initial.quotes[0].source_timestamp
    reloaded = RealtimeService(store, clock=lambda: NOW).cached(["FPT"])
    assert reloaded.quotes[0].stale and reloaded.errors


def test_paused_cache_does_not_call_network_and_ages_source_time():
    current = [NOW]
    reader = service(clock=lambda: current[0])
    reader.fetch(["FPT"])
    current[0] += timedelta(minutes=5)
    quote = reader.cached(["FPT"]).quotes[0]
    assert quote.stale and quote.depth_stale
    assert quote.received_at == NOW.isoformat()


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_http_failure_has_no_redirect_or_daily_price_fallback(status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"Location": "https://example.com/private"})
    result = RealtimeService(transport=httpx.MockTransport(handler)).fetch(["FPT"])
    assert len(calls) == 1 and not result.quotes and result.stale and result.errors
    assert str(status) in result.errors[0]


@pytest.mark.parametrize("mutation", ["wrong", "duplicate", "top_wrong"])
def test_cross_symbol_or_duplicate_response_is_rejected(mutation):
    data = source()
    if mutation == "wrong":
        info(data)["symbol"] = "VCB"
    elif mutation == "duplicate":
        data["data"]["GetKrxStockInfoBySymbols"]["si"].append(deepcopy(info(data)))
    else:
        depth(data)["symbol"] = "VCB"
    result = service(data).fetch(["FPT"])
    assert result.quotes == [] and result.errors


def test_partial_result_keeps_requested_order_and_identifies_missing():
    data = source()
    result = service(data).fetch(["SSI", "FPT"])
    assert [quote.symbol for quote in result.quotes] == ["FPT"]
    assert "SSI" in " ".join(result.errors)


def test_partial_graphql_response_never_hides_error():
    data = source()
    data["errors"] = [{"message": "unavailable"}]
    result = service(data).fetch(["FPT"])
    assert result.quotes and result.errors


def test_oversized_or_invalid_json_response_is_bounded():
    for content in [b"x" * (MAX_RESPONSE_BYTES + 1), b"not json"]:
        result = RealtimeService(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=content))).fetch(["FPT"])
        assert not result.quotes and result.errors

@pytest.mark.parametrize("data", [None, [], {"data": []}, {"data": {"GetKrxStockInfoBySymbols": []}}, {"data": {"GetKrxStockInfoBySymbols": {"si": []}, "GetTopPriceOfSymbols": []}}, {"data": {"GetKrxStockInfoBySymbols": {"si": []}, "GetTopPriceOfSymbols": {"data": []}}}])
def test_malformed_graphql_shape_is_safe_error(data):
    reader = RealtimeService(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data)))
    result = reader.fetch(["FPT"])
    assert not result.quotes and result.errors and result.stale


@pytest.mark.parametrize("field,value", [("currency", "USD"), ("symbol", "VCB"), ("last", -2), ("last", "NaN"), ("source_url", "https://example.com")])
def test_corrupt_cache_identity_or_numbers_are_ignored(tmp_path, field, value):
    store = Store(tmp_path / "quotes.sqlite3")
    service(store=store).fetch(["FPT"])
    with store.connection() as db:
        payload = json.loads(db.execute("SELECT payload FROM board_snapshot_cache").fetchone()[0])
        payload["quotes"][0][field] = value
        db.execute("UPDATE board_snapshot_cache SET payload=?", (json.dumps(payload),))
    assert RealtimeService(store, clock=lambda: NOW).cached(["FPT"]) is None


def test_slow_receive_does_not_double_poll_cadence_across_instances(tmp_path):
    store = Store(tmp_path / "cadence.sqlite3")
    current, starts = [NOW], []
    def handler(_):
        starts.append(current[0])
        current[0] += timedelta(seconds=0.7)
        return httpx.Response(200, json=source())
    def reader():
        return RealtimeService(store, clock=lambda: current[0],
                               transport=httpx.MockTransport(handler))
    initial = reader().fetch(["FPT"])
    assert initial.fetched_at == (NOW + timedelta(seconds=0.7)).isoformat()
    assert initial.quotes[0].received_at == initial.fetched_at
    assert initial.quotes[0].source_timestamp == "2026-10-19T03:29:55+00:00"
    current[0] = NOW + timedelta(seconds=4.999)
    assert reader().fetch(["FPT"]).from_cache
    current[0] = NOW + timedelta(seconds=5)
    refreshed = reader().fetch(["FPT"])
    assert not refreshed.from_cache and starts == [NOW, NOW + timedelta(seconds=5)]


def test_empty_failures_persist_and_back_off_across_fragment_instances(tmp_path):
    store = Store(tmp_path / "empty-failure.sqlite3")
    current, calls = [NOW], []
    def handler(_):
        calls.append(current[0])
        return httpx.Response(503)
    def reader():
        return RealtimeService(store, clock=lambda: current[0],
                               transport=httpx.MockTransport(handler))
    initial = reader().fetch(["FPT"])
    assert not initial.quotes and initial.fetched_at is None
    for seconds, expected_calls in [
        (0, 1), (5, 1), (9.999, 1), (10, 2), (15, 2),
        (29.999, 2), (30, 3), (35, 3), (59.999, 3), (60, 4),
    ]:
        current[0] = NOW + timedelta(seconds=seconds)
        snapshot = reader().fetch(["FPT"])
        assert len(calls) == expected_calls
        assert not snapshot.quotes and snapshot.fetched_at is None
        assert snapshot.stale and "503" in snapshot.errors[0]
    paused = reader().cached(["FPT"])
    assert paused.from_cache and paused.errors == initial.errors
    assert paused.fetched_at is None and len(calls) == 4


@pytest.mark.parametrize("first_interval,next_interval", [(30, 5), (5, 30)])
def test_failure_honors_selected_thirty_second_interval(tmp_path, first_interval, next_interval):
    store = Store(tmp_path / "selected-interval.sqlite3")
    current, calls = [NOW], []
    def handler(_):
        calls.append(current[0])
        return httpx.Response(500)
    RealtimeService(store, poll_seconds=first_interval, clock=lambda: current[0],
                    transport=httpx.MockTransport(handler)).fetch(["FPT"])
    for seconds in (5, 10, 29.999):
        current[0] = NOW + timedelta(seconds=seconds)
        RealtimeService(store, poll_seconds=next_interval, clock=lambda: current[0],
                        transport=httpx.MockTransport(handler)).fetch(["FPT"])
        assert len(calls) == 1
    current[0] = NOW + timedelta(seconds=30)
    RealtimeService(store, poll_seconds=next_interval, clock=lambda: current[0],
                    transport=httpx.MockTransport(handler)).fetch(["FPT"])
    assert len(calls) == 2


def test_manual_refresh_can_retry_transient_failure_and_success_resets_backoff(tmp_path):
    store = Store(tmp_path / "manual-retry.sqlite3")
    current, calls = [NOW], []
    def handler(_):
        calls.append(current[0])
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json=source())
    def reader():
        return RealtimeService(store, clock=lambda: current[0],
                               transport=httpx.MockTransport(handler))
    assert reader().fetch(["FPT"]).errors
    assert reader().fetch(["FPT"]).from_cache and len(calls) == 1
    assert reader().fetch(["FPT"], force=True).quotes and len(calls) == 2
    current[0] = NOW + timedelta(seconds=4.999)
    reader().fetch(["FPT"])
    assert len(calls) == 2
    current[0] = NOW + timedelta(seconds=5)
    assert not reader().fetch(["FPT"]).from_cache and len(calls) == 3


@pytest.mark.parametrize("status", [403, 429])
@pytest.mark.parametrize("retry_after,cooldown", [
    (None, 30), ("45", 45), ("900", 300), ("-10", 30), ("invalid", 30),
    (format_datetime(NOW + timedelta(seconds=90), usegmt=True), 90),
])
def test_provider_cooldown_survives_new_instances_and_manual_force(tmp_path, status, retry_after, cooldown):
    store = Store(tmp_path / "provider-cooldown.sqlite3")
    current, calls = [NOW], []
    def handler(_):
        calls.append(current[0])
        headers = {"Retry-After": retry_after} if retry_after is not None else {}
        return httpx.Response(status, headers=headers) if len(calls) == 1 else httpx.Response(200, json=source())
    def reader():
        return RealtimeService(store, clock=lambda: current[0],
                               transport=httpx.MockTransport(handler))
    initial = reader().fetch(["FPT"])
    assert str(status) in initial.errors[0]
    current[0] = NOW + timedelta(seconds=cooldown - 0.001)
    held = reader().fetch(["FPT"], force=True)
    assert len(calls) == 1 and held.from_cache and held.errors == initial.errors
    assert reader().cached(["FPT"]).errors == initial.errors
    current[0] = NOW + timedelta(seconds=cooldown)
    assert reader().fetch(["FPT"], force=True).quotes and len(calls) == 2


def test_cooldown_starts_when_rate_limit_response_is_received(tmp_path):
    store = Store(tmp_path / "slow-rate-limit.sqlite3")
    current, calls = [NOW], []
    def handler(_):
        calls.append(current[0])
        if len(calls) == 1:
            current[0] += timedelta(seconds=3)
            return httpx.Response(429, headers={"Retry-After": "30"})
        return httpx.Response(200, json=source())
    def reader():
        return RealtimeService(store, clock=lambda: current[0],
                               transport=httpx.MockTransport(handler))
    reader().fetch(["FPT"])
    current[0] = NOW + timedelta(seconds=30)
    assert reader().fetch(["FPT"], force=True).from_cache and len(calls) == 1
    current[0] = NOW + timedelta(seconds=33)
    assert reader().fetch(["FPT"], force=True).quotes and len(calls) == 2


def test_concurrent_instances_claim_only_one_request_even_with_force(tmp_path):
    store = Store(tmp_path / "concurrent-poll.sqlite3")
    entered, release, calls = Event(), Event(), []
    def handler(_):
        calls.append("HTTP")
        entered.set()
        assert release.wait(4), "test did not release the in-flight request"
        return httpx.Response(200, json=source())
    first = RealtimeService(store, clock=lambda: NOW, transport=httpx.MockTransport(handler))
    second = RealtimeService(store, clock=lambda: NOW,
                             transport=httpx.MockTransport(lambda _: pytest.fail("duplicate HTTP")))
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(first.fetch, ["FPT"])
        try:
            assert entered.wait(3)
            waiting = second.fetch(["FPT"], force=True)
            assert waiting.from_cache and not waiting.quotes and waiting.errors
            assert calls == ["HTTP"]
        finally:
            release.set()
        assert future.result(timeout=4).quotes
    assert second.fetch(["FPT"]).quotes and calls == ["HTTP"]


def test_provider_cooldown_is_scoped_to_workspace_and_symbol_set(tmp_path):
    path = tmp_path / "scoped-poll.sqlite3"
    calls = []
    def handler(_):
        calls.append("HTTP")
        return httpx.Response(429)
    def reader(workspace):
        return RealtimeService(Store(path, workspace), clock=lambda: NOW,
                               transport=httpx.MockTransport(handler))
    reader("one").fetch(["FPT"])
    reader("one").fetch(["FPT"], force=True)
    assert len(calls) == 1
    reader("two").fetch(["FPT"])
    reader("one").fetch(["VCB"])
    assert len(calls) == 3


def test_existing_instance_sees_failed_snapshot_saved_by_another_instance(tmp_path):
    store = Store(tmp_path / "shared-cache.sqlite3")
    first = service(store=store)
    initial = first.fetch(["FPT"])
    failed = RealtimeService(store, clock=lambda: NOW,
                             transport=httpx.MockTransport(lambda _: httpx.Response(429)))
    assert failed.fetch(["FPT"], force=True).errors
    paused = first.cached(["FPT"])
    assert paused.errors and paused.stale and paused.quotes[0].depth_stale
    assert paused.fetched_at == initial.fetched_at


def test_abandoned_poll_states_are_bounded_without_deleting_active_claim(tmp_path):
    store = Store(tmp_path / "bounded-poll-state.sqlite3")
    reader = service(store=store)
    old = (NOW - timedelta(minutes=10)).isoformat()
    with store.connection() as db:
        db.executemany("INSERT INTO board_poll_state VALUES (?,?,?,?,?,?,?,?,?)", [
            (store.workspace, f"A{index}", old, old, 0, None, None, None, None)
            for index in range(45)
        ])
        db.execute("INSERT INTO board_poll_state VALUES (?,?,?,?,?,?,?,?,?)",
                   (store.workspace, "ZZZ", old, old, 0, None,
                    (NOW + timedelta(seconds=30)).isoformat(), "active", None))
    assert reader.fetch(["FPT"]).quotes
    with store.connection() as db:
        count = db.execute("SELECT COUNT(*) FROM board_poll_state WHERE workspace=?",
                           (store.workspace,)).fetchone()[0]
        active = db.execute("SELECT claim_id FROM board_poll_state WHERE workspace=? AND symbols='ZZZ'",
                            (store.workspace,)).fetchone()[0]
    assert count <= 41 and active == "active"


@pytest.mark.parametrize("late_status", [200, 503])
def test_expired_claim_late_response_surfaces_newer_saved_snapshot(tmp_path, late_status):
    store = Store(tmp_path / "claim-fencing.sqlite3")
    current, entered, release = [NOW], Event(), Event()
    def slow_handler(_):
        entered.set()
        assert release.wait(4), "test did not release the late request"
        return httpx.Response(late_status, json=source())
    first = RealtimeService(store, clock=lambda: current[0],
                            transport=httpx.MockTransport(slow_handler))
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(first.fetch, ["FPT"])
        try:
            assert entered.wait(3)
            current[0] = NOW + timedelta(seconds=31)
            newer = source()
            info(newer)["matchPrice"] = 58.1
            info(newer)["tradingTime"] = current[0].isoformat()
            depth(newer)["time"] = current[0].isoformat()
            second = service(newer, store=store, clock=lambda: current[0])
            latest = second.fetch(["FPT"], force=True)
            assert not latest.from_cache and latest.quotes[0].last == 58100
        finally:
            release.set()
        late_result = future.result(timeout=4)
    assert late_result.from_cache and not late_result.errors and not late_result.stale
    assert late_result.quotes[0].last == 58100 and not late_result.quotes[0].depth_stale
    assert late_result.quotes[0].source_timestamp == current[0].isoformat()
    assert second.cached(["FPT"]).quotes[0].last == 58100
