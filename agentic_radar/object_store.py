"""Simple object store abstraction for evidence artifacts."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


class ObjectStoreError(Exception):
    """Raised when storing artifacts fails."""


class ObjectStore:
    """Minimal interface for storing files."""

    def put_file(self, source: Path, *, destination_name: Optional[str] = None) -> Path:
        raise NotImplementedError

    def put_json(self, payload: Dict[str, Any], *, destination_name: Optional[str] = None) -> Path:
        raise NotImplementedError


class LocalObjectStore(ObjectStore):
    """Filesystem-backed object store implementation."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_file(self, source: Path, *, destination_name: Optional[str] = None) -> Path:
        source = Path(source)
        if not source.exists():
            raise ObjectStoreError(f"Source file '{source}' does not exist")
        destination_name = destination_name or source.name
        destination = self.root / destination_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination

    def put_json(self, payload: Dict[str, Any], *, destination_name: Optional[str] = None) -> Path:
        destination_name = destination_name or f"{uuid.uuid4().hex}.json"
        destination = self.root / destination_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
        return destination
