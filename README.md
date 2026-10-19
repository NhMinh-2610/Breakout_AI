# Breakout AI

**Hiểu dữ liệu. Đầu tư có cơ sở.**

Breakout AI là trợ lý nghiên cứu cổ phiếu Việt Nam và Mỹ, kết hợp dữ liệu thị trường, kiến thức trong sách và danh mục cá nhân. Bản **0.8.0** chạy trên máy bằng Python, Streamlit và SQLite.

Bảng điện Việt Nam có giá, biểu đồ chỉ số, nến trong phiên và khung phân tích/chat theo mã. Ứng dụng cũng giữ bản tin 07:30, biểu đồ ngày VN/Mỹ, sổ mua/bán và tin tức có nguồn. “Breakout” là tên sản phẩm; từng kịch bản cần điều kiện và dữ liệu cụ thể.

## Chạy ứng dụng

Mở terminal tại thư mục `Breakout_AI`:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8507
```

Mở **http://localhost:8507**. Hoặc chạy `.\scripts\run.ps1`; đổi cổng bằng `.\scripts\run.ps1 -Port 8510`. Sau cập nhật, dừng tiến trình cũ bằng Ctrl+C rồi chạy lại để nạp theme.

Máy mới: `.\scripts\setup.ps1 -Dev`. Chi tiết: [Bắt đầu](docs/GETTING_STARTED.md).

## Dùng trong 5 phút

1. **Danh mục & giao dịch:** nhập cổ phiếu đang giữ, số lượng và giá vốn; VN dùng VND đầy đủ, US dùng USD.
2. **Bảng điện & biểu đồ:** chọn mã và khung nến 1/5/15 phút; xem giá, khối lượng, cung cầu và phần **Phân tích**.
3. **Chat theo mã:** hỏi “Vì sao chưa nên mua?”, “Hỗ trợ có phải đáy không?” hoặc “Lực mua/bán đang thế nào?”. Lịch sử cũng mở được tại **Chat AI**.
4. **Cơ hội hôm nay:** chọn tối đa 6 mã và bấm **Quét tín hiệu hôm nay**. Sau khi bắt đầu, kết quả tiếp tục cập nhật theo dữ liệu khi tự cập nhật đang bật.
5. **Thư viện sách:** tải PDF/TXT/MD để tra cứu, đối chiếu giải thích; chọn nguyên tắc đã kiểm tra để dùng bản tin tại **Tổng quan**.

Ghi các lần mua/bán đã thực hiện trong **Ghi giao dịch** để cập nhật danh mục. Không có sách thương mại hoặc vị thế giả nạp sẵn. [Tài liệu thử](examples/daily_rules.md) do dự án tự viết chỉ dùng kiểm tra chức năng.

## Các màn hình

| Mục | Công việc |
| --- | --- |
| Tổng quan | Bản tin theo sách, giá ngày tự tải và bản tin cũ |
| Bảng điện & biểu đồ | Chỉ số, bảng giá VN, nến/khối lượng, phân tích/chat theo mã; biểu đồ ngày VN/Mỹ riêng |
| Danh mục & giao dịch | Xem vị thế, ghi mua/bán, lọc lịch sử và xuất CSV |
| Tin tức | Tìm tiêu đề VN/Mỹ, xem nguồn/thời gian và mở báo gốc |
| Chat AI | Hỏi đáp, tìm/mở lại/đổi tên/xuất/xóa hội thoại |
| Thư viện sách | Nhập sách, tìm đoạn, chọn và kiểm tra nguyên tắc |

## Bảng điện, biểu đồ và phân tích

Mở **Bảng điện & biểu đồ → Bảng điện Việt Nam**. Phía trên là bốn chỉ số VN-Index, VN30, HNX-Index và UPCoM-Index với đường diễn biến từ nến thật. Bên dưới là bảng giá có trần/sàn/tham chiếu, ba mức mua/bán, khớp lệnh, tổng giao dịch, OHLC/giá bình quân và khối ngoại. Bố cục nhóm cột tham khảo [bảng giá DNSE](https://banggia.dnse.com.vn/v2).

Bảng theo dõi tối đa 30 mã do bạn chọn, hỗ trợ lọc sàn, tìm và sắp xếp. Mở **Tùy chọn bảng** để đổi nhịp tải, đầy đủ/rút gọn hoặc danh sách mã. Bộ lọc áp dụng danh sách này. Giá bảng theo nghìn VND, khối lượng là cổ phiếu, giá trị giao dịch theo triệu VND; chỉ số dùng điểm.

Sau khi chọn mã, khung bên trái hiện nến, SMA20, hỗ trợ/kháng cự, khối lượng và cung cầu ba mức. Khung bên phải gồm **Phân tích**, **Chat theo mã** và **Cơ hội hôm nay**. Mã đang xem được giữ khi thứ hạng bảng thay đổi.

Phân tích tính RSI14, xu hướng, vùng giá và khối lượng xác nhận từ nến đã đóng. Kết quả gồm theo dõi mua, rà soát bán với mã đang sở hữu, giữ quan sát hoặc chờ. Giá thấp hoặc RSI thấp chưa đủ để khẳng định đã chạm đáy. Mỗi kết quả nêu điều kiện, mốc mất hiệu lực và giờ dữ liệu; số điều kiện đạt không phải xác suất sinh lời. [Quy tắc phân tích](docs/TECHNICAL_ANALYSIS.md).

Chat nhận bối cảnh giá/phân tích tại lúc bạn gửi, truy xuất tối đa hai đoạn sách để giải thích và lưu lịch sử. Chế độ demo giải thích bằng quy tắc; model tùy chọn chỉ được gọi khi gửi câu hỏi. Bộ tín hiệu kỹ thuật chưa tự học toàn bộ sách thành chiến lược.

Các nhịp tải hoạt động khi trang đang mở:

| Dữ liệu | Nhịp mặc định |
| --- | --- |
| Snapshot bảng giá DNSE | 5 giây, chọn thêm 10/30 giây |
| Nến cổ phiếu | Cache 30 giây |
| Nến chỉ số | Cache 60 giây |
| Giá ngày VN/Mỹ | Cache 5 phút |

Có tạm dừng và cập nhật thủ công. Giờ nguồn tách giờ tải; dữ liệu cũ/thiếu chặn tín hiệu theo thời điểm, độ sâu cũ được ẩn. Đây là các snapshot tải định kỳ, chưa có luồng đẩy từng tick. [Bảng điện](docs/REALTIME.md) · [Nến và chỉ số](docs/INTRADAY.md).

Chọn **Biểu đồ VN / US** để xem dữ liệu ngày KBS (VN) và Yahoo (US); bản tin ở Tổng quan tiếp tục dùng luồng giá ngày và nguyên tắc sách riêng.

## Bản tin 07:30

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\daily-schedule.ps1 -Mode Install
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\daily-schedule.ps1 -Mode Status
```

