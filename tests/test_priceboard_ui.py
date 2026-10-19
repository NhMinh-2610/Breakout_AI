"""Offline UI regression coverage for the live snapshot board."""
import json
from types import SimpleNamespace

import httpx
import pytest

from breakout_ai.realtime import BoardSnapshot, LiveQuote, PriceLevel, RealtimeService
from breakout_ai.storage import Store
from test_app import app, button
from test_priceboard import TableParser


STAMP = "2026-10-19T02:35:10+00:00"


def quote(symbol, exchange, *, change_pct=1.5, total_volume=1_000_000):
    reference = 100_000
    last = reference * (1 + change_pct / 100)
    return LiveQuote(
        symbol=symbol, exchange=exchange, reference=reference,
        ceiling=107_000, floor=93_000, last=last,
        change=last - reference, change_pct=change_pct,
        match_volume=250, total_volume=total_volume,
        total_value=last * total_volume, open=100_000,
        high=max(last, 100_000), low=min(last, 100_000), average=100_500,
        foreign_buy_volume=20_000, foreign_sell_volume=10_000,
        bids=[PriceLevel(99_900, 500), PriceLevel(99_800, 700), PriceLevel(99_700, 900)],
        asks=[PriceLevel(100_100, 600), PriceLevel(100_200, 800), PriceLevel(100_300, 1_000)],
        source_timestamp=STAMP, received_at=STAMP, stale=False,
        depth_timestamp=STAMP, depth_stale=False,
    )


def board_markup(at):
    return next(item.value for item in at.markdown if '<table class="priceboard-table">' in item.value)


def board_rows(at):
    return TableParser(board_markup(at)).rows["tbody"]


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    symbols = ["FPT", "VCB", "PVS", "ACV"]
    quotes = [
        quote("FPT", "HOSE", change_pct=1.5, total_volume=1_000_000),
        quote("VCB", "HOSE", change_pct=-2, total_volume=5_000_000),
        quote("PVS", "HNX", change_pct=3, total_volume=2_000_000),
        quote("ACV", "UPCOM", change_pct=0, total_volume=500_000),
    ]
    store = Store(tmp_path / "ui.sqlite3", "test-ui")
    with store.connection() as db:
        db.execute("CREATE TABLE board_preferences (workspace TEXT PRIMARY KEY, symbols TEXT NOT NULL)")
        db.execute("INSERT INTO board_preferences VALUES (?,?)", ("test-ui", json.dumps(symbols)))
    calls = {"fetch": [], "cached": []}

    def snapshot(selected, poll_seconds):
        return BoardSnapshot(
            quotes=[item for item in quotes if item.symbol in selected],
            fetched_at=STAMP, poll_seconds=poll_seconds,
        )

    def fetch(self, selected, force=False):
        calls["fetch"].append((list(selected), force, self.poll_seconds))
        return snapshot(selected, self.poll_seconds)

    def cached(self, selected):
        calls["cached"].append(list(selected))
        return snapshot(selected, self.poll_seconds)

    def forbid_network(*args, **kwargs):
        raise AssertionError("UI tests must never request an external network source.")

    monkeypatch.setattr(RealtimeService, "fetch", fetch)
    monkeypatch.setattr(RealtimeService, "cached", cached)
    monkeypatch.setattr(httpx.Client, "send", forbid_network)

    def open_board(enabled=True):
        monkeypatch.setenv("MARKET_DATA_ENABLED", "true" if enabled else "false")
        at = app(monkeypatch, tmp_path)
        at.sidebar.radio[0].set_value("Thị trường").run()
        assert not at.exception
        return at

    return SimpleNamespace(open=open_board, calls=calls, store=store, symbols=symbols, quotes=quotes)


def test_market_defaults_to_full_live_board_without_daily_chart(workspace):
    at = workspace.open()
    assert at.radio(key="market_view").value == "Bảng điện Việt Nam"
    assert at.checkbox(key="board_full").value
    rows = board_rows(at)
    assert len(rows) == 4 and all(len(row["cells"]) == 29 for row in rows)
    assert at.selectbox(key="board_selected").options == ["ACV", "FPT", "PVS", "VCB"]
    assert not at.get("arrow_vega_lite_chart")
    assert not any(item.key == "chart_symbol" for item in at.text_input)
    assert workspace.calls["fetch"] == [(workspace.symbols, False, 5)]
    assert any("Snapshot DNSE · cập nhật 5 giây" in item.value for item in at.markdown)
    assert any("chưa phải luồng đẩy từng giao dịch" in item.value for item in at.caption)


def test_exchange_search_sort_and_selection_drive_rows_and_details(workspace):
    at = workspace.open()
    at.selectbox(key="board_sort").set_value("Tăng giá nhiều nhất").run()
    assert [row["cells"][0]["text"] for row in board_rows(at)] == ["PVSHNX", "FPTHOSE", "ACVUPCOM", "VCBHOSE"]
    assert at.selectbox(key="board_selected").options == ["ACV", "FPT", "PVS", "VCB"]
    at.selectbox(key="board_selected").set_value("FPT").run()
    assert any(item.label == "Giá khớp · VND / CP" and item.value == "101,500" for item in at.metric)
    rows = board_rows(at)
    selected = [row for row in rows if "is-selected" in row["attrs"]["class"].split()]
    assert len(selected) == 1 and selected[0]["cells"][0]["text"] == "FPTHOSE"
    at.selectbox(key="board_sort").set_value("Khối lượng lớn nhất").run()
    assert [row["cells"][0]["text"] for row in board_rows(at)] == ["VCBHOSE", "PVSHNX", "FPTHOSE", "ACVUPCOM"]
    assert at.selectbox(key="board_selected").options == ["ACV", "FPT", "PVS", "VCB"]
    assert at.selectbox(key="board_selected").value == "FPT"
    at.selectbox(key="board_exchange").set_value("HOSE").run()
    assert at.selectbox(key="board_selected").options == ["FPT", "VCB"]
    assert at.selectbox(key="board_selected").value == "FPT"
    at.text_input(key="board_search").set_value("fp").run()
    assert at.selectbox(key="board_selected").options == ["FPT"]
    assert len(board_rows(at)) == 1
    at.text_input(key="board_search").set_value("")
    at.selectbox(key="board_exchange").set_value("HNX").run()
    assert not at.exception and at.selectbox(key="board_selected").options == ["PVS"]
    assert any(item.label == "Giá khớp · VND / CP" and item.value == "103,000" for item in at.metric)


