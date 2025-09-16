"""Command line interface for Agentic Radar."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .evidence import create_evidence_pack
from .runner import ScanConfig, TestConfig, run_scan, run_test


class CLIError(Exception):
    """Raised for CLI usage errors."""


def _add_common_run_arguments(parser: argparse.ArgumentParser, *, default_output: str) -> None:
    parser.add_argument("path", nargs="?", default=".", help="Project root to scan")
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        default=None,
        help="Path to write the JSON report (defaults to project root)",
    )
    parser.add_argument(
        "--object-store",
        dest="object_store",
        default=None,
        help="Optional path to a directory-backed object store",
    )
    parser.add_argument(
        "--trace-id",
        dest="trace_ids",
        action="append",
        default=None,
        help="Trace identifier to include in the report metadata (repeatable)",
    )
    parser.add_argument(
        "--label",
        dest="labels",
        action="append",
        default=None,
        metavar="KEY=VALUE",
        help="Attach metadata labels to the report",
    )
    parser.add_argument(
        "--no-project-snapshot",
        dest="include_snapshot",
        action="store_false",
        help="Skip embedding the project snapshot in the report",
    )
    parser.set_defaults(default_output=default_output)


def _parse_labels(pairs: Optional[Iterable[str]]) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    if not pairs:
        return metadata
    for pair in pairs:
        if "=" not in pair:
            raise CLIError(f"Invalid label '{pair}', expected KEY=VALUE")
        key, value = pair.split("=", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def _resolve_output_path(root: Path, provided: Optional[str], default_filename: str) -> Path:
    if provided:
        return Path(provided)
    return root / default_filename


def _handle_scan(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    output_path = _resolve_output_path(root, args.output, args.default_output)
    metadata = _parse_labels(args.labels)
    config = ScanConfig(
        root=root,
        output_path=output_path,
        object_store_path=Path(args.object_store) if args.object_store else None,
        trace_ids=list(args.trace_ids or []),
        metadata=metadata,
        include_project_snapshot=args.include_snapshot,
    )
    result = run_scan(config)
    _print_report_summary(result.report, output_path=result.output_path, stored_artifact=result.stored_artifact)
    return 0


def _handle_test(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    output_path = _resolve_output_path(root, args.output, args.default_output)
    metadata = _parse_labels(args.labels)
    config = TestConfig(
        root=root,
        output_path=output_path,
        object_store_path=Path(args.object_store) if args.object_store else None,
        trace_ids=list(args.trace_ids or []),
        metadata=metadata,
        include_project_snapshot=args.include_snapshot,
        scenarios=list(args.scenarios or []),
    )
    result = run_test(config)
    _print_report_summary(result.report, output_path=result.output_path, stored_artifact=result.stored_artifact)
    _print_scenario_summary(result.scenario_results)
    return 0


def _handle_evidence_pack(args: argparse.Namespace) -> int:
    if not args.findings:
        raise CLIError("At least one --findings path must be provided")
    findings_paths = [Path(path) for path in args.findings]
    logs_path = Path(args.logs) if args.logs else None
    output_path = Path(args.output) if args.output else None
    result = create_evidence_pack(
        findings_paths,
        logs_path=logs_path,
        trace_ids=list(args.trace_ids or []),
        output_path=output_path,
        object_store_path=Path(args.object_store) if args.object_store else None,
    )
    _print_evidence_summary(result)
    return 0


def _print_report_summary(report, *, output_path: Path, stored_artifact: Optional[Path]) -> None:
    summary = report.summary.get("findings", {})
    print(f"Report written to {output_path}")
    print(f"Project: {report.project_name} | mode={report.mode}")
    if report.trace_ids:
        print(f"Trace IDs: {', '.join(report.trace_ids)}")
    print("Findings summary:")
    for severity in ["critical", "high", "medium", "low", "info", "unknown", "total"]:
        if severity in summary:
            print(f"  {severity}: {summary[severity]}")
    if stored_artifact:
        print(f"Stored artifact at {stored_artifact}")


def _print_scenario_summary(scenarios) -> None:
    if not scenarios:
        return
    print("Scenario results:")
    for result in scenarios:
        suffix = f" ({result.details})" if result.details else ""
        print(f"  {result.name}: {result.status}{suffix}")


def _print_evidence_summary(result) -> None:
    print(f"Evidence pack created at {result.pack_path}")
    findings_count = len(result.metadata.get("findings", []))
    logs_count = len(result.metadata.get("logs", []))
    print(f"Includes {findings_count} findings file(s) and {logs_count} log file(s)")
    if result.metadata.get("trace_ids"):
        print(f"Trace IDs: {', '.join(result.metadata['trace_ids'])}")
    if result.stored_path:
        print(f"Stored artifact at {result.stored_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentic-radar", description="Agentic Radar CLI")
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="Run a radar scan")
    _add_common_run_arguments(scan_parser, default_output="agentic-radar-report.json")
    scan_parser.set_defaults(handler=_handle_scan)

    test_parser = subparsers.add_parser("test", help="Run radar adversarial tests")
    _add_common_run_arguments(test_parser, default_output="agentic-radar-test-report.json")
    test_parser.add_argument(
        "--scenario",
        dest="scenarios",
        action="append",
        default=None,
        help="Scenario to execute (repeatable)",
    )
    test_parser.set_defaults(handler=_handle_test)

    evidence_parser = subparsers.add_parser("evidence", help="Evidence bundle operations")
    evidence_subparsers = evidence_parser.add_subparsers(dest="evidence_command")
    pack_parser = evidence_subparsers.add_parser("pack", help="Create an evidence pack")
    pack_parser.add_argument(
        "--findings",
        dest="findings",
        action="append",
        required=True,
        help="Path to a findings JSON file (repeatable)",
    )
    pack_parser.add_argument("--logs", dest="logs", default=None, help="Path to logs directory or file")
    pack_parser.add_argument(
        "--trace-id",
        dest="trace_ids",
        action="append",
        default=None,
        help="Trace identifier to embed in the evidence pack",
    )
    pack_parser.add_argument("-o", "--output", dest="output", default=None, help="Destination zip path")
    pack_parser.add_argument(
        "--object-store",
        dest="object_store",
        default=None,
        help="Optional path to store the evidence pack",
    )
    pack_parser.set_defaults(handler=_handle_evidence_pack)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 1
    try:
        return args.handler(args)
    except CLIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
