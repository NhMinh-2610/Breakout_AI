"""Book-grounded daily buy/hold/sell review and scheduled CLI entrypoint."""

import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math

from breakout_ai.book_rules import BookRule, learn_rules
from breakout_ai.books import BookLibrary
from breakout_ai.config import Settings
from breakout_ai.market import MarketService, MarketSnapshot
from breakout_ai.portfolio import Portfolio
from breakout_ai.storage import Store, utc_now

VN_TIME = timezone(timedelta(hours=7))
POLICY_VERSION = "book-daily-v1"


def local_day() -> str:
    return datetime.now(VN_TIME).date().isoformat()


def rules_signature(rules: list[BookRule]) -> str:
    return hashlib.sha256(json.dumps([rule.payload() for rule in rules], sort_keys=True).encode()).hexdigest()


def closed_snapshot(snapshot: MarketSnapshot, now: datetime | None = None) -> MarketSnapshot | None:
    """Conservative session cutoff, including US DST and after-hours buffer.

    VN: only previous Vietnam calendar dates. US: today's UTC bar is eligible
    only after 22:00 UTC (later than both regular close times). Not realtime.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now.astimezone(VN_TIME).date() if snapshot.market == "VN" else now.astimezone(timezone.utc).date()
    allow_same_day = snapshot.market == "US" and now.astimezone(timezone.utc).hour >= 22
    bars = [bar for bar in snapshot.bars if datetime.fromisoformat(bar.date).date() < cutoff or
            (allow_same_day and datetime.fromisoformat(bar.date).date() == cutoff)]
    return replace(snapshot, bars=bars) if bars else None


def _evaluate(rule: BookRule, snapshot: MarketSnapshot, holding: dict | None, estimate: float | None) -> dict:
    result = {**rule.payload(), "triggered": False, "available": True, "detail": ""}
    price = snapshot.latest.close
    if rule.kind in {"stop_loss_pct", "take_profit_pct"}:
        if not holding:
            result.update(available=False, detail="Cần biết giá vốn của mã đang sở hữu.")
            return result
        change = (price / holding["average_cost"] - 1) * 100
        target = holding["average_cost"] * (1 + (-rule.value if rule.kind == "stop_loss_pct" else rule.value) / 100)
        if not math.isfinite(change) or not math.isfinite(target):
            result.update(available=False, detail="Giá hoặc giá vốn vượt phạm vi tính toán. Kiểm tra lại vị thế.")
            return result
        result.update(triggered=price <= target if rule.kind == "stop_loss_pct" else price >= target,
                      detail=f"Giá ngày {price:,.2f} {snapshot.currency}; giá vốn {holding['average_cost']:,.2f}; lãi/lỗ giá {change:+.2f}%; mốc trong sách {rule.value:g}% (giá tham chiếu {target:,.2f}).")
    elif rule.kind == "margin_of_safety_pct":
        if not estimate:
            result.update(available=False, detail="Sách cần giá trị nội tại ước tính; chưa có dữ liệu này để đối chiếu.")
            return result
        target = estimate * (1 - rule.value / 100)
        result.update(triggered=price <= target, detail=f"Giá ngày {price:,.2f} {snapshot.currency}; mức mua theo ước tính bạn nhập {target:,.2f} (biên {rule.value:g}%). Ước tính này chưa được kiểm chứng.")
    else:
        window = int(rule.value)
        need_previous = "cross" in rule.kind
        if len(snapshot.bars) < window + int(need_previous):
            result.update(available=False, detail=f"Cần {window + int(need_previous)} phiên cho nguyên tắc này; nguồn mới có {len(snapshot.bars)}.")
            return result
        use_adjusted = all(bar.adjusted_close is not None for bar in snapshot.bars)
        prices = [bar.adjusted_close if use_adjusted else bar.close for bar in snapshot.bars]
        moving_average = sum(value / window for value in prices[-window:])
        above = prices[-1] > moving_average
        if need_previous:
            previous_average = sum(value / window for value in prices[-window - 1:-1])
            triggered = (prices[-2] <= previous_average and above) if rule.kind == "buy_cross_ma" else (prices[-2] >= previous_average and prices[-1] < moving_average)
        else:
            triggered = above if rule.kind == "buy_above_ma" else prices[-1] < moving_average
        result.update(triggered=triggered, detail=f"Giá dùng phân tích {prices[-1]:,.2f}; trung bình {window} phiên {moving_average:,.2f} {snapshot.currency}.")
        if not use_adjusted:
            result["detail"] += " Chưa xác minh điều chỉnh quyền của chuỗi giá."
    return result


class DailyPlanner:
    def __init__(self, settings: Settings, portfolio: Portfolio, books: BookLibrary, market: MarketService):
        self.settings, self.portfolio, self.books, self.market = settings, portfolio, books, market

    def active_book(self) -> dict | None:
        documents = self.books.documents()
        if not documents:
            return None
        active = self.portfolio.preferences()["active_book"]
        selected = next((book for book in documents if book["id"] == active), documents[0])
        if selected["id"] != active:
            self.portfolio.set_preferences(active_book=selected["id"])
        return selected

    def rules(self) -> list[BookRule]:
        book = self.active_book()
        return learn_rules(self.books.passages(book["id"])) if book else []

    def fingerprint(self) -> str:
        book = self.active_book()
        inputs = {"policy": POLICY_VERSION, "book": book["sha256"] if book else None,
                  "holdings": self.portfolio.holdings(), "preferences": self.portfolio.preferences(),
                  "market_enabled": self.settings.market_enabled,
                  "providers": [self.settings.vn_market_provider, self.settings.us_market_provider, self.settings.market_gateway_url]}
        return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()

    def get_today(self, refresh: bool = False) -> dict:
        fingerprint = self.fingerprint()
        existing = self.portfolio.report(local_day())
        if existing and existing["fingerprint"] == fingerprint and not refresh:
            return existing
        return self.generate(fingerprint)

    def generate(self, fingerprint: str | None = None) -> dict:
        book = self.active_book()
        rules = self.rules()
        holdings = self.portfolio.holdings()
        preferences = self.portfolio.preferences()
        report = {"day": local_day(), "created_at": utc_now(), "fingerprint": fingerprint or self.fingerprint(),
                  "book": {key: book[key] for key in ("id", "title", "author")} if book else None,
                  "rules": [rule.payload() for rule in rules], "items": [], "errors": [],
                  "status": "ready", "policy_version": POLICY_VERSION, "lesson": None}
        if not book:
            report["status"] = "needs_book"
            self.portfolio.save_report(report)
            return report
        passages = self.books.passages(book["id"])
        if passages:
            passage = passages[datetime.now(VN_TIME).date().toordinal() % len(passages)]
            report["lesson"] = {"text": passage.text[:750], "citation": passage.citation()}
        if not rules:
            report["status"] = "needs_measurable_rules"
            self.portfolio.save_report(report)
            return report
        if preferences["approved_rules"] != rules_signature(rules):
            report["status"] = "needs_rule_review"
            self.portfolio.save_report(report)
            return report
        requested = list(dict.fromkeys([(holding["market"], holding["symbol"]) for holding in holdings] + [tuple(pair) for pair in preferences["candidates"]]))
        snapshots = []
        for start in range(0, len(requested), self.settings.market_max_symbols):
            batch, errors = self.market.many(requested[start:start + self.settings.market_max_symbols], force=True)
            snapshots.extend(batch)
            report["errors"].extend(errors)
        closed = [closed_snapshot(snapshot) for snapshot in snapshots]
        by_identity = {(snapshot.market, snapshot.symbol): snapshot for snapshot in closed if snapshot is not None}
        owned = {(holding["market"], holding["symbol"]): holding for holding in holdings}
        for identity in requested:
            snapshot = by_identity.get(identity)
            holding = owned.get(identity)
            item = {"market": identity[0], "symbol": identity[1], "owned": holding is not None,
                    "action": "wait", "title": "Cần xem thêm", "reason": "", "checks": [], "quote": None,
                    "quantity": holding["quantity"] if holding else None, "average_cost": holding["average_cost"] if holding else None,
                    "pnl": None, "pnl_pct": None}
            if not snapshot:
                item["reason"] = "Chưa lấy được dữ liệu cho mã này. Chưa đưa ra gợi ý mua hoặc bán."
            else:
                item["quote"] = snapshot.summary()
                age = (datetime.now(timezone.utc).date() - datetime.fromisoformat(snapshot.latest.date).date()).days
                if snapshot.cache_stale or age < 0 or age > 7 or snapshot.latest.volume <= 0:
                    item["reason"] = "Dữ liệu đang cũ hoặc tải lại thất bại. Chờ nguồn cập nhật trước khi đánh giá."
                else:
                    applicable = [rule for rule in rules if rule.kind.startswith(("sell_", "stop_", "take_"))] if holding else [rule for rule in rules if rule.kind.startswith("buy_") or rule.kind == "margin_of_safety_pct"]
                    estimate = preferences["estimates"].get(":".join(identity))
                    item["checks"] = [_evaluate(rule, snapshot, holding, estimate) for rule in applicable]
                    checks = item["checks"]
                    if holding:
                        pnl = (snapshot.latest.close - holding["average_cost"]) * holding["quantity"]
                        pnl_pct = (snapshot.latest.close / holding["average_cost"] - 1) * 100
                        if math.isfinite(pnl) and math.isfinite(pnl_pct):
                            item.update(pnl=pnl, pnl_pct=pnl_pct)
                    if not checks:
                        item["reason"] = "Sách đã chọn chưa có nguyên tắc mua/bán đo được phù hợp với mã này."
                    elif holding and any(check["available"] and check["triggered"] for check in checks):
                        item.update(action="sell", title="Cân nhắc bán", reason=next(check["detail"] for check in checks if check["triggered"]))
                    elif any(not check["available"] for check in checks):
                        item["reason"] = next(check["detail"] for check in checks if not check["available"])
                    elif holding:
                        item.update(action="hold", title="Giữ và theo dõi", reason="Chưa chạm điều kiện bán trong sách đã chọn. " + checks[0]["detail"])
                    elif all(check["triggered"] for check in checks):
                        item.update(action="buy", title="Cân nhắc mua", reason="Đạt các điều kiện mua có thể kiểm tra trong sách. " + checks[0]["detail"])
                    else:
                        item["reason"] = "Chưa đạt đủ điều kiện mua trong sách. " + next(check["detail"] for check in checks if not check["triggered"])
            report["items"].append(item)
        self.portfolio.save_report(report)
        return report


def build_planner(settings: Settings | None = None) -> DailyPlanner:
    settings = settings or Settings.from_env()
    store = Store(settings.database_path, settings.workspace_id)
    return DailyPlanner(settings, Portfolio(store), BookLibrary(store), MarketService(settings, store))


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the personal morning review from owned books and market data; never places trades.")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    report = build_planner().get_today(refresh=args.refresh)
    # Contains no positions, excerpts, secrets or raw provider bodies in console output.
    print(f"Breakout AI daily: day={report['day']} status={report['status']} items={len(report['items'])}")
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
