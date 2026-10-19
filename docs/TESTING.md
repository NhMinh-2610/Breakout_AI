# Kiểm thử Breakout AI 0.8

## Phạm vi bản 0.8 — 19/10/2026

**509 kiểm thử đạt**, không lỗi, thời gian 120.11 giây. Có 47 ca adapter nến/chỉ số, 41 ca kỹ thuật, 45 ca copilot/biểu đồ và 10 ca tích hợp workbench mới. Các mốc 366/247 bên dưới thuộc bản trước. JUnit: .artifacts/terminal-v08-tests.xml.

- CSS: 408 rule không lỗi, 92 liên kết Markdown nội bộ hợp lệ. Cấu trúc selector đối chiếu frontend Streamlit 1.45.1; .artifacts/css-layout-evidence.json.
- HTTP trang/health đều 200, tiến trình thử đã dừng: .artifacts/terminal-v08-http-smoke.json.
- Compileall đạt. Bản tổng hợp bằng chứng: .artifacts/terminal-v08-validation.json.
- Một cảnh báo deprecation Altair từ Streamlit không làm lỗi kiểm thử. Chưa xác minh hình ảnh trình duyệt.

Đã chạy riêng **47 kiểm thử adapter intraday đạt**: đơn vị cổ phiếu/chỉ số, khung 1/5/15 phút, nến đang hình thành, khối lượng thiếu, dữ liệu lỗi, giới hạn phản hồi, cache theo workspace, thời gian nguồn cũ, cooldown 403/429 và chống request trùng giữa nhiều instance.

Smoke service thật ngày 19/10/2026 lấy được VIC 230 nến, VNINDEX 230, VN30 230, HNX 245 và UPCOM 270 trong cửa sổ 7 ngày. Ngoài giờ giao dịch, nguồn được đánh dấu cũ đúng; không dùng lần HTTP 200 này để khẳng định feed có SLA hoặc cập nhật từng tick. Artifact: `.artifacts/intraday-live-smoke.json`.

Phạm vi nghiệm thu tích hợp:

- Chỉ báo/tín hiệu: RSI, SMA20, vùng giá và khối lượng nền loại nến xác nhận; nến chưa đóng không xác nhận tín hiệu; giá/nến cũ hoặc lỗi chặn hành động; rà soát bán chỉ cho mã sở hữu.
- Biểu đồ: giá/khối lượng giữ đúng đơn vị, chỉ số giữ điểm, nguồn thiếu không dựng đường giả, nến đang hình thành có trạng thái riêng.
- Workbench: bảng giá phía trên, mã đang xem ổn định, đổi khung nến, tạm dừng không gọi nguồn, scanner tối đa 6 mã sau thao tác bắt đầu.
- Chat: câu hỏi lấy bối cảnh mã khi gửi, lưu lịch sử, không tự gửi lại khi fragment cập nhật; model không được gọi theo chu kỳ tải thị trường.
- Layout: gap ngang cột gốc giữ 16px, lưới có key quản lý width/gap riêng, selector panel không áp border/padding lên toàn bộ khối tổ tiên.

