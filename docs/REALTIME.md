# Bảng giá trực tiếp — Breakout AI

Bảng điện Việt Nam lấy **snapshot thật từ DNSE**, tự yêu cầu bản mới mỗi 5 giây khi trang đang mở và chế độ cập nhật được bật. Đây là **polling snapshot**, chưa phải luồng WebSocket đẩy từng tick. Độ trễ từ sàn đến nguồn DNSE không được nguồn công khai cam kết; thời gian của dữ liệu luôn được hiển thị riêng với thời gian ứng dụng nhận phản hồi.

## Dữ liệu đang sử dụng

Adapter `breakout_ai/realtime.py` chỉ truy vấn endpoint công khai mà [bảng giá DNSE v2](https://banggia.dnse.com.vn/v2) sử dụng:

```text
POST https://api.dnse.com.vn/price-api/query
```

Một request GraphQL gộp danh sách tối đa 30 mã và hai nhóm dữ liệu:

- `GetKrxStockInfoBySymbols(symbols: [...], board: 2)`: giá tham chiếu/trần/sàn, giá và khối lượng khớp gần nhất, tổng khối lượng/giá trị, mở cửa/cao/thấp/trung bình, mua/bán nước ngoài, mã sàn và thời gian giao dịch.
- `GetTopPriceOfSymbols(symbolList: [...])`: ba mức giá/khối lượng chờ mua và chờ bán, kèm thời gian riêng của độ sâu thị trường.

Ứng dụng không gửi tài khoản, mật khẩu, cookie, API key hay lệnh giao dịch cho endpoint này. Không tự chuyển sang nguồn giá ngày hoặc tạo số liệu giả khi DNSE lỗi. Bảng chỉ hỗ trợ chứng khoán cơ sở Việt Nam trong lần nâng cấp này; biểu đồ VN/US tiếp tục sử dụng nguồn giá theo phiên riêng.

Các trường không có được hiển thị bằng dấu `—`. Không suy ra trần/sàn từ một tỷ lệ cố định; không lấy giá cuối nhân tổng khối lượng để giả thành tổng giá trị giao dịch.

## Đơn vị và ánh xạ

Các hệ số dưới đây được đối chiếu với mã hiển thị công khai của DNSE v2 và phản hồi thật ngày 19/10/2026. Chúng thuộc adapter snapshot của website, **không được áp dụng tự động cho API LightSpeed hoặc phái sinh**.

| Trường nguồn | Dữ liệu trong Python | Trình bày trên bảng điện |
| --- | --- | --- |
| Các giá: `referencePrice`, `matchPrice`, `bidPrice1`… | Nhân 1.000, đơn vị VND | Có thể chia 1.000, với nhãn “Giá ×1.000đ” |
| `matchQuantity`, `totalVolumeTraded`, khối lượng bid/ask và nước ngoài | Nhân 10, đơn vị cổ phiếu | Số cổ phiếu, không nhân/chia ngầm lần nữa |
| `grossTradeAmount` | Nhân 1.000.000.000, đơn vị VND | Có thể hiển thị tỷ đồng với nhãn rõ |
| `marketId` | 6 → HOSE; 7 → HNX; 8 → UPCOM | Tên sàn từ nguồn |
| `tradingTime` | UTC, thời điểm cập nhật giao dịch của mã | Chuyển sang giờ Việt Nam khi hiển thị |
| `time` trong top price | UTC, thời điểm của ba mức mua/bán | Theo dõi độ mới riêng với giá khớp |

Ví dụ một snapshot FPT có `averagePrice = 58.017`, `totalVolumeTraded = 143800` và `grossTradeAmount = 83.42787`: giá trung bình khoảng 58.017 đồng/cổ phiếu, khối lượng 1.438.000 cổ phiếu và giá trị 83,42787 tỷ đồng. Ví dụ là chứng cứ ánh xạ đơn vị, không phải giá hiện tại để giao dịch.

## Tình trạng dữ liệu

`source_timestamp` là thời gian giao dịch do nguồn gửi; `depth_timestamp` là thời gian sổ giá. `received_at` là thời gian nhận HTTP, không thay thế cho hai mốc nguồn.

- Giá hoặc độ sâu không có mốc thời gian, hoặc mốc cũ hơn 180 giây: đánh dấu cũ độc lập cho từng nhóm.
- Một mã ít giao dịch hoặc thị trường đóng cửa có thể có giá khớp cũ dù kết nối vẫn thành công. Nhãn cũ mô tả tuổi của dữ liệu, không khẳng định nguồn bị mất kết nối.
- HTTP lỗi, giới hạn tốc độ, timeout hoặc dữ liệu không hợp lệ: giữ snapshot đã lưu kèm lỗi và đánh dấu cũ; không đổi thời gian nguồn thành giờ hiện tại.
- Không có cache: để bảng trống cùng thông báo nguồn chưa sẵn sàng.
- Tạm dừng: đọc lại dữ liệu đã lưu, không gửi request. Nhãn thời gian tiếp tục cho biết dữ liệu đã nhận từ lúc nào.

Nhịp tự động được tính từ **lúc bắt đầu request**, không cộng thêm thời gian HTTP vào TTL. Ví dụ bắt đầu lúc 10:00:00, nhận lúc 10:00:00,7 thì nhịp 5 giây vẫn cho phép lần kế tiếp từ 10:00:05. Thời gian nhận và thời gian nguồn tiếp tục giữ đúng nghĩa riêng của chúng.

`board_poll_state` lưu lần thử theo workspace và tổ hợp mã trong SQLite, nên tạo lại service hoặc thao tác form không làm mất nhịp tải. Claim bằng giao dịch `BEGIN IMMEDIATE` được ghi trước khi gọi HTTP; hai instance cùng đọc một bảng không gửi hai request đồng thời. Claim có lease 30 giây để có thể phục hồi nếu process dừng giữa chừng. Request đã xong mới giải phóng claim; không giữ khóa ghi SQLite trong lúc chờ mạng. Nếu lease cũ hết hạn và instance mới đã nhận quyền tải, phản hồi về muộn của instance cũ bị loại; kết quả hiển thị lấy từ snapshot đã lưu của instance mới.

- Khi thành công: nhịp tự động tối thiểu là khoảng người dùng đã chọn (5/10/30 giây trên giao diện).
- Lỗi thường: giãn nhịp theo 10 → 20 → 30 giây giữa các lần bắt đầu thử, luôn ít nhất bằng khoảng đã chọn. Lỗi được lưu cả khi chưa từng tải thành công, tránh việc mỗi lần render lại đều gọi nguồn.
- HTTP 403/429: nghỉ ít nhất 30 giây từ lúc nhận lỗi; tôn trọng `Retry-After` dạng số giây hoặc HTTP date, tối đa 300 giây. Nút tải thủ công cũng chờ hết cooldown này và không tạo request trùng khi có request đang chạy.
- Nút tải thủ công có thể thử lại ngay với lỗi kết nối/HTTP 5xx thông thường. Tạm dừng chỉ đọc cache, gồm cả lỗi đã lưu, không làm một lần thử mới.
- Lỗi có dữ liệu cũ: giữ mốc nhận thành công trước đó, đánh dấu giá và độ sâu cũ. Lỗi chưa có dữ liệu: `fetched_at` vẫn là `None`; thời gian lưu nội bộ không được trình bày thành thời gian nhận dữ liệu.

Một request cho cả nhóm, tối đa 30 mã, timeout mặc định 5 giây, phản hồi tối đa 1 MB. Cache SQLite có phạm vi workspace, giữ tối đa 20 tổ hợp mã. Trạng thái polling giữ 40 tổ hợp gần nhất, cộng các claim/cooldown/nhịp chờ chưa hết hạn để không làm mất giới hạn đang có hiệu lực. Cache quá 7 ngày bị bỏ.

## Giao diện lập trình

```python
from breakout_ai.realtime import RealtimeService

reader = RealtimeService(store, poll_seconds=5)
snapshot = reader.fetch(["FPT", "VCB", "SSI"])

for quote in snapshot.quotes:
    print(quote.symbol, quote.last, quote.source_timestamp, quote.stale)
    print(quote.bids[0].price, quote.bids[0].volume)

# Khi người dùng tạm dừng; không gọi mạng:
paused = reader.cached(["FPT", "VCB", "SSI"])
```

`BoardSnapshot.mode` luôn là `polling`; `from_cache` cho biết phản hồi được dùng lại. `LiveQuote` dùng VND và cổ phiếu, các trường thiếu là `None`. Đây là module độc lập với `MarketService` và bộ gợi ý hàng ngày; bảng điện không tự thay đổi quy tắc mua/bán từ sách.

## Muốn nhận từng tick qua WebSocket

DNSE có dịch vụ Market Data API và SDK WebSocket chính thức. [Tài liệu xác thực](https://developers.dnse.com.vn/docs/guide/intro/authentication/) mô tả API key, API secret và chữ ký theo request; [SDK chính thức của DNSE](https://github.com/dnse-tech/openapi-sdk/tree/main/python) có ví dụ nhận `quote`, `trade`, `trade_extra`, `foreign_investor`, `market_index`. SDK dùng gateway `wss://ws-openapi.dnse.com.vn`.

Hiện dự án chưa có tài khoản/quyền Market Data của người dùng và chưa chạy client WebSocket xác thực. Không có nhãn “đã kết nối streaming” trong phiên bản polling. Để triển khai streaming cần quyền dữ liệu phù hợp, sau đó bổ sung worker kết nối một lần, subscription gộp, reconnect/backoff, xử lý thứ tự tick và snapshot đồng bộ sau reconnect. Khóa lưu phía server trong môi trường triển khai, không đưa vào chat hoặc mã nguồn công khai.

Endpoint snapshot website không có hợp đồng API ổn định hoặc giấy phép phân phối kèm phản hồi HTTP. Bản tích hợp hiện phù hợp thử nghiệm cá nhân. Trước khi bán dịch vụ dữ liệu/bảng giá cho khách hàng, cần thỏa thuận quyền sử dụng và phân phối với DNSE; [điều khoản LightSpeed](https://hdsd.dnse.com.vn/die-u-khoa-n-di-ch-vu-dnse/dieu-khoan-san-pham-dich-vu/dieu-khoan-san-pham-lightspeed-api) cũng quy định việc cung cấp dữ liệu cho bên thứ ba phải được chấp thuận.

## Xác minh

`tests/test_realtime.py` dùng phản hồi tự tạo để kiểm tra đơn vị, mã/sàn, giá thiếu và bất thường, thời gian giá/độ sâu độc lập, cache theo workspace, lỗi nguồn, giới hạn phản hồi và schema GraphQL không hợp lệ. Các ca riêng xác minh HTTP chậm không làm nhân đôi chu kỳ, trạng thái lỗi tồn tại qua instance mới, nhịp 30 giây, backoff, nút thử lại, Retry-After, claim đồng thời, giới hạn trạng thái cũ và đọc lỗi khi tạm dừng. Không gọi mạng trong bộ kiểm thử.

Tài liệu nguồn chính thức tham khảo thêm: [Dữ liệu thị trường](https://developers.dnse.com.vn/docs/dnse/market-data/), [Khớp lệnh gần nhất](https://developers.dnse.com.vn/docs/dnse/get-latest-trades/), [Bid/ask gần nhất](https://developers.dnse.com.vn/docs/dnse/get-latest-quotes/), [Trần/sàn/tham chiếu](https://developers.dnse.com.vn/docs/dnse/get-symbol-secdef/).
