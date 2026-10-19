# Changelog — Breakout AI

## 0.8.0 — 2026-10-19

- Sửa cột bị ép/chồng do gap ngang khác cách Streamlit tính độ rộng; giới hạn selector panel để khối tổ tiên không nhận padding/border. Cột thường giữ gap 16px, lưới chính và panel có khoảng đệm riêng.
- Thêm bốn thẻ VN-Index/VN30/HNX-Index/UPCoM-Index từ dữ liệu điểm thật và đường diễn biến nến 5 phút.
- Đặt bảng giá phía trên, biểu đồ/phân tích phía dưới: nến 1/5/15 phút, SMA20, hỗ trợ/kháng cự, khối lượng và cung cầu ba mức.
- Thêm Phân tích, Chat theo mã và Cơ hội hôm nay; quét tối đa 6 mã sau thao tác bắt đầu, tải tối đa 3 mã đồng thời.
- Tín hiệu dùng nến đã đóng và quote đủ mới; lỗi/cũ/thiếu chuyển sang chờ. Rà soát bán chỉ xét mã sở hữu; số điều kiện đạt không phải xác suất lợi nhuận.
- Chat chụp bối cảnh khi gửi, truy xuất sách để giải thích và lưu cùng lịch sử hiện có. Tự cập nhật thị trường không gọi LLM.
- Tách nhịp snapshot 5/10/30 giây, nến 30 giây và chỉ số 60 giây; vẫn là polling, chưa có tick stream hoặc đặt lệnh tự động.
- Bổ sung tài liệu nguồn nến/chỉ số, quy tắc phân tích, kiến trúc và nghiệm thu. 509 kiểm thử đạt; smoke nguồn nến/chỉ số thật và HTTP thành công. Chi tiết tại docs/TESTING.md.
- Chưa xác minh screenshot/mobile vì Browser không khả dụng; không xem kiểm thử widget/CSS parser là bằng chứng bố cục thực tế.

## 0.7.0 — 2026-10-19

- Thêm bảng điện Việt Nam dùng snapshot công khai DNSE, nhịp 5/10/30 giây, tạm dừng và cập nhật thủ công.
- Nhóm ba mức mua/bán, khớp lệnh, trần/sàn/tham chiếu, tổng giao dịch, OHLC/bình quân và khối ngoại; hiển thị giờ nguồn và trạng thái cũ.
- Theo dõi tối đa 30 mã, lọc sàn/tìm/sắp xếp, chọn mã chi tiết và bảng đầy đủ/rút gọn; giữ biểu đồ ngày VN/Mỹ trong chế độ riêng.
- Mở rộng trang thị trường 1760px, cố định tiêu đề/cột mã khi cuộn, giãn khối 24px/thẻ 16px và ô bảng 8×12px.
- Tách nguồn snapshot khỏi bản tin ngày; thêm tài liệu cơ chế polling, đơn vị và giới hạn nguồn.
- 366 kiểm thử đạt; API thật 6 mã và HTTP smoke đạt. Chưa có QA hình ảnh trình duyệt.
- Tự tải giá khi thiếu/cũ, kiểm tra mỗi 5 phút và nút cập nhật theo nhóm trên Tổng quan.
- Bảng theo dõi giữ dòng thiếu dữ liệu, hiện riêng giá cũ và nguồn/tiền tệ/phiên.
- Batch dùng chung HTTP pool tối đa ba kết nối; loại trùng sau chuẩn hóa mã.
- Cooldown sau lỗi tránh gọi API lặp mỗi lần tương tác; cập nhật thủ công thử ngay.
- Chuẩn hóa khoảng cách 8/16/24/32px, thẻ số liệu, control 44px và responsive theo container.


## 0.6.0 — 2026-10-19

- Nhận diện Breakout AI trên tiêu đề, sidebar, chat, logo/favicon, tệp xuất và prompt.
- Package breakout_ai, metadata breakout-ai và CLI mới; giữ lựa chọn DB cũ, schema v4 và dữ liệu hiện có.
- Giới hạn chiều rộng trang, căn sidebar/thẻ/dải giá; khung chat và ô nhập dùng cùng chiều rộng, news toolbar cùng hàng.
- Viết lại bộ tài liệu sử dụng/phát triển/vận hành; thêm index, BRAND và MIGRATION; cập nhật notes.
- Cập nhật lịch 07:30 sang root và module mới, sao lưu XML và chạy thử thành công.
- 238 test local đạt, HTTP smoke 200; kiểm tra CSS/link và số bản ghi trước/sau. Chưa có QA trực quan vì Browser không khả dụng.

## 0.5.0 — 2026-10-18

