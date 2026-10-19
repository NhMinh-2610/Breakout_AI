from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Event

import httpx
import pytest

from breakout_ai.intraday import (
    MAX_CANDLES, MAX_RESPONSE_BYTES, SOURCE_URL, SUPPORTED_INDICES, Candle,
    IntradayError, IntradayService,
)
from breakout_ai.storage import Store


NOW = datetime(2026, 10, 19, 4, 30, tzinfo=timezone.utc)


def source(*, count=40, resolution=5, end=None):
    end = end or NOW - timedelta(minutes=resolution)
    times = [int((end - timedelta(minutes=resolution * i)).timestamp())
             for i in reversed(range(count))]
    return {"t": times, "o": [200.0] * count, "h": [203.0] * count,
            "l": [199.0] * count, "c": [201.0] * count,
            "v": [123400] * count, "nextTime": 0}


def reader(payload=None, *, store=None, clock=None):
    return IntradayService(
        store, clock=clock or (lambda: NOW),
        transport=httpx.MockTransport(lambda _: httpx.Response(
            200, json=payload if payload is not None else source())))


def test_public_read_only_request_and_units():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.method == "GET" and str(request.url).startswith(SOURCE_URL)
        params = dict(request.url.params)
        assert params == {"symbol": "VIC", "resolution": "5",
                          "from": str(int((NOW - timedelta(days=7)).timestamp())),
                          "to": str(int(NOW.timestamp()))}
        assert "authorization" not in request.headers and "cookie" not in request.headers
        return httpx.Response(200, json=source())
    service = IntradayService(clock=lambda: NOW, transport=httpx.MockTransport(handler))
    assert service.cached("VIC") is None and not calls
    result = service.fetch(" vic ")
    assert len(calls) == 1 and not result.from_cache and not result.stale
    assert not result.errors and result.fetched_at == NOW.isoformat()
    candle = result.candles[-1]
    assert (candle.open, candle.high, candle.low, candle.close) == (200000, 203000, 199000, 201000)
    assert candle.volume == 123400  # Already shares, unlike price-board quantity ×10.
    assert candle.interval_minutes == 5 and candle.complete
    assert candle.time == (NOW - timedelta(minutes=5)).isoformat()


@pytest.mark.parametrize("resolution", ["1", "5", "15"])
def test_supported_resolutions_keep_completion_metadata(resolution):
    result = reader(source(resolution=int(resolution))).fetch("VIC", resolution)
    assert result.resolution == resolution
    assert all(c.interval_minutes == int(resolution) for c in result.candles)


@pytest.mark.parametrize("symbol,resolution", [
    (["VIC"], "5"), ("A", "5"), ("VIC/ABC", "5"), ("VIC;DROP", "5"),
    ("A" * 11, "5"), (True, "5"), ("VIC", "60"), ("VIC", "1D"), ("VIC", 5),
])
def test_invalid_inputs_never_request_network(symbol, resolution):
    service = IntradayService(transport=httpx.MockTransport(lambda _: pytest.fail("network")))
    with pytest.raises(IntradayError):
        service.fetch(symbol, resolution)


def test_missing_volume_is_unknown_instead_of_zero():
    payload = source()
    payload.pop("v")
    result = reader(payload).fetch("VIC")
    assert result.candles and not result.errors
    assert all(c.volume is None for c in result.candles)


def test_null_and_zero_volume_keep_distinct_meaning():
    payload = source()
    payload["v"][-2:] = [None, 0]
    candles = reader(payload).fetch("VIC").candles
    assert candles[-2].volume is None and candles[-1].volume == 0


def test_open_candle_becomes_complete_using_clock_without_network():
    current = [NOW]
    payload = source(count=2, end=NOW - timedelta(minutes=2))
    service = reader(payload, clock=lambda: current[0])
    assert not service.fetch("VIC").candles[-1].complete
    current[0] += timedelta(minutes=4)
    cached = service.cached("VIC")
    assert cached.candles[-1].complete and cached.from_cache and cached.stale


@pytest.mark.parametrize("mutator", [
    lambda p: p.update(t=[]),
    lambda p: p["t"].__setitem__(-1, p["t"][-2]),
    lambda p: p["t"].__setitem__(-1, int(NOW.timestamp()) + 120),
    lambda p: p["t"].__setitem__(-1, int(NOW.timestamp()) - 86400 * 8),
    lambda p: p["t"].__setitem__(-1, True),
    lambda p: p["t"].__setitem__(-1, 1e30),
    lambda p: p["t"].__setitem__(-1, p["t"][-1] + .5),
    lambda p: p["h"].__setitem__(-1, 190),
    lambda p: p["c"].__setitem__(-1, 0),
    lambda p: p["o"].__setitem__(-1, True),
    lambda p: p["l"].__setitem__(-1, "NaN"),
    lambda p: p["v"].__setitem__(-1, -1),
    lambda p: p.update(v=[1]),
    lambda p: p.update(o=None),
    lambda p: p.update(t=None, o=None, h=None, l=None, c=None, v=None),
])
def test_invalid_provider_data_never_fabricates_history(mutator):
    payload = source()
    mutator(payload)
    result = reader(payload).fetch("VIC")
    assert result.candles == [] and result.errors and result.stale
    assert result.fetched_at is None


def test_unordered_provider_bars_are_sorted():
    payload = source()
    for key in ["t", "o", "h", "l", "c", "v"]:
        payload[key].reverse()
    candles = reader(payload).fetch("VIC").candles
    assert [c.time for c in candles] == sorted(c.time for c in candles)


def test_response_and_candle_limits():
    oversized = IntradayService(clock=lambda: NOW, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, content=b" " * (MAX_RESPONSE_BYTES + 1))))
    assert oversized.fetch("VIC").errors
    assert reader(source(count=MAX_CANDLES + 1)).fetch("VIC").candles == []


