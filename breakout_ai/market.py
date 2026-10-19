"""On-demand daily market data, with explicit provenance and cache status.

Public KBS/Yahoo adapters are research integrations, not licensed commercial feeds.
No fallback creates data, changes a currency, or silently changes providers.
"""

from dataclasses import asdict, dataclass, replace
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone
import json
import re

import httpx

from breakout_ai.config import Settings
from breakout_ai.finance import number, validate_symbol
from breakout_ai.storage import Store, utc_now


class MarketError(ValueError):
    pass


@dataclass(frozen=True)
class Bar:
    date: str
    close: float
    volume: float
    adjusted_close: float | None = None


@dataclass(frozen=True)
class MarketSnapshot:
    market: str
    symbol: str
    currency: str
    provider: str
    source_url: str
    fetched_at: str
    bars: list[Bar]
    price_basis: str = "provider-adjustment-unknown"
    cache_stale: bool = False
    from_cache: bool = False

    @property
    def latest(self) -> Bar:
        return self.bars[-1]

    def summary(self) -> dict:
        previous = self.bars[-2].close if len(self.bars) > 1 else None
        return {
            "market": self.market, "symbol": self.symbol, "currency": self.currency,
            "provider": self.provider, "source_url": self.source_url,
            "as_of": self.latest.date, "fetched_at": self.fetched_at,
            "close": self.latest.close, "volume": self.latest.volume,
            "change_pct": (self.latest.close / previous - 1) * 100 if previous else None,
            "price_basis": self.price_basis,
            "data_kind": "daily-bar; may include an unfinished trading session; not a realtime quote",
            "cache_stale": self.cache_stale, "from_cache": self.from_cache,
            "fundamentals_available": False,
        }


def _bars(rows: list[dict]) -> list[Bar]:
    if not isinstance(rows, list) or not 2 <= len(rows) <= 400:
        raise MarketError("Nguồn cần trả về 2–400 phiên hợp lệ.")
    result, seen = [], set()
    today = datetime.now(timezone.utc).date()
    for row in rows:
        day = row["date"]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or date.fromisoformat(day) > today:
            raise MarketError("Nguồn trả về ngày không hợp lệ.")
        if day in seen:
            raise MarketError("Nguồn trả về trùng ngày giao dịch.")
        close, volume = number(row["close"], "Giá"), number(row["volume"], "Khối lượng")
        adjusted = row.get("adjusted_close")
        adjusted = number(adjusted, "Giá điều chỉnh") if adjusted is not None else None
        if close <= 0 or volume < 0 or (adjusted is not None and adjusted <= 0):
            raise MarketError("Giá phải dương và khối lượng không được âm.")
        result.append(Bar(day, close, volume, adjusted))
        seen.add(day)
    return sorted(result, key=lambda bar: bar.date)