- Đổi giao diện sang nền đen/xám, điểm nhấn vàng, giá tăng xanh và giảm đỏ; biểu đồ có màu/trục phù hợp nền tối.
- Đưa gợi ý hôm nay lên trước biểu đồ phụ, thêm dải giá theo phiên và lối tắt mở đúng mục ghi/xem giao dịch.
- Danh mục hiện tại hiển thị bảng cổ phiếu trước biểu mẫu; ba mục được điều hướng riêng để giảm nội dung thừa.
- Chat một cột rộng tối đa 860px, lịch sử/tùy chọn trong sidebar, ô nhập cố định bằng cơ chế gốc Streamlit. Đổi tên dùng callback để tránh trạng thái widget cũ.
- Tin tức thành danh sách tiêu đề có thể bấm, giữ nguồn/thời gian/trạng thái cũ. CSS có focus bàn phím và breakpoint màn hình nhỏ.
- Không đổi schema, dữ liệu tài chính hoặc lịch 07:30. Cần khởi động lại Streamlit để nạp theme mới.

## 0.4.0 — 2026-10-18

- Giao diện dashboard với sidebar sáu mục, thẻ thống kê, biểu đồ nhanh và nhật ký gần đây; CSS riêng trong assets.
- Biểu đồ giá ngày/MA20, tooltip và biến động; phân bổ vốn tách VND/USD; không tạo dữ liệu hoặc hiệu suất tài khoản giả.
- Nhật ký mua/bán có phí, giá vốn bình quân, lãi/lỗ đã chốt và xuất CSV; lưu nguyên tử cùng vị thế, chống trùng và bán vượt số lượng, xử lý cổ phiếu lẻ.
- Lịch sử chat tìm/mở lại/đổi tên/xuất JSON; bản tin ngày có archive và sơ đồ giải thích.
- RSS tiêu đề VnExpress/CNBC có nguồn/thời gian, bộ lọc, cache 15 phút và tự kiểm tra lại khi trang đang mở; tin tức độc lập với tín hiệu từ sách.
- Schema v4 thêm journal/news cache, giữ dữ liệu cũ; lịch buổi sáng 07:30 tiếp tục dùng CLI cũ.
- Tài liệu TRADES/NEWS và kiểm thử domain, cache, workspace, biểu đồ và UI mới. Chưa có broker, hiệu suất toàn tài khoản hoặc quyền thương mại đã xác nhận cho nguồn công khai.

## 0.3.0 — 2026-10-18

- Làm lại UI thành Hôm nay, Cổ phiếu của tôi, Sách và Hỏi thêm; thẻ hành động dễ đọc và có giải thích mở rộng.
- Danh mục sở hữu có số lượng/giá vốn riêng với watchlist; bản tin chỉ gợi ý bán mã đang sở hữu.
- Đọc một số nguyên tắc đo được từ sách đã chọn, giữ câu/trang, yêu cầu đối chiếu trước khi dùng; không gán score kỹ thuật cũ cho sách.
- Bản tin theo ngày: mua/giữ/bán/chờ, chặn dữ liệu thiếu/cũ và loại phiên chưa đóng theo mốc bảo thủ; thay đầu vào tạo lại báo cáo.
- CLI và Windows task cục bộ 07:30 giờ Việt Nam, cài/kiểm tra/gỡ lịch; không gửi thông báo hoặc đặt lệnh.
- Schema v3 giữ dữ liệu cũ, thêm holdings/preferences/reports; xóa sách xóa báo cáo chứa trích đoạn.
- Hướng dẫn dùng hằng ngày, tài liệu kiến trúc/sản phẩm và kiểm thử mới. Chưa có corpus sách chuyên ngành hoặc đánh giá hiệu quả chiến lược.

## 0.2.0

- Tra giá ngày thật qua KBS cho VN và Yahoo cho US, provenance và cache tách workspace.
- So sánh ứng viên bằng 5 tiêu chí minh bạch, ngưỡng ưu tiên, xử lý dữ liệu thiếu/cũ; chưa phải chiến lược đã backtest.
- Nhập PDF/TXT/MD, truy xuất sách theo trang/đoạn và đưa bằng chứng vào chat.
- Kết hợp dữ liệu và sách trong prompt LLM; chế độ không LLM vẫn dùng được dữ liệu và trích đoạn.
- Thêm gateway contract, CLI xác minh nguồn thật và schema SQLite v2 giữ dữ liệu v1.
- Tài liệu dữ liệu thị trường, sách và kiểm thử mở rộng.

## 0.1.0 — 2026-10-17

- MVP trợ lý kiến thức chứng khoán cho thị trường Việt Nam và Mỹ.
- Chat demo và adapter OpenAI Responses/Ollama, nguồn tham khảo, bộ lọc thị trường.
- Lịch sử SQLite, sổ theo dõi, công thức tài chính, đọc/xuất CSV và JSON.
- Cấu hình môi trường, script Windows, kiểm thử và workflow CI.
- Tài liệu sản phẩm, kỹ thuật, nguồn dữ liệu, vận hành và kế hoạch bán thử.

Chưa có feed giá, auth, thanh toán hoặc triển khai SaaS.
