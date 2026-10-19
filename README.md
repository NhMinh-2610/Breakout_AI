# Breakout AI
**Hiểu dữ liệu. Đầu tư có cơ sở.**

Breakout AI là trợ lý nghiên cứu cổ phiếu Việt Nam và Mỹ, kết hợp kiến thức trong sách với dữ liệu giá và danh mục cá nhân. Bản **0.6.0** chạy trên máy bằng Python, Streamlit và SQLite.

Ứng dụng có bản tin 07:30, biểu đồ giá theo phiên, sổ mua/bán, tin tức có nguồn và chat lưu lịch sử. “Breakout” là tên sản phẩm; bản tin vẫn theo nguyên tắc trong sách bạn chọn, không mặc định dùng chiến lược phá vỡ giá.

## Chạy ứng dụng
Mở terminal tại thư mục `Breakout_AI`:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8507
```

Mở **http://localhost:8507**. Hoặc chạy `.\scripts\run.ps1`; đổi cổng bằng `.\scripts\run.ps1 -Port 8510`. Sau cập nhật, dừng tiến trình cũ bằng Ctrl+C rồi chạy lại để nạp theme.

Máy mới: `.\scripts\setup.ps1 -Dev`. Chi tiết: [Bắt đầu](docs/GETTING_STARTED.md).

## Dùng trong 5 phút
1. **Thư viện sách:** tải PDF/TXT/MD, chọn sách và đối chiếu nguyên tắc được trích trước khi dùng.
2. **Danh mục & giao dịch:** nhập cổ phiếu đang giữ, số lượng và giá vốn; VN dùng VND đầy đủ, US dùng USD.
3. **Tổng quan:** xem gợi ý hôm nay, mở giải thích và đối chiếu nguồn sách, phiên giá.
4. **Chat AI:** hỏi khái niệm hoặc mã như `VN:FPT`, `US:AAPL`; lịch sử nằm ở sidebar.
5. Ghi các lần mua/bán đã thực hiện trong **Ghi giao dịch** để cập nhật danh mục.

Không có sách thương mại hoặc vị thế giả nạp sẵn. [Tài liệu thử](examples/daily_rules.md) do dự án tự viết chỉ dùng kiểm tra chức năng.

## Các màn hình
| Mục | Công việc |
| --- | --- |
| Tổng quan | Gợi ý hôm nay, giá tự tải, cập nhật theo nhóm và bản tin cũ |
| Bảng giá & biểu đồ | Tra giá theo phiên, MA20, bảng dữ liệu và nguồn |
| Danh mục & giao dịch | Xem vị thế, ghi mua/bán, lọc lịch sử và xuất CSV |
| Tin tức | Tìm tiêu đề VN/Mỹ, xem nguồn/thời gian và mở báo gốc |
| Chat AI | Hỏi đáp, tìm/mở lại/đổi tên/xuất/xóa hội thoại |
| Thư viện sách | Nhập sách, tìm đoạn, chọn và kiểm tra nguyên tắc |

## Giá chứng khoán và giao diện
Mở Tổng quan để tải giá từ KBS (VN) và Yahoo (US). Ứng dụng ưu tiên cache, tự kiểm tra mỗi 5 phút khi trang mở; nút **Cập nhật giá theo dõi** lấy lại cả nhóm mã. Khi nguồn lỗi, có thời gian chờ trước khi tự thử lại, vẫn cho cập nhật thủ công. Giá cũ/thiếu có trạng thái riêng.

Bảng giá có dòng cho từng mã, gồm giá, tiền tệ, phần trăm, phiên và nguồn. Các ô số liệu đều chiều cao; form/nút căn hàng, khoảng cách 8/16/24/32px và bố cục riêng cho màn nhỏ. Dữ liệu theo phiên, chưa phải báo giá tick realtime.

## Bản tin 07:30
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\daily-schedule.ps1 -Mode Install
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\daily-schedule.ps1 -Mode Status
```

Lịch chạy **07:30 giờ Việt Nam**, cần máy bật, tài khoản đăng nhập và kết nối mạng. App có thể đóng. Bản tin lưu trong ứng dụng, chưa gửi thông báo hoặc đặt lệnh. [Hướng dẫn hằng ngày](docs/DAILY_GUIDE.md).

Chạy ngay: `.\.venv\Scripts\python.exe -m breakout_ai.daily --refresh`.

## Phạm vi thực tế
- Sách được trích chữ và truy xuất theo đoạn/trang; chưa huấn luyện lại trọng số LLM.
- Bản tin tính một số điều kiện rõ ràng từ sách đã đối chiếu, chưa hiểu toàn bộ phương pháp của tác giả.
- Giá từ KBS/Yahoo phục vụ phát triển, theo ngày và có thể chậm. Thiếu dữ liệu thì chờ cập nhật.
- Demo dùng được không cần key; cấu hình OpenAI/Ollama để tổng hợp tự nhiên.
- Nhật ký ghi giao dịch bạn đã thực hiện; chưa có broker, hiệu suất đầy đủ sau quyền/thuế hoặc quy trình sửa giao dịch.
- Auth, billing và quyền phân phối dữ liệu thương mại cần hoàn thiện trước khi bán.

## Mã và tài liệu
[Bản đồ tài liệu](docs/README.md) · [Sản phẩm](docs/PRODUCT.md) · [UI/UX](docs/UI_UX.md) · [Kiến trúc](docs/ARCHITECTURE.md) · [Kiểm thử](docs/TESTING.md) · [Chuyển đổi tên](docs/MIGRATION.md)

```text
app.py                Điều hướng và màn hình Streamlit
assets/               Theme, logo và favicon
breakout_ai/           Dữ liệu, sách, chat, danh mục và bản tin
content/              Ghi chú tài chính nền có nguồn
scripts/              Cài đặt, chạy, kiểm thử và lịch Windows
tests/                Kiểm thử nghiệp vụ, adapter và giao diện
docs/                 Hướng dẫn sử dụng và kỹ thuật
notes/                Quyết định, backlog và nhật ký
```

Kiểm tra: `.\.venv\Scripts\python.exe -m pytest`. Nâng cấp giữ database đã có; không đổi hoặc xóa dữ liệu để đổi thương hiệu.
