# Vận hành Breakout AI
## Chạy local
Dùng `scripts/run.ps1` hoặc Python trong .venv; mặc định script mở cổng 8507, bind 127.0.0.1. Chỉ expose mạng sau khi có xác thực và kiểm soát truy cập phù hợp; bản hiện tại chưa là SaaS.

Đặt .env ở root. Không log/gửi key. Đổi provider/theme cần restart. WORKSPACE_ID là scope local, không phải tài khoản đã xác thực. Khi dùng LLM ngoài máy, dữ liệu truy xuất có thể ra khỏi máy.

## Database
Cài mới dùng data/breakout_ai.sqlite3, nâng cấp giữ data/stocklab.sqlite3 nếu đã có. DATABASE_PATH rõ luôn ưu tiên. Không xóa/đổi tên file để làm mới thương hiệu; xem [MIGRATION](MIGRATION.md).

Sao lưu bằng SQLite backup API khi app hoạt động:
```python
import sqlite3
from breakout_ai.config import Settings

settings = Settings.from_env()
with sqlite3.connect(settings.database_path) as source:
    with sqlite3.connect("data/breakout-ai-backup.sqlite3") as backup:
        source.backup(backup)
```

Backup có thể chứa chat/sách/danh mục cá nhân; không commit. Thử phục hồi vào DB riêng trước, không đè dữ liệu đang dùng. Nếu sao lưu file khi tắt app, tránh lúc task đang chạy. Chưa có backup định kỳ tự động.

## Lịch 07:30
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\daily-schedule.ps1 -Mode Status
```

Kiểm tra task thực tế; schedule.json chỉ ghi trạng thái gần nhất. Action phải dùng pythonw trong đúng root với `-m breakout_ai.daily --refresh`. Task Limited/Interactive cần máy bật, tài khoản đăng nhập và mạng. Di chuyển thư mục/venv phải cập nhật lịch; không giữ task cũ trỏ đường dẫn mất.

## Khi lỗi
| Triệu chứng | Kiểm tra |
| --- | --- |
| Chat lỗi | Provider, model/key, timeout, quota; không in bí mật vào log |
| Giá không mới | Cờ stale, nguồn, thời điểm bar; không dùng cache lỗi để khuyến nghị |
| Tin thiếu | Feed lỗi, cache quá hạn; nguồn khác vẫn có thể hiện |
| Số dư sai | Đơn vị, số lượng, phí, giao dịch và quyền/chia tách |
| Dữ liệu biến mất | Database/workspace đang mở, không vội tạo dữ liệu mới |
| Giao diện giữ màu cũ | Restart tiến trình, tải lại trang; kiểm tra theme trong Settings |

Journal chưa cho sửa/hủy; cần quy trình điều chỉnh có audit trước khi dùng rộng. Không tự sửa SQLite để làm lệch ledger/vị thế.

## Trước triển khai nhiều người dùng
Bổ sung xác thực và phân quyền workspace ở server, quota/ngân sách, logging giảm dữ liệu nhạy cảm, backup/retention, export/xóa dữ liệu, giám sát và load test. PDF cần thêm biện pháp cách ly tài nguyên trước public upload. Hoàn thiện quyền dữ liệu, billing/idempotent webhook và hỗ trợ. [Kế hoạch thương mại](COMMERCIAL_PLAN.md).
