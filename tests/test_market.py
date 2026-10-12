from dataclasses import replace
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from breakout_ai.market import MarketError, MarketService


def yahoo_payload(symbol="AAPL", currency="USD"):
    end = datetime.now(timezone.utc) - timedelta(days=1)
    times = [int((end - timedelta(days=79 - i)).timestamp()) for i in range(80)]
    closes = [100 + i for i in range(80)]
    return {"chart": {"result": [{"meta": {"symbol": symbol, "currency": currency}, "timestamp": times,
        "indicators": {"quote": [{"close": closes, "volume": [10000] * 80}], "adjclose": [{"adjclose": [p * .98 for p in closes]}]}}], "error": None}}


def test_yahoo_request_and_daily_data_are_normalized(settings):
    def handler(request):
        assert request.url.host == "query1.finance.yahoo.com"
        assert request.url.params["interval"] == "1d"
        return httpx.Response(200, json=yahoo_payload())
    service = MarketService(replace(settings, market_enabled=True), transport=httpx.MockTransport(handler))
    snapshot = service.get("US", "aapl")
    assert snapshot.latest.close == 179 and snapshot.currency == "USD"
    assert len(snapshot.bars) == 80 and snapshot.price_basis == "adjusted-by-provider"
    assert snapshot.summary()["fundamentals_available"] is False


def test_chart_cache_read_has_no_network_and_exposes_expired_age(settings, store):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=yahoo_payload())
    service = MarketService(replace(settings, market_enabled=True), store, httpx.MockTransport(handler))
    assert service.cached("US", "AAPL") is None
    service.get("US", "AAPL")
    saved = service.cached("US", "AAPL")
    assert saved.from_cache and not saved.cache_stale and len(requests) == 1
    expired = MarketService(replace(settings, market_cache_seconds=0), store).cached("US", "AAPL")
    assert expired.cache_stale and len(requests) == 1


def test_failed_refresh_flag_survives_chart_cache_read(settings, store):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=yahoo_payload()) if len(calls) == 1 else httpx.Response(503)
    service = MarketService(replace(settings, market_enabled=True), store, httpx.MockTransport(handler))
    service.get("US", "AAPL")
    assert service.get("US", "AAPL", force=True).cache_stale
    assert service.cached("US", "AAPL").cache_stale
    assert service.get("US", "AAPL").cache_stale
    assert len(calls) == 2


def test_kbs_raw_prices_remain_full_vnd(settings):
    def handler(request):
        assert "/stocks/FPT/data_day" in request.url.path
        assert len(request.url.params["sdate"].split("-")) == 3
        return httpx.Response(200, json={"symbol": "FPT", "data_day": [
            {"t": "2026-10-16 07:00", "c": 58200, "v": 3733300},
            {"t": "2026-10-15 07:00", "c": 58000, "v": 1000000}]})
    snapshot = MarketService(replace(settings, market_enabled=True), transport=httpx.MockTransport(handler)).get("VN", "FPT")
    assert snapshot.latest.close == 58200 and snapshot.currency == "VND"
    assert snapshot.bars[0].date == "2026-10-15"


def test_fresh_cache_avoids_network_and_failed_refresh_is_flagged(settings, store):
    requests = []
    def handler(request):
        requests.append(request)
        if len(requests) > 1:
            return httpx.Response(503)
        return httpx.Response(200, json=yahoo_payload())
    service = MarketService(replace(settings, market_enabled=True), store, httpx.MockTransport(handler))
    service.get("US", "AAPL")
    cached = service.get("US", "AAPL")
    assert len(requests) == 1 and cached.from_cache and not cached.cache_stale
    stale = service.get("US", "AAPL", force=True)
    assert len(requests) == 2 and stale.cache_stale


@pytest.mark.parametrize("payload", [
    {"chart": {"result": None}},
    yahoo_payload(currency="CAD"),
    yahoo_payload(symbol="MSFT"),
])
def test_wrong_identity_currency_and_empty_data_are_rejected(settings, payload):
    service = MarketService(replace(settings, market_enabled=True), transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))
    with pytest.raises(MarketError):
        service.get("US", "AAPL")


def test_missing_values_are_skipped_without_fabricating_bars(settings):
    payload = yahoo_payload()
    payload["chart"]["result"][0]["indicators"]["quote"][0]["close"][-1] = None
    service = MarketService(replace(settings, market_enabled=True), transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))
    snapshot = service.get("US", "AAPL")
    assert len(snapshot.bars) == 79 and snapshot.latest.close == 178


def test_many_retains_successes_and_reports_each_failure(settings):
    def handler(request):
        return httpx.Response(200, json=yahoo_payload()) if request.url.path.endswith("AAPL") else httpx.Response(404)
    service = MarketService(replace(settings, market_enabled=True), transport=httpx.MockTransport(handler))
    snapshots, errors = service.many([("US", "AAPL"), ("US", "MISSING")])
    assert len(snapshots) == len(errors) == 1


def test_request_limit_is_applied_before_network(settings):
    service = MarketService(replace(settings, market_enabled=True, market_max_symbols=1))
    with pytest.raises(MarketError, match="tối đa"):
        service.many([("US", "AAPL"), ("US", "MSFT")])


def test_gateway_contract_and_credentials_are_separate_from_data(settings):
    day = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-data-token"
        assert request.url.params["market"] == "VN"
        return httpx.Response(200, json={"market": "VN", "symbol": "FPT", "currency": "VND", "source_url": "https://data.example.org/FPT", "bars": [
            {"date": (day - timedelta(days=1)).isoformat(), "close": 58000, "volume": 100},
            {"date": day.isoformat(), "close": 58200, "volume": 200}]})
    configured = replace(settings, market_enabled=True, vn_market_provider="gateway", market_gateway_url="https://gateway.example.org/history", market_gateway_token="test-data-token")
    snapshot = MarketService(configured, transport=httpx.MockTransport(handler)).get("VN", "FPT")
    assert snapshot.provider == "gateway" and "test-data-token" not in str(snapshot.summary())


def test_http_errors_never_include_provider_response_body(settings):
    service = MarketService(replace(settings, market_enabled=True), transport=httpx.MockTransport(lambda req: httpx.Response(403, text="SECRET-DETAIL")))
    with pytest.raises(MarketError) as error:
        service.get("US", "AAPL")
    assert "SECRET-DETAIL" not in str(error.value)
