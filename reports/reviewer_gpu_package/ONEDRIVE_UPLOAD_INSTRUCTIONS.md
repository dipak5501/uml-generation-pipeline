# OneDrive Upload Instructions (for Dipak)

Follow these steps to share the reviewer GPU package with your advisor/reviewer via OneDrive. **Do not include secrets** (`.env`, tokens, API keys, or private adapter weights unless explicitly requested separately).

---

## Step 1 — Verify package contents locally

From the repository root:

```bash
ls -la reports/reviewer_gpu_package/
ls -la reports/reviewer_gpu_package/SAMPLE_DATA/
```

Expected top-level files:

- `SAMPLE_DATA/` (sample inputs)
- `CLAUDE_CODE_GPU_PROMPT.md`
- `README_FOR_REVIEWER.md`
- `ONEDRIVE_UPLOAD_INSTRUCTIONS.md` (this file)

Also verify the progress report exists:

```bash
ls -la reports/REVIEWER_PROGRESS_REPORT.md
ls -la reports/REVIEWER_PROGRESS_REPORT.pdf   # if generated
```

---

## Step 2 — Create the zip archive

```bash
cd /Users/033783670/Desktop/uml-generation-pipeline-main/reports
zip -r reviewer_gpu_package.zip reviewer_gpu_package/
```

Optional — include the progress report in the same zip:

```bash
cd /Users/033783670/Desktop/uml-generation-pipeline-main/reports
zip reviewer_gpu_package.zip REVIEWER_PROGRESS_REPORT.md
zip reviewer_gpu_package.zip REVIEWER_PROGRESS_REPORT.pdf 2>/dev/null || true
```

Check size:

```bash
ls -lh reviewer_gpu_package.zip
```

---

## Step 3 — Upload to OneDrive

1. Open https://onedrive.live.com/ (or your university OneDrive) in a browser.
2. Sign in with your account.
3. Create a folder, e.g. `UML-Pipeline-Reviewer-2026-08`.
4. Click **Upload** → **Files** → select:
   - `reports/reviewer_gpu_package.zip`
   - Optionally upload `REVIEWER_PROGRESS_REPORT.pdf` separately for easy preview.
5. Wait for upload to complete.

---

## Step 4 — Share with reviewer

1. Right-click the uploaded zip (or folder) → **Share**.
2. Enter the reviewer’s email address.
3. Set permission to **Can view** (or **Can edit** if they need to comment).
4. Click **Send** or **Copy link**.
5. Paste the share link in your email to the reviewer.

**Suggested email text:**

> Dear [Reviewer name],
>
> Please find the UML-Pipeline reproduction package here: [OneDrive link]
>
> Contents: sample data, Claude Code GPU prompt, one-page README, and detailed progress report (`REVIEWER_PROGRESS_REPORT.md` inside the zip or attached as PDF).
>
> Live demo UI: https://orange-fountain-especially-positive.trycloudflare.com  
> (URLs may change; I can send updated links if needed.)
>
> The system runs on the Math department Mac Studio (M1 Ultra, 128 GB) at full capacity — 153 tests pass, 9/9 live source-code smoke with VLM scores 4.72–6.00.
>
> Best,  
> Dipak Yadav

---

## Step 5 — What NOT to upload

| Do NOT upload | Reason |
|---------------|--------|
| `.env` | Contains API tokens |
| `HF_TOKEN`, `API_ACCESS_TOKEN`, `REMOTE_AGENT_TOKEN` | Secrets |
| Full `models/` directory | Large; MLX adapters are gitignored; share privately if reviewer has Apple Silicon |
| Full `data/uml_app.db` | May contain private test inputs |
| Full `data/finetune/train.jsonl` | ~130k lines; sample included instead |

---

## Step 6 — Update live demo link before sending

Quick-tunnel URLs rotate. Before emailing, check:

```bash
cat Link
# or
cat data/run/public_ui_url.txt
cat data/run/public_api_url.txt
```

Replace the URL in your email if it changed since 2026-08-27.

---

*Prepared automatically for reviewer Q2 deliverable.*
