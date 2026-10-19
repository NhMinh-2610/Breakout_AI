# Nhật ký Breakout AI

## 19/10/2026 — Bản 0.8, bố cục bảng điện và phân tích theo mã

Ảnh người dùng cung cấp cho thấy nội dung bị ép và chữ sát mép. Đối chiếu DOM/width calculation của Streamlit phát hiện gap ngang CSS 24px khác gap 16px mà cột gốc dùng tính độ rộng; selector panel :has quá rộng cũng áp border/padding lên khối tổ tiên. Sửa về gap gốc cho cột thường, dùng lưới có key để quản lý width/gap và giới hạn selector wrapper/con trực tiếp. Nội dung chính/panel có khoảng đệm riêng.

Không gian thị trường gồm bốn chỉ số thật dạng gọn, hàng điều khiển sáu cột và dải thống kê nhỏ thay cho metric lớn; bỏ tiêu đề lớn bị lặp. Nhịp tải/chế độ bảng/danh sách mã chuyển vào popover Tùy chọn bảng. Bảng giá rộng phía trên và khu vực theo mã phía dưới. Biểu đồ nến/khối lượng có SMA20, hỗ trợ/kháng cự; cung cầu ba mức tách giờ nguồn. Bên phải có phân tích, chat theo mã và quét tối đa 6 mã. Scanner chỉ bắt đầu sau thao tác người dùng rồi cập nhật theo dữ liệu khi tự tải bật.

Nguồn OHLCV công khai DNSE đã kiểm tra trực tiếp cho VIC và bốn chỉ số. Giá cổ phiếu nến nhân 1.000 VND, volume giữ số cổ phiếu; index giữ điểm. Snapshot giá 5/10/30 giây, nến cache 30 giây và index 60 giây. Chưa tích hợp luồng tick đẩy.

Bộ kỹ thuật chỉ dùng nến đã đóng, quote mới và dữ liệu đủ điều kiện; lỗi/cũ chuyển chờ, bán chỉ xét mã sở hữu. Không suy luận “giá thấp nghĩa là đáy”. Sách truy xuất để giải thích, chưa tự học thành chiến lược. Chat chụp bối cảnh lúc gửi, lưu lịch sử và không tự gọi model theo chu kỳ thị trường.

509 kiểm thử toàn bộ, smoke nguồn nến/chỉ số thật và HTTP đạt. [Kiểm thử](../docs/TESTING.md) ghi kết quả tích hợp/toàn bộ và giới hạn còn lại. Browser không khả dụng; sửa selector chưa phải xác minh screenshot/pixel/mobile.

## 19/10/2026 — Bảng điện Việt Nam

Bổ sung chế độ bảng điện theo bố cục nhóm mua/khớp/bán, dùng snapshot công khai DNSE tải theo chu kỳ 5/10/30 giây. Tối đa 30 mã do người dùng chọn, lọc sàn/tìm/sắp xếp, bảng đầy đủ/rút gọn, tạm dừng và xem chi tiết mã. Giữ biểu đồ ngày VN/Mỹ riêng; không thay điều kiện bản tin mua/bán.

Giá chuẩn hóa về VND và số cổ phiếu; giờ tải/giờ khớp/giờ độ sâu tách riêng. Trường thiếu giữ dấu gạch, độ sâu quá cũ bị ẩn. Snapshot chưa phải luồng đẩy tick; quyền phân phối thương mại cần xác nhận với bên dữ liệu trước pilot trả phí.

Trang thị trường rộng tối đa 1760px, tiêu đề và cột mã cố định khi cuộn. Giãn khối 24px, thẻ tóm tắt 16px, ô bảng 8×12px. Bộ sửa danh sách nằm trong popover; chọn chi tiết bên dưới bảng và giữ nguyên mã khi thứ hạng thay đổi. Bằng chứng test và giới hạn QA trình duyệt được theo dõi tại [Kiểm thử](../docs/TESTING.md); 366 kiểm thử của bản mới đạt, API thật sáu mã và HTTP smoke thành công; chưa có QA hình ảnh trình duyệt.
## 19/10/2026 — API tự tải và căn khoảng cách

Theo yêu cầu, giao diện tự lấy giá khi thiếu/cũ và kiểm tra mỗi 5 phút khi mở; thêm cập nhật theo nhóm, cooldown lỗi và bảng mã giữ dòng chưa có giá. Batch HTTP dùng chung pool ba kết nối, chuẩn hóa/loại trùng mã trước giới hạn. Không đổi logic gợi ý mua/bán.

Chuẩn hóa nhịp 8/16/24/32px, control44px, thẻ số liệu128px và nhãn36px. Responsive gắn key từng hàng để tránh co nhầm biểu đồ; chat giữ input cố định. API thật sáu mã VN/Mỹ thành công. 247 test đạt; chưa có QA ảnh vì Browser không khả dụng.


## 19/10/2026 — Bản 0.6, đổi tên và hoàn thiện nhận diện

Theo yêu cầu chủ dự án, dùng tên Breakout AI và thư mục Breakout_AI đã được đổi trước đó. Đã sao lưu nguồn/SQLite, đổi package thành breakout_ai, cập nhật import/CLI, prompt nhận diện, export và metadata. DB cũ tiếp tục được chọn để giữ lịch sử.

Thêm logo SVG/favicon, căn sidebar 256px, nội dung dữ liệu tối đa 1360px, trang đọc 1080px và chat/composer cùng 820px. Căn nhãn thẻ số liệu, dải giá theo màn hình và bộ lọc tin tức. Viết lại tài liệu sử dụng/kỹ thuật, thêm bản đồ tài liệu, thương hiệu và hướng dẫn chuyển đổi.

Task cũ trỏ root trước đổi tên được xuất XML. Task BreakoutAI mới được kiểm tra marker/action/root/giờ trước khi gỡ task cũ. Chạy thử thành công với last_result=0 và giữ 07:30 Việt Nam.

238 tests passed, 1 cảnh báo dependency. Kiểm tra HTTP, CSS, link và số bản ghi trước/sau. Test temp/cache cũ gặp hạn chế quyền nên dùng thư mục thử mới, không sửa ACL hoặc xóa dữ liệu cũ. Browser không khả dụng; chưa có QA hình ảnh/mobile. Chi tiết và artifact ở TESTING.md.

## Các mốc trước đổi tên

- **0.5 — 18/10/2026:** nền tối kiểu bảng điện, chat tập trung, điều hướng giao dịch riêng, sửa đổi tên chat và câu hỏi mẫu gửi lặp. 235 test đạt.
- **0.4 — 18/10/2026:** dashboard sáu trang, journal mua/bán, biểu đồ, RSS, lịch sử chat/bản tin. Schema v4, 233 test đạt.
- **0.3 — 18/10/2026:** bản tin theo sách, danh mục sở hữu, nguyên tắc có nguồn và lịch 07:30.
- **0.2:** giá ngày KBS/Yahoo, RAG sách và nghiên cứu có điều kiện.
- **Khởi đầu:** từ trợ lý học tập chuyển sang ngách chứng khoán VN/US theo lựa chọn của chủ dự án.

Chưa có doanh thu, người dùng pilot hoặc hiệu quả chiến lược được xác minh. [Backlog](BACKLOG.md) · [Kiểm thử](../docs/TESTING.md).
