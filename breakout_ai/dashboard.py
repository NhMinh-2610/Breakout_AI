"""Presentation helpers for sourced daily prices and currency-specific portfolios.

Charts never fill missing trading sessions or treat a price return as account P&L.
All amounts retain their source currency; allocation never combines VND and USD.
"""

from collections import defaultdict
from datetime import date, timedelta
import math

import altair as alt

from breakout_ai.market import MarketSnapshot


PRICE_BLUE = "#79B8FF"
MA_AMBER = "#F0BC51"
PALETTE = [PRICE_BLUE, "#35D399", MA_AMBER, "#B59BFF", "#FF8B96", "#60D8E5", "#BBC7D9"]


def _positive(value) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) and parsed > 0 else None


def price_records(snapshot: MarketSnapshot, days: int = 90) -> list[dict]:
    """Return real sessions in the last ``days`` calendar days, plus a 20-session MA.

    A complete adjusted series is used only when the adapter identifies its basis.
    The MA uses earlier source bars too, even when those bars precede the window.
    """
    days = max(1, min(int(days), 730))
    valid = []
    seen = set()
    for bar in sorted(snapshot.bars, key=lambda item: item.date):
        try:
            day = date.fromisoformat(bar.date)
        except (TypeError, ValueError):
            continue
        if day in seen or _positive(bar.close) is None:
            continue
        seen.add(day)
        valid.append((day, bar))
    if not valid:
        return []
    adjusted = snapshot.price_basis == "adjusted-by-provider" and all(_positive(bar.adjusted_close) is not None for _, bar in valid)
    basis = "Giá điều chỉnh" if adjusted else "Giá đóng cửa"
    cutoff = valid[-1][0] - timedelta(days=days - 1)
    prices = [float(bar.adjusted_close if adjusted else bar.close) for _, bar in valid]
    result = []
    for index, (day, bar) in enumerate(valid):
        if day < cutoff:
            continue
        volume = float(bar.volume) if isinstance(bar.volume, (int, float)) and math.isfinite(bar.volume) and bar.volume >= 0 else None
        result.append({
            "date": day.isoformat(), "price": prices[index], "raw_close": float(bar.close),
            "ma20": sum(prices[index - 19:index + 1]) / 20 if index >= 19 else None,
            "volume": volume, "currency": snapshot.currency, "basis": basis,
        })
    return result


def price_summary(snapshot: MarketSnapshot, days: int = 90) -> dict | None:
    """Describe price movement, with a separate raw quote and adjusted-series label."""
    records = price_records(snapshot, days)
    if not records:
        return None
    latest = records[-1]
    previous = records[-2] if len(records) > 1 else None
    peak, max_drawdown = records[0]["price"], 0.0
    for row in records:
        peak = max(peak, row["price"])
        max_drawdown = min(max_drawdown, (row["price"] / peak - 1) * 100)
    return {
        "symbol": snapshot.symbol, "market": snapshot.market, "currency": snapshot.currency,
        "latest_close": latest["raw_close"], "previous_close": previous["raw_close"] if previous else None,
        "change_pct": (latest["raw_close"] / previous["raw_close"] - 1) * 100 if previous else None,
        "period_change_pct": (latest["price"] / records[0]["price"] - 1) * 100 if len(records) > 1 else None,
        "max_drawdown_pct": max_drawdown, "latest_drawdown_pct": (latest["price"] / peak - 1) * 100,
        "first_date": records[0]["date"], "as_of": latest["date"], "observations": len(records),
        "basis_label": latest["basis"], "price_basis": snapshot.price_basis,
        "cache_stale": snapshot.cache_stale,
    }


