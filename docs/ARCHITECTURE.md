# Kiến trúc Breakout AI

`app.py` dựng sáu trang Streamlit. Package `breakout_ai` chứa nghiệp vụ; `assets` chứa theme/logo; `content/knowledge.json` là ghi chú nền. SQLite giữ dữ liệu theo workspace.

| Module | Trách nhiệm |
| --- | --- |
| config, brand | Cấu hình hợp lệ và nhận diện |
| storage | Hội thoại, quota, schema và workspace |
| books, knowledge | Trích chữ, BM25, kiến thức và nguồn |
| book_rules, daily | Nguyên tắc sách, kiểm tra và bản tin |
| portfolio | Vị thế, journal, phí, giá vốn, export |
| market, screening, research | Giá ngày, cache, phép tính và nghiên cứu |
| market_view | Cache/cooldown cho dữ liệu ngày, tách khỏi gọi nguồn |
| realtime, priceboard | Snapshot DNSE, thời gian nguồn và dựng HTML bảng điện đã escape |
| intraday | Nến DNSE cổ phiếu/chỉ số, đơn vị, cache và nhịp tải |
| technical | Chỉ báo, kịch bản theo điều kiện, độ mới và kiểm tra sở hữu |
| market_visuals | Biểu đồ nến/khối lượng/độ sâu và thẻ giải thích |
| workbench | Điều phối bảng chỉ số, biểu đồ/phân tích/chat và quét tối đa 6 mã |
| copilot | Diễn giải bối cảnh mã đã chụp, truy xuất sách, demo/model tùy chọn |
| providers, tutor | API model, điều phối hỏi đáp và lưu lượt chat |
| news, dashboard | RSS và biểu diễn dữ liệu ngày |
| schedule, verify_data | Lịch Windows và kiểm tra nguồn |

## Các luồng nghiệp vụ

**Bản tin theo sách:** sách chọn → nguyên tắc đã đối chiếu → danh mục/candidate → giá ngày đủ điều kiện → kiểm tra → báo cáo ngày. LLM không tính tín hiệu bản tin.

**Phân tích trong phiên:** quote + nến đã đóng → chuẩn hóa/kiểm tra → technical → SignalReport → panel, scanner và bối cảnh chat. Nến đang hình thành có thể hiển thị trên biểu đồ nhưng không xác nhận tín hiệu.

**Chat theo mã:** câu hỏi → chụp report/quote/giờ dữ liệu/mã sở hữu → truy xuất tối đa hai đoạn sách → giải thích demo hoặc gọi model → lưu lượt qua cơ chế hội thoại hiện có. Không gọi model trong chu kỳ tải giá/nến. Kết luận tính bằng Python giữ hiển thị ngay cả khi có phần diễn giải LLM.

**Chat chính:** câu hỏi/lịch sử giới hạn → truy xuất → lấy giá ngày nếu cần → demo/provider → lưu lượt và metadata. Nguồn đầu vào không tự xác minh mọi câu model sinh.

**Giao dịch:** kiểm tra → `BEGIN IMMEDIATE` → cập nhật số dư/giá vốn và journal → commit; lỗi rollback cả hai. Idempotency gắn workspace và khóa gửi.

**Tin tức:** RSS allowlist → kiểm tra XML/URL/ngày → cache → tiêu đề có nguồn. Chưa tham gia điều kiện mua/bán.

## Bảng điện và không gian phân tích

Bảng điện mặc định giữ cấu trúc chỉ số gọn → một hàng điều khiển → dải đếm/bảng giá → chọn mã/khung nến → biểu đồ và panel giải thích. Nhịp tải, chế độ cột và danh sách mã nằm trong popover Tùy chọn bảng; trang không lặp tiêu đề lớn. Biểu đồ ngày VN/US tiếp tục là chế độ riêng.

| Luồng | Nguồn / phạm vi | Nhịp và giới hạn |
| --- | --- | --- |
| Snapshot cổ phiếu | DNSE public GraphQL, tối đa 30 mã | 5/10/30 giây; một POST cho cả danh sách |
| Nến cổ phiếu | DNSE public OHLCV, một mã/khung | Cache 30 giây; khung 1/5/15 phút, cửa sổ 7 ngày |
| Nến chỉ số | DNSE OHLCV /index, bốn chỉ số được xác minh | Cache 60 giây; khung 5 phút, giá là điểm |
| Quét tín hiệu | Tối đa 6 mã được chọn từ bảng | Sau khi bấm quét; tối đa 3 lượt tải đồng thời |
| Giá ngày | KBS VN / Yahoo US | Cache và fragment 300 giây |

