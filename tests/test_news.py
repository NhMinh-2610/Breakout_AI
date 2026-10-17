from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest

from breakout_ai.news import FEEDS, MAX_FEED_BYTES, NewsService
from breakout_ai.storage import Store


VN_RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Market &amp; business</title><link>https://vnexpress.net/market-123.html?utm_source=rss</link><pubDate>Fri, 16 Oct 2026 09:00:00 +0700</pubDate><description>Do not store this article body.</description></item>
<item><title>Duplicate</title><link>https://vnexpress.net/market-123.html</link></item>
</channel></rss>'''
US_RSS = b'''<rss><channel><item><title>Wall Street update</title>
<link>https://www.cnbc.com/2026/10/16/market.html</link><pubDate>Fri, 16 Oct 2026 12:00:00 GMT</pubDate>
</item></channel></rss>'''


def response(request):
    return httpx.Response(200, content=VN_RSS if request.url.host == "vnexpress.net" else US_RSS)


def age_cache(store, days=0, seconds=0):
    timestamp = (datetime.now(timezone.utc) - timedelta(days=days, seconds=seconds)).isoformat(timespec="microseconds")
    with store.connection() as db:
        for row in db.execute("SELECT feed_key,payload FROM news_cache WHERE workspace=?", (store.workspace,)).fetchall():
            payload = json.loads(row["payload"])
            for article in payload:
                article["fetched_at"] = timestamp
            db.execute("UPDATE news_cache SET fetched_at=?,payload=? WHERE workspace=? AND feed_key=?",
                       (timestamp, json.dumps(payload), store.workspace, row["feed_key"]))


def test_reader_has_no_network_until_fetch_and_keeps_provenance(store):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return response(request)

    service = NewsService(store, transport=httpx.MockTransport(handler))
    assert calls == []
    result = service.fetch()
    assert set(calls) == {feed.url for feed in FEEDS}
    assert len(result.articles) == 2
    assert result.articles[0].market == "US"
    assert result.errors == [] and not result.stale and not result.from_cache
    assert result.fetched_at
    article = next(item for item in result.articles if item.market == "VN")
    assert article.title == "Market & business"
    assert article.url == "https://vnexpress.net/market-123.html"
    assert article.source == FEEDS[0].name
    assert article.feed_url == FEEDS[0].url
    assert article.published_at == "2026-10-16T02:00:00+00:00"
    with store.connection() as db:
        payloads = str([row[0] for row in db.execute("SELECT payload FROM news_cache")])
    assert "Do not store this article body" not in payloads


def test_fresh_cache_reused_force_refreshes_and_market_filter(store):
    calls = []

    def handler(request):
        calls.append(request.url.host)
        return response(request)

    service = NewsService(store, transport=httpx.MockTransport(handler))
    service.fetch("VN")
    cached = service.fetch("VN")
    assert calls == ["vnexpress.net"]
    assert cached.from_cache and not cached.stale
    assert {item.market for item in cached.articles} == {"VN"}
    service.fetch("VN", force=True)
    assert calls == ["vnexpress.net", "vnexpress.net"]
    with pytest.raises(ValueError):
        service.fetch("http://localhost")


def test_cache_expiry_triggers_new_network_request(store):
    NewsService(store, transport=httpx.MockTransport(response)).fetch("VN")
    age_cache(store, seconds=901)
    calls = []

    def handler(request):
        calls.append(request)
        return response(request)

    result = NewsService(store, transport=httpx.MockTransport(handler)).fetch("VN")
    assert len(calls) == 1 and not result.from_cache


def test_timeout_returns_stale_cache_and_sanitized_error(store):
    NewsService(store, transport=httpx.MockTransport(response)).fetch("VN")
    age_cache(store, seconds=901)

    def timeout(request):
        raise httpx.ReadTimeout("secret-value or traceback", request=request)

    result = NewsService(store, transport=httpx.MockTransport(timeout)).fetch("VN")
    assert result.stale and result.from_cache
    assert all(item.cache_stale for item in result.articles)
    assert len(result.errors) == 1 and "secret-value" not in result.errors[0]
    age_cache(store, days=8)
    expired = NewsService(store, transport=httpx.MockTransport(timeout)).fetch("VN")
    assert expired.articles == [] and expired.errors and not expired.stale


def test_failure_on_one_feed_does_not_hide_other_feed(store):
    def handler(request):
        return httpx.Response(403, text="blocked") if request.url.host != "vnexpress.net" else response(request)

    result = NewsService(store, transport=httpx.MockTransport(handler)).fetch()
    assert len(result.articles) == 1 and result.articles[0].market == "VN"
    assert len(result.errors) == 1 and "CNBC" in result.errors[0]


@pytest.mark.parametrize("content", [
    b"<html><body>Not RSS</body></html>", b"<rss><broken>",
    b'<!DOCTYPE rss [<!ENTITY secret "injected">]><rss><channel/></rss>',
    '<rss><channel/></rss>'.encode('utf-16'),
    b"<rss><channel>" + b" " * MAX_FEED_BYTES + b"</channel></rss>",
], ids=["html", "broken-xml", "entity", "utf16", "too-large"])
def test_malformed_unsafe_or_oversized_feed_rejected(store, content):
    result = NewsService(store, transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content))).fetch("VN")
    assert result.articles == [] and result.errors


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "file:///C:/secret", "http://127.0.0.1/feed",
    "https://user:password@vnexpress.net/news", "https://vnexpress.net.evil.example/news",
    "https://vnexpress.net:8080/news", "https://vnexpress.net/has space",
], ids=["script", "file", "loopback", "credentials", "wrong-host", "port", "space"])
def test_unsafe_article_links_rejected_without_following(store, url):
    calls = []
    content = f"<rss><channel><item><title>Headline</title><link>{url}</link></item></channel></rss>".encode()

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=content)

    result = NewsService(store, transport=httpx.MockTransport(handler)).fetch("VN")
    assert result.articles == [] and result.errors
    assert calls == [FEEDS[0].url]


def test_redirect_is_not_followed(store):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    result = NewsService(store, transport=httpx.MockTransport(handler)).fetch("VN")
    assert len(calls) == 1 and result.errors and not result.articles


def test_atom_markup_and_invalid_dates_are_explicitly_unknown(store):
    content = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <title>&lt;b&gt;Plain headline&lt;/b&gt;</title>
      <link rel="alternate" href="https://www.cnbc.com/story"/>
      <published>2099-01-01T00:00:00Z</published></entry>
      <entry><title>No timezone</title><link href="https://cnbc.com/other"/>
      <published>2026-10-16T09:00:00</published></entry></feed>'''
    result = NewsService(store, transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content))).fetch("US")
    assert len(result.articles) == 2
    assert {article.title for article in result.articles} == {"Plain headline", "No timezone"}
    assert all(article.published_at is None for article in result.articles)


def test_cache_isolated_by_workspace(store):
    NewsService(store, transport=httpx.MockTransport(response)).fetch("VN")
    other = Store(store.path, "other")
    result = NewsService(other, transport=httpx.MockTransport(lambda request: httpx.Response(503))).fetch("VN")
    assert not result.articles and result.errors and not result.from_cache


def test_corrupted_cache_is_not_displayed(store):
    NewsService(store, transport=httpx.MockTransport(response)).fetch("VN")
    with store.connection() as db:
        db.execute("UPDATE news_cache SET payload=?", ('[{"url":"javascript:alert(1)"}]',))
    result = NewsService(store, transport=httpx.MockTransport(lambda request: httpx.Response(503))).fetch("VN")
    assert not result.articles and result.errors
