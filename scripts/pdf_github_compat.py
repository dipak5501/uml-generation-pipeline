"""Rewrite ReportLab PDFs so GitHub's PDF.js viewer can open page 1.

GitHub's embedder fails on ReportLab defaults:
- ASCII85 + Flate stream filters
- empty page /Trans dictionaries
"""

from __future__ import annotations

from pathlib import Path


def disable_reportlab_ascii85() -> None:
    from reportlab import rl_config

    rl_config.useA85 = 0


def github_compat_pdf(path: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    src = Path(path)
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for page in reader.pages:
        if "/Trans" in page:
            del page["/Trans"]
        writer.add_page(page)
    meta = reader.metadata
    if meta:
        writer.add_metadata({k: str(v) for k, v in dict(meta).items() if v not in (None, "")})
    tmp = src.with_suffix(".github.pdf")
    with tmp.open("wb") as fh:
        writer.write(fh)
    tmp.replace(src)
