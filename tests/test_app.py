from streamlit.testing.v1 import AppTest

from breakout_ai.config import ROOT
from breakout_ai.news import NewsResult, NewsService


def app(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "demo")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ui.sqlite3"))
    monkeypatch.setenv("WORKSPACE_ID", "test-ui")
    monkeypatch.setattr(NewsService, "fetch", lambda self, market="BOTH", force=False: NewsResult([], [], None))
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()


def button(at, label):
    return next(item for item in at.button if item.label == label)


def test_empty_home_and_six_navigation_pages(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path)
    assert not at.exception and at.sidebar.radio
    assert len(at.sidebar.radio[0].options) == 6
    button(at, "1. Thêm cuốn sách đầu tiên").click().run()
    assert not at.exception and at.sidebar.radio[0].value == "Thư viện sách"
    for page in ["Danh mục", "Thư viện sách", "Trợ lý AI", "Thị trường", "Tin tức", "Tổng quan"]:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page


def test_chat_followup_and_delete(monkeypatch, tmp_path):
    at = app(monkeypatch, tmp_path)
    at.sidebar.radio[0].set_value("Trợ lý AI").run()
    at.chat_input[0].set_value("P/E là gì?").run()
    assert not at.exception and len(at.chat_message) == 2
    at.chat_input[0].set_value("Cho ví dụ khác").run()
    assert not at.exception and len(at.chat_message) == 4
    button(at, "Xóa hội thoại đang mở").click().run()
    assert not at.exception and len(at.chat_message) == 0


def test_owned_position_add_remove_and_invalid_candidates(monkeypatch, tmp_path):
    from breakout_ai.portfolio import Portfolio
    from breakout_ai.storage import Store
    at = app(monkeypatch, tmp_path)
    at.sidebar.radio[0].set_value("Danh mục").run()
    next(item for item in at.text_input if item.label == "Mã cổ phiếu").set_value("AAPL")
    next(item for item in at.selectbox if item.label == "Thị trường").select("US")
    next(item for item in at.number_input if item.label == "Số lượng đang có").set_value(10)
    next(item for item in at.number_input if item.label == "Giá mua bình quân / cổ phiếu").set_value(150)
    button(at, "Lưu cổ phiếu").click().run()
    holdings = Portfolio(Store(tmp_path / "ui.sqlite3", "test-ui")).holdings()
    assert not at.exception and holdings[0]["symbol"] == "AAPL" and holdings[0]["average_cost"] == 150
    assert next(item for item in at.metric if item.label == "Mã đang sở hữu").value == "1"
    assert next(item for item in at.metric if item.label == "Vốn vị thế đang mở · USD").value == "1,500.00"
    assert len(at.get("arrow_vega_lite_chart")) == 1
    assert at.text_input(key="initial_symbol").value == ""
    button(at, "Bỏ khỏi danh mục").click().run()
    assert not at.exception and not any(item.label == "Bỏ khỏi danh mục" for item in at.button)
    assert next(item for item in at.metric if item.label == "Mã đang sở hữu").value == "0"
    assert next(item for item in at.metric if item.label == "Vốn vị thế đang mở · USD").value == "0.00"
    assert not at.get("arrow_vega_lite_chart")
    next(item for item in at.text_area if item.label == "Danh sách tìm mua").set_value("AAPL")
    button(at, "Lưu danh sách tìm mua").click().run()
    assert not at.exception and at.error


def test_book_review_then_daily_cards_and_delete(monkeypatch, tmp_path):
    from breakout_ai.books import BookLibrary
    from breakout_ai.market import MarketService
    from breakout_ai.storage import Store
    from test_daily import quote
    monkeypatch.setattr(MarketService, "many", lambda self, identities, force=False: ([quote()], []))
    at = app(monkeypatch, tmp_path)
    library = BookLibrary(Store(tmp_path / "ui.sqlite3", "test-ui"))
    library.ingest("rules.txt", b"Buy when price is above MA 20.", "Test rule book")
    at.sidebar.radio[0].set_value("Thư viện sách").run()
    assert not at.exception and button(at, "Dùng cho bản tin hằng ngày").disabled
    at.checkbox[0].check().run()
    button(at, "Dùng cho bản tin hằng ngày").click().run()
    button(at, "Xem bản tin hôm nay").click().run()
    assert not at.exception and len(at.metric) == 8
    assert next(item for item in at.metric if item.label == "Cân nhắc mua").value == "1"
    assert any("Vì sao" in item.label for item in at.expander)
    at.sidebar.radio[0].set_value("Thư viện sách").run()
    next(item for item in at.text_input if item.label == "Tìm đoạn trong sách").set_value("moving average").run()
    button(at, "Xóa sách").click().run()
    assert not at.exception and library.documents() == []
    at.sidebar.radio[0].set_value("Tổng quan").run()
    assert not at.exception and len(at.metric) == 4
