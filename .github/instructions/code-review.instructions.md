---
description: "Instructions for Copilot code review on GitHub pull requests only."
applyTo: "**"
excludeAgent: "coding-agent"
---

# Copilot Code Review

Be concise. Comment only on issues worth a developer's time; stay silent otherwise. Do not summarize the PR or praise code.

## Report only
- Bugs and logic errors (wrong results, unhandled edge cases, regressions, float equality on computed values).
- Security issues in XML/GPX/ZIP handling: XML must be parsed with `lxml.etree` using `resolve_entities=False, no_network=True`; never stdlib `ElementTree` on untrusted input; no unsafe ZIP extraction (path traversal, unbounded sizes).
- Missing or broken tests for changed behavior.

## Do not comment on
- Formatting, naming, import order, type-annotation style, or complexity: ruff, mypy and CI already enforce these.
- Generated or catalog files: `src/i18n/locales/**` (`.po`, `.pot`, `.mo`), `build/`, `output/`, `logs/`, `cov_annotated/`, `*.egg-info/`, `*.log`.
- Documentation-only or comment-only changes.
- Commit message or PR title wording.
- Optional refactors, speculative improvements, or issues in code the PR did not change.

## Rules
- One comment per distinct root cause; do not repeat it on every occurrence.
- Only suggest a fix when you are confident it is correct.
