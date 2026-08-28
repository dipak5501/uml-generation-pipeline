#!/usr/bin/env bash
# Generate PDFs from Dr. Zhao thesis progress markdown reports (ReportLab, no LaTeX).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/.venv/bin/python" "$ROOT/scripts/generate_dr_zhao_pdfs.py"
