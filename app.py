"""Breakout AI investment workspace. Run: python -m streamlit run app.py."""

from datetime import datetime
from html import escape
import json
import re
from uuid import uuid4

import streamlit as st

from breakout_ai.brand import NAME
from breakout_ai.books import BookError, BookLibrary
from breakout_ai.config import ROOT, Settings
from breakout_ai.daily import DailyPlanner, VN_TIME, rules_signature
from breakout_ai.dashboard import allocation_chart, price_chart, price_summary, workflow_diagram
from breakout_ai.finance import validate_symbol
from breakout_ai.market import MarketError, MarketService
from breakout_ai.news import FEEDS, NewsService
from breakout_ai.market_view import load_quotes
from breakout_ai.realtime import BoardSnapshot, RealtimeService, MAX_SYMBOLS
from breakout_ai.priceboard import DEFAULT_SYMBOLS, board_table, depth_table, format_number, time_label
from breakout_ai.portfolio import Portfolio
from breakout_ai.providers import ProviderError
from breakout_ai.storage import Store
from breakout_ai.tutor import STYLES, Tutor, chat_turn

st.set_page_config(page_title=f"{NAME} · Nghiên cứu đầu tư", page_icon=str(ROOT / "assets" / "favicon.png"), layout="wide", initial_sidebar_state="expanded")
BRAND_MARK = (ROOT / "assets" / "brand-mark.svg").read_text(encoding="utf-8")
st.markdown("<style>" + (ROOT / "assets" / "terminal.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)


def go(page: str, view: str | None = None) -> None:
    st.session_state.page = page
    if view:
        st.session_state.portfolio_view = view


def new_conversation(store: Store, delete: bool = False) -> None:
    identifier = st.session_state.pop("conversation_id", None)
    if delete and identifier:
        store.delete_conversation(identifier)


def intro(kicker: str, title: str, description: str) -> None:
    st.markdown(f'<div class="masthead"><div class="eyebrow">{escape(kicker)}</div><h1>{escape(title)}</h1><p>{escape(description)}</p></div>', unsafe_allow_html=True)


def local_time(value: str) -> str:
    return datetime.fromisoformat(value).astimezone(VN_TIME).strftime("%H:%M · %d/%m/%Y")


def schedule_caption(settings: Settings) -> str:
    try:
        state = json.loads((ROOT / "data" / "schedule.json").read_text(encoding="utf-8-sig"))
        if state["workspace"] == settings.workspace_id and state["database"] == str(settings.database_path):
            return "Đã cài lịch 07:30 mỗi sáng · giờ Việt Nam · máy cần bật và tài khoản đã đăng nhập."
    except (OSError, ValueError, KeyError):
        pass
    return "Mốc buổi sáng: 07:30 giờ Việt Nam · tự tạo bản tin khi mở ứng dụng; xem tài liệu để cài lịch chạy nền."


def action_card(item: dict) -> None:
    with st.container(border=True):
        st.markdown(f'<div class="stock-top"><div class="ticker">{escape(item["symbol"])}<span class="market-tag">{escape(item["market"])}</span></div><span class="action {escape(item["action"])}">{escape(item["title"])}</span></div>', unsafe_allow_html=True)
        quote = item.get("quote")
        if quote:
            st.markdown(f'<div class="price">{quote["close"]:,.2f} <small>{escape(quote["currency"])}</small></div>', unsafe_allow_html=True)
            st.caption(f"Giá đóng cửa {quote['as_of']} · {quote['provider']}")
        if item["owned"]:
            text = f"Đang có {item['quantity']:g} cổ phiếu · giá vốn {item['average_cost']:,.2f}"
            if item.get("pnl_pct") is not None:
                text += f" · lãi/lỗ giá {item['pnl_pct']:+.2f}%"
            st.caption(text)
        st.markdown(f'<p class="stock-reason">{escape(item["reason"])}</p>', unsafe_allow_html=True)
        if item["checks"]:
            with st.expander("Vì sao có gợi ý này?"):
                for check in item["checks"]:
                    state = "Đạt điều kiện" if check["triggered"] else "Chưa đạt điều kiện"
                    if not check["available"]:
                        state = "Thiếu dữ liệu"
                    st.write(f"**{state} · {check['label']}**")
                    st.write(check["detail"])
                    st.text(check["quote"])
                    st.caption(check["citation"]["source_title"])
                st.caption("Mua: cần đạt tất cả điều kiện mua đã đọc. Bán: chỉ áp dụng cho mã bạn đang sở hữu và có ít nhất một điều kiện bán đạt.")
        if quote:
            st.markdown(f"[Đối chiếu nguồn giá]({quote['source_url']})")
            st.caption(f"Lấy lúc {local_time(quote['fetched_at'])}. Chưa tính phí, thuế, cổ tức hoặc thay đổi số lượng do quyền.")


def today_page(planner: DailyPlanner, settings: Settings, report: dict | None = None) -> None:
    st.caption(schedule_caption(settings))
    if report is None:
        with st.spinner("Đang chuẩn bị bản tin từ sách và dữ liệu thị trường…"):
            report = planner.get_today()
    if report["status"] == "needs_book":
        st.markdown('<div class="empty-guide"><div class="eyebrow">Bắt đầu trong 2 bước</div><h2>Thêm sách. Nhập cổ phiếu đang có.</h2><p>1. Tải sách lên và kiểm tra các nguyên tắc ứng dụng đọc được.<br>2. Nhập mã, số lượng và giá mua. Bản tin sẽ đối chiếu với dữ liệu giá thật.</p></div>', unsafe_allow_html=True)
        left, right = st.columns(2)
        left.button("1. Thêm cuốn sách đầu tiên", on_click=go, args=("Thư viện sách",), type="primary", use_container_width=True)
        right.button("2. Nhập cổ phiếu của tôi", on_click=go, args=("Danh mục",), use_container_width=True)
        st.info("Chưa có sách nên chưa có gợi ý mua hoặc bán. Không có dữ liệu mẫu nào được coi là danh mục của bạn.")
        return
    st.caption(f"Sách đang áp dụng: {report['book']['title']} · bản tin {local_time(report['created_at'])}")
    if report["status"] in {"needs_measurable_rules", "needs_rule_review"}:
        message = "Sách chưa có nguyên tắc mua/bán đo được mà ứng dụng hỗ trợ. Bạn vẫn có thể đọc và hỏi kiến thức trong sách." if report["status"] == "needs_measurable_rules" else "Ứng dụng đã đọc được nguyên tắc. Hãy đối chiếu trích đoạn trong mục Sách một lần trước khi dùng cho bản tin."
        st.info(message)
        st.button("Mở sách và nguyên tắc", on_click=go, args=("Thư viện sách",), type="primary")
    else:
        counts = {action: sum(item["action"] == action for item in report["items"]) for action in ("buy", "sell", "hold", "wait")}
        with st.container(key="daily_action_metrics"):
            for column, action, label in zip(st.columns(4), counts, ("Cân nhắc mua", "Cân nhắc bán", "Giữ và theo dõi", "Cần xem thêm")):
                column.metric(label, counts[action])
        st.write("")
        if st.button("Cập nhật dữ liệu và gợi ý", type="primary"):
            with st.spinner("Đang đối chiếu giá mới với nguyên tắc trong sách…"):
                planner.get_today(refresh=True)
            st.rerun()
        if report["errors"]:
            st.warning("Một số mã chưa lấy được giá. Các mã đó sẽ hiện ‘Cần xem thêm’.")
            with st.expander("Tình trạng nguồn dữ liệu"):
                for error in report["errors"]:
                    st.text(str(error))
        for owned, label in ((True, "Cổ phiếu bạn đang sở hữu"), (False, "Các mã đang tìm cơ hội mua")):
            st.subheader(label)
            items = [item for item in report["items"] if item["owned"] == owned]
            if not items:
                st.caption("Bạn chưa nhập cổ phiếu đang sở hữu." if owned else "Bạn chưa chọn mã để tìm cơ hội mua.")
            priority = {"sell": 0, "buy": 1, "hold": 2, "wait": 3}
            columns = st.columns(2, gap="medium")
            for index, item in enumerate(sorted(items, key=lambda row: priority[row["action"]])):
                with columns[index % 2]:
                    action_card(item)
    if report.get("lesson"):
        st.subheader("Một ý trong sách hôm nay")
        with st.container(border=True):
            st.text(report["lesson"]["text"])
            st.caption(report["lesson"]["citation"]["source_title"])
        st.button("Hỏi thêm về kiến thức này", on_click=go, args=("Trợ lý AI",))
    st.caption("Gợi ý chỉ phản ánh điều kiện trong sách và dữ liệu hiện có; chưa đánh giá đầy đủ doanh nghiệp hoặc mức rủi ro phù hợp với bạn. Giá ngày được lọc để tránh phiên chưa đóng; nguồn công khai có thể chậm.")


def initial_holding_submission(portfolio: Portfolio) -> None:
    state = st.session_state
    try:
        portfolio.upsert(state.initial_market, state.initial_symbol, state.initial_quantity, state.initial_cost)
        state.holding_notice = ("success", "Đã lưu vị thế ban đầu. Danh mục và phân bổ vốn đã cập nhật.")
        state.initial_symbol = ""
    except ValueError as exc:
        state.holding_notice = ("error", str(exc))


def holdings_editor(portfolio: Portfolio) -> None:
    holdings = portfolio.holdings()
    if holdings:
        st.dataframe([{"Thị trường": row["market"], "Mã": row["symbol"], "Số lượng": row["quantity"], "Giá vốn / CP": row["average_cost"], "Vốn đang mở": row["quantity"] * row["average_cost"], "Tiền tệ": "VND" if row["market"] == "VN" else "USD"} for row in holdings], use_container_width=True, hide_index=True)
        st.caption("Giá vốn đã ghi nhận, chưa phải giá thị trường hiện tại.")
    else:
        st.info("Danh mục trống. Nhập cổ phiếu đang có hoặc ghi một giao dịch mua đã thực hiện.")
    st.button("Ghi giao dịch mua / bán", on_click=go, args=("Danh mục", "Ghi giao dịch"), type="primary", key="portfolio_record")
    with st.expander("Nhập / sửa cổ phiếu đang có", expanded=not holdings):
        st.caption("Nhập vị thế ban đầu nếu bạn đã sở hữu cổ phiếu từ trước. Với mã đã có nhật ký giao dịch, dùng mục Ghi giao dịch để thay đổi số lượng và giá vốn.")
        notice = st.session_state.pop("holding_notice", None)
        if notice:
            (st.success if notice[0] == "success" else st.error)(notice[1])
        with st.form("holding"):
            first, second = st.columns([1, 2])
            first.selectbox("Thị trường", ["VN", "US"], format_func=lambda value: "Việt Nam · VND" if value == "VN" else "Mỹ · USD", key="initial_market")
            second.text_input("Mã cổ phiếu", placeholder="FPT hoặc AAPL", max_chars=12, key="initial_symbol")
            left, right = st.columns(2)
            left.number_input("Số lượng đang có", min_value=0.0001, value=100.0, step=1.0, format="%.4f", key="initial_quantity")
            right.number_input("Giá mua bình quân / cổ phiếu", min_value=0.0001, value=100.0, step=1.0, format="%.4f", key="initial_cost")
            st.caption("VN nhập đầy đủ VND, ví dụ 58.000 đồng nhập 58000. US nhập USD. Lưu lại cùng mã sẽ cập nhật vị thế hiện có.")
            st.form_submit_button("Lưu cổ phiếu", type="primary", on_click=initial_holding_submission, args=(portfolio,))
    if holdings:
        with st.expander("Quản lý vị thế đã nhập"):
            for holding in holdings:
                with st.container(border=True):
                    left, right = st.columns([4, 1])
                    left.write(f"**{holding['market']}:{holding['symbol']}** · {holding['quantity']:g} cổ phiếu")
                    left.caption(f"Giá vốn {holding['average_cost']:,.2f} {'VND' if holding['market'] == 'VN' else 'USD'} / cổ phiếu")
                    if portfolio.has_trades(holding["market"], holding["symbol"]):
                        right.caption("Đã có sổ giao dịch")
                    else:
                        right.button("Bỏ khỏi danh mục", key=f"remove_{holding['id']}", on_click=portfolio.remove, args=(holding["id"],))
    with st.expander("Chọn các mã để tìm cơ hội mua mới"):
        st.caption("Danh sách này chỉ là phạm vi tìm kiếm, chưa phải khuyến nghị. Tối đa 10 mã; ghi thị trường để tránh nhầm tên.")
        preferences = portfolio.preferences()
        with st.form("candidates"):
            text = st.text_area("Danh sách tìm mua", value=", ".join(":".join(pair) for pair in preferences["candidates"]), placeholder="VN:FPT, VN:VCB, US:AAPL")
            if st.form_submit_button("Lưu danh sách tìm mua"):
                try:
                    pairs = [entry.strip().upper().split(":") for entry in text.replace("\n", ",").split(",") if entry.strip()]
                    if any(len(pair) != 2 for pair in pairs):
                        raise ValueError("Dùng dạng VN:FPT hoặc US:AAPL, cách nhau bằng dấu phẩy.")
                    portfolio.set_preferences(candidates=pairs)
                    st.success("Đã cập nhật phạm vi tìm mua.")
                except ValueError as exc:
                    st.error(str(exc))
    with st.expander("Giá trị nội tại ước tính · chỉ dùng nếu sách yêu cầu"):
        st.caption("Đây là ước tính do bạn tự nghiên cứu, ứng dụng chưa tự định giá doanh nghiệp. Bỏ trống thì nguyên tắc biên an toàn sẽ chờ thêm dữ liệu.")
        preferences = portfolio.preferences()
        with st.form("estimates"):
            estimates = st.text_area("Ước tính mỗi cổ phiếu", value="\n".join(f"{key}={value:g}" for key, value in preferences["estimates"].items()), placeholder="VN:FPT=70000\nUS:AAPL=150")
            if st.form_submit_button("Lưu ước tính"):
                try:
                    values = {}
                    for line in estimates.splitlines():
                        if not line.strip():
                            continue
                        identity, value = line.split("=")
                        estimate_market, estimate_symbol = identity.strip().upper().split(":")
                        if estimate_market not in {"VN", "US"}:
                            raise ValueError
                        values[f"{estimate_market}:{validate_symbol(estimate_symbol)}"] = float(value)
                    portfolio.set_preferences(estimates=values)
                    st.success("Đã lưu ước tính của bạn.")
                except (ValueError, TypeError):
                    st.error("Dùng dạng VN:FPT=70000, mỗi dòng một mã; giá trị phải là số dương hữu hạn.")


def books_page(library: BookLibrary, planner: DailyPlanner) -> None:
    intro("KIẾN THỨC", "Thư viện sách", "Thêm sách → đối chiếu nguyên tắc → dùng cho gợi ý hằng ngày.")
    with st.form("upload_book", clear_on_submit=True):
        upload = st.file_uploader("Chọn sách PDF, TXT hoặc Markdown", type=["pdf", "txt", "md"])
        left, right = st.columns(2)
        title = left.text_input("Tên sách", max_chars=180)
        author = right.text_input("Tác giả", max_chars=120)
        st.caption("Chỉ tải tài liệu bạn có quyền sử dụng. PDF cần có lớp chữ; tối đa 20 MB và 400 trang mỗi tài liệu. Văn bản lưu trên máy.")
        if st.form_submit_button("Đọc sách", type="primary"):
            if upload is None:
                st.error("Hãy chọn một tệp sách trước.")
            else:
                try:
                    with st.spinner("Đang đọc và lập mục lục tìm kiếm…"):
                        _, added = library.ingest(upload.name, upload.getvalue(), title, author)
                    st.success("Đã đọc sách. Hãy kiểm tra các nguyên tắc bên dưới." if added else "Sách này đã có trong thư viện.")
                except BookError as exc:
                    st.error(str(exc))
    documents = library.documents()
    if not documents:
        st.info("Thư viện chưa có sách. Bạn có thể thử tệp tự viết examples/daily_rules.md để hiểu luồng; các ngưỡng trong tệp chỉ để thử chức năng.")
        return
    active = planner.active_book()
    choices = {book["id"]: book["title"] for book in documents}
    selected = st.selectbox("Sách áp dụng cho bản tin", list(choices), index=list(choices).index(active["id"]), format_func=choices.get)
    if selected != active["id"]:
        planner.portfolio.set_preferences(active_book=selected)
    rules = planner.rules()
    st.subheader("Nguyên tắc ứng dụng đọc được")
    st.caption("Bản hiện tại nhận một số câu điều kiện rõ ràng về lỗ/lãi so với giá vốn, đường trung bình và biên an toàn. Các nguyên tắc định tính vẫn tra cứu được nhưng chưa tự chuyển thành tín hiệu mua/bán.")
    for rule in rules:
        with st.container(border=True):
            st.write(f"**{rule.label()}**")
            st.text(rule.quote)
            st.caption(rule.citation["source_title"])
    if rules:
        signature = rules_signature(rules)
        if planner.portfolio.preferences()["approved_rules"] == signature:
            st.success("Đã chọn các nguyên tắc này cho bản tin. Tất cả điều kiện mua phải đạt; một điều kiện bán đạt sẽ được nhắc riêng cho mã đang sở hữu.")
            st.button("Xem bản tin hôm nay", on_click=go, args=("Tổng quan",), type="primary")
        else:
            reviewed = st.checkbox("Tôi đã đối chiếu trích đoạn và đồng ý dùng các nguyên tắc trên", key=f"review_{signature}")
            if st.button("Dùng cho bản tin hằng ngày", disabled=not reviewed, type="primary"):
                planner.portfolio.set_preferences(approved_rules=signature)
                st.rerun()
    else:
        st.info("Chưa đọc được nguyên tắc đủ rõ để tính tín hiệu. Ứng dụng sẽ không tự đặt tỷ lệ mua/bán thay cho tác giả.")
    with st.expander("Tìm kiến thức và quản lý thư viện"):
        query = st.text_input("Tìm đoạn trong sách", placeholder="Ví dụ: biên an toàn, quản lý rủi ro…")
        if query:
            matches = library.search(query, document_id=selected)
            if not matches:
                st.caption("Chưa tìm thấy đoạn khớp. Thử từ khóa khác.")
            for passage in matches:
                st.text(passage.text)
                st.caption(passage.citation()["source_title"])
        for book in documents:
            st.write(f"**{book['title']}** · {book['pages']} trang/phần")
            st.button("Xóa sách", key=f"delete_{book['id']}", on_click=library.delete, args=(book["id"],))


def identities(portfolio: Portfolio) -> list[tuple[str, str]]:
    return list(dict.fromkeys([(row["market"], row["symbol"]) for row in portfolio.holdings()] + [tuple(pair) for pair in portfolio.preferences()["candidates"]]))


def chart_panel(snapshot, days: int = 90, compact: bool = False) -> None:
    summary = price_summary(snapshot, days)
    if summary is None:
        st.info("Nguồn chưa có đủ dữ liệu để vẽ biểu đồ.")
        return
    with st.container(key="price_metrics"):
        columns = st.columns(2 if compact else 4)
        change = summary["change_pct"]
        columns[0].metric(f"{snapshot.symbol} · {snapshot.currency}", f"{summary['latest_close']:,.2f}", f"{change:+.2f}% so phiên trước" if change is not None else None)
        period = summary["period_change_pct"]
        columns[1].metric("Thay đổi giá trong khoảng", f"{period:+.2f}%" if period is not None else "—")
        if not compact:
            columns[2].metric("Số phiên có dữ liệu", summary["observations"])
            columns[3].metric("Mức giảm từ đỉnh trong khoảng", f"{summary['max_drawdown_pct']:.2f}%")
    chart = price_chart(snapshot, days)
    if chart is not None:
        st.altair_chart(chart.interactive(bind_y=False), use_container_width=True, theme=None)
    st.caption(f"{summary['basis_label']} · phiên {summary['as_of']} · {snapshot.provider} · lấy lúc {local_time(snapshot.fetched_at)}")
    if snapshot.cache_stale:
        st.caption("Đang xem bản lưu đã cũ hoặc lần tải lại chưa thành công. Bấm cập nhật để thử lấy dữ liệu mới.")
    st.caption("Biến động giá của mã, chưa phải hiệu suất tài khoản. Bar cuối của nguồn có thể thuộc phiên chưa đóng.")


def report_archive(portfolio: Portfolio) -> None:
    reports = portfolio.recent_reports(60)
    if not reports:
        st.info("Bản tin sẽ được lưu theo ngày khi bạn mở Tổng quan hoặc lịch 07:30 chạy.")
        return
    selected = st.selectbox("Ngày bản tin", [row["day"] for row in reports], key="report_day")
    report = portfolio.report(selected)
    if not report:
        return
    st.caption(f"Bản lưu lúc {local_time(report['created_at'])}. Các mức giá dưới đây thuộc thời điểm của bản tin, không phải giá hiện tại.")
    st.download_button("Tải bản tin JSON", json.dumps(report, ensure_ascii=False, indent=2), file_name=f"breakout-ai-{selected}.json", mime="application/json", key="report_export")
    if not report.get("items"):
        st.info("Bản tin này đang chờ sách, nguyên tắc đã đối chiếu hoặc dữ liệu bổ sung.")
    else:
        columns = st.columns(2)
        for index, item in enumerate(report["items"]):
            with columns[index % 2]:
                action_card(item)


def quote_strip(service: MarketService, portfolio: Portfolio, snapshots=None) -> None:
    """Show sourced prices; never fill an absent price with a synthetic value."""
    tiles = []
    for identity in identities(portfolio)[:service.settings.market_max_symbols]:
        snapshot = snapshots.get(identity) if snapshots is not None else service.cached(*identity)
        summary = price_summary(snapshot) if snapshot else None
        name = escape(":".join(identity))
        if summary:
            change = summary["change_pct"]
            direction = "up" if change is not None and change > 0 else "down" if change is not None and change < 0 else "flat"
            movement = f"{change:+.2f}%" if change is not None else "—"
            status = " · cần làm mới" if snapshot.cache_stale else ""
            tiles.append(f'<div class="quote-tile"><span class="quote-symbol">{name}</span><strong class="{direction}">{summary["latest_close"]:,.2f} <small>{escape(snapshot.currency)}</small></strong><span class="quote-change {direction}">{movement}</span><span class="quote-date">Phiên {escape(summary["as_of"])}{status}</span></div>')
        else:
            tiles.append(f'<div class="quote-tile"><span class="quote-symbol">{name}</span><strong>—</strong><span class="quote-date">Chưa tải giá</span></div>')
    if tiles:
        st.markdown(f'<div class="quote-strip quote-count-{len(tiles)}" style="--quote-columns:{len(tiles)}" aria-label="Giá đóng cửa đã lưu">' + "".join(tiles) + '</div>', unsafe_allow_html=True)


@st.fragment(run_every=300)
def market_board(service: MarketService, portfolio: Portfolio) -> None:
    requested = identities(portfolio)[:service.settings.market_max_symbols]
    with st.container(key="market_data_toolbar"):
        status, refresh = st.columns([3, 1], vertical_alignment="bottom", gap="medium")
        status.markdown('<div class="panel-title">Giá cổ phiếu đang theo dõi</div>', unsafe_allow_html=True)
        force = refresh.button("Cập nhật giá theo dõi", key="quotes_refresh", type="primary", use_container_width=True, disabled=not service.settings.market_enabled or not requested)
    with st.spinner("Đang kết nối dữ liệu giá VN / US…", show_time=True):
        result = load_quotes(service, requested, st.session_state, force=force)
    if force:
        st.rerun()
    quote_strip(service, portfolio, result.snapshots)
    if not service.settings.market_enabled:
        st.info("Nguồn giá đang tắt trong cấu hình. Các mức giá đã lưu, nếu có, chỉ để xem lại.")
    else:
        fresh = sum(not snapshot.cache_stale for snapshot in result.snapshots.values())
        st.caption(f"{fresh}/{len(requested)} mã đã cập nhật · giá theo phiên · tự kiểm tra mỗi 5 phút khi trang mở.")
    if result.errors:
        st.warning("Một số mã chưa cập nhật được. Giá cũ được đánh dấu riêng.")
        with st.expander("Chi tiết kết nối giá"):
            for error in result.errors:
                st.text(error)


def overview_page(planner: DailyPlanner, settings: Settings, store: Store) -> None:
    intro("BẢN TIN 07:30 · GIỜ VIỆT NAM", "Tổng quan đầu tư", "Xem gợi ý hôm nay, kiểm tra danh mục và theo dõi các mã bạn quan tâm.")
    portfolio = planner.portfolio
    report = planner.get_today()
    positions = portfolio.holdings()
    market_board(planner.market, portfolio)
    with st.container(key="overview_metrics"):
        stats = st.columns(4)
        stats[0].metric("Cổ phiếu đang sở hữu", len(positions))
        stats[1].metric("Mã tìm cơ hội mua", len(portfolio.preferences()["candidates"]))
        stats[2].metric("Giao dịch đã ghi", portfolio.trade_count())
        stats[3].metric("Sách trong thư viện", len(planner.books.documents()))
    current, archive, method = st.tabs(["Gợi ý hôm nay", "Lịch sử bản tin", "Cách tạo gợi ý"])
    with current:
        today_page(planner, settings, report)
    with archive:
        report_archive(portfolio)
    with method:
        st.markdown('<div class="workflow-scroll">' + workflow_diagram() + '</div>', unsafe_allow_html=True)
        st.caption("Bản tin áp dụng nguyên tắc đã được bạn đối chiếu. Tin tức để đọc thêm, chưa tự thay đổi điều kiện mua/bán.")
    st.divider()
    with st.container(key="overview_panels"):
        left, right = st.columns([1.7, 1], gap="medium")
        with left:
            with st.container(border=True):
                st.markdown('<div class="panel-title">Biểu đồ theo dõi</div>', unsafe_allow_html=True)
                choices = identities(portfolio)
                if choices:
                    with st.container(key="overview_chart_controls"):
                        selector, refresh = st.columns([2, 1], vertical_alignment="bottom")
                        chosen = selector.selectbox("Mã xem nhanh", choices, format_func=lambda pair: f"{pair[0]}:{pair[1]}", key="overview_symbol")
                        update = refresh.button("Cập nhật biểu đồ", key="overview_refresh", use_container_width=True)
                    snapshot = None
                    if update:
                        try:
                            with st.spinner("Đang lấy dữ liệu giá…"):
                                snapshot = planner.market.get(*chosen, force=True)
                        except MarketError as exc:
                            st.warning(str(exc))
                    if snapshot is None:
                        snapshot = planner.market.cached(*chosen)
                    if snapshot:
                        chart_panel(snapshot, compact=True)
                    else:
                        st.info("Chọn mã và bấm Cập nhật biểu đồ để tải giá theo phiên.")
                else:
                    st.info("Thêm mã trong Danh mục để bắt đầu theo dõi.")
        with right:
            with st.container(border=True):
                st.markdown('<div class="panel-title">Thao tác nhanh</div>', unsafe_allow_html=True)
                st.button("Ghi giao dịch mua / bán", on_click=go, args=("Danh mục", "Ghi giao dịch"), type="primary", use_container_width=True)
                st.button("Hỏi trợ lý AI", on_click=go, args=("Trợ lý AI",), use_container_width=True)
                st.button("Đọc tin thị trường", on_click=go, args=("Tin tức",), use_container_width=True)
            with st.container(border=True):
                st.markdown('<div class="panel-title">Giao dịch gần đây</div>', unsafe_allow_html=True)
                recent = portfolio.trades(limit=4)
                if not recent:
                    st.caption("Chưa ghi giao dịch. Ghi các lần mua bán đã thực hiện để theo dõi tại đây.")
                for trade in recent:
                    action, label = ("buy", "MUA") if trade["side"] == "BUY" else ("sell", "BÁN")
                    st.markdown(f'<div class="journal-row"><div><div class="journal-symbol">{escape(trade["market"])}:{escape(trade["symbol"])}</div><div class="journal-detail">{trade["quantity"]:g} CP · {escape(trade["trade_date"])}</div></div><span class="journal-side {action}">{label}</span></div>', unsafe_allow_html=True)
                st.button("Xem sổ giao dịch", on_click=go, args=("Danh mục", "Lịch sử giao dịch"), use_container_width=True)


def trade_submission(portfolio: Portfolio) -> None:
    state = st.session_state
    try:
        trade = portfolio.record_trade(state.trade_market, state.trade_symbol, state.trade_side, state.trade_quantity, state.trade_price,
                                       fees=state.trade_fees, trade_date=state.trade_date, note=state.trade_note,
                                       idempotency_key=state.trade_submission_id)
        state.trade_notice = ("success", f"Đã ghi {'mua' if trade['side'] == 'BUY' else 'bán'} {trade['quantity']:g} cổ phiếu {trade['symbol']}. Danh mục đã được cập nhật.")
        state.trade_submission_id = uuid4().hex
        state.trade_symbol, state.trade_note = "", ""
    except ValueError as exc:
        state.trade_notice = ("error", str(exc))


def trade_form(portfolio: Portfolio) -> None:
    st.markdown('<div class="panel-title">Ghi lại giao dịch đã thực hiện</div>', unsafe_allow_html=True)
    st.caption("Đây là sổ ghi chép cá nhân. Khi lưu, số lượng và giá vốn trong danh mục sẽ cập nhật; ứng dụng chưa gửi lệnh tới công ty chứng khoán.")
    st.session_state.setdefault("trade_submission_id", uuid4().hex)
    notice = st.session_state.pop("trade_notice", None)
    if notice:
        (st.success if notice[0] == "success" else st.error)(notice[1])
    with st.form("trade_form"):
        market, symbol, side = st.columns(3)
        market.selectbox("Thị trường giao dịch", ["VN", "US"], key="trade_market")
        symbol.text_input("Mã giao dịch", placeholder="FPT / AAPL", max_chars=12, key="trade_symbol")
        side.selectbox("Loại giao dịch", ["BUY", "SELL"], format_func=lambda value: "Mua" if value == "BUY" else "Bán", key="trade_side")
        quantity, price, fees = st.columns(3)
        quantity.number_input("Số cổ phiếu giao dịch", min_value=0.000001, value=100.0, step=1.0, format="%.6f", key="trade_quantity")
        price.number_input("Giá thực hiện / cổ phiếu", min_value=0.000001, value=100.0, step=1.0, format="%.6f", key="trade_price")
        fees.number_input("Tổng phí giao dịch", min_value=0.0, value=0.0, step=1.0, format="%.4f", key="trade_fees")
        st.date_input("Ngày giao dịch", value=datetime.now(VN_TIME).date(), max_value=datetime.now(VN_TIME).date(), key="trade_date")
        st.text_area("Ghi chú giao dịch", placeholder="Lý do mua/bán, nguyên tắc áp dụng hoặc điều cần xem lại…", max_chars=1500, key="trade_note")
        st.caption("VN nhập đầy đủ VND; US nhập USD. Phí mua được cộng vào giá vốn; phí bán được trừ khi tính lãi/lỗ đã chốt. Ghi theo thứ tự ngày; các giao dịch đã lưu được giữ nguyên để sổ và danh mục khớp nhau.")
        st.form_submit_button("Lưu giao dịch", type="primary", on_click=trade_submission, args=(portfolio,))


def trade_history(portfolio: Portfolio) -> None:
    first, second, third = st.columns([1, 1, 2])
    market = first.selectbox("Lọc thị trường giao dịch", ["Tất cả", "VN", "US"], key="trade_filter_market")
    side = second.selectbox("Lọc loại giao dịch", ["Tất cả", "BUY", "SELL"], format_func=lambda value: {"BUY": "Mua", "SELL": "Bán"}.get(value, value), key="trade_filter_side")
    symbol = third.text_input("Tìm mã trong giao dịch", max_chars=12, placeholder="Ví dụ: AAPL", key="trade_filter_symbol").strip().upper()
    filters = {"market": None if market == "Tất cả" else market, "symbol": symbol or None, "side": None if side == "Tất cả" else side}
    with st.expander("Lọc theo ngày giao dịch"):
        use_dates = st.checkbox("Giới hạn khoảng ngày", key="trade_filter_dates")
        begin, end = st.columns(2)
        start_date = begin.date_input("Từ ngày", value=datetime.now(VN_TIME).date().replace(day=1), key="trade_filter_start")
        end_date = end.date_input("Đến ngày", value=datetime.now(VN_TIME).date(), key="trade_filter_end")
        if use_dates:
            filters.update(start_date=start_date, end_date=end_date)
    try:
        trades = portfolio.trades(**filters, limit=500)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.caption("Tối đa 500 giao dịch gần nhất theo bộ lọc. Lãi/lỗ dưới đây chỉ cộng các dòng đang hiển thị, tách riêng tiền tệ; chưa phải hiệu suất toàn tài khoản hoặc báo cáo thuế.")
    if not trades:
        st.info("Chưa có giao dịch phù hợp. Các vị thế nhập ban đầu không được biến thành lịch sử mua giả.")
        return
    with st.container(key="trade_history_metrics"):
        columns = st.columns(2)
        for column, currency in zip(columns, ("VND", "USD")):
            realized = sum(row["realized_pnl"] for row in trades if row["currency"] == currency and row["realized_pnl"] is not None)
            column.metric(f"Lãi/lỗ đã chốt · {currency}", f"{realized:+,.2f}")
    rows = [{"Ngày": row["trade_date"], "Thị trường": row["market"], "Mã": row["symbol"], "Loại": "Mua" if row["side"] == "BUY" else "Bán", "Số lượng": row["quantity"], "Giá": row["price"], "Phí": row["fees"], "Tiền tệ": row["currency"], "Lãi/lỗ đã chốt": row["realized_pnl"], "Còn lại": row["quantity_after"], "Ghi chú": row["note"]} for row in trades]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.download_button("Xuất lịch sử CSV", portfolio.export_trades_csv(**filters), file_name="breakout-ai-transactions.csv", mime="text/csv", key="trade_export")
    st.caption("Tệp xuất tối đa 10.000 dòng theo bộ lọc; chưa chứa những giao dịch bạn chưa ghi vào ứng dụng.")


def portfolio_page(portfolio: Portfolio) -> None:
    intro("TÀI SẢN", "Danh mục & giao dịch", "Cổ phiếu đang giữ, vốn đã đầu tư và lịch sử mua bán của bạn.")
    holdings = portfolio.holdings()
    with st.container(key="portfolio_metrics"):
        columns = st.columns(3)
        columns[0].metric("Mã đang sở hữu", len(holdings))
        for column, market, currency in zip(columns[1:], ("VN", "US"), ("VND", "USD")):
            total = sum(row["quantity"] * row["average_cost"] for row in holdings if row["market"] == market)
            column.metric(f"Vốn vị thế đang mở · {currency}", f"{total:,.2f}")
    st.write("")
    view = st.radio("Nội dung danh mục", ["Danh mục hiện tại", "Ghi giao dịch", "Lịch sử giao dịch"], horizontal=True, key="portfolio_view", label_visibility="collapsed")
    if view == "Danh mục hiện tại":
        holdings_editor(portfolio)
        charts = allocation_chart(holdings)
        if charts:
            chart_columns = st.columns(len(charts))
            for column, (currency, chart) in zip(chart_columns, charts.items()):
                with column:
                    with st.container(border=True):
                        st.altair_chart(chart, use_container_width=True, theme=None)
            st.caption("Phân bổ theo vốn của vị thế đang mở, không cộng gộp VND với USD và không phải giá trị thị trường hiện tại.")
    elif view == "Ghi giao dịch":
        trade_form(portfolio)
    else:
        trade_history(portfolio)


def historical_market_page(settings: Settings, store: Store, portfolio: Portfolio) -> None:
    st.caption("Biểu đồ giá theo phiên · Việt Nam và Mỹ · dữ liệu này tách riêng bảng điện Việt Nam.")
    service = MarketService(settings, store)
    with st.form("market_chart"):
        first, second, third = st.columns([1, 1.8, 1.2])
        market = first.selectbox("Thị trường biểu đồ", ["VN", "US"], key="chart_market")
        symbol = second.text_input("Mã cần xem biểu đồ", value="FPT", max_chars=12, key="chart_symbol")
        days = third.selectbox("Khoảng thời gian", [30, 90, 180], index=1, format_func=lambda value: f"{value} ngày lịch", key="chart_days")
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
                st.warning("Chưa cập nhật được giá; bạn có thể thử lại bằng nút xem biểu đồ.")
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
            st.dataframe([{"Phiên": bar.date, "Giá đóng cửa": bar.close, "Khối lượng": bar.volume, "Giá điều chỉnh": bar.adjusted_close, "Tiền tệ": snapshot.currency} for bar in snapshot.bars], use_container_width=True, hide_index=True)
    else:
        st.info("Chọn thị trường, nhập mã và bấm xem để lấy dữ liệu thật. Ứng dụng không vẽ giá giả khi chưa có dữ liệu.")
    with st.container(key="market_watchlist"):
        st.subheader("Bảng theo dõi cổ phiếu")
        wanted = identities(portfolio)[:service.settings.market_max_symbols]
        force = st.button("Cập nhật bảng theo dõi", key="watchlist_refresh", use_container_width=True, disabled=not settings.market_enabled or not wanted)
        loaded = load_quotes(service, wanted, st.session_state, force=force)
        if force:
            st.rerun()
        rows = []
        for identity in wanted:
            saved = loaded.snapshots.get(identity)
            if saved:
                data = saved.summary()
                rows.append({"Mã": ":".join(identity), "Giá": data["close"], "Tiền tệ": data["currency"], "Thay đổi (%)": data["change_pct"], "Phiên": data["as_of"], "Nguồn": data["provider"], "Trạng thái": "Giá cũ · cần cập nhật" if saved.cache_stale else "Đã cập nhật"})
            else:
                rows.append({"Mã": ":".join(identity), "Giá": None, "Tiền tệ": "VND" if identity[0] == "VN" else "USD", "Thay đổi (%)": None, "Phiên": None, "Nguồn": settings.vn_market_provider if identity[0] == "VN" else settings.us_market_provider, "Trạng thái": "Chưa có dữ liệu"})
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True, column_config={"Giá": st.column_config.NumberColumn(format="%.2f"), "Thay đổi (%)": st.column_config.NumberColumn(format="%+.2f%%")})
            st.caption("Mỗi dòng giữ riêng tiền tệ và phiên nguồn. Dấu trống nghĩa chưa có giá, không phải giá bằng 0.")
        if loaded.errors:
            with st.expander("Các mã chưa cập nhật được"):
                for error in loaded.errors:
                    st.text(error)


def board_symbols(store: Store, portfolio: Portfolio) -> list[str]:
    with store.connection() as db:
        db.execute("CREATE TABLE IF NOT EXISTS board_preferences (workspace TEXT PRIMARY KEY, symbols TEXT NOT NULL)")
        saved = db.execute("SELECT symbols FROM board_preferences WHERE workspace=?", (store.workspace,)).fetchone()
    if saved:
        try:
            symbols = json.loads(saved["symbols"])
            if isinstance(symbols, list) and 0 < len(symbols) <= MAX_SYMBOLS and all(isinstance(value, str) and re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", value) for value in symbols):
                return list(dict.fromkeys(symbols))
        except (ValueError, TypeError):
            pass
    owned = [symbol for market, symbol in identities(portfolio) if market == "VN"]
    return list(dict.fromkeys(owned + list(DEFAULT_SYMBOLS)))[:MAX_SYMBOLS]


def save_board_symbols(store: Store, raw: str) -> None:
    symbols = list(dict.fromkeys(value.upper() for value in re.split(r"[\s,;]+", raw.strip()) if value))
    if not symbols or len(symbols) > MAX_SYMBOLS or any(not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", symbol) for symbol in symbols):
        raise ValueError(f"Nhập 1–{MAX_SYMBOLS} mã Việt Nam, mỗi mã gồm 2–10 ký tự chữ và số, cách nhau bằng dấu phẩy hoặc xuống dòng.")
    with store.connection() as db:
        db.execute("INSERT OR REPLACE INTO board_preferences VALUES (?,?)", (store.workspace, json.dumps(symbols)))


@st.fragment(run_every=5)
def live_priceboard(settings: Settings, store: Store, portfolio: Portfolio) -> None:
    symbols = board_symbols(store, portfolio)
    with st.container(key="live_board_controls"):
        exchange_col, search_col, sort_col, interval_col = st.columns([1, 1.4, 1.4, 1], vertical_alignment="bottom")
        exchange = exchange_col.selectbox("Sàn giao dịch", ["Tất cả", "HOSE", "HNX", "UPCOM"], key="board_exchange")
        search = search_col.text_input("Tìm mã", placeholder="Ví dụ: FPT", max_chars=10, key="board_search").strip().upper()
        order = sort_col.selectbox("Sắp xếp", ["Mã A → Z", "Tăng giá nhiều nhất", "Giảm giá nhiều nhất", "Khối lượng lớn nhất"], key="board_sort")
        interval = interval_col.selectbox("Nhịp cập nhật", [5, 10, 30], format_func=lambda value: f"{value} giây", key="board_interval")
        auto_col, full_col, edit_col, refresh_col = st.columns([1, 1.1, 1.1, 1.3], vertical_alignment="center")
        auto = auto_col.checkbox("Tự cập nhật", value=True, key="board_auto", disabled=not settings.market_enabled)
        full = full_col.checkbox("Đầy đủ thông tin", value=True, key="board_full")
        with edit_col.popover("Danh sách mã", use_container_width=True):
            st.caption("Thêm mã cổ phiếu Việt Nam để xem bảng điện. Bộ lọc bên dưới áp dụng cho danh sách này.")
            st.session_state.setdefault("board_symbols_input", ", ".join(symbols))
            with st.form("board_symbols_form"):
                raw = st.text_area("Mã trên bảng điện", key="board_symbols_input", height=90, max_chars=450)
                saved = st.form_submit_button("Lưu mã trên bảng điện")
            if saved:
                try:
                    save_board_symbols(store, raw)
                    symbols = board_symbols(store, portfolio)
                    st.success("Đã lưu danh sách bảng điện.")
                except ValueError as exc:
                    st.error(str(exc))
        refresh = refresh_col.button("Làm mới bảng giá", type="primary", key="board_refresh", use_container_width=True, disabled=not settings.market_enabled)
    service = RealtimeService(store, poll_seconds=interval)
    if settings.market_enabled and (auto or refresh):
        snapshot = service.fetch(symbols, force=refresh)
    else:
        snapshot = service.cached(symbols) or BoardSnapshot()
    quotes = {quote.symbol: quote for quote in snapshot.quotes}
    visible = [symbol for symbol in symbols if (not search or search in symbol) and (exchange == "Tất cả" or (symbol in quotes and quotes[symbol].exchange == exchange))]
    def sort_value(symbol):
        quote = quotes.get(symbol)
        value = getattr(quote, "total_volume" if order == "Khối lượng lớn nhất" else "change_pct", None)
        return (value is None, -value if value is not None and order != "Giảm giá nhiều nhất" else value or 0, symbol)
    visible.sort(key=None if order == "Mã A → Z" else sort_value)
    status = f"Snapshot DNSE · cập nhật {interval} giây" if auto and settings.market_enabled else "Đã tạm dừng tự cập nhật"
    received = time_label(snapshot.fetched_at) if snapshot.fetched_at else "Chưa tải được dữ liệu"
    st.markdown('<div class="priceboard-toolbar"><div><div class="priceboard-title">Bảng điện Việt Nam</div><div class="priceboard-caption">Giá ×1.000 đ · KL cổ phiếu · GT triệu đồng</div></div><div class="priceboard-status">' + escape(status) + '<span>Lần tải: ' + escape(received) + '</span></div></div>', unsafe_allow_html=True)
    if not settings.market_enabled:
        st.info("Nguồn giá đang tắt trong cấu hình. Bảng chỉ hiển thị bản đã lưu, nếu có.")
    if snapshot.errors:
        st.warning("Kết nối chưa đầy đủ. Các trường thiếu để trống; bản lưu cũ được đánh dấu.")
        with st.expander("Chi tiết kết nối bảng điện"):
            for error in snapshot.errors:
                st.text(error)
    priced = [quotes[symbol] for symbol in visible if symbol in quotes and quotes[symbol].last is not None]
    with st.container(key="live_board_summary"):
        first, second, third, fourth = st.columns(4)
        first.metric("Mã đang hiển thị", f"{len(visible)} / {len(symbols)}")
        second.metric("Tăng · danh sách đang xem", sum(quote.change is not None and quote.change > 0 for quote in priced))
        third.metric("Giảm · danh sách đang xem", sum(quote.change is not None and quote.change < 0 for quote in priced))
        fourth.metric("Tham chiếu · đang xem", sum(quote.change == 0 for quote in priced))
    if snapshot.stale or any(quote.stale for quote in snapshot.quotes):
        st.caption("Dòng mờ: giờ khớp nguồn đã quá 3 phút hoặc chưa có giờ nguồn; có thể ngoài phiên hoặc mã chưa phát sinh giao dịch mới. Độ sâu cũ được ẩn.")
    selected = None
    if visible:
        detail_symbols = sorted(visible)
        previous = st.session_state.get("board_selected")
        # Ranking updates reorder table rows, never the security being inspected.
        st.session_state["board_selected"] = previous if previous in detail_symbols else detail_symbols[0]
        selected = st.session_state["board_selected"]
    st.markdown(board_table(snapshot.quotes, visible, selected=selected, full=full), unsafe_allow_html=True)
    st.markdown('<div class="priceboard-legend"><span class="price-ceiling">● Trần</span><span class="price-up">● Tăng</span><span class="price-ref">● Tham chiếu</span><span class="price-down">● Giảm</span><span class="price-floor">● Sàn</span><span>— Chưa có dữ liệu</span></div>', unsafe_allow_html=True)
    if visible:
        selected = st.selectbox("Chi tiết mã", detail_symbols, key="board_selected")
    quote = quotes.get(selected)
    if quote:
        with st.container(key="market_detail_panels"):
            details, depth = st.columns([1.2, 1], gap="medium")
            with details:
                with st.container(border=True):
                    st.markdown(f'<div class="panel-title">{escape(quote.symbol)} <span class="market-tag">{escape(quote.exchange)}</span> · Thông tin phiên</div>', unsafe_allow_html=True)
                    left, right = st.columns(2)
                    left.metric("Giá khớp · VND / CP", format_number(quote.last), f"{quote.change_pct:+.2f}%" if quote.change_pct is not None else None)
                    right.metric("Tổng khối lượng · CP", format_number(quote.total_volume))
                    st.caption(f"Mở {format_number(quote.open)} · Cao {format_number(quote.high)} · Thấp {format_number(quote.low)} · TB {format_number(quote.average)} VND")
                    st.caption(f"Nước ngoài · mua {format_number(quote.foreign_buy_volume)} CP · bán {format_number(quote.foreign_sell_volume)} CP")
                    st.caption(f"Giờ khớp nguồn: {time_label(quote.source_timestamp)}")
                    st.caption(f"Nguồn: {snapshot.source} · nhận lúc {time_label(quote.received_at)}")
            with depth:
                with st.container(border=True):
                    st.markdown('<div class="panel-title">Dư mua / dư bán · 3 mức giá</div>', unsafe_allow_html=True)
                    st.markdown(depth_table(quote), unsafe_allow_html=True)
                    st.caption(f"Giờ sổ lệnh nguồn: {time_label(quote.depth_timestamp)} · giá ×1.000 đ, KL cổ phiếu")
    elif selected:
        st.info(f"{selected}: nguồn chưa trả về dữ liệu hợp lệ. Bạn có thể kiểm tra mã hoặc thử làm mới.")
    st.caption("Bảng tải snapshot theo nhịp đã chọn khi đang mở trang. Dữ liệu phụ thuộc nguồn; chưa phải luồng đẩy từng giao dịch.")
    st.markdown("[Mở bảng giá DNSE để đối chiếu](https://banggia.dnse.com.vn/v2)")


def market_page(settings: Settings, store: Store, portfolio: Portfolio) -> None:
    intro("THỊ TRƯỜNG", "Bảng giá & biểu đồ", "Theo dõi cung cầu, khớp lệnh và thông tin phiên trong một bảng.")
    view = st.radio("Nội dung thị trường", ["Bảng điện Việt Nam", "Biểu đồ VN / US"], key="market_view", horizontal=True, label_visibility="collapsed")
    if view == "Bảng điện Việt Nam":
        live_priceboard(settings, store, portfolio)
    else:
        historical_market_page(settings, store, portfolio)


@st.fragment(run_every=900)
def news_panel(store: Store) -> None:
    first, second, third = st.columns([1, 2.4, 1.2], vertical_alignment="bottom")
    market = first.selectbox("Thị trường tin tức", ["BOTH", "VN", "US"], format_func=lambda value: {"BOTH": "Tất cả", "VN": "Việt Nam", "US": "Mỹ"}[value], key="news_market")
    search = second.text_input("Tìm trong tiêu đề", placeholder="Nhập doanh nghiệp hoặc chủ đề…", key="news_search").strip().casefold()
    refresh = third.button("Cập nhật tin tức", type="primary", key="news_refresh", use_container_width=True)
    with st.spinner("Đang lấy tiêu đề từ nguồn báo…"):
        result = NewsService(store).fetch(market, force=refresh)
    if result.fetched_at:
        st.caption(f"Lần lấy nguồn: {local_time(result.fetched_at)} · tự kiểm tra lại sau 15 phút khi trang đang mở.")
    if result.errors:
        st.warning("Một số nguồn chưa cập nhật được. Tin lưu cũ, nếu có, được đánh dấu riêng.")
        with st.expander("Tình trạng nguồn báo"):
            for error in result.errors:
                st.text(error)
    articles = [article for article in result.articles if search in article.title.casefold()]
    if not articles:
        st.info("Chưa có tin phù hợp. Bạn có thể đổi thị trường, từ khóa hoặc thử cập nhật lại.")
        return
    st.caption(f"{len(articles)} tiêu đề · bấm tiêu đề để đọc bài gốc tại tòa soạn.")
    for article in articles[:40]:
        published = local_time(article.published_at) if article.published_at else "Nguồn chưa ghi ngày"
        stale = '<span class="news-stale">Bản lưu · cần cập nhật</span>' if article.cache_stale else ""
        market_label = "VN" if article.market == "VN" else "US"
        st.markdown(f'<article class="news-row"><div class="news-meta"><span class="news-market">{market_label}</span><span class="news-source">{escape(article.source)}</span><time>{escape(published)}</time>{stale}</div><a class="news-title" href="{escape(article.url, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(article.title)} <span aria-hidden="true">↗</span></a></article>', unsafe_allow_html=True)
    if len(articles) > 40:
        st.caption("Đang hiển thị 40 tin đầu. Nhập từ khóa để tìm trong tất cả tiêu đề đã lấy.")


def news_page(store: Store) -> None:
    intro("THÔNG TIN", "Tin tức thị trường", "Lọc thị trường, tìm doanh nghiệp và đọc bài gốc tại tòa soạn.")
    st.caption("Tiêu đề RSS để đọc thông tin, chưa phải dữ liệu đã xác minh từng mệnh đề hoặc tín hiệu giao dịch. Nội dung đầy đủ mở tại trang báo.")
    news_panel(store)
    with st.expander("Các nguồn đang kết nối"):
        for feed in FEEDS:
            st.markdown(f"**{feed.name}** · {feed.market} · [Trang nguồn]({feed.website})")
        st.caption("Các kết nối hiện phục vụ phát triển cá nhân; cần thỏa thuận quyền sử dụng phù hợp trước khi phân phối thương mại.")


def open_conversation(identifier: str) -> None:
    st.session_state.conversation_id = identifier


def rename_chat(store: Store, identifier: str, field_key: str) -> None:
    try:
        store.rename_conversation(identifier, st.session_state[field_key])
        st.session_state.chat_rename_notice = ("success", "Đã đổi tên cuộc trò chuyện.")
    except ValueError as exc:
        st.session_state.chat_rename_notice = ("error", str(exc))


def chat_history_sidebar(store: Store) -> None:
    with st.sidebar:
        st.divider()
        st.button("＋ Trò chuyện mới", on_click=new_conversation, args=(store,), use_container_width=True, key="new_chat")
        query = st.text_input("Tìm lịch sử chat", placeholder="Tìm cuộc trò chuyện…", key="chat_history_search", label_visibility="collapsed").strip().casefold()
        st.markdown('<div class="side-label">LỊCH SỬ TRÒ CHUYỆN</div>', unsafe_allow_html=True)
        conversations = [row for row in store.conversations() if query in row["title"].casefold()]
        if not conversations:
            st.caption("Chưa có kết quả." if query else "Cuộc trò chuyện của bạn sẽ xuất hiện ở đây.")
        count = st.session_state.get("chat_history_limit", 20)
        with st.container(height=260, border=False, key="chat_history_list"):
            for conversation in conversations[:count]:
                active = conversation["id"] == st.session_state.get("conversation_id")
                st.button(conversation["title"], key=f"conversation_{conversation['id']}", on_click=open_conversation, args=(conversation["id"],), use_container_width=True, type="primary" if active else "secondary", help=f"Tạo lúc {local_time(conversation['created_at'])}")
            if len(conversations) > count and st.button("Xem thêm hội thoại"):
                st.session_state.chat_history_limit = count + 20
                st.rerun()


def chat_page(settings: Settings, store: Store, library: BookLibrary) -> None:
    chat_history_sidebar(store)
    identifier = st.session_state.get("conversation_id")
    history = store.messages(identifier)
    current = next((row for row in store.conversations() if row["id"] == identifier), None)
    title = current["title"] if current else "Cuộc trò chuyện mới"
    mode = "Tra cứu trích đoạn" if settings.provider == "demo" else "Trợ lý AI"
    st.markdown(f'<div class="chat-toolbar"><strong>{escape(title)}</strong><span>{mode}</span></div>', unsafe_allow_html=True)
    if settings.provider == "demo":
        st.caption("Đang dùng chế độ tra cứu. Có thể tìm sách và tính toán; cần cấu hình mô hình để trò chuyện tự nhiên.")
    suggested_prompt = None
    if not history:
        st.markdown(f'<div class="chat-welcome"><div class="chat-emblem" aria-hidden="true">{BRAND_MARK}</div><div class="chat-brand">BREAKOUT AI</div><h1>Bạn muốn tìm hiểu điều gì?</h1><p>Hỏi về cổ phiếu, kiến thức tài chính hoặc sách của bạn.</p></div>', unsafe_allow_html=True)
        for column, question in zip(st.columns(3), ("Biên an toàn là gì?", "Giá VN:FPT gần nhất?", "Giải thích đường trung bình")):
            if column.button(question, use_container_width=True):
                suggested_prompt = question
        st.markdown('<p class="chat-hint">Ví dụ mã: VN:FPT · US:AAPL &nbsp;|&nbsp; Hội thoại được lưu tự động</p>', unsafe_allow_html=True)
    else:
        for row in history:
            with st.chat_message(row["role"], avatar=None if row["role"] == "user" else ":material/auto_awesome:"):
                st.markdown(re.sub(r"\[B[a-f0-9]{32}_\d+\]", "", row["content"]))
                sources = row["metadata"].get("sources", [])
                if sources:
                    with st.expander(f"{len(sources)} tài liệu tham khảo"):
                        for source in sources:
                            st.text(source.get("source_title", source.get("title", "")))
                            if source.get("source_url"):
                                st.link_button("Mở nguồn", source["source_url"])
        with st.sidebar.expander("Tùy chọn cuộc trò chuyện"):
            notice = st.session_state.pop("chat_rename_notice", None)
            if notice:
                (st.success if notice[0] == "success" else st.error)(notice[1])
            with st.form("rename_chat"):
                field_key = f"chat_title_{identifier}"
                st.session_state.setdefault(field_key, current["title"] if current else "")
                st.text_input("Tên cuộc trò chuyện", key=field_key, max_chars=100)
                st.form_submit_button("Lưu tên cuộc trò chuyện", on_click=rename_chat, args=(store, identifier, field_key))
            st.download_button("Xuất hội thoại JSON", json.dumps({"conversation": current, "messages": history}, ensure_ascii=False, indent=2), file_name=f"breakout-ai-chat-{identifier}.json", mime="application/json", key="chat_export", use_container_width=True)
            st.button("Xóa hội thoại đang mở", on_click=new_conversation, args=(store, True), key="delete_chat", use_container_width=True)
    # Root-level chat_input uses Streamlit's fixed bottom composer, including on mobile.
    prompt = st.chat_input("Hỏi Breakout AI…", max_chars=settings.max_input_chars) or suggested_prompt
    if prompt:
        try:
            tutor = Tutor(settings, market_service=MarketService(settings, store), books=library)
            with st.spinner("Đang tìm kiến thức và chuẩn bị câu trả lời…"):
                st.session_state.conversation_id = chat_turn(store, tutor, prompt, identifier, "BOTH", next(iter(STYLES)))
            st.rerun()
        except (ValueError, ProviderError) as exc:
            st.error(str(exc))


def main() -> None:
    try:
        settings = Settings.from_env()
        store = Store(settings.database_path, settings.workspace_id)
        portfolio, library = Portfolio(store), BookLibrary(store)
        planner = DailyPlanner(settings, portfolio, library, MarketService(settings, store))
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    pages = {"Tổng quan": "Tổng quan", "Thị trường": "Bảng điện & biểu đồ", "Danh mục": "Danh mục & giao dịch", "Tin tức": "Tin tức", "Trợ lý AI": "Chat AI", "Thư viện sách": "Thư viện sách"}
    if st.session_state.get("page") not in pages:
        st.session_state.page = "Tổng quan"
    with st.sidebar:
        st.markdown(f'<div class="side-brand"><span class="brand-mark" aria-hidden="true">{BRAND_MARK}</span><div class="brand-wordmark">Breakout <span>AI</span><small>Đầu tư có cơ sở</small></div></div>', unsafe_allow_html=True)
        page = st.radio("Điều hướng", list(pages), format_func=pages.get, key="page", label_visibility="collapsed")
        if page != "Trợ lý AI":
            st.markdown('<div class="side-status"><span class="status-dot"></span> Snapshot VN · Biểu đồ VN / US</div>', unsafe_allow_html=True)
            with st.expander("Bản tin 07:30 · giờ Việt Nam"):
                st.caption(schedule_caption(settings))
            st.caption("Lịch sử và danh mục lưu trên máy.")
    mode = "chat" if page == "Trợ lý AI" else "terminal"
    view = {"Tin tức": "news", "Thư viện sách": "books", "Danh mục": "portfolio", "Thị trường": "market", "Trợ lý AI": "chat"}.get(page, "overview")
    st.markdown(f'<div class="workspace-mode-{mode}" data-view="{view}"></div>', unsafe_allow_html=True)
    if page != "Trợ lý AI":
        now = datetime.now(VN_TIME).strftime("%d/%m/%Y")
        st.markdown(f'<div class="topline"><span>BREAKOUT AI <span class="top-divider">/</span> <b>{escape(pages[page])}</b></span><span>{now}<span class="market-pill">VN · VND</span><span class="market-pill">US · USD</span></span></div>', unsafe_allow_html=True)
    if page == "Tổng quan":
        overview_page(planner, settings, store)
    elif page == "Danh mục":
        portfolio_page(portfolio)
    elif page == "Thị trường":
        market_page(settings, store, portfolio)
    elif page == "Tin tức":
        news_page(store)
    elif page == "Thư viện sách":
        books_page(library, planner)
    else:
        chat_page(settings, store, library)
    if page != "Trợ lý AI":
        st.markdown('<div class="footer">Breakout AI · Nguồn và thời điểm ghi rõ trên từng bảng · Giao dịch lưu vào sổ cá nhân.</div>', unsafe_allow_html=True)


main()


