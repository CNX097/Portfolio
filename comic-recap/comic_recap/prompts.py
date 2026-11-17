"""Prompts for Gemini (Vietnamese recap style)."""

ANALYZE = """Bạn là trợ lý phân tích truyện tranh. Ảnh đính kèm là các khung tranh liên tiếp của truyện "{title}", theo thứ tự, mang mã: {ids}.

Nhân vật đã biết (tên gốc -> tên tiếng Việt dùng khi kể): {characters}

Với MỖI khung tranh, hãy:
- "description": mô tả ngắn gọn bằng tiếng Việt chuyện gì xảy ra (ai, làm gì, cảm xúc, hành động).
- "dialogue": chép lại lời thoại/chữ trong khung (giữ ngôn ngữ gốc), để trống nếu không có.
Liệt kê nhân vật có tên xuất hiện trong "characters": tên gốc -> tên tiếng Việt dễ nghe (phiên âm Hán-Việt cho tên Trung/Hàn khi hợp lý, ví dụ "Shadow Ghost" -> "U Linh Bóng Tối"). Giữ nguyên tên tiếng Việt cho nhân vật đã biết. Nhân vật chưa rõ tên thì mô tả theo đặc điểm (vd. "chàng trai tóc đen") trong description, không thêm vào characters.

Chỉ trả lời JSON đúng dạng:
{{"panels": [{{"id": 0, "description": "...", "dialogue": "..."}}], "characters": {{"Tên gốc": "Tên Việt"}}}}"""

SCRIPT = """Bạn là người dẫn kênh review/recap truyện tranh trên TikTok và YouTube, giọng kể cuốn hút, giàu cảm xúc, kịch tính.
Viết lời thuyết minh tiếng Việt kể lại chapter truyện "{title}" dựa trên danh sách khung tranh dưới đây.

Yêu cầu:
- Kể ở ngôi thứ ba như kể chuyện, KHÔNG đọc lại nguyên văn lời thoại; diễn giải tự nhiên.
- Câu mở đầu phải gây tò mò, giữ chân người xem ngay từ giây đầu.
- Dùng đúng tên tiếng Việt của nhân vật: {characters}
- Mỗi câu ngắn gọn (dưới 30 từ), dễ đọc thành tiếng, không dùng ký tự đặc biệt, không emoji.
- Mỗi câu gắn với "panel_id" là khung tranh minh họa phù hợp nhất; đi theo thứ tự truyện, có thể bỏ qua khung không quan trọng.
- Tổng độ dài khoảng {words} từ (khoảng {seconds} giây đọc).

Khung tranh:
{panels}

Chỉ trả lời JSON đúng dạng:
{{"lines": [{{"text": "...", "panel_id": 0}}]}}"""
