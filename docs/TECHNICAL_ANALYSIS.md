# Phân tích kỹ thuật trong phiên

Breakout AI tạo **kịch bản theo dõi mua/bán** từ nến trong phiên và snapshot khớp lệnh mới. Bộ quy tắc hiện tại chạy bằng Python trong [technical.py](../breakout_ai/technical.py), không dự báo chắc chắn giá tăng, không gán xác suất thắng và không gửi lệnh giao dịch.

## Dữ liệu và thời gian

- Giá đầu vào là VND; khối lượng là số cổ phiếu.
- Nến có `time` là giờ bắt đầu kèm múi giờ, OHLC, volume, `interval_minutes` và `complete`. Hỗ trợ nến 1, 5, 15 phút.
- Cần tối thiểu 30 nến đã đóng. Nến chưa đủ thời gian hoặc bị nguồn đánh dấu chưa đóng được loại khỏi chỉ báo và xác nhận.
- Snapshot cần đúng mã, có giá khớp, giờ nguồn không quá 180 giây, và không bị đánh dấu cũ. Giờ nhận HTTP không thay thế giờ giao dịch.
- Nến đóng gần nhất phải thuộc ngày Việt Nam hiện tại; tuổi tính từ giờ đóng không quá hai chu kỳ nến cộng 30 giây. Hết phiên, nghỉ trưa hoặc mất dữ liệu có thể chuyển về **chờ dữ liệu mới**.
- Nến lỗi, trùng thời gian, sai khung hoặc thời gian tương lai chặn mọi tín hiệu mua/bán. Khối lượng thiếu hoặc bình quân bằng 0 không được tự điền thành dữ liệu xác nhận.
- Lớp giao diện [workbench.py](../breakout_ai/workbench.py) còn chặn tín hiệu khi snapshot nến bị đánh dấu cũ hoặc lần tải nguồn lỗi, kể cả nến cache vẫn còn trong giới hạn thời gian. Biểu đồ và mốc giá được giữ để xem lại.

Các chỉ báo là **14/20 nến của khung đang xem**, ví dụ RSI14 nến 5 phút; không phải RSI14 ngày.

## Chỉ báo và mức giá

| Mục | Cách tính |
| --- | --- |
| RSI14 | Tính chênh lệch đóng cửa; trung bình tăng/giảm đầu tiên trên 14 biến động, sau đó làm mượt Wilder `(trung_bình_trước × 13 + biến_động_mới) / 14`. RSI = `100 − 100 / (1 + tăng_tb / giảm_tb)`. |
| Trường hợp biên RSI | Chỉ tăng: 100; chỉ giảm: 0; hoàn toàn đi ngang: quy ước 50. Thiếu dữ liệu: không có giá trị. |
| SMA20 | Trung bình đóng cửa 20 nến đã đóng gần nhất, gồm nến đang đánh giá. |
| Hỗ trợ / kháng cự | Thấp nhất / cao nhất của **20 nến trước**; loại nến xác nhận để tránh tự tạo mức so sánh. Đây là vùng quan sát của ứng dụng, không phải đáy/đỉnh đã được chứng minh. |
| Khối lượng tương đối | Khối lượng nến xác nhận / trung bình khối lượng **20 nến trước**. Không dùng tổng khối lượng cả ngày để so với một nến 5 phút. |
| Dư mua / dư bán | Tổng khối lượng tại ba mức giá mới trên mỗi phía. Tỷ trọng mua = dư mua / (dư mua + dư bán). Đây là lệnh chờ có thể sửa/hủy, không phải dòng tiền đã khớp. |

RSI làm mượt phụ thuộc độ dài chuỗi ban đầu. 30 nến đáp ứng ngưỡng tối thiểu của sản phẩm nhưng có thể khác nền tảng dùng hàng trăm nến khởi tạo. Phương pháp RSI tham khảo [StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-strength-index-rsi); SMA tham khảo [Fidelity](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/sma).

## Điều kiện tạo kịch bản

Các ngưỡng dưới đây là lựa chọn minh bạch của ứng dụng, **chưa có kết quả backtest chứng minh hiệu quả**. Cần đồng thời thỏa tất cả điều kiện trong một hàng và mọi kiểm tra độ mới.

