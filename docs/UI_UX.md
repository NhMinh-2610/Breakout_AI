# Giao diện Breakout AI

## Bố cục và khoảng cách

Menu trái cố định; các form, bảng, tiêu đề và biểu đồ dùng chung mép căn. Mỗi loại trang có giới hạn chiều rộng phù hợp nội dung.

| Thành phần | Quy ước |
| --- | --- |
| Sidebar | 256px, logo 40px, tên và mô tả hai dòng |
| Trang dữ liệu | Tối đa 1360px, lề 24px |
| Thị trường / bảng điện | Tối đa 1760px |
| Tin tức / sách | Tối đa 1080px |
| Hội thoại / ô nhập | Cùng giới hạn 820px và lề hai bên |
| Thẻ số liệu thông thường | Cao tối thiểu 128px, vùng nhãn 36px |
| Tóm tắt bảng điện | Thẻ tối thiểu 88px, khoảng cách 16px |
| Khối nội dung / control | Khoảng cách 24px, ô nhập/nút cao tối thiểu 44px |

Khoảng cách dùng các mốc 8/16/24/32px. Padding khối là 24px trên desktop, 16px trên mobile. Hàng số liệu có key riêng để thay đổi responsive không làm co nhầm cột biểu đồ. Tổng quan ưu tiên gợi ý trước biểu đồ phụ; biểu đồ/thao tác nhanh chia tỷ lệ 1,7:1.

## Bảng điện Việt Nam

Trang Thị trường mặc định mở **Bảng điện Việt Nam**. **Biểu đồ VN / US** giữ phần giá ngày và MA20. Hai chế độ có nguồn và nhịp cập nhật riêng.

Bảng điện tham khảo cách nhóm thông tin của [DNSE](https://banggia.dnse.com.vn/v2): mã, trần/sàn/tham chiếu, bên mua, khớp lệnh, bên bán, tổng giao dịch, thống kê trong ngày và khối ngoại. Ba mức mua hiển thị từ mức 3 đến 1, bên bán từ 1 đến 3 để mức tốt nhất nằm cạnh khớp lệnh. Đơn vị luôn ghi cạnh bảng: giá ×1.000 VND, khối lượng cổ phiếu, giá trị triệu VND.

| Vùng | Hành vi |
| --- | --- |
| Bộ điều khiển | Lọc sàn trong danh sách đang theo dõi, tìm mã, sắp xếp, chọn nhịp 5/10/30 giây |
| Danh sách mã | Mở nút Danh sách mã để chỉnh tối đa 30 mã; danh sách ban đầu không đại diện toàn sàn hoặc rổ chỉ số |
| Tự cập nhật | Có tạm dừng và cập nhật thủ công; trạng thái ghi rõ snapshot và nhịp tải |
| Bảng số liệu | Chế độ đầy đủ/rút gọn; tiêu đề hai tầng và cột mã cố định khi cuộn |
| Chi tiết mã | Chọn mã bên dưới bảng để xem thông tin giá, độ sâu ba mức và thời gian nguồn; giữ mã đang xem khi thứ hạng đổi |
| Trạng thái | Giờ tải tách giờ nguồn; dữ liệu cũ có nhãn, độ sâu quá cũ được ẩn |

Bảng có vùng cuộn riêng, rộng tối thiểu 1680px để các cột số không bị ép. Ô bảng có padding dọc 8px, ngang 12px; nhóm cột có đường ngăn rõ. Tiêu đề hai tầng cao 40px/36px, cột mã tối thiểu 104px. Vùng cuộn có focus bàn phím và giới hạn chiều cao để phần chi tiết vẫn dễ tiếp cận.

Bộ tóm tắt phản ánh các mã đang hiển thị, không được gọi là độ rộng toàn thị trường. Khi nguồn thiếu/lỗi, giữ trạng thái thiếu/cũ thay vì tạo số liệu. Quy tắc dữ liệu: [Snapshot và thời gian nguồn](REALTIME.md).

## Màu và khả năng đọc

| Vai trò | Màu |
| --- | --- |
| Nền / khối | #101216 / #181b21 |
| Chữ chính / phụ | #edf0f4 / #a1a9b6 |
| Nhận diện / thao tác | #f0bc51 |
| Tăng / giảm | #35d399 / #ff727f |
| Tham chiếu / trần / sàn trên bảng điện | #f0bc51 / #d984f9 / #45d5e7 |
| Đường giá / MA20 | #79b8ff / #f0bc51 |
| Nền chat / tin người dùng | #212121 / #303030 |

Dùng Segoe UI/Arial có sẵn và số tabular. Chú giải, dấu phần trăm và nhãn cột bổ sung ý nghĩa cho màu. Bảng điện so sánh với tham chiếu do nguồn trả về; màu vàng trên dải giá ngày ở Tổng quan chỉ biểu thị biến động bằng 0.

## Chat và thao tác

Lịch sử có tìm kiếm/vùng cuộn riêng ở sidebar. Hội thoại một cột, câu hỏi bên phải, câu trả lời có thể mở nguồn. Ô nhập dùng st.chat_input ở cấp trang để ghim dưới màn hình. Câu hỏi mẫu xử lý ngay lượt nhấn, tránh gửi lại khi chuyển trang.

Tùy chọn chat và thiết lập ít dùng nằm trong khối mở rộng. Danh mục chỉ dựng mục đang chọn. Nút giữ nhãn, focus bàn phím và hover rõ ràng.

## Màn hình nhỏ

Dưới 1100px, biểu đồ/thao tác nhanh và chi tiết bảng điện xếp thành từng hàng; tóm tắt bốn thẻ thành hai cột. Dưới 640px, form một cột, số liệu hai cột; bảng/sơ đồ cuộn trong khối riêng. Giữ nút mở sidebar gốc và tôn trọng prefers-reduced-motion.

## Xác minh

AppTest kiểm tra trạng thái/thao tác; parser kiểm tra CSS. Chúng không xác minh kích thước thực tế. Cần xem tại 1366×768, 1920×1080 và rộng 390px: không cắt chữ, không tràn trang, ô nhập không che tin cuối, focus rõ và bảng cuộn được.

Browser tích hợp không khả dụng trong phiên cập nhật; chưa có xác minh screenshot/mobile hoặc chứng nhận WCAG toàn ứng dụng.
