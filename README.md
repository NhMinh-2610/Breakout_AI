# Breakout AI

**Hiểu dữ liệu. Đầu tư có cơ sở.**

Breakout AI là trợ lý nghiên cứu cổ phiếu Việt Nam và Mỹ, kết hợp kiến thức trong sách với dữ liệu giá và danh mục cá nhân. Bản **0.7.0** chạy trên máy bằng Python, Streamlit và SQLite.

Ứng dụng có bảng điện Việt Nam cập nhật theo chu kỳ, bản tin 07:30, biểu đồ giá theo phiên VN/Mỹ, sổ mua/bán, tin tức có nguồn và chat lưu lịch sử. “Breakout” là tên sản phẩm; bản tin vẫn theo nguyên tắc trong sách bạn chọn, không mặc định dùng chiến lược phá vỡ giá.

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
| Bảng điện & biểu đồ | Theo dõi bảng điện Việt Nam; chuyển sang biểu đồ ngày VN/Mỹ, MA20 và nguồn |
| Danh mục & giao dịch | Xem vị thế, ghi mua/bán, lọc lịch sử và xuất CSV |
| Tin tức | Tìm tiêu đề VN/Mỹ, xem nguồn/thời gian và mở báo gốc |
| Chat AI | Hỏi đáp, tìm/mở lại/đổi tên/xuất/xóa hội thoại |
| Thư viện sách | Nhập sách, tìm đoạn, chọn và kiểm tra nguyên tắc |

## Bảng điện và dữ liệu giá

Mở **Bảng điện & biểu đồ → Bảng điện Việt Nam** để xem snapshot DNSE: trần/sàn/tham chiếu, ba mức giá và khối lượng mua/bán, khớp lệnh, tổng giao dịch, OHLC/giá bình quân và khối ngoại. Mặc định tải mỗi **5 giây** khi trang mở; có thể chọn 10/30 giây, tạm dừng hoặc cập nhật thủ công.

Bảng theo dõi tối đa 30 mã do bạn chọn, có lọc HOSE/HNX/UPCOM, tìm mã, sắp xếp và chế độ đầy đủ/rút gọn. Bộ lọc chỉ áp dụng danh sách này. Giá hiển thị theo nghìn VND, khối lượng là cổ phiếu, giá trị giao dịch theo triệu VND. Xem giờ nguồn và giờ tải để nhận biết dữ liệu cũ; độ sâu mua/bán quá cũ được ẩn. Đây là snapshot tải định kỳ, chưa có luồng đẩy từng tick. [Chi tiết nguồn và cập nhật](docs/REALTIME.md).

Chọn **Biểu đồ VN / US** để xem dữ liệu ngày từ KBS (VN) và Yahoo (US). Tổng quan cũng dùng nguồn ngày này, ưu tiên cache và kiểm tra mỗi 5 phút khi mở. Nút **Cập nhật giá theo dõi** tải lại cả nhóm; nguồn lỗi có thời gian chờ trước khi tự thử lại.

Giao diện bảng điện lấy bố cục nhóm cột từ [bảng giá DNSE](https://banggia.dnse.com.vn/v2), có tiêu đề/cột mã cố định khi cuộn. Khoảng cách giữa các khối là 24px, giữa thẻ số liệu là 16px; bảng cuộn trong vùng riêng trên màn hình nhỏ.

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
- Bảng điện DNSE là snapshot công khai phục vụ phát triển, có thể chậm hoặc gián đoạn. KBS/Yahoo vẫn là dữ liệu ngày. Thiếu trường hiển thị dấu gạch, không tự tạo giá.
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
