# Quyết định thiết kế Breakout AI
Bản tổng hợp hiện hành cho 0.6. Những thay đổi theo phiên bản nằm trong CHANGELOG; bản sao mã/tài liệu trước đổi tên đã được lưu trước khi biên tập.

| ID | Quyết định | Lý do | Khi xem lại |
| --- | --- | --- | --- |
| ADR-01 | Python + Streamlit + SQLite local | Phù hợp nền Python cơ bản và thử sản phẩm nhanh | Khi UX nhiều vai trò hoặc tải cần nền tảng khác |
| ADR-02 | Breakout AI / breakout_ai | Tên do chủ dự án chọn, thống nhất UI và API phát triển | Khi có yêu cầu pháp lý/thương hiệu cụ thể |
| ADR-03 | Giữ database cũ, schema v4 | Đổi thương hiệu không được làm mất dữ liệu | Migration dữ liệu thật cần backup và kế hoạch riêng |
| ADR-04 | Demo mặc định, provider qua adapter | Thử được không cần key; không khóa một model | Khi có benchmark và môi trường pilot |
| ADR-05 | Sách RAG theo trang, BM25 | Có thể đối chiếu và xóa/cập nhật local | Khi lỗi retrieval thực tế cho thấy cần embedding |
| ADR-06 | Parser nguyên tắc giới hạn, người dùng đối chiếu | Không tự gán ngưỡng hoặc hiểu sai toàn bộ sách | Có corpus và đánh giá chuyên môn |
| ADR-07 | Công thức bằng code, LLM diễn giải | Phép tính có thể kiểm thử/tái lập | Giữ khi mở rộng |
| ADR-08 | Danh mục tách danh sách tìm mua | Không suy ra người dùng đã sở hữu mã | Broker import có xác minh |
| ADR-09 | Journal nguyên tử, bất biến và idempotent | Không lệch sổ/vị thế khi lỗi hoặc gửi lại | Thêm adjustment có audit |
| ADR-10 | VND/USD riêng, không tạo hiệu suất giả | Tránh tổng tiền sai đơn vị và lịch sử thiếu | Có FX và dòng tiền/quyền đầy đủ |
| ADR-11 | RSS chỉ tiêu đề, độc lập tín hiệu sách | Không biến tiêu đề thành căn cứ mua/bán | Có phương pháp, nguồn và eval phù hợp |
| ADR-12 | Sáu trang, thao tác chính rõ | Mỗi tác vụ có nơi dễ tìm | Quan sát người dùng thực tế |
| ADR-13 | Chat một cột, lịch sử sidebar, input cấp trang | Đọc dễ và không mất ô nhập khi cuộn | Sau QA desktop/mobile |
| ADR-14 | Theme tối, giới hạn chiều rộng | Hợp bảng điện, giảm kéo giãn và mất cân đối | Đo khả năng đọc và nhu cầu theme |
| ADR-15 | Task Windows 07:30 Limited/Interactive | Giờ người dùng chọn, không cần server | Trước SaaS cần scheduler giám sát |
| ADR-16 | Tách bằng chứng test và hình ảnh | Test pass không chứng minh UX hoặc lợi nhuận | Luôn giữ nguyên tắc này |

Quyết định mới phải nêu vấn đề, lựa chọn, đánh đổi, bằng chứng và điều kiện xem lại.
