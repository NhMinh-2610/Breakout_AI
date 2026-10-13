"""Transparent technical screening, not a trained prediction model."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
import math
from statistics import stdev

from breakout_ai.market import MarketSnapshot


@dataclass(frozen=True)
class Criteria:
    volatility_cap: float = 35
    drawdown_cap: float = 15
    min_score: int = 80

    def __post_init__(self):
        if not 1 <= self.volatility_cap <= 200 or not 1 <= self.drawdown_cap <= 90 or self.min_score not in {20, 40, 60, 80, 100}:
            raise ValueError("Ngưỡng biến động/sụt giảm không hợp lệ.")


def indicators(snapshot: MarketSnapshot) -> dict:
    if len(snapshot.bars) < 61:
        raise ValueError("Cần ít nhất 61 phiên để tính tiêu chí 60 phiên.")
    adjusted = all(bar.adjusted_close is not None for bar in snapshot.bars)
    prices = [bar.adjusted_close if adjusted else bar.close for bar in snapshot.bars]
    if any(not math.isfinite(price) or price <= 0 for price in prices):
        raise ValueError("Chuỗi giá có giá trị không hợp lệ.")
    recent = prices[-21:]
    returns = [math.log(b) - math.log(a) for a, b in zip(recent, recent[1:])]
    peak, worst = prices[-60], 0.0
    for price in prices[-60:]:
        peak = max(peak, price)
        worst = min(worst, price / peak - 1)
    result = {
        "sma20": sum(price / 20 for price in prices[-20:]),
        "sma60": sum(price / 60 for price in prices[-60:]),
        "momentum20_pct": (prices[-1] / prices[-21] - 1) * 100,
        "momentum60_pct": (prices[-1] / prices[-61] - 1) * 100,
        "volatility20_pct": stdev(returns) * math.sqrt(252) * 100,
        "max_drawdown60_pct": worst * 100,
        "analysis_price": prices[-1],
        "analysis_basis": "adjusted-by-provider" if adjusted else snapshot.price_basis,
    }
    if any(isinstance(value, (int, float)) and not math.isfinite(value) for value in result.values()):
        raise ValueError("Chuỗi giá vượt phạm vi tính chỉ báo.")
    return result


def rank_candidates(snapshots: list[MarketSnapshot], criteria: Criteria | None = None) -> list[dict]:
    criteria = criteria or Criteria()
    result = []
    today = datetime.now(timezone.utc).date()
    for snapshot in snapshots:
        row = {**snapshot.summary(), "score": None, "eligible": False, "meets_screen": False, "min_score": criteria.min_score, "reasons": [], "risks": []}
        age = (today - date.fromisoformat(snapshot.latest.date)).days
        if snapshot.cache_stale or age < 0 or age > 7 or snapshot.latest.volume <= 0:
            row["risks"].append("Dữ liệu cũ, tải lại thất bại hoặc không có khối lượng: loại khỏi xếp hạng.")
            result.append(row)
            continue
        try:
            stats = indicators(snapshot)
        except ValueError as exc:
            row["risks"].append(str(exc))
            result.append(row)
            continue
        checks = [
            (stats["analysis_price"] > stats["sma20"], "Giá phân tích trên SMA20", "Giá phân tích chưa trên SMA20"),
            (stats["analysis_price"] > stats["sma60"], "Giá phân tích trên SMA60", "Giá phân tích chưa trên SMA60"),
            (stats["momentum60_pct"] > 0, "Động lượng 60 phiên dương", "Động lượng 60 phiên không dương"),
            (stats["volatility20_pct"] <= criteria.volatility_cap, f"Biến động 20 phiên ≤ {criteria.volatility_cap:g}%/năm", f"Biến động vượt {criteria.volatility_cap:g}%/năm"),
            (stats["max_drawdown60_pct"] >= -criteria.drawdown_cap, f"Sụt giảm 60 phiên trong ngưỡng {criteria.drawdown_cap:g}%", f"Sụt giảm vượt {criteria.drawdown_cap:g}%"),
        ]
        row.update(stats)
        row.update(score=sum(20 for passed, _, _ in checks if passed), eligible=True)
        row["meets_screen"] = row["score"] >= criteria.min_score
        for passed, reason, risk in checks:
            row["reasons" if passed else "risks"].append(reason if passed else risk)
        if stats["analysis_basis"] != "adjusted-by-provider":
            row["risks"].append("Chưa xác minh điều chỉnh chia tách/cổ tức của chuỗi giá; biến động có thể chịu ảnh hưởng quyền.")
        row["risks"].append("Chưa đánh giá lợi nhuận, nợ, định giá, tin tức hoặc tính phù hợp với tài chính cá nhân.")
        result.append(row)
    return sorted(result, key=lambda row: (row["eligible"], row["score"] if row["score"] is not None else -1), reverse=True)


def render_candidates(rows: list[dict]) -> str:
    lines = ["### Các mã đáng nghiên cứu theo tiêu chí đang dùng", "", "Điểm 0–100 là số tiêu chí kỹ thuật đạt được (20 điểm/tiêu chí), không phải xác suất có lãi hoặc kết luận cổ phiếu rẻ."]
    if rows and not any(row["meets_screen"] for row in rows):
        lines += ["", f"**Chưa có mã đạt ngưỡng {rows[0]['min_score']}/100 trong danh sách.** Bộ lọc không buộc phải chọn một mã để mua."]
    # Rank within each market and data date, avoiding a misleading combined leaderboard.
    groups = sorted({(row["market"], row["as_of"]) for row in rows})
    for market, as_of in groups:
        lines += ["", f"**{market} · dữ liệu ngày {as_of}**"]
        for row in [r for r in rows if (r["market"], r["as_of"]) == (market, as_of)]:
            score = f"{row['score']}/100" if row["eligible"] else "chưa đủ dữ liệu để xếp hạng"
            lines.append(f"- **{row['symbol']} — {score}**; giá ngày {row['close']:,.2f} {row['currency']}.")
            if row["eligible"]:
                lines.append("  - " + ("Đạt ngưỡng để ưu tiên nghiên cứu." if row["meets_screen"] else "Chưa đạt ngưỡng ưu tiên của bộ lọc."))
            if row["reasons"]:
                lines.append("  - Điểm hỗ trợ: " + "; ".join(row["reasons"]) + ".")
            lines.append("  - Cần kiểm tra: " + "; ".join(row["risks"]) + ".")
    lines += ["", "Chỉ xem xét các mã trong danh sách đã yêu cầu. Trước khi cân nhắc mua, cần kiểm tra báo cáo, định giá và rủi ro riêng; công thức này chưa được backtest hoặc hiệu chỉnh dự báo."]
    return "\n".join(lines)
