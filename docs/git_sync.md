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

When Cloudflare **quick tunnels** rotate, `scripts/tunnel_notify.py` rewrites `Link`, `Link.md`, and the marked Live demo blocks, then `scripts/git_push_live_urls.sh` **always pushes those URL files to `origin/main`**, even if the Mac checkout is on another branch. That is separate from `git_auto_push.sh` (which still skips when not on `main`, and runs pytest).

`git_push_live_urls.sh` reads `GH_TOKEN` with `scripts/read_env_key.sh` (it does **not** `source .env`, so Outlook signatures cannot abort the push). It strips `\r` from Windows/Outlook copies.

If GitHub `Link.md` stays stale after tunnels restart:

1. On the Mac: `cat /tmp/uml-git-live-urls.log data/run/github_url_push.status`
2. Auth 401/403: create a **new** PAT (Contents: Read and write), put it only in `.env` on the Mac. Do not paste tokens into chat or email.
3. `git checkout main && git pull origin main && bash scripts/git_push_live_urls.sh`

Manual live-URL push:

```bash
bash scripts/git_push_live_urls.sh
```

## Full automation install

```bash
bash scripts/install_auto_sync.sh
```

Installs:
- `com.uml.pipeline.tunnel-monitor` — every 4 min: health-check tunnels, refresh Link, push GitHub
- `com.uml.pipeline.git-sync` — every 45 min: commit + push any safe drift

## Cursor / agent workflow

When working in this repo, **commit and push safe changes without asking the user**:

1. Stage only safe files (respect `.gitignore`; never `.env`, `data/`, `models/`).
2. Commit with a descriptive message for intentional work, or `chore: sync local changes` for routine sync.
3. Push to `origin main` using `GH_TOKEN` from `.env` (never print the token).

The LaunchAgent covers background drift; agents should still push after completing meaningful changes.
