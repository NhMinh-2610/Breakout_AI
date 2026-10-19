# Kế hoạch bán thử Breakout AI
## Định vị
Trợ lý nghiên cứu cho người Việt theo dõi VN/US: mỗi sáng hiểu mã nào cần xem lại, căn cứ nào đến từ sách và số liệu nào thực sự có. Giá trị cần kiểm chứng là giảm công tra cứu, giữ lập luận và theo dõi danh mục trong một nơi.

Bản 0.6 là nền tảng local để demo, chưa là SaaS thu phí công khai. Đổi tên và giao diện không thay thế quyền dữ liệu, đánh giá chất lượng hoặc kiểm chứng nhu cầu.

## Giả thuyết
1. Người dùng quay lại xem bản tin có nguồn mỗi tuần.
2. Giải thích từ sách và dữ liệu giúp họ hiểu kết luận.
3. Nhật ký/chat lưu bền tạo giá trị hơn một câu trả lời rời rạc.
4. Hỗ trợ VN/US phù hợp cùng một phân khúc ban đầu.
5. Họ sẵn sàng trả tiền cho việc nghiên cứu thuận tiện, không chỉ lời hứa dự đoán giá.

## Thử nghiệm 30 ngày
| Giai đoạn | Việc làm | Bằng chứng |
| --- | --- | --- |
| Tuần 1 | Phỏng vấn khoảng 10 người; demo tác vụ thật | Vấn đề gần đây, công cụ đang dùng |
| Tuần 2 | Khoảng 5 người dùng thử có hỗ trợ | Họ tự hoàn thành tác vụ nào, vướng ở đâu |
| Tuần 3 | Sửa lỗi lặp lại, đánh giá model/sách thực | Câu trả lời đúng, nguồn rõ, chi phí |
| Tuần 4 | Đề xuất pilot có phạm vi cụ thể | Cam kết trả tiền, lý do từ chối |

Các con số là kế hoạch thử nhỏ, chưa có kết quả/doanh thu. Theo dõi activation, quay lại tuần sau, tác vụ hoàn thành, lỗi nghiêm trọng và chi phí/người dùng. Không dùng lời khen UI làm bằng chứng trả tiền.

## Gói để nghiên cứu
Trải nghiệm giới hạn lượt; cá nhân có bản tin/danh mục/lịch sử; nhóm có quản trị nếu nhu cầu được xác nhận. Chưa triển khai gói/thanh toán và chưa ấn định giá bán. Chọn mức giá sau phỏng vấn và đo chi phí thực.

Chi phí gồm model, nguồn giá/tin/sách, hosting, lưu trữ, thanh toán và hỗ trợ. Dùng đơn giá thực tế của nhà cung cấp; usage local không phải hóa đơn. Cần ngân sách cứng và kiểm soát quota trước gọi model.

## Điều kiện ra pilot
- Nguồn giá, RSS và sách có quyền sử dụng đúng phạm vi thương mại.
- Auth và tách dữ liệu giữa tài khoản được kiểm thử.
- Đánh giá nội dung bằng sách có quyền và người có chuyên môn; kiểm tra ngoại lệ của parser.
- Quy trình điều chỉnh journal, backup, export/xóa dữ liệu và hỗ trợ.
- Billing/webhook chống trùng, đối soát/hoàn tiền.
- Mô tả đúng giới hạn, điều khoản phù hợp phạm vi hoạt động và thị trường.
- Kiểm tra tên miền/nhãn hiệu khi quyết định dùng thương hiệu công khai.

Tên Breakout AI không hàm ý chiến lược đã backtest. Nguồn public hiện chưa được xác nhận quyền phân phối thương mại. [Nguồn giá](MARKET_DATA.md) · [Tin tức](NEWS.md) · [Sách](BOOKS.md).
