"""Transparent intraday observations; no forecasts, probabilities or orders.

All prices are full VND and volumes individual shares. Rules use only completed
bars; support/resistance and comparison volume exclude the decision bar.
"""
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timedelta, timezone
import math


VN_TIME = timezone(timedelta(hours=7))
MIN_BARS = 30
QUOTE_MAX_AGE_SECONDS = 180
MAX_BARS = 10_000


@dataclass(frozen=True)
class SignalReport:
    symbol: str
    action: str = "wait"
    title: str = "Chờ dữ liệu mới"
    summary: str = "Chưa có đủ dữ liệu để đánh giá."
    evidence: list[str] = field(default_factory=list)
    levels: dict = field(default_factory=dict)
    indicators: dict = field(default_factory=dict)
    as_of: str | None = None
    blockers: list[str] = field(default_factory=list)
    signal_strength: str = "0/0 điều kiện quan sát"
    timeframe: str = "Nến 5 phút"
    condition_checks: dict[str, bool] = field(default_factory=dict)

    def payload(self) -> dict:
        return asdict(self)


def _mapping(value) -> dict:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return dict(value) if isinstance(value, dict) else {}


def _number(value, *, positive=False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0 or number > 1e20:
        return None
    return number if not positive or number > 0 else None


def _moment(value) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(timezone.utc)


def rsi_wilder(closes: list[float], period=14) -> list[float | None]:
    """RSI seeded with period simple gains/losses, then Wilder smoothing.

    A flat series is 50 by explicit convention (neither gains nor losses).
    Invalid input yields unavailable values instead of a numeric substitute.
    """
    if isinstance(period, bool) or not isinstance(period, int) or period < 1:
        raise ValueError("RSI period must be a positive integer.")
    values = [_number(value, positive=True) for value in closes]
    result = [None] * len(values)
    if len(values) <= period or any(value is None for value in values):
        return result
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gain = sum(max(change, 0.0) for change in changes[:period]) / period
    loss = sum(max(-change, 0.0) for change in changes[:period]) / period
    def current():
        if gain == 0 and loss == 0:
            return 50.0
        if loss == 0:
            return 100.0
        return 100 - 100 / (1 + gain / loss)
    result[period] = current()
    for index in range(period + 1, len(values)):
        change = changes[index - 1]
        gain = (gain * (period - 1) + max(change, 0.0)) / period
        loss = (loss * (period - 1) + max(-change, 0.0)) / period
        result[index] = current()
    return result


def _book(quote: dict, now: datetime) -> tuple[dict, str | None]:
    depth_time = _moment(quote.get("depth_timestamp"))
    if (quote.get("depth_stale", True) or depth_time is None
            or not -30 <= (now - depth_time).total_seconds() <= QUOTE_MAX_AGE_SECONDS):
        return {}, "Sổ lệnh thiếu hoặc cũ; không dùng để đánh giá cung cầu hiện tại."
    totals = []
    for side in ("bids", "asks"):
        levels = quote.get(side)
        if not isinstance(levels, (list, tuple)) or len(levels) < 3:
            return {}, "Chưa đủ ba mức dư mua và dư bán để so sánh cung cầu."
        volumes = []
        for level in levels[:3]:
            row = _mapping(level)
            price = _number(row.get("price"), positive=True)
            volume = _number(row.get("volume"))
            if price is None or volume is None:
                return {}, "Ba mức dư mua/bán có giá hoặc khối lượng chưa xác định."
            volumes.append(volume)
        totals.append(sum(volumes))
    bid, ask = totals
    if bid + ask <= 0:
        return {}, "Dư mua và dư bán bằng 0; chưa có tỷ lệ cung cầu."
    return {
        "bid_volume": bid, "ask_volume": ask,
        "book_imbalance": (bid - ask) / (bid + ask),
        "bid_share_pct": 100 * bid / (bid + ask),
    }, (
        f"Ba mức giá: dư mua {bid:,.0f} cp, dư bán {ask:,.0f} cp "
        f"(tỷ trọng mua {100 * bid / (bid + ask):.1f}%). "
        "Đây là lệnh chờ có thể sửa/hủy, không phải lượng mua bán đã khớp."
    )


def analyze(symbol, candles, quote, *, owned=False, now=None, resolution_minutes=5) -> SignalReport:
    """Observe completed intraday candles plus a separately timestamped quote.

    Only full, fresh inputs can qualify a watch_buy/watch_sell observation.
    'owned' solely gates sell observations; no allocation or execution occurs.
    """
    clock = _moment(now) if now is not None else datetime.now(timezone.utc)
    if clock is None:
        raise ValueError("now must include a timezone.")
    if (isinstance(resolution_minutes, bool) or not isinstance(resolution_minutes, int)
            or resolution_minutes not in (1, 5, 15)):
        raise ValueError("Supported intraday resolutions: 1, 5, 15 minutes.")
    symbol = str(symbol).strip().upper()
    timeframe = f"Nến {resolution_minutes} phút"
    blockers, evidence = [], []
    interval = timedelta(minutes=resolution_minutes)
    rows = []
    if not isinstance(candles, (list, tuple)) or len(candles) > MAX_BARS:
        blockers.append("Danh sách nến không hợp lệ hoặc vượt giới hạn.")
        candles = []
    for candle in candles:
        row = _mapping(candle)
        moment = _moment(row.get("time"))
        if moment is None:
            blockers.append("Có nến thiếu thời gian nguồn kèm múi giờ.")
            continue
        if moment > clock:
            blockers.append("Có nến mang thời gian tương lai.")
            continue
        if row.get("interval_minutes", resolution_minutes) != resolution_minutes:
            blockers.append("Khung thời gian nến không đồng nhất.")
            continue
        # The source timestamps the beginning of the bar. An in-progress bar
        # must never create a completed-bar confirmation, even if flagged True.
        if row.get("complete", True) is False or moment + interval > clock:
            continue
        values = {name: _number(row.get(name), positive=True)
                  for name in ("open", "high", "low", "close")}
        if (any(value is None for value in values.values())
                or values["low"] > min(values["open"], values["close"])
                or values["high"] < max(values["open"], values["close"])
                or values["low"] > values["high"]):
            blockers.append("Có nến OHLC không hợp lệ; không tính tín hiệu từ chuỗi lỗi.")
            continue
        rows.append(dict(values, time=moment, volume=_number(row.get("volume"))))
    rows.sort(key=lambda row: row["time"])
    if any(rows[index]["time"] == rows[index - 1]["time"] for index in range(1, len(rows))):
        blockers.append("Chuỗi nến có thời gian trùng lặp.")
    # Multiples allow lunch breaks and overnight gaps, but reject mixed bars.
    if any((rows[index]["time"] - rows[index - 1]["time"]).total_seconds()
           % interval.total_seconds() != 0 for index in range(1, len(rows))):
        blockers.append("Khoảng cách nến không khớp khung thời gian đã chọn.")
    if len(rows) < MIN_BARS:
        blockers.append(f"Cần ít nhất {MIN_BARS} nến đã đóng; hiện có {len(rows)}.")

    quote = _mapping(quote)
    quote_time = _moment(quote.get("source_timestamp"))
    last = _number(quote.get("last"), positive=True)
    if not isinstance(quote.get("symbol"), str) or quote["symbol"].strip().upper() != symbol:
        blockers.append("Snapshot giá không đúng mã đang phân tích.")
    if (quote.get("stale", True) or quote_time is None
            or not -30 <= (clock - quote_time).total_seconds() <= QUOTE_MAX_AGE_SECONDS):
        blockers.append("Snapshot khớp lệnh quá 180 giây hoặc thiếu giờ nguồn.")
    if last is None:
        blockers.append("Chưa có giá khớp hợp lệ để xác nhận quan sát.")
    as_of = (rows[-1]["time"] + interval).isoformat() if rows else None
    if rows:
        latest_end = rows[-1]["time"] + interval
        if (latest_end.astimezone(VN_TIME).date() != clock.astimezone(VN_TIME).date()
                or (clock - latest_end).total_seconds() > 2 * interval.total_seconds() + 30):
            blockers.append("Nến đã đóng gần nhất đã cũ; chỉ xem được bối cảnh lịch sử.")

    indicators = {"rsi14": None, "rsi14_previous": None, "sma20": None,
                  "relative_volume": None, "last": last,
                  "quote_timestamp": quote_time.isoformat() if quote_time else None}
    book, book_text = _book(quote, clock)
    indicators.update(book)
    if book_text:
        evidence.append(book_text)
    levels = {"support": None, "resistance": None, "invalidation": None}
    if len(rows) < MIN_BARS:
        return SignalReport(symbol=symbol, timeframe=timeframe, as_of=as_of,
                            evidence=evidence, levels=levels, indicators=indicators,
                            blockers=list(dict.fromkeys(blockers)))
    closes = [row["close"] for row in rows]
    latest = rows[-1]
    previous = rows[-21:-1]
    rsi = rsi_wilder(closes)
    sma20 = sum(closes[-20:]) / 20
    previous_sma20 = sum(closes[-21:-1]) / 20
    support = min(row["low"] for row in previous)
    resistance = max(row["high"] for row in previous)
    prior_volumes = [row["volume"] for row in previous]
    relative_volume = None
    if latest["volume"] is not None and all(volume is not None for volume in prior_volumes):
        average_volume = sum(prior_volumes) / 20
        if average_volume > 0:
            relative_volume = latest["volume"] / average_volume
    if relative_volume is None:
        blockers.append("Thiếu khối lượng hoặc bình quân 20 nến bằng 0; chưa xác nhận được dòng tiền.")
    indicators.update(rsi14=rsi[-1], rsi14_previous=rsi[-2], sma20=sma20,
                      previous_sma20=previous_sma20, relative_volume=relative_volume,
                      latest_close=latest["close"], completed_bars=len(rows),
                      candle_time=latest["time"].isoformat())
    levels.update(support=support, resistance=resistance)
    evidence[:0] = [
        f"{timeframe}: dùng {len(rows)} nến đã đóng; RSI(14) {rsi[-1]:.1f}, SMA20 {sma20:,.0f} đ.",
        f"Hỗ trợ {support:,.0f} đ / kháng cự {resistance:,.0f} đ từ 20 nến trước, loại nến đang đánh giá.",
        (f"Khối lượng nến xác nhận bằng {relative_volume:.2f} lần bình quân 20 nến trước."
         if relative_volume is not None else "Chưa có tỷ lệ khối lượng để xác nhận tín hiệu."),
    ]
    if rsi[-1] < 30:
        evidence.append("RSI dưới 30 là quá bán theo ngưỡng quy ước; giá vẫn có thể tiếp tục giảm.")
    if rsi[-1] > 70:
        evidence.append("RSI trên 70 là quá mua theo ngưỡng quy ước; không tự tạo yêu cầu bán.")

    vol_breakout = relative_volume is not None and relative_volume >= 1.5
    vol_rebound = relative_volume is not None and relative_volume >= 1.2
    patterns = [
        ("breakout", {
            "Đóng cửa vượt kháng cự 20 nến": latest["close"] > resistance,
            "Khối lượng ít nhất 1,5 lần": vol_breakout,
            "Đóng cửa trên SMA20": latest["close"] > sma20,
            "Giá khớp còn trên kháng cự": last is not None and last > resistance,
        }),
        ("rebound", {
            "Kiểm định vùng hỗ trợ ±2% và đóng lại trên hỗ trợ":
                support * .98 <= latest["low"] <= support * 1.02 and support <= latest["close"] <= support * 1.02,
            "RSI hồi từ ≤30 lên >30": rsi[-2] <= 30 < rsi[-1],
            "Nến xác nhận tăng": latest["close"] > latest["open"],
            "Khối lượng ít nhất 1,2 lần": vol_rebound,
            "Giá khớp còn trong vùng hỗ trợ +2%": last is not None and support <= last <= support * 1.02,
        }),
    ]
    if owned:
        patterns += [
            ("breakdown", {
                "Đóng cửa thủng hỗ trợ 20 nến": latest["close"] < support,
                "Khối lượng ít nhất 1,5 lần": vol_breakout,
                "Đóng cửa dưới SMA20": latest["close"] < sma20,
                "Giá khớp còn dưới hỗ trợ": last is not None and last < support,
            }),
            ("momentum_exit", {
                "RSI rời vùng ≥70 xuống <70": rsi[-2] >= 70 > rsi[-1],
                "Giá dưới SMA20 đang giảm": latest["close"] < sma20 < previous_sma20,
                "Khối lượng ít nhất 1,2 lần": vol_rebound,
                "Giá khớp còn dưới SMA20": last is not None and last < sma20,
            }),
        ]
    # Sell observations take precedence for an owned asset in conflicting data.
    qualified = [pattern for pattern in patterns if all(pattern[1].values())]
    chosen = (next((pattern for pattern in qualified if pattern[0] in ("breakdown", "momentum_exit")), None)
              or (qualified[0] if qualified else max(patterns, key=lambda item: sum(item[1].values()) / len(item[1]))))
    kind, checks = chosen
    count = sum(checks.values())
    strength = f"{count}/{len(checks)} điều kiện quan sát"
    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return SignalReport(symbol=symbol, action="wait", title="Chờ dữ liệu mới",
                            summary=blockers[0], evidence=evidence, levels=levels,
                            indicators=indicators, as_of=as_of, blockers=blockers,
                            signal_strength=strength + " · dữ liệu chưa sẵn sàng",
                            timeframe=timeframe, condition_checks=checks)
    action = "hold" if owned else "wait"
    title = "Tiếp tục quan sát" if owned else "Chưa có điểm mua được xác nhận"
    summary = "Chưa có mô hình đáp ứng đầy đủ điều kiện giá, khối lượng và snapshot hiện tại."
    if qualified:
        if kind in ("breakout", "rebound"):
            action, title = "watch_buy", "Theo dõi điểm mua"
            summary = ("Nến đã đóng vượt kháng cự kèm khối lượng tăng; snapshot hiện tại còn giữ mức vượt."
                       if kind == "breakout" else
                       "Có nhịp hồi được xác nhận quanh hỗ trợ, RSI rời vùng quá bán và khối lượng tăng.")
            levels["invalidation"] = resistance if kind == "breakout" else support * .98
        else:
            action, title = "watch_sell", "Rà soát điểm bán trong danh mục"
            summary = ("Mã đang sở hữu thủng hỗ trợ với khối lượng tăng; snapshot vẫn dưới hỗ trợ."
                       if kind == "breakdown" else
                       "RSI rời vùng quá mua, giá dưới SMA20 đang giảm và khối lượng tăng.")
            levels["invalidation"] = support if kind == "breakdown" else sma20
    evidence.append("Số điều kiện là kiểm tra quy tắc, không phải xác suất thắng hay cam kết lợi nhuận.")
    return SignalReport(symbol=symbol, action=action, title=title, summary=summary,
                        evidence=evidence, levels=levels, indicators=indicators,
                        as_of=as_of, blockers=blockers, signal_strength=strength,
                        timeframe=timeframe, condition_checks=checks)
