# Backlog Breakout AI
## Đã hoàn thành trong 0.6
- Nhận diện Breakout AI trên UI, logo/favicon, chat, export và tài liệu.
- Package breakout_ai, metadata breakout-ai và lệnh chạy mới.
- Căn độ rộng trang, sidebar, thẻ số liệu, dải giá và hội thoại/ô nhập.
- Viết lại tài liệu có trang chỉ mục, hướng dẫn chuyển đổi và quy ước thương hiệu.
- Backup nguồn/SQLite; giữ DB hiện có và scope dữ liệu.
- Chuyển task sang root mới, giữ 07:30, chạy thử thành công.
- 238 kiểm thử local đạt; HTTP smoke và kiểm tra CSS/link.

## Ưu tiên trước pilot
| Ưu tiên | Công việc | Đạt khi |
| --- | --- | --- |
| P0 | QA trực quan desktop/mobile và bàn phím | Không che/tràn/cắt thao tác chính, có bằng chứng thiết bị |
| P0 | Đánh giá sách và nguyên tắc thực | Tập câu hỏi/ngoại lệ có quyền, kết quả được đối chiếu |
| P0 | Chọn dữ liệu cấp phép | Hồ sơ quyền hiển thị/phân phối, hạn mức và chi phí rõ |
| P0 | Điều chỉnh giao dịch | Có audit, giữ số dư/giá vốn nhất quán khi sửa sai |
| P1 | Model thật và chi phí | Đo chất lượng, latency, usage và lỗi |
| P1 | Backup/restore | Khôi phục thử trên DB riêng và có quy trình |
| P1 | Nhóm khách hàng ban đầu | Phỏng vấn, quan sát tác vụ, bằng chứng quay lại |
| P1 | Auth và bảo vệ workspace | Tách dữ liệu được kiểm thử qua server |
| P2 | Billing/quota theo gói | Webhook chống trùng, đối soát, giới hạn chi phí |
| P2 | Scheduler server/thông báo | Có giám sát, retry và đồng ý nhận thông báo |
| P2 | Truy xuất tốt hơn | Cải thiện đo được trên câu hỏi thật, không đổi công nghệ chỉ vì phổ biến |

## Chưa thuộc phạm vi hiện tại
Tự đặt lệnh broker, dự đoán lợi nhuận chắc chắn, quét toàn sàn realtime, tự định giá đầy đủ doanh nghiệp, hiểu toàn bộ hình/bảng sách, SaaS sẵn sàng thu phí.

[Đặc tả](../docs/PRODUCT.md) · [Kế hoạch thử](../docs/COMMERCIAL_PLAN.md).
