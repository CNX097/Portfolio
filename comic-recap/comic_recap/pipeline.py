"""Glue between stages; used by the UI."""
from __future__ import annotations

import time
from pathlib import Path

from . import ai, render, sources, split, tts
from .project import Panel, Project, load_characters, save_characters, slugify

__all__ = ["from_url", "from_uploads", "prepare", "voice", "export", "update_characters", "load_characters"]


def _new(title: str, base: Path) -> Project:
    root = Path(base) / "projects" / f"{time.strftime('%Y%m%d-%H%M%S')}-{slugify(title)}"
    return Project.create(root, title)


def _add_pages(p: Project, pages: list[Path]) -> None:
    p.panels = []
    for page in pages:
        for f in split.split_image(page, p.root / "panels", len(p.panels)):
            p.panels.append(Panel(len(p.panels), str(f.relative_to(p.root))))
    p.save()


def from_url(url: str, base: Path, title: str = "") -> Project:
    tmp = Path(base) / "downloads" / sources.parse_mangadex_chapter_id(url)
    series, pages = sources.fetch_mangadex(url, tmp)
    p = _new(title or series, base)
    _add_pages(p, pages)
    return p


def from_uploads(files: list[Path], title: str, base: Path) -> Project:
    p = _new(title or "Truyện", base)
    _add_pages(p, sources.import_uploads(files, p.root / "pages"))
    return p


def prepare(p: Project, prov, base: Path, target_seconds: int = 180, progress=None) -> None:
    p.characters = {**load_characters(p.title, base), **p.characters}
    ai.analyze_panels(p, prov, progress=progress)
    save_characters(p.title, p.characters, base)
    ai.write_script(p, prov, target_seconds)


def update_characters(p: Project, new: dict[str, str], base: Path) -> None:
    for orig, vi in new.items():
        old = p.characters.get(orig)
        if old and vi and old != vi:
            for line in p.lines:
                line.text = line.text.replace(old, vi)
    p.characters = {k: v for k, v in new.items() if k and v}
    save_characters(p.title, p.characters, base)
    p.save()


def voice(p: Project, voice: str = "vi-VN-HoaiMyNeural", rate: str = "+10%", engine=None, progress=None) -> None:
    tts.synthesize_lines(p, voice, rate, engine=engine, progress=progress)


def export(p: Project, aspect: str, watermark: str = "", music: Path | None = None, progress=None) -> Path:
    return render.render_video(p, aspect, watermark, music, progress=progress)
