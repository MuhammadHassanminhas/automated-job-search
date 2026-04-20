"""
A.1 layout tests — verify required project paths exist and are non-empty.
Fails with AssertionError for each missing path until Builder creates them.
"""
from __future__ import annotations

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_PATHS = [
    "pyproject.toml",
    "app/__init__.py",
    "app/main.py",
    "web/package.json",
    "docker-compose.yml",
    ".env.example",
    "alembic.ini",
    "tests/conftest.py",
    ".github/workflows/ci.yml",
    ".gitignore",
]


@pytest.mark.parametrize("rel_path", REQUIRED_PATHS)
def test_required_path_exists(rel_path: str) -> None:
    assert (ROOT / rel_path).exists(), f"Required path does not exist: {rel_path}"


@pytest.mark.parametrize("rel_path", REQUIRED_PATHS)
def test_required_path_nonempty(rel_path: str) -> None:
    p = ROOT / rel_path
    assert p.exists(), f"Required path does not exist: {rel_path}"
    assert p.stat().st_size > 0, f"Required path is empty: {rel_path}"