Chạy phần mới:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_intraday.py tests/test_technical.py tests/test_workbench_ui.py
```

Kiểm tra CSS/parser và AppTest không đo vị trí phần tử trên màn hình. Browser không khả dụng trong phiên; chưa xác minh screenshot/pixel/mobile. Cần kiểm tra lại ảnh thật theo các kích thước ở [UI/UX](UI_UX.md).

## Kết quả bản 0.7 — 19/10/2026

**366 kiểm thử đạt**, không lỗi; JUnit: .artifacts/priceboard-tests.xml. Trong đó có 76 kiểm thử adapter DNSE, 36 kiểm thử renderer và 7 kiểm thử giao diện bảng điện. Bộ kiểm thử dùng dữ liệu giả lập; yêu cầu HTTP thật được xác minh riêng.

- API DNSE thật: 6 mã trên HOSE/HNX/UPCOM lúc 20:13 giờ Việt Nam ngày 19/10, không có lỗi. Giá và độ sâu được đánh dấu cũ đúng vì ngoài phiên; bằng chứng .artifacts/priceboard-live-api.json.
- HTTP trang/health đều 200, tiến trình thử đã dừng: .artifacts/priceboard-http-smoke.json.
- CSS: 281 rule không lỗi cú pháp; 75 liên kết Markdown nội bộ hợp lệ. Bằng chứng .artifacts/priceboard-static-validation.json.
- Kiểm tra compileall đạt. Chưa có QA hình ảnh, kích thước thực tế hoặc thiết bị di động do Browser không khả dụng.

## Mốc trước bảng điện — 19/10/2026

**247 tests passed, 1 warning**, 51,86 giây. Môi trường Python 3.13.5, Streamlit 1.45.1, Altair 5.5.0, pytest 8.3.4. Warning là API theme nội bộ Streamlit gọi Altair đã deprecated, không làm lỗi kiểm thử.

Bằng chứng JUnit: `.artifacts/rebrand-tests.xml`. Đây là kết quả local, chưa phải GitHub Actions đã chạy.

## Kiểm tra bảng điện DNSE

Phạm vi đã kiểm tra cho lần cập nhật này:

- Hợp đồng snapshot: ba mức mua/bán, tham chiếu/trần/sàn, chuẩn hóa VND/cổ phiếu, dữ liệu thiếu, giới hạn danh sách và phản hồi không hợp lệ.
- Cache: scope workspace, nhịp 5/10/30 giây, cập nhật thủ công, đọc khi tạm dừng, lỗi nguồn và thời gian cũ cho giá/độ sâu.
- Renderer: nhóm cột, đơn vị, năm màu giá, escape HTML, dấu gạch khi thiếu và ẩn độ sâu quá cũ.
- UI: bảng điện là mặc định, lọc/tìm/sắp xếp/chọn mã, đầy đủ/rút gọn và chuyển sang biểu đồ ngày VN/US.
- HTTP thật được kiểm tra riêng với nguồn công khai; không dùng mạng trong unit test. Ghi rõ thời điểm kiểm tra thay vì xem một lần HTTP 200 là bảo đảm nguồn luôn hoạt động.

Các mốc 247/238 test bên dưới được giữ làm lịch sử; kết quả mới nằm ở đầu tài liệu. AppTest kiểm tra thao tác và trạng thái; độ trễ thị trường, chu kỳ thực tế trên trình duyệt và bố cục cần đo riêng.

Chạy tập trung trước khi chạy toàn bộ:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_realtime.py tests/test_priceboard.py tests/test_priceboard_ui.py tests/test_workspace_ui.py
```

## Cập nhật API và khoảng cách giao diện

- Thêm 3 case về batch HTTP dùng chung client và chuẩn hóa mã trước giới hạn.
- Thêm 4 case market_view về cache, tự tải, cooldown, tắt nguồn, scope và giữ stale.
- Thêm 2 case UI về cập nhật cả nhóm/biểu đồ và lỗi nguồn vẫn giữ nhãn cũ.
- API thật FPT/VCB/VNM/AAPL/MSFT/GOOGL thành công, không lỗi hoặc stale; bằng chứng local .artifacts/market-api-ui-check.json.
- CSS đã chuẩn hóa control/thẻ/khoảng cách và dùng key riêng cho hàng metric; parser không thay thế QA ảnh.
- Browser vẫn không khả dụng; chưa xác minh pixel/mobile.

## Phạm vi

