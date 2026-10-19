"""Regression checks for the exchange board's display contract and data honesty."""
from copy import deepcopy
from dataclasses import dataclass, field
from html.parser import HTMLParser

import pytest

from breakout_ai.priceboard import (
    board_table, depth_table, format_number, price_class, time_label,
)


class TableParser(HTMLParser):
    """Collect cells while retaining the distinction between headers and data."""

    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.rows = {"thead": [], "tbody": []}
        self.tags = []
        self.section = None
        self.row = None
        self.cell = None
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag in self.rows:
            self.section = tag
        elif tag == "tr" and self.section:
            self.row = {"attrs": dict(attrs), "cells": []}
            self.rows[self.section].append(self.row)
        elif tag in ("td", "th") and self.row is not None:
            self.cell = {"tag": tag, "attrs": dict(attrs), "text": ""}
            self.row["cells"].append(self.cell)

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.cell = None
        elif tag == "tr":
            self.row = None
        elif tag == self.section:
            self.section = None


@pytest.fixture
def quote():
    return {
        "symbol": "FPT", "exchange": "HOSE",
        "reference": 100_000, "ceiling": 107_000, "floor": 93_000,
        "last": 101_500, "change": 1_500, "change_pct": 1.5,
        "match_volume": 250, "total_volume": 1_234_567,
        "total_value": 1_234_567_890,
        "open": 99_000, "high": 104_000, "low": 98_000,
        "average": 101_250,
        "foreign_buy_volume": 14_000, "foreign_sell_volume": 7_500,
        "bids": [
            {"price": 101_000, "volume": 1_200},
            {"price": 100_500, "volume": 2_300},
            {"price": 100_000, "volume": 3_400},
        ],
        "asks": [
            {"price": 102_000, "volume": 4_500},
            {"price": 102_500, "volume": 5_600},
            {"price": 103_000, "volume": 6_700},
        ],
        "source_timestamp": "2026-10-19T02:35:10Z",
        "stale": False, "depth_stale": False,
    }


@pytest.mark.parametrize(("full", "column_count"), [(True, 29), (False, 23)])
def test_grouped_headers_and_body_have_matching_column_counts(quote, full, column_count):
    document = TableParser(board_table([quote], full=full))
    headers = document.rows["thead"]
    assert len(headers) == 2
    first, second = [row["cells"] for row in headers]
    assert sum(int(cell["attrs"].get("colspan", 1)) for cell in first) == column_count
    fixed = sum(int(cell["attrs"].get("colspan", 1)) for cell in first
                if cell["attrs"].get("rowspan") == "2")
    assert fixed + sum(int(cell["attrs"].get("colspan", 1)) for cell in second) == column_count
    assert len(document.rows["tbody"][0]["cells"]) == column_count
    groups = {cell["text"]: int(cell["attrs"]["colspan"])
              for cell in first if "colspan" in cell["attrs"]}
    assert groups["Bên mua"] == 6
    assert groups["Khớp lệnh"] == 4
    assert groups["Bên bán"] == 6
    assert ("Giá trong phiên" in groups) is full
    assert ("Nước ngoài (CP)" in groups) is full
    assert document.rows["tbody"][0]["cells"][0]["attrs"]["scope"] == "row"


def test_full_vnd_values_are_scaled_only_for_display(quote):
    cells = TableParser(board_table([quote])).rows["tbody"][0]["cells"]
    assert [cell["text"] for cell in cells[1:4]] == ["107.00", "93.00", "100.00"]
    assert cells[10]["text"] == "101.50"
    assert cells[11]["text"] == "250"
    assert cells[12]["text"] == "1.50"
    assert cells[13]["text"] == "1.50"
    assert cells[20]["text"] == "1,234,567"
    assert cells[21]["text"] == "1,234.57"
    assert [cell["text"] for cell in cells[22:28]] == [
        "99.00", "104.00", "98.00", "101.25", "14,000", "7,500",
    ]
    assert quote["last"] == 101_500  # The renderer never changes canonical source data.


def test_book_orders_bids_three_to_one_and_asks_one_to_three(quote):
    cells = TableParser(board_table([quote])).rows["tbody"][0]["cells"]
    assert [cells[index]["text"] for index in (4, 6, 8)] == ["100.00", "100.50", "101.00"]
    assert [cells[index]["text"] for index in (14, 16, 18)] == ["102.00", "102.50", "103.00"]
    assert [cells[index]["text"] for index in (5, 7, 9)] == ["3,400", "2,300", "1,200"]
    assert [cells[index]["text"] for index in (15, 17, 19)] == ["4,500", "5,600", "6,700"]


@pytest.mark.parametrize(("price", "expected"), [
    (100_000, "price-ref"), (107_000, "price-ceiling"),
    (93_000, "price-floor"), (101_000, "price-up"),
    (99_000, "price-down"), (None, ""), (float("nan"), ""),
    (float("inf"), ""), (True, ""), (0, ""),
])
def test_price_colors_follow_reference_and_exchange_limits(quote, price, expected):
    assert price_class(price, quote) == expected


