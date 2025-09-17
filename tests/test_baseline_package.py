from __future__ import annotations

from pathlib import Path
from runpy import run_path

run_path(Path(__file__).resolve().with_name("_baseline_imports.py"))

import op_observe


def test_op_observe_exports_match_baseline(baseline_packages: tuple[str, ...]) -> None:
    """Ensure the package exposes the canonical baseline namespace."""

    assert isinstance(op_observe.__all__, list)
    assert op_observe.__all__ == list(baseline_packages)


def test_op_observe_dir_contains_baseline_exports(
    baseline_packages: tuple[str, ...]
) -> None:
    """``dir(op_observe)`` should surface the reserved namespace entries."""

    module_dir = set(dir(op_observe))
    for name in baseline_packages:
        assert name in module_dir


def test_gitignore_contains_baseline_patterns() -> None:
    """Verify the unified ignore rules are present and well documented."""

    gitignore_path = Path(__file__).resolve().parents[1] / ".gitignore"
    lines = gitignore_path.read_text().splitlines()
    patterns = [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]

    required_patterns = [
        "env/",
        "__pycache__/",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        "build/",
        "dist/",
        "*.egg-info/",
        ".eggs/",
        "pip-wheel-metadata/",
        "vendor/",
        "*.log",
        ".coverage",
        "coverage.xml",
        "htmlcov/",
        ".pytest_cache/",
        ".tox/",
        ".nox/",
        ".mypy_cache/",
        ".pyre/",
        ".ruff_cache/",
    ]

    for pattern in required_patterns:
        assert pattern in patterns, f"{pattern} missing from baseline .gitignore"

    assert len(patterns) == len(
        set(patterns)
    ), "Duplicate ignore patterns detected in baseline .gitignore"

    comment_lines = [line for line in lines if line.strip().startswith("#")]
    assert any(
        "baseline" in line.lower() for line in comment_lines
    ), "Expected baseline documentation comments in .gitignore"
