# Comic Recap Tool — Thiết kế

## Mục đích
Tool cá nhân chạy trên Mac: dán link 1 chapter truyện tranh → ra video review/recap tiếng Việt có giọng đọc, phụ đề, watermark, sẵn sàng đăng TikTok (dọc 9:16) và YouTube (ngang 16:9). Lấy cảm hứng từ "Comic Recap Studio" (video TikTok người dùng chia sẻ).

## Mục tiêu
1. Lấy truyện từ link: tự tải toàn bộ ảnh của chapter.
2. AI phân tích từng trang: khung tranh + lời thoại (thường là tiếng Anh).
3. Hiểu cốt truyện & nhân vật, giữ tên nhất quán qua các chapter (lưu "từ điển nhân vật" theo bộ truyện).
4. Phiên âm tên nhân vật kiểu Việt (vd. "U Linh Sa"), người dùng sửa được.
5. Giọng đọc tiếng Việt miễn phí.
6. Tự chọn khung tranh cho từng câu thuyết minh, ghép video: khung tranh ở giữa, nền là chính ảnh đó làm mờ, zoom/trượt nhẹ.
7. Phụ đề tự động khớp từng câu.
8. Watermark tên kênh tùy chỉnh.
- Có bước xem lại và chỉnh tay kịch bản/cảnh trước khi xuất video.

## Không làm (giai đoạn này)
- Tự đăng lên YouTube/TikTok (người dùng tự upload).
- Bán/phân phối, bản quyền phần mềm, đa người dùng.
- Chạy AI phân tích ảnh hoàn toàn offline.

## Anti-goals
- Video dạng "slideshow" đơn điệu, lời kể chỉ đọc lại thoại — phải là lời kể recap có cảm xúc.
- Tên nhân vật đổi lung tung giữa các đoạn/chapter.

## Ràng buộc
- macOS, một người dùng, chạy local.
- AI: **Google Gemini** (gói miễn phí) trước; kiến trúc cho phép đổi sang Claude sau (chỉ đổi cấu hình + API key).
- Chi phí vận hành ~0đ khi dùng Gemini free tier (có giới hạn số request/ngày).
- Rủi ro bản quyền nội dung truyện là trách nhiệm người dùng; tool không né cơ chế Content ID.

## Các phương án đã cân nhắc
- **A. AI trên mạng đọc tranh + giọng đọc/ghép video local** — ĐÃ CHỌN. Chất lượng lời kể tốt, chi phí thấp/miễn phí.
- B. 100% local (mô hình mở) — loại: cần GPU mạnh, lời kể tiếng Việt kém.
- C. Bán tự động (tự dán kịch bản) — loại: trái mục tiêu tự động.
- Nhà cung cấp AI: người dùng chọn **thử Gemini trước**, Claude là phương án nâng cấp.

## Thiết kế
**Công nghệ (lựa chọn của Claude):** Python 3.11+, giao diện web local bằng Gradio (mở trên trình duyệt), FFmpeg ghép video, Pillow xử lý ảnh, `google-genai` SDK.

**Pipeline (mỗi bước lưu kết quả ra thư mục project để chạy lại/sửa được):**
1. `fetch` — nguồn: (a) link chapter MangaDex qua API công khai (at-home server); (b) tải lên thư mục/nhiều file ảnh từ bất kỳ nguồn nào. Kiến trúc adapter để thêm site khác sau. Cắt ảnh webtoon dài thành các khung bằng dò dải nền trắng/đen giữa khung.
2. `analyze` — gửi các khung theo lô cho Gemini: mô tả cảnh, trích thoại, nhận diện nhân vật. Kèm từ điển nhân vật của bộ truyện.
3. `script` — Gemini viết kịch bản recap tiếng Việt dạng JSON: danh sách câu, mỗi câu gắn ID khung tranh minh họa. Cập nhật từ điển nhân vật (tên gốc → tên Việt).
4. `review` (UI) — người dùng xem/sửa câu, đổi khung, sửa tên.
5. `voice` — TTS từng câu → file audio + thời lượng.
6. `render` — FFmpeg: mỗi câu = khung tranh (zoom nhẹ) trên nền mờ, phụ đề theo thời lượng audio, watermark, nhạc nền tùy chọn; xuất 9:16 và/hoặc 16:9.

**Giọng đọc (lựa chọn của Claude):** mặc định `edge-tts` (giọng Việt HoaiMy/NamMinh, miễn phí, chất lượng tốt nhưng cần mạng); giữ giao diện TTS để sau thêm giọng chạy hoàn toàn offline.

**Vị trí code:** thư mục `comic-recap/` trong repo này.

## Để lại cho người build
Cách cắt khung chi tiết, prompt cho Gemini, hiệu ứng chuyển cảnh, font phụ đề, cấu trúc thư mục.

## Quyết định nguồn truyện
Người dùng chưa có nguồn quen; đã chọn: MangaDex + upload ảnh thủ công. Người dùng được lưu ý rủi ro bản quyền.
