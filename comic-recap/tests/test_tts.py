import shutil
import subprocess
import pytest
from comic_recap.project import Project, Line
from comic_recap.tts import synthesize_lines

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")


async def fake_engine(text, voice, rate, out_path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", "1", str(out_path)], check=True)


def test_synthesize(tmp_path):
    p = Project.create(tmp_path / "p", "T")
    p.lines = [Line("Xin chào", 0), Line("Tạm biệt", 0)]
    synthesize_lines(p, engine=fake_engine)
    assert [l.audio for l in p.lines] == ["audio/000.mp3", "audio/001.mp3"]
    assert all(abs(l.duration - 1.0) < 0.1 for l in p.lines)
