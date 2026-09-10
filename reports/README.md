# Reports

Tracked PDF deliverables for the M.S. thesis project (regenerate after content changes):

| File | What it is | Generator |
|------|------------|-----------|
| [UML_Pipeline_Application_Report.pdf](UML_Pipeline_Application_Report.pdf) | System design, UML types, datasets, UI/API, Mac Studio production | `python scripts/generate_progress_pdf.py` |
| [Dipak_Yadav_MS_Thesis_Draft.pdf](Dipak_Yadav_MS_Thesis_Draft.pdf) | CSULB-style M.S. thesis **draft** (CECS 698) from `paper/main.tex` plus implementation chapters | `python scripts/generate_thesis_draft.py` |
| [Dipak_Yadav_Thesis_Research_Brief.pdf](Dipak_Yadav_Thesis_Research_Brief.pdf) | Two-page committee invitation brief (paper method, RQs, tables) | `python scripts/generate_committee_brief.py` |
| [RQ3_PACKAGE_FAILURE_CHAPTER.md](RQ3_PACKAGE_FAILURE_CHAPTER.md) | Live Mac Studio package taxonomy + repair win-rate (not paper n=8k) | `python scripts/generate_rq3_package_chapter.py` |

```bash
make app-report-pdf
make thesis-pdf
make committee-brief-pdf
python scripts/generate_rq3_package_chapter.py
```

The thesis PDF is an **advisor-review draft**, not the official CSULB Thesis Office template. Expand bibliography from `paper/references.bib` before final submission.

If GitHub shows “Error loading PDF page number 1”, use **Download** (raw file). The tracked PDFs are rewritten with Flate-only streams so the GitHub viewer works; an older ReportLab ASCII85 encoding caused that error.

Markdown companions in this folder (`PUBLICATION_TECHNICAL_REPORT.md`, `REVIEWER_PROGRESS_REPORT.md`, `REMOTE_CURSOR_ACCESS.md`) are source notes, not the submission PDFs.
