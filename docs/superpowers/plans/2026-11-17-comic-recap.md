# Comic Recap Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Local Mac tool: MangaDex link or uploaded images → Vietnamese recap video (voice, subtitles, watermark) in 9:16 / 16:9.

**Architecture:** Python package `comic_recap` with one module per pipeline stage (sources → split → ai → tts → render), all reading/writing a `Project` folder (`project.json` + `panels/`, `audio/`, `out/`). Gradio UI calls the stages. AI behind a `Provider` interface (Gemini now, Claude later).

**Tech Stack:** Python ≥3.11, `google-genai`, `edge-tts`, `gradio`, `Pillow`, `numpy`, `requests`, FFmpeg CLI (Homebrew), pytest.

**Spec:** `docs/superpowers/specs/2026-11-17-comic-recap-design.md`

## Global Constraints
- macOS, single user, everything under `comic-recap/`.
- AI default: Gemini; model name in config (default `gemini-2.5-flash`), key from env `GEMINI_API_KEY` or UI settings.
- TTS default `edge-tts`, voices `vi-VN-HoaiMyNeural` / `vi-VN-NamMinhNeural`.
- Output sizes: 1080×1920 (9:16), 1920×1080 (16:9), 30 fps, H.264 + AAC.
- All user-facing UI text in Vietnamese.
- Tests never hit the network (fake provider / mocked HTTP / fake TTS).

## Review Focus
- Very tall webtoon strip (e.g. 800×20000 px) → split into several panels, none taller than 3× width. (Task 2 test)
- Gemini returns JSON wrapped in ```json fences or with a bad panel id → parsed, bad ids clamped to a valid panel. (Task 4 test)
- Gemini free-tier rate limit (429) → retry with backoff, then a clear Vietnamese error, not a crash. (Task 4 test)
- Vietnamese diacritics in subtitles render correctly (font with Vietnamese glyphs, UTF-8 SRT). (Task 6 test)
- Invalid / non-MangaDex link → clear message, no traceback. (Task 3 test)

---

### Task 1: Scaffold + project model

**Files:** Create `comic-recap/pyproject.toml`, `comic-recap/README.md` (Vietnamese setup: brew install ffmpeg, python venv, pip install -e ., run), `comic-recap/comic_recap/__init__.py`, `comic_recap/project.py`, `tests/test_project.py`

**Interfaces — Produces:**
- `@dataclass Panel(id: int, path: str, description: str = "", dialogue: str = "")`
- `@dataclass Line(text: str, panel_id: int, audio: str = "", duration: float = 0.0)`
- `@dataclass Project(root: Path, title: str, panels: list[Panel], lines: list[Line], characters: dict[str,str])`
- `Project.create(root: Path, title: str) -> Project`, `Project.load(root) -> Project`, `project.save() -> None` (writes `project.json`, UTF-8, `ensure_ascii=False`)
- `load_characters(series: str, base: Path) -> dict[str,str]` / `save_characters(series, chars, base)` → `base/characters/<slug>.json`

- [ ] Test: `test_roundtrip` — create, add 2 panels + 1 line with "Tiếng Việt", save, load, equal. `test_characters_persist` — save {"Ghost":"U Linh"}, load returns same.
- [ ] Run `pytest comic-recap/tests/test_project.py -v` → FAIL
- [ ] Implement.
- [ ] Run → PASS. Commit `feat: project model`.

### Task 2: Panel splitter

**Files:** Create `comic_recap/split.py`, `tests/test_split.py`
**Interfaces — Produces:** `split_image(path: Path, out_dir: Path, start_id: int) -> list[Path]`

Algorithm: grayscale → per-row std-dev; rows with std < 4 and mean >240 or <15 are "gutter"; cut at middle of gutter runs ≥ 12 px; drop pieces < 80 px tall; any piece taller than 3×width is further cut at the lowest-variance row near each 2×width boundary. Images with height ≤ 1.5×width are kept whole.

- [ ] Tests (images generated with Pillow): `test_two_panels_white_gutter` → 2 files; `test_short_image_kept` → 1; `test_very_tall_no_gutter` (800×20000 noise) → every piece height ≤ 2400.
- [ ] Run → FAIL; implement; run → PASS; commit `feat: panel splitter`.

### Task 3: Sources (MangaDex + upload)

**Files:** Create `comic_recap/sources.py`, `tests/test_sources.py`
**Interfaces — Produces:**
- `class SourceError(Exception)` (Vietnamese message)
- `parse_mangadex_chapter_id(url: str) -> str` (accepts `mangadex.org/chapter/<uuid>[/...]`, else SourceError)
- `fetch_mangadex(url: str, dest: Path, session=requests) -> tuple[str, list[Path]]` → (series title, page files in order). Uses `GET https://api.mangadex.org/at-home/server/{id}` → `baseUrl + /data/{hash}/{file}`; title via `GET /chapter/{id}?includes[]=manga`. Sleep 0.2 s between pages; User-Agent `comic-recap/0.1`.
- `import_uploads(files: list[Path], dest: Path) -> list[Path]` — natural sort by filename (`2.jpg` before `10.jpg`), copy.

