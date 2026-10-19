# Đưa Breakout AI lên Git
## Trạng thái và ý nghĩa ngày
Repository hiện có nhánh main, chưa có commit hoặc remote. Kế hoạch dưới đây chia snapshot hoàn chỉnh thành 11 nhóm từ 09–19/10/2026. Những ngày/giờ này là **mốc được dựng lại**, không xác nhận công việc đã thực hiện vào các ngày đó. README/version vẫn phản ánh bản hiện tại; đây không phải khôi phục các phiên bản cũ.

Git có author date và committer date, có thể đặt bằng GIT_AUTHOR_DATE/GIT_COMMITTER_DATE. Chỉ --date không đổi cả hai. Push time là thời điểm máy chủ nhận dữ liệu, không chỉnh lùi bằng Git local. Không đổi giờ hệ điều hành.

## Message và kế hoạch
Tiêu đề dùng tiếng Anh theo mẫu type(scope): action; mô tả sau dòng trống là một câu tiếng Việt. Thời gian theo Việt Nam, offset +07:00, có thể sửa trong scripts/git-history-plan.json theo hồ sơ thực của bạn.

| Mốc | Tiêu đề | Mô tả |
| --- | --- | --- |
| 09/10 19:30 | `chore(core): establish project foundation` | Thiết lập cấu hình, dữ liệu local và kiểm thử nền. |
| 10/10 20:15 | `feat(knowledge): add knowledge and LLM providers` | Bổ sung kiến thức tài chính và kết nối mô hình. |
| 11/10 16:40 | `feat(books): index books and extract trading rules` | Đọc sách, tìm trích đoạn và nhận diện điều kiện đầu tư. |
| 12/10 21:05 | `feat(market): integrate Vietnam and US price data` | Lấy giá theo phiên, lưu cache và giữ nguồn dữ liệu. |
| 13/10 19:50 | `feat(screening): rank stock research candidates` | Thêm tiêu chí sàng lọc và kiểm tra nguồn giá. |
| 14/10 20:35 | `feat(chat): add research answers with citations` | Kết hợp kiến thức, sách và giá trong câu trả lời có nguồn. |
| 15/10 21:20 | `feat(portfolio): track holdings and trade history` | Ghi mua bán, cập nhật giá vốn và tính lãi lỗ đã chốt. |
| 16/10 19:45 | `feat(daily): schedule morning stock reviews` | Tạo bản tin từ sách và cài lịch 07:30. |
| 17/10 17:10 | `feat(insights): add news feeds and price charts` | Hiển thị tin có nguồn, biểu đồ giá và phân bổ vốn. |
| 18/10 21:15 | `feat(ui): build Breakout AI trading workspace` | Hoàn thiện giao diện tối, danh mục và lịch sử chat. |
| 19/10 08:00 | `docs: document Breakout AI setup and delivery` | Bổ sung hướng dẫn sử dụng, vận hành và đưa mã lên Git. |

File cụ thể của mỗi nhóm nằm trong `scripts/git-history-plan.json`. Phụ thuộc nền tảng đi trước; UI xuất hiện ngày 18 và tài liệu hoàn chỉnh ngày 19. Mốc cuối không gọi “rename” vì snapshot trong các nhóm đã mang tên Breakout AI.

## 1. Xem trước
Từ thư mục Breakout_AI:
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\prepare-git-history.ps1 -Mode Plan
```
Lệnh chỉ đọc và kiểm tra kế hoạch; không stage, commit, đổi config hoặc liên hệ remote.

Nếu cần, đặt tác giả bằng git config --local user.name/user.email; dùng email đã xác minh trên GitHub hoặc địa chỉ noreply của tài khoản. Script không tự đổi danh tính.

## 2. Tạo commit local
Kiểm tra kế hoạch rồi chạy:
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\prepare-git-history.ps1 -Mode Commit
git log --reverse --format="%h %aI | %cI | %s"
git status --short
```

Script dùng đúng danh sách file, giữ hai mốc ngày giống nhau, lưu message UTF-8 và khôi phục biến ngày trong finally. Mặc định loại DB, .env, venv, artifacts và cache; không dùng git add -f.

Chỉ dùng cho repo chưa có commit và index trống. Không chạy git add . trước script. Nếu có file ngoài kế hoạch, thêm rõ vào nhóm thích hợp rồi xem lại. Nếu commit bị hook/ký số chặn giữa chừng, kiểm tra git status/log và tiếp tục thủ công phần còn lại; script không xóa hoặc viết lại các commit đã tạo.

## 3. Tạo repo GitHub và push
Trên GitHub, tạo repository trống tên Breakout_AI. Chọn quyền truy cập theo nhu cầu; không khởi tạo thêm README, license hoặc .gitignore ở remote vì local đã có mã.

Thay YOUR_USERNAME bằng tài khoản sở hữu repository:
```powershell
git remote add origin https://github.com/YOUR_USERNAME/Breakout_AI.git
git remote -v
git push -u origin main
```

Chỉ add origin khi chưa có. Nếu có remote, kiểm tra URL trước; hướng dẫn không tự đổi hoặc force-push. Push một lần vẫn gửi toàn bộ 11 commit và giữ metadata ngày commit; không tạo được 11 lần push trong quá khứ.

Nếu GitHub yêu cầu đăng nhập, dùng Git Credential Manager hoặc phương thức GitHub hỗ trợ; không đưa token vào URL/file mã. Nếu remote đã có lịch sử, fetch và kiểm tra trước, không dùng force để vượt lỗi.

## Ví dụ một commit thủ công
```powershell
$env:GIT_AUTHOR_DATE = "2026-10-12T21:05:00+07:00"
$env:GIT_COMMITTER_DATE = $env:GIT_AUTHOR_DATE
git add -- breakout_ai/market.py tests/test_market.py
git commit -m "feat(market): integrate Vietnam and US price data" -m "Lấy giá theo phiên, lưu cache và giữ nguồn dữ liệu."
Remove-Item Env:GIT_AUTHOR_DATE
Remove-Item Env:GIT_COMMITTER_DATE
```

Ví dụ dành cho phiên terminal chưa đặt sẵn hai biến ngày; script tự bảo toàn giá trị cũ tốt hơn. Không kết hợp ví dụ thủ công với toàn bộ kế hoạch mà không bỏ nhóm đã commit.

Nguồn chính thức: [git commit](https://git-scm.com/docs/git-commit), [git push](https://git-scm.com/docs/git-push).
