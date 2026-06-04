# UML Generation Pipeline

**Author:** [Dipak Yadav](https://github.com/dipak5501)  
**Repository:** [github.com/dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline)

An end-to-end AI pipeline that turns software requirements into **UML design diagrams** (Class, Object, Component, Package), renders them with **PlantUML**, and scores quality with a **multimodal vision–language ensemble**.

## Highlights

- **Dual-LLM generation** — lightweight model for specs, reasoning model for PlantUML
- **Multimodal verification** — three VLMs with MMMU-weighted composite scoring
- **Dataset tooling** — download, analyze, render, and export UML artifacts at scale
- **Design-phase focus** — structural UML types used in early software design

## Architecture

```mermaid
flowchart LR
  A[Requirements / Spec] --> B[LLM: Technical specification]
  B --> C[LLM: PlantUML code]
  C --> D[PlantUML render]
  D --> E[VLM ensemble scoring]
  E --> F[Validated dataset]
```

## Commands

| Task | Command |
|------|---------|
| Download benchmark data | `python scripts/download_datasets.py` |
| Render diagrams | `python scripts/render_diagrams.py --limit 20` |
| Analyze scores | `python scripts/analyze_dataset.py` |
| Generate new samples | `python scripts/run_generation.py --diagram-type class -n 10` |
| Publish to GitHub | `./scripts/publish_to_github.sh` |

## Quick start

```bash
git clone https://github.com/dipak5501/uml-generation-pipeline.git
cd uml-generation-pipeline

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**Download sample datasets (optional):**

```bash
python scripts/download_datasets.py --skip-errors
python scripts/analyze_dataset.py
```

**Generate your own UML artifacts:**

```bash
# OpenAI-compatible API
export OPENAI_API_KEY=sk-...
python scripts/run_generation.py --diagram-type class -n 10

# Or local Ollama
export USE_OLLAMA=true
python scripts/run_generation.py --diagram-type package -n 5
```

**Render diagrams** (requires Java JDK):

```bash
python scripts/render_diagrams.py --limit 20 --diagram-type class
```

## Output schema

Each generated or downloaded record includes:

| Field | Description |
|-------|-------------|
| `input` | Technical specification or feature description |
| `reasoning` | Model reasoning trace (when available) |
| `uml_code` | PlantUML source |
| `qwen25vl3b`, `llama32vl11b`, `aya_vision_8b` | Per-model scores (0–6) |
| `scores` | Weighted composite validation score |

## Configuration

Edit `config.yaml` for VLM weights, diagram types, and optional Hugging Face dataset sources.

## Project layout

```
uml_pipeline/   Core library
scripts/        CLI tools
config.yaml     Pipeline settings
data/           Local datasets (gitignored)
output/         Figures and exports (gitignored)
```

## Author

**Dipak Yadav** — [GitHub @dipak5501](https://github.com/dipak5501)

Sole author and maintainer of this project. See [AUTHORS.md](AUTHORS.md).

## License

MIT — see [LICENSE](LICENSE).
