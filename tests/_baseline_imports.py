"""Baseline helper to ensure the repository root is importable during tests.

This module is part of the merge-conflict prevention baseline. Execute it via
``run_path`` from test modules to guarantee that :mod:`op_observe` can be
resolved without customising individual conftest files.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
