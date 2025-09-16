"""Evidence packaging utilities."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from .object_store import LocalObjectStore, ObjectStore


@dataclass
class EvidencePackResult:
    """Result of creating an evidence pack."""

    pack_path: Path
    metadata: dict
    stored_path: Optional[Path] = None


class EvidencePackBuilder:
    """Builds zip-based evidence packs combining findings and logs."""

    def __init__(self, object_store: Optional[ObjectStore] = None) -> None:
        self.object_store = object_store

    def build(
        self,
        *,
        findings_paths: Iterable[Path],
        logs_path: Optional[Path] = None,
        trace_ids: Optional[Iterable[str]] = None,
        output_path: Optional[Path] = None,
    ) -> EvidencePackResult:
        findings_list = [Path(path) for path in findings_paths]
        if not findings_list:
            raise ValueError("At least one findings file must be provided")
        for path in findings_list:
            if not path.exists():
                raise FileNotFoundError(f"Findings file '{path}' does not exist")

        output_path = Path(output_path or (findings_list[0].parent / "evidence-pack.zip"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        metadata = {
            "artifact_type": "agentic-radar-evidence",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "findings": [],
            "logs": [],
            "trace_ids": list(trace_ids or []),
        }

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for findings_path in findings_list:
                arcname = f"findings/{findings_path.name}"
                archive.write(findings_path, arcname)
                metadata["findings"].append(arcname)

            if logs_path is not None:
                logs_path = Path(logs_path)
                if logs_path.is_dir():
                    for file_path in sorted(p for p in logs_path.rglob("*") if p.is_file()):
                        arcname = f"logs/{file_path.relative_to(logs_path)}"
                        archive.write(file_path, arcname)
                        metadata["logs"].append(str(arcname))
                elif logs_path.is_file():
                    arcname = f"logs/{logs_path.name}"
                    archive.write(logs_path, arcname)
                    metadata["logs"].append(arcname)
                else:
                    raise FileNotFoundError(f"Logs path '{logs_path}' does not exist")

            archive.writestr("metadata.json", json.dumps(metadata, indent=2))

        stored_path: Optional[Path] = None
        if self.object_store is not None:
            destination_name = output_path.name
            stored_path = self.object_store.put_file(output_path, destination_name=destination_name)

        return EvidencePackResult(pack_path=output_path, metadata=metadata, stored_path=stored_path)


def create_evidence_pack(
    findings_paths: Iterable[Path],
    *,
    logs_path: Optional[Path] = None,
    trace_ids: Optional[Iterable[str]] = None,
    output_path: Optional[Path] = None,
    object_store_path: Optional[Path] = None,
) -> EvidencePackResult:
    object_store = LocalObjectStore(object_store_path) if object_store_path else None
    builder = EvidencePackBuilder(object_store=object_store)
    return builder.build(
        findings_paths=findings_paths,
        logs_path=logs_path,
        trace_ids=trace_ids,
        output_path=output_path,
    )
