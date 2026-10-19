"""Read-only DNSE public snapshots, explicitly polled rather than tick streaming.

Equity-board prices are normalized to VND, quantities to individual shares and
values to VND. Missing source values remain None. Daily research data is separate.
"""

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import math
import re
from threading import RLock
from typing import Callable
from uuid import uuid4

import httpx

from breakout_ai.storage import Store


SOURCE_URL = "https://api.dnse.com.vn/price-api/query"
SOURCE_NAME = "DNSE public snapshot"
MAX_SYMBOLS = 30
MAX_RESPONSE_BYTES = 1_000_000
MAX_SOURCE_AGE_SECONDS = 180
VN_TIME = timezone(timedelta(hours=7))
EXCHANGES = {6: "HOSE", 7: "HNX", 8: "UPCOM"}
INFO_FIELDS = """symbol highLimitPrice lowLimitPrice referencePrice matchPrice
matchQuantity totalVolumeTraded grossTradeAmount openPrice highestPrice lowestPrice
averagePrice buyForeignQuantity sellForeignQuantity tradingTime marketId
productGrpId securityGroupId tradingSessionId"""
DEPTH_FIELDS = """symbol bidPrice1 bidQtty1 bidPrice2 bidQtty2 bidPrice3 bidQtty3
 offerPrice1 offerQtty1 offerPrice2 offerQtty2 offerPrice3 offerQtty3 time"""


class RealtimeError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _number(value, *, multiplier=1.0, price=False) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise RealtimeError("Dữ liệu số không hợp lệ.")
    try:
        result = float(value) * multiplier
    except (TypeError, ValueError, OverflowError) as exc:
        raise RealtimeError("Dữ liệu số không hợp lệ.") from exc
    if not math.isfinite(result) or result < 0 or result > 1e20:
        raise RealtimeError("Dữ liệu số vượt giới hạn hợp lệ.")
    # DNSE uses a zero price when there has not been a valid match/order.
    return None if price and result == 0 else result


def _timestamp(value, now: datetime) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise RealtimeError("Thời gian nguồn không hợp lệ.")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RealtimeError("Thời gian nguồn không hợp lệ.") from exc
    if moment.tzinfo is None or moment > now + timedelta(seconds=30):
        raise RealtimeError("Thời gian nguồn thiếu múi giờ hoặc nằm trong tương lai.")
    return moment.astimezone(timezone.utc).isoformat()


def _old(timestamp: str | None, now: datetime) -> bool:
    if timestamp is None:
        return True
    age = (now - datetime.fromisoformat(timestamp)).total_seconds()
    return not -30 <= age <= MAX_SOURCE_AGE_SECONDS


def _symbols(values) -> list[str]:
    if isinstance(values, str) or not isinstance(values, (list, tuple, set)):
        raise RealtimeError("Cung cấp danh sách mã chứng khoán Việt Nam.")
    result = []
    for value in values:
        if not isinstance(value, str):
            raise RealtimeError("Mã chứng khoán không hợp lệ.")
        symbol = value.strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", symbol):
            raise RealtimeError("Mã chứng khoán cần có 2–10 ký tự chữ và số.")
        if symbol not in result:
            result.append(symbol)
    if len(result) > MAX_SYMBOLS:
        raise RealtimeError(f"Mỗi bảng giá hỗ trợ tối đa {MAX_SYMBOLS} mã.")
    return result


@dataclass(frozen=True)
class PriceLevel:
    price: float | None = None
    volume: float | None = None


