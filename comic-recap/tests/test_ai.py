import json
import pytest
from comic_recap.project import Project, Panel
from comic_recap import ai
from comic_recap.ai import parse_json, analyze_panels, write_script, AIError, with_retry


class FakeProvider:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def generate(self, prompt, images):
        self.calls.append((prompt, images))
        return self.replies.pop(0)


def _proj(tmp_path, n=3):
    p = Project.create(tmp_path / "p", "Solo")
    p.panels = [Panel(i, f"panels/{i:03d}.png") for i in range(n)]
    return p


def test_parse_json_fenced():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('blah {"a": [1]} tail') == {"a": [1]}


def test_analyze_fills_and_keeps_names(tmp_path):
    p = _proj(tmp_path)
    p.characters = {"Jin": "Tấn"}
    reply = json.dumps({"panels": [
        {"id": 0, "description": "cảnh 0", "dialogue": "Run!"},
        {"id": 1, "description": "cảnh 1", "dialogue": ""},
        {"id": 2, "description": "cảnh 2", "dialogue": "Ghost!"}],
        "characters": {"Jin": "Jin", "Ghost": "U Linh"}})
    analyze_panels(p, FakeProvider([reply]), batch=8)
    assert p.panels[0].description == "cảnh 0" and p.panels[2].dialogue == "Ghost!"
    assert p.characters == {"Jin": "Tấn", "Ghost": "U Linh"}


def test_analyze_batches(tmp_path):
    p = _proj(tmp_path, 3)
    prov = FakeProvider(['{"panels": [], "characters": {}}'] * 2)
    analyze_panels(p, prov, batch=2)
    assert [len(c[1]) for c in prov.calls] == [2, 1]


def test_script_clamps_panel_id(tmp_path):
    p = _proj(tmp_path)
    reply = '```json\n{"lines": [{"text": "Mở đầu", "panel_id": 0}, {"text": "Kết", "panel_id": 999}]}\n```'
    write_script(p, FakeProvider([reply]))
    assert [(l.text, l.panel_id) for l in p.lines] == [("Mở đầu", 0), ("Kết", 2)]


def test_rate_limit_retries_then_errors(monkeypatch):
    monkeypatch.setattr(ai.time, "sleep", lambda s: None)
    n = {"c": 0}

    class E(Exception):
        code = 429

    def f():
        n["c"] += 1
        raise E("429 RESOURCE_EXHAUSTED")

    with pytest.raises(AIError, match="giới hạn"):
        with_retry(f)
    assert n["c"] == 4


def test_parse_json_bad_raises_aierror():
    with pytest.raises(AIError):
        parse_json("{not json at all}")


def test_parse_json_list_wrapped():
    assert parse_json('[{"text": "a", "panel_id": 0}]') == {"items": [{"text": "a", "panel_id": 0}]}


def test_script_accepts_list_and_string_ids(tmp_path):
    p = _proj(tmp_path)
    write_script(p, FakeProvider(['[{"text": "A", "panel_id": "2"}, {"text": "B", "panel_id": "x"}]']))
    assert [(l.text, l.panel_id) for l in p.lines] == [("A", 2), ("B", 2)]


def test_analyze_string_ids(tmp_path):
    p = _proj(tmp_path)
    analyze_panels(p, FakeProvider(['{"panels": [{"id": "1", "description": "d1"}]}']))
    assert p.panels[1].description == "d1"


def test_retries_503(monkeypatch):
    monkeypatch.setattr(ai.time, "sleep", lambda s: None)
    n = {"c": 0}

    class E(Exception):
        code = 503

    def f():
        n["c"] += 1
        if n["c"] < 3:
            raise E("503 UNAVAILABLE")
        return "ok"

    assert with_retry(f) == "ok"


def test_image_bytes_downscaled(tmp_path):
    from PIL import Image
    import numpy as np
    f = tmp_path / "big.png"
    Image.fromarray(np.random.default_rng(0).integers(0, 255, (4000, 1000, 3)).astype("uint8")).save(f)
    data, mime = ai.image_payload(f)
    assert mime == "image/jpeg" and len(data) < 1_500_000
    import io
    assert max(Image.open(io.BytesIO(data)).size) <= 1600
