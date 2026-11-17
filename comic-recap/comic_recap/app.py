"""Gradio web UI (Vietnamese)."""
from __future__ import annotations

from pathlib import Path

import gradio as gr

from . import pipeline
from .ai import AIError, GeminiProvider
from .config import DATA, load_config, save_config
from .project import Line, Project
from .sources import SourceError
from .tts import VOICES

USER_ERRORS = (AIError, SourceError, RuntimeError)


def _load(root: str) -> Project:
    if not root:
        raise gr.Error("Chưa có dự án. Hãy tải truyện ở tab 1 trước.")
    return Project.load(Path(root))


def _gallery(p: Project):
    return [(str(p.abs(x.path)), f"Khung {x.id}") for x in p.panels]


def _lines_table(p: Project):
    return [[l.text, l.panel_id] for l in p.lines]


def _chars_table(p: Project):
    return [[k, v] for k, v in p.characters.items()] or [["", ""]]


def _guard(fn):
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except USER_ERRORS as e:
            raise gr.Error(str(e)) from e
    wrapper.__name__ = fn.__name__
    return wrapper


def _rows(df) -> list[list]:
    if df is None:
        return []
    if hasattr(df, "values"):
        return df.values.tolist()
    return list(df)


@_guard
def load_source(url, files, title, progress=gr.Progress()):
    progress(0, desc="Đang tải truyện...")
    if files:
        p = pipeline.from_uploads([Path(f) for f in files], title, DATA)
    elif url:
        p = pipeline.from_url(url.strip(), DATA, title)
    else:
        raise gr.Error("Hãy dán link MangaDex hoặc tải ảnh lên.")
    return str(p.root), _gallery(p), f"Đã tải {len(p.panels)} khung tranh — truyện: {p.title}"


@_guard
def analyze(root, seconds, progress=gr.Progress()):
    p, cfg = _load(root), load_config()
    prov = GeminiProvider(cfg["gemini_api_key"], cfg["gemini_model"])
    cb = lambda d, n: progress(d / max(n, 1), desc=f"AI đang đọc tranh {d}/{n}")
    pipeline.prepare(p, prov, DATA, int(seconds), progress=cb)
    progress(1, desc="Xong")
    return _lines_table(p), _chars_table(p), _gallery(p), f"Kịch bản có {len(p.lines)} câu."


def open_edit(root):
    if not root:
        return [], [["", ""]], []
    p = _load(root)
    return _lines_table(p), _chars_table(p), _gallery(p)


@_guard
def save_edits(root, lines_df, chars_df):
    p = _load(root)
    ids = {x.id for x in p.panels}
    lines = []
    for text, pid in _rows(lines_df):
        text = str(text or "").strip()
        if not text:
            continue
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            pid = min(ids)
        lines.append(Line(text, pid if pid in ids else min(ids)))
    p.lines = lines
    pipeline.update_characters(
        p, {str(a).strip(): str(b).strip() for a, b in _rows(chars_df) if a and b}, DATA
    )
    return _lines_table(p), _chars_table(p), "Đã lưu chỉnh sửa."


@_guard
def make_video(root, voice_label, aspects, watermark, music, progress=gr.Progress()):
    p, cfg = _load(root), load_config()
    if not p.lines:
        raise gr.Error("Chưa có kịch bản. Hãy chạy bước 2 trước.")
    if not aspects:
        raise gr.Error("Chọn ít nhất một tỉ lệ video.")
    cfg.update(voice=VOICES[voice_label], watermark=watermark)
    save_config(cfg)
    pipeline.voice(p, cfg["voice"], cfg["rate"],
                   progress=lambda d, n: progress(d / n * 0.3, desc=f"Tạo giọng đọc {d}/{n}"))
    outs = []
    for k, a in enumerate(aspects):
        outs.append(pipeline.export(
            p, a, watermark, Path(music) if music else None,
            progress=lambda d, n: progress(0.3 + 0.7 * (k + d / n) / len(aspects), desc=f"Dựng video {a}: {d}/{n}"),
        ))
    files = [str(o) for o in outs] + [str(o.with_suffix(".srt")) for o in outs]
    return str(outs[0]), files, f"Xong! Video lưu tại: {outs[0].parent}"


