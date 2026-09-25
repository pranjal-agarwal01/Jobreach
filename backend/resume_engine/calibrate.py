"""
Find, per track, the largest type scale at which the resume still renders as exactly
one page.

Coarse-to-fine search: one renderer pass over a coarse grid for every track, then one
pass over the fine grid inside each track's fit/spill bracket. Two soffice runs in
total however many tracks there are, since renderer start-up dominates the cost.

Re-calibrate whenever the fact bank changes: a longer bullet at an unchanged scale is
exactly how a resume silently spills to page 2.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from .builder import build
from .pages import count_pages
from .schema import BuildOptions, ResumeData

# Below MIN_SCALE the right column drops under ~7pt. A resume that needs less than this
# to fit has too much on it: drop a line rather than shrink the type further.
MIN_SCALE = 0.88
MAX_SCALE = 1.20
COARSE_STEP = 0.04
FINE_STEP = 0.01

Counter = Callable[[Sequence[str]], dict[str, int]]


@dataclass
class Calibration:
    track: str
    scale: Optional[float]          # None: nothing fits, even at the smallest scale
    first_spill: Optional[float]    # None: fits at the largest scale tested
    tested: dict[float, int] = field(default_factory=dict)

    @property
    def capped(self) -> bool:
        """True when the track fit at every scale tested, so `scale` is the ceiling."""
        return self.scale is not None and self.first_spill is None


def grid(lo: float, hi: float, step: float) -> list[float]:
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 3) for i in range(n + 1) if lo + i * step <= hi + 1e-9]


def _pick(tested: dict[float, int]) -> tuple[Optional[float], Optional[float]]:
    rows = sorted(tested.items())
    first_spill = next((s for s, pages in rows if pages != 1), None)
    # Never step past a failure: if a smaller scale spilled, larger ones are not trusted.
    ok = [s for s, pages in rows if pages == 1 and (first_spill is None or s < first_spill)]
    return (ok[-1] if ok else None), first_spill


def calibrate(data: ResumeData, tracks: Optional[Sequence[str]] = None,
              lo: float = MIN_SCALE, hi: float = MAX_SCALE,
              coarse: float = COARSE_STEP, fine: float = FINE_STEP,
              counter: Counter = count_pages) -> dict[str, Calibration]:
    tracks = list(tracks or data.tracks)
    tested: dict[str, dict[float, int]] = {t: {} for t in tracks}

    with tempfile.TemporaryDirectory(prefix="calib-") as tmp:
        def measure(jobs: list[tuple[str, float]]) -> None:
            if not jobs:
                return
            paths: dict[tuple[str, float], str] = {}
            for n, (t, sc) in enumerate(jobs):
                path = os.path.join(tmp, "c{:04d}.docx".format(n))
                build(data, BuildOptions(track=t), path, scale=sc)
                paths[(t, sc)] = path
            counts = counter(list(paths.values()))
            for (t, sc), path in paths.items():
                tested[t][sc] = counts[path]
            for path in paths.values():
                os.remove(path)

        measure([(t, sc) for t in tracks for sc in grid(lo, hi, coarse)])

        fine_jobs = []
        for t in tracks:
            fit, spill = _pick(tested[t])
            if fit is not None and spill is not None:
                fine_jobs += [(t, sc) for sc in grid(fit, spill, fine) if fit < sc < spill]
        measure(fine_jobs)

    out = {}
    for t in tracks:
        scale, first_spill = _pick(tested[t])
        out[t] = Calibration(track=t, scale=scale, first_spill=first_spill,
                             tested=dict(sorted(tested[t].items())))
    return out


def apply(data: ResumeData, results: dict[str, Calibration]) -> ResumeData:
    """Return a copy of `data` with each calibrated track's scale set."""
    tracks = {k: v.model_copy() for k, v in data.tracks.items()}
    for t, cal in results.items():
        tracks[t].scale = cal.scale
    return data.model_copy(update={"tracks": tracks})
