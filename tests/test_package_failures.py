"""Package failure taxonomy + RQ3 chapter formatting."""

from app.services.package_failures import (
    classify_package_failure,
    format_package_failure_chapter,
    _wilson_ci,
)


def test_empty_package_classified():
    cats = classify_package_failure("@startuml\n@enduml\n", "empty or incomplete")
    assert "empty_or_incomplete" in cats
    assert "missing_package_block" in cats


def test_self_dependency_classified():
    code = """
@startuml
package core {
  class A
}
core ..> core
@enduml
"""
    cats = classify_package_failure(code, "Self-referential dependency")
    assert "self_dependency" in cats


def test_unbalanced_braces():
    cats = classify_package_failure("@startuml\npackage core {\nclass A\n@enduml\n")
    assert "unbalanced_braces" in cats


def test_wilson_ci_bounds():
    lo, hi = _wilson_ci(8, 100)
    assert lo is not None and hi is not None
    assert 0.0 <= lo < hi <= 1.0


def test_format_chapter_includes_claim_scope():
    md = format_package_failure_chapter(
        {
            "note": "Live only.",
            "package_total": 10,
            "package_successes": 8,
            "package_failures": 2,
            "failure_rate": 0.2,
            "failure_rate_ci95": {"low": 0.05, "high": 0.4},
            "mean_s_success": 4.1,
            "mean_s_failure": 0.0,
            "majority_accept_success_pct": 75.0,
            "by_category_rates": {
                "missing_package_block": {
                    "count": 2,
                    "share_of_failures": 1.0,
                    "share_of_packages": 0.2,
                }
            },
            "repair": {
                "artifacts_with_repair": 3,
                "repair_attempts": 4,
                "repair_successes": 2,
                "attempt_win_rate": 0.5,
                "rescued_artifacts": 1,
                "rescue_rate": 1 / 3,
            },
            "examples": {},
        }
    )
    assert "Claim scope" in md
    assert "Repair win-rate" in md
    assert "missing_package_block" in md
