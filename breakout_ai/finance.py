"""Deterministic financial arithmetic; inputs are user-supplied, not quotes."""

import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from io import StringIO
import math
import re


def number(value: float | str, label: str) -> float:
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{label} phải là số.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} phải là số hữu hạn.")
    return result


def validate_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-^]{0,11}", symbol):
        raise ValueError("Mã cần có 1–12 ký tự: chữ, số, dấu chấm, gạch ngang hoặc ^.")
    return symbol


def valuation(price: float, eps: float, bvps: float, dividend: float = 0) -> dict:
    price, eps, bvps, dividend = [number(v, k) for v, k in zip((price, eps, bvps, dividend), ("Giá", "EPS", "BVPS", "Cổ tức"))]
    if price <= 0 or dividend < 0:
        raise ValueError("Giá phải lớn hơn 0 và cổ tức không được âm.")
    result = {
        "pe": price / eps if eps > 0 else None,
        "pb": price / bvps if bvps > 0 else None,
        "dividend_yield_pct": dividend / price * 100,
    }
    if any(value is not None and not math.isfinite(value) for value in result.values()):
        raise ValueError("Số liệu quá lớn hoặc mẫu số quá nhỏ để tính chính xác bằng công cụ này.")
    return result


def hypothetical_return(entry: float, exit_price: float, shares: int, fees: float = 0) -> dict:
    entry, exit_price, fees = [number(v, k) for v, k in zip((entry, exit_price, fees), ("Giá mua", "Giá bán", "Phí"))]
    if entry <= 0 or exit_price < 0 or fees < 0 or isinstance(shares, bool) or not isinstance(shares, int) or shares <= 0:
        raise ValueError("Giá mua và số lượng phải dương; giá bán và tổng phí không được âm.")
    invested = entry * shares
    net = (exit_price - entry) * shares - fees
    if not math.isfinite(invested) or not math.isfinite(net) or invested <= 0:
        raise ValueError("Số liệu vượt phạm vi tính toán của công cụ.")
    result = {"invested": invested, "net_pnl": net, "return_pct": net / invested * 100}
    if not math.isfinite(result["return_pct"]):
        raise ValueError("Số liệu vượt phạm vi tính toán của công cụ.")
    return result


@dataclass(frozen=True)
class Snapshot:
    market: str
    symbol: str
    currency: str
    price: float
    eps_ttm: float
    bvps: float
    dividend_per_share: float
    as_of: str
    source: str

    def metrics(self) -> dict:
        return {**asdict(self), **valuation(self.price, self.eps_ttm, self.bvps, self.dividend_per_share)}


def read_snapshots(data: bytes) -> list[Snapshot]:
    if len(data) > 1_000_000:
        raise ValueError("CSV tối đa 1 MB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Hãy lưu CSV bằng UTF-8.") from exc
    reader = csv.DictReader(StringIO(text))
    expected = set(Snapshot.__dataclass_fields__)
    if set(reader.fieldnames or []) != expected or len(reader.fieldnames or []) != len(expected):
        raise ValueError("CSV cần đúng các cột: " + ", ".join(Snapshot.__dataclass_fields__))
    result, seen = [], set()
    today = datetime.now(timezone(timedelta(hours=7))).date()
    for row_index, row in enumerate(reader, start=2):
        if len(result) >= 200:
            raise ValueError("CSV tối đa 200 dòng dữ liệu.")
        try:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Số cột không khớp.")
            row = {k: v.strip() for k, v in row.items()}
            if row["market"] not in {"VN", "US"}:
                raise ValueError("market phải là VN hoặc US.")
            if row["currency"] != {"VN": "VND", "US": "USD"}[row["market"]]:
                raise ValueError("VN dùng VND, US dùng USD; không tự quy đổi ngoại tệ.")
            symbol = validate_symbol(row["symbol"])
            identity = (row["market"], symbol)
            if identity in seen:
                raise ValueError("Một mã xuất hiện nhiều lần trong cùng thị trường.")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["as_of"]) or date.fromisoformat(row["as_of"]) > today:
                raise ValueError("as_of cần là ngày YYYY-MM-DD không nằm trong tương lai.")
            if not row["source"] or len(row["source"]) > 300:
                raise ValueError("source cần có 1–300 ký tự.")
            numeric = {key: number(row[key], key) for key in ("price", "eps_ttm", "bvps", "dividend_per_share")}
            valuation(numeric["price"], numeric["eps_ttm"], numeric["bvps"], numeric["dividend_per_share"])
            result.append(Snapshot(market=row["market"], symbol=symbol, currency=row["currency"], as_of=row["as_of"], source=row["source"], **numeric))
            seen.add(identity)
        except ValueError as exc:
            raise ValueError(f"Dòng {row_index}: {exc}") from exc
    if not result:
        raise ValueError("CSV chưa có dữ liệu.")
    return result


def safe_csv(rows: list[dict], fields: list[str]) -> str:
    """Neutralize spreadsheet formulas in user-controlled text on export."""
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        cleaned = {}
        for key in fields:
            value = row.get(key, "")
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            cleaned[key] = value
        writer.writerow(cleaned)
    return stream.getvalue()
