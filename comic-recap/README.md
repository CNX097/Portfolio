# Comic Recap — biến truyện tranh thành video review

Dán link chapter MangaDex (hoặc tải ảnh lên) → AI (Gemini) đọc truyện, viết lời recap tiếng Việt → giọng đọc + phụ đề + watermark → video 9:16 (TikTok) / 16:9 (YouTube).

## Cài đặt trên Mac (làm 1 lần)

Mở ứng dụng **Terminal** và chạy lần lượt:

```bash
# 1. Cài Homebrew nếu chưa có (xem https://brew.sh), rồi:
brew install python@3.12 ffmpeg git

# 2. Tải code
git clone https://github.com/CNX097/Portfolio.git
cd Portfolio/comic-recap

# 3. Tạo môi trường và cài thư viện
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Chạy

```bash
cd Portfolio/comic-recap
source .venv/bin/activate
python -m comic_recap
```

Trình duyệt sẽ tự mở http://127.0.0.1:7860.

1. Tab **Cài đặt**: dán Gemini API key (lấy miễn phí tại https://aistudio.google.com/apikey) → Lưu.
2. Tab **1. Nguồn truyện**: dán link chapter MangaDex (dạng `https://mangadex.org/chapter/...`) hoặc kéo thả ảnh, nhập tên bộ truyện → Tải truyện.
3. Tab **2**: chọn độ dài → AI đọc truyện và viết kịch bản.
4. Tab **3. Chỉnh sửa**: sửa câu, đổi số khung tranh, sửa tên nhân vật → Lưu.
5. Tab **4. Xuất video**: chọn giọng, tỉ lệ, watermark, nhạc nền → Tạo video.

Dữ liệu lưu ở thư mục `~/ComicRecap` (dự án, video trong `projects/<tên>/out/`, từ điển tên nhân vật trong `characters/`).

## Lưu ý
- Gemini miễn phí có giới hạn lượt dùng mỗi phút/ngày; nếu báo giới hạn, đợi vài phút rồi bấm lại.
- Giọng đọc dùng dịch vụ Microsoft Edge TTS miễn phí, cần có mạng.
- Nội dung truyện có thể có bản quyền — bạn tự chịu trách nhiệm khi đăng tải.

## Phát triển
`pip install -e '.[dev]' && pytest`
