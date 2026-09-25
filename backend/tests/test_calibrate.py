"""Calibration logic against a fake renderer, so it runs without LibreOffice."""
import zipfile

from resume_engine import calibrate as cal
from resume_engine.schema import BuildOptions

from .conftest import PROFILES, load_profile


def _font_size_counter(limit_half_points):
    """Fake renderer: one page while the name (the document's first sized run) is at
    most `limit` half-points. The name is 19pt * scale, so 39 flips between 1.04 and 1.05."""
    import re

    def count(paths):
        out = {}
        for p in paths:
            xml = zipfile.ZipFile(p).read("word/document.xml").decode()
            name_size = int(re.search(r'<w:sz w:val="(\d+)"/>', xml).group(1))
            out[p] = 1 if name_size <= limit_half_points else 2
        return out
    return count


def test_grid():
    assert cal.grid(0.88, 1.20, 0.04) == [0.88, 0.92, 0.96, 1.0, 1.04, 1.08, 1.12, 1.16, 1.2]
    assert cal.grid(1.08, 1.12, 0.01) == [1.08, 1.09, 1.1, 1.11, 1.12]


def test_pick_never_steps_past_a_failure():
    assert cal._pick({1.0: 1, 1.04: 1, 1.08: 2, 1.12: 1}) == (1.04, 1.08)
    assert cal._pick({1.0: 2, 1.04: 1}) == (None, 1.0)
    assert cal._pick({1.0: 1, 1.2: 1}) == (1.2, None)


def test_coarse_to_fine_finds_boundary_and_flags_extremes():
    data = load_profile(PROFILES[0])
    r = cal.calibrate(data, counter=_font_size_counter(39))["sde"]
    assert (r.scale, r.first_spill) == (1.04, 1.05)
    assert not r.capped

    capped = cal.calibrate(data, counter=_font_size_counter(99))["sde"]
    assert capped.scale == cal.MAX_SCALE and capped.capped

    none_fit = cal.calibrate(data, counter=_font_size_counter(1))["sde"]
    assert none_fit.scale is None


def test_apply_sets_scale_without_mutating_input():
    data = load_profile(PROFILES[0])
    res = {"sde": cal.Calibration(track="sde", scale=1.07, first_spill=1.08)}
    out = cal.apply(data, res)
    assert out.tracks["sde"].scale == 1.07
    assert data.tracks["sde"].scale is None
    BuildOptions(track="sde")  # still a valid track
