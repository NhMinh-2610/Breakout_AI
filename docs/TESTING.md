# Kiểm thử Breakout AI 0.6
## Kết quả ngày 19/10/2026
**238 tests passed, 1 warning**, 54,71 giây. Môi trường Python 3.13.5, Streamlit 1.45.1, Altair 5.5.0, pytest 8.3.4. Warning là API theme nội bộ Streamlit gọi Altair đã deprecated, không làm lỗi kiểm thử.

Bằng chứng JUnit: `.artifacts/rebrand-tests.xml`. Đây là kết quả local, chưa phải GitHub Actions đã chạy.

## Phạm vi
| Nhóm | Hành vi |
| --- | --- |
| Finance, screening | Công thức, đơn vị, NaN/inf, cửa sổ giá, thiếu dữ liệu |
| Storage, config | Scope workspace, quota, schema, cấu hình và lựa chọn DB sau đổi tên |
| Market, news | Hợp đồng HTTP giả lập, cache, stale, URL/XML và nguồn |
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
