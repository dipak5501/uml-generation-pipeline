# Git auto-sync

This repo pushes safe local changes to [dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline) automatically so GitHub stays current as work progresses.

## What gets synced

- Tracked code, scripts, docs, and config that are **not** in `.gitignore`
- Commit message: `chore: sync local changes`
- Author: `dipak5501 <dipak5501@users.noreply.github.com>`

## What is never synced

- `.env`, credentials, tokens
- `data/`, `models/`, `output/`, `.venv/`, local PDFs/thesis docs (see `.gitignore`)

## Setup

1. Set `GH_TOKEN` in `.env` (GitHub PAT with **Contents: Read and write**).
2. Install the periodic LaunchAgent (default every 45 minutes):

```bash
bash scripts/install_git_sync.sh
```

Optional: change interval (seconds), e.g. 30 minutes:

```bash
GIT_SYNC_INTERVAL_SEC=1800 bash scripts/install_git_sync.sh
```

## Manual sync

```bash
bash scripts/git_auto_push.sh
```

## Cursor / agent workflow

When working in this repo, **commit and push safe changes without asking the user**:

1. Stage only safe files (respect `.gitignore`; never `.env`, `data/`, `models/`).
2. Commit with a descriptive message for intentional work, or `chore: sync local changes` for routine sync.
3. Push to `origin main` using `GH_TOKEN` from `.env` (never print the token).

The LaunchAgent covers background drift; agents should still push after completing meaningful changes.
