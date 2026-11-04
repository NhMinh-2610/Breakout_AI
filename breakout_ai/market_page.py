"""Market workspace pages: live equity board and sourced daily charts."""

from html import escape
import json
import re

import streamlit as st

from breakout_ai.config import Settings
from breakout_ai.finance import validate_symbol
from breakout_ai.market import MarketError, MarketService
from breakout_ai.market_view import load_quotes
from breakout_ai.portfolio import Portfolio
from breakout_ai.priceboard import DEFAULT_SYMBOLS, board_table, time_label
from breakout_ai.realtime import BoardSnapshot, MAX_SYMBOLS, RealtimeService
from breakout_ai.storage import Store
from breakout_ai.ui_common import chart_panel, identities
from breakout_ai.workbench import render_indices, render_workbench


def historical_market_page(
    settings: Settings, store: Store, portfolio: Portfolio
) -> None:
    st.caption(
        "Biểu đồ giá theo phiên · Việt Nam và Mỹ · dữ liệu này tách riêng bảng điện Việt Nam."
    )
    service = MarketService(settings, store)
    with st.form("market_chart"):
        first, second, third = st.columns([1, 1.8, 1.2])
        market = first.selectbox("Thị trường biểu đồ", ["VN", "US"], key="chart_market")
        symbol = second.text_input(
            "Mã cần xem biểu đồ", value="FPT", max_chars=12, key="chart_symbol"
        )
        days = third.selectbox(
            "Khoảng thời gian",
            [30, 90, 180],
            index=1,
            format_func=lambda value: f"{value} ngày lịch",
            key="chart_days",
        )
        submitted = st.form_submit_button("Xem và cập nhật biểu đồ", type="primary")
    try:
        symbol = validate_symbol(symbol)
        if submitted:
            with st.spinner("Đang tải dữ liệu từ nguồn thị trường…"):
                snapshot = service.get(market, symbol, force=True)
        else:
            loaded = load_quotes(service, [(market, symbol)], st.session_state)
            snapshot = loaded.snapshots.get((market, symbol))
            if loaded.errors:
                st.warning(
                    "Chưa cập nhật được giá; bạn có thể thử lại bằng nút xem biểu đồ."
                )
    except MarketError as exc:
        st.error(str(exc))
        snapshot = None
    except ValueError as exc:
        st.error(str(exc))
        snapshot = None
    if snapshot:
        with st.container(border=True):
            chart_panel(snapshot, days)
            st.link_button("Đối chiếu nguồn dữ liệu", snapshot.source_url)
        with st.expander("Bảng dữ liệu giá theo phiên"):
            st.dataframe(
                [
                    {
                        "Phiên": bar.date,
                        "Giá đóng cửa": bar.close,
                        "Khối lượng": bar.volume,
                        "Giá điều chỉnh": bar.adjusted_close,
                        "Tiền tệ": snapshot.currency,
                    }
                    for bar in snapshot.bars
                ],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info(
            "Chọn thị trường, nhập mã và bấm xem để lấy dữ liệu thật. Ứng dụng không vẽ giá giả khi chưa có dữ liệu."
        )
    with st.container(key="market_watchlist"):
        st.subheader("Bảng theo dõi cổ phiếu")
        wanted = identities(portfolio)[: service.settings.market_max_symbols]
        force = st.button(
            "Cập nhật bảng theo dõi",
            key="watchlist_refresh",
            use_container_width=True,
            disabled=not settings.market_enabled or not wanted,
        )
        loaded = load_quotes(service, wanted, st.session_state, force=force)
        if force:
            st.rerun()
        rows = []
        for identity in wanted:
            saved = loaded.snapshots.get(identity)
            if saved:
                data = saved.summary()
                rows.append(
                    {
                        "Mã": ":".join(identity),
                        "Giá": data["close"],
                        "Tiền tệ": data["currency"],
                        "Thay đổi (%)": data["change_pct"],
                        "Phiên": data["as_of"],
                        "Nguồn": data["provider"],
                        "Trạng thái": (
                            "Giá cũ · cần cập nhật"
                            if saved.cache_stale
                            else "Đã cập nhật"
                        ),
                    }
                )
            else:
                rows.append(
                    {
                        "Mã": ":".join(identity),
                        "Giá": None,
                        "Tiền tệ": "VND" if identity[0] == "VN" else "USD",
                        "Thay đổi (%)": None,
                        "Phiên": None,
                        "Nguồn": (
                            settings.vn_market_provider
                            if identity[0] == "VN"
                            else settings.us_market_provider
                        ),
                        "Trạng thái": "Chưa có dữ liệu",
                    }
                )
        if rows:
            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Giá": st.column_config.NumberColumn(format="%.2f"),
                    "Thay đổi (%)": st.column_config.NumberColumn(format="%+.2f%%"),
                },
            )
            st.caption(
                "Mỗi dòng giữ riêng tiền tệ và phiên nguồn. Dấu trống nghĩa chưa có giá, không phải giá bằng 0."
            )
        if loaded.errors:
            with st.expander("Các mã chưa cập nhật được"):
                for error in loaded.errors:
                    st.text(error)


