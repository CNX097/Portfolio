"""Text-to-speech (edge-tts by default)."""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from .project import Project

VOICES = {"Nữ - Hoài My": "vi-VN-HoaiMyNeural", "Nam - Nam Minh": "vi-VN-NamMinhNeural"}


async def edge_engine(text: str, voice: str, rate: str, out_path: Path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, voice, rate=rate).save(str(out_path))


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def synthesize_lines(p: Project, voice: str = "vi-VN-HoaiMyNeural", rate: str = "+10%",
                     engine=None, progress=None) -> None:
    engine = engine or edge_engine
    (p.root / "audio").mkdir(exist_ok=True)

    async def run() -> None:
        for i, line in enumerate(p.lines):
            rel = f"audio/{i:03d}.mp3"
            try:
                await engine(line.text, voice, rate, p.abs(rel))
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"Không tạo được giọng đọc (kiểm tra kết nối mạng): {e}") from e
            line.audio, line.duration = rel, probe_duration(p.abs(rel))
            if progress:
                progress(i + 1, len(p.lines))

    asyncio.run(run())
    p.save()
