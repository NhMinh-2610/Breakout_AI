# Phát triển Breakout AI
## Thiết lập
Dùng Python 3.11+, source checkout và dependencies pin trong requirements/pyproject. Không cần GPU để chạy test.
```powershell
.\scripts\setup.ps1 -Dev
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall -q app.py breakout_ai tests
```

Import bằng `breakout_ai`; các CLI trong README dùng package mới. Tài nguyên UI/content vẫn đọc từ checkout, chưa có wheel độc lập chứa đủ tài nguyên. [Kiến trúc](ARCHITECTURE.md).

## Quy tắc sửa mã
- Tách công thức, dữ liệu, provider và UI.
- Số liệu phải giữ tiền tệ, kỳ, ngày và nguồn; không tạo dữ liệu hiện tại thiếu adapter.
- Không log key, toàn bộ prompt hoặc response lỗi thô.
- Chỉ HTML tĩnh hoặc chuỗi escape mới dùng unsafe_allow_html.
- Test hành vi có rủi ro: transaction, quota, workspace, stale, chuyển trang và bảo toàn dữ liệu.
- Không tăng version schema chỉ để đổi thương hiệu; database migration phải có kế hoạch backup.

## Mở rộng nội dung
Ghi chú nằm trong `content/knowledge.json`: ID, market, từ khóa, diễn giải, ví dụ, caveat, câu hỏi tiếp và nguồn. Viết bằng lời riêng, ghi đúng ngày rà soát, test có/không dấu và thuật ngữ dễ nhầm. Link nguồn không thay thế thẩm định nội dung.

## Mở rộng adapter
Provider trả Completion có text/usage, timeout và lỗi gọn; kiểm thử HTTP bằng MockTransport, không fallback demo âm thầm. Giá dùng MarketSnapshot có ngày, đơn vị, nguồn, price_basis và cờ stale. Gateway và format: [MARKET_DATA](MARKET_DATA.md).

Tin tức là luồng riêng; sách có quyền/nguồn/trang. Không dùng tiêu đề báo hoặc điểm heuristic như nguyên tắc đã học từ sách.

## UI
CSS/nhận diện ở assets, nội dung ở app.py, phép tính biểu đồ ở dashboard.py. Dùng màu/chiều rộng trong [UI_UX](UI_UX.md). Giữ root chat_input để ghim phía dưới, callback để cập nhật số liệu trước render. Khi nâng Streamlit phải kiểm tra selector và responsive thực tế.

## Nợ kỹ thuật
BM25/parser có phạm vi hạn chế; chưa kiểm tra từng trích dẫn model, đặt chỗ quota trước request hoặc điều chỉnh journal. Chưa có auth/billing/telemetry/retention/cloud scheduler, nguồn thương mại hoặc backtest. CI có cấu hình Windows/Ubuntu, nhưng chỉ gọi là CI đạt khi có kết quả chạy remote.

[Backlog](../notes/BACKLOG.md) · [Quyết định](../notes/DECISIONS.md) · [Kiểm thử](TESTING.md).
