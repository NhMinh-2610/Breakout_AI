"""Capture one canonical, auditable chart observation for UI, scanning and AI.

The observer reads the OHLCV data behind a chart. Structural descriptions add
context to the existing technical rules; they never create another trade rule.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import datetime, timedelta, timezone
import math

from breakout_ai.intraday import IntradaySnapshot
from breakout_ai.realtime import LiveQuote
from breakout_ai.technical import MAX_BARS, MIN_BARS, SignalReport, analyze


MAX_CONTEXT_CANDLES = 60
RESOLUTIONS = {"1", "5", "15"}
QUOTE_FIELDS = {
    "symbol",
    "exchange",
    "reference",
    "ceiling",
    "floor",
    "last",
    "change",
    "change_pct",
    "match_volume",
    "total_volume",
    "total_value",
    "open",
    "high",
    "low",
    "average",
    "foreign_buy_volume",
    "foreign_sell_volume",
    "bids",
    "asks",
    "source_timestamp",
    "received_at",
    "stale",
    "depth_timestamp",
    "depth_stale",
    "market",
    "currency",
    "source",
    "source_url",
    "trading_session",
}


@dataclass(frozen=True)
class ChartObservation:
    symbol: str
    report: SignalReport
    chart: dict
    quote: dict
    owned: bool
    captured_at: str

    def context(self) -> dict:
        """Return a detached JSON-safe snapshot, never a view of mutable inputs."""
        return {
            "analysis": self.report.payload(),
            "quote": deepcopy(self.quote),
            "chart": deepcopy(self.chart),
            "owned": self.owned,
            "captured_at": self.captured_at,
        }


def _mapping(value) -> dict:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return dict(value) if isinstance(value, dict) else {}


def _number(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    if not math.isfinite(parsed) or abs(parsed) > 1e20:
        return None
    return parsed if not positive or parsed > 0 else None


def _moment(value):
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if moment.tzinfo is None or moment.utcoffset() is None:
        return None
    return moment.astimezone(timezone.utc)


def _json_safe(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {
            key: _json_safe(item) for key, item in value.items() if isinstance(key, str)
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return None


def _completed(candles, resolution, now):
    if not isinstance(candles, (list, tuple)) or len(candles) > MAX_BARS:
        return []
    result = []
    for candle in candles:
        row = _mapping(candle)
        moment = _moment(row.get("time"))
        if (
            moment is None
            or moment + timedelta(minutes=resolution) > now
            or row.get("complete", True) is False
            or row.get("interval_minutes", resolution) != resolution
        ):
            continue
        values = {
            key: _number(row.get(key), positive=True)
            for key in ("open", "high", "low", "close")
        }
        if (
            any(value is None for value in values.values())
            or not values["low"]
            <= min(values["open"], values["close"])
            <= max(values["open"], values["close"])
            <= values["high"]
        ):
            continue
        volume = _number(row.get("volume"))
        if volume is not None and volume < 0:
            volume = None
        result.append(
            dict(
                values,
                time=moment.isoformat(),
                volume=volume,
                interval_minutes=resolution,
                complete=True,
            )
        )
    return sorted(result, key=lambda item: item["time"])


def _fact(identifier, label, text, *, role="observation", **values):
    return {
        "id": identifier,
        "label": label,
        "text": text,
        "role": role,
        "values": _json_safe(values),
    }


def _facts(report, rows):
    indicators, levels = report.indicators, report.levels
    sma = indicators.get("sma20")
    close = indicators.get("latest_close")
    facts = []
    if sma is not None and close is not None:
        relation = "trên" if close > sma else "dưới" if close < sma else "bằng"
        text = f"Nến đã đóng {close:,.0f} VND nằm {relation} SMA20 {sma:,.0f} VND."
    else:
        text = "Chưa đủ nến hợp lệ để mô tả vị trí giá so với SMA20."
    facts.append(
        _fact(
            "trend.sma20",
            "Giá và đường trung bình",
            text,
            latest_close=close,
            sma20=sma,
        )
    )
    rsi = indicators.get("rsi14")
    previous_rsi = indicators.get("rsi14_previous")
    if rsi is None:
        text = "Chưa có RSI14 từ chuỗi nến đã đóng."
    elif rsi < 30:
        text = f"RSI14 {rsi:.1f} dưới 30; động lượng giảm mạnh, chưa xác nhận tạo đáy."
    elif rsi > 70:
        text = (
            f"RSI14 {rsi:.1f} trên 70; động lượng tăng mạnh, chưa tự tạo điều kiện bán."
        )
    else:
        text = f"RSI14 {rsi:.1f} nằm giữa hai ngưỡng quan sát 30 và 70."
    facts.append(
        _fact(
            "momentum.rsi14",
            "Động lượng RSI14",
            text,
            role=(
                "risk" if rsi is not None and (rsi < 30 or rsi > 70) else "observation"
            ),
            rsi14=rsi,
            previous=previous_rsi,
            lower_threshold=30,
            upper_threshold=70,
        )
    )
    ratio = indicators.get("relative_volume")
    text = (
        f"Khối lượng nến đã đóng bằng {ratio:.2f} lần bình quân 20 nến trước."
        if ratio is not None
        else "Chưa có khối lượng tương đối đủ điều kiện."
    )
    facts.append(
        _fact(
            "volume.relative",
            "Xác nhận bằng khối lượng",
            text,
            relative_volume=ratio,
            comparison_bars=20,
        )
    )
    for key, label in (("support", "Vùng hỗ trợ"), ("resistance", "Vùng kháng cự")):
        value = levels.get(key)
        text = (
            f"{label} {value:,.0f} VND từ 20 nến trước, không gồm nến đánh giá."
            if value is not None
            else f"Chưa xác định {label.lower()} từ dữ liệu hợp lệ."
        )
        facts.append(
            _fact("level." + key, label, text, price=value, comparison_bars=20)
        )
    if len(rows) >= 10:
        before, recent = rows[-10:-5], rows[-5:]
        old_high, old_low = max(row["high"] for row in before), min(
            row["low"] for row in before
        )
        high, low = max(row["high"] for row in recent), min(
            row["low"] for row in recent
        )
        structure = (
            "higher"
            if high > old_high and low > old_low
            else "lower" if high < old_high and low < old_low else "mixed"
        )
        description = {
            "higher": "Đỉnh và đáy cao hơn",
            "lower": "Đỉnh và đáy thấp hơn",
            "mixed": "Đỉnh và đáy chưa cùng hướng",
        }[structure]
        facts.append(
            _fact(
                "structure.recent",
                "Cấu trúc giá gần nhất",
                description
                + " khi so nhóm 5 nến mới nhất với nhóm 5 nến liền trước; đây là mô tả cửa sổ quan sát.",
                structure=structure,
                window_bars=5,
                recent_high=high,
                recent_low=low,
                previous_high=old_high,
                previous_low=old_low,
            )
        )
    else:
        facts.append(
            _fact(
                "structure.recent",
                "Cấu trúc giá gần nhất",
                "Cần 10 nến đã đóng để so hai nhóm 5 nến không chồng lấn.",
                structure=None,
                required_bars=10,
            )
        )
    if len(rows) >= 21:
        prior = rows[-21:-1]
        high, low = max(row["high"] for row in prior), min(row["low"] for row in prior)
        width = (high / low - 1) * 100
        facts.append(
            _fact(
                "structure.range20",
                "Vùng dao động trước nến xác nhận",
                f"Biên độ 20 nến trước là {width:.2f}%; riêng độ rộng này chưa xác nhận tích lũy hoặc phá vỡ.",
                high=high,
                low=low,
                width_pct=width,
                comparison_bars=20,
            )
        )
    if rows:
        latest = rows[-1]
        span = latest["high"] - latest["low"]
        body = abs(latest["close"] - latest["open"])
        upper = latest["high"] - max(latest["open"], latest["close"])
        lower = min(latest["open"], latest["close"]) - latest["low"]
        body_pct, upper_pct, lower_pct, position = (
            (
                100 * body / span,
                100 * upper / span,
                100 * lower / span,
                100 * (latest["close"] - latest["low"]) / span,
            )
            if span
            else (None, None, None, None)
        )
        text = (
            f"Nến đã đóng gần nhất có thân {body_pct:.1f}% biên độ; giá đóng ở {position:.1f}% tính từ đáy nến."
            if span
            else "Nến đã đóng gần nhất không có biên độ; chưa có tỷ lệ thân/bóng nến."
        )
        facts.append(
            _fact(
                "candle.latest",
                "Thân và bóng nến gần nhất",
                text,
                time=latest["time"],
                open=latest["open"],
                high=latest["high"],
                low=latest["low"],
                close=latest["close"],
                body_pct=body_pct,
                upper_wick_pct=upper_pct,
                lower_wick_pct=lower_pct,
                close_position_pct=position,
            )
        )
    else:
        facts.append(
            _fact(
                "candle.latest",
                "Thân và bóng nến gần nhất",
                "Chưa có nến đã đóng hợp lệ để quan sát.",
            )
        )
    facts.append(
        _fact(
            "data.readiness",
            "Điều kiện dữ liệu",
            (
                "Dữ liệu đủ điều kiện kiểm tra quy tắc hiện tại."
                if not report.blockers
                else " ".join(report.blockers)
            ),
            role="blocker" if report.blockers else "observation",
            ready=not report.blockers,
            completed_bars=len(rows),
            required_bars=MIN_BARS,
        )
    )
    return facts


def _scenarios(report):
    blocked = bool(report.blockers)
    checks = [
        ("Đạt: " if passed else "Chờ: ") + label
        for label, passed in report.condition_checks.items()
    ]
    if not checks:
        checks = list(report.blockers) or ["Chờ mẫu hình có đầy đủ xác nhận."]
    invalidation = report.levels.get("invalidation")
    result = [
        {
            "id": "setup.current",
            "label": report.title,
            "action": report.action,
            "confirmation": "; ".join(checks),
            "invalidation": (
                f"Luận điểm mất hiệu lực quanh {invalidation:,.0f} VND theo quy tắc đang dùng."
                if invalidation is not None
                else "Chưa có mức vô hiệu của một tín hiệu được xác nhận."
            ),
            "status": (
                "blocked"
                if blocked
                else (
                    "qualified"
                    if report.action in {"watch_buy", "watch_sell"}
                    else "watch"
                )
            ),
            "evidence_ids": [
                "trend.sma20",
                "momentum.rsi14",
                "volume.relative",
                "level.support",
                "level.resistance",
                "data.readiness",
            ],
            "values": {"invalidation": invalidation},
        }
    ]
    support = report.levels.get("support")
    result.append(
        {
            "id": "risk.support",
            "label": "Rủi ro mất vùng hỗ trợ",
            "confirmation": (
                f"Theo dõi phản ứng giá tại hỗ trợ {support:,.0f} VND và khối lượng xác nhận."
                if support is not None
                else "Cần đủ nến để xác định vùng hỗ trợ trước."
            ),
            "invalidation": "Kịch bản rủi ro cần đánh giá lại nếu giá lấy lại vùng hỗ trợ; không tự tạo lệnh bán.",
            "status": (
                "blocked"
                if blocked or support is None
                else "qualified" if report.action == "watch_sell" else "watch"
            ),
            "evidence_ids": ["level.support", "volume.relative", "data.readiness"],
            "values": {"support": support},
        }
    )
    return result


def observe_chart(
    symbol: str,
    chart: IntradaySnapshot,
    quote: LiveQuote | None,
    *,
    owned=False,
    resolution="5",
    now=None,
) -> ChartObservation:
    """Build one observation and preserve the technical engine's trade authority."""
    if not isinstance(resolution, str) or resolution not in RESOLUTIONS:
        raise ValueError("Khung nến hỗ trợ: 1, 5 hoặc 15 phút.")
    captured = _moment(now) if now is not None else datetime.now(timezone.utc)
    if captured is None:
        raise ValueError("Thời điểm quan sát cần có múi giờ.")
    symbol = str(symbol).strip().upper()
    source, quote_data = _mapping(chart), _mapping(quote)
    raw_candles = source.get("candles", [])
    identity_errors = []
    if source.get("symbol") != symbol:
        identity_errors.append("Nguồn nến không đúng mã đang phân tích.")
    if source.get("asset_type") != "equity" or source.get("price_unit") != "VND":
        identity_errors.append(
            "Không áp dụng quy tắc cổ phiếu VND cho dữ liệu chỉ số hoặc đơn vị khác."
        )
    if source.get("resolution") != resolution:
        identity_errors.append("Khung nến nguồn không trùng khung đang phân tích.")
    if (
        quote_data.get("currency", "VND") != "VND"
        or quote_data.get("market", "VN") != "VN"
    ):
        identity_errors.append("Snapshot giá không thuộc cổ phiếu Việt Nam đơn vị VND.")
    safe_candles = [] if identity_errors else raw_candles
    safe_quote = None if identity_errors else quote
    report = analyze(
        symbol,
        safe_candles,
        safe_quote,
        owned=bool(owned),
        now=captured,
        resolution_minutes=int(resolution),
    )
    extra = list(identity_errors)
    if source.get("stale", True) or source.get("errors"):
        extra.append("Nguồn nến đang cũ hoặc lần cập nhật chưa thành công.")
    source_errors = source.get("errors", [])
    if isinstance(source_errors, (list, tuple)):
        extra.extend(str(error) for error in source_errors)
    if extra:
        blockers = list(dict.fromkeys(report.blockers + extra))
        report = replace(
            report,
            action="wait",
            title="Chờ dữ liệu biểu đồ hợp lệ",
            summary=extra[0],
            blockers=blockers,
            signal_strength="Tạm dừng tín hiệu · dữ liệu chưa sẵn sàng",
        )
    rows = _completed(safe_candles, int(resolution), captured)
    chart_data = {
        "symbol": symbol,
        "resolution": resolution,
        "source_symbol": source.get("symbol"),
        "source_resolution": source.get("resolution"),
        "source_url": source.get("source_url"),
        "fetched_at": source.get("fetched_at"),
        "as_of": report.as_of,
        "currency": "VND",
        "price_unit": source.get("price_unit"),
        "asset_type": source.get("asset_type"),
        "candles": rows[-MAX_CONTEXT_CANDLES:],
        "facts": _facts(report, rows),
        "scenarios": _scenarios(report),
    }
    public_quote = {
        key: value for key, value in quote_data.items() if key in QUOTE_FIELDS
    }
    return ChartObservation(
        symbol,
        report,
        _json_safe(chart_data),
        _json_safe(public_quote),
        bool(owned),
        captured.isoformat(),
    )
