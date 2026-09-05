import subprocess
import sys
import tomllib
from pathlib import Path

from babel.messages.frontend import main as babel_main


def get_git_tag() -> str:
    """Retrieve the latest git tag, falling back to an empty string if unavailable."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def load_project_metadata() -> dict[str, str]:
    """Extract project metadata from pyproject.toml and git tag."""
    version = get_git_tag()

    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        return {
            "project": "",
            "version": version or "dev",
            "author": "",
            "email": "",
        }

    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project_data = data.get("project", {})

    authors = project_data.get("authors", [])
    first_author = authors[0] if authors else {}

    # Use git tag first, then pyproject version, then fallback to 'dev'
    if not version:
        version = project_data.get("version", "dev")

    return {
        "project": project_data.get("name", "").title(),
        "version": version,
        "author": first_author.get("name", ""),
        "email": first_author.get("email", ""),
    }


def clean_pot_header(pot_path: Path) -> None:
    """Remove placeholder and fuzzy/obsolete markers from the generated POT header."""
    if not pot_path.exists():
        return

    content = pot_path.read_text(encoding="utf-8")

    # Filter out unwanted comment lines
    lines = [
        line
        for line in content.splitlines(keepends=True)
        if not line.startswith("# FIRST AUTHOR <EMAIL@ADDRESS>")
        and line != "#, fuzzy\n"
        and line != "#, fuzzy\r\n"
        and not line.startswith("#~")
    ]

    cleaned_content = "".join(lines)

    # Clean up empty comment line leftover if present
    cleaned_content = cleaned_content.replace("#\n#\nmsgid", "#\nmsgid")

    pot_path.write_text(cleaned_content, encoding="utf-8")


def main() -> None:
    metadata = load_project_metadata()
    output_pot = Path("src/i18n/locales/messages.pot")

    args = [
        "pybabel",
        "extract",
        "-k",
        "t",
        "-k",
        "translate",
        "--sort-output",
        "--no-location",
        f"--project={metadata['project']}",
        f"--version={metadata['version']}",
        f"--copyright-holder={metadata['author']}",
        f"--msgid-bugs-address={metadata['email']}",
        "-o",
        str(output_pot),
        "src",
    ]

    sys.argv = args
    babel_main()

    # Clean up unwanted header lines
    clean_pot_header(output_pot)


if __name__ == "__main__":
    main()
