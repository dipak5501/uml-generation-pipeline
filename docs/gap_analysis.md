# Gap Analysis: UML Generation Thesis Application

**Original date:** 2026-07-13  
**Updated:** 2026-08-28  
**Paper:** *Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design* (Dipak Yadav, Yutong Zhao)  
**Repo:** [dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline)

This document originally compared the research CLI to a target application. **As of August 2026 the application is implemented and in production on the Math department Mac Studio (24/7 LaunchAgents).** Remaining gaps are mostly paper-exact model sizing (local stand-ins for DeepSeek-32B) and large-n human-evaluation correlation studies.

See [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) for the current architecture.

---

## Current repo capabilities (2026-08-26)

| Area | Status | Notes |
|------|--------|-------|
| Spec generation | **Done** | User requirements + source code → structured spec; persisted |
| PlantUML generation | **Done** | LoRA + Ollama + spec-builder fallback; versioned prompts |
| Rendering | **Done** | Local Java + JAR; remote fallback; B&W policy |
| VLM scoring | **Done** | 3-model ensemble; composite S + majority A; render gate |
| LLM providers | **Done** | Mock, Ollama dual-host, HF, MLX LoRA, local Aya |
| Dataset tooling | **Done** | HF download, 50k/100k corpora, parquet/JSONL, export API |
| Batch generation | **Done** | API jobs + Streamlit progress UI |
| Persistence | **Done** | SQLite + artifact files + sidecar JSON |
| API | **Done** | FastAPI with auth token, OpenAPI, async jobs |
| UI | **Done** | Streamlit 8-page app |
| Repair/retry | **Done** | Package validators, repair loop, acceptance gates |
| Human evaluation | **Done** | Rubric UI + analytics |
| Analytics app | **Done** | Online summary, distributions, export |
| Tests | **Done** | pytest unit + API + security |
| Docker / deployment | **Done** | Docker + Mac LaunchAgents + Cloudflare tunnels |
| Prompt management | **Done** | `prompts/` + registry |
| Production ops | **Done** | `install_macos_user_server.sh`, tunnels, `restart_api.sh` |
| Fine-tuned PlantUML | **Done** | Production adapter `uml-plantuml-lora-sourcecode-30k` (30k Java/Python/C, 6k iters); prior 50k/100k/200k/source10k superseded |

---

## Target vs delivered

| Target capability | Delivered? |
|-------------------|------------|
| Requirement + source-code intake | ✅ `input_mode` requirement / source_code |
| Diagram-specific PlantUML (4 API types) | ✅ class, object, component, package (`flowchart` in corpus only, not on API) |
| Render PNG with failure handling | ✅ |
| Package-aware validation + repair | ✅ |
| Multimodal scoring (53.1 / 50.7 / 39.9) | ✅ local Ollama + local Aya |
| Full artifact traces in SQLite | ✅ |
| REST API + Streamlit UI | ✅ |
| Human review + analytics + export | ✅ |
| Local runnable without paid APIs | ✅ |
| Real tests, Docker, README | ✅ |
| Always-on Mac server | ✅ LaunchAgents, no Azure |
| Paper-scale 8k+ training corpus | ✅ 30k source-code production adapter; 50k/100k/200k complete |
| Paper-exact DeepSeek-32B locally | ⚠️ MLX LoRA 0.5B stand-in (documented) |
| Paper-exact 8k dataset generation at scale | ✅ Batch jobs + export; production LoRA on sourcecode-30k |

---

## Paper requirements vs repo

| Paper element | In repo? | Remaining gap |
|---------------|----------|---------------|
| Dual-LLM (spec + reasoning PlantUML) | Yes | Local LoRA stand-in for 32B code model |
| Design-phase diagram types (4 API + flowchart in corpus) | Yes | API: class/object/component/package only |
| PlantUML render as gate | Yes | — |
| 3 VLMs + MMMU weights | Yes | Aya requires local Transformers (not Ollama) |
| Majority vote + composite threshold | Yes | — |
| Human evaluation correlation | Yes | UI + export; large-n correlation is research task |
| Large dataset generation | Yes | Batch jobs + export; production `sourcecode-30k` adapter |
| Failure analysis (esp. package) | Yes | acceptance.json categories + analytics |

---

## Intentional stand-ins (documented, not bugs)

| Paper component | Local production choice | Rationale |
|-----------------|-------------------------|-----------|
| DeepSeek-R1-Distill-Qwen-32B | MLX LoRA on Qwen2.5-0.5B (`sourcecode-30k`) | 32B impractical on-device; LoRA trained on 30k+ UML pairs |
| Aya-Vision-8B via cloud | Local Transformers on M1 Ultra | Paper-exact; not in Ollama library |
| Dual Ollama versions | 0.24 + 0.32 on two ports | Qwen-VL vs LLaMA-Vision incompatibility on single Ollama build |

---

## Verdict (updated)

The repo is a **complete end-to-end application** wrapping the original research pipeline. Core generation/render/score logic was extended, not replaced. Remaining work is **paper-scale experimental evaluation** (large-n batch runs, human correlation), not missing application modules.

---

## Historical note

The sections below describe the **pre-application** state (July 2026) for archaeology:

<details>
<summary>Original gap table (July 2026 — superseded)</summary>

Previously missing: FastAPI, Streamlit, SQLite, mock providers, repair loop, human review, tests, Docker. All have been built. See git history and [implementation_plan.md](implementation_plan.md).

</details>