def board_symbols(store: Store, portfolio: Portfolio) -> list[str]:
    with store.connection() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS board_preferences (workspace TEXT PRIMARY KEY, symbols TEXT NOT NULL)"
        )
        saved = db.execute(
            "SELECT symbols FROM board_preferences WHERE workspace=?",
            (store.workspace,),
        ).fetchone()
    if saved:
        try:
            symbols = json.loads(saved["symbols"])
            if (
                isinstance(symbols, list)
                and 0 < len(symbols) <= MAX_SYMBOLS
                and all(
                    isinstance(value, str)
                    and re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", value)
                    for value in symbols
                )
            ):
                return list(dict.fromkeys(symbols))
        except (ValueError, TypeError):
            pass
    owned = [symbol for market, symbol in identities(portfolio) if market == "VN"]
    return list(dict.fromkeys(owned + list(DEFAULT_SYMBOLS)))[:MAX_SYMBOLS]


def save_board_symbols(store: Store, raw: str) -> None:
    symbols = list(
        dict.fromkeys(
            value.upper() for value in re.split(r"[\s,;]+", raw.strip()) if value
        )
    )
    if (
        not symbols
        or len(symbols) > MAX_SYMBOLS
        or any(not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", symbol) for symbol in symbols)
    ):
        raise ValueError(
            f"Nhập 1–{MAX_SYMBOLS} mã Việt Nam, mỗi mã gồm 2–10 ký tự chữ và số, cách nhau bằng dấu phẩy hoặc xuống dòng."
        )
    with store.connection() as db:
        db.execute(
            "INSERT OR REPLACE INTO board_preferences VALUES (?,?)",
            (store.workspace, json.dumps(symbols)),
        )


@st.fragment(run_every=5)
def live_priceboard(settings: Settings, store: Store, portfolio: Portfolio) -> None:
    with st.container(key="market_terminal"):
        render_priceboard(settings, store, portfolio)


def render_priceboard(settings: Settings, store: Store, portfolio: Portfolio) -> None:
    symbols = board_symbols(store, portfolio)
    render_indices(settings, store, auto=st.session_state.get("board_auto", True))
    with st.container(key="live_board_controls"):
        exchange_col, search_col, sort_col, auto_col, edit_col, refresh_col = (
            st.columns([1, 1.25, 1.35, 1, 1, 1.1], vertical_alignment="bottom")
        )
        exchange = exchange_col.selectbox(
            "Sàn giao dịch", ["Tất cả", "HOSE", "HNX", "UPCOM"], key="board_exchange"
        )
        search = (
            search_col.text_input(
                "Tìm mã", placeholder="Ví dụ: VIC", max_chars=10, key="board_search"
            )
            .strip()
            .upper()
        )
        order = sort_col.selectbox(
            "Sắp xếp",
            [
                "Mã A → Z",
                "Tăng giá nhiều nhất",
                "Giảm giá nhiều nhất",
                "Khối lượng lớn nhất",
            ],
            key="board_sort",
        )
        auto = auto_col.checkbox(
            "Tự cập nhật",
            value=True,
            key="board_auto",
            disabled=not settings.market_enabled,
        )
        with edit_col.popover("Tùy chọn bảng", use_container_width=True):
            interval = st.selectbox(
                "Nhịp cập nhật",
                [5, 10, 30],
                format_func=lambda value: f"{value} giây",
                key="board_interval",
            )
            full = st.checkbox("Đầy đủ thông tin", value=True, key="board_full")
            st.caption(
                f"Danh sách theo dõi · tối đa {MAX_SYMBOLS} mã. Bộ lọc áp dụng cho danh sách này."
            )
            st.session_state.setdefault("board_symbols_input", ", ".join(symbols))
            with st.form("board_symbols_form"):
                raw = st.text_area(
                    "Mã trên bảng điện",
                    key="board_symbols_input",
                    height=90,
                    max_chars=450,
                )
                saved = st.form_submit_button("Lưu mã trên bảng điện")
            if saved:
                try:
                    save_board_symbols(store, raw)
                    symbols = board_symbols(store, portfolio)
                    st.success("Đã lưu danh sách bảng điện.")
                except ValueError as exc:
                    st.error(str(exc))
        refresh = refresh_col.button(
            "Làm mới",
            type="primary",
            key="board_refresh",
            use_container_width=True,
            disabled=not settings.market_enabled,
        )
    service = RealtimeService(store, poll_seconds=interval)
    if settings.market_enabled and (auto or refresh):
        snapshot = service.fetch(symbols, force=refresh)
    else:
        snapshot = service.cached(symbols) or BoardSnapshot()
    quotes = {quote.symbol: quote for quote in snapshot.quotes}
    visible = [
        symbol
        for symbol in symbols
        if (not search or search in symbol)
        and (
            exchange == "Tất cả"
            or (symbol in quotes and quotes[symbol].exchange == exchange)
        )
    ]

    def sort_value(symbol):
        quote = quotes.get(symbol)
        value = getattr(
            quote,
            "total_volume" if order == "Khối lượng lớn nhất" else "change_pct",
            None,
        )
        return (
            value is None,
            (
                -value
                if value is not None and order != "Giảm giá nhiều nhất"
                else value or 0
            ),
            symbol,
        )

    visible.sort(key=None if order == "Mã A → Z" else sort_value)
    status = (
        f"Snapshot DNSE · cập nhật {interval} giây"
        if auto and settings.market_enabled
        else "Đã tạm dừng tự cập nhật"
    )
    received = (
        time_label(snapshot.fetched_at)
        if snapshot.fetched_at
        else "Chưa tải được dữ liệu"
    )
    st.markdown(
        '<div class="priceboard-toolbar"><div><div class="priceboard-title">Bảng điện Việt Nam</div><div class="priceboard-caption">Giá ×1.000 đ · KL cổ phiếu · GT triệu đồng</div></div><div class="priceboard-status">'
        + escape(status)
        + "<span>Lần tải: "
        + escape(received)
        + "</span></div></div>",
        unsafe_allow_html=True,
    )
    if not settings.market_enabled:
        st.info(
            "Nguồn giá đang tắt trong cấu hình. Bảng chỉ hiển thị bản đã lưu, nếu có."
        )
    if snapshot.errors:
        st.warning(
            "Kết nối chưa đầy đủ. Các trường thiếu để trống; bản lưu cũ được đánh dấu."
        )
        with st.expander("Chi tiết kết nối bảng điện"):
            for error in snapshot.errors:
                st.text(error)
    priced = [
        quotes[symbol]
        for symbol in visible
        if symbol in quotes and quotes[symbol].last is not None
    ]
    with st.container(key="live_board_summary"):
        up = sum(quote.change is not None and quote.change > 0 for quote in priced)
        down = sum(quote.change is not None and quote.change < 0 for quote in priced)
        flat = sum(quote.change == 0 for quote in priced)
        st.markdown(
            f'<div class="priceboard-summary"><span>Đang xem <strong>{len(visible)}/{len(symbols)}</strong> mã</span><span class="price-up">Tăng <strong>{up}</strong></span><span class="price-down">Giảm <strong>{down}</strong></span><span class="price-ref">Tham chiếu <strong>{flat}</strong></span><span>Trong danh sách theo dõi</span></div>',
            unsafe_allow_html=True,
        )
    if snapshot.stale or any(quote.stale for quote in snapshot.quotes):
        st.caption(
            "Dòng mờ: giờ khớp nguồn đã quá 3 phút hoặc chưa có giờ nguồn; có thể ngoài phiên hoặc mã chưa phát sinh giao dịch mới. Độ sâu cũ được ẩn."
        )
    selected = None
    if visible:
        detail_symbols = sorted(visible)
        previous = st.session_state.get("board_selected")
        # Ranking updates reorder table rows, never the security being inspected.
        st.session_state["board_selected"] = (
            previous if previous in detail_symbols else detail_symbols[0]
        )
        selected = st.session_state["board_selected"]
    st.markdown(
        board_table(snapshot.quotes, visible, selected=selected, full=full),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="priceboard-legend"><span class="price-ceiling">● Trần</span><span class="price-up">● Tăng</span><span class="price-ref">● Tham chiếu</span><span class="price-down">● Giảm</span><span class="price-floor">● Sàn</span><span>— Chưa có dữ liệu</span></div>',
        unsafe_allow_html=True,
    )
    if visible:
        with st.container(key="market_analysis_controls"):
            selection, timeframe, update = st.columns(
                [1.6, 1, 1], vertical_alignment="bottom"
            )
            selected = selection.selectbox(
                "Chi tiết mã", detail_symbols, key="board_selected"
            )
            resolution = timeframe.selectbox(
                "Khung nến",
                ["1", "5", "15"],
                index=1,
                format_func=lambda value: f"{value} phút",
                key="market_candle_resolution",
            )
            chart_refresh = update.button(
                "Cập nhật biểu đồ",
                key="market_chart_refresh",
                disabled=not settings.market_enabled,
                use_container_width=True,
            )
        render_workbench(
            settings,
            store,
            portfolio,
            snapshot,
            symbols,
            selected,
            resolution=resolution,
            auto=auto,
            refresh=chart_refresh or refresh,
        )
    st.caption(
        "Bảng tải snapshot theo nhịp đã chọn khi đang mở trang. Dữ liệu phụ thuộc nguồn; chưa phải luồng đẩy từng giao dịch."
    )
    st.markdown("[Mở bảng giá DNSE để đối chiếu](https://banggia.dnse.com.vn/v2)")


@st.fragment(run_every=5)
def analysis_page(settings: Settings, store: Store, portfolio: Portfolio) -> None:
    """The primary task is observing one chart, independent of a large quote table."""
    symbols = board_symbols(store, portfolio)
    with st.container(key="analysis_workspace"):
        st.markdown(
            '<div class="analysis-header"><h1>AI quan sát biểu đồ</h1>'
            "<p>Chọn mã, đọc cấu trúc giá và đối chiếu cơ hội cùng rủi ro.</p></div>",
            unsafe_allow_html=True,
        )
        with st.container(key="analysis_controls"):
            selection, timeframe, live, refresh = st.columns(
                [1.5, 1, 1, 1.1], vertical_alignment="bottom"
            )
            options = sorted(symbols)
            previous = st.session_state.get("analysis_symbol", "VIC")
            st.session_state["analysis_symbol"] = (
                previous if previous in options else options[0]
            )
            symbol = selection.selectbox("Mã phân tích", options, key="analysis_symbol")
            resolution = timeframe.selectbox(
                "Khung nến",
                ["1", "5", "15"],
                index=1,
                format_func=lambda value: f"{value} phút",
                key="analysis_resolution",
            )
            auto = live.checkbox(
                "Theo dõi tự động",
                value=True,
                key="analysis_auto",
                disabled=not settings.market_enabled,
            )
            force = refresh.button(
                "Cập nhật",
                key="analysis_refresh",
                type="primary",
                disabled=not settings.market_enabled,
                use_container_width=True,
            )
        if settings.provider == "demo":
            st.caption(
                "Đang dùng bộ quy tắc có thể kiểm tra. Kết nối mô hình để AI chọn luận điểm từ chuỗi nến và bằng chứng."
            )
        else:
            st.caption(
                "AI nhận chuỗi nến đã đóng và bằng chứng có nguồn; chỉ được gọi khi bạn bấm nhận định hoặc gửi câu hỏi."
            )
        service = RealtimeService(store)
        if settings.market_enabled and (auto or force):
            board = service.fetch([symbol], force=force)
        else:
            board = service.cached([symbol]) or BoardSnapshot()
        if board.errors:
            st.warning(
                "Giá nguồn chưa đầy đủ; nhận định theo thời điểm sẽ chờ dữ liệu mới."
            )
        render_workbench(
            settings,
            store,
            portfolio,
            board,
            symbols,
            symbol,
            resolution=resolution,
            auto=auto,
            refresh=force,
        )
        st.caption(
            "Tín hiệu có điều kiện trên khung nến đã chọn, chưa được kiểm định thành chiến lược đầu tư."
        )


def market_page(settings: Settings, store: Store, portfolio: Portfolio) -> None:
    view = st.radio(
        "Nội dung thị trường",
        ["Phân tích biểu đồ", "Bảng điện Việt Nam", "Biểu đồ VN / US"],
        key="market_view",
        horizontal=True,
        label_visibility="collapsed",
    )
    if view == "Phân tích biểu đồ":
        analysis_page(settings, store, portfolio)
    elif view == "Bảng điện Việt Nam":
        live_priceboard(settings, store, portfolio)
    else:
        historical_market_page(settings, store, portfolio)
