# Kiến trúc Breakout AI 0.9

Ứng dụng xoay quanh một bối cảnh quan sát biểu đồ dùng chung cho panel, quét cơ hội và chat. SQLite giữ dữ liệu theo workspace; giao diện không tự tính một bộ tín hiệu khác.

## Luồng chính

**Quote + OHLCV → kiểm tra dữ liệu → technical → observation → hiển thị / copilot → kiểm tra phản hồi → lưu nhận định.**

`technical` tính RSI14 Wilder, SMA20, vùng hỗ trợ/kháng cự và khối lượng xác nhận từ nến đã đóng. `observation.observe_chart` kiểm tra thêm mã, khung và đơn vị; tạo báo cáo, tối đa 60 nến đóng, facts và scenarios có ID. Đầu ra được sao chép an toàn trước khi gửi hoặc lưu.

`MarketCopilot` nhận đúng bối cảnh này. Model chỉ trả bốn trường JSON chọn action/bằng chứng/kịch bản. `interpretation` kiểm tra action, ID và blocker rồi dựng văn bản chuẩn từ nguồn. Phản hồi ngoài hợp đồng giữ nhận định theo quy tắc.

## Ranh giới module

| Module | Trách nhiệm |
| --- | --- |
| `app.py` | Điều hướng và các công cụ hỗ trợ hiện có |
| `market_page` | Trang phân tích chính; chế độ bảng điện và giá ngày |
| `ui_common` | Helper giao diện/biểu đồ ngày dùng chung |
| `realtime`, `intraday` | Quote/nến, chuẩn hóa đơn vị, cache và điều phối HTTP |
| `technical` | Chỉ báo, điều kiện, freshness và kiểm tra sở hữu |
| `observation` | Bối cảnh biểu đồ thống nhất, facts/scenarios và provenance |
| `copilot`, `interpretation` | Yêu cầu diễn giải model và kiểm tra đầu ra |
| `workbench`, `market_visuals` | Panel biểu đồ/nhận định/chat và hình biểu diễn dữ liệu |
| `storage`, `portfolio` | Hội thoại/quota, vị thế và sổ giao dịch |
| `books`, `knowledge` | Trích chữ, truy xuất theo đoạn và nguồn kiến thức |
| `book_rules`, `daily` | Bản tin theo sách, tách khỏi luồng nến trong phiên |
| `market`, `market_view`, `research` | Dữ liệu ngày VN/US và luồng hỏi đáp cũ |
| `news`, `schedule` | Tin tức và lịch bản tin |

Việc tách trang thị trường và helper khỏi `app.py` làm rõ ranh giới UI/nghiệp vụ. Đợt làm sạch CSS loại khai báo đã bị ghi đè; không được xem là QA hình ảnh.

## Tải dữ liệu

Trang chính chỉ lấy quote và nến của mã đang chọn. Bảng điện và bốn chỉ số chỉ tải khi mở chế độ tương ứng; scanner tối đa 6 mã sau thao tác bắt đầu.

| Luồng | Nhịp / phạm vi |
| --- | --- |
| Quote phân tích chính | Mặc định 5 giây, một mã |
| Bảng điện VN | 5/10/30 giây, tối đa 30 mã mỗi batch |
| Nến cổ phiếu | Cache 30 giây, khung 1/5/15 phút |
| Nến chỉ số | Cache 60 giây, đơn vị điểm |
| Giá ngày VN/US | Cache và fragment 5 phút |

Fragment thức không đồng nghĩa mọi nguồn đều được tải lại. Tạm dừng chỉ đọc cache; model không chạy theo chu kỳ. Giá cổ phiếu nội bộ là VND đầy đủ, volume là số cổ phiếu. Index giữ điểm. [Nguồn nến](INTRADAY.md) · [Snapshot](REALTIME.md).

## Tính nhất quán của dữ liệu

Claim SQLite được ghi trước HTTP và giải phóng sau phản hồi; không giữ transaction ghi trong lúc chờ mạng. 403/429 có cooldown được lưu theo khóa dữ liệu.

Sau lỗi tải, snapshot lỗi/cũ được giữ cả khi chưa có nến; cache/rerun/instance mới không nâng nó thành dữ liệu mới. Chỉ phản hồi thành công mới xóa trạng thái lỗi. `fetched_at` vẫn chỉ mốc nhận dữ liệu thành công, không bị thay bằng lúc thử lại.

Một phản hồi về muộn đã mất quyền claim không được hiện lại hoặc ghi đè dữ liệu mới. Dịch vụ trả snapshot của chủ mới, hoặc chờ nếu chưa có. Giờ nhận, giờ giao dịch và thời gian nến giữ riêng.

## Lưu nhận định

Một lượt lưu gồm văn bản, nguồn, quote/report, `chart_context` và `interpretation`. `chart_context` chứa nến/facts/scenarios tại lúc gửi; polling sau đó không sửa lịch sử. `interpretation.mode` phân biệt rules/model và `validated` ghi kết quả kiểm tra hợp đồng.

Schema chính v4 và dữ liệu hiện có được giữ. Adapter tạo bảng cache riêng khi cần. Sách vẫn là truy xuất theo đoạn; chưa fine-tune model. Bản tin, giao dịch và tin tức có luồng nghiệp vụ riêng.

[Hợp đồng observer](CHART_OBSERVER.md) · [Quy tắc kỹ thuật](TECHNICAL_ANALYSIS.md) · [Kiểm thử](TESTING.md).
