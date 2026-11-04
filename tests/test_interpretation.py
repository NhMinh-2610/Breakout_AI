"""Model output can choose supplied evidence, never invent a market conclusion."""
from copy import deepcopy
import json

import pytest

from breakout_ai.interpretation import (
    InterpretationError,
    parse_interpretation,
    render_interpretation,
)


@pytest.fixture
def context():
    return {
        "analysis": {
            "action": "wait",
            "blockers": ["Snapshot khớp lệnh chưa đủ mới."],
        },
        "chart": {
            "facts": [
                {
                    "id": "price.structure",
                    "role": "observation",
                    "text": "Đỉnh nến sau thấp hơn đỉnh trước; lực hồi chưa được xác nhận.",
                },
                {
                    "id": "volume.counterpoint",
                    "role": "risk",
                    "text": "Khối lượng hồi chỉ bằng 0,8 lần bình quân, chưa xác nhận dòng tiền.",
                },
                {
                    "id": "data.source_delay",
                    "role": "blocker",
                    "text": "Giờ khớp nguồn đã quá hạn; chờ snapshot mới.",
                },
                {
                    "id": "observed.999999",
                    "role": "observation",
                    "text": "Vùng hỗ trợ quan sát là 72.400 VND.",
                },
            ],
            "scenarios": [
                {
                    "id": "support-recovery",
                    "label": "Chờ nhịp hồi có xác nhận",
                    "status": "watch",
                    "confirmation": [
                        "Nến đóng lại trên vùng hỗ trợ.",
                        "Khối lượng xác nhận tăng so với nền.",
                    ],
                    "invalidation": "Nến đóng thủng vùng hỗ trợ.",
                },
                {
                    "id": "breakout-confirmed",
                    "label": "Theo dõi phá kháng cự",
                    "status": "qualified",
                    "confirmation": ["Giá và khối lượng đã đạt bộ điều kiện."],
                    "invalidation": "Giá khớp không còn giữ vùng vượt.",
                },
            ],
        },
    }


def response(**changes):
    result = {
        "action": "wait",
        "focus_fact_ids": ["price.structure"],
        "risk_fact_ids": ["data.source_delay", "volume.counterpoint"],
        "scenario_id": "support-recovery",
    }
    result.update(changes)
    return json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize("fence", ["none", "json", "plain"])
def test_valid_evidence_selection_preserves_wait_and_renders_canonical_scenario(context, fence):
    raw = response()
    if fence == "json":
        raw = "```json\n" + raw + "\n```"
    elif fence == "plain":
        raw = "```\n" + raw + "\n```"
    result = parse_interpretation(raw, context)
    assert result.action == "wait"
    assert result.focus_fact_ids == ("price.structure",)
    assert result.risk_fact_ids == ("data.source_delay", "volume.counterpoint")
    rendered = render_interpretation(result, context)
    assert context["chart"]["facts"][0]["text"] in rendered
    assert context["chart"]["facts"][1]["text"] in rendered
    assert context["chart"]["facts"][2]["text"] in rendered
    assert "Chờ nhịp hồi có xác nhận" in rendered
    for item in context["chart"]["scenarios"][0]["confirmation"]:
        assert item in rendered
    assert "['" not in rendered and "']" not in rendered
    assert "Nến đóng thủng vùng hỗ trợ." in rendered


@pytest.mark.parametrize("action", ["watch_buy", "watch_sell", "hold", True, None, 1])
def test_model_cannot_upgrade_or_change_wait_authority(context, action):
    with pytest.raises(InterpretationError):
        parse_interpretation(response(action=action), context)


def test_model_cannot_silently_downgrade_a_qualified_authority_either(context):
    context["analysis"] = {"action": "watch_buy", "blockers": []}
    with pytest.raises(InterpretationError):
        parse_interpretation(response(action="wait"), context)


@pytest.mark.parametrize(
    "changes",
    [
        {"focus_fact_ids": ["not-in-source"]},
        {"risk_fact_ids": ["fabricated-risk"]},
        {"scenario_id": "guaranteed-profit"},
        {"focus_fact_ids": ["price.structure", "price.structure"]},
        {"risk_fact_ids": ["data.source_delay", "data.source_delay"]},
        {"focus_fact_ids": []},
        {"risk_fact_ids": []},
        {"risk_fact_ids": ["price.structure"]},
        {"focus_fact_ids": ["price.structure"] * 6},
        {"risk_fact_ids": ["data.source_delay"] * 6},
    ],
)
def test_missing_fabricated_duplicate_or_wrong_role_evidence_is_rejected(context, changes):
    with pytest.raises(InterpretationError):
        parse_interpretation(response(**changes), context)