def price_chart(snapshot: MarketSnapshot, days: int = 90):
    """Build a responsive daily price chart; return None when no valid bars exist."""
    records = price_records(snapshot, days)
    if not records:
        return None
    basis = records[-1]["basis"]
    series = [basis] + (["TB 20 phiên"] if any(row["ma20"] is not None for row in records) else [])
    rows = []
    for row in records:
        rows.append({**row, "series": basis, "value": row["price"]})
        if row["ma20"] is not None:
            rows.append({**row, "series": "TB 20 phiên", "value": row["ma20"]})
    chart = alt.Chart(alt.Data(values=rows)).mark_line(strokeWidth=2.5, clip=True).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(format="%d/%m", labelColor="#A1A9B6", tickCount=5, grid=False)),
        y=alt.Y("value:Q", title=f"{basis} ({snapshot.currency})", scale=alt.Scale(zero=False), axis=alt.Axis(format=",.2f" if snapshot.currency == "USD" else ",.0f", tickCount=5, gridColor="#303640", domain=False)),
        color=alt.Color("series:N", title=None, scale=alt.Scale(domain=series, range=[PRICE_BLUE, MA_AMBER][:len(series)]), legend=alt.Legend(orient="top", labelColor="#C5CDD8", symbolType="stroke", symbolStrokeWidth=3)),
        strokeDash=alt.StrokeDash("series:N", scale=alt.Scale(domain=series, range=[[1, 0], [5, 4]][:len(series)]), legend=None),
        tooltip=[alt.Tooltip("date:T", title="Phiên", format="%d/%m/%Y"), alt.Tooltip("series:N", title="Chuỗi giá"), alt.Tooltip("value:Q", title=f"Giá ({snapshot.currency})", format=",.2f"), alt.Tooltip("raw_close:Q", title="Đóng cửa gốc", format=",.2f"), alt.Tooltip("volume:Q", title="Khối lượng", format=",.0f")],
    ).properties(height=300, width="container", title=alt.TitleParams(f"{snapshot.symbol} · Diễn biến giá", subtitle=f"{records[0]['date']} — {records[-1]['date']} · Dữ liệu theo phiên", anchor="start", fontSize=15, color="#EDF0F4", subtitleFontSize=11, subtitleColor="#A1A9B6"))
    return chart.configure_view(stroke=None).configure_axis(labelFontSize=11, labelColor="#A1A9B6", titleFontSize=11, titleFontWeight="normal", titleColor="#A1A9B6").configure(background="transparent")


def _quotes_by_identity(quotes) -> dict:
    if not quotes:
        return {}
    values = quotes.values() if isinstance(quotes, dict) else quotes
    result = {}
    for item in values:
        if isinstance(item, MarketSnapshot):
            if item.bars and not item.cache_stale:
                result[(item.market, item.symbol)] = {"close": item.latest.close, "currency": item.currency}
        elif isinstance(item, dict) and not item.get("cache_stale", False):
            result[(item.get("market"), item.get("symbol"))] = item
    return result


def allocation_records(holdings: list[dict], quotes=None) -> dict[str, list[dict]]:
    """Group positions by currency, using market values only for complete groups.

    Quotes can be snapshots or normalized summary dictionaries. With a missing
    quote, the entire currency group falls back to explicitly labeled cost basis.
    """
    grouped = defaultdict(list)
    quote_map = _quotes_by_identity(quotes)
    for holding in holdings:
        currency = {"VN": "VND", "US": "USD"}.get(holding.get("market"))
        quantity, cost = _positive(holding.get("quantity")), _positive(holding.get("average_cost"))
        if not currency or not holding.get("symbol") or quantity is None or cost is None or not math.isfinite(quantity * cost):
            continue
        quote = quote_map.get((holding["market"], holding["symbol"]))
        price = _positive(quote.get("close")) if quote and quote.get("currency") == currency else None
        value = quantity * price if price is not None else None
        grouped[currency].append({"symbol": holding["symbol"], "market": holding["market"], "quantity": quantity, "cost_basis": quantity * cost, "market_value": value if value is not None and math.isfinite(value) else None})
    result = {}
    for currency, rows in grouped.items():
        use_market = all(row["market_value"] is not None for row in rows)
        basis = "Giá trị theo giá gần nhất" if use_market else "Vốn đã nhập"
        field = "market_value" if use_market else "cost_basis"
        total = sum(row[field] for row in rows)
        if not math.isfinite(total) or total <= 0:
            continue
        result[currency] = sorted([{**row, "currency": currency, "value": row[field], "share": row[field] / total, "valuation_basis": basis} for row in rows], key=lambda row: (-row["value"], row["symbol"]))
    return result


