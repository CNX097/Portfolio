"""User settings in ~/.comic-recap/config.json; data in ~/ComicRecap."""
from __future__ import annotations

import json
from pathlib import Path

CONFIG = Path.home() / ".comic-recap" / "config.json"
DATA = Path.home() / "ComicRecap"
DEFAULTS = {
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "voice": "vi-VN-HoaiMyNeural",
    "rate": "+10%",
    "watermark": "",
    "target_seconds": 180,
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG.exists():
        cfg.update(json.loads(CONFIG.read_text("utf-8")))
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
    CONFIG.chmod(0o600)
