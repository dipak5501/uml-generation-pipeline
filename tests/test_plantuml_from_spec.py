"""Spec-faithful PlantUML builder and fidelity gate."""

from app.services.plantuml_from_spec import (
    ensure_faithful_plantuml,
    fidelity_report,
    plantuml_from_spec,
)
from app.services.spec_json import extract_named_concepts, structure_to_spec_json
from app.services.plantuml_validate import validate_diagram


def test_extract_library_concepts():
    text = (
        "Library management system with classes Book, Member, Loan, and Librarian. "
        "A Member borrows a Book through a Loan."
    )
    names = extract_named_concepts(text)
    for required in ("Book", "Member", "Loan", "Librarian"):
        assert required in names


def test_class_builder_includes_all_entities():
    spec = {
        "diagram_type": "class",
        "entities": [
            {"name": "Book", "attributes": ["title: str"], "methods": ["borrow()"]},
            {"name": "Member", "attributes": ["name: str"], "methods": []},
            {"name": "Loan", "attributes": [], "methods": []},
            {"name": "Librarian", "attributes": [], "methods": []},
        ],
        "relationships": [
            {"source": "Member", "target": "Loan", "type": "association"},
            {"source": "Loan", "target": "Book", "type": "association"},
            {"source": "Librarian", "target": "Book", "type": "association"},
        ],
    }
    code = plantuml_from_spec(spec, "class")
    assert validate_diagram(code, "class").ok
    for name in ("Book", "Member", "Loan", "Librarian"):
        assert name in code
    assert "Module" not in code


def test_package_builder_uses_named_packages():
    spec = {
        "diagram_type": "package",
        "entities": [
            {"name": "Accounts"},
            {"name": "Transactions"},
            {"name": "Reporting"},
        ],
        "relationships": [
            {"source": "Transactions", "target": "Accounts", "type": "dependency"},
            {"source": "Reporting", "target": "Transactions", "type": "dependency"},
        ],
        "packages": [
            {"name": "Accounts", "contains": ["Accounts"]},
            {"name": "Transactions", "contains": ["Transactions"]},
            {"name": "Reporting", "contains": ["Reporting"]},
        ],
    }
    code = plantuml_from_spec(spec, "package")
    assert validate_diagram(code, "package").ok
    assert "package Accounts" in code
    assert "Reporting" in code
    assert "Module" not in code


def test_component_no_double_service_suffix():
    spec = {
        "diagram_type": "component",
        "entities": [{"name": "CartService"}, {"name": "PaymentService"}],
        "components": [
            {"name": "CartService", "interfaces": ["ICart"]},
            {"name": "PaymentService", "interfaces": ["IPayment"]},
            {"name": "InventoryService", "interfaces": ["IInventory"]},
        ],
        "relationships": [
            {"source": "CartService", "target": "InventoryService", "type": "dependency"}
        ],
    }
    code = plantuml_from_spec(spec, "component")
    assert "CartServiceService" not in code
    assert "InventoryService" in code
    assert validate_diagram(code, "component").ok


def test_fidelity_replaces_generic_module_output():
    spec = {
        "diagram_type": "class",
        "entities": [{"name": "Book"}, {"name": "Member"}, {"name": "Librarian"}],
        "relationships": [{"source": "Member", "target": "Book", "type": "association"}],
    }
    bad = "@startuml\nclass Module1\nclass Module2\nModule1 --> Module2\n@enduml\n"
    fixed, report = ensure_faithful_plantuml(bad, spec, "class")
    assert report.get("replaced")
    assert "Librarian" in fixed
    assert "Module1" not in fixed


def test_structure_json_from_python():
    code = '''
class User:
    def authenticate(self, password: str) -> bool:
        return True
class Order:
    def __init__(self, user: User):
        self.user = user
class Payment:
    def charge(self, order: Order) -> bool:
        return True
'''
    data = structure_to_spec_json(code, "class")
    names = {e["name"] for e in data["entities"]}
    assert {"User", "Order", "Payment"} <= names
    assert fidelity_report(plantuml_from_spec(data, "class"), data, "class")["ok"]
