---
description: "Use when parsing Apple Health export data, working with XML/GPX, or touching src/logic/. Covers lxml security requirements and numeric handling."
applyTo: "src/logic/**"
excludeAgent: "code-review"
---

# Parsing and Data Handling

## Parsing and security
- Keep XML parsing on `lxml.etree` with `resolve_entities=False, no_network=True` (never use stdlib `ElementTree` for untrusted XML parsing).
- Preserve streaming parsing patterns (`iterparse` with `tag=` filtering + `elem.clear()` and deleting previous siblings) for all export files, since Apple Health exports can exceed 1 GB.
- GPX files use the namespace `http://www.topografix.com/GPX/1/1`. Apply the same lxml security settings and streaming pattern to GPX parsing, using the GPX namespace in `tag=` filters. Convert `lat`, `lon`, and `ele` attributes to `float`.
- `ExportParser` remains a context manager and should be used with `with ExportParser() as ep:`.
- If an Apple Health export is invalid or corrupted and cannot be parsed, raise a `ValueError` with a message that includes the file path, and log the error at ERROR level using `logging.getLogger(__name__)`. Do not print to stdout. If parsing fails after records have been yielded, stop iteration, log the failing file path and the last successfully parsed record index, and raise the error. Do not return partial results silently.

## Data and numeric handling
- Convert the `value` attribute of `Record` elements to `float`. Convert `count` and `sourceVersion`-independent integer fields to `int`. Keep date and string attributes as `str`. If conversion raises `ValueError`, log a warning and skip that element.
