#!/usr/bin/env bash
# Publish this project to https://github.com/dipak5501/uml-generation-pipeline
set -euo pipefail

REPO="dipak5501/uml-generation-pipeline"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI: brew install gh"
  exit 1
fi

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [ -z "${GH_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ]; then
  if ! gh auth status >/dev/null 2>&1; then
    echo "Set GH_TOKEN in .env (Contents: Read and write) or run: gh auth login"
    exit 1
  fi
else
  export GH_TOKEN="${GH_TOKEN:-$GITHUB_TOKEN}"
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  git init -b main
fi

if ! git config user.name >/dev/null 2>&1; then
  git config user.name "Dipak Yadav"
  git config user.email "71300693+dipak5501@users.noreply.github.com"
fi

git add -A
git status

if git diff --cached --quiet; then
  echo "Nothing to commit."
else
  git commit -m "$(cat <<'EOF'
Update UML generation pipeline by Dipak Yadav.

Dual-LLM PlantUML generation, multimodal VLM verification, dataset tooling.
EOF
)"
fi

if gh repo view "$REPO" >/dev/null 2>&1; then
  echo "Remote repo exists: https://github.com/$REPO"
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$REPO.git"
  git push -u origin main
else
  gh repo create "$REPO" --public --source=. --remote=origin --push --description \
    "AI-driven UML dataset generation and multimodal verification by Dipak Yadav"
fi

echo "Done: https://github.com/$REPO"
