"""Project parser for Agentic Radar."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import AgentComponent, Dependency, MCPServer, ParsedProject, Tool


class ParserError(Exception):
    """Raised when parsing fails."""


class ProjectParser:
    """Parse agentic projects into structured metadata."""

    manifest_candidates: Iterable[str] = (
        "agentic_radar.json",
        "agentic_radar_manifest.json",
        "radar_manifest.json",
    )

    def __init__(self, manifest_path: Optional[Path] = None) -> None:
        self._explicit_manifest = manifest_path

    def parse(self, root: Path) -> ParsedProject:
        root = Path(root)
        if not root.exists() or not root.is_dir():
            raise ParserError(f"Project root '{root}' does not exist or is not a directory")

        manifest_path = self._explicit_manifest or self._discover_manifest(root)
        if manifest_path is not None:
            data = self._load_manifest(manifest_path)
        else:
            data = self._derive_manifest(root)

        project_name = data.get("project") or data.get("project_name") or root.name

        agents = [
            AgentComponent(
                name=item.get("name", "unknown"),
                description=item.get("description"),
                tools=list(item.get("tools", [])),
            )
            for item in data.get("agents", [])
        ]

        tools = [
            Tool(
                name=item.get("name", "unknown"),
                version=item.get("version"),
                source=item.get("source"),
                scope=item.get("scope"),
            )
            for item in data.get("tools", [])
        ]

        mcp_servers = [
            MCPServer(
                name=item.get("name", "unknown"),
                endpoint=item.get("endpoint", ""),
                capabilities=list(item.get("capabilities", [])),
                auth_mode=item.get("auth_mode"),
            )
            for item in data.get("mcp_servers", [])
        ]

        dependencies = [
            Dependency(
                name=item.get("name", "unknown"),
                version=item.get("version"),
                license=item.get("license"),
                vulnerabilities=list(item.get("vulnerabilities", [])),
            )
            for item in data.get("dependencies", [])
        ]

        metadata: Dict[str, object] = dict(data.get("metadata", {}))
        if manifest_path is not None:
            metadata.setdefault("manifest_path", str(manifest_path))
            metadata.setdefault("manifest_discovered", True)
        else:
            metadata.setdefault("manifest_generated", True)

        return ParsedProject(
            root=root,
            project_name=project_name,
            agents=agents,
            tools=tools,
            mcp_servers=mcp_servers,
            dependencies=dependencies,
            metadata=metadata,
        )

    def _discover_manifest(self, root: Path) -> Optional[Path]:
        for candidate in self.manifest_candidates:
            manifest_path = root / candidate
            if manifest_path.exists():
                return manifest_path
        return None

    def _load_manifest(self, manifest_path: Path) -> Dict[str, object]:
        try:
            with Path(manifest_path).open("r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError as exc:
            raise ParserError(f"Failed to parse manifest '{manifest_path}': {exc}") from exc

    def _derive_manifest(self, root: Path) -> Dict[str, object]:
        agents: List[Dict[str, object]] = []
        seen_agents = set()
        for file in root.rglob("*.py"):
            if file.name.startswith("test_"):
                continue
            agent_name = file.stem.replace("_", "-")
            if agent_name in seen_agents:
                continue
            seen_agents.add(agent_name)
            agents.append({"name": agent_name, "tools": []})

        metadata = {"derived_from_source": True}
        return {
            "project": root.name,
            "agents": agents,
            "tools": [],
            "mcp_servers": [],
            "dependencies": [],
            "metadata": metadata,
        }
