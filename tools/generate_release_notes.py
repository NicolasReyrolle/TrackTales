"""Generate release notes with a Conventional Commit grouped changelog."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?: (?P<description>.+)$"
)

SECTION_ORDER = [
    ("feat", "Features"),
    ("fix", "Bug Fixes"),
    ("perf", "Performance"),
    ("refactor", "Refactoring"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("build", "Build System"),
    ("ci", "CI"),
    ("chore", "Chores"),
    ("revert", "Reverts"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate release notes from git history.")
    parser.add_argument("--tag", required=True, help="Target release tag, for example v2026.05.2")
    parser.add_argument(
        "--last-tag", default="", help="Previous release tag used as changelog start."
    )
    parser.add_argument("--release-notes", default="", help="Optional maintainer notes.")
    parser.add_argument("--output", default="release-notes.md", help="Output file path.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root where git log is evaluated.",
    )
    return parser.parse_args()


def git_log_subjects(repo_root: Path, last_tag: str) -> list[tuple[str, str]]:
    command = ["git", "log", "--pretty=format:%h%x09%s"]
    if last_tag:
        command.append(f"{last_tag}..HEAD")

    output = subprocess.check_output(command, cwd=repo_root, text=True)
    entries: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        sha, subject = (line.split("\t", 1) + [""])[:2]
        entries.append((sha.strip(), subject.strip()))
    return entries


def format_commit_line(description: str, scope: str | None, sha: str) -> str:
    if scope:
        return f"- **{scope}**: {description} ({sha})"
    return f"- {description} ({sha})"


def grouped_changelog_lines(commits: list[tuple[str, str]]) -> list[str]:
    grouped: dict[str, list[str]] = {kind: [] for kind, _ in SECTION_ORDER}
    breaking: list[str] = []
    other: list[str] = []

    for sha, subject in commits:
        match = CONVENTIONAL_COMMIT_RE.match(subject)
        if not match:
            other.append(f"- {subject} ({sha})")
            continue

        commit_type = match.group("type")
        scope = match.group("scope")
        description = match.group("description")
        line = format_commit_line(description, scope, sha)

        if match.group("breaking"):
            breaking.append(line)
            continue

        if commit_type in grouped:
            grouped[commit_type].append(line)
        else:
            other.append(f"- {subject} ({sha})")

    lines: list[str] = ["## Changelog", ""]
    has_changes = False

    if breaking:
        has_changes = True
        lines.extend(["### Breaking Changes", *breaking, ""])

    for commit_type, section_title in SECTION_ORDER:
        section_lines = grouped[commit_type]
        if not section_lines:
            continue
        has_changes = True
        lines.extend([f"### {section_title}", *section_lines, ""])

    if other:
        has_changes = True
        lines.extend(["### Other Changes", *other, ""])

    if not has_changes:
        lines.extend(["- No user-facing changes in this release.", ""])

    return lines


def build_release_notes(repo_root: Path, tag: str, last_tag: str, user_notes: str) -> str:
    version = tag.removeprefix("v")
    commits = git_log_subjects(repo_root, last_tag)

    lines = [
        f"# TrackTales {version}",
        "",
        "## Install",
        "",
        "- Windows: download the .exe asset from this release and run it directly.",
        "- macOS: download the .dmg asset from this release and drag the app to Applications.",
        f"- Python users: `pip install tracktales=={version}`",
        "",
    ]
    lines.extend(grouped_changelog_lines(commits))

    if user_notes:
        lines.extend(["## Maintainer Notes", user_notes, ""])

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    notes = build_release_notes(repo_root, args.tag, args.last_tag, args.release_notes)
    output_path = Path(args.output)
    output_path.write_text(notes, encoding="utf-8")
    print(f"Release notes written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