| Kịch bản | Điều kiện |
| --- | --- |
| Theo dõi mua: vượt kháng cự | Nến đóng vượt đỉnh 20 nến trước; khối lượng ≥1,5 lần; đóng trên SMA20; giá khớp snapshot vẫn trên kháng cự. |
| Theo dõi mua: hồi quanh hỗ trợ | Đáy nến trong vùng hỗ trợ ±2%, đóng cửa từ hỗ trợ đến +2%; RSI từ ≤30 vượt lên >30; nến tăng; khối lượng ≥1,2 lần; giá snapshot vẫn từ hỗ trợ đến +2%. |
| Rà soát bán: thủng hỗ trợ | **Chỉ với mã đang sở hữu**: nến đóng dưới hỗ trợ; khối lượng ≥1,5 lần; đóng dưới SMA20; snapshot vẫn dưới hỗ trợ. |
| Rà soát bán: mất động lượng | **Chỉ với mã đang sở hữu**: RSI từ ≥70 xuống <70; đóng dưới SMA20 đang giảm; khối lượng ≥1,2 lần; snapshot vẫn dưới SMA20. |

RSI dưới 30 **không đủ để mua**; mức quá bán có thể kéo dài. RSI trên 70 không tự tạo yêu cầu bán. Những hạn chế này phù hợp với [hướng dẫn RSI của Fidelity](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/RSI). Hỗ trợ/kháng cự có tính diễn giải và có thể bị phá vỡ; tham khảo [Fidelity về hỗ trợ và kháng cự](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/support-and-resistance?print=true).

Nếu mã đang sở hữu đồng thời có nhiều mẫu phù hợp, kịch bản rà soát bán được ưu tiên hiển thị. Khi dữ liệu đủ mới nhưng chưa có mẫu hoàn chỉnh, kết quả là `hold` với mã đang sở hữu hoặc `wait` với mã khác. `hold` nghĩa là tiếp tục quan sát, không xét giá vốn, tỷ trọng hay khả năng chịu rủi ro của chủ tài khoản.

## Đọc kết quả

`SignalReport` gồm:

- `action`: `watch_buy`, `watch_sell`, `hold` hoặc `wait`.
- `evidence`: lý do có số liệu, khung nến và dữ liệu sổ lệnh nếu còn mới.
- `condition_checks` và `signal_strength`: ví dụ **4/4 điều kiện quan sát**. Đây là số quy tắc được đáp ứng; không phải xác suất thành công.
- `blockers`: nguyên nhân dữ liệu chưa đủ điều kiện. Có blocker thì luôn `wait`, dù một mẫu lịch sử đã đủ số điều kiện.
- `levels`: hỗ trợ, kháng cự và mốc làm mất hiệu lực kịch bản. Mốc này không phải lệnh cắt lỗ tự động, giá khớp dự kiến hoặc mức lỗ tối đa.
- `as_of`: giờ **đóng** nến cuối được phân tích; `indicators.quote_timestamp` giữ giờ giao dịch của snapshot riêng.

Mốc mất hiệu lực quan sát: vượt kháng cự dùng kháng cự cũ; hồi hỗ trợ dùng `hỗ_trợ × 0,98`; thủng hỗ trợ dùng hỗ trợ cũ; mất động lượng dùng SMA20. Các mức không tính phí, thanh khoản, bước giá hoặc khả năng thực thi lệnh.

Ví dụ API:

```python
from breakout_ai.technical import analyze

report = analyze(
    "VIC",
    intraday_snapshot.candles,
    live_quote,
    owned=False,
    resolution_minutes=5,
)
print(report.action, report.summary, report.blockers)
```

Kịch bản không khẳng định “VIC đã chạm đáy và sẽ tăng”. Kết quả có thể là chờ xác nhận, kèm vùng hỗ trợ và điều kiện khối lượng còn thiếu. Kiến thức từ sách được truy xuất riêng; nội dung sách không sửa số liệu thị trường hay biến quy tắc trên thành mô hình đã học hoặc đã kiểm định.

Kiểm thử giao diện và lưu ngữ cảnh: [tests/test_workbench_ui.py](../tests/test_workbench_ui.py).

Kiểm thử phép tính: [tests/test_technical.py](../tests/test_technical.py) kiểm tra công thức RSI, loại nến đang chạy, loại nến xác nhận khỏi mốc/khối lượng nền, giới hạn độ mới, dữ liệu lỗi, khối lượng thiếu, điều kiện bán theo sở hữu và sổ lệnh không tự tạo tín hiệu.