def save_settings(key, model, seconds):
    cfg = load_config()
    cfg.update(gemini_api_key=key.strip(), gemini_model=model.strip(), target_seconds=int(seconds))
    save_config(cfg)
    return "Đã lưu cài đặt."


def build_app() -> gr.Blocks:
    cfg = load_config()
    voice_label = next((k for k, v in VOICES.items() if v == cfg["voice"]), next(iter(VOICES)))
    with gr.Blocks(title="Comic Recap") as app:
        root = gr.State("")
        gr.Markdown("# Comic Recap — biến truyện tranh thành video review")
        with gr.Tab("1. Nguồn truyện"):
            url = gr.Textbox(label="Link chapter MangaDex", placeholder="https://mangadex.org/chapter/...")
            files = gr.File(label="…hoặc tải ảnh lên (theo thứ tự tên file)", file_count="multiple", file_types=["image"])
            title = gr.Textbox(label="Tên bộ truyện (dùng để nhớ tên nhân vật)")
            b1 = gr.Button("Tải truyện", variant="primary")
            msg1 = gr.Markdown()
            gal1 = gr.Gallery(label="Khung tranh", columns=6, height=400)
        with gr.Tab("2. Phân tích & kịch bản"):
            secs = gr.Slider(30, 600, value=cfg["target_seconds"], step=10, label="Độ dài video mong muốn (giây)")
            b2 = gr.Button("AI đọc truyện và viết kịch bản", variant="primary")
            msg2 = gr.Markdown()
        with gr.Tab("3. Chỉnh sửa") as tab3:
            with gr.Row():
                with gr.Column(scale=3):
                    lines = gr.Dataframe(headers=["Câu thuyết minh", "Khung"], datatype=["str", "number"],
                                         col_count=(2, "fixed"), interactive=True, wrap=True, label="Kịch bản")
                    chars = gr.Dataframe(headers=["Tên gốc", "Tên tiếng Việt"], col_count=(2, "fixed"),
                                         interactive=True, label="Tên nhân vật (đổi tên Việt sẽ cập nhật cả kịch bản)")
                    b3 = gr.Button("Lưu chỉnh sửa", variant="primary")
                    msg3 = gr.Markdown()
                with gr.Column(scale=2):
                    gal3 = gr.Gallery(label="Khung tranh (số khung để điền vào cột Khung)", columns=3, height=700)
        with gr.Tab("4. Xuất video"):
            voice = gr.Radio(list(VOICES), value=voice_label, label="Giọng đọc")
            aspects = gr.CheckboxGroup(["9:16", "16:9"], value=["9:16"], label="Tỉ lệ (9:16 TikTok, 16:9 YouTube)")
            wm = gr.Textbox(value=cfg["watermark"], label="Watermark (tên kênh)")
            music = gr.File(label="Nhạc nền (tuỳ chọn, mp3)", file_types=["audio"], type="filepath")
            b4 = gr.Button("Tạo video", variant="primary")
            msg4 = gr.Markdown()
            video = gr.Video(label="Xem trước")
            outs = gr.File(label="Tải về (video + phụ đề .srt)", file_count="multiple")
        with gr.Tab("Cài đặt"):
            gr.Markdown("Lấy Gemini API key miễn phí tại https://aistudio.google.com/apikey")
            key = gr.Textbox(value=cfg["gemini_api_key"], type="password", label="Gemini API key")
            model = gr.Textbox(value=cfg["gemini_model"], label="Model Gemini")
            secs2 = gr.Number(value=cfg["target_seconds"], label="Độ dài mặc định (giây)")
            b5 = gr.Button("Lưu cài đặt")
            msg5 = gr.Markdown()

        b1.click(load_source, [url, files, title], [root, gal1, msg1])
        b2.click(analyze, [root, secs], [lines, chars, gal3, msg2])
        tab3.select(open_edit, [root], [lines, chars, gal3])
        b3.click(save_edits, [root, lines, chars], [lines, chars, msg3])
        b4.click(make_video, [root, voice, aspects, wm, music], [video, outs, msg4])
        b5.click(save_settings, [key, model, secs2], [msg5])
    return app


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    build_app().queue().launch(server_name="127.0.0.1", server_port=7860, inbrowser=True,
                               allowed_paths=[str(DATA)])
