# Chuyển sang Breakout AI 0.6
| Trước | Hiện tại |
| --- | --- |
| Tên sản phẩm cũ | Breakout AI |
| `LLM_Ai` | `Breakout_AI` |
| Package `stocklab` | `breakout_ai` |
| Metadata `stocklab-assistant` | `breakout-ai` |
| `python -m stocklab.daily` | `python -m breakout_ai.daily` |
| `StockLab-Morning-…` | `BreakoutAI-Morning-…` |
| Export `stocklab-…` | `breakout-ai-…` |

Import và lệnh trong dự án đã cập nhật; không có package alias cũ. Script ngoài dự án dùng tên cũ cần đổi import/lệnh.

## Giữ dữ liệu
Giữ schema v4, workspace và ID. DB `data/stocklab.sqlite3` có sẵn tiếp tục được mở; cài mới dùng `data/breakout_ai.sqlite3`. Nếu cả hai có mặt, mặc định ưu tiên file cũ để tránh mở nhầm workspace trắng; dùng DATABASE_PATH khi muốn chọn rõ.

Không tự đổi nội dung hội thoại cũ hoặc tệp export đã lưu. Nếu .env chứa đường dẫn tuyệt đối cũ, cần sửa đường dẫn. Không xóa DB để “làm mới” thương hiệu.

Trước chuyển đổi, mã được lưu trong `.artifacts/before-breakout-*.zip`, SQLite trong `data/backups/before-breakout-*.sqlite3`. Archive nguồn không chứa .env hoặc DB. Sao lưu chưa đồng nghĩa kiểm thử khôi phục.

## Môi trường và lịch
Dùng `.\.venv\Scripts\python.exe -m ...`; launcher/activation của venv di chuyển có thể giữ đường dẫn cũ. Tạo lại venv nếu cần chuyển máy.

Task cũ đã được xuất XML ở `.artifacts/schedule-before-breakout.xml`. Task mới được xác minh marker, action, đường dẫn và 07:30 trước khi gỡ task cũ đúng dự án. Task khác không bị sửa.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\daily-schedule.ps1 -Mode Status
```

Nếu sau này chuyển thư mục, gỡ lịch trước khi di chuyển và cài lại sau đó. Nếu đã chuyển, kiểm tra Task Scheduler và chỉ gỡ đúng tác vụ dự án.

## Kiểm tra sau nâng cấp
Chạy test, mở app và xác nhận dữ liệu; kiểm tra action/giờ của task. Test dùng DB tạm, không nạp giao dịch giả vào DB thật. Restart Streamlit để nạp logo/theme.

Muốn quay lại mã cũ: dừng app/job, khôi phục source riêng; không phục hồi DB backup đè lên giao dịch mới sau nâng cấp.
