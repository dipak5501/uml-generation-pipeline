"""Prompt templates for specification and PlantUML generation."""

SPEC_USER_PROMPT = """Act as an end-user or product owner who has conceived a software feature.
You are now explaining this feature requirement to a software developer.
The developer needs this information to draft flowcharts and class diagram.
Your task is to:
1. Invent a plausible and interesting new software feature.
2. Describe this feature from a user's perspective, focusing on what it does.
Output should be easy to understand.
Answer only about the description of the feature, not about the flowchart or use case diagram.

Feature description:"""

SYSTEM_ARCHITECT_PROMPT = """You are a senior system architect. Given a software feature described from a user's perspective,
produce a detailed technical specification suitable for the Design phase of software engineering.
Include:
- Core entities (classes/components/packages) with key attributes
- Relationships (association, composition, aggregation, dependency, inheritance as appropriate)
- For object diagrams: concrete object instances and links
- For component diagrams: modules, interfaces, and dependencies
- For package diagrams: package hierarchy and cross-package dependencies

Do NOT output PlantUML or code. Output only the structured technical specification in clear prose and bullet points."""

PLANTUML_DIAGRAM_HINTS = {
    "class": (
        "Generate a UML Class Diagram in PlantUML. Include classes with attributes and methods, "
        "and correct relationship notation (--|>, -->, *--, o--, ..>). Use domain names from the "
        "specification — never Module1/EntityA placeholders."
    ),
    "object": (
        "Generate a UML Object Diagram in PlantUML. Every instance MUST use `object name : Type` "
        "(e.g. `object alice : User`). Link instances with -->. Do NOT emit class declarations. "
        "Prefer concrete instance names (alice, order1) typed from the specification."
    ),
    "component": (
        "Generate a UML Component Diagram in PlantUML. Show real modules as [Name] or "
        "`component Name`, with interfaces only when the specification names them. "
        "Use ..> for dependencies. Do not invent IXxx interfaces or generic Svc/Api labels."
    ),
    "package": (
        "Generate a UML Package Diagram in PlantUML. Use nested `package Name { ... }` blocks "
        "for containment (e.g. package api { package controllers { class X } }). "
        "Dependencies between packages use ..>. Never emit flat peer packages like "
        "`package com.app.core` and `package com.app.api` — nest under shared parents instead. "
        "Put classes/interfaces inside packages; avoid empty package shells."
    ),
    "flowchart": (
        "Generate a PlantUML FLOWCHART (activity diagram). Use start/:Step;/if-endif/stop "
        "for the main process and decisions."
    ),
}

PLANTUML_CODE_PROMPT = """You are a UML expert. Convert the technical specification into syntactically valid PlantUML.

{diagram_hint}

Rules:
1. Think step-by-step about entities and connectors before writing code.
2. Output ONLY valid PlantUML between @startuml and @enduml.
3. No markdown fences or extra commentary outside the diagram.
4. Keep the diagram readable; avoid unnecessary complexity.
5. Use only names grounded in the specification (no Module1 / EntityA / Svc placeholders).
6. Match the requested diagram type exactly — do not switch to class/sequence/etc.

Technical specification:
{specification}
"""

VLM_SCORING_PROMPT = """You are evaluating a UML/flowchart diagram image against a technical specification.
The specification may come from natural-language requirements OR reverse-engineered source code.

Specification:
{specification}

Score the diagram from 0 to 6 using these paper criteria jointly:
1. Semantic correctness — entities/relationships/constraints match the specification (penalize hallucination/omission)
2. Structural completeness — all major mandated components are present
3. Syntactic accuracy — correct UML/PlantUML notation for the diagram type
4. Overall coherence — clear, usable, consistent layout and naming

Scale:
- 0: missing, unreadable, non-renderable, or no alignment
- 1-2: major gaps or wrong diagram type
- 3-4: partial alignment with notable issues
- 5: strong alignment with minor issues
- 6: complete alignment

Respond in exactly this format (no other prose before SCORE).
Write SCORE and EXPLANATION in English only (no Japanese, Chinese, or other languages):
SCORE: <integer 0-6>
EXPLANATION: <2-4 English sentences covering semantic, structural, syntactic, and coherence findings>
"""
