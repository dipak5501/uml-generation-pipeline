#!/usr/bin/env bash
# Import an Overleaf "Download → Source" ZIP into paper/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAPER="$ROOT/paper"

if [ $# -lt 1 ]; then
  echo "Usage: $0 /path/to/overleaf-export.zip"
  echo ""
  echo "Steps:"
  echo "  1. Overleaf → Menu → Download → Source"
  echo "  2. Run: $0 ~/Downloads/project-*.zip"
  exit 1
fi

ZIP="$1"
if [ ! -f "$ZIP" ]; then
  echo "File not found: $ZIP"
  exit 1
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

unzip -q "$ZIP" -d "$TMP"

# Overleaf zips often have files at root or one subfolder
SRC="$TMP"
if [ "$(find "$TMP" -maxdepth 1 -name '*.tex' | wc -l)" -eq 0 ]; then
  SUB=$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)
  if [ -n "$SUB" ] && [ -n "$(find "$SUB" -maxdepth 1 -name '*.tex' 2>/dev/null)" ]; then
    SRC="$SUB"
  fi
fi

mkdir -p "$PAPER/figures"
shopt -s nullglob
for ext in tex bib bst cls sty png pdf jpg jpeg eps svg; do
  for f in "$SRC"/*."$ext" "$SRC"/**/*."$ext"; do
    [ -f "$f" ] || continue
    base=$(basename "$f")
    if [ "$base" = "README.md" ]; then
      continue
    fi
    dest="$PAPER/$base"
    if [[ "$f" == *figures* ]] || [[ "$f" == *Figures* ]] || [[ "$f" == *image* ]]; then
      dest="$PAPER/figures/$base"
    fi
    cp "$f" "$dest"
    echo "  copied → $dest"
  done
done

echo ""
echo "Done. Review paper/ then:"
echo "  cd $ROOT && git add paper/ && git status"
