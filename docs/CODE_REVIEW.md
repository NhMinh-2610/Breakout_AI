# Rà soát code — Breakout AI 0.9

Ngày hoàn tất: **05/11/2026**. Phạm vi: đưa việc quan sát biểu đồ và nhận định cơ hội có căn cứ thành luồng chính.

| Vấn đề đã xác minh | Ảnh hưởng trước sửa | Thay đổi |
| --- | --- | --- |
| Lỗi tải nến không được giữ trong cache | Sau lần tải lỗi, rerun nhanh có thể trả lại dữ liệu với nhãn mới và kích hoạt lại tín hiệu | Lưu trạng thái lỗi cùng snapshot; chỉ lần tải thành công mới khôi phục trạng thái |
| Phản hồi HTTP về sau khi claim đã bị thay thế | UI có thể nhận kết quả cũ dù cache đã có kết quả mới hơn | Kiểm tra chủ sở hữu claim khi hoàn tất; dùng kết quả có thẩm quyền mới nhất |
| Model không nhận chuỗi nến | LLM chỉ diễn giải các chỉ báo được tính sẵn | Tạo gói quan sát gồm tối đa 60 nến đã đóng, cấu trúc giá, thân/bóng nến, facts và scenarios |
| Văn bản model được nối trực tiếp vào nhận định | Chỉ dẫn trong prompt chưa đủ để ngăn kết luận hoặc số liệu ngoài nguồn | Kiểm tra JSON bốn trường, mã bằng chứng/kịch bản và action; chỉ render nội dung chuẩn đã cung cấp |
| Trang mặc định ưu tiên bản tin và nhiều tính năng phụ | Tác vụ quan sát một mã cần nhiều bước điều hướng | Mặc định mở Phân tích AI; bảng điện, sách, danh mục và bản tin là các luồng phụ |

## Cấu trúc sau làm sạch

- [market_page.py](../breakout_ai/market_page.py): chọn mã/khung nến, trang phân tích và các chế độ thị trường.
- [ui_common.py](../breakout_ai/ui_common.py): helper trình bày dùng chung.
- [observation.py](../breakout_ai/observation.py): gói quan sát duy nhất cho UI, scanner và model; kiểm tra đúng mã, đơn vị, khung nến và trạng thái nguồn.
- [technical.py](../breakout_ai/technical.py): tính chỉ báo và kiểm tra điều kiện kỹ thuật.
- [copilot.py](../breakout_ai/copilot.py), [interpretation.py](../breakout_ai/interpretation.py): gọi model theo thao tác và xác minh bằng chứng trước hiển thị.
- CSS bỏ 24 declaration bị ghi đè; giữ kết quả cascade và tách mỗi declaration để dễ đọc. Sáu module trọng tâm được format với kiểm tra AST trước/sau giống hệt nhau.

## Bằng chứng

**633 kiểm thử đạt, không lỗi**, JUnit local: .artifacts/observer-v09-tests.xml. Các ca mới kiểm tra nguồn lỗi qua rerun/instance, claim về muộn, nến đã đóng, gói dữ liệu bất biến, từ chối bằng chứng/kịch bản lạ, không đổi action và không tự gọi model.

Compileall đạt. HTTP trang/health đều 200; tiến trình thử đã dừng. Kiểm tra CSS/parser và AppTest không thay thế xác minh hình ảnh hoặc đánh giá hiệu quả đầu tư.

## Giới hạn còn lại

Máy hiện cấu hình provider demo, chưa có model/key hoặc model Ollama sẵn dùng. Luồng LLM được kiểm tra bằng phản hồi giả lập; chưa đánh giá suy luận trên model thật. Observer đọc dữ liệu OHLCV tạo nên biểu đồ, chưa đọc ảnh chụp biểu đồ.

Chưa có bộ dữ liệu đánh giá chất lượng nhận định hoặc backtest ngoài mẫu có phí/trượt giá. Không suy ra xác suất thắng, lợi nhuận hoặc chất lượng chiến lược từ kết quả unit test. Chưa có QA hình ảnh trình duyệt trong phiên này.

[Thiết kế observer](CHART_OBSERVER.md) · [Kiểm thử](TESTING.md) · [Quy tắc kỹ thuật](TECHNICAL_ANALYSIS.md).
