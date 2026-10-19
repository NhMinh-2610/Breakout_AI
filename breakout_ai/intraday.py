"""Read-only intraday OHLCV from DNSE's public chart feed.

This is a polled chart snapshot, not a tick stream. Equity prices arrive in
thousands of VND; candle volumes already count individual shares.
"""

from contextlib import contextmanager
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


SOURCE_URL = "https://api.dnse.com.vn/chart-api/v2/ohlcs"
SOURCE_NAME = "DNSE public OHLCV"
SUPPORTED_INDICES = {
    "VNINDEX": "VN-Index", "VN30": "VN30",
    "HNX": "HNX-Index", "UPCOM": "UPCoM-Index",
}
RESOLUTIONS = ("1", "5", "15")
MAX_RESPONSE_BYTES = 1_000_000
MAX_CANDLES = 2_000
WINDOW_DAYS = 7


class IntradayError(ValueError):
    pass


@dataclass(frozen=True)
class Candle:
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    interval_minutes: int = 5
    complete: bool = True


@dataclass(frozen=True)
class IntradaySnapshot:
    symbol: str
    resolution: str = "5"
    candles: list[Candle] = field(default_factory=list)
    source_url: str = SOURCE_URL
    fetched_at: str | None = None
    stale: bool = True
    errors: list[str] = field(default_factory=list)
    from_cache: bool = False
    source: str = SOURCE_NAME
    price_unit: str = "VND"
    asset_type: str = "equity"

    def payload(self) -> dict:
        return asdict(self)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _identity(symbol, resolution) -> tuple[str, str]:
    if not isinstance(symbol, str):
        raise IntradayError("Chọn một mã cổ phiếu Việt Nam.")
    symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", symbol):
        raise IntradayError("Mã cổ phiếu cần có 2–10 ký tự chữ và số.")
    if not isinstance(resolution, str) or resolution not in RESOLUTIONS:
        raise IntradayError("Khung nến hỗ trợ: 1, 5 hoặc 15 phút.")
    return symbol, resolution


def _source_url(symbol: str) -> str:
    return SOURCE_URL + "/index" if symbol in SUPPORTED_INDICES else SOURCE_URL


