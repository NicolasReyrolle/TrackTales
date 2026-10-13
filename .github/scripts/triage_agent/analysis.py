import re
from typing import Literal

from .models import TriageAnalysis

_BUG_TERMS = re.compile(
    r"\b(?:bugs?|errors?|crash(?:es|ed|ing)?|fail(?:s|ures?|ed|ing)?|incorrect|wrong|regressions?)\b"
)
_FEATURE_TERMS = re.compile(r"\b(?:feature|enhancement|improve|request|support)\b")
_QUESTION_TERMS = re.compile(r"\b(?:how|what|why|question|help)\b")
_INVALID_TERMS = re.compile(r"\b(?:spam|unrelated|duplicate|not an issue)\b")
_CRITICAL_TERMS = re.compile(r"\b(?:data loss|corrupt(?:ion|ed)?|security|vulnerability)\b")
_HIGH_TERMS = re.compile(r"\b(?:crash(?:es|ed)?|exception|traceback|unusable|blocking)\b")
_TEST_EVIDENCE = re.compile(
    r"\b(?:steps to reproduce|to reproduce|reproduction|steps:|expected behavior|"
    r"actual behavior|traceback|sample (?:xml|gpx))\b"
)


def analyze_issue(title: str, body: str) -> TriageAnalysis:
    text = f"{title}\n{body}".lower()

    classification: Literal["bug", "enhancement", "question", "invalid"]
    if _INVALID_TERMS.search(text):
        classification = "invalid"
    elif _FEATURE_TERMS.search(text):
        classification = "enhancement"
    elif _QUESTION_TERMS.search(text) and not _BUG_TERMS.search(text):
        classification = "question"
    else:
        classification = "bug"

    severity: Literal["low", "medium", "high", "critical"]
    if _CRITICAL_TERMS.search(text):
        severity = "critical"
    elif _HIGH_TERMS.search(text):
        severity = "high"
    elif classification != "bug":
        severity = "low"
    else:
        severity = "medium"

    summary = title.strip() or "Issue submitted without a title"
    return TriageAnalysis(
        classification=classification,
        severity=severity,
        is_testable=bool(_TEST_EVIDENCE.search(text)),
        summary=summary,
        suggested_labels=[],
        formatted_comment=(
            f"Automated triage classified this as **{classification}** "
            f"with **{severity}** severity.\n\n**Summary:** {summary}"
        ),
    )
