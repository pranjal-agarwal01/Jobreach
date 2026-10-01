"""
Page counting with LibreOffice headless: .docx -> PDF -> count pages with pypdf.

This replaces the reference pipeline's Word COM automation, which cannot run on a
Linux server. It is only trustworthy with the Carlito font installed (metric-
compatible with Calibri) and after the Word parity test in scripts/parity_check.py.

LibreOffice start-up dominates the cost, so count_pages converts a whole batch in
one soffice process. Each call gets its own throwaway LibreOffice profile, so
concurrent calls do not fight over a shared profile lock.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Sequence

from pypdf import PdfReader

# On Windows, soffice.com is the console launcher: it waits for the conversion and
# writes to stdout. soffice.exe is a GUI launcher and prints nothing.
_WINDOWS_DEFAULT = r"C:\Program Files\LibreOffice\program\soffice.com"


class RendererError(RuntimeError):
    pass


def soffice_path() -> str:
    for candidate in (os.environ.get("SOFFICE"), shutil.which("soffice"),
                      shutil.which("libreoffice")):
        if candidate:
            return candidate
    if os.path.exists(_WINDOWS_DEFAULT):
        return _WINDOWS_DEFAULT
    raise RendererError("LibreOffice not found; install it or set SOFFICE to its path")


def renderer_version() -> str:
    """For the resumes.renderer column: which renderer verified a page count."""
    out = subprocess.run([soffice_path(), "--version"], capture_output=True, text=True,
                         timeout=60)
    return out.stdout.strip() or "libreoffice (unknown version)"


def _copy_with_fonts(src, dst: Path, mapping: dict[str, str]) -> None:
    """Copy a .docx, renaming fonts in its XML parts (e.g. Calibri -> Carlito)."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                text = data.decode("utf-8")
                for old, new in mapping.items():
                    text = text.replace('="{}"'.format(old), '="{}"'.format(new))
                data = text.encode("utf-8")
            zout.writestr(info, data)


def count_pages(paths: Sequence[str | os.PathLike], timeout: int = 300,
                substitute_fonts: Optional[dict[str, str]] = None) -> dict[str, int]:
    """Return {input path: rendered page count} for each .docx, in one soffice run.

    substitute_fonts renders copies with fonts renamed. The Linux server has no Calibri,
    so it renders Calibri as Carlito on its own; {"Calibri": "Carlito"} reproduces that
    on a machine that does have Calibri (the Windows parity test).
    """
    return {k: n for k, (n, _) in render(paths, timeout, substitute_fonts).items()}


def render(paths: Sequence[str | os.PathLike], timeout: int = 300,
           substitute_fonts: Optional[dict[str, str]] = None,
           keep_pdf: bool = False) -> dict[str, tuple[int, Optional[bytes]]]:
    """Return {input path: (page count, PDF bytes or None)}. The PDF is the one the page
    count was measured on, so a delivered PDF is exactly the page-checked render. LibreOffice
    writes it tagged, and its text reads column by column (checked 2026-10-01)."""
    if not paths:
        return {}
    with tempfile.TemporaryDirectory(prefix="pages-") as tmp:
        tmp_path = Path(tmp)
        src_dir, out_dir = tmp_path / "in", tmp_path / "out"
        src_dir.mkdir()
        out_dir.mkdir()
        # Inputs often share a file name (every copy is resume_<First>_<Last>.docx), and
        # soffice names each PDF after its input, so give each input a unique name.
        staged: dict[str, Path] = {}
        for i, p in enumerate(paths):
            dst = src_dir / "doc{:04d}.docx".format(i)
            if substitute_fonts:
                _copy_with_fonts(p, dst, substitute_fonts)
            else:
                shutil.copyfile(p, dst)
            staged[str(p)] = dst

        profile = (tmp_path / "lo-profile").resolve().as_uri()
        cmd = [soffice_path(), "-env:UserInstallation=" + profile, "--headless", "--norestore",
               "--convert-to", "pdf", "--outdir", str(out_dir)]
        cmd += [str(d) for d in staged.values()]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        out: dict[str, tuple[int, Optional[bytes]]] = {}
        for original, dst in staged.items():
            pdf = out_dir / (dst.stem + ".pdf")
            if not pdf.exists():
                raise RendererError("no PDF for {} (soffice exit {}): {}".format(
                    original, proc.returncode, (proc.stderr or proc.stdout).strip()[:500]))
            out[original] = (len(PdfReader(str(pdf)).pages), pdf.read_bytes() if keep_pdf else None)
        return out


def count_one(path: str | os.PathLike, timeout: int = 120) -> int:
    return count_pages([path], timeout=timeout)[str(path)]
