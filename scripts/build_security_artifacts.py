#!/usr/bin/env python3
"""Assemble HTML/JSON security reports and evidence bundles."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from security_pipeline import (
    build_security_payload,
    load_security_config,
    write_security_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/security_targets.toml"),
        help="Path to the security configuration file.",
    )
    parser.add_argument(
        "--radar",
        type=Path,
        default=Path("reports/radar-findings.json"),
        help="Radar findings JSON file.",
    )
    parser.add_argument(
        "--vulnerabilities",
        type=Path,
        default=Path("reports/dependency-vulnerabilities.json"),
        help="Dependency vulnerability findings JSON file.",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=Path("reports/security-report.html"),
        help="Destination HTML report path.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("reports/security-report.json"),
        help="Destination JSON report path.",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("reports/security-evidence.zip"),
        help="Destination evidence bundle zip path.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("reports/security-summary.md"),
        help="Markdown summary output path.",
    )
    parser.add_argument(
        "--commit",
        default=os.environ.get("GITHUB_SHA"),
        help="Commit hash to embed in the report metadata.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Expected input file missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _attachment_paths(*paths: Path) -> Iterable[Path]:
    for item in paths:
        if item.exists():
            yield item


def main() -> None:
    args = parse_args()
    config = load_security_config(args.config)
    radar_data = _load_json(args.radar)
    vulnerability_data = _load_json(args.vulnerabilities)

    payload = build_security_payload(
        config,
        radar=radar_data,
        vulnerabilities=vulnerability_data,
        commit=args.commit,
    )

    summary = write_security_artifacts(
        payload,
        html_path=args.html,
        json_path=args.json,
        evidence_path=args.evidence,
        summary_path=args.summary,
        attachments=list(_attachment_paths(args.radar, args.vulnerabilities)),
    )

    print(summary)


if __name__ == "__main__":
    main()