def test_rendered_match_price_uses_exchange_color(quote):
    for value, expected in ((107_000, "price-ceiling"), (93_000, "price-floor"),
                            (100_000, "price-ref"), (101_500, "price-up"),
                            (99_500, "price-down")):
        row = deepcopy(quote)
        row["last"] = value
        cells = TableParser(board_table([row])).rows["tbody"][0]["cells"]
        assert expected in cells[10]["attrs"]["class"].split()


def test_selection_and_old_source_are_visible_without_inventing_freshness(quote):
    quote["stale"] = True
    table = TableParser(board_table([quote], selected="FPT"))
    row = table.rows["tbody"][0]
    assert {"is-stale", "is-selected"} <= set(row["attrs"]["class"].split())
    assert row["cells"][-1]["text"] == "09:35:10 · 19/10 · bản cũ"


def test_stale_depth_is_hidden_but_last_known_trade_remains(quote):
    quote["depth_stale"] = True
    row = TableParser(board_table([quote])).rows["tbody"][0]
    book_cells = [row["cells"][index] for index in (*range(4, 10), *range(14, 20))]
    assert all(cell["text"] == "—" for cell in book_cells)
    assert all("Độ sâu cũ" in cell["attrs"]["title"] for cell in book_cells)
    assert all(not ({"price-up", "price-down", "price-ref"} &
                    set(cell["attrs"]["class"].split())) for cell in book_cells)
    assert row["cells"][10]["text"] == "101.50"
    assert "is-stale" not in row["attrs"]["class"].split()


def test_missing_symbol_keeps_requested_row_with_blanks():
    document = TableParser(board_table([], symbols=["FPT"]))
    row = document.rows["tbody"][0]
    assert len(row["cells"]) == 29
    assert row["cells"][0]["text"] == "FPT—"
    assert all(cell["text"] == "—" for cell in row["cells"][1:-1])
    assert row["cells"][-1]["text"] == "Chưa có giờ nguồn"


@pytest.mark.parametrize(("full", "expected"), [(True, "29"), (False, "23")])
def test_empty_filter_has_one_message_spanning_the_board(full, expected):
    rows = TableParser(board_table([], full=full)).rows["tbody"]
    assert len(rows) == 1 and len(rows[0]["cells"]) == 1
    assert rows[0]["cells"][0]["attrs"]["colspan"] == expected
    assert "Không có mã phù hợp" in rows[0]["cells"][0]["text"]


def test_untrusted_symbol_exchange_and_numeric_fields_are_escaped(quote):
    quote["symbol"] = '<img src=x onerror="alert(1)">'
    quote["exchange"] = "<script>alert(2)</script>"
    quote["last"] = '<svg onload="alert(3)">'
    markup = board_table([quote], selected=quote["symbol"])
    table = TableParser(markup)
    assert not {"img", "script", "svg"} & set(table.tags)
    assert "&lt;img" in markup and "&lt;script&gt;" in markup
    assert 'onerror="alert(1)"' not in markup
    assert table.rows["tbody"][0]["cells"][10]["text"] == "—"


@pytest.mark.parametrize("value", [None, True, False, "bad", float("nan"), float("inf"), -float("inf")])
def test_invalid_numeric_values_render_as_missing(value):
    assert format_number(value) == "—"


@pytest.mark.parametrize("value", [None, "", "not-a-time", "2026-10-19T02:35:10"])
def test_missing_or_ambiguous_timestamps_never_claim_a_source_time(value):
    assert time_label(value) == "Chưa có giờ nguồn"


def test_depth_detail_shows_three_real_levels_in_full_share_units(quote):
    rows = TableParser(depth_table(quote)).rows["tbody"]
    assert len(rows) == 3 and all(len(row["cells"]) == 4 for row in rows)
    assert [cell["text"] for cell in rows[0]["cells"]] == [
        "1,200", "101.00", "102.00", "4,500",
    ]


def test_depth_detail_with_missing_levels_uses_blanks(quote):
    quote["bids"], quote["asks"] = [], [{"price": None, "volume": None}]
    rows = TableParser(depth_table(quote)).rows["tbody"]
    assert len(rows) == 3
    assert all(cell["text"] == "—" for row in rows for cell in row["cells"])


def test_depth_detail_refuses_stale_order_book(quote):
    quote["depth_stale"] = True
    markup = depth_table(quote)
    assert "Sổ lệnh đang cũ" in markup
    assert "<table" not in markup and "101.00" not in markup


def test_dataclass_quotes_and_nested_levels_use_same_display_contract():
    @dataclass
    class Level:
        price: float
        volume: float

    @dataclass
    class Quote:
        symbol: str = "FPT"
        reference: float = 100_000
        bids: list = field(default_factory=lambda: [Level(99_000, 500)])
        asks: list = field(default_factory=lambda: [Level(101_000, 700)])

    quote = Quote()
    board = TableParser(board_table([quote])).rows["tbody"][0]["cells"]
    assert board[8]["text"] == "99.00" and board[14]["text"] == "101.00"
    detail = TableParser(depth_table(quote)).rows["tbody"]
    assert [cell["text"] for cell in detail[0]["cells"]] == ["500", "99.00", "101.00", "700"]
