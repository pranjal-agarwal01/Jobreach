# Backend

Python backend for the Job Outreach Copilot (see `../PRODUCT-SPEC.md`). Phase 0 holds the
resume engine only; the FastAPI app, database and pipeline arrive in Phase 1.

## Resume engine (`resume_engine/`)

| Module | What it does |
|---|---|
| `schema.py` | Resume data schema v3: any number of tracks, items, bullets and right-column sections. Every bullet and entry cites fact ids; `validate_fact_refs` checks each traces to a confirmed fact |
| `builder.py` | Two-column one-page `.docx` builder, ported from the reference `build_resume.py` |
| `pages.py` | Page count via LibreOffice headless → PDF → `pypdf`, one `soffice` run per batch |
| `calibrate.py` | Largest one-page type scale per track, coarse-to-fine, two renderer runs in total |
| `ats_score.py`, `jd_match.py` | JD-independent ATS score and JD keyword coverage, advice only |
| `legacy.py` | Converts reference schema v2 data, for the parity test only |

### Two layout fixes over the reference builder

Found by testing against Word; both change what recipients see.

1. **Table grid widths.** The reference builder set the cell widths (340/195pt) but left
   the table grid at python-docx's default of two equal 267pt columns. Word follows the
   cells; LibreOffice follows the grid, squeezing the left column onto page 2. Three of
   the four reference resumes in `send/` render as two pages in LibreOffice for this reason.
2. **Blank page 2.** A document cannot end on a table, so Word adds a body-size empty
   paragraph after it, which lands on a blank second page when the table nearly fills
   page 1. The builder now ends with a 1pt paragraph that always fits.

## Setup (Windows, no Docker)

```bash
python -m venv ../.venv
../.venv/Scripts/python -m pip install -r requirements.txt
```

The page check needs LibreOffice (`winget install TheDocumentFoundation.LibreOffice`) and
the Carlito font. On a machine with Office, Calibri is installed and LibreOffice would use
it; tests swap fonts to Carlito so they render the way the Linux server will.

```bash
../.venv/Scripts/python -m pytest -q                       # everything
../.venv/Scripts/python -m pytest -q --deselect tests/test_render.py   # without LibreOffice
```

Tests that need `../reference/` (personal data, git-ignored) skip when it is absent.

## Word parity test (`scripts/parity_check.py`)

Needs Windows with Word and LibreOffice. Builds 204 documents across a grid of scales that
straddles the one-page boundary, counts pages in both renderers, and fails on any
"false fit" (LibreOffice says one page, Word says two).

```bash
python scripts/parity_check.py build
powershell -File scripts/word_pages.ps1 -Manifest out/parity/manifest.json -Out out/parity/word.json
python scripts/parity_check.py lo --font carlito
python scripts/parity_check.py lo --font native
python scripts/parity_check.py report
```

## Deployment

`Dockerfile` is the deploy recipe (Python, LibreOffice without GUI, Carlito). Hosts such as
Render or Railway build it on their side; it is not needed for local development.
