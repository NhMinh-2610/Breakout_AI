"""Small presentation helpers shared by the investment workspace pages."""

from datetime import datetime
from html import escape

import streamlit as st

from breakout_ai.daily import VN_TIME
from breakout_ai.dashboard import price_chart, price_summary
from breakout_ai.portfolio import Portfolio


def intro(kicker: str, title: str, description: str) -> None:
    st.markdown(
        f'<div class="masthead"><div class="eyebrow">{escape(kicker)}</div><h1>{escape(title)}</h1><p>{escape(description)}</p></div>',
        unsafe_allow_html=True,
    )


def local_time(value: str) -> str:
    return (
        datetime.fromisoformat(value).astimezone(VN_TIME).strftime("%H:%M · %d/%m/%Y")
    )


def identities(portfolio: Portfolio) -> list[tuple[str, str]]:
    return list(
        dict.fromkeys(
            [(row["market"], row["symbol"]) for row in portfolio.holdings()]
            + [tuple(pair) for pair in portfolio.preferences()["candidates"]]
        )
    )


def chart_panel(snapshot, days: int = 90, compact: bool = False) -> None:
    summary = price_summary(snapshot, days)
    if summary is None:
        st.info("Nguồn chưa có đủ dữ liệu để vẽ biểu đồ.")
        return
    with st.container(key="price_metrics"):
        columns = st.columns(2 if compact else 4)
        change = summary["change_pct"]
        columns[0].metric(
            f"{snapshot.symbol} · {snapshot.currency}",
            f"{summary['latest_close']:,.2f}",
            f"{change:+.2f}% so phiên trước" if change is not None else None,
        )
        period = summary["period_change_pct"]
        columns[1].metric(
            "Thay đổi giá trong khoảng",
            f"{period:+.2f}%" if period is not None else "—",
        )
        if not compact:
            columns[2].metric("Số phiên có dữ liệu", summary["observations"])
            columns[3].metric(
                "Mức giảm từ đỉnh trong khoảng", f"{summary['max_drawdown_pct']:.2f}%"
            )
    chart = price_chart(snapshot, days)
    if chart is not None:
        st.altair_chart(
            chart.interactive(bind_y=False), use_container_width=True, theme=None
        )
    st.caption(
        f"{summary['basis_label']} · phiên {summary['as_of']} · {snapshot.provider} · lấy lúc {local_time(snapshot.fetched_at)}"
    )
    if snapshot.cache_stale:
        st.caption(
            "Đang xem bản lưu đã cũ hoặc lần tải lại chưa thành công. Bấm cập nhật để thử lấy dữ liệu mới."
        )
    st.caption(
        "Biến động giá của mã, chưa phải hiệu suất tài khoản. Bar cuối của nguồn có thể thuộc phiên chưa đóng."
    )
