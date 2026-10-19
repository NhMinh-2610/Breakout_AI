# Kiến trúc Breakout AI
`app.py` dựng sáu trang Streamlit. Package `breakout_ai` chứa nghiệp vụ; `assets` chứa theme/logo; `content/knowledge.json` là ghi chú nền. SQLite giữ dữ liệu theo workspace.

| Module | Trách nhiệm |
| --- | --- |
| config, brand | Cấu hình hợp lệ và nhận diện |
| storage | Hội thoại, quota, schema và workspace |
| books, knowledge | Trích chữ, BM25, kiến thức và nguồn |
| book_rules, daily | Nguyên tắc sách, kiểm tra và bản tin |
| portfolio | Vị thế, journal, phí, giá vốn, export |
| market, screening, research | Giá, cache, phép tính, bối cảnh nghiên cứu |
| providers, tutor | API model và điều phối hỏi đáp |
| news, dashboard | RSS và biểu diễn dữ liệu |
| schedule, verify_data | Lịch Windows và kiểm tra nguồn |

## Luồng
**Bản tin:** sách chọn → nguyên tắc đã đối chiếu → danh mục/candidate → giá đủ điều kiện → kiểm tra → báo cáo ngày. Không gọi LLM để tính tín hiệu.

**Chat:** câu hỏi/lịch sử giới hạn → truy xuất → lấy giá nếu cần → demo/provider → lưu lượt và metadata. Nguồn đầu vào không tự xác minh mọi câu model sinh.

**Giao dịch:** kiểm tra → `BEGIN IMMEDIATE` → cập nhật số dư/giá vốn và thêm journal → commit; lỗi rollback cả hai. Idempotency gắn workspace và khóa gửi.

**Tin tức:** RSS allowlist → kiểm tra XML/URL/ngày → cache → tiêu đề có nguồn. Không đi vào điều kiện mua/bán.

## Lưu trữ
Schema **v4** giữ nguyên trong bản 0.6. Dịch vụ tạo/migrate bảng theo nhu cầu; dữ liệu có scope workspace. Hội thoại mở lại bằng ID, không tạo bản sao.

Cài mới dùng `data/breakout_ai.sqlite3`; nâng cấp tiếp tục DB đời trước. `DATABASE_PATH` rõ luôn ưu tiên. Không di chuyển SQLite đang hoạt động để đổi tên sản phẩm.

## UI
Nhãn hiển thị mới, khóa điều hướng nội bộ ổn định. Lưu vị thế/giao dịch/đổi tên chat dùng callback trước render. Chat input cấp trang; danh mục chỉ dựng mục được chọn. HTML động phải escape; nội dung người dùng/model dùng widget mặc định.

## Vận hành
Task chạy `pythonw -m breakout_ai.daily --refresh` lúc 07:30, Limited/Interactive. ROOT tính từ file package. App local chưa có auth, cloud scheduler, billing hoặc broker; WORKSPACE_ID không thay thế xác thực SaaS.

[Phát triển](DEVELOPMENT.md) · [Vận hành](OPERATIONS.md) · [Chuyển đổi](MIGRATION.md).
