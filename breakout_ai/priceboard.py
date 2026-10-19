"""Accessible exchange-style price board; blanks never stand in for invented data."""
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone, timedelta
from html import escape
import math


VN_TIME = timezone(timedelta(hours=7))
DEFAULT_SYMBOLS = ("FPT", "VCB", "VNM", "HPG", "SSI", "MBB", "TCB", "STB", "MWG", "VIC", "VHM", "VRE", "PVS", "SHS", "ACV", "QNS")


def row_data(quote) -> dict:
    return asdict(quote) if is_dataclass(quote) else dict(quote)


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def format_number(value, decimals=0, divisor=1) -> str:
    parsed = number(value)
    return "—" if parsed is None else f"{parsed / divisor:,.{decimals}f}"


def price_class(value, row) -> str:
    value, reference = number(value), number(row.get("reference"))
    if value is None or value <= 0 or reference is None:
        return ""
    if math.isclose(value, reference, rel_tol=1e-10, abs_tol=1e-6):
        return "price-ref"
    ceiling, floor = number(row.get("ceiling")), number(row.get("floor"))
    if ceiling is not None and math.isclose(value, ceiling, rel_tol=1e-10, abs_tol=1e-6):
        return "price-ceiling"
    if floor is not None and math.isclose(value, floor, rel_tol=1e-10, abs_tol=1e-6):
        return "price-floor"
    return "price-up" if value > reference else "price-down"


def time_label(value) -> str:
    if not value:
        return "Chưa có giờ nguồn"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return "Chưa có giờ nguồn"
        return parsed.astimezone(VN_TIME).strftime("%H:%M:%S · %d/%m")
    except (ValueError, TypeError):
        return "Chưa có giờ nguồn"


