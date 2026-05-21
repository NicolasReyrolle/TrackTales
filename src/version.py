"""Version information for TrackTales."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path


def _get_version() -> str:
    """Return the installed package version, falling back to pyproject.toml."""
    try:
        return package_version("tracktales")
    except PackageNotFoundError:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            try:
                content = pyproject_path.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if line.startswith('version = "'):
                        return line.split('"')[1]
            except OSError:
                pass

    return "0.0.0.dev"


__version__ = _get_version()

__all__ = ["__version__"]
