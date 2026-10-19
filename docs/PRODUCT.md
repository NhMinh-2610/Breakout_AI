# Breakout AI — Đặc tả sản phẩm 0.6
## Người dùng và công việc
Người Việt theo dõi cổ phiếu VN/US, cần hiểu căn cứ trước khi quyết định và lưu lịch sử nghiên cứu. Mỗi sáng, họ muốn biết mã đang giữ nào cần chú ý, mã nào đạt điều kiện nghiên cứu thêm và giải thích trong sách.

Luồng chính: **Sách → nguyên tắc đã đối chiếu → giá và danh mục → bản tin → nghiên cứu thêm.**

Thư viện nhận PDF/TXT/MD. Người dùng chọn một sách, kiểm tra câu trích và xác nhận nguyên tắc. Danh mục là vị thế thực do họ nhập, độc lập với danh sách tìm mua. Chat và tin tức hỗ trợ nghiên cứu.

| Trạng thái | Điều kiện |
| --- | --- |
| Cân nhắc mua | Mã chưa sở hữu đạt tất cả điều kiện mua hỗ trợ và đủ dữ liệu |
| Cân nhắc bán | Mã đang sở hữu chạm ít nhất một điều kiện bán kiểm tra được |
| Giữ và theo dõi | Kiểm tra đủ điều kiện bán và chưa chạm ngưỡng |
| Cần xem thêm | Thiếu dữ liệu/nguyên tắc hoặc chưa đạt điều kiện mua |

Chưa có sách/nguyên tắc hỗ trợ hoặc chưa đối chiếu thì hướng dẫn bước tiếp theo. Không tự đặt ngưỡng để tạo gợi ý.

## Tổ chức sản phẩm
Tổng quan ưu tiên bản tin. Bảng giá & biểu đồ có nguồn theo phiên. Danh mục & giao dịch tách vị thế, ghi giao dịch và lịch sử. Tin tức có tiêu đề/nguồn/thời gian. Chat AI có lịch sử sidebar và ô nhập cố định. Thư viện sách quản lý dữ liệu và nguyên tắc.

## Tiêu chí nghiệm thu
- Tên, logo, tiêu đề, tệp xuất và tài liệu thống nhất Breakout AI.
- Lối tắt mở đúng công việc; thao tác lưu cập nhật số liệu ngay.
- Chat lưu bền, tìm/mở/đổi tên/xuất/xóa được, không gửi lặp khi chuyển trang.
- Giao dịch và số dư nguyên tử, chống trùng/bán vượt/thứ tự ngày sai.
- Giá có ngày, tiền tệ và nguồn; thiếu dữ liệu không thay bằng giá giả.
- VND/USD giữ riêng; phân bổ vốn không gọi là hiệu suất tài khoản.
- Nâng cấp giữ dữ liệu, CLI hoạt động, lịch dùng đúng thư mục mới.
- Kiểm thử chức năng và kiểm tra hình ảnh được báo cáo riêng.

## Ranh giới
Bản local chưa có auth/billing/broker. Parser có phạm vi hữu hạn; RAG chưa fine-tune hoặc hiểu toàn bộ sách. Nguồn phát triển chưa xác nhận quyền phân phối thương mại; phương pháp chưa backtest. [Kế hoạch bán thử](COMMERCIAL_PLAN.md) và [Backlog](../notes/BACKLOG.md) ghi việc cần hoàn thiện.