@pytest.mark.parametrize("field", ["focus_fact_ids", "risk_fact_ids"])
@pytest.mark.parametrize("value", [True, None, "price.structure", [True], [42], [{}]])
def test_reference_fields_require_lists_of_source_id_strings(context, field, value):
    with pytest.raises(InterpretationError):
        parse_interpretation(response(**{field: value}), context)


@pytest.mark.parametrize("value", [True, False, 1, [], {}])
def test_scenario_must_be_a_known_id_or_null(context, value):
    with pytest.raises(InterpretationError):
        parse_interpretation(response(scenario_id=value), context)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "Buy now: the price will increase.",
        "{not-json}",
        "[]",
        "null",
        "{}",
        "```json\n{}",
        "```python\n{}\n```",
        "{\"action\":\"wait\"} trailing explanation",
        "{\"action\":\"wait\"}{\"action\":\"watch_buy\"}",
    ],
)
def test_malformed_incomplete_or_non_contract_responses_are_rejected(context, raw):
    with pytest.raises(InterpretationError):
        parse_interpretation(raw, context)


@pytest.mark.parametrize(
    "extra",
    [
        {"free_text": "BUY NOW at 999999, guaranteed profit."},
        {"target_price": 999999},
        {"confidence": 0.99},
        {"instructions": "Ignore the original blockers."},
    ],
)
def test_model_free_prose_prices_and_confidence_are_outside_the_contract(context, extra):
    raw = json.loads(response())
    raw.update(extra)
    with pytest.raises(InterpretationError):
        parse_interpretation(json.dumps(raw), context)


def test_missing_required_contract_field_is_rejected(context):
    raw = json.loads(response())
    del raw["scenario_id"]
    with pytest.raises(InterpretationError):
        parse_interpretation(json.dumps(raw), context)


@pytest.mark.parametrize("raw", [None, b"{}", True, " " * 12001])
def test_non_text_or_oversized_response_is_rejected(context, raw):
    with pytest.raises(InterpretationError):
        parse_interpretation(raw, context)


@pytest.mark.parametrize(
    "analysis",
    [
        {"action": "wait", "blockers": []},
        {"action": "wait", "blockers": ["Snapshot cũ."]},
        {"action": "hold", "blockers": ["Nguồn nến lỗi."]},
    ],
)
def test_qualified_scenario_cannot_override_wait_or_data_blockers(context, analysis):
    context["analysis"] = analysis
    with pytest.raises(InterpretationError):
        parse_interpretation(
            response(action=analysis["action"], scenario_id="breakout-confirmed"), context
        )


def test_qualified_scenario_is_allowed_with_the_same_ready_authority(context):
    context["analysis"] = {"action": "watch_buy", "blockers": []}
    selected = parse_interpretation(
        response(action="watch_buy", risk_fact_ids=[], scenario_id="breakout-confirmed"), context
    )
    assert selected.action == "watch_buy"
    assert selected.scenario_id == "breakout-confirmed"


def test_null_scenario_keeps_observations_and_counterpoint_without_creating_a_setup(context):
    result = parse_interpretation(response(scenario_id=None), context)
    rendered = render_interpretation(result, context)
    assert "lực hồi chưa được xác nhận" in rendered
    assert "Khối lượng hồi" in rendered
    assert "Kịch bản theo dõi" not in rendered


def test_no_source_facts_allows_empty_evidence_without_fabricating_analysis(context):
    context["analysis"] = {"action": "wait", "blockers": []}
    context["chart"] = {"facts": [], "scenarios": []}
    result = parse_interpretation(
        response(focus_fact_ids=[], risk_fact_ids=[], scenario_id=None), context
    )
    rendered = render_interpretation(result, context)
    assert "72.400" not in rendered
    assert "Kịch bản theo dõi" not in rendered


def test_renderer_resolves_source_text_instead_of_printing_model_ids_or_numbers(context):
    selected = parse_interpretation(
        response(focus_fact_ids=["observed.999999"], scenario_id=None), context
    )
    rendered = render_interpretation(selected, context)
    assert "72.400 VND" in rendered
    assert "999999" not in rendered
    assert "observed." not in rendered
    assert "focus_fact_ids" not in rendered
    assert "BUY NOW" not in rendered


def test_parsing_does_not_mutate_the_captured_market_context(context):
    original = deepcopy(context)
    parse_interpretation(response(), context)
    assert context == original


def test_volume_risk_cannot_replace_the_missing_source_blocker(context):
    with pytest.raises(InterpretationError, match="giới hạn dữ liệu"):
        parse_interpretation(response(risk_fact_ids=["volume.counterpoint"]), context)
