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
| market_view | Chính sách cache/cooldown cho dữ liệu ngày, tách khỏi gọi nguồn |
| realtime, priceboard | Snapshot DNSE, cache/thời gian nguồn và dựng bảng điện HTML đã escape |
| news, dashboard | RSS và biểu diễn dữ liệu |
| schedule, verify_data | Lịch Windows và kiểm tra nguồn |

## Luồng

**Bản tin:** sách chọn → nguyên tắc đã đối chiếu → danh mục/candidate → giá đủ điều kiện → kiểm tra → báo cáo ngày. Không gọi LLM để tính tín hiệu.

**Chat:** câu hỏi/lịch sử giới hạn → truy xuất → lấy giá nếu cần → demo/provider → lưu lượt và metadata. Nguồn đầu vào không tự xác minh mọi câu model sinh.

**Giao dịch:** kiểm tra → `BEGIN IMMEDIATE` → cập nhật số dư/giá vốn và thêm journal → commit; lỗi rollback cả hai. Idempotency gắn workspace và khóa gửi.

**Tin tức:** RSS allowlist → kiểm tra XML/URL/ngày → cache → tiêu đề có nguồn. Không đi vào điều kiện mua/bán.

UI giá ngày dùng fragment 300 giây. market_view giữ thời điểm thử theo workspace/provider/danh sách, yêu cầu mã thiếu/cũ và giới hạn batch theo cấu hình. Lần tải lỗi không tự lặp trên mỗi rerun; stale từ service được giữ nguyên.

## Bảng điện Việt Nam

Trang Thị trường có hai chế độ: bảng điện mặc định và biểu đồ ngày VN/US. Bảng điện dùng RealtimeService riêng, không thay nguồn ngày cho bản tin hoặc tín hiệu.

Luồng tải: danh sách tối đa 30 mã → cache theo workspace/danh sách → một POST GraphQL tới snapshot công khai DNSE → kiểm tra trường/đơn vị/thời gian → BoardSnapshot → lọc/sắp xếp trong UI → priceboard dựng HTML. Giá nội bộ là VND đầy đủ, khối lượng là số cổ phiếu; việc chia đơn vị chỉ nằm ở lớp hiển thị.

Fragment thức mỗi 5 giây; trạng thái lần thử theo workspace/danh sách quyết định gửi request theo nhịp 5/10/30 giây, tính từ lúc bắt đầu yêu cầu. Claim SQLite ngăn hai phiên gửi trùng; lỗi có backoff được lưu qua rerun. Tạm dừng chỉ đọc cache. Cập nhật thủ công có thể thử ngay với lỗi thông thường, vẫn tôn trọng cooldown 403/429 và yêu cầu đang chạy. Khi tắt nguồn thị trường, UI không gọi HTTP.

Cache SQLite có scope workspace. Giờ nhận snapshot, giờ khớp và giờ độ sâu được giữ riêng; dữ liệu lỗi/cũ không được nâng thành mới. Độ sâu quá cũ được ẩn. Cơ chế này là polling snapshot; luồng đẩy tick chính thức cần adapter và thông tin xác thực DNSE riêng. [Hợp đồng và giới hạn nguồn](REALTIME.md).

## Lưu trữ

Schema **v4** giữ nguyên trong bản 0.7. Dịch vụ tạo/migrate bảng theo nhu cầu; dữ liệu có scope workspace. Hội thoại mở lại bằng ID, không tạo bản sao.

Cài mới dùng `data/breakout_ai.sqlite3`; nâng cấp tiếp tục DB đời trước. `DATABASE_PATH` rõ luôn ưu tiên. Không di chuyển SQLite đang hoạt động để đổi tên sản phẩm.

## UI

Nhãn hiển thị mới, khóa điều hướng nội bộ ổn định. Lưu vị thế/giao dịch/đổi tên chat dùng callback trước render. Chat input cấp trang; danh mục chỉ dựng mục được chọn. HTML động phải escape; nội dung người dùng/model dùng widget mặc định.

## Vận hành

Task chạy `pythonw -m breakout_ai.daily --refresh` lúc 07:30, Limited/Interactive. ROOT tính từ file package. App local chưa có auth, cloud scheduler, billing hoặc broker; WORKSPACE_ID không thay thế xác thực SaaS.

[Snapshot bảng điện](REALTIME.md) · [Phát triển](DEVELOPMENT.md) · [Vận hành](OPERATIONS.md) · [Chuyển đổi](MIGRATION.md).