@dataclass(frozen=True)
class LiveQuote:
    symbol: str
    exchange: str
    reference: float | None
    ceiling: float | None
    floor: float | None
    last: float | None
    change: float | None
    change_pct: float | None
    match_volume: float | None
    total_volume: float | None
    total_value: float | None
    open: float | None
    high: float | None
    low: float | None
    average: float | None
    foreign_buy_volume: float | None
    foreign_sell_volume: float | None
    bids: list[PriceLevel]
    asks: list[PriceLevel]
    source_timestamp: str | None
    received_at: str
    stale: bool
    depth_timestamp: str | None = None
    depth_stale: bool = True
    market: str = "VN"
    currency: str = "VND"
    source: str = SOURCE_NAME
    source_url: str = SOURCE_URL
    trading_session: str | None = None

    def payload(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BoardSnapshot:
    quotes: list[LiveQuote] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    fetched_at: str | None = None
    mode: str = "polling"
    source: str = SOURCE_NAME
    source_url: str = SOURCE_URL
    from_cache: bool = False
    stale: bool = False
    poll_seconds: int = 5

    def payload(self) -> dict:
        return asdict(self)


def _quote(info: dict, depth: dict | None, now: datetime) -> LiveQuote:
    symbol = _symbols([info.get("symbol")])[0]
    market_id = info.get("marketId")
    if isinstance(market_id, bool) or market_id not in EXCHANGES:
        raise RealtimeError("Sàn giao dịch không thuộc bảng cổ phiếu được hỗ trợ.")
    received = now.isoformat()
    trade_time = _timestamp(info.get("tradingTime"), now)
    # The two datasets have separate observation clocks; neither clock is replaced
    # with the HTTP receive time or with the timestamp of the other dataset.
    depth_time = _timestamp(depth.get("time"), now) if depth else None
    price = lambda name: _number(info.get(name), multiplier=1_000, price=True)
    shares = lambda name: _number(info.get(name), multiplier=10)
    reference, last = price("referencePrice"), price("matchPrice")
    ceiling, floor = price("highLimitPrice"), price("lowLimitPrice")
    if floor is not None and reference is not None and floor > reference:
        raise RealtimeError("Giá sàn lớn hơn giá tham chiếu.")
    if ceiling is not None and reference is not None and ceiling < reference:
        raise RealtimeError("Giá trần nhỏ hơn giá tham chiếu.")
    if floor is not None and ceiling is not None and floor > ceiling:
        raise RealtimeError("Khoảng giá trần/sàn không hợp lệ.")
    high, low = price("highestPrice"), price("lowestPrice")
    if high is not None and low is not None and high < low:
        raise RealtimeError("Giá cao nhất nhỏ hơn giá thấp nhất.")
    def levels(side: str) -> list[PriceLevel]:
        if not depth:
            return [PriceLevel() for _ in range(3)]
        return [PriceLevel(
            _number(depth.get(f"{side}Price{level}"), multiplier=1_000, price=True),
            _number(depth.get(f"{side}Qtty{level}"), multiplier=10),
        ) for level in range(1, 4)]
    change = last - reference if last is not None and reference else None
    return LiveQuote(
        symbol=symbol, exchange=EXCHANGES[market_id], reference=reference,
        ceiling=ceiling, floor=floor, last=last, change=change,
        change_pct=change / reference * 100 if change is not None and reference else None,
        match_volume=shares("matchQuantity"), total_volume=shares("totalVolumeTraded"),
        total_value=_number(info.get("grossTradeAmount"), multiplier=1_000_000_000),
        open=price("openPrice"), high=high, low=low, average=price("averagePrice"),
        foreign_buy_volume=shares("buyForeignQuantity"),
        foreign_sell_volume=shares("sellForeignQuantity"),
        bids=levels("bid"), asks=levels("offer"), source_timestamp=trade_time,
        received_at=received, stale=_old(trade_time, now), depth_timestamp=depth_time,
        depth_stale=_old(depth_time, now),
        trading_session=str(info["tradingSessionId"]) if info.get("tradingSessionId") is not None else None,
    )


@dataclass(frozen=True)
class _PollState:
    attempted_at: str | None = None
    next_poll_at: str | None = None
    failure_count: int = 0
    hard_until: str | None = None
    lease_until: str | None = None
    claim_id: str | None = None
    last_error: str | None = None


def _moment(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value)
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (TypeError, ValueError):
        return None


def _retry_after(response: httpx.Response, now: datetime) -> float:
    """403/429 always rest at least 30s; bounded Retry-After also supports dates."""
    value = response.headers.get("Retry-After", "")
    try:
        seconds = float(value)
    except ValueError:
        try:
            moment = parsedate_to_datetime(value)
            seconds = (moment - now).total_seconds() if moment.tzinfo else 0
        except (TypeError, ValueError, OverflowError):
            seconds = 0
    return max(30, min(300, seconds)) if math.isfinite(seconds) else 30


class RealtimeService:
    """One batched read per poll, with persistent claims, backoff and cooldowns."""

    def __init__(self, store: Store | None = None, *, timeout=5, transport=None,
                 poll_seconds=5, clock: Callable[[], datetime] | None = None):
        self.store = store
        self.timeout = min(8, max(1, float(timeout)))
        self.transport = transport
        self.poll_seconds = min(60, max(5, int(poll_seconds)))
        self.clock = clock or _now
        self._memory: dict[str, tuple[BoardSnapshot, str]] = {}
        self._poll_memory: dict[str, _PollState] = {}
        self._lock = RLock()
        if store:
            with store.connection() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS board_snapshot_cache (
                    workspace TEXT NOT NULL, symbols TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(workspace,symbols))""")
                db.execute("""CREATE TABLE IF NOT EXISTS board_poll_state (
                    workspace TEXT NOT NULL, symbols TEXT NOT NULL,
                    attempted_at TEXT, next_poll_at TEXT,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    hard_until TEXT, lease_until TEXT, claim_id TEXT, last_error TEXT,
                    PRIMARY KEY(workspace,symbols))""")

    def _save(self, key: str, snapshot: BoardSnapshot, now: datetime, db=None) -> None:
        self._memory[key] = (snapshot, now.isoformat())
        if db is not None:
            payload = {**snapshot.payload(), "_saved_at": now.isoformat()}
            db.execute("INSERT OR REPLACE INTO board_snapshot_cache VALUES (?,?,?)",
                       (self.store.workspace, key, json.dumps(payload, allow_nan=False)))
            # Bound abandoned symbol combinations from search/filter usage.
            db.execute("""DELETE FROM board_snapshot_cache WHERE workspace=? AND rowid NOT IN
                (SELECT rowid FROM board_snapshot_cache WHERE workspace=? ORDER BY rowid DESC LIMIT 20)""",
                       (self.store.workspace, self.store.workspace))
        while len(self._memory) > 20:
            del self._memory[next(iter(self._memory))]

    def _cached(self, key: str, now: datetime) -> BoardSnapshot | None:
        result, saved_at = self._memory.get(key, (None, None))
        # SQLite is authoritative: another instance may have completed a newer poll.
        if self.store:
            with self.store.connection() as db:
                row = db.execute("SELECT payload FROM board_snapshot_cache WHERE workspace=? AND symbols=?",
                                 (self.store.workspace, key)).fetchone()
            if row is None:
                return None
            try:
                data = json.loads(row["payload"])
                saved_at = data.pop("_saved_at", data.get("fetched_at"))
                quotes = []
                expected = set(key.split(","))
                for item in data.pop("quotes"):
                    if item["symbol"] not in expected or item["exchange"] not in EXCHANGES.values():
                        return None
                    if item.get("market") != "VN" or item.get("currency") != "VND":
                        return None
                    if item.get("source_url") != SOURCE_URL or item.get("source") != SOURCE_NAME:
                        return None
                    _timestamp(item.get("source_timestamp"), now)
                    _timestamp(item.get("depth_timestamp"), now)
                    _timestamp(item.get("received_at"), now)
                    for name in ("reference", "ceiling", "floor", "last", "match_volume", "total_volume",
                                 "total_value", "open", "high", "low", "average", "foreign_buy_volume",
                                 "foreign_sell_volume"):
                        _number(item.get(name))
                    for name in ("change", "change_pct"):
                        value = item.get(name)
                        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                            return None
                    for side in ("bids", "asks"):
                        if not isinstance(item.get(side), list) or len(item[side]) != 3:
                            return None
                        for level in item[side]:
                            _number(level.get("price"))
                            _number(level.get("volume"))
                    item["bids"] = [PriceLevel(**level) for level in item["bids"]]
                    item["asks"] = [PriceLevel(**level) for level in item["asks"]]
                    quotes.append(LiveQuote(**item))
                result = BoardSnapshot(quotes=quotes, **data)
            except (ValueError, KeyError, TypeError, AttributeError):
                return None
        if result is None:
            return None
        # An empty failure has no successful receive time. Its private save time
        # bounds cache lifetime without inventing a fetched_at/source timestamp.
        anchor = _moment(result.fetched_at or saved_at)
        if anchor is None or not 0 <= (now - anchor).total_seconds() < 7 * 86400:
            return None
        try:
            quotes = [replace(q, stale=q.stale or _old(q.source_timestamp, now),
                              depth_stale=q.depth_stale or _old(q.depth_timestamp, now)) for q in result.quotes]
        except (TypeError, ValueError):
            return None
        return replace(result, quotes=quotes, from_cache=True,
                       stale=result.stale or any(q.stale for q in quotes), poll_seconds=self.poll_seconds)

    def _read_state(self, key: str, db=None) -> _PollState:
        if db is None:
            return self._poll_memory.get(key, _PollState())
        row = db.execute("""SELECT attempted_at,next_poll_at,failure_count,hard_until,
            lease_until,claim_id,last_error FROM board_poll_state
            WHERE workspace=? AND symbols=?""", (self.store.workspace, key)).fetchone()
        return _PollState(**dict(row)) if row else _PollState()

    def _write_state(self, key: str, state: _PollState, db=None) -> None:
        if db is None:
            self._poll_memory[key] = state
            if len(self._poll_memory) > 40:
                now = self.clock()
                newest = set(sorted(self._poll_memory, key=lambda item:
                             self._poll_memory[item].attempted_at or "", reverse=True)[:40])
                for item, previous in list(self._poll_memory.items()):
                    protected = any(moment and moment > now for moment in
                                    (_moment(previous.lease_until), _moment(previous.hard_until),
                                     _moment(previous.next_poll_at)))
                    if item not in newest and not protected:
                        del self._poll_memory[item]
            return
        db.execute("""INSERT OR REPLACE INTO board_poll_state
            (workspace,symbols,attempted_at,next_poll_at,failure_count,hard_until,
             lease_until,claim_id,last_error) VALUES (?,?,?,?,?,?,?,?,?)""",
                   (self.store.workspace, key, state.attempted_at, state.next_poll_at,
                    state.failure_count, state.hard_until, state.lease_until,
                    state.claim_id, state.last_error))
        cutoff = self.clock().isoformat()
        # Preserve active requests/cooldowns even when watchlist combinations
        # churn; only abandoned, eligible state is removed beyond the latest 40.
        db.execute("""DELETE FROM board_poll_state WHERE workspace=?
            AND (lease_until IS NULL OR lease_until<=?)
            AND (hard_until IS NULL OR hard_until<=?)
            AND (next_poll_at IS NULL OR next_poll_at<=?)
            AND symbols NOT IN (SELECT symbols FROM board_poll_state
                WHERE workspace=? ORDER BY attempted_at DESC,rowid DESC LIMIT 40)""",
                   (self.store.workspace, cutoff, cutoff, cutoff, self.store.workspace))

    def _claim_in(self, key: str, now: datetime, force: bool, db=None):
        state = self._read_state(key, db)
        # A manual refresh never duplicates an in-flight request or bypasses a
        # provider's explicit cooldown. It may retry ordinary transient failures.
        if any(moment and moment > now for moment in
               (_moment(state.lease_until), _moment(state.hard_until))):
            return None, state
        attempted = _moment(state.attempted_at)
        due = _moment(state.next_poll_at)
        selected_due = attempted + timedelta(seconds=self.poll_seconds) if attempted else None
        if not force and any(moment and moment > now for moment in (due, selected_due)):
            return None, state
        claim_id = uuid4().hex
        state = replace(state, attempted_at=now.isoformat(),
                        next_poll_at=(now + timedelta(seconds=self.poll_seconds)).isoformat(),
                        lease_until=(now + timedelta(seconds=max(30, self.timeout * 3))).isoformat(),
                        claim_id=claim_id)
        self._write_state(key, state, db)
        return claim_id, state

    def _claim(self, key: str, now: datetime, force: bool):
        if not self.store:
            return self._claim_in(key, now, force)
        with self.store.connection() as db:
            # The claim is committed before HTTP starts. Other service instances
            # see it without holding SQLite's write lock throughout the request.
            db.execute("BEGIN IMMEDIATE")
            return self._claim_in(key, now, force, db)

    def _complete_in(self, key: str, claim_id: str, snapshot: BoardSnapshot,
                     now: datetime, failed: bool, hard_seconds: float, db=None) -> bool:
        state = self._read_state(key, db)
        if state.claim_id != claim_id:
            return False
        failures = min(30, state.failure_count + 1) if failed else 0
        backoff = min(30, 10 * (2 ** (failures - 1))) if failed else 0
        delay = max(self.poll_seconds, backoff)
        started = _moment(state.attempted_at) or now
        hard_until = now + timedelta(seconds=hard_seconds) if hard_seconds else None
        due = max(started + timedelta(seconds=delay), hard_until or started)
        state = replace(state, next_poll_at=due.isoformat(), failure_count=failures,
                        hard_until=hard_until.isoformat() if hard_until else None,
                        lease_until=None, claim_id=None,
                        last_error=snapshot.errors[0] if failed and snapshot.errors else None)
        self._save(key, snapshot, now, db)
        self._write_state(key, state, db)
        return True

    def _complete(self, key: str, claim_id: str, snapshot: BoardSnapshot,
                  now: datetime, *, failed=False, hard_seconds=0) -> bool:
        if not self.store:
            return self._complete_in(key, claim_id, snapshot, now, failed, hard_seconds)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._complete_in(key, claim_id, snapshot, now, failed, hard_seconds, db)

    def _finish(self, key: str, claim_id: str, snapshot: BoardSnapshot,
                now: datetime, symbols: list[str], *, failed=False, hard_seconds=0) -> BoardSnapshot:
        if self._complete(key, claim_id, snapshot, now, failed=failed, hard_seconds=hard_seconds):
            return self._ordered(snapshot, symbols)
        # An expired claim can be replaced while its HTTP request is still
        # returning. Its late response must not overwrite or surface over the
        # snapshot produced by the newer owner.
        latest = self._cached(key, self.clock())
        if latest is not None:
            return self._ordered(latest, symbols)
        return BoardSnapshot(errors=["Yêu cầu snapshot DNSE đã được thay thế; đang chờ lần tải mới."],
                             stale=True, from_cache=True, poll_seconds=self.poll_seconds)

    def cached(self, symbols) -> BoardSnapshot | None:
        """Read without polling, including failed empty snapshots when paused."""
        normalized = _symbols(symbols)
        with self._lock:
            result = self._cached(",".join(sorted(normalized)), self.clock()) if normalized else None
            return self._ordered(result, normalized) if result is not None else None

    def _ordered(self, snapshot: BoardSnapshot, symbols: list[str]) -> BoardSnapshot:
        return replace(snapshot, quotes=sorted(snapshot.quotes, key=lambda q: symbols.index(q.symbol)),
                       poll_seconds=self.poll_seconds)

    def fetch(self, symbols, force: bool = False) -> BoardSnapshot:
        normalized = _symbols(symbols)
        if not normalized:
            return BoardSnapshot(poll_seconds=self.poll_seconds)
        key = ",".join(sorted(normalized))
        with self._lock:
            now = self.clock()
            cached = self._cached(key, now)
            claim_id, state = self._claim(key, now, force)
            if claim_id is None:
                # Re-read after the atomic claim check: a concurrent poll may
                # have completed after the first cache read.
                cached = self._cached(key, self.clock()) or cached
                if cached is not None:
                    return self._ordered(cached, normalized)
                error = state.last_error or "Snapshot DNSE đang chờ cập nhật; hãy đợi nhịp tải kế tiếp."
                return BoardSnapshot(errors=[error], stale=True, from_cache=True,
                                     poll_seconds=self.poll_seconds)
            query = "{GetKrxStockInfoBySymbols(symbols:" + json.dumps(normalized) + ",board:2){si{" + INFO_FIELDS + "}} "
            query += "GetTopPriceOfSymbols(symbolList:" + json.dumps(normalized) + "){data{tp{" + DEPTH_FIELDS + "}}}}"
            try:
                with httpx.Client(timeout=self.timeout, transport=self.transport, follow_redirects=False,
                                  headers={"User-Agent": "BreakoutAI/0.7 public-market-research"}) as client:
                    with client.stream("POST", SOURCE_URL, json={"query": query}) as response:
                        response.raise_for_status()
                        payload = bytearray()
                        for chunk in response.iter_bytes():
                            payload.extend(chunk)
                            if len(payload) > MAX_RESPONSE_BYTES:
                                raise RealtimeError("Phản hồi bảng giá vượt giới hạn dung lượng.")
                        data = json.loads(payload)
                received = self.clock()
                result = self._parse(data, normalized, received)
                if not result.quotes:
                    raise RealtimeError("Nguồn không trả về mã hợp lệ cho bảng giá.")
                return self._finish(key, claim_id, result, received, normalized)
            except (httpx.HTTPError, ValueError, TypeError, KeyError, OverflowError) as exc:
                received = self.clock()
                hard_seconds = 0
                if isinstance(exc, httpx.HTTPStatusError):
                    reason = f"HTTP {exc.response.status_code}"
                    if exc.response.status_code in {403, 429}:
                        hard_seconds = _retry_after(exc.response, received)
                elif isinstance(exc, RealtimeError):
                    reason = str(exc)
                else:
                    reason = "kết nối hoặc dữ liệu nguồn không hợp lệ"
                error = f"Không cập nhật được snapshot DNSE: {reason}."
                if cached:
                    fallback = replace(cached, quotes=[replace(q, stale=True, depth_stale=True) for q in cached.quotes],
                                       errors=[error], stale=True, from_cache=True)
                else:
                    fallback = BoardSnapshot(errors=[error], fetched_at=None, stale=True,
                                             poll_seconds=self.poll_seconds)
                return self._finish(key, claim_id, fallback, received, normalized,
                                    failed=True, hard_seconds=hard_seconds)

    def _parse(self, response, symbols: list[str], now: datetime) -> BoardSnapshot:
        if not isinstance(response, dict) or not isinstance(response.get("data"), dict):
            raise RealtimeError("Nguồn trả về lỗi GraphQL hoặc thiếu dữ liệu.")
        data = response["data"]
        info_block = data.get("GetKrxStockInfoBySymbols")
        top_block = data.get("GetTopPriceOfSymbols")
        if not isinstance(info_block, dict):
            raise RealtimeError("Nguồn thiếu snapshot chứng khoán hợp lệ.")
        if top_block is not None and not isinstance(top_block, dict):
            raise RealtimeError("Nguồn trả về độ sâu mua bán không hợp lệ.")
        top_data = top_block.get("data") if top_block else None
        if top_data is not None and not isinstance(top_data, dict):
            raise RealtimeError("Nguồn trả về độ sâu mua bán không hợp lệ.")
        info = info_block.get("si")
        top = top_data.get("tp") if top_data else None
        if not isinstance(info, list) or len(info) > MAX_SYMBOLS:
            raise RealtimeError("Danh sách snapshot không hợp lệ.")
        if top is not None and (not isinstance(top, list) or len(top) > MAX_SYMBOLS):
            raise RealtimeError("Danh sách độ sâu mua bán không hợp lệ.")
        errors = []
        if response.get("errors"):
            errors.append("Nguồn trả về một phần dữ liệu; một số trường có thể chưa có.")
        if top is None:
            errors.append("Nguồn chưa trả về độ sâu mua bán.")
        depths = {}
        for row in top or []:
            if not isinstance(row, dict) or row.get("symbol") not in symbols or row["symbol"] in depths:
                raise RealtimeError("Độ sâu trả về sai mã hoặc trùng mã.")
            depths[row["symbol"]] = row
        quotes, seen = [], set()
        for row in info:
            if not isinstance(row, dict) or row.get("symbol") not in symbols or row["symbol"] in seen:
                raise RealtimeError("Snapshot trả về sai mã hoặc trùng mã.")
            symbol = row["symbol"]
            seen.add(symbol)
            depth = depths.get(symbol)
            try:
                # Keep valid price data when an independent depth payload is bad.
                try:
                    quote = _quote(row, depth, now)
                except RealtimeError:
                    if depth is None:
                        raise
                    quote = _quote(row, None, now)
                    errors.append(f"{symbol}: độ sâu mua bán chưa hợp lệ.")
                quotes.append(quote)
            except RealtimeError:
                errors.append(f"{symbol}: dữ liệu giá không hợp lệ, đã bỏ qua.")
        missing = [symbol for symbol in symbols if symbol not in {q.symbol for q in quotes}]
        if missing:
            errors.append("Chưa có snapshot hợp lệ: " + ", ".join(missing) + ".")
        quotes.sort(key=lambda q: symbols.index(q.symbol))
        return BoardSnapshot(quotes=quotes, errors=errors, fetched_at=now.isoformat(),
                             stale=any(q.stale for q in quotes), poll_seconds=self.poll_seconds)
