"""Validate model-selected chart evidence before rendering any market conclusion."""

from dataclasses import dataclass
import json


class InterpretationError(ValueError):
    """A model response does not refer exclusively to the supplied observation."""


@dataclass(frozen=True)
class Interpretation:
    action: str
    focus_fact_ids: tuple[str, ...]
    risk_fact_ids: tuple[str, ...]
    scenario_id: str | None

    def payload(self) -> dict:
        return {
            "action": self.action,
            "focus_fact_ids": list(self.focus_fact_ids),
            "risk_fact_ids": list(self.risk_fact_ids),
            "scenario_id": self.scenario_id,
        }


def parse_interpretation(text: str, context: dict) -> Interpretation:
    if not isinstance(text, str) or len(text) > 12_000:
        raise InterpretationError("Phản hồi AI vượt giới hạn.")
    raw = text.strip()
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[7:-3].strip()
    elif raw.startswith("```") and raw.endswith("```"):
        raw = raw[3:-3].strip()
    try:
        result = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise InterpretationError("Phản hồi AI chưa đúng cấu trúc.") from exc
    expected = {"action", "focus_fact_ids", "risk_fact_ids", "scenario_id"}
    if not isinstance(result, dict) or set(result) != expected:
        raise InterpretationError("Phản hồi AI có trường ngoài hợp đồng.")
    analysis = context.get("analysis", {})
    action = analysis.get("action", "wait")
    if result["action"] != action:
        raise InterpretationError("AI đã đổi kết luận của bộ kiểm tra dữ liệu.")
    chart = context.get("chart", {})
    facts = {fact["id"]: fact for fact in chart.get("facts", [])}

    def references(name, *, risks=False):
        values = result[name]
        if (
            not isinstance(values, list)
            or len(values) > 5
            or any(not isinstance(value, str) for value in values)
            or len(set(values)) != len(values)
            or any(value not in facts for value in values)
        ):
            raise InterpretationError("AI dẫn bằng chứng không có trong biểu đồ.")
        if risks and any(
            facts[value].get("role") not in {"risk", "blocker"} for value in values
        ):
            raise InterpretationError("AI chưa dẫn đúng bằng chứng phản biện.")
        return tuple(values)

    focus = references("focus_fact_ids")
    risks = references("risk_fact_ids", risks=True)
    if facts and not focus:
        raise InterpretationError("AI chưa nêu bằng chứng cho nhận định.")
    if analysis.get("blockers") and not any(
        facts[reference].get("role") == "blocker" for reference in risks
    ):
        raise InterpretationError("AI bỏ qua giới hạn dữ liệu.")
    scenarios = {scenario["id"]: scenario for scenario in chart.get("scenarios", [])}
    selected = result["scenario_id"]
    if selected is not None:
        if not isinstance(selected, str) or selected not in scenarios:
            raise InterpretationError("AI tạo kịch bản không được cung cấp.")
        if (analysis.get("blockers") or action == "wait") and scenarios[selected].get(
            "status"
        ) == "qualified":
            raise InterpretationError("AI xác nhận kịch bản khi dữ liệu chưa sẵn sàng.")
    return Interpretation(action, focus, risks, selected)


def render_interpretation(result: Interpretation, context: dict) -> str:
    """Render canonical source text; arbitrary model prose never becomes advice."""
    chart = context.get("chart", {})
    facts = {fact["id"]: fact for fact in chart.get("facts", [])}
    lines = ["**AI đọc cấu trúc biểu đồ:**"]
    lines.extend("- " + facts[reference]["text"] for reference in result.focus_fact_ids)
    if result.risk_fact_ids:
        lines.append("**Phản biện và điều cần chờ:**")
        lines.extend(
            "- " + facts[reference]["text"] for reference in result.risk_fact_ids
        )
    if result.scenario_id:
        scenario = next(
            item for item in chart["scenarios"] if item["id"] == result.scenario_id
        )
        confirmation = scenario["confirmation"]
        if isinstance(confirmation, list):
            confirmation = "; ".join(confirmation)
        lines.extend(
            [
                "**Kịch bản theo dõi: " + scenario["label"] + "**",
                "Xác nhận: " + str(confirmation),
                "Vô hiệu: " + str(scenario["invalidation"]),
            ]
        )
    return "\n\n".join(lines)
