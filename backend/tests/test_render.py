"""Phase 0 acceptance on the real renderer: every synthetic profile calibrates and
builds to exactly one page, and an overfull profile is reported as not fitting.

On a machine that has Calibri (Windows with Office), fonts are swapped to Carlito so
the test renders the way the Linux server will.
"""
import functools
import sys

import pytest

from resume_engine import calibrate as cal
from resume_engine.builder import build
from resume_engine.pages import count_pages
from resume_engine.schema import BuildOptions, Bullet, Item, LeftSection

from .conftest import PROFILES, load_profile, requires_renderer

SUBST = {"Calibri": "Carlito"} if sys.platform == "win32" else None
counter = functools.partial(count_pages, substitute_fonts=SUBST)


@requires_renderer
@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_profile_calibrates_to_one_page(path, tmp_path):
    data = load_profile(path)
    results = cal.calibrate(data, counter=counter)
    calibrated = cal.apply(data, results)
    paths = {}
    for track, r in results.items():
        assert r.scale is not None, "{} track {} fits at no scale: {}".format(path.stem, track, r.tested)
        out = tmp_path / "{}.docx".format(track)
        build(calibrated, BuildOptions(track=track), str(out))
        paths[track] = str(out)
    pages = counter(list(paths.values()))
    for track, p in paths.items():
        print("{:<32} {:<10} scale {:.2f}{}".format(
            path.stem, track, results[track].scale, "  (ceiling)" if results[track].capped else ""))
        assert pages[p] == 1


@requires_renderer
def test_overfull_profile_fits_at_no_scale():
    data = load_profile(next(p for p in PROFILES if "rohan" in p.stem))
    long_text = ("Rebuilt the same subsystem again with a different approach and measured it "
                 "against the previous version on the same workload for comparison purposes.")
    for n in range(6):
        iid = "extra{}".format(n)
        data.items[iid] = Item(id=iid, name="Extra Project {}".format(n), tagline="Filler",
                               period="Jan 2025 – Feb 2025", stack="Python",
                               bullets=[Bullet(id="{}.b{}".format(iid, i), text=long_text)
                                        for i in range(5)])
    data.tracks["fullstack"].left_sections = [
        LeftSection(heading="Projects",
                    item_ids=["splitsy", "tutorlink", "pixelforge"] + ["extra{}".format(n) for n in range(6)])]
    r = cal.calibrate(data, tracks=["fullstack"], counter=counter)["fullstack"]
    assert r.scale is None
