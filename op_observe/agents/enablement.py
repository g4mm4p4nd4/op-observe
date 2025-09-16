"""Enablement utilities for packaging evidence bundles."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Mapping


@dataclass(slots=True)
class EvidenceBundle:
    """Represents a packaged evidence artifact."""

    digest: str
    json_blob: str
    html_report: str
    created_at: float


class EnablementAgent:
    """Packages telemetry, RAG output, and radar reports into evidence bundles."""

    def __init__(self) -> None:
        self._initialized = False

    def initialize(self) -> None:
        self._initialized = True

    def package(
        self,
        *,
        rag_result: Mapping[str, object],
        radar_results: Mapping[str, object],
        telemetry_snapshot: Mapping[str, object],
    ) -> EvidenceBundle:
        if not self._initialized:
            raise RuntimeError("EnablementAgent must be initialized before packaging evidence")

        payload = {
            "rag_result": rag_result,
            "radar_report": radar_results.get("report_json"),
            "telemetry": telemetry_snapshot,
        }
        json_blob = json.dumps(payload, sort_keys=True)
        digest = hashlib.sha256(json_blob.encode("utf-8")).hexdigest()
        return EvidenceBundle(
            digest=digest,
            json_blob=json_blob,
            html_report=str(radar_results.get("report_html", "")),
            created_at=time.time(),
        )
