"""Execution helpers for the Agentic Radar CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .detectors import MCPDetector, ToolInventoryDetector, VulnerabilityDetector, run_detectors
from .models import ParsedProject, RadarReport, ScenarioResult
from .object_store import LocalObjectStore
from .parser import ProjectParser
from .reporting import build_report
from .testing import TestRunner


@dataclass
class ScanConfig:
    """Configuration for a radar scan run."""

    root: Path
    output_path: Path
    object_store_path: Optional[Path] = None
    trace_ids: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    detectors: Optional[Sequence] = None
    parser: Optional[ProjectParser] = None
    include_project_snapshot: bool = True


@dataclass
class ScanResult:
    """Result of executing a radar scan."""

    report: RadarReport
    output_path: Path
    stored_artifact: Optional[Path]


@dataclass
class TestConfig(ScanConfig):
    """Configuration for a radar test run."""

    __test__ = False
    scenarios: List[str] = field(default_factory=list)


@dataclass
class TestResult:
    """Result of executing radar tests."""

    __test__ = False
    report: RadarReport
    output_path: Path
    stored_artifact: Optional[Path]
    scenario_results: List[ScenarioResult]


def _default_detectors() -> List:
    return [ToolInventoryDetector(), MCPDetector(), VulnerabilityDetector()]


def _resolve_detectors(detectors: Optional[Sequence]) -> List:
    if detectors is None:
        return _default_detectors()
    return list(detectors)


def _parse_project(config: ScanConfig) -> ParsedProject:
    parser = config.parser or ProjectParser()
    return parser.parse(config.root)


def _write_and_store(report: RadarReport, config: ScanConfig) -> Optional[Path]:
    output_path = Path(config.output_path)
    report.write_json(output_path)
    stored_artifact: Optional[Path] = None
    if config.object_store_path:
        store = LocalObjectStore(config.object_store_path)
        stored_artifact = store.put_file(output_path, destination_name=output_path.name)
    return stored_artifact


def run_scan(config: ScanConfig) -> ScanResult:
    project = _parse_project(config)
    detectors = _resolve_detectors(config.detectors)
    findings = run_detectors(project, detectors)
    metadata = dict(config.metadata)
    metadata.setdefault("mode", "scan")
    metadata.setdefault("detectors", [getattr(detector, "name", "detector") for detector in detectors])
    metadata.setdefault("trace_id_count", len(config.trace_ids))

    report = build_report(
        project,
        findings,
        mode="scan",
        trace_ids=config.trace_ids,
        metadata=metadata,
        include_project_snapshot=config.include_project_snapshot,
    )

    stored_artifact = _write_and_store(report, config)
    return ScanResult(report=report, output_path=Path(config.output_path), stored_artifact=stored_artifact)


def run_test(config: TestConfig) -> TestResult:
    project = _parse_project(config)
    detectors = _resolve_detectors(config.detectors)
    findings = run_detectors(project, detectors)

    test_runner = TestRunner()
    scenario_names = list(config.scenarios) if config.scenarios else list(test_runner.scenarios)
    scenario_findings, scenario_results = test_runner.run(project, override_scenarios=scenario_names)
    all_findings = findings + scenario_findings

    metadata = dict(config.metadata)
    metadata.setdefault("mode", "test")
    metadata.setdefault("detectors", [getattr(detector, "name", "detector") for detector in detectors] + ["scenario-runner"])
    metadata.setdefault("trace_id_count", len(config.trace_ids))
    metadata["scenarios"] = scenario_names
    metadata["scenario_failures"] = [result.name for result in scenario_results if result.status == "failed"]

    report = build_report(
        project,
        all_findings,
        mode="test",
        trace_ids=config.trace_ids,
        scenario_results=scenario_results,
        metadata=metadata,
        include_project_snapshot=config.include_project_snapshot,
    )

    stored_artifact = _write_and_store(report, config)
    return TestResult(
        report=report,
        output_path=Path(config.output_path),
        stored_artifact=stored_artifact,
        scenario_results=scenario_results,
    )
