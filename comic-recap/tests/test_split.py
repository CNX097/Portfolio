import numpy as np
from PIL import Image
from comic_recap.split import split_image


def _save(arr, p):
    Image.fromarray(arr.astype("uint8")).save(p)
    return p


def _noise(h, w, rng):
    return rng.integers(0, 255, (h, w, 3))


def test_two_panels_white_gutter(tmp_path):
    rng = np.random.default_rng(0)
    img = np.vstack([_noise(900, 600, rng), np.full((60, 600, 3), 255), _noise(900, 600, rng)])
    out = split_image(_save(img, tmp_path / "a.png"), tmp_path / "o", 0)
    assert len(out) == 2


def test_short_image_kept(tmp_path):
    rng = np.random.default_rng(1)
    img = np.vstack([_noise(300, 600, rng), np.full((60, 600, 3), 255), _noise(300, 600, rng)])
    out = split_image(_save(img, tmp_path / "a.png"), tmp_path / "o", 5)
    assert len(out) == 1 and out[0].name == "005.png"


def test_very_tall_no_gutter(tmp_path):
    rng = np.random.default_rng(2)
    out = split_image(_save(_noise(20000, 800, rng), tmp_path / "a.png"), tmp_path / "o", 0)
    assert len(out) > 1
    for p in out:
        assert Image.open(p).height <= 2400


def test_large_blank_gap_not_a_panel(tmp_path):
    rng = np.random.default_rng(3)
    img = np.vstack([_noise(900, 600, rng), np.full((400, 600, 3), 255), _noise(900, 600, rng)])
    out = split_image(_save(img, tmp_path / "a.png"), tmp_path / "o", 0)
    assert len(out) == 2


def test_unsupported_image_raises_source_error(tmp_path):
    import pytest
    from comic_recap.sources import SourceError
    bad = tmp_path / "x.heic"
    bad.write_bytes(b"not an image")
    with pytest.raises(SourceError, match="không hỗ trợ"):
        split_image(bad, tmp_path / "o", 0)
