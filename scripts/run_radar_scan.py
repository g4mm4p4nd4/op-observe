#!/usr/bin/env python3
"""Generate radar findings for the current repository configuration."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from security_pipeline import generate_radar_findings, load_security_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/security_targets.toml"),
        help="Path to the radar configuration file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/radar-findings.json"),
        help="Destination JSON file for radar findings.",
    )
    parser.add_argument(
        "--commit",
        default=os.environ.get("GITHUB_SHA"),
        help="Commit hash to embed in the findings.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_security_config(args.config)
    findings = generate_radar_findings(config, commit=args.commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    print(f"✅ Radar findings written to {args.output}")


if __name__ == "__main__":
    main()