def test_fresh_fetch_can_have_stale_source_bars():
    result = reader(source(end=NOW - timedelta(hours=2))).fetch("VIC")
    assert result.fetched_at == NOW.isoformat() and result.stale and result.candles


def test_cache_ttl_persists_across_instances_and_is_workspace_scoped(tmp_path):
    store = Store(tmp_path / "data.sqlite3", "one")
    reader(store=store).fetch("VIC")
    service = IntradayService(store, clock=lambda: NOW + timedelta(seconds=29),
        transport=httpx.MockTransport(lambda _: pytest.fail("fresh cache")))
    cached = service.fetch("VIC")
    assert cached.from_cache and not cached.stale and cached.candles[-1].close == 201000
    other = IntradayService(Store(store.path, "two"), clock=lambda: NOW)
    assert other.cached("VIC") is None
    assert service.cached("FPT") is None and service.cached("VIC", "1") is None


def test_force_refresh_bypasses_regular_cache_ttl():
    calls = []
    service = IntradayService(clock=lambda: NOW, transport=httpx.MockTransport(
        lambda request: calls.append(request) or httpx.Response(200, json=source())))
    service.fetch("VIC")
    service.fetch("VIC")
    service.fetch("VIC", force=True)
    assert len(calls) == 2


def test_failure_keeps_original_receipt_time_and_throttles_retries(tmp_path):
    current, calls, fail = [NOW], [], [False]
    store = Store(tmp_path / "data.sqlite3")
    def handler(request):
        calls.append(request)
        return httpx.Response(503) if fail[0] else httpx.Response(200, json=source())
    service = IntradayService(store, clock=lambda: current[0], transport=httpx.MockTransport(handler))
    first = service.fetch("VIC")
    fail[0] = True
    current[0] += timedelta(seconds=31)
    fallback = service.fetch("VIC")
    assert fallback.candles == first.candles and fallback.from_cache and fallback.stale
    assert fallback.fetched_at == first.fetched_at and fallback.errors
    next_instance = IntradayService(store, clock=lambda: current[0], transport=httpx.MockTransport(handler))
    assert next_instance.fetch("VIC").from_cache
    assert len(calls) == 2


@pytest.mark.parametrize("status", [403, 429])
def test_manual_refresh_obeys_provider_cooldown(status, tmp_path):
    calls, current = [], [NOW]
    store = Store(tmp_path / "data.sqlite3")
    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"Retry-After": "120"})
    reader1 = IntradayService(store, clock=lambda: current[0], transport=httpx.MockTransport(handler))
    assert reader1.fetch("VIC").errors
    reader2 = IntradayService(store, clock=lambda: current[0], transport=httpx.MockTransport(handler))
    assert reader2.fetch("VIC", force=True).errors
    current[0] += timedelta(seconds=119)
    reader2.fetch("VIC", force=True)
    assert len(calls) == 1
    current[0] += timedelta(seconds=2)
    reader2.fetch("VIC", force=True)
    assert len(calls) == 2


def test_inflight_lease_prevents_duplicate_cross_instance_requests(tmp_path):
    entered, release, calls = Event(), Event(), []
    store = Store(tmp_path / "data.sqlite3")
    def handler(request):
        calls.append(request)
        entered.set()
        assert release.wait(5)
        return httpx.Response(200, json=source())
    first = IntradayService(store, clock=lambda: NOW, transport=httpx.MockTransport(handler))
    second = IntradayService(store, clock=lambda: NOW, transport=httpx.MockTransport(handler))
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(first.fetch, "VIC")
        assert entered.wait(5)
        blocked = second.fetch("VIC", force=True)
        release.set()
        result = pending.result(timeout=5)
    assert result.candles and not blocked.candles and blocked.errors
    assert len(calls) == 1


def test_corrupted_saved_candles_are_not_rendered(tmp_path):
    store = Store(tmp_path / "data.sqlite3")
    service = reader(store=store)
    service.fetch("VIC")
    with store.connection() as db:
        db.execute("UPDATE intraday_cache SET payload=?", ('{"symbol": "VIC"}',))
    assert service.cached("VIC") is None


@pytest.mark.parametrize("symbol", list(SUPPORTED_INDICES))
def test_indices_use_separate_endpoint_and_points_instead_of_equity_scale(symbol):
    calls = []
    def handler(request):
        calls.append(request)
        assert str(request.url).startswith(SOURCE_URL + "/index?")
        return httpx.Response(200, json=source())
    service = IntradayService(clock=lambda: NOW, transport=httpx.MockTransport(handler))
    snapshot = service.fetch(symbol)
    assert snapshot.candles[-1].close == 201.0
    assert snapshot.price_unit == "points" and snapshot.asset_type == "index"
    assert snapshot.source_url == SOURCE_URL + "/index"
    assert snapshot.candles[-1].volume == 123400 and len(calls) == 1


def test_index_cache_preserves_points_and_asset_type(tmp_path):
    store = Store(tmp_path / "index.sqlite3")
    reader(store=store).fetch("VNINDEX")
    service = IntradayService(store, clock=lambda: NOW,
        transport=httpx.MockTransport(lambda _: pytest.fail("fresh index cache")))
    snapshot = service.fetch("VNINDEX")
    assert snapshot.from_cache and snapshot.price_unit == "points"
    assert snapshot.candles[-1].close == 201


def test_empty_index_snapshot_does_not_claim_vnd_units():
    result = reader({}).fetch("VNINDEX")
    assert result.errors and result.source_url.endswith("/index")
    assert result.asset_type == "index" and result.price_unit == "points"
