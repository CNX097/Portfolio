"""Project folder model: project.json + panels/, audio/, out/."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Panel:
    id: int
    path: str
    description: str = ""
    dialogue: str = ""


@dataclass
class Line:
    text: str
    panel_id: int
    audio: str = ""
    duration: float = 0.0


@dataclass
class Project:
    root: Path
    title: str
    panels: list[Panel] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    characters: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(cls, root: Path, title: str) -> "Project":
        root = Path(root)
        for sub in ("panels", "pages", "audio", "out"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        p = cls(root, title)
        p.save()
        return p

    @classmethod
    def load(cls, root: Path) -> "Project":
        root = Path(root)
        d = json.loads((root / "project.json").read_text("utf-8"))
        return cls(
            root,
            d["title"],
            [Panel(**x) for x in d.get("panels", [])],
            [Line(**x) for x in d.get("lines", [])],
            d.get("characters", {}),
        )

    def save(self) -> None:
        d = {
            "title": self.title,
            "panels": [asdict(x) for x in self.panels],
            "lines": [asdict(x) for x in self.lines],
            "characters": self.characters,
        }
        (self.root / "project.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=2), "utf-8"
        )

    def abs(self, rel: str) -> Path:
        return self.root / rel

    def panel(self, pid: int) -> Panel:
        return next(x for x in self.panels if x.id == pid)


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "untitled"


def _char_file(series: str, base: Path) -> Path:
    return Path(base) / "characters" / f"{slugify(series)}.json"


def load_characters(series: str, base: Path) -> dict[str, str]:
    f = _char_file(series, base)
    return json.loads(f.read_text("utf-8")) if f.exists() else {}


def save_characters(series: str, chars: dict[str, str], base: Path) -> None:
    f = _char_file(series, base)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(chars, ensure_ascii=False, indent=2), "utf-8")
