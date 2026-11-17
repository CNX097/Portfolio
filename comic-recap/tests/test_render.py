import json
import shutil
import subprocess
import numpy as np
import pytest
from PIL import Image
from comic_recap.project import Project, Panel, Line
from comic_recap.render import make_srt, render_video

ff = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")


def test_make_srt():
    s = make_srt([Line("Cô gái tai thỏ kiệt sức", 0, duration=1.5), Line("Kết", 0, duration=2.0)])
    assert "1\n00:00:00,000 --> 00:00:01,500\nCô gái tai thỏ kiệt sức" in s
    assert "2\n00:00:01,500 --> 00:00:03,500\nKết" in s


def test_make_srt_wraps():
    s = make_srt([Line("một " * 20, 0, duration=1)])
    assert all(len(x) <= 42 for x in s.splitlines())


def _silence(path, sec):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", str(sec), str(path)], check=True)


def _probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True).stdout
    return json.loads(out)


@ff
@pytest.mark.parametrize("aspect,size", [("9:16", (1080, 1920)), ("16:9", (1920, 1080))])
def test_render(tmp_path, aspect, size):
    p = Project.create(tmp_path / "p", "Thử nghiệm")
    rng = np.random.default_rng(0)
    for i in range(2):
        Image.fromarray(rng.integers(0, 255, (900, 600, 3)).astype("uint8")).save(p.abs(f"panels/{i:03d}.png"))
        p.panels.append(Panel(i, f"panels/{i:03d}.png"))
        _silence(p.abs(f"audio/{i:03d}.mp3"), 1)
        p.lines.append(Line(f"Câu số {i} có dấu tiếng Việt", i, f"audio/{i:03d}.mp3", 1.0))
    out = render_video(p, aspect, watermark="Kênh Test")
    info = _probe(out)
    v = next(s for s in info["streams"] if "width" in s)
    assert (v["width"], v["height"]) == size
    assert abs(float(info["format"]["duration"]) - 2.0) < 0.3
    assert out.with_suffix(".srt").exists()


@ff
def test_av_in_sync_many_lines(tmp_path):
    p = Project.create(tmp_path / "p", "Sync")
    Image.new("RGB", (300, 400), "gray").save(p.abs("panels/000.png"))
    p.panels.append(Panel(0, "panels/000.png"))
    for i in range(12):
        _silence(p.abs(f"audio/{i:03d}.mp3"), 0.37)
        p.lines.append(Line("x", 0, f"audio/{i:03d}.mp3", 0.37))
    p.lines.append(Line("không có âm thanh", 0, "", 0.0))
    out = render_video(p, "16:9")
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", str(out)],
                       capture_output=True, text=True).stdout
    d = {s["codec_type"]: float(s["duration"]) for s in json.loads(o)["streams"]}
    assert abs(d["audio"] - d["video"]) < 0.06
