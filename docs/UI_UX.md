# Giao diện Breakout AI

## Bố cục và khoảng cách

Menu trái và nội dung chính có mép căn riêng. Trang thị trường ưu tiên chỉ số, bảng giá rồi khu vực xem sâu một mã; thao tác ít dùng nằm trong popover hoặc tab.

| Thành phần | Quy ước |
| --- | --- |
| Sidebar | 256px, logo 40px, tên và mô tả hai dòng |
| Trang dữ liệu | Tối đa 1360px, lề nội dung 24px |
| Thị trường / bảng điện | Tối đa 1760px |
| Tin tức / sách | Tối đa 1080px |
| Hội thoại chính / ô nhập | Cùng giới hạn 820px và lề hai bên |
| Panel biểu đồ / phân tích | Padding 24px trên desktop, 16px trên màn hình nhỏ |
| Cột Streamlit thông thường | Khoảng cách ngang 16px |
| Lưới biểu đồ / phân tích có key | Khoảng cách 24px, quản lý cả độ rộng cột |
| Ô nhập / nút | Cao tối thiểu 44px |

Khoảng cách dùng các mốc 8/16/24/32px. Nội dung panel và nhãn có khoảng đệm riêng; không dùng border/padding của panel cho toàn bộ tổ tiên trang.

Trong bản 0.8, sửa hai nguyên nhân gây ép cột và chữ sát mép: CSS từng đổi gap ngang sang 24px trong khi Streamlit vẫn tính chiều rộng cột theo gap 16px; selector panel dùng :has quá rộng khiến khối cha cũng nhận padding/border. Cột thường nay giữ gap gốc, chỉ các lưới có key mới tự quản lý chiều rộng và khoảng cách. Selector panel giới hạn theo quan hệ con trực tiếp trên wrapper phù hợp; vùng chính có padding rõ.

## Không gian bảng điện

Trang mặc định mở **Bảng điện Việt Nam**. **Biểu đồ VN / US** giữ giá ngày và MA20, với nguồn/nhịp tải riêng.

Thứ tự nội dung:

1. Bốn thẻ chỉ số gọn: VN-Index, VN30, HNX-Index và UPCoM-Index, có mức điểm, đường diễn biến cạnh số và giờ nến nguồn.
2. Một hàng desktop gồm sàn, tìm mã, sắp xếp, tự cập nhật, Tùy chọn bảng và làm mới. Popover Tùy chọn bảng chứa nhịp tải, đầy đủ/rút gọn và biểu mẫu danh sách mã.
3. Dải đếm số mã/tăng/giảm/tham chiếu gọn và bảng giá rộng toàn vùng; tiêu đề/cột mã cố định, vùng cuộn riêng.
4. Chọn mã và khung nến 1/5/15 phút.
5. Cột trái là biểu đồ nến/khối lượng và thông tin phiên/cung cầu; cột phải là Phân tích, Chat theo mã và Cơ hội hôm nay.

