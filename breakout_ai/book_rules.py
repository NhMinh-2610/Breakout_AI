"""Recognize explicit, measurable book rules with exact sentence provenance.

This is a bounded local rule reader, not proof of comprehension or fine-tuning.
No default trading percentage or moving-average window is invented.
"""

from dataclasses import asdict, dataclass
import hashlib
import re

from breakout_ai.books import Passage
from breakout_ai.knowledge import normalize

RULE_LABELS = {
    "stop_loss_pct": "Bán khi khoản lỗ chạm ngưỡng trong sách",
    "take_profit_pct": "Xem xét chốt lời theo ngưỡng trong sách",
    "buy_above_ma": "Mua khi giá nằm trên đường trung bình trong sách",
    "buy_cross_ma": "Mua khi giá cắt lên đường trung bình trong sách",
    "sell_below_ma": "Bán khi giá xuống dưới đường trung bình trong sách",
    "sell_cross_ma": "Bán khi giá cắt xuống đường trung bình trong sách",
    "margin_of_safety_pct": "Mua khi giá có biên an toàn so với giá trị ước tính",
}


@dataclass(frozen=True)
class BookRule:
    id: str
    kind: str
    value: float
    quote: str
    citation: dict

    def label(self) -> str:
        unit = " ngày" if "_ma" in self.kind else "%"
        return f"{RULE_LABELS[self.kind]} · {self.value:g}{unit}"

    def payload(self) -> dict:
        return {**asdict(self), "label": self.label()}


def learn_rules(passages: list[Passage]) -> list[BookRule]:
    result, seen = [], set()
    for passage in passages:
        # Decimal dots must not be split as sentence punctuation.
        sentences = re.split(r"(?<=[.!?])\s+|[\r\n]+", passage.text)
        for sentence in sentences:
            sentence = sentence.strip()
            if not 15 <= len(sentence) <= 650:
                continue
            text = normalize(sentence)
            if re.search(r"\b(khong|chua|not|dont|don t|shouldn t|never|avoid|vi du|example|gia dinh|hypothetical|co the|might|could|between|tu .* den)\b", text):
                continue
            # Do not silently turn a range, exception or compound instruction into a rule.
            if re.search(r"\b(or|hoac|unless|except|tru khi|nhung|however|and|va|provided)\b", text) or re.search(r"\d\s*(?:[-–—/]|to|đến)\s*\d", sentence):
                continue
            if re.search(r"\b(less than|at most|it hon|toi da|volume|khoi luong|rsi|roe|eps|earnings)\b", text):
                continue
            sell = bool(re.search(r"\b(ban|sell|cut loss|stop loss|cat lo|chot loi|take profit)\b", text))
            buy = bool(re.search(r"\b(mua|buy|purchase)\b", text))
            conditional = bool(re.search(r"\b(khi|neu|if|when|once|whenever|at|only|chi)\b", text))
            kind, value = None, None
            percentages = re.findall(r"(?<![\d.,])(\d{1,3}(?:[.,]\d+)?)\s*(?:%|percent\b|per cent\b)", sentence, flags=re.I)
            # Multiple thresholds/ranges are ambiguous; do not guess one.
            if len(percentages) == 1 and conditional:
                percentage = float(percentages[0].replace(",", "."))
                entry_anchor = bool(re.search(r"\b(gia mua|gia von|purchase price|buy price|entry price|cost basis)\b", text))
                if 1 <= percentage <= 50 and sell and entry_anchor and re.search(r"\b(giam|lo|loss|falls|fall|drops|drop|below|declines)\b", text):
                    kind, value = "stop_loss_pct", percentage
                elif 1 <= percentage <= 100 and sell and entry_anchor and re.search(r"\b(tang|lai|loi|gain|gains|rises|profit|above)\b", text):
                    kind, value = "take_profit_pct", percentage
                elif 1 <= percentage <= 70 and buy and re.search(r"\b(gia tri noi tai|intrinsic value|estimated value)\b", text) and re.search(r"\b(thap hon|duoi|below|discount|bien an toan|margin of safety)\b", text):
                    kind, value = "margin_of_safety_pct", percentage
            if not kind and conditional and not percentages and re.search(r"\b(gia|price|prices)\b", text):
                matches = re.findall(r"\b(?:sma|ma|moving average|duong trung binh|trung binh dong)\s*(\d{1,3})\b", text)
                # Also understand '20-day moving average'.
                matches += re.findall(r"\b(\d{1,3})\s*(?:day|days|ngay)\s*(?:moving average|sma|ma)\b", text)
                if len(set(matches)) == 1 and 5 <= int(matches[0]) <= 250:
                    window = int(matches[0])
                    if buy and re.search(r"\b(cat len|vuot len|crosses above|cross above)\b", text):
                        kind, value = "buy_cross_ma", window
                    elif sell and re.search(r"\b(cat xuong|crosses below|cross below)\b", text):
                        kind, value = "sell_cross_ma", window
                    elif buy and re.search(r"\b(tren|above)\b", text):
                        kind, value = "buy_above_ma", window
                    elif sell and re.search(r"\b(duoi|below)\b", text):
                        kind, value = "sell_below_ma", window
            if not kind:
                continue
            identity = (kind, value)
            if identity in seen:
                continue
            seen.add(identity)
            identifier = hashlib.sha256((passage.id + sentence).encode()).hexdigest()[:16]
            result.append(BookRule(identifier, kind, value, sentence, passage.citation()))
    return result
