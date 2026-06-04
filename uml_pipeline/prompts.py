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
    "class": "Generate a UML Class Diagram in PlantUML. Include classes with attributes and methods, and correct relationship notation.",
    "object": "Generate a UML Object Diagram in PlantUML. Use object instances with :Type syntax and links between instances.",
    "component": "Generate a UML Component Diagram in PlantUML. Show components, interfaces, and dependencies.",
    "package": "Generate a UML Package Diagram in PlantUML. Use package blocks, nesting, and dependencies (..>). Avoid treating dotted names as separate top-level packages.",
}

PLANTUML_CODE_PROMPT = """You are a UML expert. Convert the technical specification into syntactically valid PlantUML.

{diagram_hint}

Rules:
1. Think step-by-step about entities and connectors before writing code.
2. Output ONLY valid PlantUML between @startuml and @enduml.
3. No markdown fences or extra commentary outside the diagram.
4. Keep the diagram readable; avoid unnecessary complexity.

Technical specification:
{specification}
"""

VLM_SCORING_PROMPT = """You are evaluating a UML diagram image against a technical specification.

Specification:
{specification}

Score the diagram from 0 to 6:
- 0: diagram missing, unreadable, or shows none of the requirements
- 1-2: major elements missing or wrong diagram type
- 3-4: partial alignment with notable gaps
- 5: strong alignment with minor issues
- 6: complete alignment (entities, relationships, constraints)

Reply with a single integer score only."""
