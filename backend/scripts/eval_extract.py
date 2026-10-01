"""
Phase 1 acceptance: does S1 extraction match a human reading? (spec 13, Phase 1)

Real posts contain third parties' names and emails, so the eval set lives in the
git-ignored reference/ folder:

    reference/eval/posts/<id>.txt      one pasted post per file
    reference/eval/labels.json         your reading of each post (see --template)

    python scripts/eval_extract.py --template   # writes labels.template.json with blank fields
    python scripts/eval_extract.py              # runs S1 on every post and scores it

Labels are filled in by a person reading the post, not copied from the model: the check is
only worth something if the reading is independent. Needs ANTHROPIC_API_KEY; does not
touch the database.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import llm  # noqa: E402
from app.pipeline import screen  # noqa: E402
from app.pipeline.extract import extract  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "reference" / "eval"
FIELDS = {
    "stipend_stated": "figure | unpaid | unstated | performance_based",
    "stipend_monthly_max": "number per month, or null (only when stated)",
    "remote": "true | false (onsite, or a city named with no work mode) | null (neither stated)",
    "onsite_city": "city, or null",
    "country": "country, or null",
    "batch_years": "list of years, [] if none",
    "apply_email": "the published address, or null",
    "apply_route": "email | portal | none",
}


def reading(ex) -> dict:
    emails = [r.value for r in ex.apply_routes if r.type == "email" and r.value]
    portals = [r for r in ex.apply_routes if r.type in ("form", "ats", "linkedin_apply")]
    m = screen.monthly(ex)
    return {
        "stipend_stated": ex.stipend.stated,
        "stipend_monthly_max": round(m) if m is not None else None,
        "remote": ex.remote,
        "onsite_city": ex.onsite_city,
        "country": ex.country,
        "batch_years": sorted(ex.batch_years),
        "apply_email": emails[0] if emails else None,
        "apply_route": "email" if emails else ("portal" if portals else "none"),
    }


COUNTRY_ALIASES = {"uae": "united arab emirates", "usa": "united states", "us": "united states",
                   "uk": "united kingdom", "bharat": "india"}


def same(field: str, got, want) -> bool:
    if field in ("onsite_city", "country"):
        g, w = (got or "").strip().lower(), (want or "").strip().lower()
        if field == "country":
            g, w = COUNTRY_ALIASES.get(g, g), COUNTRY_ALIASES.get(w, w)
        return g == w or (bool(g) and bool(w) and (g in w or w in g))
    if field == "apply_email":
        return (got or "").lower() == (want or "").lower()
    if field == "batch_years":
        return sorted(got or []) == sorted(want or [])
    if field == "stipend_monthly_max":
        return (got is None and want is None) or (got is not None and want is not None and abs(got - want) <= 1)
    return got == want


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", action="store_true")
    a = ap.parse_args()
    posts = sorted((ROOT / "posts").glob("*.txt"))
    if not posts:
        sys.exit("No posts in {}. Paste each real post into its own .txt file there.".format(ROOT / "posts"))
    if a.template:
        tpl = {"_fields": FIELDS, **{p.stem: {k: None for k in FIELDS} for p in posts}}
        (ROOT / "labels.template.json").write_text(json.dumps(tpl, indent=2), encoding="utf-8")
        print("wrote {} (fill it in by reading each post, save as labels.json)".format(ROOT / "labels.template.json"))
        return

    labels = json.loads((ROOT / "labels.json").read_text(encoding="utf-8"))
    hits = {f: 0 for f in FIELDS}
    n, misses = 0, []
    t0 = time.monotonic()
    for p in posts:
        if p.stem not in labels:
            continue
        got = reading(extract(p.read_text(encoding="utf-8"), None, llm.CallContext(), log=False))
        n += 1
        for f in FIELDS:
            if same(f, got[f], labels[p.stem].get(f)):
                hits[f] += 1
            else:
                misses.append((p.stem, f, labels[p.stem].get(f), got[f]))
    print("S1 extraction vs human reading, {} posts ({:.0f}s)\n".format(n, time.monotonic() - t0))
    for f in FIELDS:
        print("  {:<22} {:>3}/{}  {:5.1f}%".format(f, hits[f], n, 100.0 * hits[f] / max(1, n)))
    print("\nMismatches (post, field, human, model):")
    for m in misses:
        print("  {:<24} {:<20} {!r:<28} {!r}".format(*m))
    gate = ("stipend_stated", "remote", "onsite_city", "batch_years", "apply_email", "apply_route")
    ok = all(hits[f] == n for f in gate)
    print("\nAcceptance (stipend, location, batch year, apply route all match): {}".format("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