def _number(value, *, positive=False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise IntradayError("Nguồn trả về giá hoặc khối lượng không hợp lệ.")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise IntradayError("Nguồn trả về số không hợp lệ.") from exc
    if not math.isfinite(result) or result < 0 or result > 1e20 or (positive and result == 0):
        raise IntradayError("Nguồn trả về số ngoài giới hạn hợp lệ.")
    return result


def _moment(value: str | None) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo is not None else None
    except ValueError:
        return None


def _validate_candle(candle: Candle, now: datetime) -> Candle:
    moment = _moment(candle.time)
    if moment is None or moment > now + timedelta(seconds=30):
        raise IntradayError("Thời gian nến không hợp lệ hoặc nằm trong tương lai.")
    if isinstance(candle.interval_minutes, bool) or str(candle.interval_minutes) not in RESOLUTIONS:
        raise IntradayError("Khung thời gian nến không hợp lệ.")
    values = [_number(getattr(candle, key), positive=True) for key in ("open", "high", "low", "close")]
    open_, high, low, close = values
    if not low <= min(open_, close) <= max(open_, close) <= high:
        raise IntradayError("Khoảng giá OHLC không hợp lệ.")
    volume = _number(candle.volume) if candle.volume is not None else None
    return Candle(moment.isoformat(), open_, high, low, close, volume,
                  candle.interval_minutes,
                  moment + timedelta(minutes=candle.interval_minutes) <= now)


def _parse(payload, symbol: str, resolution: str, now: datetime) -> IntradaySnapshot:
    if not isinstance(payload, dict):
        raise IntradayError("Nguồn biểu đồ trả về sai cấu trúc.")
    fields = ("t", "o", "h", "l", "c")
    arrays = [payload.get(key) for key in fields]
    if any(not isinstance(values, list) for values in arrays):
        raise IntradayError("Nguồn chưa có dữ liệu nến hợp lệ.")
    length = len(arrays[0])
    if not 1 <= length <= MAX_CANDLES or any(len(values) != length for values in arrays):
        raise IntradayError("Số lượng nến hoặc độ dài các cột không hợp lệ.")
    volumes = payload.get("v")
    if volumes is not None and (not isinstance(volumes, list) or len(volumes) != length):
        raise IntradayError("Cột khối lượng không khớp dữ liệu nến.")
    result, seen = [], set()
    for i, epoch in enumerate(arrays[0]):
        if isinstance(epoch, bool) or not isinstance(epoch, (int, float)) or not math.isfinite(epoch):
            raise IntradayError("Nguồn trả về thời gian nến không hợp lệ.")
        if epoch != int(epoch) or epoch < 946684800:
            raise IntradayError("Nguồn trả về mốc thời gian nến không hợp lệ.")
        try:
            moment = datetime.fromtimestamp(epoch, timezone.utc)
        except (ValueError, OverflowError, OSError) as exc:
            raise IntradayError("Thời gian nến vượt giới hạn.") from exc
        if moment < now - timedelta(days=WINDOW_DAYS, minutes=15) or moment > now + timedelta(seconds=30):
            raise IntradayError("Nến nằm ngoài khoảng thời gian yêu cầu.")
        if epoch in seen:
            raise IntradayError("Nguồn trả về nến trùng thời gian.")
        seen.add(epoch)
        # Equities use thousands of VND and individual shares, unlike the
        # price-board quantity scale. Index prices already represent points.
        multiplier = 1 if symbol in SUPPORTED_INDICES else 1000
        prices = [_number(values[i], positive=True) * multiplier for values in arrays[1:]]
        volume = _number(volumes[i]) if volumes is not None and volumes[i] is not None else None
        candle = Candle(moment.isoformat(), *prices, volume, int(resolution))
        result.append(_validate_candle(candle, now))
    result.sort(key=lambda candle: candle.time)
    is_index = symbol in SUPPORTED_INDICES
    return IntradaySnapshot(symbol=symbol, resolution=resolution, candles=result,
                            source_url=_source_url(symbol),
                            fetched_at=now.isoformat(), stale=False,
                            price_unit="points" if is_index else "VND",
                            asset_type="index" if is_index else "equity")


def _retry_seconds(response: httpx.Response, now: datetime) -> float:
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


class IntradayService:
    """One-symbol reads with workspace cache, persistent throttle and cooldown."""

    def __init__(self, store: Store | None = None, *, timeout=5, transport=None,
                 cache_seconds=30, clock: Callable[[], datetime] | None = None):
        self.store = store
        self.timeout = min(8, max(1, float(timeout)))
        self.transport = transport
        self.cache_seconds = min(300, max(30, int(cache_seconds)))
        self.clock = clock or _now
        self._memory: dict[tuple[str, str], IntradaySnapshot] = {}
        self._state: dict[tuple[str, str], dict] = {}
        self._lock = RLock()
        if store:
            with store.connection() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS intraday_cache (
                    workspace TEXT NOT NULL, symbol TEXT NOT NULL, resolution TEXT NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(workspace,symbol,resolution))""")
                db.execute("""CREATE TABLE IF NOT EXISTS intraday_poll_state (
                    workspace TEXT NOT NULL, symbol TEXT NOT NULL, resolution TEXT NOT NULL,
                    attempted_at TEXT, hard_until TEXT, lease_until TEXT, claim_id TEXT,
                    PRIMARY KEY(workspace,symbol,resolution))""")

    @contextmanager
    def _transaction(self):
        if self.store:
            with self.store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                yield db
        else:
            yield None

    def _read(self, key: tuple[str, str]) -> IntradaySnapshot | None:
        if not self.store:
            return self._memory.get(key)
        with self.store.connection() as db:
            row = db.execute("""SELECT payload FROM intraday_cache
                WHERE workspace=? AND symbol=? AND resolution=?""", (self.store.workspace, *key)).fetchone()
        if not row or len(row["payload"]) > MAX_RESPONSE_BYTES:
            return None
        try:
            data = json.loads(row["payload"])
            if (data["symbol"], data["resolution"]) != key or data["source_url"] != _source_url(key[0]):
                return None
            is_index = key[0] in SUPPORTED_INDICES
            if data.get("price_unit", "VND") != ("points" if is_index else "VND"):
                return None
            if data.get("asset_type", "equity") != ("index" if is_index else "equity"):
                return None
            if not isinstance(data["candles"], list) or not 1 <= len(data["candles"]) <= MAX_CANDLES:
                return None
            data["candles"] = [_validate_candle(Candle(**row), self.clock()) for row in data["candles"]]
            if any(candle.interval_minutes != int(key[1]) for candle in data["candles"]):
                return None
            if len({c.time for c in data["candles"]}) != len(data["candles"]):
                return None
            data["candles"].sort(key=lambda candle: candle.time)
            if _moment(data["fetched_at"]) is None:
                return None
            return IntradaySnapshot(**data)
        except (KeyError, TypeError, ValueError):
            return None

    def _status(self, snapshot: IntradaySnapshot, now: datetime, *, cached=False) -> IntradaySnapshot:
        fetched = _moment(snapshot.fetched_at)
        age = (now - fetched).total_seconds() if fetched else float("inf")
        last = _moment(snapshot.candles[-1].time) if snapshot.candles else None
        source_age = (now - last).total_seconds() if last else float("inf")
        max_source_age = max(180, int(snapshot.resolution) * 120)
        candles = [replace(candle, complete=(_moment(candle.time) +
                   timedelta(minutes=candle.interval_minutes) <= now)) for candle in snapshot.candles]
        return replace(snapshot, candles=candles, from_cache=cached,
                       stale=not (-30 <= age < self.cache_seconds and -30 <= source_age <= max_source_age))

    def cached(self, symbol: str, resolution="5") -> IntradaySnapshot | None:
        """Read saved candles without requesting the provider, including when paused."""
        key = _identity(symbol, resolution)
        with self._lock:
            snapshot = self._read(key)
            return self._status(snapshot, self.clock(), cached=True) if snapshot else None

    def _read_state(self, key, db):
        if db is None:
            return self._state.get(key, {})
        row = db.execute("""SELECT attempted_at,hard_until,lease_until,claim_id
            FROM intraday_poll_state WHERE workspace=? AND symbol=? AND resolution=?""",
                         (self.store.workspace, *key)).fetchone()
        return dict(row) if row else {}

    def _write_state(self, key, state, db):
        if db is None:
            self._state[key] = state
            return
        db.execute("""INSERT OR REPLACE INTO intraday_poll_state
            (workspace,symbol,resolution,attempted_at,hard_until,lease_until,claim_id)
            VALUES (?,?,?,?,?,?,?)""", (self.store.workspace, *key, state.get("attempted_at"),
            state.get("hard_until"), state.get("lease_until"), state.get("claim_id")))

    def _claim(self, key, now, force):
        with self._transaction() as db:
            state = self._read_state(key, db)
            if any(moment and moment > now for moment in
                   (_moment(state.get("hard_until")), _moment(state.get("lease_until")))):
                return None
            attempted = _moment(state.get("attempted_at"))
            if not force and attempted and (now - attempted).total_seconds() < self.cache_seconds:
                return None
            claim = uuid4().hex
            state.update(attempted_at=now.isoformat(), claim_id=claim,
                         lease_until=(now + timedelta(seconds=max(30, self.timeout * 3))).isoformat())
            self._write_state(key, state, db)
            return claim

    def _finish(self, key, claim, now, snapshot=None, hard_seconds=0):
        with self._transaction() as db:
            state = self._read_state(key, db)
            if state.get("claim_id") != claim:
                return
            state.update(claim_id=None, lease_until=None,
                         hard_until=(now + timedelta(seconds=hard_seconds)).isoformat() if hard_seconds else None)
            self._write_state(key, state, db)
            if snapshot is None:
                return
            if db is None:
                self._memory[key] = snapshot
                # Retain a small in-memory working set without dropping active
                # request leases/cooldowns in the separate state mapping.
                if len(self._memory) > 40:
                    oldest = min(self._memory, key=lambda item: self._memory[item].fetched_at or "")
                    del self._memory[oldest]
            else:
                db.execute("""INSERT OR REPLACE INTO intraday_cache
                    (workspace,symbol,resolution,payload) VALUES (?,?,?,?)""",
                    (self.store.workspace, *key, json.dumps(asdict(snapshot))))

    @staticmethod
    def _empty(key, error):
        is_index = key[0] in SUPPORTED_INDICES
        return IntradaySnapshot(symbol=key[0], resolution=key[1],
            source_url=_source_url(key[0]), errors=[error],
            price_unit="points" if is_index else "VND",
            asset_type="index" if is_index else "equity")

    def fetch(self, symbol: str, resolution="5", *, force=False) -> IntradaySnapshot:
        key = _identity(symbol, resolution)
        with self._lock:
            now = self.clock()
            previous = self._read(key)
            fetched = _moment(previous.fetched_at) if previous else None
            if not force and fetched and 0 <= (now - fetched).total_seconds() < self.cache_seconds:
                return self._status(previous, now, cached=True)
            claim = self._claim(key, now, force)
            if claim is None:
                return (replace(self._status(previous, now, cached=True),
                                errors=["Đang chờ nhịp tải hoặc thời gian nghỉ của nguồn."])
                        if previous else self._empty(key,
                            "Đang chờ nhịp tải hoặc thời gian nghỉ của nguồn."))
            hard_seconds = 0
            try:
                with httpx.Client(timeout=self.timeout, transport=self.transport, follow_redirects=False,
                                  limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
                                  headers={"User-Agent": "BreakoutAI/0.8 read-only chart research"}) as client:
                    with client.stream("GET", _source_url(key[0]), params={
                        "symbol": key[0], "resolution": key[1],
                        "from": int((now - timedelta(days=WINDOW_DAYS)).timestamp()),
                        "to": int(now.timestamp()),
                    }) as response:
                        if response.status_code in {403, 429}:
                            hard_seconds = _retry_seconds(response, now)
                        response.raise_for_status()
                        chunks, size = [], 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > MAX_RESPONSE_BYTES:
                                raise IntradayError("Dữ liệu biểu đồ vượt giới hạn tải.")
                            chunks.append(chunk)
                        payload = json.loads(b"".join(chunks))
                received = self.clock()
                snapshot = _parse(payload, *key, received)
                self._finish(key, claim, received, snapshot)
                return self._status(snapshot, received)
            except (httpx.HTTPError, ValueError, TypeError, OverflowError):
                received = self.clock()
                self._finish(key, claim, received, hard_seconds=hard_seconds)
                error = "Chưa tải được nến DNSE; dữ liệu lưu trước đó có thể đã cũ."
                if previous:
                    return replace(self._status(previous, received, cached=True),
                                   stale=True, errors=[error])
                return self._empty(key, error)
