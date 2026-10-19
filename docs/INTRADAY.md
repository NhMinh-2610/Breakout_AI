# Nến trong phiên và biểu đồ chỉ số

Cập nhật: 19/10/2026.

## Nguồn dữ liệu đã kiểm tra

Dịch vụ dùng dữ liệu đọc công khai của DNSE, không yêu cầu đăng nhập và không gửi lệnh giao dịch.

| Dữ liệu | Endpoint | Mã đã kiểm tra |
| --- | --- | --- |
| Nến cổ phiếu | https://api.dnse.com.vn/chart-api/v2/ohlcs | VIC |
| Nến chỉ số | https://api.dnse.com.vn/chart-api/v2/ohlcs/index | VNINDEX, VN30, HNX, UPCOM |
| Danh sách chỉ số của nguồn | https://api.dnse.com.vn/chart-api/symbols?type=index | Dùng để xác minh tên mã |

Các đường dẫn được đối chiếu với client công khai của [bảng giá DNSE](https://banggia.dnse.com.vn/v2) và kiểm tra HTTP thực tế. Tài liệu [OHLC chính thức của DNSE OpenAPI](https://developers.dnse.com.vn/docs/dnse/get-ohlc-history/) mô tả một API có xác thực riêng; ứng dụng chưa thay thế luồng công khai bằng dịch vụ OpenAPI đó.

Endpoint công khai chưa đồng nghĩa với quyền phân phối dữ liệu thương mại. Cần xác nhận quyền dữ liệu trước khi bán dịch vụ sử dụng lại nguồn này.

## Cách tải và đơn vị

Mỗi lần tải chỉ yêu cầu một mã, một khung nến và cửa sổ 7 ngày lịch. Khung hỗ trợ là 1, 5 và 15 phút; mặc định 5 phút.

- Thời gian nguồn là Unix giây, được lưu thành ISO 8601 UTC có múi giờ. Giao diện đổi sang giờ Việt Nam.
- Giá cổ phiếu của endpoint nến ở đơn vị nghìn đồng: ứng dụng nhân 1.000 để lưu VND.
- Khối lượng nến cổ phiếu đã là số cổ phiếu, giữ nguyên. Không áp dụng hệ số 10 của bảng snapshot GraphQL.
- Giá chỉ số đã là điểm. Các mã trong SUPPORTED_INDICES đi qua endpoint /index, giữ nguyên điểm, trả price_unit=points và asset_type=index.
- Nến cổ phiếu trả price_unit=VND và asset_type=equity. Không đưa nến chỉ số vào phân tích mua/bán cổ phiếu.
- Không suy diễn khối lượng mua/bán chủ động từ khối lượng nến. Nếu nguồn thiếu khối lượng thì volume=None, không điền bằng 0.
- Không nội suy nến, lấp thời gian nghỉ trưa, tạo ngày giao dịch hay tạo mức giá thiếu.

Đợt kiểm tra live ngày 19/10/2026 lấy được 230 nến VIC, 230 nến VNINDEX/VN30, 245 nến HNX và 270 nến UPCOM trong cùng cửa sổ 7 ngày. Tại thời điểm kiểm tra ngoài giờ giao dịch, các snapshot có stale=True dù HTTP tải thành công. Kết quả này là dấu thời gian kiểm tra nguồn, không phải cam kết độ trễ của nhà cung cấp.

## Hợp đồng Python

IntradayService nhận Store tùy chọn để lưu SQLite theo workspace. Các phương thức:

- fetch(symbol, resolution="5", force=False): tải có cache và giới hạn nhịp.
- cached(symbol, resolution="5"): chỉ đọc dữ liệu đã lưu, không gọi HTTP; dùng khi tạm dừng.
- IntradaySnapshot: symbol, resolution, candles, source_url, fetched_at, stale, errors, from_cache, source, price_unit và asset_type.
- Candle: time, open, high, low, close, volume, interval_minutes và complete.

time là thời điểm bắt đầu nến. complete chỉ đúng khi thời điểm bắt đầu cộng độ dài khung đã qua theo đồng hồ hiện tại. Trạng thái này được tính lại khi đọc cache; việc đó không thay đổi giá hay khối lượng của nến. Dữ liệu của nến vừa kết thúc vẫn có thể được nhà cung cấp cập nhật sau đó.

Phân tích kỹ thuật phải loại complete=False và kiểm tra mốc thời gian riêng trước khi phát tín hiệu. Biểu đồ có thể hiển thị nến đang hình thành với nhãn phù hợp.

## Cache và lỗi nguồn

Cache mặc định 30 giây, có thể chọn 30–300 giây. Các thẻ chỉ số có thể dùng 60 giây. Cache phân biệt workspace, mã và khung nến; không dùng cache cổ phiếu cho chỉ số.

Mỗi yêu cầu có timeout tối đa 8 giây, giới hạn phản hồi 1 MB và tối đa 2.000 nến. Dịch vụ kiểm tra số hữu hạn, quan hệ OHLC, độ dài các mảng, thời gian trùng và nến tương lai. Yêu cầu không hợp lệ bị chặn trước khi gọi mạng.

Trạng thái yêu cầu được lưu để nhiều instance không tải trùng cùng một mã/khung. Yêu cầu lỗi được nghỉ ít nhất một chu kỳ cache. HTTP 403/429 áp dụng thời gian nghỉ 30–300 giây theo Retry-After; nút tải thủ công cũng tôn trọng thời gian nghỉ này.

Nếu tải thất bại, ứng dụng giữ dữ liệu cũ, mốc tải gốc và thông báo lỗi. Không đổi fetched_at thành giờ hiện tại để làm mới dữ liệu cũ. Snapshot được đánh dấu cũ khi cache quá hạn hoặc nến mới nhất quá cũ so với khung thời gian. Ngoài giờ giao dịch, cần hiển thị mốc phiên gần nhất; không mô tả dữ liệu đó là giá đang chạy.

Đây là snapshot OHLCV được tải định kỳ, không phải luồng đẩy tick qua WebSocket. Giá và nến trên hai endpoint có thể được cập nhật khác thời điểm; không sửa nguồn để chúng trùng nhau.

## Kiểm thử

tests/test_intraday.py dùng httpx.MockTransport, không cần mạng. Các trường hợp bao gồm quy đổi đơn vị riêng cho cổ phiếu/chỉ số, khung nến và nến chưa hoàn tất, volume thiếu, dữ liệu bất hợp lệ, giới hạn tải, cache theo workspace, dữ liệu nguồn cũ, lỗi HTTP, thời gian nghỉ và chống tải trùng giữa nhiều instance.

Trên máy bị khóa thư mục tạm hệ thống, chạy pytest với một thư mục --basetemp mới bên trong .artifacts và -p no:cacheprovider. Không ghi kết quả smoke live vào thư mục dữ liệu người dùng; artifact kiểm tra nằm trong .artifacts đã được bỏ qua bởi Git.
