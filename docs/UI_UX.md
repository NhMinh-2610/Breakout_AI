# Giao diện Breakout AI
## Bố cục cân đối
Menu trái cố định, nội dung giới hạn chiều rộng để không kéo giãn trên màn hình lớn. Các form, bảng, tiêu đề và biểu đồ dùng chung mép căn.

| Thành phần | Quy ước |
| --- | --- |
| Sidebar | 256px, logo 40px, tên và mô tả hai dòng |
| Trang dữ liệu | Tối đa 1360px, lề 24px |
| Tin tức / sách | Tối đa 1080px |
| Hội thoại / ô nhập | Cùng giới hạn 820px và lề hai bên |
| Thẻ số liệu | Cao tối thiểu 128px, vùng nhãn 36px |
| Dải giá | 6 cột màn rộng, 3 cột màn vừa, cuộn ngang mobile |

Tổng quan ưu tiên gợi ý trước biểu đồ phụ. Biểu đồ/thao tác nhanh chia tỷ lệ 1,7:1. Bộ lọc và nút cập nhật tin cùng hàng ở desktop. Ô nhập/nút cao tối thiểu 44px; khoảng cách dùng các mốc 8/16/24/32px. Padding khối 24px desktop, 16px mobile.

## Màu
| Vai trò | Màu |
| --- | --- |
| Nền / khối | `#101216` / `#181b21` |
| Chữ chính / phụ | `#edf0f4` / `#a1a9b6` |
| Nhận diện / thao tác | `#f0bc51` |
| Tăng / giảm | `#35d399` / `#ff727f` |
| Đường giá / MA20 | `#79b8ff` / `#f0bc51` |
| Nền chat / tin người dùng | `#212121` / `#303030` |

Dùng Segoe UI/Arial có sẵn, số tabular. Màu đi kèm nhãn hoặc dấu phần trăm. Vàng trên dải giá nghĩa biến động bằng 0, không phải trường giá tham chiếu do sàn cung cấp.

## Chat và thao tác
Lịch sử có tìm kiếm/vùng cuộn riêng ở sidebar. Hội thoại một cột, câu hỏi bên phải, câu trả lời có thể mở nguồn. Ô nhập là `st.chat_input` ở cấp trang để ghim dưới màn hình. Câu hỏi mẫu xử lý ngay lượt nhấn, tránh gửi lại khi chuyển trang.

Tùy chọn chat và thiết lập ít dùng nằm trong khối mở rộng. Danh mục chỉ dựng mục đang chọn, giảm số form cạnh tranh sự chú ý. Nút giữ nhãn, focus bàn phím và hover.

## Giá tự cập nhật
Bảng Tổng quan tải khi chưa có cache hoặc cache hết hạn, kiểm tra lại sau 5 phút khi đang mở. Nút cập nhật theo nhóm làm mới cả giá và biểu đồ. Có trạng thái thành công, thiếu giá và giá cũ; lỗi không được trình bày thành giá mới.

Các hàng số liệu có container key riêng, tránh selector responsive tác động nhầm cả cột biểu đồ. Dưới 1100px, biểu đồ và thao tác nhanh xếp hàng riêng để giữ vùng đọc.

## Màn hình nhỏ
Dưới 640px: form một cột, số liệu hai cột; bảng/sơ đồ cuộn trong khối riêng. Hạn chế animation, tôn trọng `prefers-reduced-motion`. Giữ nút mở sidebar gốc.

## Xác minh
AppTest kiểm tra trạng thái/thao tác; parser kiểm tra CSS. Chúng không xác minh kích thước thực tế. Cần xem 1366×768, 1920×1080 và 390px: không cắt chữ, không tràn trang, ô nhập không che tin cuối, focus rõ, bảng đọc được.

Browser tích hợp không khả dụng trong phiên cập nhật; chưa có xác minh screenshot/mobile hoặc chứng nhận WCAG toàn ứng dụng.
