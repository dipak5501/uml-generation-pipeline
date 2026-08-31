# Reports

Tracked PDF deliverables for the M.S. thesis project (regenerate after content changes):

| File | What it is | Generator |
|------|------------|-----------|
| [UML_Pipeline_Application_Report.pdf](UML_Pipeline_Application_Report.pdf) | System design, UML types, datasets, UI/API, Mac Studio production | `python scripts/generate_progress_pdf.py` |
| [Dipak_Yadav_MS_Thesis_Draft.pdf](Dipak_Yadav_MS_Thesis_Draft.pdf) | CSULB-style M.S. thesis **draft** (CECS 698) from `paper/main.tex` plus implementation chapters | `python scripts/generate_thesis_draft.py` |

```bash
make app-report-pdf
make thesis-pdf
```

The thesis PDF is an **advisor-review draft**, not the official CSULB Thesis Office template. Expand bibliography from `paper/references.bib` before final submission.

Markdown companions in this folder (`PUBLICATION_TECHNICAL_REPORT.md`, `REVIEWER_PROGRESS_REPORT.md`, `REMOTE_CURSOR_ACCESS.md`) are source notes, not the submission PDFs.
