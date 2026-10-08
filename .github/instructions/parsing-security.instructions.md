---
description: "Use when parsing Apple Health export data, working with XML/GPX, or touching src/logic/. Covers lxml security requirements and numeric handling."
applyTo: "src/logic/**"
---

# Parsing and Data Handling

## Parsing and security
- Keep XML parsing on `lxml.etree` with `resolve_entities=False, no_network=True` (never use stdlib `ElementTree` for untrusted XML parsing).
- Preserve streaming parsing patterns (`iterparse` with `tag=` filtering + `elem.clear()` and deleting previous siblings) for large files.
- `ExportParser` remains a context manager and should be used with `with ExportParser() as ep:`.
- If an Apple Health export is invalid or corrupted and cannot be parsed, display an error message and log the issue.

## Data and numeric handling
- Convert numeric XML attributes/values to `int`/`float` at parse time.
