"""Scripts without class declarations must not become fake class diagrams."""

from app.services.code_analysis import analyze_source_code
from app.services.plantuml_from_spec import plantuml_from_spec
from app.services.spec_json import structure_to_spec_json

PY2PUML_SCRIPT = '''
from py2puml.py2puml import py2puml

source_folder = "my_project_folder"
domain_module = "my_project_folder.models"
output_puml_file = "diagram.puml"

print(f"Analyzing {domain_module}...")

with open(output_puml_file, "w") as f:
    for line in py2puml(source_folder, domain_module):
        f.write(line)

print(f"Success! UML structure generated and saved to '{output_puml_file}'.")
'''


def test_analyzer_finds_no_classes():
    s = analyze_source_code(PY2PUML_SCRIPT)
    assert s.classes == []
    assert s.entity_names() == []
    assert not s.has_type_declarations


def test_structure_json_does_not_invent_variable_classes():
    data = structure_to_spec_json(PY2PUML_SCRIPT, "class")
    assert data.get("script_without_types") is True
    assert data.get("diagram_type") == "flowchart"
    names = {e["name"].lower() for e in data.get("entities") or []}
    for banned in ("source_folder", "domain_module", "output_puml_file", "model", "domainobject"):
        assert banned not in names
    assert data.get("process_steps")


def test_plantuml_is_flowchart_not_fake_classes():
    data = structure_to_spec_json(PY2PUML_SCRIPT, "class")
    code = plantuml_from_spec(data, data["diagram_type"])
    low = code.lower()
    assert "source_folder" not in low
    assert "domainobject" not in low
    assert "start" in low or "note" in low
    assert "class source_folder" not in low
