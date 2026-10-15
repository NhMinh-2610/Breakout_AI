"""Owned positions are distinct from a watchlist. All records stay scoped."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from breakout_ai.finance import number, safe_csv, validate_symbol
from breakout_ai.storage import Store, utc_now

DEFAULT_CANDIDATES = [["VN", "FPT"], ["VN", "VCB"], ["VN", "VNM"], ["US", "AAPL"], ["US", "MSFT"], ["US", "GOOGL"]]
VN_TIME = timezone(timedelta(hours=7))
TRADE_EXPORT_FIELDS = ["id", "trade_date", "recorded_at", "market", "symbol", "currency", "side", "quantity", "price", "fees", "gross_value", "net_cash_flow", "average_cost_before", "average_cost_after", "quantity_after", "realized_pnl", "note"]


def _trade_day(value: str | date | None, *, future_allowed: bool = False) -> str:
    today = datetime.now(VN_TIME).date()
    if value is None:
        return today.isoformat()
    if isinstance(value, datetime):
        raise ValueError("Ngày giao dịch cần là ngày, không kèm giờ.")
    if isinstance(value, date):
        parsed = value
    else:
        try:
            parsed = date.fromisoformat(value)
        except (ValueError, TypeError) as exc:
            raise ValueError("Ngày giao dịch cần có dạng YYYY-MM-DD.") from exc
        if parsed.isoformat() != value:
            raise ValueError("Ngày giao dịch cần có dạng YYYY-MM-DD.")
    if not future_allowed and parsed > today:
        raise ValueError("Không ghi giao dịch có ngày trong tương lai theo giờ Việt Nam.")
    return parsed.isoformat()


class Portfolio:
    def __init__(self, store: Store):
        self.store = store
        with store.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL,
                    market TEXT NOT NULL CHECK(market IN ('VN','US')), symbol TEXT NOT NULL,
                    quantity REAL NOT NULL CHECK(quantity>0), average_cost REAL NOT NULL CHECK(average_cost>0),
                    updated_at TEXT NOT NULL, UNIQUE(workspace,market,symbol)
                );
                CREATE TABLE IF NOT EXISTS planner_preferences (
                    workspace TEXT PRIMARY KEY, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS daily_reports (
                    workspace TEXT NOT NULL, day TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(workspace,day)
                );
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace TEXT NOT NULL,
                    market TEXT NOT NULL CHECK(market IN ('VN','US')),
                    symbol TEXT NOT NULL,
                    currency TEXT NOT NULL CHECK(currency IN ('VND','USD')),
                    side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
                    quantity REAL NOT NULL CHECK(quantity>0),
                    price REAL NOT NULL CHECK(price>0),
                    fees REAL NOT NULL CHECK(fees>=0),
                    trade_date TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    gross_value REAL NOT NULL,
                    net_cash_flow REAL NOT NULL,
                    average_cost_before REAL,
                    average_cost_after REAL,
                    quantity_after REAL NOT NULL CHECK(quantity_after>=0),
                    realized_pnl REAL,
                    note TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    UNIQUE(workspace,idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS trades_workspace_symbol_day
                    ON trades(workspace,market,symbol,trade_date,id);
                CREATE TRIGGER IF NOT EXISTS trades_no_update BEFORE UPDATE ON trades
                    BEGIN SELECT RAISE(ABORT, 'Trade journal entries are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS trades_no_delete BEFORE DELETE ON trades
                    BEGIN SELECT RAISE(ABORT, 'Trade journal entries are immutable'); END;
            """)

    def holdings(self) -> list[dict]:
        with self.store.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM holdings WHERE workspace=? ORDER BY market,symbol", (self.store.workspace,))]

    def upsert(self, market: str, symbol: str, quantity: float, average_cost: float) -> None:
        symbol = validate_symbol(symbol)
        quantity, average_cost = number(quantity, "Số lượng"), number(average_cost, "Giá vốn")
        if market not in {"VN", "US"} or quantity <= 0 or average_cost <= 0 or quantity > 1e10 or not math.isfinite(quantity * average_cost):
            raise ValueError("Chọn đúng thị trường, số lượng và giá vốn dương, trong phạm vi tính toán.")
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM trades WHERE workspace=? AND market=? AND symbol=? LIMIT 1", (self.store.workspace, market, symbol)).fetchone():
                raise ValueError("Mã đã có nhật ký giao dịch. Hãy ghi giao dịch mua/bán thay vì sửa số dư thủ công.")
            exists = db.execute("SELECT 1 FROM holdings WHERE workspace=? AND market=? AND symbol=?", (self.store.workspace, market, symbol)).fetchone()
            count = db.execute("SELECT COUNT(*) FROM holdings WHERE workspace=?", (self.store.workspace,)).fetchone()[0]
            if not exists and count >= 20:
                raise ValueError("Bản cá nhân hỗ trợ tối đa 20 mã đang sở hữu.")
            db.execute("INSERT INTO holdings(workspace,market,symbol,quantity,average_cost,updated_at) VALUES (?,?,?,?,?,?) ON CONFLICT(workspace,market,symbol) DO UPDATE SET quantity=excluded.quantity,average_cost=excluded.average_cost,updated_at=excluded.updated_at", (self.store.workspace, market, symbol, quantity, average_cost, utc_now()))

    def remove(self, identifier: int) -> None:
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            position = db.execute("SELECT market,symbol FROM holdings WHERE id=? AND workspace=?", (identifier, self.store.workspace)).fetchone()
            if position and db.execute("SELECT 1 FROM trades WHERE workspace=? AND market=? AND symbol=? LIMIT 1", (self.store.workspace, position["market"], position["symbol"])).fetchone():
                raise ValueError("Mã đã có nhật ký giao dịch. Hãy ghi giao dịch bán để giảm hoặc đóng vị thế.")
            db.execute("DELETE FROM holdings WHERE id=? AND workspace=?", (identifier, self.store.workspace))

    def has_trades(self, market: str, symbol: str) -> bool:
        symbol = validate_symbol(symbol)
        with self.store.connection() as db:
            return db.execute("SELECT 1 FROM trades WHERE workspace=? AND market=? AND symbol=? LIMIT 1", (self.store.workspace, market, symbol)).fetchone() is not None

    def record_trade(self, market: str, symbol: str, side: str, quantity: float, price: float, *, fees: float = 0, trade_date: str | date | None = None, note: str = "", idempotency_key: str) -> dict:
        """Record a manual fill and update holdings in the same SQLite transaction.

        Buy fees enter weighted average cost; sell fees reduce realized P&L.
        Amounts stay in each market's currency. A starting position is a current
        manual snapshot, so earlier fills cannot be appended behind that snapshot.
        Otherwise entries must be chronological per symbol; same-day fills use
        insertion order. Journal entries are immutable and cannot be overwritten
        by editing a position. This is a record of user-entered fills, not orders
        sent to a broker, a complete historical return, or a tax statement.
        """
        symbol = validate_symbol(symbol)
        if market not in {"VN", "US"} or side not in {"BUY", "SELL"}:
            raise ValueError("Chọn thị trường VN/US và loại giao dịch BUY/SELL.")
        if any(isinstance(value, bool) for value in (quantity, price, fees)):
            raise ValueError("Số lượng, giá và phí phải là số hợp lệ.")
        quantity, price, fees = number(quantity, "Số lượng"), number(price, "Giá giao dịch"), number(fees, "Phí")
        if quantity <= 0 or quantity > 1e10 or price <= 0 or fees < 0:
            raise ValueError("Số lượng và giá phải dương, số lượng tối đa 10 tỷ; phí không âm.")
        day = _trade_day(trade_date)
        if not isinstance(note, str) or len(note) > 1500:
            raise ValueError("Ghi chú giao dịch tối đa 1.500 ký tự.")
        note = note.strip()
        if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 128:
            raise ValueError("Mỗi lần ghi giao dịch cần một mã chống trùng có 1–128 ký tự.")
        request = {"market": market, "symbol": symbol, "side": side, "quantity": quantity, "price": price, "fees": fees, "trade_date": day, "note": note}
        gross = quantity * price
        if not math.isfinite(gross) or not math.isfinite(gross + fees) or gross <= 0:
            raise ValueError("Giá trị giao dịch vượt phạm vi tính toán.")
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT * FROM trades WHERE workspace=? AND idempotency_key=?", (self.store.workspace, idempotency_key)).fetchone()
            if previous:
                if any(previous[field] != value for field, value in request.items()):
                    raise ValueError("Mã chống trùng đã dùng cho một giao dịch khác; hãy tạo lần ghi mới.")
                return dict(previous)
            position = db.execute("SELECT * FROM holdings WHERE workspace=? AND market=? AND symbol=?", (self.store.workspace, market, symbol)).fetchone()
            last = db.execute("SELECT trade_date FROM trades WHERE workspace=? AND market=? AND symbol=? ORDER BY trade_date DESC,id DESC LIMIT 1", (self.store.workspace, market, symbol)).fetchone()
            earliest = last["trade_date"] if last else None
            if position and not last:
                # Existing positions are current snapshots rather than past fills.
                earliest = datetime.fromisoformat(position["updated_at"]).astimezone(VN_TIME).date().isoformat()
            if earliest and day < earliest:
                raise ValueError(f"Ghi giao dịch theo thứ tự thời gian: ngày không được trước {earliest}, là mốc cập nhật vị thế gần nhất.")
            before_quantity = position["quantity"] if position else 0.0
            before_cost = position["average_cost"] if position else None
            # Decimal text arithmetic avoids residual positions such as
            # (0.1 + 0.2) - 0.3 while keeping stored/public values as finite floats.
            # Do not forgive oversells with a broad relative epsilon.
            before_units, traded_units = Decimal(str(before_quantity)), Decimal(str(quantity))
            if side == "BUY":
                if not position and db.execute("SELECT COUNT(*) FROM holdings WHERE workspace=?", (self.store.workspace,)).fetchone()[0] >= 20:
                    raise ValueError("Bản cá nhân hỗ trợ tối đa 20 mã đang sở hữu.")
                after_units = before_units + traded_units
                after_quantity = float(after_units)
                total_cost = before_quantity * (before_cost or 0) + gross + fees
                after_cost = total_cost / after_quantity
                cash_flow, realized = -(gross + fees), None
                if after_units > Decimal("1e10") or not all(math.isfinite(value) for value in (after_quantity, total_cost, after_cost, after_quantity * after_cost)) or after_cost <= 0 or after_quantity <= before_quantity:
                    raise ValueError("Số dư hoặc giá vốn vượt phạm vi tính toán; kiểm tra lại số liệu.")
            else:
                if not position or traded_units > before_units:
                    raise ValueError("Số lượng bán vượt số cổ phiếu đang sở hữu.")
                after_quantity = float(before_units - traded_units)
                after_cost = before_cost if after_quantity > 0 else None
                cash_flow = gross - fees
                realized = cash_flow - quantity * before_cost
                if not math.isfinite(realized) or (after_quantity > 0 and after_quantity == before_quantity):
                    raise ValueError("Lãi/lỗ hoặc số dư vượt phạm vi tính toán; kiểm tra lại số liệu.")
            recorded_at = utc_now()
            row = {"workspace": self.store.workspace, **request, "currency": {"VN": "VND", "US": "USD"}[market], "recorded_at": recorded_at, "gross_value": gross, "net_cash_flow": cash_flow, "average_cost_before": before_cost, "average_cost_after": after_cost, "quantity_after": after_quantity, "realized_pnl": realized, "idempotency_key": idempotency_key}
            fields = list(row)
            cursor = db.execute(f"INSERT INTO trades({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", tuple(row.values()))
            if after_quantity == 0:
                db.execute("DELETE FROM holdings WHERE workspace=? AND market=? AND symbol=?", (self.store.workspace, market, symbol))
            else:
                db.execute("INSERT INTO holdings(workspace,market,symbol,quantity,average_cost,updated_at) VALUES (?,?,?,?,?,?) ON CONFLICT(workspace,market,symbol) DO UPDATE SET quantity=excluded.quantity,average_cost=excluded.average_cost,updated_at=excluded.updated_at", (self.store.workspace, market, symbol, after_quantity, after_cost, recorded_at))
            return {"id": cursor.lastrowid, **row}

    def trades(self, market: str | None = None, symbol: str | None = None, *, side: str | None = None, start_date: str | date | None = None, end_date: str | date | None = None, limit: int = 500) -> list[dict]:
        """Return recorded fills newest first, with workspace-scoped filters."""
        clauses, values = ["workspace=?"], [self.store.workspace]
        if market is not None:
            if market not in {"VN", "US"}:
                raise ValueError("Thị trường cần là VN hoặc US.")
            clauses.append("market=?")
            values.append(market)
        if symbol is not None:
            clauses.append("symbol=?")
            values.append(validate_symbol(symbol))
        if side is not None:
            if side not in {"BUY", "SELL"}:
                raise ValueError("Loại giao dịch cần là BUY hoặc SELL.")
            clauses.append("side=?")
            values.append(side)
        start = _trade_day(start_date, future_allowed=True) if start_date is not None else None
        end = _trade_day(end_date, future_allowed=True) if end_date is not None else None
        if start and end and start > end:
            raise ValueError("Ngày bắt đầu không được sau ngày kết thúc.")
        for operator, day in ((">=", start), ("<=", end)):
            if day:
                clauses.append(f"trade_date{operator}?")
                values.append(day)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10000:
            raise ValueError("Số giao dịch mỗi lần đọc cần từ 1 đến 10.000.")
        values.append(limit)
        with self.store.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM trades WHERE " + " AND ".join(clauses) + " ORDER BY trade_date DESC,id DESC LIMIT ?", values)]

    def export_trades_csv(self, market: str | None = None, symbol: str | None = None, *, side: str | None = None, start_date: str | date | None = None, end_date: str | date | None = None, limit: int = 10000) -> str:
        """Export selected manual fills without inventing unrecorded history."""
        return safe_csv(self.trades(market, symbol, side=side, start_date=start_date, end_date=end_date, limit=limit), TRADE_EXPORT_FIELDS)

    def trade_count(self, market: str | None = None, symbol: str | None = None) -> int:
        """Count all matching journal entries without a display/export limit."""
        clauses, values = ["workspace=?"], [self.store.workspace]
        if market is not None:
            if market not in {"VN", "US"}:
                raise ValueError("Thị trường cần là VN hoặc US.")
            clauses.append("market=?")
            values.append(market)
        if symbol is not None:
            clauses.append("symbol=?")
            values.append(validate_symbol(symbol))
        with self.store.connection() as db:
            return db.execute("SELECT COUNT(*) FROM trades WHERE " + " AND ".join(clauses), values).fetchone()[0]

    def preferences(self) -> dict:
        defaults = {"active_book": None, "candidates": DEFAULT_CANDIDATES, "estimates": {}, "morning_time": "07:30", "approved_rules": ""}
        with self.store.connection() as db:
            row = db.execute("SELECT payload FROM planner_preferences WHERE workspace=?", (self.store.workspace,)).fetchone()
        return {**defaults, **json.loads(row["payload"])} if row else defaults

    def set_preferences(self, **changes) -> None:
        if not set(changes) <= {"active_book", "candidates", "estimates", "morning_time", "approved_rules"}:
            raise ValueError("Thiết lập không được hỗ trợ.")
        if "candidates" in changes:
            candidates = list(dict.fromkeys(tuple(pair) for pair in changes["candidates"]))
            if len(candidates) > 10 or any(market not in {"VN", "US"} for market, _ in candidates):
                raise ValueError("Danh sách tìm mua tối đa 10 mã, có thị trường VN/US.")
            changes["candidates"] = [[market, validate_symbol(symbol)] for market, symbol in candidates]
        if "estimates" in changes:
            for value in changes["estimates"].values():
                if number(value, "Giá trị ước tính") <= 0:
                    raise ValueError("Giá trị ước tính phải dương.")
        current = {**self.preferences(), **changes}
        with self.store.connection() as db:
            db.execute("INSERT INTO planner_preferences VALUES (?,?) ON CONFLICT(workspace) DO UPDATE SET payload=excluded.payload", (self.store.workspace, json.dumps(current, ensure_ascii=False)))

    def save_report(self, report: dict) -> None:
        with self.store.connection() as db:
            db.execute("INSERT INTO daily_reports VALUES (?,?,?,?,?) ON CONFLICT(workspace,day) DO UPDATE SET fingerprint=excluded.fingerprint,created_at=excluded.created_at,payload=excluded.payload", (self.store.workspace, report["day"], report["fingerprint"], report["created_at"], json.dumps(report, ensure_ascii=False, allow_nan=False)))

    def report(self, day: str) -> dict | None:
        with self.store.connection() as db:
            row = db.execute("SELECT payload FROM daily_reports WHERE workspace=? AND day=?", (self.store.workspace, day)).fetchone()
        return json.loads(row["payload"]) if row else None

    def recent_reports(self, limit: int = 14) -> list[dict]:
        with self.store.connection() as db:
            rows = db.execute("SELECT day,created_at FROM daily_reports WHERE workspace=? ORDER BY day DESC LIMIT ?", (self.store.workspace, max(1, min(limit, 60))))
            return [dict(row) for row in rows]
