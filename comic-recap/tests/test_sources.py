import pytest
from comic_recap.sources import SourceError, parse_mangadex_chapter_id, fetch_mangadex, import_uploads

CID = "a54c491c-8e4c-4e97-8873-5b79e59da210"


def test_parse_valid():
    assert parse_mangadex_chapter_id(f"https://mangadex.org/chapter/{CID}/2") == CID


@pytest.mark.parametrize("u", ["https://example.com/x", "mangadex.org/title/abc", ""])
def test_parse_invalid(u):
    with pytest.raises(SourceError):
        parse_mangadex_chapter_id(u)


class Resp:
    def __init__(self, json=None, content=b""):
        self._j, self.content, self.status_code = json, content, 200

    def json(self):
        return self._j

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self):
        self.urls = []

    def get(self, url, **kw):
        self.urls.append(url)
        if "at-home" in url:
            return Resp({"baseUrl": "https://h", "chapter": {"hash": "H", "data": ["1.png", "2.png", "3.png"]}})
        if "/chapter/" in url:
            return Resp({"data": {"attributes": {"chapter": "5"}, "relationships": [
                {"type": "manga", "attributes": {"title": {"en": "Solo"}}}]}})
        return Resp(content=url.encode())


def test_fetch_mangadex(tmp_path, monkeypatch):
    monkeypatch.setattr("comic_recap.sources.time.sleep", lambda s: None)
    title, files = fetch_mangadex(f"https://mangadex.org/chapter/{CID}", tmp_path, FakeSession())
    assert title == "Solo"
    assert [f.read_bytes() for f in files] == [b"https://h/data/H/1.png", b"https://h/data/H/2.png", b"https://h/data/H/3.png"]


def test_import_natural_sort(tmp_path):
    src = tmp_path / "s"
    src.mkdir()
    for n in ["10.jpg", "2.jpg", "1.jpg"]:
        (src / n).write_bytes(n.encode())
    out = import_uploads([src / "10.jpg", src / "2.jpg", src / "1.jpg"], tmp_path / "d")
    assert [f.read_bytes() for f in out] == [b"1.jpg", b"2.jpg", b"10.jpg"]
