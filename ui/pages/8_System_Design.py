"""System design — architecture overview of the UML generation application."""

from __future__ import annotations

import streamlit as st

from ui.theme import apply_theme, hero, panel

st.set_page_config(page_title="UML-Pipeline · System Design", layout="wide", page_icon="▦")
apply_theme()

hero(
    "System design",
    "Architecture of UML-Pipeline: natural-language requirements "
    "to PlantUML diagrams, multimodal verification, and dataset acceptance.",
    chips=["Dipak Yadav · Yutong Zhao", "Software design", "PlantUML + VLM ensemble"],
)

st.markdown(
    """
This page documents the **runtime architecture** of the application:
components, generation flow, provider routing, and acceptance criteria
aligned with the paper method.
"""
)

st.subheader("1 · High-level architecture")
st.caption("The UI and API share one orchestration service. Model fine-tuning is performed offline.")

st.graphviz_chart(
    """
digraph arch {
  rankdir=LR;
  bgcolor="transparent";
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
  edge [fontname="Helvetica", fontsize=9, color="#3a4a57"];

  UI [label="Streamlit UI\\n:8501", fillcolor="#e8f5f3", color="#0f766e"];
  CLI [label="CLI scripts", fillcolor="#f3efe6", color="#14212b"];
  API [label="FastAPI\\n/api/generate\\n:8000", fillcolor="#dcefea", color="#0f766e"];
  ORCH [label="Orchestration\\nspec → PlantUML\\n→ score → gate", fillcolor="#14212b", fontcolor="#f7f3ea", color="#14212b"];
  PROV [label="Providers\\nMock · MLX LoRA\\nOllama / OpenAI", fillcolor="#f7f3ea", color="#c45c26"];
  STORE [label="SQLite + PNG\\ndata/uml_app.db\\ndata/artifacts/", fillcolor="#f3efe6", color="#14212b"];
  RENDER [label="PlantUML\\nremote / local Java", fillcolor="#f7f3ea", color="#0f766e"];

  UI -> API;
  CLI -> API;
  API -> ORCH;
  ORCH -> PROV;
  ORCH -> RENDER;
  ORCH -> STORE;
}
""",
    use_container_width=True,
)

c1, c2, c3 = st.columns(3)
with c1:
    panel(
        "Clients",
        "Streamlit pages (Generate, Batch, Review, Analytics) and optional CLI scripts call the same API.",
    )
with c2:
    panel(
        "Core",
        "<code>run_single_generation()</code> in <code>app/services/orchestration.py</code> implements the end-to-end pipeline.",
    )
with c3:
    panel(
        "Outputs",
        "PlantUML text, rendered PNG, VLM scores, majority / composite flags, and SQLite artifact records.",
    )

st.subheader("2 · Generation pipeline")
st.caption("Dashed edges show the repair loop when PlantUML fails validation or rendering.")

st.graphviz_chart(
    """
digraph pipe {
  rankdir=LR;
  bgcolor="transparent";
  node [shape=box, style="rounded,filled", fillcolor="#e8f5f3", color="#0f766e", fontname="Helvetica", fontsize=10];
  edge [color="#3a4a57", fontname="Helvetica", fontsize=8];

  I [label="Input\\nrequirement or\\nsource code"];
  S [label="Tech Spec\\nLLM / analysis"];
  P [label="PlantUML\\n+ CoT"];
  V [label="Validate"];
  R [label="Repair", fillcolor="#fde8dc", color="#c45c26"];
  G [label="Render PNG"];
  M [label="3× VLM\\nscores"];
  D [label="Dataset gate\\nmajority A + S"];
  O [label="Persist"];

  I -> S -> P -> V;
  V -> R [style=dashed, color="#c45c26", label="fail"];
  R -> V [style=dashed, color="#c45c26"];
  V -> G -> M -> D -> O;
}
""",
    use_container_width=True,
)

st.subheader("3 · Dual-signal verification (dataset entry)")
g1, g2, g3 = st.columns(3)
with g1:
    st.markdown("**Render gate δ**")
    st.write(
        "PNG rendering must succeed. On failure, composite **S = 0** and the artifact is not accepted into the dataset."
    )
with g2:
    st.markdown("**Majority A**")
    st.write(
        "At least **2 of 3** vision models assign a score ≥ τ (**default 4**)."
    )
with g3:
    st.markdown("**Composite S**")
    st.write(
        "MMMU-weighted score across models. Dataset entry requires **S ≥ 3**, together with a successful render and majority acceptance."
    )

st.info(
    "An artifact is dataset-accepted when `render_ok` ∧ `majority_accepted` ∧ "
    "`composite_score ≥ min_composite`. These flags appear on Generate and Artifact Review."
)

st.subheader("4 · Provider routing")
st.markdown(
    """
| Stage | Default configuration | Alternatives |
|-------|----------------------|--------------|
| Technical specification | Mock provider / structural code analysis | Ollama or OpenAI-compatible API |
| PlantUML (natural-language requirement) | MLX LoRA when `USE_FINETUNED_CODE=true`, else mock | Live LLM |
| PlantUML (source-code input) | Base provider (LoRA trained on specification→PlantUML pairs) | Live LLM |
| VLM scoring | Mock scores (0–6) | Three vision models (Qwen / LLaMA-Vision / Aya) |
| Rendering | Remote PlantUML server, or local Java + jar | Same |

The fine-tuned code stage uses an 8 000-row open UML corpus and a LoRA adapter on Qwen2.5-0.5B (`models/uml-plantuml-lora/`). Invalid or low-quality PlantUML from the adapter is retried with the base provider.
"""
)

st.subheader("5 · Diagram types and storage")
d1, d2 = st.columns(2)
with d1:
    st.markdown(
        """
**Supported diagram types**

1. Class  
2. Object  
3. Component  
4. Package  
5. Flowchart (activity-style)

**Input modes:** natural-language requirement, or source code (language auto-detected).
"""
    )
with d2:
    st.markdown(
        """
**Persistence**

- Database: `data/uml_app.db` (SQLite)  
- Diagram images: `data/artifacts/{id}/`  
- Training corpus: `data/training/`  
- LoRA adapters: `models/uml-plantuml-lora/`
"""
    )

st.subheader("6 · Typical usage path")
st.markdown(
    """
1. Open **System Design** for the architecture overview.  
2. Use **Single Generation** with a short requirement and a diagram type.  
3. Inspect the validation summary: specification, PlantUML syntax, render status, composite **S**, majority **A**, and dataset acceptance.  
4. Open **Artifact Review** for stored PlantUML, PNG, and per-model scores.  
5. Use **Analytics** and **Settings** for aggregate metrics and runtime health (provider summary).
"""
)

st.caption(
    "UML-Pipeline · Automated UML Dataset Generation from Natural-Language Requirements "
    "with Multimodal Verification for Software Design — Yadav & Zhao"
)
