#!/usr/bin/env python3
"""Validate enforceable repository rules from copilot instructions.

This script intentionally checks only objective/measurable constraints.
"""

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_MODULE_LINES = 1000


@dataclass(frozen=True)
class Violation:
    rel_path: str
    message: str


def _git_tracked_python_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    files = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    return [repo_root / rel_path for rel_path in files]


def _changed_python_files(repo_root: Path, diff_range: str) -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--name-only", diff_range, "--", "*.py"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    files = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    return [repo_root / rel_path for rel_path in files]


def _line_count(path: Path) -> int:
    return sum(1 for _ in path.open("r", encoding="utf-8"))


def _check_module_line_limit(python_files: list[Path], repo_root: Path) -> list[Violation]:
    errors: list[Violation] = []
    for path in python_files:
        line_count = _line_count(path)
        if line_count >= MAX_MODULE_LINES:
            rel_path = path.relative_to(repo_root).as_posix()
            errors.append(
                Violation(
                    rel_path=rel_path,
                    message=f"{line_count} lines (must be < {MAX_MODULE_LINES} lines).",
                )
            )
    return errors


def _collect_init_logic_names(source: str) -> set[str]:
    module = ast.parse(source)
    names: set[str] = set()
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def _collect_init_logic_names_safe(source: str) -> tuple[set[str] | None, str | None]:
    try:
        return _collect_init_logic_names(source), None
    except SyntaxError as exc:
        return None, exc.msg


def _build_init_logic_error_lines(
    rel_path: str, logic_names: set[str], message_template: str
) -> list[Violation]:
    return [
        Violation(rel_path=rel_path, message=message_template.format(name=name))
        for name in sorted(logic_names)
    ]


def _check_init_files_for_heavy_logic(python_files: list[Path], repo_root: Path) -> list[Violation]:
    errors: list[Violation] = []
    init_files = [path for path in python_files if path.name == "__init__.py"]

    for path in init_files:
        source = path.read_text(encoding="utf-8")
        head_logic_names, parse_error = _collect_init_logic_names_safe(source)
        if parse_error is not None:
            rel_path = path.relative_to(repo_root).as_posix()
            errors.append(
                Violation(
                    rel_path=rel_path,
                    message=f"syntax error while parsing ({parse_error}).",
                )
            )
            continue
        assert head_logic_names is not None

        if not head_logic_names:
            continue

        rel_path = path.relative_to(repo_root).as_posix()
        errors.extend(
            _build_init_logic_error_lines(
                rel_path,
                head_logic_names,
                "contains top-level logic '{name}'. Keep __init__.py minimal (imports/setup only).",
            )
        )

    return errors


def _classify_violations(
    violations: list[Violation], changed_rel_paths: set[str] | None
) -> tuple[list[Violation], list[Violation]]:
    if changed_rel_paths is None:
        return violations, []

    blocking = [violation for violation in violations if violation.rel_path in changed_rel_paths]
    warnings = [
        violation for violation in violations if violation.rel_path not in changed_rel_paths
    ]
    return blocking, warnings


def _print_annotations(prefix: str, violations: list[Violation]) -> None:
    for violation in violations:
        print(f"::{prefix} file={violation.rel_path}::{violation.message}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--diff-range",
        help=(
            "Optional git diff range (for example, <base>..<head>). "
            "When provided, changed files are treated as blocking scope and "
            "non-changed files are warnings only."
        ),
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    try:
        python_files = _git_tracked_python_files(repo_root)
    except subprocess.CalledProcessError as exc:
        print("Failed to list tracked Python files via git.", file=sys.stderr)
        print(exc.stderr, file=sys.stderr)
        return 2

    if not python_files:
        print("No Python files to validate for the selected scope.")
        return 0

    changed_rel_paths: set[str] | None = None
    if args.diff_range:
        try:
            changed_rel_paths = {
                path.relative_to(repo_root).as_posix()
                for path in _changed_python_files(repo_root, args.diff_range)
            }
        except subprocess.CalledProcessError as exc:
            print("Failed to list changed Python files via git.", file=sys.stderr)
            print(exc.stderr, file=sys.stderr)
            return 2

    violations: list[Violation] = []
    violations.extend(_check_module_line_limit(python_files, repo_root))
    violations.extend(_check_init_files_for_heavy_logic(python_files, repo_root))
    blocking, warnings = _classify_violations(violations, changed_rel_paths)

    if warnings:
        print("Copilot-instruction policy warnings (outside PR-edited Python files):\n")
        for violation in warnings:
            print(f"- {violation.rel_path}: {violation.message}")
        _print_annotations("warning", warnings)

    if blocking:
        print("Copilot-instruction policy violations in PR-edited Python files:\n")
        for violation in blocking:
            print(f"- {violation.rel_path}: {violation.message}")
        _print_annotations("error", blocking)
        print(
            "\nNote: this CI check enforces only objective subsets of instructions "
            "(line limits and __init__.py minimal logic)."
        )
        return 1

    if warnings:
        print("Copilot-instruction policy check passed with warnings.")
    else:
        print("Copilot-instruction policy check passed.")
    print(f"Checked {len(python_files)} Python files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