class MarketService:
    def __init__(self, settings: Settings, store: Store | None = None, transport=None):
        self.settings, self.store, self.transport = settings, store, transport
        if store:
            with store.connection() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS market_cache (
                    workspace TEXT NOT NULL, provider TEXT NOT NULL, market TEXT NOT NULL,
                    symbol TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(workspace,provider,market,symbol)
                )""")

    def _read_cache(self, provider: str, market: str, symbol: str) -> MarketSnapshot | None:
        if not self.store:
            return None
        with self.store.connection() as db:
            row = db.execute("SELECT payload FROM market_cache WHERE workspace=? AND provider=? AND market=? AND symbol=?", (self.store.workspace, provider, market, symbol)).fetchone()
        if not row:
            return None
        try:
            data = json.loads(row["payload"])
            data["bars"] = _bars(data["bars"])
            if (data["market"], data["symbol"], data["provider"]) != (market, symbol, provider):
                return None
            if data["currency"] != {"VN": "VND", "US": "USD"}[market]:
                return None
            return MarketSnapshot(**data)
        except (ValueError, TypeError, KeyError):
            return None

    def cached(self, market: str, symbol: str) -> MarketSnapshot | None:
        """Read saved chart data without a network call; expose cache age honestly."""
        if market not in {"VN", "US"}:
            raise MarketError("Chọn VN hoặc US cho từng mã.")
        symbol = validate_symbol(symbol)
        provider = self.settings.vn_market_provider if market == "VN" else self.settings.us_market_provider
        snapshot = self._read_cache(provider, market, symbol)
        if snapshot is None:
            return None
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(snapshot.fetched_at)).total_seconds()
        except (ValueError, TypeError):
            return None
        return replace(snapshot, from_cache=True, cache_stale=snapshot.cache_stale or not 0 <= age < self.settings.market_cache_seconds)

    def _client(self) -> httpx.Client:
        # One bounded pool per batch, shared safely by its worker threads.
        return httpx.Client(
            timeout=self.settings.market_timeout, transport=self.transport,
            follow_redirects=False,
            headers={"User-Agent": "BreakoutAI/0.6 research application"},
            limits=httpx.Limits(max_connections=3, max_keepalive_connections=3, keepalive_expiry=30),
        )

    def get(self, market: str, symbol: str, force: bool = False) -> MarketSnapshot:
        return self._get(market, symbol, force)

    def _get(self, market: str, symbol: str, force: bool = False, client: httpx.Client | None = None) -> MarketSnapshot:
        if not self.settings.market_enabled:
            raise MarketError("Dữ liệu thị trường chưa kết nối: MARKET_DATA_ENABLED=false.")
        if market not in {"VN", "US"}:
            raise MarketError("Chọn VN hoặc US cho từng mã.")
        symbol = validate_symbol(symbol)
        provider = self.settings.vn_market_provider if market == "VN" else self.settings.us_market_provider
        cached = self._read_cache(provider, market, symbol)
        if cached:
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached.fetched_at)).total_seconds()
            except (ValueError, TypeError):
                cached, age = None, float("inf")
            if cached and not force and 0 <= age < self.settings.market_cache_seconds:
                return replace(cached, from_cache=True)
        try:
            with self._client() if client is None else nullcontext(client) as active_client:
                if provider == "yahoo":
                    snapshot = self._yahoo(active_client, symbol)
                elif provider == "kbs":
                    snapshot = self._kbs(active_client, symbol)
                elif provider == "gateway":
                    snapshot = self._gateway(active_client, market, symbol)
                else:
                    raise MarketError("Nhà cung cấp dữ liệu không được hỗ trợ.")
            if self.store:
                with self.store.connection() as db:
                    db.execute("INSERT INTO market_cache VALUES (?,?,?,?,?) ON CONFLICT(workspace,provider,market,symbol) DO UPDATE SET payload=excluded.payload", (self.store.workspace, provider, market, symbol, json.dumps(asdict(snapshot))))
            return snapshot
        except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            if cached:
                stale = replace(cached, from_cache=True, cache_stale=True)
                if self.store:
                    with self.store.connection() as db:
                        db.execute("UPDATE market_cache SET payload=? WHERE workspace=? AND provider=? AND market=? AND symbol=?", (json.dumps(asdict(stale)), self.store.workspace, provider, market, symbol))
                return stale
            if isinstance(exc, MarketError):
                raise
            raise MarketError(f"Không lấy được dữ liệu {market}:{symbol} từ {provider}. Nguồn có thể đang lỗi, giới hạn truy cập hoặc đổi định dạng; không có dữ liệu thay thế giả định.") from exc

    def _yahoo(self, client: httpx.Client, symbol: str) -> MarketSnapshot:
        response = client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", params={"range": "6mo", "interval": "1d", "includeAdjustedClose": "true"})
        response.raise_for_status()
        data = response.json()["chart"]["result"][0]
        meta = data["meta"]
        if meta["currency"] != "USD" or meta["symbol"].upper() != symbol:
            raise MarketError("Yahoo trả mã hoặc tiền tệ khác yêu cầu US/USD; không tự quy đổi.")
        prices = data["indicators"]["quote"][0]
        adjusted = (data["indicators"].get("adjclose") or [{}])[0].get("adjclose", [])
        rows = []
        for index, timestamp in enumerate(data["timestamp"]):
            close = prices["close"][index]
            volume = prices["volume"][index]
            if close is None or volume is None:
                continue
            rows.append({"date": datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(), "close": close, "volume": volume, "adjusted_close": adjusted[index] if index < len(adjusted) else None})
        bars = _bars(rows)
        basis = "adjusted-by-provider" if all(b.adjusted_close is not None for b in bars) else "unadjusted"
        return MarketSnapshot("US", symbol, "USD", "yahoo", f"https://finance.yahoo.com/quote/{symbol}/history/", utc_now(), bars, basis)

    def _kbs(self, client: httpx.Client, symbol: str) -> MarketSnapshot:
        end = datetime.now(timezone.utc).date() + timedelta(days=1)
        start = end - timedelta(days=230)
        url = f"https://kbbuddywts.kbsec.com.vn/iis-server/investment/stocks/{symbol}/data_day"
        response = client.get(url, params={"sdate": start.strftime("%d-%m-%Y"), "edate": end.strftime("%d-%m-%Y")})
        response.raise_for_status()
        data = response.json()
        if data.get("symbol", "").upper() != symbol:
            raise MarketError("KBS trả mã khác yêu cầu.")
        # KBS raw stock prices are already VND. Do not divide by 1000.
        rows = [{"date": row["t"][:10], "close": row["c"], "volume": row["v"]} for row in data["data_day"]]
        return MarketSnapshot("VN", symbol, "VND", "kbs", url, utc_now(), _bars(rows))

    def _gateway(self, client: httpx.Client, market: str, symbol: str) -> MarketSnapshot:
        if not self.settings.market_gateway_url:
            raise MarketError("Thiếu MARKET_GATEWAY_URL cho nguồn dữ liệu của bạn.")
        headers = {"Authorization": f"Bearer {self.settings.market_gateway_token}"} if self.settings.market_gateway_token else {}
        response = client.get(self.settings.market_gateway_url, params={"market": market, "symbol": symbol}, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data["market"] != market or data["symbol"] != symbol or data["currency"] != {"VN": "VND", "US": "USD"}[market]:
            raise MarketError("Gateway trả market/symbol/currency không khớp yêu cầu.")
        basis = data.get("price_basis", "provider-adjustment-unknown")
        if basis not in {"provider-adjustment-unknown", "unadjusted", "adjusted-by-provider"}:
            raise MarketError("price_basis của gateway không hợp lệ.")
        source_url = data["source_url"]
        if not isinstance(source_url, str) or not source_url.startswith("https://"):
            raise MarketError("Gateway cần source_url HTTPS để đối chiếu nguồn.")
        return MarketSnapshot(market, symbol, data["currency"], "gateway", source_url, utc_now(), _bars(data["bars"]), basis)

    def many(self, symbols: list[tuple[str, str]], force: bool = False) -> tuple[list[MarketSnapshot], list[str]]:
        # Normalize before deduplication/limits, matching get() identity semantics.
        identities = list(dict.fromkeys((market, symbol.strip().upper()) for market, symbol in symbols))
        if len(identities) > self.settings.market_max_symbols:
            raise MarketError(f"Mỗi lần tối đa {self.settings.market_max_symbols} mã để giới hạn request.")
        def fetch(identity):
            market, symbol = identity
            try:
                return self._get(market, symbol, force, client), None
            except ValueError as exc:
                return None, str(exc)
        snapshots, errors = [], []
        if not identities:
            return snapshots, errors
        # HTTPX Client supports thread sharing: workers reuse its TCP/TLS pool.
        # Fresh cache entries still return before any HTTP request is made.
        with self._client() as client:
            with ThreadPoolExecutor(max_workers=min(3, len(identities))) as workers:
                for snapshot, error in workers.map(fetch, identities):
                    if snapshot is not None:
                        snapshots.append(snapshot)
                    if error:
                        errors.append(error)
        return snapshots, errors
