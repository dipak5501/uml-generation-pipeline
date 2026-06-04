# Research Paper (LaTeX)

**Title:** Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design  

**Authors:** Dipak Yadav, Yutong Zhao  

**Overleaf project:** [Open in Overleaf](https://www.overleaf.com/project/69ed35eca71ed1faa143a7b9)

This folder holds the LaTeX source for the paper that describes the [UML Generation Pipeline](../README.md). The live draft is edited on Overleaf; this repo stores a copy for version control alongside the code.

## Quick link

| Resource | URL |
|----------|-----|
| Overleaf (edit) | https://www.overleaf.com/project/69ed35eca71ed1faa143a7b9 |
| Main LaTeX | `paper/main.tex` |
| Bibliography | `paper/references.bib`, `paper/refs_corrected.bib` |
| GitHub (code + paper) | https://github.com/dipak5501/uml-generation-pipeline |

## Add your paper from Overleaf (one-time)

1. Open your project on [Overleaf](https://www.overleaf.com/project/69ed35eca71ed1faa143a7b9).
2. Click **Menu** (top left) → **Download** → **Source**.
3. Unzip the download.
4. Copy all `.tex`, `.bib`, `.bst`, and image files into this `paper/` folder (keep `main.tex` as the entry point if you use one).
5. From the repo root, run:

```bash
./scripts/sync_paper_from_overleaf.sh ~/Downloads/your-overleaf-export.zip
```

Or copy files manually, then:

```bash
git add paper/
git commit -m "Add LaTeX paper source from Overleaf"
git push origin main
```

## Folder layout (after export)

```
paper/
  README.md           ← this file
  main.tex            ← your main file (from Overleaf)
  references.bib      ← bibliography
  figures/            ← images and pipeline plots
  sections/           ← optional chapter files
```

## Use pipeline figures in the paper

Copy charts from the code pipeline into `paper/figures/`:

```bash
cp output/figures/*.png paper/figures/
```

In LaTeX:

```latex
\includegraphics[width=\linewidth]{figures/scores_component.png}
```

## Build locally (optional)

```bash
cd paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Or keep compiling on Overleaf and only push source to GitHub when you want a snapshot.

## Sync workflow (recommended)

1. Write on **Overleaf** (collaboration, spelling, templates).
2. When you finish a milestone, **Download → Source** and run `sync_paper_from_overleaf.sh` or copy into `paper/`.
3. **Commit and push** so the paper and code share the same GitHub history under your name.
