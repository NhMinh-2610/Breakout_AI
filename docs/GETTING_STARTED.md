# Bắt đầu với Breakout AI
## Trên máy hiện tại
Mở thư mục `Breakout_AI`:
```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8507
```
Mở http://localhost:8507. Dừng bằng Ctrl+C. `.\scripts\run.ps1 -Port 8507` là lệnh tương đương và tự dùng đúng thư mục.

Sau đổi theme hoặc cấu hình, dừng tiến trình cũ rồi chạy lại. Nếu cổng bận, chọn `-Port 8510`, không cần xóa dữ liệu hoặc dừng tiến trình không rõ nguồn.

## Cài mới
Python 3.11 trở lên. Không cần GPU với demo hoặc API ngoài máy.
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8507
```
PowerShell có thể dùng `.\scripts\setup.ps1 -Dev`. macOS/Linux dùng `.venv/bin/python`.

Môi trường hiện có dùng thư viện Anaconda qua `system-site-packages`. Máy mới nên tạo venv độc lập. Dùng `python -m ...` để tránh launcher giữ đường dẫn cũ khi đổi thư mục.

## Cấu hình chat
Sao chép `.env.example` thành `.env` khi cần đổi cấu hình.

| Provider | Cần cấu hình | Kết quả |
| --- | --- | --- |
| `demo` | `LLM_PROVIDER=demo` | Trích đoạn và phép tính, không gọi LLM |
| `openai` | Provider, `LLM_MODEL`, `OPENAI_API_KEY` | Tổng hợp qua API |
| `ollama` | Provider, model đã có, URL Ollama | Tổng hợp qua server của bạn |

```dotenv
LLM_PROVIDER=demo
WORKSPACE_ID=local
MARKET_DATA_ENABLED=true
VN_MARKET_PROVIDER=kbs
US_MARKET_PROVIDER=yahoo
```

Model và quyền truy cập tùy tài khoản/máy; tài liệu không hardcode một model cho mọi người. Trong luồng quan sát biểu đồ, provider ngoài máy có thể nhận câu hỏi, lịch sử gần nhất, tối đa 60 nến đã đóng, chỉ báo/bằng chứng/kịch bản và đoạn sách truy xuất. Bản tin điều kiện vẫn tính cục bộ. Không đưa key vào mã, Git hoặc chat hỗ trợ.

## Dữ liệu sau nâng cấp
Nếu `data/stocklab.sqlite3` đã có, ứng dụng tiếp tục mở file này. Cài mới dùng `data/breakout_ai.sqlite3`. `DATABASE_PATH` đặt rõ được ưu tiên; giữ cấu hình cũ khi nâng cấp. [Chi tiết](MIGRATION.md).

## Thử ứng dụng
1. Mở **Phân tích AI → Phân tích biểu đồ**, chọn mã và khung nến.
2. Xem cấu trúc nến, khối lượng và giới hạn dữ liệu; bấm **Đọc biểu đồ & nhận định**.
3. Hỏi “Điều kiện xác nhận là gì?” hoặc “Điều gì làm kịch bản mất hiệu lực?”.
4. Thêm vị thế ở Danh mục nếu cần rà soát bán; sách dùng bổ sung kiến thức, không phải điều kiện bắt buộc để đọc biểu đồ.

Demo giải thích bằng quy tắc. Khi cấu hình model, AI chọn bằng chứng/kịch bản trong dữ liệu đã cung cấp; đầu ra sai hợp đồng bị từ chối và hiển thị rõ giới hạn. [Thiết kế observer](CHART_OBSERVER.md).

Bản tin theo sách và lịch 07:30 là luồng phụ: [hướng dẫn hằng ngày](DAILY_GUIDE.md).

| Lỗi | Xử lý |
| --- | --- |
| Thiếu .venv/module | Tạo môi trường, dùng Python trong .venv từ root dự án |
| Chat chỉ trả trích đoạn | Demo đang hoạt động; cấu hình model nếu cần tổng hợp |
| Nhận định đang chờ | Kiểm tra thời gian giá/nến, nguồn lỗi, khối lượng và điều kiện chưa đạt; không ép tạo cơ hội |
| Không thấy dữ liệu cũ | Kiểm tra DATABASE_PATH, WORKSPACE_ID; không xóa DB |
| Task hỏng sau chuyển thư mục | Cài lại lịch, đối chiếu action và đường dẫn |
