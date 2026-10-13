import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / ".github" / "scripts"))

from triage_agent.analysis import analyze_issue  # noqa: E402


def test_analyze_issue_classifies_reproducible_crash_as_high_severity_bug():
    result = analyze_issue(
        "App crashes while importing",
        "Steps to reproduce: import the attached sample XML.",
    )

    assert result.classification == "bug"
    assert result.severity == "high"
    assert result.is_testable


def test_analyze_issue_classifies_feature_request_as_low_severity():
    result = analyze_issue("Feature request: improve chart colors", "")

    assert result.classification == "enhancement"
    assert result.severity == "low"
    assert not result.is_testable


def test_analyze_issue_classifies_question_without_bug_terms():
    result = analyze_issue("How do I export a workout?", "")

    assert result.classification == "question"
    assert result.severity == "low"
