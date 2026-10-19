"""Charts and safe HTML for the market workbench; only source candles are drawn."""
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from html import escape

import altair as alt

from breakout_ai.priceboard import format_number, time_label, number


VN_TIME = timezone(timedelta(hours=7))


def data(value):
    return asdict(value) if is_dataclass(value) else dict(value or {})


def candle_chart(snapshot, quote=None, report=None):
    snapshot, quote, report = data(snapshot), data(quote), data(report)
    candles = snapshot.get("candles", [])
    if snapshot.get("price_unit", "VND") != "VND" or snapshot.get("asset_type", "equity") != "equity":
        return None
    if not candles:
        return None
    rows, closes = [], []
    for raw in candles:
        row = data(raw)
        moment = datetime.fromisoformat(row["time"]).astimezone(VN_TIME)
        closes.append(row["close"])
        rows.append({**row, "label": moment.strftime("%d/%m %H:%M"), "direction": "Tăng" if row["close"] >= row["open"] else "Giảm", "ma20": sum(closes[-20:]) / 20 if len(closes) >= 20 else None})
    rows = rows[-160:]
    labels = [row["label"] for row in rows]
    source = alt.Data(values=rows)
    x = alt.X("label:O", title=None, sort=labels, axis=alt.Axis(labelAngle=0, labelOverlap="greedy", labelLimit=86, grid=False))
    base = alt.Chart(source).encode(x=x)
    color = alt.Color("direction:N", scale=alt.Scale(domain=["Tăng", "Giảm"], range=["#35d399", "#ff727f"]), legend=None)
    tooltip = [
        alt.Tooltip("label:O", title="Giờ VN"), alt.Tooltip("open:Q", title="Mở · VND", format=",.0f"),
        alt.Tooltip("high:Q", title="Cao · VND", format=",.0f"), alt.Tooltip("low:Q", title="Thấp · VND", format=",.0f"),
        alt.Tooltip("close:Q", title="Đóng · VND", format=",.0f"), alt.Tooltip("volume:Q", title="KL · CP", format=",.0f"),
        alt.Tooltip("complete:N", title="Nến đã đóng"),
    ]
    wick = base.mark_rule().encode(y=alt.Y("low:Q", title="Giá · VND", scale=alt.Scale(zero=False)), y2="high:Q", color=color, tooltip=tooltip)
    body = base.mark_bar(size=5).encode(y=alt.Y("open:Q", scale=alt.Scale(zero=False)), y2="close:Q", color=color, opacity=alt.condition("datum.complete", alt.value(1), alt.value(0.55)), tooltip=tooltip)
    ma = base.mark_line(color="#f0bc51", strokeWidth=1.5).encode(y="ma20:Q")
    layers = [wick, body, ma]
    levels = report.get("levels", {})
    for field, label, stroke in (("support", "Hỗ trợ 20 nến", "#79b8ff"), ("resistance", "Kháng cự 20 nến", "#d984f9")):
        value = number(levels.get(field))
        if value is not None and value > 0:
            layers.append(alt.Chart(alt.Data(values=[{"value": value, "name": label}])).mark_rule(color=stroke, strokeDash=[4, 4], opacity=.8).encode(y="value:Q", tooltip=[alt.Tooltip("name:N", title="Vùng quan sát"), alt.Tooltip("value:Q", title="VND", format=",.0f")]))
    last = number(quote.get("last"))
    if last is not None and last > 0 and quote.get("symbol") == snapshot.get("symbol") and not quote.get("stale", True):
        layers.append(alt.Chart(alt.Data(values=[{"value": last}])).mark_rule(color="#edf0f4", strokeDash=[2, 3]).encode(y="value:Q", tooltip=[alt.Tooltip("value:Q", title="Khớp gần nhất · VND", format=",.0f")]))
    prices = alt.layer(*layers).properties(height=270)
    volumes = base.mark_bar().encode(y=alt.Y("volume:Q", title="KL · CP", axis=alt.Axis(format="~s", tickCount=3)), color=color, tooltip=[alt.Tooltip("label:O", title="Giờ VN"), alt.Tooltip("volume:Q", title="Cổ phiếu", format=",.0f")]).properties(height=80)
    return alt.vconcat(prices, volumes, spacing=12).resolve_scale(x="shared").configure_view(stroke=None).configure(background="transparent").configure_axis(labelColor="#a1a9b6", titleColor="#a1a9b6", gridColor="#303640", domain=False, labelFontSize=10, titleFontSize=11).configure_concat(spacing=12)


def depth_chart(quote):
    quote = data(quote)
    if quote.get("depth_stale", True):
        return None
    rows = []
    for side, label in (("bids", "Dư mua"), ("asks", "Dư bán")):
        for index, raw in enumerate(quote.get(side, [])[:3]):
            row = data(raw)
            if row.get("price") is not None and row.get("volume") is not None:
                rows.append({"label": f"{label} {index+1} · {row['price']/1000:,.2f}", "side": label, "volume": row["volume"], "price": row["price"]})
    if not rows:
        return None
    return alt.Chart(alt.Data(values=rows)).mark_bar(cornerRadiusEnd=3).encode(
        x=alt.X("volume:Q", title="Lệnh chờ · CP", axis=alt.Axis(format="~s", tickCount=4)),
        y=alt.Y("label:N", title=None, sort=[row["label"] for row in rows], axis=alt.Axis(labelLimit=140)),
        color=alt.Color("side:N", scale=alt.Scale(domain=["Dư mua", "Dư bán"], range=["#35d399", "#ff727f"]), legend=None),
        tooltip=[alt.Tooltip("side:N", title="Bên"), alt.Tooltip("price:Q", title="Giá · VND", format=",.0f"), alt.Tooltip("volume:Q", title="KL · CP", format=",.0f")],
    ).properties(height=155).configure_view(stroke=None).configure(background="transparent").configure_axis(labelColor="#a1a9b6", titleColor="#a1a9b6", gridColor="#303640", domain=False)


def signal_card(report) -> str:
    report = data(report)
    action = report.get("action", "wait")
    title = escape(str(report.get("title", "Chờ dữ liệu")))
    symbol = escape(str(report.get("symbol", "")))
    cls = action if action in {"watch_buy", "watch_sell", "hold", "wait"} else "wait"
    items = "".join("<li>" + escape(str(item)) + "</li>" for item in report.get("evidence", [])[:5])
    blockers = report.get("blockers", [])
    block = '<div class="signal-blockers">' + "<br>".join(escape(str(item)) for item in blockers[:4]) + "</div>" if blockers else ""
    levels = report.get("levels", {})
    level_html = "".join('<div><small>' + label + '</small><strong>' + format_number(levels.get(key)) + '</strong></div>' for key, label in (("support", "Hỗ trợ · VND"), ("resistance", "Kháng cự · VND"), ("invalidation", "Vô hiệu · VND")))
    return '<section class="signal-card"><div class="signal-header"><strong>' + symbol + '</strong><span class="signal-tag ' + cls + '">' + title + '</span></div><p>' + escape(str(report.get("summary", ""))) + '</p><div class="signal-strength">' + escape(str(report.get("signal_strength", ""))) + '</div><ul class="signal-evidence">' + items + '</ul><div class="signal-levels">' + level_html + '</div>' + block + '<small>' + escape(str(report.get("timeframe", ""))) + ' · nến ' + escape(time_label(report.get("as_of"))) + '</small></section>'