| Nhóm | Hành vi |
| --- | --- |
| Finance, screening | Công thức, đơn vị, NaN/inf, cửa sổ giá, thiếu dữ liệu |
| Storage, config | Scope workspace, quota, schema, cấu hình và lựa chọn DB sau đổi tên |
| Market, news | Hợp đồng HTTP giả lập, cache, stale, URL/XML và nguồn |
| Realtime, priceboard | Snapshot DNSE, đơn vị, độ sâu, thời gian nguồn, cache và HTML bảng điện |
| Intraday, technical | Nến/chỉ số, đơn vị riêng, cache/cooldown, chỉ báo và kiểm tra tín hiệu |
| Workbench, copilot | Biểu đồ, mã/khung nến, chat bối cảnh và scanner theo thao tác |
| Books, knowledge | Trích xuất, trang/đoạn, giới hạn, scope và truy xuất |
| Providers, tutor, research | Request/response, lỗi, lịch sử, nguồn và phạm vi |
| Daily | Nguyên tắc, kết hợp điều kiện, mốc phiên, fingerprint, thiếu dữ liệu |
| Trades | Phí, giá vốn, lãi/lỗ, transaction, idempotency, bán vượt, cổ phiếu lẻ |
| Dashboard | Chuỗi giá, MA20, tỷ trọng VND/USD và spec Altair |
| App, workspace UI | Sáu trang, form, chat, nguồn, archive, tin tức và lối tắt |

Bản 0.6 thêm ba trường hợp database: cài mới; chỉ có DB cũ; cả DB cũ/mới. File cũ được ưu tiên và nội dung không bị sửa bởi bộ chọn đường dẫn. Những test còn lại chạy lại với import package mới.

## Chạy lại

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall -q app.py breakout_ai tests
```

Trong môi trường thực thi hiện tại, cache/temp cũ có hạn chế quyền nên lần kiểm tra dùng thư mục mới:
```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .artifacts/pytest-breakout-full -o cache_dir=.artifacts/pytest-breakout-full-cache --junitxml=.artifacts/rebrand-tests.xml
```
Nếu cần giữ kết quả temp cũ, chọn tên basetemp mới; pytest có thể dọn basetemp được chỉ định. Test dùng DB tạm, không thêm dữ liệu giao dịch mẫu vào database thật.

## Xác minh bản đổi tên

- 171 rule CSS được parse, không có lỗi declaration; các link Markdown nội bộ được kiểm tra.
- Metadata `breakout-ai`, package `breakout_ai`, version `0.6.0` và schema v4 nhất quán.
- Số bản ghi conversations/messages/holdings/trades/books khớp trước chuyển đổi; giữ file database hiện có.
- Task `BreakoutAI-Morning-d663cadb1694` dùng đúng pythonw/root/package. Chạy thử hoàn tất, `last_result=0`, lịch 07:30 giờ Việt Nam.
- Server thử trả 200 cho trang và 200 ok cho health; đã dừng tiến trình thử. Chi tiết: `.artifacts/breakout-ui-smoke.json`.
- Bằng chứng cấu hình/CSS/dữ liệu: `.artifacts/rebrand-validation.json`.

## Giới hạn xác minh

Browser tích hợp không có công cụ khả dụng trong phiên. Chưa có screenshot, kiểm tra pixel/mobile, screen reader hoặc chứng nhận WCAG. AppTest xác minh widget và state, không xác minh CSS trên thiết bị thật.

Chưa gọi model thật vì chưa cấu hình model/key; adapter dùng dữ liệu giả lập. Kiểm thử phần mềm không chứng minh chất lượng tư vấn hoặc hiệu quả đầu tư. Giá/RSS thật đã từng được kiểm tra ngày 18/10/2026; lần đổi tên không được mô tả là kiểm tra lại toàn bộ nguồn, giấy phép hoặc độ chính xác nội dung.

## Checklist tiếp theo

- Desktop 1366×768, 1920×1080 và điện thoại 390px: căn cột, logo, ô nhập, sidebar và bảng.
- Tab/Shift+Tab, focus, đọc bằng screen reader và tương phản của control thực tế.
- Model thật: câu thiếu dữ liệu, câu tiếp nối, nguồn mâu thuẫn, yêu cầu ngoài phạm vi, prompt injection trong sách.
- Sách có quyền: kiểm tra truy xuất, ngoại lệ câu điều kiện và ngữ cảnh cùng người có chuyên môn.
- Phục hồi backup vào DB riêng; kiểm tra mất mạng, lỗi nguồn, quota và dữ liệu nhập sai.

[UI/UX](UI_UX.md) · [Vận hành](OPERATIONS.md) · [Chuyển đổi](MIGRATION.md).