- [ ] Tests: parse valid/invalid URL (invalid → SourceError); `fetch_mangadex` with fake session returning canned JSON + bytes → 3 files in order; natural sort.
- [ ] FAIL → implement → PASS → commit `feat: sources`.

### Task 4: AI provider (Gemini) — analyze + script

**Files:** Create `comic_recap/ai.py`, `comic_recap/prompts.py`, `tests/test_ai.py`
**Interfaces:**
- Consumes: `Project`, `Panel`, `Line`.
- Produces:
  - `class Provider(Protocol): def generate(self, prompt: str, images: list[Path]) -> str`
  - `class GeminiProvider(Provider)(api_key: str, model: str = "gemini-2.5-flash")` using `google-genai` `client.models.generate_content`; on 429 retry 3× (5/15/45 s) then raise `AIError("Gemini đang giới hạn lượt dùng, thử lại sau ít phút.")`.
  - `parse_json(text: str) -> Any` (strips ``` fences)
  - `analyze_panels(p: Project, prov: Provider, batch: int = 8) -> None` — fills `description`, `dialogue`, merges detected names into `p.characters` (keep existing Vietnamese names; new ones get a Hán-Việt/Vietnamese-friendly transliteration from the model).
  - `write_script(p: Project, prov: Provider, target_seconds: int = 180) -> None` — sets `p.lines`; panel_id not in panels → nearest valid id.
- Prompts (Vietnamese recap style, energetic storyteller, third person, names from `characters`, ~2.5 words/sec for length) live in `prompts.py`.

- [ ] Tests with `FakeProvider` returning canned strings: fenced JSON parsed; analyze fills fields + characters; existing character name not overwritten; script with panel_id 999 clamped; provider raising 429-like error 4× → AIError (patch sleep).
- [ ] FAIL → implement → PASS → commit `feat: gemini analyze and script`.

### Task 5: TTS

**Files:** Create `comic_recap/tts.py`, `tests/test_tts.py`
**Interfaces — Produces:** `synthesize_lines(p: Project, voice: str = "vi-VN-HoaiMyNeural", rate: str = "+10%", engine=None) -> None` — writes `audio/NNN.mp3`, sets `line.audio`, `line.duration` (via `ffprobe`). `engine` is an async callable `(text, voice, rate, out_path)`; default wraps `edge_tts.Communicate(...).save`.

- [ ] Test with fake engine writing a 1 s silent mp3 (generated by ffmpeg `anullsrc`) → durations ≈ 1.0; skip test if ffmpeg missing.
- [ ] FAIL → implement → PASS → commit `feat: tts`.

### Task 6: Subtitles + render

**Files:** Create `comic_recap/render.py`, `comic_recap/assets/` (bundle `BeVietnamPro-Bold.ttf`, OFL), `tests/test_render.py`
**Interfaces — Produces:**
- `make_srt(lines: list[Line]) -> str` — cumulative timing, long lines wrapped at 42 chars.
- `render_video(p: Project, aspect: Literal["9:16","16:9"], watermark: str = "", music: Path | None = None) -> Path` → `out/<title>_<aspect>.mp4`.
- Per line: frame = blurred, darkened cover-scaled panel as background + panel fit-inside at 88% width/height, slow zoom 1.00→1.06 over line duration (`zoompan`); concat segments; burn subtitles (`subtitles` filter with the bundled font, white, black outline, bottom 15%); watermark text top-right 60% opacity; music mixed at -18 dB, looped, trimmed.

- [ ] Tests: `make_srt` timing for durations [1.5, 2.0] → `00:00:01,500` boundary; diacritics preserved; render 2 lines × 1 s with generated panels → mp4 exists, ffprobe size 1080×1920, duration ≈ 2 s (skip if no ffmpeg).
- [ ] FAIL → implement → PASS → commit `feat: render`.

### Task 7: Gradio UI

**Files:** Create `comic_recap/app.py`, `comic_recap/__main__.py` (`python -m comic_recap` → launch on 127.0.0.1:7860), `comic_recap/config.py` (settings in `~/.comic-recap/config.json`: api key, model, voice, watermark), `tests/test_app.py`
**Interfaces — Consumes:** all above.

Tabs (Vietnamese): **1. Nguồn truyện** (link MangaDex or upload ảnh, tên bộ truyện) → **2. Phân tích & kịch bản** (button runs split+analyze+script, progress) → **3. Chỉnh sửa** (editable table: câu thoại | khung | xem ảnh; character table gốc→Việt with "áp dụng lại tên") → **4. Xuất video** (voice, tỉ lệ, watermark, nhạc nền, buttons → video preview + download) → **Cài đặt** (Gemini key, model).

- [ ] Test: `build_app()` returns `gr.Blocks` without error; pipeline function `run_all(project, FakeProvider, fake tts)` produces lines with audio.
- [ ] Manual check: `python -m comic_recap`, run on 1 MangaDex chapter end to end, watch the video.
- [ ] Commit `feat: gradio ui`.
