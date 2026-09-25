"""
Parity test: does the LibreOffice + Carlito page check agree with Microsoft Word?

The server cannot run Word, so the product trusts LibreOffice. This measures whether
that trust is earned, on the reference baselines and on tailored variants built across
a grid of scales that straddles the one-page boundary.

Runs on a Windows machine with both Word and LibreOffice installed:

    python scripts/parity_check.py build            # candidates + manifest
    powershell -File scripts/word_pages.ps1 -Manifest out/parity/manifest.json -Out out/parity/word.json
    python scripts/parity_check.py lo --font carlito  # LibreOffice with Calibri renamed to Carlito
    python scripts/parity_check.py lo --font native   # LibreOffice with the real Calibri
    python scripts/parity_check.py report           # compare; exit 1 on a false fit

The server has no Calibri and renders with Carlito, so the carlito run is the one the
acceptance check is about. The native run separates renderer differences from font
differences.

A "false fit" (LibreOffice says one page, Word says two) is the failure that matters:
the product would ship a resume that spills in the recipient's Word. The reverse only
costs a slightly smaller type size.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from resume_engine.builder import build  # noqa: E402
from resume_engine.calibrate import grid  # noqa: E402
from resume_engine.legacy import from_v2  # noqa: E402
from resume_engine.schema import BuildOptions, LeftSection  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
OUT = BACKEND / "out" / "parity"
REFERENCE = Path(os.environ.get("REFERENCE_DIR", BACKEND.parent / "reference"))
SEND_DIRS = {"A": "SDE", "B": "ML-CV", "C": "AI-Automation", "D": "FullStack-Web"}
SCALES = grid(0.96, 1.20, 0.01)


def variants():
    """Baseline track builds plus tailored ones: a swapped project, a reordering, a
    dropped role. Each changes length, which is what moves the page boundary."""
    items = lambda *ids: [LeftSection(heading="Projects", item_ids=list(ids))]  # noqa: E731
    return {
        "A": BuildOptions(track="A"),
        "B": BuildOptions(track="B"),
        "C": BuildOptions(track="C"),
        "D": BuildOptions(track="D"),
        "A-cv": BuildOptions(track="A", left_sections=items("supplysense", "everlink", "stationwatch")),
        "B-reorder": BuildOptions(track="B", left_sections=items("sevcs", "stationwatch", "newsletter_ai")),
        "C-dropR2": BuildOptions(track="C", drop={"R2"}),
        "D-sde": BuildOptions(track="D", left_sections=items("everlink", "newsletter_sde", "supplysense")),
    }


def cmd_build():
    with open(REFERENCE / "profile" / "resume_data.json", encoding="utf-8") as f:
        data = from_v2(json.load(f))
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "docs").mkdir(parents=True)
    manifest = []
    for track, sub in SEND_DIRS.items():
        rel = "docs/send_{}.docx".format(track)
        shutil.copyfile(REFERENCE / "send" / sub / "resume_Pranjal_Agarwal.docx", OUT / rel)
        manifest.append({"path": rel, "variant": "send-" + track, "scale": None})
    for name, opts in variants().items():
        for sc in SCALES:
            rel = "docs/{}_{:.2f}.docx".format(name, sc)
            build(data, opts, str(OUT / rel), scale=sc)
            manifest.append({"path": rel, "variant": name, "scale": sc})
    with open(OUT / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    print("built {} documents in {}".format(len(manifest), OUT))


def cmd_lo(font):
    from resume_engine.pages import count_pages, renderer_version
    with open(OUT / "manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    paths = [str(OUT / e["path"]) for e in manifest]
    subst = {"Calibri": "Carlito"} if font == "carlito" else None
    counts = count_pages(paths, timeout=1800, substitute_fonts=subst)
    result = {e["path"]: counts[str(OUT / e["path"])] for e in manifest}
    version = renderer_version()
    with open(OUT / "lo_{}.json".format(font), "w", encoding="utf-8") as f:
        json.dump({"renderer": version, "font": font, "pages": result}, f, indent=1)
    print("wrote {} LibreOffice page counts, font {} ({})".format(len(result), font, version))


def _max_fit(rows):
    fits = [sc for sc, pages in rows if pages == 1]
    first_spill = next((sc for sc, pages in rows if pages != 1), None)
    ok = [sc for sc in fits if first_spill is None or sc < first_spill]
    return ok[-1] if ok else None


def cmd_report():
    with open(OUT / "manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(OUT / "word.json", encoding="utf-8-sig") as f:
        word = json.load(f)
    ok = True
    for font in ("carlito", "native"):
        path = OUT / "lo_{}.json".format(font)
        if path.exists():
            with open(path, encoding="utf-8") as f:
                lo_doc = json.load(f)
            passed = _report_one(manifest, word, lo_doc)
            # Only the Carlito run models the server, so only it gates acceptance.
            ok = ok and (passed or font != "carlito")
    sys.exit(0 if ok else 1)


def _report_one(manifest, word, lo_doc) -> bool:
    lo = lo_doc["pages"]
    print("=" * 78)
    print("Word vs LibreOffice, font: {}   ({})\n".format(lo_doc["font"], lo_doc["renderer"]))
    print("Files as sent (send/, built by the reference builder, grid bug included):")
    for e in manifest:
        if e["scale"] is None:
            print("  {:<8} Word {} page(s)   LibreOffice {} page(s)".format(
                e["variant"], word[e["path"]], lo[e["path"]]))

    with open(REFERENCE / "profile" / "resume_data.json", encoding="utf-8") as f:
        stored = json.load(f)["scale"]
    print("\nBaselines rebuilt by the port at each track's stored scale:")
    baseline_ok = True
    for e in manifest:
        if e["variant"] in stored and e["scale"] == stored[e["variant"]]:
            w, l_ = word[e["path"]], lo[e["path"]]
            baseline_ok = baseline_ok and w == 1 and l_ == 1
            print("  {:<8} scale {:.2f}   Word {} page(s)   LibreOffice {} page(s)".format(
                e["variant"], e["scale"], w, l_))

    print("\nLargest one-page scale per variant (grid {:.2f}-{:.2f}, step 0.01):".format(
        SCALES[0], SCALES[-1]))
    print("  {:<10} {:>6} {:>6}  {}".format("variant", "Word", "LO", "verdict"))
    by_variant: dict[str, list] = {}
    for e in manifest:
        if e["scale"] is not None:
            by_variant.setdefault(e["variant"], []).append(e)

    false_fits, false_spills, agree, total = [], [], 0, 0
    for name, entries in by_variant.items():
        entries.sort(key=lambda e: e["scale"])
        w_rows = [(e["scale"], word[e["path"]]) for e in entries]
        l_rows = [(e["scale"], lo[e["path"]]) for e in entries]
        for e in entries:
            total += 1
            w, l_ = word[e["path"]], lo[e["path"]]
            if w == l_:
                agree += 1
            elif l_ == 1 and w > 1:
                false_fits.append((name, e["scale"], w, l_))
            elif l_ > 1 and w == 1:
                false_spills.append((name, e["scale"], w, l_))
        wm, lm = _max_fit(w_rows), _max_fit(l_rows)
        if wm == lm:
            verdict = "exact"
        elif wm is not None and lm is not None and lm < wm:
            verdict = "LO stricter by {:.2f} (safe)".format(wm - lm)
        else:
            verdict = "LO LENIENT - would ship 2 pages"
        fmt = lambda v: "{:.2f}".format(v) if v is not None else "none"  # noqa: E731
        print("  {:<10} {:>6} {:>6}  {}".format(name, fmt(wm), fmt(lm), verdict))

    print("\nPer-document agreement: {}/{} ({:.1f}%)".format(agree, total, 100.0 * agree / total))
    print("False fits (LO 1 page, Word 2+): {}".format(len(false_fits)))
    for row in false_fits:
        print("  {} @ {:.2f}: Word {}, LO {}".format(*row))
    print("False spills (LO 2+, Word 1): {}".format(len(false_spills)))
    for row in false_spills:
        print("  {} @ {:.2f}: Word {}, LO {}".format(*row))

    print("\nAcceptance: four rebuilt baselines one page in both renderers: {}".format(
        "PASS" if baseline_ok else "FAIL"))
    print("Acceptance: no false fits: {}\n".format("PASS" if not false_fits else "FAIL"))
    return baseline_ok and not false_fits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["build", "lo", "report"])
    ap.add_argument("--font", choices=["carlito", "native"], default="carlito")
    a = ap.parse_args()
    if a.step == "lo":
        cmd_lo(a.font)
    else:
        {"build": cmd_build, "report": cmd_report}[a.step]()


if __name__ == "__main__":
    main()
