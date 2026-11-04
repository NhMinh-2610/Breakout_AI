# Breakout AI — Phạm vi sản phẩm 0.9

## Công việc chính

Người theo dõi cổ phiếu muốn nhìn một biểu đồ, biết dữ liệu đang mô tả điều gì và xem có cơ hội đáng nghiên cứu hay điều kiện rủi ro cần chú ý. Breakout AI hỗ trợ công việc đó bằng bằng chứng có nguồn và các điều kiện kiểm tra được.

Luồng chính: **Chọn mã → đọc dữ liệu biểu đồ → đối chiếu bằng chứng → nhận định có điều kiện → hỏi phản biện.** Màn hình đầu tiên là **Phân tích AI → Phân tích biểu đồ**, tập trung một mã cổ phiếu Việt Nam.

## Đầu vào và đầu ra

Đầu vào gồm quote, nến OHLCV, khung thời gian, giờ nguồn và thông tin mã có đang được sở hữu. Observer tạo báo cáo kỹ thuật, mô tả cấu trúc giá, thân/bóng nến, vùng giá, khối lượng và các kịch bản có ID.

Đầu ra trả lời ba việc: đang quan sát điều gì; cần điều kiện nào để xem đó là cơ hội; điều gì làm luận điểm mất hiệu lực hoặc buộc chờ. “Theo dõi mua” và “rà soát bán” là tín hiệu quan sát, chưa phải lệnh giao dịch.

| Trạng thái | Quy ước |
| --- | --- |
| Theo dõi mua | Mẫu hình có đủ xác nhận và dữ liệu đủ mới |
| Rà soát bán | Điều kiện rủi ro xảy ra ở mã đang sở hữu |
| Tiếp tục quan sát | Mã sở hữu chưa có điều kiện mới đủ xác nhận |
| Chờ | Dữ liệu chưa sẵn sàng hoặc mẫu hình chưa đủ điều kiện |

## Vai trò của AI

Ứng dụng đọc dữ liệu số tạo nên biểu đồ, chưa đọc ảnh chụp. Bộ tính kiểm tra chỉ báo và điều kiện; model nhận tối đa 60 nến đã đóng cùng các bằng chứng/kịch bản. Model chọn các ID phù hợp với câu hỏi; bộ kiểm tra giữ nguyên action và chỉ dựng văn bản từ dữ liệu được cấp.

Demo hiển thị rõ là quy tắc, không giả là model đã được kết nối. Các lượt dùng model thật cần được đánh giá riêng; test mock không chứng minh chất lượng mô hình thực tế. [Hợp đồng observer](CHART_OBSERVER.md).

## Công cụ phụ

Bảng điện, danh mục/sổ giao dịch, sách, lịch sử hỏi đáp, bản tin theo sách và tin tức được giữ nguyên dữ liệu. Chúng hỗ trợ luồng nghiên cứu, không quyết định thứ tự màn hình chính.

Sách dùng để truy xuất/đối chiếu kiến thức. Bản tin 07:30 có quy tắc riêng đã được người dùng kiểm tra; không trộn với nhận định nến trong phiên.

## Tiêu chí nghiệm thu

- Mở ứng dụng thấy biểu đồ một mã; không tự chạy bản tin hoặc tải cả bảng điện.
- Quote, nến, khung thời gian và đơn vị khớp nhau trước khi phân tích.
- Nến chưa đóng không xác nhận tín hiệu; dữ liệu lỗi/cũ/thiếu chuyển chờ.
- Nhận định có bằng chứng, điều kiện xác nhận/vô hiệu và giờ dữ liệu.
- AI không đổi action, tạo ID bằng chứng hoặc thêm giá/xác suất tùy ý.
- Polling không gọi model; bấm nhận định/gửi câu hỏi chỉ lưu một lượt.
- Nhận định lưu bối cảnh bất biến; đổi mã không trộn lịch sử.
- Nâng cấp giữ dữ liệu; kiểm thử chức năng và QA hình ảnh được báo cáo riêng.

## Ưu tiên tiếp theo

Tạo tập đánh giá biểu đồ có nhãn, đánh giá nhận định trên model thật và kiểm định theo thời gian với phí/trượt giá. Sau khi có bằng chứng về chất lượng mới mở rộng phạm vi sử dụng. [Backlog](../notes/BACKLOG.md).

Chưa có cam kết hiệu quả đầu tư, tự đặt lệnh, quét toàn sàn bằng tick stream hoặc sản phẩm SaaS sẵn sàng thu phí.