Bảng tham khảo cách nhóm cột của [DNSE](https://banggia.dnse.com.vn/v2): mã, trần/sàn/tham chiếu, bên mua, khớp lệnh, bên bán, tổng giao dịch, thống kê phiên và khối ngoại. Mua từ mức 3 đến 1, bán từ 1 đến 3 để mức tốt nhất nằm cạnh khớp lệnh. Chú giải ghi giá ×1.000 VND, khối lượng cổ phiếu và giá trị triệu VND; các thẻ chỉ số ghi điểm.

Bảng theo dõi tối đa 30 mã. Bộ lọc và thống kê tăng/giảm chỉ mô tả danh sách đang xem, không đại diện toàn thị trường hoặc rổ VN30. Danh sách ban đầu là mẫu theo dõi, không phải gợi ý mua.

| Vùng | Hành vi |
| --- | --- |
| Tự cập nhật | Snapshot 5/10/30 giây; nến 30 giây; chỉ số 60 giây; có tạm dừng và tải thủ công |
| Chi tiết mã | Giữ mã khi bảng được sắp xếp lại; đổi mã lấy đúng dữ liệu cho biểu đồ/phân tích/chat |
| Biểu đồ | Nến, SMA20, hỗ trợ/kháng cự và khối lượng; nến đang hình thành có dấu hiệu riêng |
| Cung cầu | Ba mức giá chờ và biểu đồ độ sâu; hiển thị giờ nguồn, ẩn dữ liệu quá cũ |
| Phân tích | Kịch bản, bằng chứng, điều kiện đạt/chưa đạt, mốc mất hiệu lực và dữ liệu cần chờ |
| Chat theo mã | Form gửi nằm trong panel; lịch sử cuộn riêng và cũng lưu tại Chat AI |
| Cơ hội hôm nay | Chọn tối đa 6 mã, bấm quét để bắt đầu; ưu tiên rà soát bán ở mã sở hữu và điều kiện mua |
| Thiếu / lỗi | Giữ dữ liệu cũ có nhãn hoặc dấu gạch; không tạo biểu đồ/số giả để lấp panel |

Phần chính giữ một tiêu đề điều hướng, không lặp thêm tiêu đề lớn phía trên bảng. Container market_terminal dùng khoảng cách dọc 16px; bộ lọc desktop sáu cột chuyển sang ba cột trên tablet và hai cột trên mobile. Dải thống kê dùng chữ/số gọn thay cho bốn thẻ metric lớn.

Biểu đồ rộng hơn panel giải thích ở desktop. Trong bảng, các cột số giữ chiều rộng và khoảng đệm; cuộn ngang chỉ nằm trong bảng, không ép toàn trang. Thông tin dày như bảng cung cầu có vùng cuộn riêng khi cần.

## Diễn đạt phân tích

Dùng “theo dõi mua”, “rà soát bán”, “giữ quan sát” và “chờ xác nhận”. Một mức giá thấp, RSI dưới 30 hoặc dư mua lớn không đủ để khẳng định đáy hay giá chắc chắn tăng.

Số điều kiện đạt mô tả các kiểm tra của ứng dụng, không biểu thị xác suất thắng. Giá, giờ nguồn, khung nến và điều kiện làm mất hiệu lực đi cùng kết luận. Bán chỉ xét mã trong danh mục sở hữu. Khi quote/nến cũ, nguồn lỗi hoặc dữ liệu chưa đủ, panel chuyển sang chờ.

Sách được truy xuất để giải thích kiến thức trong chat. Không mô tả bộ tín hiệu kỹ thuật là chiến lược tự học từ toàn bộ sách. [Quy tắc phân tích](TECHNICAL_ANALYSIS.md).

## Màu và khả năng đọc

| Vai trò | Màu |
| --- | --- |
| Nền / khối | #101216 / #181b21 |
| Chữ chính / phụ | #edf0f4 / #a1a9b6 |
| Nhận diện / thao tác | #f0bc51 |
| Tăng / giảm | #35d399 / #ff727f |
| Tham chiếu / trần / sàn | #f0bc51 / #d984f9 / #45d5e7 |
| Đường giá / SMA20 | #79b8ff / #f0bc51 |
| Nền chat / tin người dùng | #212121 / #303030 |

Dùng Segoe UI/Arial và số tabular. Chú giải, dấu phần trăm, nhãn và trạng thái bổ sung ý nghĩa cho màu. Năm màu bảng điện dựa trên tham chiếu/trần/sàn thực nhận; không dùng màu để che thiếu dữ liệu.

## Chat chính và chat theo mã

**Chat AI** là trang hội thoại đầy đủ: lịch sử tìm/mở lại/đổi tên/xuất, ô nhập gốc ở cấp trang. **Chat theo mã** nằm trong panel thị trường: lịch sử có vùng cuộn và form gửi ngay trong panel để không che bảng hoặc kéo composer toàn màn hình.

Chỉ gửi câu hỏi mới gọi model; tự tải giá/nến không sinh thêm lượt chat. Câu trả lời gắn với bối cảnh lúc gửi, không tự thay nội dung lịch sử theo tick mới. Chế độ demo giải thích bằng quy tắc; model tùy chọn diễn giải bối cảnh đã chụp.

## Màn hình nhỏ và xác minh

Responsive dựa trên chiều rộng khả dụng của vùng nội dung; biểu đồ và panel giải thích xếp dọc khi thiếu chỗ. Bộ lọc/thẻ chỉ số xếp lại theo hàng, padding panel giảm còn 16px; bảng giá giữ vùng cuộn riêng.

AppTest kiểm tra widget, điều hướng và state; parser kiểm tra cú pháp CSS. Hai cách này không xác minh kích thước thực tế. Cần kiểm tra tại 1366×768, 1920×1080 và rộng 390px: nội dung không chồng, chữ không dính viền, không tràn trang, chat không che nội dung cuối, focus rõ và bảng cuộn được.

Browser tích hợp không khả dụng trong phiên cập nhật; chưa có QA screenshot/mobile, screen reader hoặc chứng nhận WCAG toàn ứng dụng. [Kiểm thử](TESTING.md).
