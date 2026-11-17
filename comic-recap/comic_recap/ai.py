"""AI provider (Gemini) + analyze/script stages."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Protocol

from . import prompts
from .project import Line, Project

RETRY_WAITS = (5, 15, 45)


class AIError(Exception):
    pass


class Provider(Protocol):
    def generate(self, prompt: str, images: list[Path]) -> str: ...


def _is_rate_limit(e: Exception) -> bool:
    return getattr(e, "code", None) == 429 or "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)


def with_retry(fn: Callable[[], str]) -> str:
    for wait in (*RETRY_WAITS, None):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - provider SDK errors vary
            if not _is_rate_limit(e):
                raise AIError(f"Lỗi khi gọi AI: {e}") from e
            if wait is None:
                raise AIError("Gemini đang giới hạn lượt dùng, thử lại sau ít phút.") from e
            time.sleep(wait)
    raise AssertionError("unreachable")


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        if not api_key:
            raise AIError("Chưa có Gemini API key. Vào tab Cài đặt để nhập key.")
        from google import genai

        self._genai = genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, prompt: str, images: list[Path]) -> str:
        types = self._genai.types
        parts = [
            types.Part.from_bytes(data=Path(i).read_bytes(), mime_type=_mime(i)) for i in images
        ]
        cfg = types.GenerateContentConfig(response_mime_type="application/json")

        def call() -> str:
            r = self.client.models.generate_content(
                model=self.model, contents=[*parts, prompt], config=cfg
            )
            return r.text or ""

        return with_retry(call)


def _mime(p: Path) -> str:
    ext = Path(p).suffix.lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "image/png")


def parse_json(text: str) -> Any:
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise AIError("AI trả về dữ liệu không đọc được, hãy thử lại.")
        return json.loads(text[start : end + 1])


def analyze_panels(p: Project, prov: Provider, batch: int = 8, progress=None) -> None:
    by_id = {x.id: x for x in p.panels}
    for i in range(0, len(p.panels), batch):
        chunk = p.panels[i : i + batch]
        prompt = prompts.ANALYZE.format(
            title=p.title,
            ids=", ".join(str(x.id) for x in chunk),
            characters=json.dumps(p.characters, ensure_ascii=False) or "{}",
        )
        data = parse_json(prov.generate(prompt, [p.abs(x.path) for x in chunk]))
        for item in data.get("panels", []):
            panel = by_id.get(item.get("id"))
            if panel:
                panel.description = item.get("description", "")
                panel.dialogue = item.get("dialogue", "")
        for orig, vi in (data.get("characters") or {}).items():
            p.characters.setdefault(orig, vi)
        if progress:
            progress(min(i + batch, len(p.panels)), len(p.panels))
    p.save()


def write_script(p: Project, prov: Provider, target_seconds: int = 180) -> None:
    listing = "\n".join(
        f"[{x.id}] {x.description}" + (f' | thoại: "{x.dialogue}"' if x.dialogue else "")
        for x in p.panels
    )
    prompt = prompts.SCRIPT.format(
        title=p.title,
        characters=json.dumps(p.characters, ensure_ascii=False),
        words=int(target_seconds * 2.5),
        seconds=target_seconds,
        panels=listing,
    )
    data = parse_json(prov.generate(prompt, []))
    ids = sorted(x.id for x in p.panels)
    lines = []
    for item in data.get("lines", []):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        pid = item.get("panel_id", ids[0])
        if pid not in ids:
            pid = min(ids, key=lambda k: abs(k - (pid if isinstance(pid, int) else 0)))
        lines.append(Line(text, pid))
    if not lines:
        raise AIError("AI không viết được kịch bản, hãy thử lại.")
    p.lines = lines
    p.save()
