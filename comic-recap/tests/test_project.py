from comic_recap.project import Project, Panel, Line, load_characters, save_characters


def test_roundtrip(tmp_path):
    p = Project.create(tmp_path / "p", "Truyện A")
    p.panels += [Panel(0, "panels/000.png"), Panel(1, "panels/001.png", "cảnh", "hi")]
    p.lines.append(Line("Tiếng Việt có dấu", 1, "audio/000.mp3", 2.5))
    p.save()
    q = Project.load(tmp_path / "p")
    assert q == p
    assert "Tiếng Việt" in (tmp_path / "p" / "project.json").read_text("utf-8")


def test_characters_persist(tmp_path):
    save_characters("Solo Leveling!", {"Ghost": "U Linh"}, tmp_path)
    assert load_characters("Solo Leveling!", tmp_path) == {"Ghost": "U Linh"}
    assert load_characters("khác", tmp_path) == {}
