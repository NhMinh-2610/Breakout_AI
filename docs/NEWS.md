# Tin tức Breakout AI
Tin tức là danh sách tiêu đề có nguồn và thời gian; bấm tiêu đề mở bài gốc. Có bộ lọc VN/Mỹ/tất cả, tìm từ khóa và nút cập nhật. Không tải toàn văn, ảnh hoặc đưa tiêu đề vào điều kiện mua/bán của sách.

| Thị trường | Nguồn | RSS |
| --- | --- | --- |
| VN | [VnExpress Kinh doanh](https://vnexpress.net/kinh-doanh) | `https://vnexpress.net/rss/kinh-doanh.rss` |
| US | [CNBC Finance](https://www.cnbc.com/finance/) | `https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664` |

Hai nguồn từng được thử HTTP 200/XML ngày 18/10/2026. Đây là bằng chứng thời điểm đó, không đảm bảo hiện luôn hoạt động. Không đổi sang nguồn khác âm thầm khi lỗi.

## Cập nhật
Cache theo nguồn/workspace 15 phút; trang đang mở kiểm tra lại mỗi 900 giây. Nút cập nhật yêu cầu lấy mới. Nếu một nguồn lỗi, nguồn còn lại vẫn hiện; bản lưu không quá 7 ngày có nhãn cũ và lỗi. Cũ hơn bị bỏ.

Ngày bài viết và lúc tải nguồn là hai trường riêng. Ngày thiếu/sai/không timezone/quá xa tương lai không được thay bằng ngày tải. fetched_at của kết quả là thời điểm cũ nhất trong các nguồn đang hiện.

## Adapter
`NewsService.fetch(market="BOTH", force=False)` trả articles, errors, fetched_at, stale, from_cache. Article có title, url, source, market, published_at, fetched_at, feed_url, cache_stale.

Chỉ gọi URL allowlist, không theo redirect hoặc tải bài gốc ở server. Mỗi feed tối đa 512 KiB/60 mục; kiểm tra URL cùng miền nguồn, không credentials. Từ chối DTD/entity/XML UTF-16/32; bỏ URL trùng hoặc tiêu đề lỗi. UI escape dữ liệu trước HTML.

## Quyền sử dụng
[Điều khoản RSS VnExpress](https://vnexpress.net/rss) là nguồn để đối chiếu phạm vi dùng; hồ sơ dự án trước đó ghi nhận miễn phí cho cá nhân/tổ chức phi lợi nhuận. Quyền phân phối thương mại của các feed chưa được xác nhận. Trước bán cần thỏa thuận phù hợp hoặc nguồn được cấp phép; truy cập công khai không đồng nghĩa giấy phép bán lại.

Kiểm thử offline ở `tests/test_news.py`; pytest không gọi feed thật. [Kế hoạch thương mại](COMMERCIAL_PLAN.md).
