"""Stage-1 JSON specification validity."""

from app.services.spec_json import (
    ensure_valid_spec,
    extract_json_object,
    heuristic_spec_from_text,
    spec_to_prose,
    validate_spec_json,
    validity_metrics,
)


def test_extract_json_from_fenced_block():
    raw = """```json
{"diagram_type":"class","entities":[{"name":"Book"}],"relationships":[{"source":"A","target":"B","type":"association"}]}
```"""
    obj = extract_json_object(raw)
    assert obj is not None
    assert obj["diagram_type"] == "class"


def test_validate_requires_entities():
    result = validate_spec_json({"diagram_type": "class", "relationships": []}, "class")
    assert not result.ok


def test_valid_minimal_spec():
    data = {
        "diagram_type": "class",
        "summary": "Library",
        "entities": [{"name": "Book", "kind": "class", "attributes": [], "methods": []}],
        "relationships": [{"source": "Member", "target": "Book", "type": "association"}],
    }
    result = validate_spec_json(data, "class")
    assert result.ok
    prose = spec_to_prose(result.data)
    assert "Book" in prose
    metrics = validity_metrics(result.data)
    assert metrics["json_valid"]
    assert metrics["entity_count"] == 1


def test_ensure_valid_falls_back_from_prose():
    prose = "- Book: title\n- Member: name\n- Member associates with Book\n"
    data, out, msgs = ensure_valid_spec(prose, "class")
    assert data["entities"]
    assert "Book" in out or any(e["name"] == "Book" for e in data["entities"])
    assert msgs  # notes fallback


def test_heuristic_flowchart_has_steps():
    data = heuristic_spec_from_text("1. Start\n2. Work\n3. End\n- Job: task", "flowchart")
    assert len(data.get("process_steps") or []) >= 2
