"""Chapter sources: MangaDex public API, or user-uploaded images."""
from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

import requests

API = "https://api.mangadex.org"
UA = {"User-Agent": "comic-recap/0.1"}
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class SourceError(Exception):
    pass


def parse_mangadex_chapter_id(url: str) -> str:
    m = re.search(rf"mangadex\.org/chapter/({_UUID})", url or "", re.I)
    if not m:
        raise SourceError(
            "Link không hợp lệ. Hãy dán link chapter MangaDex dạng "
            "https://mangadex.org/chapter/<mã-chapter>"
        )
    return m.group(1).lower()


def fetch_mangadex(url: str, dest: Path, session=requests) -> tuple[str, list[Path]]:
    cid = parse_mangadex_chapter_id(url)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        meta = _get(session, f"{API}/chapter/{cid}", params={"includes[]": "manga"}).json()
        title = _manga_title(meta)
        server = _get(session, f"{API}/at-home/server/{cid}").json()
        base, ch = server["baseUrl"], server["chapter"]
        files = []
        for i, name in enumerate(ch["data"]):
            r = _get(session, f"{base}/data/{ch['hash']}/{name}")
            f = dest / f"{i:03d}{Path(name).suffix or '.png'}"
            f.write_bytes(r.content)
            files.append(f)
            time.sleep(0.2)
    except SourceError:
        raise
    except (requests.RequestException, KeyError, ValueError) as e:
        raise SourceError(f"Không tải được chapter từ MangaDex: {e}") from e
    if not files:
        raise SourceError("Chapter này không có trang ảnh nào (có thể là link ngoài MangaDex).")
    return title, files


def _get(session, url, **kw):
    r = session.get(url, headers=UA, timeout=30, **kw)
    r.raise_for_status()
    return r


def _manga_title(meta: dict) -> str:
    for rel in meta.get("data", {}).get("relationships", []):
        if rel.get("type") == "manga":
            t = rel.get("attributes", {}).get("title", {})
            return t.get("en") or next(iter(t.values()), "Truyện")
    return "Truyện"


def _natural_key(p: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def import_uploads(files: list[Path], dest: Path) -> list[Path]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for i, f in enumerate(sorted(map(Path, files), key=_natural_key)):
        t = dest / f"{i:03d}{f.suffix.lower()}"
        shutil.copyfile(f, t)
        out.append(t)
    return out
