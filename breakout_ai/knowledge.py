"""Small, inspectable lexical retrieval. No vector model or live browsing."""

from collections import Counter
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re
import unicodedata

from breakout_ai.config import ROOT

STOPWORDS = set("la gi va cua cho mot cac ve toi minh ban hay the nao co khong duoc voi khi thi nay do them vi du in the is a an of to what how for and please explain".split())


def normalize(text: str) -> str:
    text = text.lower().replace("đ", "d")
    for original, replacement in (("p/e", " pe "), ("p/b", " pb "), ("10-k", "10k"), ("10-q", "10q"), ("8-k", "8k")):
        text = text.replace(original, replacement)
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def tokens(text: str) -> list[str]:
    words = [w for w in normalize(text).split() if w not in STOPWORDS]
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    market: str
    keywords: list[str]
    explanation: str
    example: str
    caveat: str
    question: str
    source_title: str
    source_url: str
    reviewed_at: str

    def citation(self) -> dict:
        return {key: asdict(self)[key] for key in ("id", "title", "source_title", "source_url", "reviewed_at")}


class KnowledgeBase:
    def __init__(self, path: Path | None = None):
        raw = json.loads((path or ROOT / "content" / "knowledge.json").read_text(encoding="utf-8"))
        self.articles = [Article(**entry) for entry in raw]
        if len({a.id for a in self.articles}) != len(self.articles):
            raise ValueError("Mã tài liệu bị trùng.")
        self._terms = [Counter(tokens(" ".join([a.title] * 3 + a.keywords * 4 + [a.explanation]))) for a in self.articles]
        self._lengths = [sum(t.values()) for t in self._terms]
        self._average = sum(self._lengths) / max(len(self._lengths), 1)
        self._frequency = Counter(term for doc in self._terms for term in doc)

    def search(self, query: str, market: str = "BOTH", limit: int = 3) -> list[Article]:
        if market not in {"VN", "US", "BOTH"}:
            raise ValueError("Thị trường không hợp lệ.")
        terms = set(tokens(query))
        scored = []
        count = len(self.articles)
        for article, counts, length in zip(self.articles, self._terms, self._lengths):
            if market != "BOTH" and article.market not in {"GLOBAL", market}:
                continue
            score = 0.0
            for term in terms:
                frequency = counts[term]
                if frequency:
                    idf = math.log(1 + (count - self._frequency[term] + 0.5) / (self._frequency[term] + 0.5))
                    denominator = frequency + 1.5 * (0.25 + 0.75 * length / self._average)
                    score += idf * frequency * 2.5 / denominator
            if score > 0:
                scored.append((score, article))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [article for _, article in scored[:limit]]
