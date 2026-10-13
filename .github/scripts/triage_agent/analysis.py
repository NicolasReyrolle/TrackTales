import re
from typing import Literal

from .models import TriageAnalysis

_BUG_TERMS = re.compile(
    r"\b(?:bugs?|errors?|crash(?:es|ed|ing)?|fail(?:s|ures?|ed|ing)?|incorrect|wrong|regressions?)\b"
)
_FEATURE_TERMS = re.compile(r"\b(?:feature|enhancement|improve|request|support)\b")
_QUESTION_TERMS = re.compile(r"\b(?:how|what|why|question|help)\b")
_INVALID_TERMS = re.compile(r"\b(?:spam|unrelated|duplicate\s+of\s+#\d+|not an issue)\b")
_CRITICAL_TERMS = re.compile(r"\b(?:data loss|corrupt(?:ion|ed)?|security|vulnerability)\b")
_HIGH_TERMS = re.compile(r"\b(?:crash(?:es|ed)?|exception|traceback|unusable|blocking)\b")
_TEST_EVIDENCE_SECTION = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:steps(?: to reproduce)?|to reproduce|reproduction|"
    r"expected behavior|actual behavior|traceback|sample (?:xml|gpx))\s*:?\s*(.*)$",
    re.IGNORECASE,
)
_TEST_EVIDENCE_FILE = re.compile(r"\b[\w.-]+\.(?:xml|gpx)\b", re.IGNORECASE)
_NON_ACTIONABLE_EVIDENCE = re.compile(
    r"(?:unknown|n/?a|none(?: provided)?|tbd|todo|not provided|not applicable|no steps|no data)"
    r"[.!? ]*",
    re.IGNORECASE,
)


def _has_test_evidence(text: str) -> bool:
    if _TEST_EVIDENCE_FILE.search(text):
        return True

    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = _TEST_EVIDENCE_SECTION.match(line)
        if not match:
            continue

        evidence = match.group(1).strip()
        if not evidence:
            for next_line in lines[index + 1 :]:
                if not next_line.strip():
                    continue
                if _TEST_EVIDENCE_SECTION.match(next_line):
                    break
                evidence = next_line.strip()
                break

        evidence = evidence.strip(" \t*_`-")
        if (
            evidence
            and re.search(r"[a-z0-9]", evidence)
            and not _NON_ACTIONABLE_EVIDENCE.fullmatch(evidence)
        ):
            return True

    return False


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
        is_testable=_has_test_evidence(text),
        summary=summary,
        suggested_labels=[],
        formatted_comment=(
            f"Automated triage classified this as **{classification}** "
            f"with **{severity}** severity.\n\n**Summary:** {summary}"
        ),
    )
