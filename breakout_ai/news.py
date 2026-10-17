"""Headline-only RSS reader with publisher provenance and workspace-local cache.

Only the two fixed publisher endpoints below can be fetched. News is a separate
reading aid: it does not enter the book rules or generate investment actions.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

import httpx

from breakout_ai.storage import Store, utc_now


MAX_FEED_BYTES = 512 * 1024
MAX_FEED_ITEMS = 60
MAX_STALE_SECONDS = 7 * 24 * 60 * 60


class NewsError(ValueError):
    """A feed could not safely be read; details are safe to show in the UI."""


@dataclass(frozen=True)
class Feed:
    key: str
    name: str
    market: str
    url: str
    article_host: str
    website: str


FEEDS = (
    Feed("vnexpress-business", "VnExpress · Kinh doanh", "VN",
         "https://vnexpress.net/rss/kinh-doanh.rss", "vnexpress.net",
         "https://vnexpress.net/kinh-doanh"),
    Feed("cnbc-finance", "CNBC · Finance", "US",
         "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
         "cnbc.com", "https://www.cnbc.com/finance/"),
)


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    source: str
    market: str
    published_at: str | None
    fetched_at: str
    feed_url: str
    cache_stale: bool = False

    def payload(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class NewsResult:
    articles: list[Article]
    errors: list[str]
    fetched_at: str | None
    stale: bool = False
    from_cache: bool = False


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)


def _title(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2000:
        return ""
    parser = _Text()
    parser.feed(unescape(value))
    text = " ".join("".join(parser.parts).split())
    text = re.sub(r"[\x00-\x1f\x7f]", "", text)
    return text if 1 <= len(text) <= 500 else ""


def _article_url(value: str, feed: Feed) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 2000:
        return None
    if re.search(r"[\s\x00-\x1f\x7f\\]", value):
        return None
    try:
        url = urlsplit(value)
        host = (url.hostname or "").lower()
        if (url.scheme not in {"http", "https"} or url.username is not None
                or url.password is not None or url.port not in {None, 80, 443}
                or not (host == feed.article_host or host.endswith("." + feed.article_host))):
            return None
        query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
        return urlunsplit((url.scheme, url.netloc.lower(), url.path, urlencode(query), ""))
    except ValueError:
        return None


def _published(value: str | None) -> str | None:
    if not value or len(value) > 100:
        return None
    try:
        try:
            day = parsedate_to_datetime(value)
        except (ValueError, TypeError, IndexError):
            day = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if day.tzinfo is None or day.utcoffset() is None:
            return None
        day = day.astimezone(timezone.utc)
        if day.year < 1990 or day > datetime.now(timezone.utc) + timedelta(days=1):
            return None
        return day.isoformat(timespec="seconds")
    except (ValueError, TypeError, OverflowError):
        return None


def _child(node: ET.Element, name: str) -> ET.Element | None:
    return next((element for element in node if element.tag.rsplit("}", 1)[-1] == name), None)


def _text(node: ET.Element, name: str) -> str:
    element = _child(node, name)
    return "" if element is None else "".join(element.itertext()).strip()


def _parse_feed(data: bytes, feed: Feed, fetched_at: str) -> list[Article]:
    # NUL excludes UTF-16/32 bypasses of the declaration check; sources use UTF-8.
    if (len(data) > MAX_FEED_BYTES or b"\x00" in data
            or re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", data, re.I)):
        raise NewsError("RSS vượt giới hạn hoặc chứa khai báo XML không được hỗ trợ.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise NewsError("Nguồn không trả RSS/Atom hợp lệ.") from exc
    tag = root.tag.rsplit("}", 1)[-1]
    if tag == "rss":
        channel = _child(root, "channel")
        if channel is None:
            raise NewsError("RSS thiếu kênh tin.")
        entries = [node for node in channel if node.tag.rsplit("}", 1)[-1] == "item"]
    elif tag == "feed":
        entries = [node for node in root if node.tag.rsplit("}", 1)[-1] == "entry"]
    else:
        raise NewsError("Nguồn không trả RSS/Atom hợp lệ.")
    articles, seen = [], set()
    for node in entries[:MAX_FEED_ITEMS]:
        headline = _title(_text(node, "title"))
        link = _text(node, "link")
        if tag == "feed":
            link = next((child.attrib.get("href", "") for child in node
                         if child.tag.rsplit("}", 1)[-1] == "link"
                         and child.attrib.get("rel", "alternate") == "alternate"), "")
        safe_url = _article_url(link, feed)
        if not headline or not safe_url or safe_url in seen:
            continue
        published = _published(_text(node, "pubDate") or _text(node, "published") or _text(node, "updated"))
        articles.append(Article(headline, safe_url, feed.name, feed.market,
                                published, fetched_at, feed.url))
        seen.add(safe_url)
    if entries and not articles:
        raise NewsError("Nguồn chưa có tiêu đề và liên kết hợp lệ để hiển thị.")
    return articles


class NewsService:
    """Fetch on explicit page access/refresh, never on import or construction."""

    def __init__(self, store: Store, timeout: float = 10, transport=None, cache_seconds: int = 900):
        if not 1 <= timeout <= 30 or not 60 <= cache_seconds <= 86400:
            raise ValueError("Thời gian chờ hoặc bộ nhớ đệm tin tức không hợp lệ.")
        self.store, self.timeout = store, timeout
        self.transport, self.cache_seconds = transport, cache_seconds
        with store.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS news_cache (
                workspace TEXT NOT NULL, feed_key TEXT NOT NULL,
                fetched_at TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(workspace,feed_key)
            )""")

    def _cached(self, feed: Feed) -> tuple[list[Article], str, float] | None:
        with self.store.connection() as db:
            row = db.execute("SELECT fetched_at,payload FROM news_cache WHERE workspace=? AND feed_key=?",
                             (self.store.workspace, feed.key)).fetchone()
        if not row:
            return None
        try:
            fetched_at = row["fetched_at"]
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)).total_seconds()
            payload = json.loads(row["payload"])
            if age < 0 or age > MAX_STALE_SECONDS or not isinstance(payload, list) or len(payload) > MAX_FEED_ITEMS:
                return None
            articles = []
            for item in payload:
                article = Article(**item)
                if (article.source != feed.name or article.market != feed.market or article.feed_url != feed.url
                        or article.fetched_at != fetched_at or _article_url(article.url, feed) != article.url
                        or _title(article.title) != article.title
                        or (article.published_at is not None and _published(article.published_at) != article.published_at)):
                    return None
                articles.append(replace(article, cache_stale=False))
            return articles, fetched_at, age
        except (ValueError, TypeError, KeyError, OverflowError):
            return None

    def _feed(self, feed: Feed, force: bool) -> tuple[list[Article], str | None, bool, bool, str | None]:
        cached = self._cached(feed)
        if cached and not force and cached[2] < self.cache_seconds:
            return cached[0], cached[1], False, True, None
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport, follow_redirects=False,
                              headers={"User-Agent": "BreakoutAI/0.6 personal RSS reader", "Accept": "application/rss+xml, application/atom+xml, application/xml"}) as client:
                with client.stream("GET", feed.url) as response:
                    response.raise_for_status()
                    if 300 <= response.status_code < 400:
                        raise NewsError("Nguồn yêu cầu chuyển hướng ngoài địa chỉ đã xác minh.")
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_FEED_BYTES:
                            raise NewsError("RSS vượt giới hạn kích thước.")
            fetched_at = utc_now()
            articles = _parse_feed(bytes(data), feed, fetched_at)
            with self.store.connection() as db:
                db.execute("""INSERT INTO news_cache(workspace,feed_key,fetched_at,payload) VALUES (?,?,?,?)
                    ON CONFLICT(workspace,feed_key) DO UPDATE SET fetched_at=excluded.fetched_at,payload=excluded.payload""",
                    (self.store.workspace, feed.key, fetched_at, json.dumps([article.payload() for article in articles], ensure_ascii=False)))
            return articles, fetched_at, False, False, None
        except (httpx.HTTPError, NewsError, ValueError, TypeError):
            error = f"{feed.name}: chưa cập nhật được RSS; nguồn có thể đang lỗi hoặc giới hạn truy cập."
            if cached:
                return [replace(article, cache_stale=True) for article in cached[0]], cached[1], True, True, error
            return [], None, False, False, error

    def fetch(self, market: str = "BOTH", force: bool = False) -> NewsResult:
        if market not in {"VN", "US", "BOTH"}:
            raise ValueError("Chọn tin Việt Nam, Mỹ hoặc cả hai thị trường.")
        feeds = [feed for feed in FEEDS if market == "BOTH" or feed.market == market]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda feed: self._feed(feed, force), feeds))
        articles, seen = [], set()
        for result in results:
            for article in result[0]:
                if article.url not in seen:
                    articles.append(article)
                    seen.add(article.url)
        articles.sort(key=lambda article: (article.published_at or "", article.url), reverse=True)
        fetched_times = [result[1] for result in results if result[1]]
        return NewsResult(articles=articles, errors=[result[4] for result in results if result[4]],
                          fetched_at=min(fetched_times) if fetched_times else None,
                          stale=any(result[2] for result in results),
                          from_cache=any(result[3] for result in results))
