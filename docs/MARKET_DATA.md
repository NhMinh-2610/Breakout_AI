# Dữ liệu thị trường Breakout AI

## Nguồn giá và đơn vị

| Thị trường | Adapter mặc định | Dữ liệu đang lấy | Tiền tệ |
| --- | --- | --- | --- |
| Việt Nam | KBS public daily endpoint | Khoảng 230 ngày lịch của giá ngày và khối lượng | VND đầy đủ |
| Mỹ | Yahoo chart endpoint | Khoảng 6 tháng giá ngày, khối lượng và adjusted close khi có | USD |
| VN/US | Gateway tùy chọn | Schema chuẩn do nguồn của người vận hành trả về | VN/VND hoặc US/USD |

KBS wire format đã được đối chiếu với [adapter công khai của vnstock](https://github.com/thinh-vu/vnstock/blob/main/vnstock/explorer/kbs/quote.py) và thử trên endpoint thật. Ứng dụng viết adapter riêng, không cài vnstock và không gọi đặt lệnh. Nguồn raw KBS trả giá cổ phiếu bằng VND; thư viện cộng đồng có thể chuẩn hóa sang nghìn đồng, nhưng Breakout AI giữ **VND đầy đủ**.

Yahoo là nguồn phát triển cho nghiên cứu cá nhân. [Dự án yfinance](https://github.com/ranaroussi/yfinance) mô tả API công khai là dành cho personal use; chưa có xác nhận quyền phân phối thương mại. Breakout AI gọi chart HTTP trực tiếp, không cài yfinance. Việc gọi trực tiếp không thay đổi quyền sử dụng dữ liệu.

Nguồn KBS công khai cũng chưa được xác nhận quyền redisplay thương mại trong dự án. Khi chuẩn bị bán, thay bằng nguồn được cấp quyền qua adapter phù hợp/gateway. Đây là giới hạn của các nguồn đã chọn, không phải chứng nhận rằng chỉ cần một API key là đủ quyền bán lại dữ liệu.

## Cách dùng

Trong chat:

```text
Giá VN:FPT gần nhất?
Phân tích US:AAPL.
Gợi ý các mã đáng cân nhắc mua: VN:FPT, VN:VCB, VN:VNM.
So sánh US:AAPL và US:MSFT theo tiêu chí xu hướng.
```

Trong Breakout AI 0.6, mở **Tổng quan → Gợi ý hôm nay** để đọc bản tin từ sách; chỉnh danh mục và danh sách tìm mua trong **Danh mục & giao dịch**. Biểu đồ và bảng phiên nằm tại **Bảng giá & biểu đồ**. Bản tin chia batch tối đa 6 mã/lần mặc định, tối đa 3 request đồng thời; không quét toàn bộ sàn. Hỏi đáp có luồng xếp hạng kỹ thuật riêng khi được hỏi, với universe mặc định nhỏ nếu không nêu mã; điểm đó chưa phải nguyên tắc học từ sách.

`VN:MÃ` và `US:MÃ` xác định thị trường rõ. Mã không có prefix dùng thị trường đơn đang chọn; với BOTH chỉ suy ra các mã phổ biến đã biết, còn mã không rõ sẽ yêu cầu prefix. Prefix có thể chỉ rõ thị trường khác bộ lọc kiến thức.

## Điều dữ liệu này cho biết

`close` là giá trong bar ngày gần nhất nhận được; với chat bar cuối có thể thuộc phiên chưa hoàn tất. Bản tin có bộ lọc riêng: VN chỉ dùng ngày trước ngày Việt Nam hiện tại, US chỉ nhận bar cùng ngày UTC từ 22:00 UTC. Đây là mốc bảo thủ, chưa phải xác nhận calendar từng phiên. `as_of` là ngày bar dùng; `fetched_at` là lúc tải bằng UTC, hai thời điểm có ý nghĩa khác nhau.

Mốc US được chọn sau giờ core session thông thường 09:30–16:00 ET theo [NYSE](https://www.nyse.com/markets/hours-calendars) và [Nasdaq](https://www.nasdaq.com/market-activity/stock-market-holiday-schedule), có khoảng đệm cho chênh lệch DST. Đây là quyết định triển khai của Breakout AI; nguồn feed và lịch phiên đặc biệt vẫn cần xác minh riêng.

Chưa có quote realtime, bid/ask, order book, EPS/P/E/P/B/ROE hoặc BCTC được lấy từ feed giá này. App không suy ra chỉ số thiếu từ giá. Biểu đồ dùng chuỗi adjusted khi nguồn xác nhận và đầy đủ; nếu thiếu, toàn chuỗi dùng close gốc. Giá headline dùng close gốc và ghi rõ cơ sở chuỗi. Tin tức RSS có adapter riêng, chưa tham gia điều kiện mua/bán của sách. Nguồn chưa xác minh điều chỉnh quyền được ghi rõ giới hạn.

## Cache và lỗi

Cache SQLite theo workspace + provider + market + symbol, TTL mặc định 300 giây. Chat và bảng giá tái sử dụng cache còn hạn; trong một batch, chỉ mã chưa có dữ liệu hoặc cache hết hạn cần gọi mạng. Nút làm mới chủ động có thể bỏ qua TTL. Mỗi lần tạo lại bản tin yêu cầu tải từ nguồn; mở lại bản tin cùng ngày/cùng đầu vào dùng báo cáo đã lưu, nút cập nhật yêu cầu tải lại.

Nếu cập nhật thất bại nhưng có cache, kết quả mang `cache_stale=true` và hiển thị bản lưu cũ. Kết quả đó **không được xếp hạng**. Nếu không có cache, trả lỗi thay vì tạo giá. Thay provider không tự chuyển sang provider khác khi lỗi.

Batch chuẩn hóa mã trước khi loại trùng (`aapl`, ` AAPL ` → `AAPL`), áp giới hạn tối đa 6 mã và tải tối đa 3 mã đồng thời. Cả batch dùng chung một HTTPX client với pool tối đa 3 kết nối để tái sử dụng TCP/TLS theo [cơ chế connection pooling của HTTPX](https://www.python-httpx.org/advanced/clients/); client được đóng sau khi hoàn tất. Không có vòng lặp retry tự động khi nhà cung cấp giới hạn truy cập hoặc trả lỗi. Kết quả giữ thứ tự mã đầu vào và giữ cả các mã thành công nếu một mã khác lỗi.

Đổi URL gateway nhưng giữ cùng provider có thể còn cache của gateway cũ trong TTL. Dùng nút cập nhật từ nguồn hoặc chờ hết TTL khi đổi cấu hình nguồn.

## Tiêu chí xếp hạng trong chat, độc lập với bản tin sách

Đây là heuristic kỹ thuật kiểm tra được, không phải mô hình học từ dữ liệu lợi nhuận tương lai. Mỗi điều kiện đạt cộng 20 điểm:

1. Giá phân tích lớn hơn SMA20.
2. Giá phân tích lớn hơn SMA60.
3. Lợi suất giá 60 phiên lớn hơn 0.
4. Biến động 20 phiên năm hóa không vượt ngưỡng, mặc định 35%.
5. Sụt giảm tối đa trong cửa sổ 60 phiên không vượt ngưỡng, mặc định 15%.

Biến động dùng độ lệch chuẩn mẫu của log return 20 phiên nhân căn 252. Sụt giảm đo từ đỉnh tích lũy trong cửa sổ, không phải dự báo sụt giảm tương lai. Cần ít nhất 61 bar; giá cũ quá 7 ngày lịch, cache lỗi hoặc khối lượng cuối không dương bị loại. Bản text nhóm riêng theo thị trường và ngày dữ liệu để tránh leaderboard trộn bối cảnh.

Điểm 100 chỉ nghĩa đạt 5 điều kiện. Ngưỡng ưu tiên domain mặc định là 80/100; UI hiện tại không đưa công cụ chỉnh score vào luồng chính. Có thể không có mã nào đạt ngưỡng. Chưa có backtest, kiểm định out-of-sample, đánh giá EPS, dòng tiền, định giá, ngành, tin tức, thanh khoản theo giá trị tiền hoặc mức phù hợp với tài chính cá nhân. Nguồn chưa xác minh điều chỉnh quyền được gắn rủi ro. LLM có thể diễn giải ứng viên có điều kiện từ dữ liệu này, nhưng không được tạo thêm dữ kiện doanh nghiệp.

## Cấu hình

```dotenv
MARKET_DATA_ENABLED=true
VN_MARKET_PROVIDER=kbs
US_MARKET_PROVIDER=yahoo
MARKET_TIMEOUT_SECONDS=15
MARKET_CACHE_SECONDS=300
MARKET_MAX_SYMBOLS=6
```

Không cần API key với hai nguồn phát triển. Cấu hình `LLM_PROVIDER` độc lập: giá và phép tính dùng được cả khi model vẫn là demo.

## Gateway cho nguồn dữ liệu của bạn

Đặt VN/US provider thành `gateway`, `MARKET_GATEWAY_URL` là URL server tin cậy, và token trong `.env`. App gửi GET với query `market=VN&symbol=FPT`, bearer token chỉ gửi tới URL do người vận hành cấu hình. Trả JSON:

```json
{
  "market": "VN",
  "symbol": "FPT",
  "currency": "VND",
  "source_url": "https://your-data-provider.example/history/FPT",
  "price_basis": "provider-adjustment-unknown",
  "bars": [
    {"date": "2026-10-01", "close": 100000, "volume": 1000},
    {"date": "2026-10-02", "close": 101000, "volume": 1200}
  ]
}
```

Ví dụ JSON là giả định. Cần 2–400 bar có ngày duy nhất; để xếp hạng cần 61. `adjusted_close` là trường tùy chọn mỗi bar; `price_basis` nhận `adjusted-by-provider`, `unadjusted` hoặc `provider-adjustment-unknown`. Giá trị hữu hạn, giá dương, khối lượng không âm. `source_url` HTTPS để người dùng đối chiếu. Gateway chỉ là hợp đồng tích hợp, chưa có nhà cung cấp thương mại được kết nối và xác nhận quyền.

## Kiểm tra kết nối thật

```powershell
.\.venv\Scripts\python.exe -m breakout_ai.verify_data
```

Lệnh này chủ động gọi mạng, lưu cache và ghi báo cáo provenance tại `.artifacts/market_check.json`. Không gọi LLM, không đặt lệnh và không tải sách. Test pytest thông thường vẫn dùng HTTP giả lập.

## Đọc thông tin trên giao diện

Dải giá Tổng quan tự tải mã chưa có giá hoặc cache hết hạn, kiểm tra lại mỗi 5 phút khi trang mở. Nút Cập nhật giá theo dõi lấy lại nhóm mã và làm mới biểu đồ. Request cùng batch dùng chung pool tối đa ba kết nối. Lỗi tải có cooldown theo TTL (tối thiểu 30 giây), cập nhật thủ công vẫn được thử ngay. Giá cũ giữ nhãn riêng; không có giá thì hiện dấu gạch. Không dựng chỉ số thị trường hoặc bảng lệnh giả. Đường giá màu xanh dương và MA20 màu vàng dùng chung nền tối; biến động giá chưa phải hiệu suất danh mục.

[Bản đồ tài liệu](README.md) · [Bản tin](DAILY_GUIDE.md) · [UI/UX](UI_UX.md).

Kiểm tra API thật ngày 19/10/2026: FPT, VCB, VNM qua KBS; AAPL, MSFT, GOOGL qua Yahoo. Cả sáu thành công, không lỗi hoặc cache stale. Phiên VN trả về 19/10 có thể chưa đóng; US gần nhất 16/10. Báo cáo local tại .artifacts/market-api-ui-check.json, không đưa vào Git. Đây là trạng thái lần kiểm tra, không chứng minh feed có SLA/realtime hoặc quyền redisplay thương mại.
