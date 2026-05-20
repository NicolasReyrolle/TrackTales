from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from pathlib import Path

import version


def test_get_version_uses_installed_distribution(monkeypatch) -> None:
    monkeypatch.setattr(version, "package_version", lambda _name: "2026.05.2")

    assert version._get_version() == "2026.05.2"


def test_get_version_falls_back_to_pyproject(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        version, "package_version", lambda _name: (_ for _ in ()).throw(PackageNotFoundError())
    )
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[project]\nversion = "2026.05.3"\n', encoding="utf-8")
    monkeypatch.setattr(version, "__file__", str(src_dir / "version.py"))

    assert version._get_version() == "2026.05.3"


def test_get_version_returns_dev_when_pyproject_missing_or_unreadable(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        version, "package_version", lambda _name: (_ for _ in ()).throw(PackageNotFoundError())
    )
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    monkeypatch.setattr(version, "__file__", str(src_dir / "version.py"))

    assert version._get_version() == "0.0.0.dev"

    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[project]\nversion = "2026.05.4"\n', encoding="utf-8")
    monkeypatch.setattr(
        Path, "read_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError())
    )

    assert version._get_version() == "0.0.0.dev"
