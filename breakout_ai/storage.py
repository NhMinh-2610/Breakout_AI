"""Workspace-scoped SQLite persistence and atomic conversation turns."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from breakout_ai.finance import validate_symbol


class QuotaExceeded(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class Store:
    def __init__(self, path: Path, workspace: str = "local"):
        self.path, self.workspace = Path(path), workspace
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, 1, 2, 3, 4}:
                raise ValueError("Database dùng schema mới hơn ứng dụng; cần nâng phiên bản trước khi mở.")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, workspace TEXT NOT NULL,
                    title TEXT NOT NULL, market TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL,
                    market TEXT NOT NULL CHECK(market IN ('VN','US')),
                    symbol TEXT NOT NULL, note TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(workspace, market, symbol)
                );
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL,
                    created_at TEXT NOT NULL, provider TEXT NOT NULL,
                    input_tokens INTEGER, output_tokens INTEGER
                );
                CREATE INDEX IF NOT EXISTS conversations_workspace ON conversations(workspace, created_at);
                CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id, id);
                CREATE INDEX IF NOT EXISTS usage_workspace_time ON usage_events(workspace, created_at);
                PRAGMA user_version = 4;
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def conversations(self) -> list[dict]:
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM conversations WHERE workspace=? ORDER BY created_at DESC, id DESC", (self.workspace,))]

    def rename_conversation(self, identifier: str, title: str) -> None:
        title = title.strip()
        if not title or len(title) > 100:
            raise ValueError("Tên cuộc trò chuyện cần có 1–100 ký tự.")
        with self.connection() as db:
            db.execute("UPDATE conversations SET title=? WHERE id=? AND workspace=?", (title, identifier, self.workspace))

    def messages(self, conversation_id: str | None) -> list[dict]:
        if not conversation_id:
            return []
        with self.connection() as db:
            rows = db.execute("SELECT m.* FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.id=? AND c.workspace=? ORDER BY m.id", (conversation_id, self.workspace))
            return [{**dict(row), "metadata": json.loads(row["metadata"])} for row in rows]

    def _count(self, db: sqlite3.Connection) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="microseconds")
        return db.execute("SELECT COUNT(*) FROM usage_events WHERE workspace=? AND created_at>=?", (self.workspace, cutoff)).fetchone()[0]

    def usage(self) -> int:
        with self.connection() as db:
            return self._count(db)

    def save_turn(self, question: str, answer: str, metadata: dict, market: str, conversation_id: str | None, limit: int) -> str:
        if market not in {"VN", "US", "BOTH"}:
            raise ValueError("Thị trường không hợp lệ.")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if self._count(db) >= limit:
                raise QuotaExceeded("Bạn đã dùng hết số lượt trong 24 giờ. Hãy quay lại sau hoặc điều chỉnh hạn mức trong cấu hình.")
            if conversation_id:
                exists = db.execute("SELECT 1 FROM conversations WHERE id=? AND workspace=?", (conversation_id, self.workspace)).fetchone()
                if not exists:
                    raise ValueError("Không tìm thấy cuộc trò chuyện trong không gian này.")
            else:
                conversation_id = uuid4().hex
                db.execute("INSERT INTO conversations VALUES (?,?,?,?,?)", (conversation_id, self.workspace, question[:70], market, utc_now()))
            serialized = json.dumps(metadata, ensure_ascii=False)
            db.executemany("INSERT INTO messages(conversation_id,role,content,metadata,created_at) VALUES (?,?,?,?,?)", [
                (conversation_id, "user", question, "{}", utc_now()),
                (conversation_id, "assistant", answer, serialized, utc_now()),
            ])
            db.execute("INSERT INTO usage_events(workspace,created_at,provider,input_tokens,output_tokens) VALUES (?,?,?,?,?)", (self.workspace, utc_now(), metadata.get("provider", "unknown"), metadata.get("input_tokens"), metadata.get("output_tokens")))
        return conversation_id

    def delete_conversation(self, conversation_id: str) -> None:
        with self.connection() as db:
            db.execute("DELETE FROM conversations WHERE id=? AND workspace=?", (conversation_id, self.workspace))

    def watchlist(self) -> list[dict]:
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM watchlist WHERE workspace=? ORDER BY market,symbol", (self.workspace,))]

    def upsert_watch(self, market: str, symbol: str, note: str) -> None:
        symbol = validate_symbol(symbol)
        if market not in {"VN", "US"} or len(note) > 1500:
            raise ValueError("Thị trường không hợp lệ hoặc ghi chú dài quá 1.500 ký tự.")
        with self.connection() as db:
            db.execute("INSERT INTO watchlist(workspace,market,symbol,note,updated_at) VALUES (?,?,?,?,?) ON CONFLICT(workspace,market,symbol) DO UPDATE SET note=excluded.note,updated_at=excluded.updated_at", (self.workspace, market, symbol, note.strip(), utc_now()))

    def remove_watch(self, item_id: int) -> None:
        with self.connection() as db:
            db.execute("DELETE FROM watchlist WHERE id=? AND workspace=?", (item_id, self.workspace))
