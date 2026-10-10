import pytest

from breakout_ai.knowledge import KnowledgeBase


@pytest.mark.parametrize("query,expected", [
    ("P/E là gì?", "K02"),
    ("pe va eps la gi", "K02"),
    ("P/B và BVPS", "K03"),
    ("Đa dạng hóa danh mục", "K05"),
    ("ETF hoạt động thế nào", "K06"),
    ("SEC EDGAR 10-K", "K07"),
    ("HOSE công bố thông tin", "K08"),
    ("Tỷ giá USD VND", "K09"),
])
def test_supported_topics_retrieve_expected_source(query, expected):
    assert KnowledgeBase().search(query)[0].id == expected


def test_market_filter_keeps_global_and_excludes_other_market():
    kb = KnowledgeBase()
    assert "K07" not in {a.id for a in kb.search("SEC EDGAR 10-K", "VN")}
    assert kb.search("P/E", "US")[0].id == "K02"


def test_unrelated_question_returns_no_documents():
    assert KnowledgeBase().search("Recipe pancakes chocolate") == []
