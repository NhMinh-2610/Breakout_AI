"""Local, workspace-scoped PDF/TXT/Markdown ingestion with page citations."""

from collections import Counter
from dataclasses import dataclass
import hashlib
from io import BytesIO
import math
from pathlib import Path
import re
from uuid import uuid4

from pypdf import PdfReader

from breakout_ai.knowledge import normalize, tokens
from breakout_ai.storage import Store, utc_now

MAX_FILE_BYTES = 20_000_000
MAX_PAGES = 400
MAX_TEXT_CHARS = 1_500_000
MAX_CHUNKS = 3000
MAX_WORKSPACE_CHUNKS = 6000
ALIASES = {
    "bien an toan": "margin of safety", "dinh gia": "valuation intrinsic value",
    "gia tri noi tai": "intrinsic value", "loi the canh tranh": "competitive advantage economic moat",
    "da dang hoa": "diversification portfolio", "loi nhuan": "earnings profit",
    "dong tien": "cash flow", "co tuc": "dividend", "rui ro": "risk",
    "bang can doi": "balance sheet", "co phieu": "stock equity", "no": "debt",
    "tang truong": "growth", "pe": "earnings ratio", "pb": "book value",
}


class BookError(ValueError):
    pass


@dataclass(frozen=True)
class Passage:
    id: str
    document_id: str
    title: str
    author: str
    page: int | None
    ordinal: int
    text: str
    imported_at: str

    def citation(self) -> dict:
        location = f"trang PDF {self.page}" if self.page is not None else f"đoạn {self.ordinal + 1}"
        return {"id": self.id, "kind": "book", "document_id": self.document_id, "page": self.page,
                "title": self.title, "source_title": f"{self.title} · {location}",
                "source_url": "", "reviewed_at": self.imported_at[:10], "author": self.author}


def chunk_text(text: str, size: int = 1500, overlap: int = 180) -> list[str]:
    if not 0 <= overlap < size:
        raise BookError("Cấu hình chia đoạn không hợp lệ.")
    text = re.sub(r"[ \t]+", " ", text.replace("\x00", "")).strip()
    result, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        piece = text[start:end].strip()
        if piece:
            result.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return result


