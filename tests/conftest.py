"""Baseline pytest configuration shared across all modules.

This file is part of the repository-wide merge-conflict prevention baseline.
Feature branches must not modify it; request changes through the baseline
update process instead.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def baseline_packages() -> tuple[str, ...]:
    """Return the canonical top-level packages exported by :mod:`op_observe`."""

    return (
        "observability",
        "security",
        "retrieval",
        "telemetry",
        "enablement",
        "core",
    )
