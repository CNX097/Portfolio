"""AI provider (Gemini) + analyze/script stages."""
from __future__ import annotations

import io
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


def _is_transient(e: Exception) -> bool:
    return _is_rate_limit(e) or getattr(e, "code", None) in (500, 502, 503, 504) or "UNAVAILABLE" in str(e)


def with_retry(fn: Callable[[], str]) -> str:
    for wait in (*RETRY_WAITS, None):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - provider SDK errors vary
            if not _is_transient(e):
                raise AIError(f"Lỗi khi gọi AI: {e}") from e
            if wait is None:
                if _is_rate_limit(e):
                    raise AIError("Gemini đang giới hạn lượt dùng, thử lại sau ít phút.") from e
                raise AIError("Máy chủ Gemini đang quá tải, thử lại sau ít phút.") from e
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
        parts = []
        for i in images:
            data, mime = image_payload(i)
            parts.append(types.Part.from_bytes(data=data, mime_type=mime))
        cfg = types.GenerateContentConfig(response_mime_type="application/json")

        def call() -> str:
            r = self.client.models.generate_content(
                model=self.model, contents=[*parts, prompt], config=cfg
            )
            return r.text or ""

        return with_retry(call)


def image_payload(path: Path, max_side: int = 1600) -> tuple[bytes, str]:
    """Downscale + JPEG so a batch stays well under Gemini's inline size limit."""
    from PIL import Image

    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


def _as_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_json(text: str) -> dict:
    """Parse model JSON; always returns a dict (a bare list becomes {"items": [...]})."""
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    bad = AIError("AI trả về dữ liệu không đọc được, hãy thử lại.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
        end = max(text.rfind("}"), text.rfind("]"))
        if start == -1 or end <= start:
            raise bad
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            raise bad from e
    if isinstance(data, list):
        data = {"items": data}
    if not isinstance(data, dict):
        raise bad
    return data


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
        for item in data.get("panels") or data.get("items") or []:
            if not isinstance(item, dict):
                continue
            panel = by_id.get(_as_int(item.get("id")))
            if panel:
                panel.description = item.get("description", "")
                panel.dialogue = item.get("dialogue", "")
        chars = data.get("characters")
        for orig, vi in (chars if isinstance(chars, dict) else {}).items():
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
    lines: list[Line] = []
    for item in data.get("lines") or data.get("items") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        pid = _as_int(item.get("panel_id"))
        if pid is None:
            pid = lines[-1].panel_id if lines else ids[0]
        elif pid not in ids:
            pid = min(ids, key=lambda k: abs(k - pid))
        lines.append(Line(text, pid))
    if not lines:
        raise AIError("AI không viết được kịch bản, hãy thử lại.")
    p.lines = lines
    p.save()
