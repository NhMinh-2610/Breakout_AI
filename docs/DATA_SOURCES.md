# Nguồn kiến thức và chất lượng nội dung Breakout AI

Bộ ghi chú nền đã được rà soát ngày 17/10/2026; lần đổi thương hiệu không cập nhật lại ngày kiểm chứng nội dung. Kho kiến thức mặc định là ghi chú giáo dục và ví dụ tự tạo, không phải dữ liệu giá. Dữ liệu thật được lấy riêng qua adapter; sách do người dùng nhập được lưu riêng trong thư viện.

| Nguồn | Dùng cho | Giới hạn |
| --- | --- | --- |
| [Investor.gov — Stocks](https://www.investor.gov/introduction-investing/investing-basics/investment-products/stocks) | K01: quyền sở hữu, cổ tức, biến động giá | Nội dung giáo dục của Mỹ; các quyền cụ thể tùy cổ phần và thị trường |
| [Investor.gov — P/E](https://www.investor.gov/introduction-investing/investing-basics/glossary/price-earnings-pe-ratio) | K02: quan hệ giá/EPS | Không cho biết P/E hiện tại của một mã |
| [FINRA — Defining Value](https://syndication.finra.org/content/defining-value-investment) | K03: công thức P/B và bối cảnh giá trị sổ sách | Không cho biết giá trị hợp lý của một cổ phiếu cụ thể |
| [SEC — Financial statements](https://www.sec.gov/about/reports-publications/beginners-guide-financial-statements) | K04: cách đọc báo cáo | Ghi chú nền, không phải chuẩn mực kế toán đầy đủ |
| [Investor.gov — Diversification](https://www.investor.gov/introduction-investing/getting-started/asset-allocation) | K05: đa dạng hóa | Không thiết kế danh mục cá nhân |
| [Investor.gov — ETF](https://www.investor.gov/introduction-investing/investing-basics/investment-products/mutual-funds-and-exchange-traded-2) | K06: khái niệm ETF | Không chứa danh mục hoặc mức phí mới nhất của quỹ cụ thể |
| [Investor.gov — Public Companies](https://www.investor.gov/introduction-investing/investing-basics/how-stock-markets-work/public-companies) | K07: báo cáo Mỹ và SEC | Không coi mọi công ty Mỹ hoặc nước ngoài dùng cùng một bộ form |
| [HOSE](https://www.hsx.vn/) | K08: điểm bắt đầu tra cứu tại Việt Nam | Trang có nội dung động; chưa trích xuất hoặc đồng bộ hồ sơ vào app |
| [Investor.gov — International Investing](https://www.investor.gov/introduction-investing/investing-basics/investment-products/international-investing) | K09: bối cảnh tỷ giá và đầu tư quốc tế | Không cung cấp feed tỷ giá cho app |

K08 là checklist nghiên cứu được biên soạn cho sản phẩm và liên kết đến cổng HOSE; không phải tóm tắt một quy định giao dịch. HNX/UPCoM được nêu như từ khóa để dẫn vào việc kiểm tra nguồn, không có dữ liệu phiên, chu kỳ thanh toán hoặc quy tắc lệnh được khẳng định trong kho.

## Biên soạn, kiểm tra và cập nhật

Người biên soạn ghi nguồn, thị trường, ngày kiểm tra và phạm vi kết luận. Người rà soát kiểm tra công thức, thuật ngữ, đơn vị và các trường hợp ngoại lệ. Sau khi sửa, chạy bộ test retrieval và đánh giá thủ công câu trả lời mẫu. Với nội dung về quy tắc hiện hành, cần dẫn đúng văn bản và ngày hiệu lực; bài nền hiện tại chủ động không đưa những quy tắc đó.

## Dữ liệu nhập vào và đơn vị

Giá ngày và provenance: [MARKET_DATA.md](MARKET_DATA.md). Tài liệu PDF/TXT/MD, quyền sử dụng và page citation: [BOOKS.md](BOOKS.md). Không tự tải sách thương mại hoặc coi ví dụ trong sách là số liệu hiện tại.

CSV yêu cầu đúng các cột:

```text
market,symbol,currency,price,eps_ttm,bvps,dividend_per_share,as_of,source
```

- `market`: VN hoặc US; `currency`: VND hoặc USD tương ứng.
- Giá, EPS, BVPS, cổ tức đều tính trên một cổ phiếu và cùng tiền tệ; giá VND nhập bằng đồng, không bằng nghìn đồng.
- `eps_ttm`: lợi nhuận/cổ phiếu 12 tháng gần nhất do người dùng cung cấp.
- `as_of`: ngày snapshot YYYY-MM-DD, không ở tương lai; không thay thế kỳ của từng chỉ số.
- `source`: mô tả hoặc link nguồn, không để trống. Ứng dụng chưa kiểm chứng link hoặc số liệu.
- Tối đa 1 MB và 200 dòng, một mã trên mỗi thị trường. File hợp lệ về định dạng chưa chắc đúng về tài chính.

Hai dòng trong file mẫu là **giả định**, dùng cùng tỷ lệ ở hai đơn vị để kiểm tra công thức. `DEMO` không phải dữ liệu của một doanh nghiệp được khuyến nghị.

## Quyền sử dụng cho bản bán thử

Khả năng truy cập một trang công khai không tự xác nhận quyền thu thập, lưu lại hoặc bán lại dữ liệu. Trước khi thêm feed, lưu hồ sơ về nhà cung cấp, điều khoản, phạm vi redisplay, độ trễ, giới hạn request và quyền dùng thương mại. Tài liệu này là checklist vận hành sản phẩm, không kết luận pháp lý về nguồn nào.

## Phân biệt các lớp bằng chứng

Ghi chú nền giải thích khái niệm; sách phản ánh tài liệu bạn cung cấp; snapshot giá gắn với phiên cụ thể; RSS dẫn tới báo gốc. Không dùng lớp này thay cho dữ kiện thiếu của lớp khác. Tên Breakout AI không thay đổi phạm vi hoặc độ tin cậy đã xác minh của dữ liệu.

[Bản đồ tài liệu](README.md) · [Sách](BOOKS.md) · [Thị trường](MARKET_DATA.md).