Fragment bảng điện thức mỗi 5 giây. Dịch vụ quyết định yêu cầu HTTP theo TTL/trạng thái lần thử; thời gian thức fragment không đồng nghĩa mọi nguồn bị tải lại mỗi 5 giây. Tạm dừng hoặc tắt nguồn thị trường chỉ đọc cache. Quét đã khởi động tiếp tục dùng dữ liệu mới khi tự cập nhật bật; không quét toàn sàn.

Giờ nhận HTTP, giờ khớp, giờ độ sâu và thời gian nến giữ riêng. Giá cổ phiếu nội bộ dùng VND đầy đủ, khối lượng cổ phiếu dùng số cổ phiếu. Hai nguồn DNSE có hệ số khối lượng khác nhau; index giữ điểm, không dùng như cổ phiếu.

Cache/trạng thái yêu cầu có scope workspace. Claim SQLite tránh tải trùng cùng khóa giữa nhiều instance; HTTP không giữ transaction ghi trong toàn thời gian chờ mạng. HTTP 403/429 có thời gian nghỉ mà cập nhật thủ công cũng phải tôn trọng. Lỗi không tạo giá thay thế hoặc nâng mốc tải dữ liệu cũ thành hiện tại.

Đây là các snapshot tải định kỳ; chưa có luồng đẩy tick. [Snapshot](REALTIME.md) · [Nến/chỉ số](INTRADAY.md).

## Quy tắc phân tích và sách

technical tính RSI14 Wilder, SMA20, vùng hỗ trợ/kháng cự từ cửa sổ trước nến xác nhận, khối lượng tương đối và cung cầu ba mức khi đủ mới. Dư mua/bán là lệnh chờ, không phải khối lượng đã khớp.

Tín hiệu cần tối thiểu 30 nến đóng, quote đúng mã/đủ mới và nến gần nhất đủ điều kiện. Lớp workbench chặn thêm khi snapshot nến cũ hoặc tải lỗi. Rà soát bán chỉ áp dụng mã đang sở hữu; thiếu điều kiện trả wait/hold thay vì ép có ứng viên mua.

Các quy tắc này được viết rõ trong [Phân tích kỹ thuật](TECHNICAL_ANALYSIS.md); chưa phải mô hình học từ lợi nhuận tương lai hoặc chiến lược được tạo từ toàn bộ sách. BM25 truy xuất sách để giải thích kiến thức, không sửa giá/chỉ báo và không vượt qua blocker dữ liệu.

## Lưu trữ và UI

Schema chính **v4** giữ nguyên trong bản 0.8; adapter tạo bảng cache/trạng thái riêng khi cần. Dữ liệu có scope workspace. Hội thoại lưu bằng cơ chế hiện có và mở lại bằng ID.

Cài mới dùng `data/breakout_ai.sqlite3`; nâng cấp tiếp tục DB đời trước. `DATABASE_PATH` rõ luôn ưu tiên. Không di chuyển SQLite đang hoạt động để đổi tên sản phẩm.

Nhãn hiển thị có thể đổi trong khi khóa điều hướng giữ ổn định. Vị thế/giao dịch/đổi tên chat dùng callback trước render. Chat chính dùng input cấp trang; chat thị trường dùng form nằm trong panel. HTML động được escape; nội dung người dùng/model qua widget Markdown mặc định.

CSS giữ gap ngang gốc 16px cho cột thường và chỉ tự quản lý gap/width tại lưới có key. Panel selector giới hạn đúng wrapper/con trực tiếp, tránh nhận toàn bộ khối tổ tiên. [Quy ước giao diện và giới hạn QA](UI_UX.md).

## Vận hành

Task chạy `pythonw -m breakout_ai.daily --refresh` lúc 07:30, Limited/Interactive. ROOT tính từ file package. App local chưa có auth, cloud scheduler, billing hoặc broker; WORKSPACE_ID không thay thế xác thực SaaS.

[Phát triển](DEVELOPMENT.md) · [Vận hành](OPERATIONS.md) · [Chuyển đổi](MIGRATION.md).
