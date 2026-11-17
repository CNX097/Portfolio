"""Compose frames with Pillow and encode the video with FFmpeg.

Each script line becomes one segment: blurred panel background + the panel
centered (slow zoom), subtitle and watermark drawn by Pillow (so FFmpeg does
not need libass/freetype), and that line's narration audio.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .project import Line, Project, slugify

FONT = Path(__file__).parent / "assets" / "BeVietnamPro-Bold.ttf"
SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080)}
FPS = 30


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def make_srt(lines: list[Line]) -> str:
    out, t = [], 0.0
    for i, line in enumerate(lines, 1):
        text = "\n".join(textwrap.wrap(line.text, 42)) or line.text
        out.append(f"{i}\n{_ts(t)} --> {_ts(t + line.duration)}\n{text}\n")
        t += line.duration
    return "\n".join(out)


def _frame(panel_path: Path, size: tuple[int, int]) -> Image.Image:
    W, H = size
    img = Image.open(panel_path).convert("RGB")
    bg_scale = max(W / img.width, H / img.height)
    bg = img.resize((int(img.width * bg_scale) + 1, int(img.height * bg_scale) + 1))
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(40))).enhance(0.55)
    fg_scale = min(W * 0.88 / img.width, H * 0.88 / img.height)
    fg = img.resize((int(img.width * fg_scale), int(img.height * fg_scale)), Image.LANCZOS)
    bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    return bg


def _wrap_px(text: str, font, max_w: int, draw) -> list[str]:
    words, rows, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            rows.append(cur)
            cur = w
    return rows + ([cur] if cur else [])


def _overlay(text: str, watermark: str, size: tuple[int, int]) -> Image.Image:
    W, H = size
    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    fs = int(min(W, H) * 0.045)
    font = ImageFont.truetype(str(FONT), fs)
    rows = _wrap_px(text, font, int(W * 0.86), d)
    line_h = int(fs * 1.3)
    y = int(H * 0.85) - line_h * len(rows)
    for row in rows:
        x = (W - d.textlength(row, font=font)) / 2
        d.text((x, y), row, font=font, fill="white", stroke_width=max(3, fs // 12), stroke_fill="black")
        y += line_h
    if watermark:
        wf = ImageFont.truetype(str(FONT), int(min(W, H) * 0.03))
        tw = d.textlength(watermark, font=wf)
        d.text((W - tw - W * 0.04, H * 0.04), watermark, font=wf, fill=(255, 255, 255, 150))
    return ov


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg lỗi: {r.stderr[-800:]}")


def _seg_seconds(line: Line) -> float:
    """Whole-frame segment length; lines without audio get a short silent beat."""
    dur = line.duration if line.audio and line.duration > 0 else 1.5
    return max(1, round(dur * FPS)) / FPS


def render_video(p: Project, aspect: Literal["9:16", "16:9"], watermark: str = "",
                 music: Path | None = None, progress=None) -> Path:
    """Video-only segments + one exact-length PCM audio track, muxed once (no A/V drift)."""
    if not p.lines:
        raise RuntimeError("Chưa có kịch bản để dựng video.")
    size = SIZES[aspect]
    W, H = size
    work = p.root / "out" / f"tmp_{aspect.replace(':', 'x')}"
    work.mkdir(parents=True, exist_ok=True)
    vsegs, asegs, timed = [], [], []
    for i, line in enumerate(p.lines):
        secs = _seg_seconds(line)
        n = round(secs * FPS)
        timed.append(Line(line.text, line.panel_id, line.audio, secs))
        frame, ov = work / f"f{i:03d}.png", work / f"o{i:03d}.png"
        vseg, aseg = work / f"v{i:03d}.mp4", work / f"a{i:03d}.wav"
        _frame(p.abs(p.panel(line.panel_id).path), size).save(frame)
        _overlay(line.text, watermark, size).save(ov)
        zoom = (
            f"[0:v]scale={W * 2}:{H * 2},zoompan=z='1+0.06*on/{n}':d={n}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}[z];"
            f"[z][1:v]overlay=0:0,format=yuv420p[v]"
        )
        _run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(frame), "-i", str(ov),
              "-filter_complex", zoom, "-map", "[v]", "-frames:v", str(n),
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS), str(vseg)])
        src = (["-i", str(p.abs(line.audio))] if line.audio and p.abs(line.audio).exists()
               else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"])
        _run(["ffmpeg", "-y", "-loglevel", "error", *src, "-af", f"apad=whole_dur={secs:.4f}",
              "-t", f"{secs:.4f}", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(aseg)])
        vsegs.append(vseg)
        asegs.append(aseg)
        if progress:
            progress(i + 1, len(p.lines))
    vlist, alist = work / "v.txt", work / "a.txt"
    vlist.write_text("".join(f"file '{s.name}'\n" for s in vsegs))
    alist.write_text("".join(f"file '{s.name}'\n" for s in asegs))
    video, voice = work / "video.mp4", work / "voice.wav"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(vlist), "-c", "copy", str(video)])
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(alist), "-c", "copy", str(voice)])
    out = p.root / "out" / f"{slugify(p.title)}_{aspect.replace(':', 'x')}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(voice)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                "[2:a]volume=-18dB[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]", "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    _run(cmd + ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)])
    out.with_suffix(".srt").write_text(make_srt(timed), "utf-8")
    return out