Lịch chạy **07:30 giờ Việt Nam**, cần máy bật, tài khoản đăng nhập và kết nối mạng. App có thể đóng. Bản tin lưu trong ứng dụng, chưa gửi thông báo hoặc đặt lệnh. [Hướng dẫn hằng ngày](docs/DAILY_GUIDE.md).

Chạy ngay: `.\.venv\Scripts\python.exe -m breakout_ai.daily --refresh`.

## Phạm vi thực tế

- Sách được trích chữ và truy xuất theo đoạn/trang; chưa huấn luyện lại trọng số LLM.
- Bản tin theo sách và tín hiệu kỹ thuật trong phiên có quy tắc riêng, chưa có kết quả kiểm định hiệu quả đầu tư.
- Nguồn công khai có thể chậm hoặc gián đoạn; thiếu dữ liệu hiển thị dấu gạch, không tạo giá hay biểu đồ mẫu.
- Demo không cần key; có thể cấu hình OpenAI/Ollama để diễn giải tự nhiên.
- Nhật ký lưu giao dịch bạn đã thực hiện; chưa kết nối broker, không tự đặt lệnh.
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

Kiểm tra: `.\.venv\Scripts\python.exe -m pytest`. Nâng cấp giữ database đã có; không đổi hoặc xóa dữ liệu để đổi thương hiệu. Bản 0.8 sửa cách căn cột/panel theo DOM Streamlit; chưa xác minh ảnh chụp desktop/mobile vì Browser không khả dụng trong phiên.
