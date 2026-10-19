# Bản tin hằng ngày của Breakout AI
## Thiết lập một lần
1. Chạy app, mở **Thư viện sách**, tải PDF có lớp chữ/TXT/MD và bấm **Đọc sách**.
2. Chọn một sách, đối chiếu nguyên tắc với câu/trang gốc, xác nhận **Dùng cho bản tin hằng ngày**. Kiểm tra lại khi đổi sách/nguyên tắc.
3. Trong **Danh mục & giao dịch → Danh mục hiện tại**, mở **Nhập / sửa cổ phiếu đang có** để nhập vị thế ban đầu. VN dùng VND đầy đủ, US dùng USD.
4. Mở phần **Chọn các mã để tìm cơ hội mua mới** để chọn tối đa 10 mã; danh mục sở hữu tối đa 20 mã.
5. Xem **Tổng quan → Gợi ý hôm nay**. Mở **Vì sao có gợi ý này?** để đọc điều kiện, phép tính và nguồn.

Các mã mặc định để thử phạm vi tìm kiếm không phải danh sách được khuyến nghị mua. Ví dụ tự viết ở `examples/daily_rules.md` dùng thử chức năng, chưa được kiểm chứng bằng đầu tư.

## Đọc bản tin
| Nhãn | Cách hiểu |
| --- | --- |
| Cân nhắc mua | Mã chưa sở hữu đạt tất cả điều kiện mua hỗ trợ |
| Cân nhắc bán | Mã đang giữ chạm ít nhất một điều kiện bán đủ dữ liệu |
| Giữ và theo dõi | Các điều kiện bán đều kiểm tra được và chưa chạm ngưỡng |
| Cần xem thêm | Thiếu dữ liệu/nguyên tắc hoặc chưa đạt điều kiện mua |

Mỗi thẻ giữ nguyên trích đoạn, ngày giá, nguồn và tiền tệ. Gợi ý chưa định lượng số cổ phiếu nên giao dịch hoặc đánh giá đầy đủ doanh nghiệp/tài chính cá nhân. Sổ giao dịch mới cập nhật số lượng khi bạn ghi một giao dịch đã thực hiện.

Lãi/lỗ giá trong bản tin so với giá vốn; chưa trừ phí bán/thuế/cổ tức. Lãi/lỗ đã chốt trong journal có công thức riêng. [Sổ giao dịch](TRADES.md).

## Nguyên tắc hỗ trợ
Parser nhận một số câu điều kiện trực tiếp Việt/Anh về tỷ lệ lãi/lỗ so với giá vốn, giá trên/dưới/cắt đường trung bình và biên an toàn có tỷ lệ. Giá trị nội tại, nếu cần, do bạn nhập và chưa được hệ thống xác minh.

Sách định tính vẫn dùng hỏi đáp, nhưng không tự chuyển thành tín hiệu. Parser có thể bỏ sót ngoại lệ/ngữ cảnh; chỉ xác nhận điều kiện phản ánh đúng nội dung gốc. Tin tức RSS không tự sửa điều kiện sách.

## Lịch 07:30 Việt Nam
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\daily-schedule.ps1 -Mode Install
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\daily-schedule.ps1 -Mode Status
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\daily-schedule.ps1 -Mode Remove
```

Windows dùng `SE Asia Standard Time`. Task `BreakoutAI-Morning-<hash>` có marker riêng; script không sửa task không khớp. Job dùng pythonw, quyền Limited và Interactive; cần máy bật, tài khoản đăng nhập và mạng. App có thể đóng. Không lưu mật khẩu, không gửi email/push hoặc lệnh môi giới.

ExecutionPolicy Bypass chỉ áp dụng tiến trình gọi script. Task có chạy bù theo Windows, tối đa hai lần retry cách 5 phút; không bảo đảm đúng phút khi máy ngủ/tắt. `last_result=0` chỉ chứng minh tiến trình thành công, có thể bản tin vẫn “chưa có sách”.

## Chạy ngay và xem lại
```powershell
.\.venv\Scripts\python.exe -m breakout_ai.daily --refresh
```
Console chỉ in ngày, trạng thái và số mã. Cùng ngày/đầu vào dùng bản lưu; đổi sách/danh mục/ước tính sẽ tạo lại. Nút **Cập nhật dữ liệu và gợi ý** tải lại giá. Lịch sử giữ bản cập nhật gần nhất mỗi ngày, UI cho xem tối đa 60 ngày gần nhất và xuất JSON.

VN dùng phiên trước ngày Việt Nam hiện tại; US nhận bar cùng ngày UTC từ 22:00 UTC. Đây là mốc bảo thủ, chưa phải lịch giao dịch đã kiểm chứng mọi phiên. Dữ liệu cũ quá 7 ngày, cache tải lại lỗi hoặc khối lượng không dương sẽ chờ.

Không thấy bản tin: kiểm tra sách/nguyên tắc, nguồn và Status. Đổi thư mục phải cập nhật lịch theo [MIGRATION](MIGRATION.md).