def allocation_chart(holdings: list[dict], quotes=None) -> dict:
    """Return one horizontal allocation chart per currency, never an FX total."""
    charts = {}
    for currency, records in allocation_records(holdings, quotes).items():
        charts[currency] = alt.Chart(alt.Data(values=records)).mark_bar(cornerRadiusEnd=5, height=17).encode(
            y=alt.Y("symbol:N", title=None, sort="-x", axis=alt.Axis(domain=False, ticks=False, labelColor="#EDF0F4", labelFontWeight="bold")),
            x=alt.X("share:Q", title=None, scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format=".0%", gridColor="#303640", domain=False, tickCount=4, labelColor="#A1A9B6")),
            color=alt.Color("symbol:N", scale=alt.Scale(range=PALETTE), legend=None),
            tooltip=[alt.Tooltip("symbol:N", title="Mã"), alt.Tooltip("share:Q", title="Tỷ trọng", format=".1%"), alt.Tooltip("value:Q", title=f"Giá trị ({currency})", format=",.2f" if currency == "USD" else ",.0f"), alt.Tooltip("valuation_basis:N", title="Cơ sở tính")],
        ).properties(height=max(100, 34 * len(records)), width="container", title=alt.TitleParams(f"Phân bổ {currency}", subtitle=records[0]["valuation_basis"], anchor="start", fontSize=14, color="#EDF0F4", subtitleColor="#A1A9B6")).configure_view(stroke=None).configure(background="transparent")
    return charts


def workflow_diagram() -> str:
    """An accessible, static explanation; no user content is interpolated."""
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 134" role="img" aria-labelledby="method-title method-description" style="width:100%;height:auto;max-height:160px">
  <title id="method-title">Từ sách đến gợi ý mỗi ngày</title>
  <desc id="method-description">Sách bạn chọn được chuyển thành quy tắc có thể đối chiếu. Giá thị trường và danh mục được so với quy tắc để tạo gợi ý kèm giải thích.</desc>
  <defs><marker id="method-arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#6C788C"/></marker></defs>
  <g fill="none" stroke="#6C788C" stroke-width="2" marker-end="url(#method-arrow)"><path d="M 201 58 H 233"/><path d="M 428 58 H 460"/><path d="M 655 58 H 687"/></g>
  <g font-family="Arial, sans-serif">
    <rect x="1" y="12" width="200" height="92" rx="14" fill="#181B21" stroke="#303640"/><text x="20" y="39" font-size="11" fill="#A1A9B6">01 · KIẾN THỨC</text><text x="20" y="62" font-size="16" font-weight="600" fill="#EDF0F4">Sách bạn chọn</text><text x="20" y="84" font-size="11" fill="#A1A9B6">Có trích đoạn và số trang</text>
    <rect x="234" y="12" width="194" height="92" rx="14" fill="#181B21" stroke="#303640"/><text x="253" y="39" font-size="11" fill="#A1A9B6">02 · NGUYÊN TẮC</text><text x="253" y="62" font-size="16" font-weight="600" fill="#EDF0F4">Quy tắc đối chiếu</text><text x="253" y="84" font-size="11" fill="#A1A9B6">Bạn đọc và xác nhận trước</text>
    <rect x="461" y="12" width="194" height="92" rx="14" fill="#181B21" stroke="#303640"/><text x="480" y="39" font-size="11" fill="#A1A9B6">03 · DỮ LIỆU</text><text x="480" y="62" font-size="16" font-weight="600" fill="#EDF0F4">Giá và danh mục</text><text x="480" y="84" font-size="11" fill="#A1A9B6">Ghi rõ nguồn và phiên giá</text>
    <rect x="688" y="12" width="211" height="92" rx="14" fill="#303B50"/><text x="707" y="39" font-size="11" fill="#BCCEEA">04 · QUYẾT ĐỊNH</text><text x="707" y="62" font-size="16" font-weight="600" fill="#FFFFFF">Gợi ý có giải thích</text><text x="707" y="84" font-size="11" fill="#CCD8EC">Bạn xem xét và quyết định</text>
  </g>
</svg>'''