def test_live_rank_changes_and_filter_membership_preserve_selected_security(workspace):
    at = workspace.open()
    at.selectbox(key="board_selected").set_value("FPT").run()
    at.selectbox(key="board_sort").set_value("Tăng giá nhiều nhất").run()
    assert board_rows(at)[0]["cells"][0]["text"] == "PVSHNX"
    assert at.selectbox(key="board_selected").value == "FPT"

    # The next snapshot changes the leading gainer while the detail stays on FPT.
    workspace.quotes[1] = quote("VCB", "HOSE", change_pct=4, total_volume=5_000_000)
    at.run()
    assert not at.exception
    assert board_rows(at)[0]["cells"][0]["text"] == "VCBHOSE"
    assert at.selectbox(key="board_selected").value == "FPT"

    at.selectbox(key="board_sort").set_value("Khối lượng lớn nhất").run()
    assert board_rows(at)[0]["cells"][0]["text"] == "VCBHOSE"
    workspace.quotes[0] = quote("FPT", "HOSE", change_pct=1.5, total_volume=8_000_000)
    at.run()
    assert not at.exception
    assert board_rows(at)[0]["cells"][0]["text"] == "FPTHOSE"
    assert at.selectbox(key="board_selected").value == "FPT"

    # Changing available options also preserves a selection that remains valid.
    at.selectbox(key="board_exchange").set_value("HOSE").run()
    assert at.selectbox(key="board_selected").options == ["FPT", "VCB"]
    assert at.selectbox(key="board_selected").value == "FPT"
    at.text_input(key="board_search").set_value("FP").run()
    assert at.selectbox(key="board_selected").value == "FPT"
    at.text_input(key="board_search").set_value("").run()
    assert at.selectbox(key="board_selected").value == "FPT"
    at.selectbox(key="board_exchange").set_value("HNX").run()
    assert not at.exception
    assert at.selectbox(key="board_selected").value == "PVS"


def test_pause_uses_cache_and_manual_refresh_fetches_once_with_force(workspace):
    at = workspace.open()
    before = len(workspace.calls["fetch"])
    at.checkbox(key="board_auto").uncheck().run()
    assert len(workspace.calls["fetch"]) == before
    assert workspace.calls["cached"][-1] == workspace.symbols
    assert any("Đã tạm dừng tự cập nhật" in item.value for item in at.markdown)
    at.text_input(key="board_search").set_value("FPT").run()
    assert len(workspace.calls["fetch"]) == before
    at.button(key="board_refresh").click().run()
    assert not at.exception and len(workspace.calls["fetch"]) == before + 1
    assert workspace.calls["fetch"][-1] == (workspace.symbols, True, 5)
    assert not at.checkbox(key="board_auto").value
    at.run()
    assert len(workspace.calls["fetch"]) == before + 1


def test_interval_selection_is_passed_to_snapshot_service(workspace):
    at = workspace.open()
    at.selectbox(key="board_interval").set_value(30).run()
    assert not at.exception and workspace.calls["fetch"][-1][-1] == 30
    assert any("Snapshot DNSE · cập nhật 30 giây" in item.value for item in at.markdown)


def test_compact_mode_and_saved_watchlist_survive_invalid_edit_and_new_session(workspace):
    at = workspace.open()
    at.checkbox(key="board_full").uncheck().run()
    assert all(len(row["cells"]) == 23 for row in board_rows(at))
    at.text_area(key="board_symbols_input").set_value("fpt, PVS; FPT")
    button(at, "Lưu mã trên bảng điện").click().run()
    assert not at.exception
    assert at.selectbox(key="board_selected").options == ["FPT", "PVS"]
    assert workspace.calls["fetch"][-1][0] == ["FPT", "PVS"]
    at.text_area(key="board_symbols_input").set_value("FPT, <script>")
    button(at, "Lưu mã trên bảng điện").click().run()
    assert not at.exception and at.error
    assert at.selectbox(key="board_selected").options == ["FPT", "PVS"]
    with workspace.store.connection() as db:
        saved = json.loads(db.execute("SELECT symbols FROM board_preferences WHERE workspace=?", ("test-ui",)).fetchone()["symbols"])
    assert saved == ["FPT", "PVS"]
    fresh = workspace.open()
    assert fresh.text_area(key="board_symbols_input").value == "FPT, PVS"
    assert fresh.selectbox(key="board_selected").options == ["FPT", "PVS"]


def test_disabled_market_never_fetches_and_controls_remain_disabled(workspace):
    at = workspace.open(enabled=False)
    assert not workspace.calls["fetch"]
    assert workspace.calls["cached"] == [workspace.symbols]
    assert at.checkbox(key="board_auto").disabled
    assert at.button(key="board_refresh").disabled
    assert any("Nguồn giá đang tắt" in item.value for item in at.info)
    at.selectbox(key="board_exchange").set_value("HOSE").run()
    assert not at.exception and not workspace.calls["fetch"]
    assert at.selectbox(key="board_selected").options == ["FPT", "VCB"]
