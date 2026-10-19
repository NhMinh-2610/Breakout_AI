# Danh mục và sổ giao dịch Breakout AI
## Ba mục riêng
- **Danh mục hiện tại:** bảng vị thế, giá vốn và phân bổ vốn theo từng tiền tệ.
- **Ghi giao dịch:** ghi lần mua/bán đã thực hiện.
- **Lịch sử giao dịch:** lọc thị trường, mã, loại, ngày; xem lãi/lỗ và xuất CSV.

Lối tắt ở Tổng quan mở đúng mục. Đây là sổ ghi chép, chưa gửi lệnh đến môi giới.

## Vị thế ban đầu
Nhập mã, thị trường, số lượng và giá vốn nếu đã có cổ phiếu từ trước. VN nhập đầy đủ VND (58.000 đồng nhập 58000), US nhập USD. Snapshot ban đầu không trở thành giao dịch mua giả.

Mã chưa có journal có thể sửa/bỏ snapshot. Khi đã ghi journal, thay đổi số lượng bằng giao dịch; không sửa snapshot để làm lệch sổ. Biểu đồ phân bổ mặc định dựa trên vốn đang mở, giữ VND/USD riêng.

## Công thức
Mua:
```text
Giá vốn mới = (số lượng cũ × giá vốn cũ + số mua × giá mua + phí mua)
              / (số lượng cũ + số mua)
```
Bán:
```text
Lãi/lỗ đã chốt = số bán × (giá bán − giá vốn trước bán) − phí bán
```

Bán một phần giữ giá vốn đơn vị; bán hết bỏ vị thế mở. Sổ không tự quy đổi tiền tệ, tính thuế, cổ tức hoặc quyền/chia tách. Tổng lãi/lỗ ở lịch sử chỉ cộng các dòng đang hiển thị, không phải hiệu suất đầy đủ của tài khoản.

## Ràng buộc dữ liệu
Giao dịch và vị thế được ghi trong một transaction SQLite. Cùng khóa gửi/cùng nội dung trả bản ghi cũ; cùng khóa khác nội dung bị từ chối. Chặn bán vượt số lượng, ngày tương lai, ngày đi ngược lịch sử cùng mã, giá trị không hữu hạn và vượt giới hạn. Số lượng lẻ dùng Decimal ở các phép cộng/trừ quan trọng.

Mã có snapshot ban đầu chỉ ghi giao dịch từ ngày snapshot trở đi. Giao dịch cùng ngày theo thứ tự ghi; sổ không lưu giờ khớp. UPDATE/DELETE journal bị chặn; hiện chưa có quy trình hủy/điều chỉnh. Nếu nhập sai, không sửa DB thủ công để làm mất dấu vết; cần bổ sung cơ chế điều chỉnh trước dùng quy mô lớn.

## Lọc và xuất
UI hiển thị tối đa 500 dòng theo bộ lọc; CSV tối đa 10.000 dòng. Ghi chú có phòng ngừa công thức bảng tính. Export không có workspace ID hoặc khóa idempotency. Vị thế đầu kỳ không được bổ sung vào lịch sử dưới dạng giả định.

API chính: `Portfolio.record_trade`, `trades`, `trade_count`, `export_trades_csv`. Kiểm thử nghiệp vụ nằm trong `tests/test_trades.py`, thao tác UI trong `tests/test_workspace_ui.py`.
