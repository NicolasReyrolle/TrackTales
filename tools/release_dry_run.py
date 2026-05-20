"""Local dry-run helper for the release workflow."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local dry run of the release flow.")
    parser.add_argument("--release-notes", default="", help="Optional maintainer notes.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest execution.")
    parser.add_argument("--skip-python-build", action="store_true", help="Skip wheel/sdist build.")
    parser.add_argument("--skip-pyinstaller", action="store_true", help="Skip PyInstaller build.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep the temporary workspace.")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run(command: list[str], cwd: Path) -> None:
    print(f"[run] {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def git_output(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def compute_version(root: Path) -> tuple[str, str, str]:
    current_month = datetime.now().strftime("%Y.%m")
    tags = git_output(["tag", "-l", "--sort=version:refname", f"v{current_month}.*"], root)
    last_tag = tags.splitlines()[-1] if tags else ""
    last_patch = int(last_tag.rsplit(".", 1)[-1]) if last_tag else 0
    new_version = f"{current_month}.{last_patch + 1}"
    return new_version, f"v{new_version}", last_tag


def release_notes(root: Path, tag: str, last_tag: str, user_notes: str) -> str:
    version = tag.removeprefix("v")
    if last_tag:
        changes = git_output(["log", "--oneline", f"{last_tag}..HEAD"], root)
    else:
        changes = git_output(["log", "--oneline"], root)
    lines = [
        f"# TrackTales {version}",
        "",
        "## Install",
        "",
        "- Windows: download the .exe asset from this release and run it directly.",
        "- macOS: download the .dmg asset from this release and drag the app to Applications.",
        f"- Python users: `pip install tracktales=={version}`",
        "",
        "## Changes",
    ]
    lines.extend(f"- {line}" for line in changes.splitlines() if line)
    if user_notes:
        lines.extend(["", "## Maintainer Notes", user_notes])
    return "\n".join(lines) + "\n"


def copy_workspace(root: Path) -> Path:
    temp_root = Path(tempfile.mkdtemp(prefix="tracktales-release-dry-run-"))
    workspace = temp_root / root.name
    shutil.copytree(
        root,
        workspace,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            "build",
            "dist",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "__pycache__",
        ),
    )
    return workspace


def write_version(workspace: Path, version: str) -> None:
    pyproject = workspace / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    text = re.sub(r'^version = ".*"$', f'version = "{version}"', text, flags=re.M)
    pyproject.write_text(text, encoding="utf-8")


def copy_outputs(workspace: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    dist = workspace / "dist"
    if dist.exists():
        for artifact in dist.iterdir():
            target = output_dir / artifact.name
            if artifact.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(artifact, target)
            else:
                shutil.copy2(artifact, target)


def main() -> int:
    args = parse_args()
    root = repo_root()
    version, tag, last_tag = compute_version(root)
    notes = release_notes(root, tag, last_tag, args.release_notes)
    workspace = copy_workspace(root)
    output_dir = root / "output" / "release-dry-run"

    print(f"Dry run version: {version}")
    print(f"Dry run tag: {tag}")
    print(f"Workspace: {workspace}")

    try:
        write_version(workspace, version)
        (workspace / "release-notes.md").write_text(notes, encoding="utf-8")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "release-notes.md").write_text(notes, encoding="utf-8")

        if not args.skip_python_build:
            run([sys.executable, "-m", "build"], workspace)
        if not args.skip_tests:
            run([sys.executable, "-m", "pytest", "--cov=src", "tests/"], workspace)
        if not args.skip_pyinstaller:
            run([sys.executable, "-m", "PyInstaller", "tracktales.spec"], workspace)

        copy_outputs(workspace, output_dir)
        print(f"Dry-run artifacts written to: {output_dir}")
        return 0
    finally:
        if args.keep_temp:
            print(f"Temporary workspace kept at: {workspace}")
        else:
            shutil.rmtree(workspace.parent, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
