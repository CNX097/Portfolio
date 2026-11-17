import json
import shutil
import subprocess
import numpy as np
import pytest
from PIL import Image
from comic_recap import pipeline
from comic_recap.project import Project, Line


class FakeProvider:
    def generate(self, prompt, images):
        if images:
            return json.dumps({"panels": [{"id": 0, "description": "d", "dialogue": ""}],
                               "characters": {"Ghost": "U Linh"}})
        return json.dumps({"lines": [{"text": "U Linh xuất hiện", "panel_id": 0}]})


async def fake_engine(text, voice, rate, out):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", "1", str(out)], check=True)


def test_build_app():
    import gradio as gr
    from comic_recap.app import build_app
    assert isinstance(build_app(), gr.Blocks)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")
def test_run_all(tmp_path):
    img = tmp_path / "1.png"
    Image.fromarray(np.random.default_rng(0).integers(0, 255, (900, 600, 3)).astype("uint8")).save(img)
    p = pipeline.from_uploads([img], "Solo", tmp_path)
    pipeline.prepare(p, FakeProvider(), tmp_path)
    assert pipeline.load_characters("Solo", tmp_path) == {"Ghost": "U Linh"}
    pipeline.voice(p, engine=fake_engine)
    out = pipeline.export(p, "9:16")
    assert out.exists() and p.lines[0].duration > 0


def test_rename_character(tmp_path):
    p = Project.create(tmp_path / "p", "S")
    p.characters = {"Ghost": "U Linh"}
    p.lines = [Line("U Linh tấn công", 0)]
    pipeline.update_characters(p, {"Ghost": "Bóng Ma"}, tmp_path)
    assert p.lines[0].text == "Bóng Ma tấn công"
    assert p.characters == {"Ghost": "Bóng Ma"}
