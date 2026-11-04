# Backlog Breakout AI

## Trọng tâm

Hoàn thiện khả năng đọc dữ liệu biểu đồ, giải thích cơ hội và phản biện bằng bằng chứng. Giữ phạm vi nhỏ để đo chất lượng trước khi mở rộng sản phẩm.

## Đã có trong 0.9

- Trang đầu tập trung một mã và biểu đồ; bảng điện/công cụ cũ giữ ở luồng phụ.
- Observer dùng chung cho report, facts, scenarios và tối đa 60 nến đóng.
- Model chọn ID bằng chứng/kịch bản trong hợp đồng; đầu ra sai giữ kết quả theo quy tắc.
- Nhận định lưu bối cảnh; polling không gọi model.
- Lỗi nguồn giữ qua cache/rerun; phản hồi mất quyền claim không thay dữ liệu mới.

## Ưu tiên tiếp theo

| Ưu tiên | Công việc | Bằng chứng hoàn thành |
| --- | --- | --- |
| P0 | Tập đánh giá biểu đồ có nhãn | Bộ tình huống có nguồn/thời gian, xu hướng/vùng giá/xác nhận/giới hạn được đối chiếu |
| P0 | Đánh giá model thật | Đo chọn bằng chứng, bỏ sót phản biện, sai hợp đồng, latency và chi phí trên cùng tập dữ liệu |
| P0 | Backtest theo thời gian | Tách giai đoạn phát triển/đánh giá, tính phí/trượt giá và tránh dùng dữ liệu tương lai |
| P0 | Chất lượng dữ liệu | Kiểm tra mất nến, đổi đơn vị, cổ tức/quyền, phiên nghỉ và sai lệch giữa quote/biểu đồ |
| P0 | QA giao diện thật | Bằng chứng desktop/mobile/bàn phím; nội dung không chồng hoặc che thao tác chính |
| P1 | Nhật ký nhận định và kết quả | Đối chiếu nhận định đã chụp với diễn biến sau đó, không sửa lịch sử |
| P1 | Quyền sử dụng dữ liệu | Phạm vi hiển thị/phân phối, hạn mức và chi phí rõ trước pilot bên ngoài |
| P1 | Backup/restore | Khôi phục thử trên database riêng |
| P2 | Thử nghiệm với nhóm nhỏ | Quan sát tác vụ đọc biểu đồ và lý do người dùng tin/không tin nhận định |

Auth/billing, thông báo đám mây và mở rộng nhiều thị trường chỉ xem lại sau khi luồng phân tích có bằng chứng đủ tốt. Nhận ảnh chụp biểu đồ cần hợp đồng và tập đánh giá riêng, chưa suy ra từ khả năng đọc OHLCV hiện tại.

Chưa làm tự đặt lệnh, quét toàn sàn bằng tick stream hoặc cam kết lợi nhuận. [Sản phẩm](../docs/PRODUCT.md) · [Observer](../docs/CHART_OBSERVER.md).
