"""Resolve market intent and produce evidence-backed research summaries."""

from dataclasses import dataclass, field
import re

from breakout_ai.knowledge import normalize
from breakout_ai.market import MarketService, MarketSnapshot
from breakout_ai.screening import rank_candidates, render_candidates

VN_SYMBOLS = set("FPT VCB VNM HPG TCB SSI VND MWG VIC VHM BID CTG MBB ACB MSN GAS PLX HDB STB VPB DGC GMD PNJ REE VRE SAB VJC VIB SHB".split())
US_SYMBOLS = set("AAPL MSFT GOOGL GOOG AMZN NVDA META TSLA IBM AMD NFLX AVGO JPM BAC BRK.B KO PEP COST WMT TSM INTC ORCL SPY VOO QQQ".split())
EXCLUDED = set("EPS TTM BVPS USD VND PE PB SEC ETF HOSE HSX HNX US VN ROE ROA CSV PDF TXT MD API AI SMA RSI GDP CPI YOY USA EBIT EBITDA VN30 VNINDEX HNXINDEX UPCOM KBS YAHOO".split())
DEFAULT_UNIVERSE = {"VN": ["FPT", "VCB", "VNM"], "US": ["AAPL", "MSFT", "GOOGL"]}


def recommendation_intent(question: str) -> bool:
    normalized = normalize(question)
    if re.search(r"\b(sach|book|books|tai lieu)\b", normalized) and not re.search(r"\b(co phieu|stock|stocks|vn|us)\b", normalized):
        return False
    return bool(re.search(r"\b(nen mua|can mua|goi y|khuyen nghi|chon ma|co nen mua|dang mua|sang loc|xep hang|recommend|buy|screen|rank|which stock)\b", normalized))


def extract_symbols(question: str, market: str) -> tuple[list[tuple[str, str]], list[str]]:
    found, ambiguous = [], []
    for selected, symbol in re.findall(r"\b(VN|US):([A-Z0-9][A-Z0-9.\-^]{0,11})\b", question.upper()):
        found.append((selected, symbol))
    explicit_symbols = {symbol for _, symbol in found}
    candidates = set(re.findall(r"\b[A-Z][A-Z0-9.\-^]{1,11}\b", question)) - EXCLUDED
    normalized_words = set(normalize(question).split())
    candidates |= {symbol for symbol in VN_SYMBOLS | US_SYMBOLS if symbol.lower() in normalized_words}
    scope = market
    normalized = normalize(question)
    if market == "BOTH":
        if re.search(r"\b(my|united states|usa)\b", normalized):
            scope = "US"
        elif "viet nam" in normalized:
            scope = "VN"
    for symbol in sorted(candidates):
        if symbol in explicit_symbols or re.fullmatch(r"(?:SMA|EMA|RSI|MA)\d+", symbol):
            continue
        if scope in {"VN", "US"}:
            found.append((scope, symbol))
        elif symbol in VN_SYMBOLS:
            found.append(("VN", symbol))
        elif symbol in US_SYMBOLS:
            found.append(("US", symbol))
        else:
            ambiguous.append(symbol)
    return list(dict.fromkeys(found)), ambiguous


def research_intent(question: str) -> bool:
    return recommendation_intent(question) or bool(re.search(r"\b(phan tich|so sanh|gia|price|quote|hom nay|hien tai|moi nhat|today|latest|current)\b", normalize(question)))


@dataclass
class ResearchBundle:
    snapshots: list[MarketSnapshot] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    requested: list[tuple[str, str]] = field(default_factory=list)

    def sources(self) -> list[dict]:
        return [{"id": f"M{s.market}_{s.symbol}", "kind": "market", "title": f"{s.market}:{s.symbol} · {s.latest.date}", "source_title": s.provider,
                 "source_url": s.source_url, "reviewed_at": s.latest.date, "fetched_at": s.fetched_at,
                 "cache_stale": s.cache_stale, "currency": s.currency} for s in self.snapshots]

    def context(self) -> dict:
        return {"requested": self.requested, "snapshots": [s.summary() for s in self.snapshots], "screening": self.candidates, "errors": self.errors}


def collect_research(service: MarketService, question: str, market: str) -> ResearchBundle:
    bundle = ResearchBundle()
    question_normal = normalize(question)
    if re.search(r"\b(tin tuc|news|earnings announcement)\b", question_normal):
        bundle.errors.append("Chưa có nguồn tin tức hoặc sự kiện doanh nghiệp. Dữ liệu giá ngày không xác nhận một tin mới.")
        return bundle
    symbols, ambiguous = extract_symbols(question, market)
    if ambiguous:
        bundle.errors.append("Chưa xác định được thị trường cho " + ", ".join(ambiguous) + ". Hãy viết VN:MÃ hoặc US:MÃ, hoặc chọn một thị trường.")
        return bundle
    recommend = recommendation_intent(question)
    if not symbols and recommend:
        markets = [market] if market != "BOTH" else ["VN", "US"]
        if "my" in question_normal and "viet nam" not in question_normal:
            markets = ["US"]
        elif "viet nam" in question_normal and "my" not in question_normal:
            markets = ["VN"]
        symbols = [(selected, symbol) for selected in markets for symbol in DEFAULT_UNIVERSE[selected]]
    if not symbols:
        bundle.errors.append("Hãy nêu mã và thị trường, ví dụ VN:FPT hoặc US:AAPL. Chưa có dữ liệu toàn thị trường để trả lời câu hỏi chung theo thời điểm.")
        return bundle
    bundle.requested = symbols
    bundle.snapshots, bundle.errors = service.many(symbols)
    if recommend:
        bundle.candidates = rank_candidates(bundle.snapshots)
    return bundle


def render_research(bundle: ResearchBundle) -> str:
    lines = ["### Dữ liệu thị trường đã lấy" if bundle.snapshots else "### Chưa lấy được dữ liệu phù hợp", "", "Đây là dữ liệu giá ngày từ nguồn, có thể gồm phiên chưa đóng; không phải báo giá realtime." if bundle.snapshots else "Mình sẽ không tạo số liệu thay cho phần chưa lấy được."]
    for snapshot in bundle.snapshots:
        row = snapshot.summary()
        change = f"{row['change_pct']:+.2f}%" if row["change_pct"] is not None else "chưa đủ dữ liệu"
        lines.append(f"- **{snapshot.market}:{snapshot.symbol}** — {row['close']:,.2f} {snapshot.currency}, ngày **{row['as_of']}**, thay đổi giá ngày {change}. [M{snapshot.market}_{snapshot.symbol}]")
        if snapshot.cache_stale:
            lines.append("  - Tải lại nguồn thất bại: đang dùng bản lưu cũ; không dùng để xếp hạng mua.")
    if bundle.candidates:
        lines += ["", render_candidates(bundle.candidates)]
    if bundle.errors:
        lines += ["", "**Phần chưa lấy được:**", *[f"- {error}" for error in bundle.errors]]
    if bundle.snapshots:
        lines += ["", "Nguồn hiện chưa cung cấp EPS/P/E/P/B, báo cáo tài chính hoặc tin tức vào chat; mình chưa có cơ sở kết luận định giá hay giá mục tiêu của từng doanh nghiệp."]
    return "\n".join(lines)
