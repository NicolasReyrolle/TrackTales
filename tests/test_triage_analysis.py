import sys
from importlib import import_module
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github" / "scripts"))
analyze_issue = import_module("triage_agent.analysis").analyze_issue


@pytest.mark.parametrize(
    ("body", "classification"),
    [
        ("Duplicate workouts are shown after import.", "bug"),
        ("Duplicate of #123.", "invalid"),
    ],
)
def test_duplicate_classification_requires_issue_reference(body: str, classification: str) -> None:
    assert analyze_issue("Issue", body).classification == classification


@pytest.mark.parametrize(
    "title",
    [
        "Why does importing keep failing?",
        "Why is the app crashing?",
    ],
)
def test_bug_inflections_take_priority_over_question_wording(title: str) -> None:
    assert analyze_issue(title, "").classification == "bug"


@pytest.mark.parametrize(
    "body",
    [
        "Steps to reproduce: unknown",
        "Expected behavior:",
        "Sample XML",
        "Steps to reproduce: ...",
    ],
)
def test_empty_test_evidence_is_not_testable(body: str) -> None:
    assert not analyze_issue("Issue", body).is_testable


@pytest.mark.parametrize(
    "body",
    [
        "Steps to reproduce: Import the export and open the trends tab.",
        "Expected behavior\nThe app should show the workout.",
        "Attached sample: health-export.xml",
    ],
)
def test_actionable_test_evidence_is_testable(body: str) -> None:
    assert analyze_issue("Issue", body).is_testable
