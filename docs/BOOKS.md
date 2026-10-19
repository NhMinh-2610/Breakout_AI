# Thư viện sách Breakout AI
## Sách được dùng thế nào?
Tài liệu được trích chữ, chia đoạn theo trang, lưu SQLite và truy xuất bằng BM25. Chat dùng những đoạn liên quan kèm nguồn; đây là RAG, chưa thay đổi trọng số LLM.

Sách giải thích khái niệm/phương pháp; dữ liệu thị trường cung cấp số liệu theo thời điểm. Nội dung sách không chứng minh một doanh nghiệp hiện tại đáp ứng điều kiện tác giả nêu.

## Nhập sách
1. Mở **Thư viện sách**, chọn PDF có lớp chữ, TXT hoặc Markdown có quyền sử dụng.
2. Nhập tên/tác giả, bấm **Đọc sách** và chọn sách cho bản tin.
3. Đối chiếu câu trích/nguyên tắc; xác nhận nếu đúng ngữ cảnh.
4. Tìm từ khóa trong phần quản lý thư viện hoặc hỏi ở **Chat AI**.

Demo trả trích đoạn; provider LLM có thể tổng hợp khi được cấu hình. Bản tin dùng parser cục bộ riêng, chỉ một sách đã chọn và không gọi LLM. [Hướng dẫn bản tin](DAILY_GUIDE.md).

## Giới hạn
| Nội dung | Giới hạn |
| --- | --- |
| File | 20 MB, 400 trang, 1,5 triệu ký tự, 3.000 đoạn |
| Thư viện mỗi workspace | 6.000 đoạn |
| Đoạn truy xuất | Khoảng 1.500 ký tự, overlap khoảng 180 |
| Đưa vào model | Tối đa 3 đoạn |
| PDF | Không nhận mã hóa/mật khẩu; scan cần OCR bên ngoài |

PDF dẫn số trang vật lý kể từ bìa; TXT/MD dẫn số đoạn. SHA-256 chống nhập trùng nội dung trong workspace. Trích xuất bằng [pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) không bảo đảm thứ tự bảng/công thức/nhiều cột; chưa đọc hình/biểu đồ hoặc OCR.

BM25 có chuẩn hóa tiếng Việt và alias Việt–Anh nhỏ. Từ khóa khác cách viết có thể bị bỏ sót; chưa có embedding hoặc benchmark trên bộ sách thực của người dùng.

## Lưu trữ và quyền
File gốc không lưu xuống filesystem; text và metadata nằm trong books/book_chunks. Khi dùng LLM ngoài máy, đoạn truy xuất và lịch sử gần nhất có thể được gửi đi. Tài liệu được đưa vào như dữ liệu tham khảo, không phải chỉ dẫn thay vai trò.

Xóa sách xóa đoạn và báo cáo ngày của sách; trích đoạn đã nằm trong chat, backup hoặc export không tự mất. Chưa có xóa toàn workspace. Không tự tải sách thương mại hoặc chia sẻ corpus giữa khách hàng. Ví dụ dự án tự viết để thử, không phải sách chuyên khảo cấp phép sẵn.
