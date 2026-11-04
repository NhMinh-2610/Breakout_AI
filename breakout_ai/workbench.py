"""Market chart, explicit technical observations and a contextual chat panel."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import escape

import streamlit as st

from breakout_ai.books import BookLibrary
from breakout_ai.copilot import MarketCopilot
from breakout_ai.intraday import IntradayService, IntradaySnapshot, SUPPORTED_INDICES
from breakout_ai.market_visuals import candle_chart, depth_chart, signal_card
from breakout_ai.priceboard import depth_table, format_number, time_label
from breakout_ai.providers import ProviderError
from breakout_ai.observation import observe_chart
from breakout_ai.tutor import chat_turn
from breakout_ai.realtime import RealtimeService


def render_indices(settings, store, *, auto=True):
    def load(symbol):
        service = IntradayService(store, cache_seconds=60)
        if settings.market_enabled and auto:
            return service.fetch(symbol, resolution="5")
        return service.cached(symbol, resolution="5") or IntradaySnapshot(symbol)

    symbols = list(SUPPORTED_INDICES)
    with ThreadPoolExecutor(max_workers=3) as pool:
        snapshots = list(pool.map(load, symbols))
    with st.container(key="market_indices"):
        for column, symbol, snapshot in zip(
            st.columns(len(symbols)), symbols, snapshots
        ):
            rows = snapshot.candles if snapshot.price_unit == "points" else []
            current = rows[-1] if rows else None
            latest_day = (
                datetime.fromisoformat(current.time)
                .astimezone(timezone(timedelta(hours=7)))
                .date()
                if current
                else None
            )
            today = [
                bar
                for bar in rows
                if datetime.fromisoformat(bar.time)
                .astimezone(timezone(timedelta(hours=7)))
                .date()
                == latest_day
            ]
            prior = (
                [
                    bar
                    for bar in rows
                    if datetime.fromisoformat(bar.time)
                    .astimezone(timezone(timedelta(hours=7)))
                    .date()
                    < latest_day
                ]
                if latest_day
                else []
            )
            reference = prior[-1].close if prior else None
            change = (
                (current.close / reference - 1) * 100 if current and reference else None
            )
            color = (
                "#35d399"
                if change is not None and change > 0
                else "#ff727f" if change is not None and change < 0 else "#f0bc51"
            )
            points = ""
            if today:
                low, high = min(bar.close for bar in today), max(
                    bar.close for bar in today
                )
                points = " ".join(
                    f"{index / max(1, len(today)-1) * 220:.2f},{34-(bar.close-low)/max(high-low,1e-9)*30:.2f}"
                    for index, bar in enumerate(today)
                )
            spark = (
                '<svg class="market-index-spark" viewBox="0 0 220 38" preserveAspectRatio="none" role="img" aria-label="Diễn biến chỉ số từ nến nguồn"><polyline fill="none" stroke="'
                + color
                + '" stroke-width="1.8" points="'
                + points
                + '"/></svg>'
                if today
                else '<div class="market-index-spark"></div>'
            )
            movement = (
                f"{change:+.2f}% so phiên trước"
                if change is not None
                else "Chưa có mức so sánh"
            )
            stamp = time_label(current.time) if current else "Chưa có dữ liệu chỉ số"
            column.markdown(
                '<div class="market-index-card"><div class="market-index-name">'
                + escape(SUPPORTED_INDICES[symbol])
                + '</div><div class="market-index-value">'
                + format_number(current.close if current else None, 2)
                + '<small> điểm</small></div><div class="market-index-change" style="color:'
                + color
                + '">'
                + escape(movement)
                + "</div>"
                + spark
                + '<div class="market-index-meta">Nến 5 phút · '
                + escape(stamp)
                + "</div></div>",
                unsafe_allow_html=True,
            )


def _chat(settings, store, symbols, selected, observation):
    conversations = st.session_state.setdefault("market_chat_conversations", {})
    identifier = conversations.get(selected)
    history = store.messages(identifier)
    if identifier and not history:
        identifier = None
        conversations.pop(selected, None)
    st.caption(f"Chat gắn với {selected} · câu trả lời giữ giờ dữ liệu lúc gửi.")
    with st.container(height=300, border=False, key="market_chat_log"):
        if not history:
            st.write(
                "Bạn có thể hỏi: “Vì sao chưa nên mua?”, “Hỗ trợ có phải đáy không?” hoặc “Lực mua/bán đang thế nào?”."
            )
        for message in history[-8:]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    with st.form("market_chat_form", clear_on_submit=True):
        question = st.text_input(
            f"Hỏi về {selected}",
            key="market_chat_question",
            max_chars=settings.max_input_chars,
            placeholder="Điều gì cần xác nhận trước khi mua?",
        )
        send = st.form_submit_button("Gửi", type="primary", use_container_width=True)
    if st.button("Cuộc trò chuyện mới", key="market_chat_new"):
        conversations.pop(selected, None)
        st.rerun()
    if send:
        context = {**observation.context(), "symbols": symbols}
        try:
            copilot = MarketCopilot(settings, context, BookLibrary(store))
            with st.spinner("Đang đối chiếu dữ liệu và kiến thức…"):
                conversations[selected] = chat_turn(
                    store,
                    copilot,
                    question,
                    identifier,
                    "VN",
                    "Gợi ý cổ phiếu có điều kiện",
                )
            st.rerun()
        except (ValueError, ProviderError) as exc:
            st.error(str(exc))
    st.caption(
        "Lịch sử cũng được lưu trong Chat AI. Chế độ demo giải thích bằng quy tắc; cấu hình model để có diễn giải LLM."
    )


def _scan(settings, store, portfolio, board, symbols, auto, resolution):
    st.caption(
        "Theo dõi điều kiện mua mới và rủi ro ở vị thế đang sở hữu. Phạm vi tối đa 6 mã; kết quả là tín hiệu quan sát, không phải lệnh."
    )
    default = list(
        dict.fromkeys(
            [row["symbol"] for row in portfolio.holdings() if row["market"] == "VN"]
            + symbols
        )
    )[:6]
    # Keep widget options stable as price rankings change.
    candidates = sorted(symbols)
    default = [symbol for symbol in default if symbol in candidates]
    previous = st.session_state.get("market_scan_choices")
    if previous is not None:
        st.session_state["market_scan_choices"] = [
            value for value in previous if value in candidates
        ][:6]
    chosen = st.multiselect(
        "Mã theo dõi tín hiệu",
        candidates,
        default=default,
        max_selections=6,
        key="market_scan_choices",
    )
    run = st.button(
        "Quét tín hiệu hôm nay",
        type="primary",
        key="market_scan_run",
        disabled=not settings.market_enabled or not chosen,
        use_container_width=True,
    )
    active = st.session_state.setdefault("market_scan_active", [])
    if run:
        active[:] = chosen
    active[:] = [symbol for symbol in active if symbol in symbols]
    if not active:
        st.info(
            "Chọn mã và bấm quét. Chỉ hiện điều kiện có đủ dữ liệu; không ép tạo mã nên mua khi thị trường chưa xác nhận."
        )
        return

    def load(symbol):
        service = IntradayService(store)
        if settings.market_enabled and (auto or run):
            return service.fetch(symbol, resolution=resolution, force=run)
        return service.cached(symbol, resolution=resolution) or IntradaySnapshot(
            symbol, resolution=resolution
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        charts = dict(zip(active, pool.map(load, active)))
    quote_service = RealtimeService(store)
    if settings.market_enabled and (auto or run):
        scan_board = quote_service.fetch(active, force=run)
    else:
        scan_board = quote_service.cached(active) or board
    quotes = {quote.symbol: quote for quote in scan_board.quotes}
    owned = {row["symbol"] for row in portfolio.holdings() if row["market"] == "VN"}
    reports = []
    for symbol in active:
        chart = charts[symbol]
        report = observe_chart(
            symbol,
            chart,
            quotes.get(symbol),
            owned=symbol in owned,
            resolution=resolution,
        ).report
        reports.append(report)
    priority = {"watch_sell": 0, "watch_buy": 1, "hold": 2, "wait": 3}
    reports.sort(key=lambda report: (priority[report.action], report.symbol))
    for report in reports:
        st.markdown(signal_card(report), unsafe_allow_html=True)


def render_workbench(
    settings,
    store,
    portfolio,
    board,
    symbols,
    selected,
    *,
    resolution="5",
    auto=True,
    refresh=False,
):
    service = IntradayService(store)
    if settings.market_enabled and (auto or refresh):
        chart_data = service.fetch(selected, resolution=resolution, force=refresh)
    else:
        chart_data = service.cached(
            selected, resolution=resolution
        ) or IntradaySnapshot(selected, resolution=resolution)
    quote = next((quote for quote in board.quotes if quote.symbol == selected), None)
    owned = any(
        row["market"] == "VN" and row["symbol"] == selected
        for row in portfolio.holdings()
    )
    observation = observe_chart(
        selected, chart_data, quote, owned=owned, resolution=resolution
    )
    report = observation.report
    with st.container(key="market_workbench"):
        left, right = st.columns([1.9, 1], gap="medium")
        with left:
            with st.container(border=True, key="market_chart_panel"):
                st.markdown(f"**{selected} · Biểu đồ nến {resolution} phút**")
                st.caption(
                    "Nến giá · đường vàng SMA20 · vùng hỗ trợ/kháng cự · khối lượng bên dưới. Nến mờ đang hình thành."
                )
                chart = candle_chart(chart_data, quote, report)
                if chart is None:
                    st.info("Nguồn chưa trả đủ nến để vẽ. Bảng không tạo biểu đồ mẫu.")
                else:
                    st.altair_chart(chart, use_container_width=True, theme=None)
                st.caption(
                    f"{chart_data.source} · nến tải lúc {time_label(chart_data.fetched_at)} · kiểm tra lại mỗi 30 giây."
                )
                if chart_data.stale:
                    st.caption(
                        "Biểu đồ đang cũ hoặc ngoài phiên; dùng xem lại, chưa có tín hiệu giao dịch hiện tại."
                    )
                if chart_data.errors:
                    with st.expander("Tình trạng nguồn biểu đồ"):
                        for error in chart_data.errors:
                            st.text(error)
                if quote:
                    session, depth = st.tabs(["Thông tin phiên", "Cung cầu 3 mức"])
                    with session:
                        first, second = st.columns(2)
                        first.metric(
                            "Giá khớp · VND / CP",
                            format_number(quote.last),
                            (
                                f"{quote.change_pct:+.2f}%"
                                if quote.change_pct is not None
                                else None
                            ),
                        )
                        second.metric(
                            "Tổng khối lượng · CP", format_number(quote.total_volume)
                        )
                        st.caption(
                            f"Mở {format_number(quote.open)} · Cao {format_number(quote.high)} · Thấp {format_number(quote.low)} · TB {format_number(quote.average)} VND"
                        )
                        st.caption(
                            f"Nước ngoài · mua {format_number(quote.foreign_buy_volume)} CP · bán {format_number(quote.foreign_sell_volume)} CP"
                        )
                        st.caption(
                            f"Giờ khớp nguồn: {time_label(quote.source_timestamp)}"
                        )
                        st.caption(
                            f"Nguồn: {board.source} · nhận lúc {time_label(quote.received_at)}"
                        )
                    with depth:
                        chart = depth_chart(quote)
                        if chart is not None:
                            st.altair_chart(chart, use_container_width=True, theme=None)
                        st.markdown(depth_table(quote), unsafe_allow_html=True)
                        st.caption(
                            f"Giờ sổ lệnh: {time_label(quote.depth_timestamp)} · lệnh chờ có thể sửa/hủy."
                        )
        with right:
            with st.container(border=True, key="market_insight_panel"):
                analysis, chat, scan = st.tabs(
                    ["Phân tích", "Chat theo mã", "Cơ hội hôm nay"]
                )
                with analysis:
                    st.markdown(signal_card(report), unsafe_allow_html=True)
                    indicators = report.indicators
                    st.caption(
                        "RSI14 "
                        + format_number(indicators.get("rsi14"), 1)
                        + " · KL tương đối "
                        + format_number(indicators.get("relative_volume"), 2)
                        + "×"
                    )
                    with st.expander("Điều kiện đang kiểm tra"):
                        for label, passed in report.condition_checks.items():
                            st.write(("✓ " if passed else "○ ") + label)
                        st.caption(
                            "Số điều kiện đạt mô tả quy tắc; không phải độ tin cậy hay xác suất sinh lời."
                        )
                    st.caption(
                        "Đọc dữ liệu nến tạo nên biểu đồ: cấu trúc giá, khối lượng, bằng chứng ủng hộ và phản biện."
                    )
                    with st.expander("Cấu trúc nến đang quan sát", expanded=True):
                        for fact in observation.chart["facts"]:
                            if fact["id"] in {
                                "structure.recent",
                                "structure.range20",
                                "candle.latest",
                            }:
                                st.write(fact["text"])

                    if st.button(
                        "Đọc biểu đồ & nhận định",
                        key="market_ai_review",
                        type="primary",
                        use_container_width=True,
                    ):
                        conversations = st.session_state.setdefault(
                            "market_chat_conversations", {}
                        )
                        context = {**observation.context(), "symbols": symbols}
                        copilot = MarketCopilot(settings, context, BookLibrary(store))
                        try:
                            with st.spinner(
                                "Đang đọc cấu trúc nến và đối chiếu cơ hội…"
                            ):
                                identifier = chat_turn(
                                    store,
                                    copilot,
                                    "Đọc cấu trúc biểu đồ, chọn bằng chứng quan trọng và phản biện; nêu cơ hội cùng điều kiện xác nhận, vô hiệu.",
                                    conversations.get(selected),
                                    "VN",
                                    "Gợi ý cổ phiếu có điều kiện",
                                )
                            conversations[selected] = identifier
                            st.session_state.setdefault("market_review_turns", {})[
                                selected
                            ] = identifier
                            st.rerun()
                        except (ValueError, ProviderError) as exc:
                            st.error(str(exc))
                    review_id = st.session_state.get("market_review_turns", {}).get(
                        selected
                    )
                    messages = store.messages(review_id) if review_id else []
                    if messages:
                        latest = next(
                            (
                                message
                                for message in reversed(messages)
                                if message["role"] == "assistant"
                            ),
                            None,
                        )
                        if latest:
                            st.caption(
                                "Nhận định đã lưu theo dữ liệu lúc gửi. Bấm đọc lại để cập nhật."
                            )
                            st.markdown(latest["content"])
                with chat:
                    _chat(settings, store, symbols, selected, observation)
                with scan:
                    _scan(settings, store, portfolio, board, symbols, auto, resolution)