def board_table(quotes, symbols=None, *, selected=None, full=True, price_divisor=1000) -> str:
    rows = {row["symbol"]: row for quote in quotes if (row := row_data(quote)).get("symbol")}
    ordered = list(symbols) if symbols is not None else list(rows)
    group = lambda label, span: f'<th scope="colgroup" colspan="{span}">{label}</th>'
    fixed = lambda label, cls="": f'<th scope="col" rowspan="2" class="{cls}">{label}</th>'
    first = fixed("Mã", "priceboard-symbol") + fixed("Trần", "price-ceiling") + fixed("Sàn", "price-floor") + fixed("TC", "price-ref")
    first += group("Bên mua", 6) + group("Khớp lệnh", 4) + group("Bên bán", 6) + fixed("Tổng KL", "group-start") + fixed("GT (triệu)")
    if full:
        first += group("Giá trong phiên", 4) + group("Nước ngoài (CP)", 2)
    first += fixed("Giờ nguồn", "group-start")
    second = []
    for index in (3, 2, 1):
        second += [f'<th scope="col" class="{"group-start" if index == 3 else ""}">Giá {index}</th>', f'<th scope="col">KL {index}</th>']
    second += ['<th scope="col" class="group-start">Giá</th>', '<th scope="col">KL</th>', '<th scope="col">+/−</th>', '<th scope="col">%</th>']
    for index in (1, 2, 3):
        second += [f'<th scope="col" class="{"group-start" if index == 1 else ""}">Giá {index}</th>', f'<th scope="col">KL {index}</th>']
    if full:
        second += ['<th scope="col" class="group-start">Mở</th>', '<th scope="col">Cao</th>', '<th scope="col">Thấp</th>', '<th scope="col">TB</th>', '<th scope="col" class="group-start">Mua</th>', '<th scope="col">Bán</th>']
    body = []
    for symbol in ordered:
        row = rows.get(symbol, {"symbol": symbol})
        classes = []
        if row.get("stale"):
            classes.append("is-stale")
        if symbol == selected:
            classes.append("is-selected")
        cells = [f'<th scope="row" class="priceboard-symbol">{escape(str(symbol))}<small>{escape(str(row.get("exchange") or "—"))}</small></th>']
        def cell(value, *, price=False, cls="", decimals=0, divisor=1, title=""):
            color = price_class(value, row) if price else ""
            text = format_number(value, decimals, divisor)
            cells.append(f'<td class="{cls} {color}" title="{escape(title, quote=True)}">{text}</td>')
        for key, color in (("ceiling", "price-ceiling"), ("floor", "price-floor"), ("reference", "price-ref")):
            cell(row.get(key), cls=color, decimals=2, divisor=price_divisor)
        for side, order in (("bids", (2, 1, 0)), ("asks", (0, 1, 2))):
            if side == "asks":
                cell(row.get("last"), price=True, cls="group-start", decimals=2, divisor=price_divisor)
                cell(row.get("match_volume"))
                change = number(row.get("change"))
                direction = "price-up" if change is not None and change > 0 else "price-down" if change is not None and change < 0 else "price-ref" if change is not None else ""
                cell(change, cls=direction, decimals=2, divisor=price_divisor)
                cell(row.get("change_pct"), cls=direction, decimals=2)
            levels = row.get(side) or []
            for offset, index in enumerate(order):
                level = levels[index] if index < len(levels) else {}
                if is_dataclass(level):
                    level = asdict(level)
                # Never color old depth as a fresh orderbook.
                stale_depth = row.get("depth_stale", False)
                value = None if stale_depth else level.get("price")
                volume = None if stale_depth else level.get("volume")
                title = "Độ sâu cũ; chờ dữ liệu mới" if stale_depth else ""
                cell(value, price=True, cls="group-start" if offset == 0 else "", decimals=2, divisor=price_divisor, title=title)
                cell(volume, title=title)
        cell(row.get("total_volume"), cls="group-start")
        cell(row.get("total_value"), decimals=2, divisor=1_000_000)
        if full:
            for index, key in enumerate(("open", "high", "low", "average")):
                cell(row.get(key), price=True, cls="group-start" if index == 0 else "", decimals=2, divisor=price_divisor)
            cell(row.get("foreign_buy_volume"), cls="group-start")
            cell(row.get("foreign_sell_volume"))
        label = time_label(row.get("source_timestamp"))
        if row.get("stale"):
            label += " · bản cũ"
        cells.append(f'<td class="group-start priceboard-time">{escape(label)}</td>')
        body.append('<tr class="' + " ".join(classes) + '">' + "".join(cells) + '</tr>')
    if not body:
        columns = 29 if full else 23
        body.append(f'<tr><td colspan="{columns}" class="priceboard-empty">Không có mã phù hợp với bộ lọc.</td></tr>')
    return '<div class="priceboard-scroll" tabindex="0" aria-label="Bảng giá cổ phiếu có thể cuộn ngang"><table class="priceboard-table"><thead><tr>' + first + '</tr><tr>' + "".join(second) + '</tr></thead><tbody>' + "".join(body) + '</tbody></table></div>'


def depth_table(quote, *, price_divisor=1000) -> str:
    row = row_data(quote)
    if row.get("depth_stale"):
        return '<div class="priceboard-empty">Sổ lệnh đang cũ. Chờ lần tải mới trước khi xem độ sâu.</div>'
    bids, asks = row.get("bids") or [], row.get("asks") or []
    body = []
    for index in range(3):
        bid = bids[index] if index < len(bids) else {}
        ask = asks[index] if index < len(asks) else {}
        bid = asdict(bid) if is_dataclass(bid) else bid
        ask = asdict(ask) if is_dataclass(ask) else ask
        body.append('<tr><td>' + format_number(bid.get("volume")) + '</td><td class="' + price_class(bid.get("price"), row) + '">' + format_number(bid.get("price"), 2, price_divisor) + '</td><td class="' + price_class(ask.get("price"), row) + '">' + format_number(ask.get("price"), 2, price_divisor) + '</td><td>' + format_number(ask.get("volume")) + '</td></tr>')
    return '<div class="priceboard-detail"><table><thead><tr><th>KL mua</th><th>Giá mua</th><th>Giá bán</th><th>KL bán</th></tr></thead><tbody>' + "".join(body) + '</tbody></table></div>'
