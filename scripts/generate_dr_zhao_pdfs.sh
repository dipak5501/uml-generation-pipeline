#!/usr/bin/env bash
# Generate PDFs from Dr. Zhao thesis progress markdown reports.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCS="$ROOT/docs"
PANDOC="${PANDOC:-pandoc}"

ENGINE="${PDF_ENGINE:-pdflatex}"
OPTS=(
  --pdf-engine="$ENGINE"
  -V geometry:margin=1in
  -V fontsize=11pt
  -V documentclass=article
  -V colorlinks=true
  -V linkcolor=blue
  -V urlcolor=blue
  --toc
  --toc-depth=2
)

gen() {
  local md="$1"
  local pdf="$2"
  echo "→ $pdf"
  "$PANDOC" "$md" -o "$pdf" "${OPTS[@]}"
}

gen "$DOCS/DR_ZHAO_PROGRESS_SUMMARY.md" "$DOCS/DR_ZHAO_PROGRESS_SUMMARY.pdf"
gen "$DOCS/DR_ZHAO_THESIS_PROGRESS_REPORT.md" "$DOCS/DR_ZHAO_THESIS_PROGRESS_REPORT.pdf"
gen "$DOCS/OVERLEAF_PAPER_HANDOFF.md" "$DOCS/OVERLEAF_PAPER_HANDOFF.pdf"
gen "$DOCS/IMPLEMENTATION_EVIDENCE_MATRIX.md" "$DOCS/IMPLEMENTATION_EVIDENCE_MATRIX.pdf"

echo ""
echo "Done. PDFs written to $DOCS/"
ls -lh "$DOCS"/*.pdf
