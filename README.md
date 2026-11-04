# Breakout AI

**Quan sát biểu đồ. Đối chiếu cơ hội. Hiểu điều kiện và rủi ro.**

Breakout AI **0.9.0** tập trung vào một việc: đọc dữ liệu giá/khối lượng tạo nên biểu đồ cổ phiếu Việt Nam và đưa ra nhận định có căn cứ. Ứng dụng chạy local bằng Python, Streamlit và SQLite.

Luồng chính: **Chọn mã → quan sát nến → kiểm tra bằng chứng → đọc nhận định → hỏi phản biện.** Màn hình mặc định mở biểu đồ của một mã, không tải bảng điện hoặc chạy bản tin theo sách trước.

## Chạy ứng dụng

Mở terminal tại thư mục `Breakout_AI`:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8507
```

Mở **http://localhost:8507**. Có thể dùng `.\scripts\run.ps1`; máy mới chạy `.\scripts\setup.ps1 -Dev`. [Hướng dẫn cài đặt](docs/GETTING_STARTED.md).

## Dùng luồng phân tích

1. Mở **Phân tích AI → Phân tích biểu đồ**.
2. Chọn mã và khung nến **1/5/15 phút**. Xem cấu trúc giá, SMA20, RSI14, hỗ trợ/kháng cự và khối lượng.
3. Đọc trạng thái quan sát, bằng chứng và điều kiện còn thiếu. Nến đang hình thành có thể hiển thị nhưng không xác nhận tín hiệu.
4. Bấm **Đọc biểu đồ & nhận định** để lưu một nhận định theo dữ liệu tại lúc gửi. Trong demo, đây là diễn giải bằng quy tắc; khi cấu hình model, AI chọn bằng chứng và kịch bản từ bối cảnh đã kiểm tra.
5. Dùng **Chat theo mã** để hỏi lý do, phản biện hoặc kiến thức liên quan. Nhận định và hội thoại có thể mở lại tại **Lịch sử & hỏi đáp**.

Để thêm mã ngoài danh sách hiện có, chuyển sang **Bảng điện Việt Nam → Tùy chọn bảng** và lưu danh sách theo dõi. **Cơ hội hôm nay** cho phép chọn tối đa 6 mã để quét sau khi bấm bắt đầu.

## AI đang đọc gì?

Observer tạo một bối cảnh thống nhất gồm quote đúng mã, báo cáo kỹ thuật, tối đa **60 nến OHLCV đã đóng**, các bằng chứng có ID và các kịch bản xác nhận/vô hiệu. AI nhận dữ liệu số đứng sau biểu đồ; phiên bản này chưa nhận ảnh chụp biểu đồ.

Khi dùng model, phản hồi phải là JSON với bốn trường `action`, `focus_fact_ids`, `risk_fact_ids` và `scenario_id`. Ứng dụng kiểm tra ID, giữ nguyên trạng thái của bộ quy tắc rồi dựng văn bản từ dữ liệu gốc. Nội dung model tự tạo thêm giá mục tiêu, xác suất hoặc kết luận vượt qua blocker không được hiển thị như nhận định hợp lệ. Phản hồi sai hợp đồng quay về diễn giải theo quy tắc.

[Hợp đồng quan sát biểu đồ](docs/CHART_OBSERVER.md) · [Quy tắc kỹ thuật](docs/TECHNICAL_ANALYSIS.md).

## Kết quả được diễn đạt thế nào?

| Trạng thái | Ý nghĩa |
| --- | --- |
| Theo dõi điểm mua | Có mẫu hình đủ điều kiện giá, khối lượng và dữ liệu hiện tại |
| Rà soát điểm bán | Mã đang sở hữu có điều kiện rủi ro được xác nhận |
| Tiếp tục quan sát | Chưa có điều kiện mới đủ để thay đổi nhận định |
| Chờ | Dữ liệu cũ/thiếu/lỗi hoặc mẫu hình chưa được xác nhận |

Giá thấp hoặc RSI thấp chưa chứng minh đã tạo đáy. Số điều kiện đạt là số kiểm tra, không phải xác suất thắng. Các quy tắc hiện chưa được kiểm định thành chiến lược đầu tư; ứng dụng chưa tự đặt lệnh.

## Dữ liệu và nhịp cập nhật

Trang phân tích chính chỉ yêu cầu quote và nến của mã đang xem. Tự cập nhật thị trường không gọi model; model chỉ chạy khi bấm nhận định hoặc gửi câu hỏi.

| Dữ liệu | Nguồn / nhịp |
| --- | --- |
| Snapshot cổ phiếu VN | DNSE public snapshot; mặc định 5 giây |
| Nến cổ phiếu VN | DNSE public OHLCV; cache 30 giây |
| Chỉ số ở chế độ bảng điện | DNSE index OHLCV; cache 60 giây |
| Biểu đồ ngày VN / US | KBS / Yahoo; luồng riêng |

Có tạm dừng và cập nhật thủ công. Giờ nguồn, giờ nhận và thời gian nến được giữ riêng. Lỗi nguồn được giữ qua cache/rerun đến khi tải lại thành công; phản hồi cũ về muộn không thay thế dữ liệu mới. Đây là polling snapshot, chưa có luồng tick đẩy. [Snapshot](docs/REALTIME.md) · [Nến/chỉ số và đơn vị](docs/INTRADAY.md).

## Các công cụ hỗ trợ

Danh mục/giao dịch, kiến thức từ sách, lịch sử hỏi đáp, bản tin theo sách và tin tức vẫn được giữ để hỗ trợ nghiên cứu. Bảng điện đầy đủ và biểu đồ ngày VN/US nằm trong các chế độ phụ; phân tích nến trong phiên hiện dành cho cổ phiếu VN.

Sách được truy xuất theo đoạn/trang để giải thích, chưa huấn luyện lại trọng số model hoặc tự biến toàn bộ sách thành chiến lược. Bản tin theo sách lúc 07:30 có luồng riêng. [Sách](docs/BOOKS.md) · [Bản tin](docs/DAILY_GUIDE.md) · [Sổ giao dịch](docs/TRADES.md).

## Phát triển và xác minh

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Dự án tách lớp dữ liệu, kiểm tra kỹ thuật, observer, diễn giải model và giao diện. Các kiểm thử phần mềm không chứng minh hiệu quả đầu tư. Trạng thái model thật, API thật và QA trình duyệt được ghi riêng tại [Kiểm thử](docs/TESTING.md).

[Sản phẩm](docs/PRODUCT.md) · [Kiến trúc](docs/ARCHITECTURE.md) · [UI/UX](docs/UI_UX.md) · [Bản đồ tài liệu](docs/README.md) · [Backlog](notes/BACKLOG.md).

Nguồn phát triển có thể chậm hoặc gián đoạn; quyền hiển thị/phân phối thương mại cần xác nhận trước khi bán dịch vụ.
