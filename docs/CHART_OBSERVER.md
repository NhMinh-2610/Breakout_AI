# Hợp đồng quan sát biểu đồ

## Phạm vi

`observe_chart(symbol, chart, quote, owned=False, resolution="5", now=None)` tạo một `ChartObservation` dùng chung cho giao diện, scanner và AI. Nó đọc dữ liệu OHLCV tạo nên biểu đồ, chưa xử lý ảnh chụp hoặc nhận dạng hình ảnh.

Đầu vào phải khớp mã, khung 1/5/15 phút, cổ phiếu VN và đơn vị VND. Quote/nến cũ, nguồn lỗi, dữ liệu thiếu hoặc sai danh tính làm action chuyển `wait`. Rà soát bán chỉ xét mã đang sở hữu.

## Bối cảnh được chụp

`ChartObservation.context()` trả một bản sao JSON-safe:

| Trường | Nội dung |
| --- | --- |
| `analysis` | SignalReport: action, bằng chứng, chỉ báo, mốc giá và blockers |
| `quote` | Các trường quote công khai đã chọn, có giờ nguồn và trạng thái |
| `chart.candles` | Tối đa 60 nến đã đóng, giữ OHLCV và thời gian gốc |
| `chart.facts` | Bằng chứng có ID, mô tả chuẩn, vai trò và giá trị kiểm tra được |
| `chart.scenarios` | Kịch bản có ID, điều kiện xác nhận/vô hiệu, trạng thái và ID bằng chứng |
| `owned` | Mã có thuộc vị thế sở hữu tại lúc quan sát |
| `captured_at` | Thời điểm chụp bối cảnh |

Cấu trúc giá gồm so sánh nhóm đỉnh/đáy gần nhất, vùng quan sát, thân/bóng và vị trí đóng của nến. Đây là mô tả cửa sổ dữ liệu, không tự tạo thêm chiến lược giao dịch. Chỉ báo có thể dùng lịch sử dài hơn 60 nến; giới hạn 60 chỉ áp dụng phần dữ liệu gửi kèm AI.

Nến đang hình thành có thể vẽ mờ trên biểu đồ nhưng không đi vào bằng chứng xác nhận hoặc chuỗi nến đóng gửi model. Mã/khung/đơn vị sai không được dùng để sinh kết luận từ dữ liệu của mã khác.

## Hợp đồng phản hồi model

Model nhận context cùng câu hỏi/lịch sử giới hạn và tối đa hai đoạn sách phù hợp. Phản hồi chỉ gồm:

```json
{
  "action": "wait",
  "focus_fact_ids": ["trend.sma20"],
  "risk_fact_ids": ["data.readiness"],
  "scenario_id": null
}
```

Các ID trên chỉ hợp lệ nếu tồn tại trong context của lượt đó. `action` phải bằng `analysis.action`. Bằng chứng phản biện phải có role `risk` hoặc `blocker`; khi có blockers, danh sách phản biện không được rỗng. Không được chọn kịch bản `qualified` khi đang chờ hoặc dữ liệu bị chặn.

Bộ kiểm tra từ chối trường dư, ID lạ/trùng, action bị đổi hoặc phản hồi sai cấu trúc. Văn bản được dựng từ facts/scenarios chuẩn; đoạn model tự tạo giá mục tiêu, xác suất hoặc lời khẳng định ngoài dữ liệu không được xuất như nhận định hợp lệ.

Nếu phản hồi không đạt, ứng dụng giữ giải thích theo quy tắc và ghi `validated=false`. Demo không gọi model, lưu `mode="rules"`. Model hợp lệ lưu `mode="model"` cùng các ID đã chọn.

## Lưu và đối chiếu

Bấm **Đọc biểu đồ & nhận định** hoặc gửi **Chat theo mã** mới tạo lượt. Tự cập nhật giá/nến không gọi model hoặc tính thêm quota. Lượt lưu có `chart_context` và `interpretation`; dữ liệu mới không sửa bản đã lưu.

Sách dùng làm tài liệu giải thích và có trích dẫn đoạn/trang, chưa huấn luyện lại model hay tự thay quy tắc. Kết quả chưa có kiểm định hiệu quả đầu tư. Cần tập đánh giá và backtest theo thời gian trước khi dùng như một phương pháp đã xác minh.

[Kiến trúc](ARCHITECTURE.md) · [Kỹ thuật](TECHNICAL_ANALYSIS.md) · [Kiểm thử](TESTING.md).