def extract_pages(filename: str, data: bytes) -> list[tuple[int | None, str]]:
    if not data or len(data) > MAX_FILE_BYTES:
        raise BookError("Tài liệu cần có dữ liệu và không vượt 20 MB.")
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        try:
            pages = [(None, data.decode("utf-8-sig"))]
        except UnicodeDecodeError as exc:
            raise BookError("TXT/Markdown cần dùng UTF-8.") from exc
    elif suffix == ".pdf":
        try:
            reader = PdfReader(BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise BookError("PDF có mật khẩu. Hãy tải bản không mã hóa mà bạn được phép sử dụng.")
            if len(reader.pages) > MAX_PAGES:
                raise BookError("Mỗi tài liệu tối đa 400 trang; hãy tách sách thành các phần.")
            pages, total = [], 0
            for index, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                total += len(text)
                if total > MAX_TEXT_CHARS:
                    raise BookError("Nội dung vượt 1,5 triệu ký tự; hãy tách tài liệu.")
                pages.append((index, text))
        except BookError:
            raise
        except Exception as exc:
            raise BookError("Không đọc được PDF. Kiểm tra file hoặc xuất lại bản PDF có lớp chữ.") from exc
    else:
        raise BookError("Chỉ hỗ trợ PDF, TXT và Markdown.")
    if sum(len(text) for _, text in pages) > MAX_TEXT_CHARS:
        raise BookError("Nội dung vượt 1,5 triệu ký tự; hãy tách tài liệu.")
    if not any(text.strip() for _, text in pages):
        raise BookError("Không tìm thấy chữ. PDF scan cần OCR trước; ứng dụng chưa có OCR.")
    return pages


class BookLibrary:
    def __init__(self, store: Store):
        self.store = store
        with store.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS books (
                    id TEXT PRIMARY KEY, workspace TEXT NOT NULL,
                    title TEXT NOT NULL, author TEXT NOT NULL, filename TEXT NOT NULL,
                    sha256 TEXT NOT NULL, pages INTEGER NOT NULL, imported_at TEXT NOT NULL,
                    UNIQUE(workspace,sha256)
                );
                CREATE TABLE IF NOT EXISTS book_chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                    page INTEGER, ordinal INTEGER NOT NULL, text TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS books_workspace ON books(workspace);
                CREATE INDEX IF NOT EXISTS book_document ON book_chunks(document_id);
            """)

    def documents(self) -> list[dict]:
        with self.store.connection() as db:
            return [dict(row) for row in db.execute("SELECT b.*,COUNT(c.id) AS chunks FROM books b LEFT JOIN book_chunks c ON c.document_id=b.id WHERE b.workspace=? GROUP BY b.id ORDER BY b.imported_at DESC", (self.store.workspace,))]

    def ingest(self, filename: str, data: bytes, title: str = "", author: str = "") -> tuple[str, bool]:
        filename = Path(filename.replace("\\", "/")).name
        title = (title.strip() or Path(filename).stem).strip()
        if not title or len(title) > 200 or len(author) > 160:
            raise BookError("Tên sách cần có 1–200 ký tự; tác giả tối đa 160 ký tự.")
        digest = hashlib.sha256(data).hexdigest()
        with self.store.connection() as db:
            existing = db.execute("SELECT id FROM books WHERE workspace=? AND sha256=?", (self.store.workspace, digest)).fetchone()
            if existing:
                return existing["id"], False
        pages = extract_pages(filename, data)
        identifier = uuid4().hex
        chunks = []
        for page, text in pages:
            for piece in chunk_text(text):
                ordinal = len(chunks)
                chunks.append((f"B{identifier}_{ordinal}", identifier, page, ordinal, piece))
                if len(chunks) > MAX_CHUNKS:
                    raise BookError("Tài liệu có quá nhiều đoạn; hãy tách nhỏ.")
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT id FROM books WHERE workspace=? AND sha256=?", (self.store.workspace, digest)).fetchone()
            if existing:
                return existing["id"], False
            total = db.execute("SELECT COUNT(c.id) FROM book_chunks c JOIN books b ON b.id=c.document_id WHERE b.workspace=?", (self.store.workspace,)).fetchone()[0]
            if total + len(chunks) > MAX_WORKSPACE_CHUNKS:
                raise BookError("Thư viện vượt giới hạn 6.000 đoạn. Hãy xóa tài liệu không cần trước khi nhập thêm.")
            db.execute("INSERT INTO books VALUES (?,?,?,?,?,?,?,?)", (identifier, self.store.workspace, title, author.strip(), filename, digest, len(pages), utc_now()))
            db.executemany("INSERT INTO book_chunks VALUES (?,?,?,?,?)", chunks)
        return identifier, True

    def delete(self, document_id: str) -> None:
        with self.store.connection() as db:
            deleted = db.execute("DELETE FROM books WHERE id=? AND workspace=?", (document_id, self.store.workspace)).rowcount
            if deleted and db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='daily_reports'").fetchone():
                # Daily reports contain source excerpts; remove them with their book.
                db.execute("DELETE FROM daily_reports WHERE workspace=? AND json_extract(payload,'$.book.id')=?", (self.store.workspace, document_id))

    def passages(self, document_id: str | None = None) -> list[Passage]:
        with self.store.connection() as db:
            rows = [dict(row) for row in db.execute("SELECT c.*,b.title,b.author,b.imported_at FROM book_chunks c JOIN books b ON b.id=c.document_id WHERE b.workspace=? AND (? IS NULL OR b.id=?) ORDER BY b.imported_at,c.ordinal", (self.store.workspace, document_id, document_id))]
        return [Passage(**row) for row in rows]

    def search(self, query: str, limit: int = 3, document_id: str | None = None) -> list[Passage]:
        normalized = normalize(query)
        for term, english in ALIASES.items():
            if re.search(r"\b" + re.escape(term) + r"\b", normalized):
                query += " " + english
        query_terms = set(tokens(query))
        with self.store.connection() as db:
            rows = [dict(row) for row in db.execute("SELECT c.*,b.title,b.author,b.imported_at FROM book_chunks c JOIN books b ON b.id=c.document_id WHERE b.workspace=? AND (? IS NULL OR b.id=?)", (self.store.workspace, document_id, document_id))]
        if not rows or not query_terms:
            return []
        counts = [Counter(tokens(row["text"])) for row in rows]
        frequency = Counter(term for count in counts for term in count)
        avg = sum(sum(count.values()) for count in counts) / len(counts) or 1
        scored = []
        for row, count in zip(rows, counts):
            score = 0.0
            length = sum(count.values())
            for term in query_terms:
                tf = count[term]
                if tf:
                    idf = math.log(1 + (len(rows) - frequency[term] + 0.5) / (frequency[term] + 0.5))
                    score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / avg))
            if score:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [Passage(**row) for _, row in scored[:max(0, min(limit, 5))]]
