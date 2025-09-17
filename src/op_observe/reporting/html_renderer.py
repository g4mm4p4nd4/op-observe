"""HTML rendering helpers for the agentic security report."""
from __future__ import annotations

import html
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, List, Mapping, Sequence, Tuple

from .models import (
    AgentSecurityReport,
    EvidenceLink,
    EvaluationSummary,
    GuardrailSummary,
    MCPServer,
    ReportMetadata,
    ToolInventoryEntry,
    VulnerabilityFinding,
    WorkflowGraph,
    WorkflowNode,
)


class WorkflowGraphRenderer:
    """Renders a workflow graph as inline SVG.

    The renderer intentionally keeps the layout algorithm simple to avoid
    depending on Graphviz. Nodes are placed in layers derived from the
    topological depth of the workflow. Edges are drawn as curved paths with
    arrow markers so that the rendered graph remains legible even for sparse
    layouts.
    """

    NODE_WIDTH = 180
    NODE_HEIGHT = 64
    HORIZONTAL_SPACING = 120
    VERTICAL_SPACING = 56
    MARGIN = 40

    def render(self, graph: WorkflowGraph) -> str:
        if not graph.nodes:
            return "<p class=\"empty-graph\">No workflow graph data available.</p>"

        node_map: Dict[str, WorkflowNode] = {node.id: node for node in graph.nodes}
        layers = self._compute_layers(graph, node_map)
        layer_ids = sorted(layers.items(), key=lambda item: (item[1], node_map[item[0]].label.lower()))
        max_depth = max(layers.values()) if layers else 0

        nodes_by_layer: Dict[int, List[str]] = defaultdict(list)
        for node_id, depth in layer_ids:
            nodes_by_layer[depth].append(node_id)

        max_layer_size = max((len(node_ids) for node_ids in nodes_by_layer.values()), default=1)
        svg_width = (
            self.MARGIN * 2
            + (max_depth + 1) * self.NODE_WIDTH
            + max_depth * self.HORIZONTAL_SPACING
        )
        svg_height = (
            self.MARGIN * 2
            + max_layer_size * self.NODE_HEIGHT
            + max(0, max_layer_size - 1) * self.VERTICAL_SPACING
        )

        positions: Dict[str, Tuple[float, float]] = {}
        for depth in range(max_depth + 1):
            node_ids = nodes_by_layer.get(depth, [])
            if not node_ids:
                continue
            # Align nodes vertically within the layer.
            cluster_height = (
                len(node_ids) * self.NODE_HEIGHT
                + max(0, len(node_ids) - 1) * self.VERTICAL_SPACING
            )
            start_y = self.MARGIN + (svg_height - 2 * self.MARGIN - cluster_height) / 2
            for index, node_id in enumerate(node_ids):
                x = self.MARGIN + depth * (self.NODE_WIDTH + self.HORIZONTAL_SPACING)
                y = start_y + index * (self.NODE_HEIGHT + self.VERTICAL_SPACING)
                positions[node_id] = (x + self.NODE_WIDTH / 2, y + self.NODE_HEIGHT / 2)

        svg_parts = [
            '<svg class="workflow-graph" viewBox="0 0 {width} {height}" '
            'xmlns="http://www.w3.org/2000/svg">'.format(width=svg_width, height=svg_height),
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            '<path d="M 0 0 L 10 5 L 0 10 z" /></marker></defs>',
        ]

        # Draw edges first so that nodes appear on top.
        for edge in graph.edges:
            if edge.source not in positions or edge.target not in positions:
                continue
            x1, y1 = positions[edge.source]
            x2, y2 = positions[edge.target]
            path = (
                f"M {x1 + self.NODE_WIDTH / 2:.2f} {y1:.2f} "
                f"C {x1 + self.NODE_WIDTH:.2f} {y1:.2f}, {x2 - self.NODE_WIDTH:.2f} {y2:.2f}, "
                f"{x2 - self.NODE_WIDTH / 2:.2f} {y2:.2f}"
            )
            svg_parts.append(
                '<path class="workflow-edge" d="{path}" marker-end="url(#arrow)" />'.format(path=path)
            )
            if edge.label:
                label_x = (x1 + x2) / 2
                label_y = (y1 + y2) / 2 - 6
                svg_parts.append(
                    '<text class="edge-label" x="{x:.2f}" y="{y:.2f}">{label}</text>'.format(
                        x=label_x,
                        y=label_y,
                        label=html.escape(edge.label),
                    )
                )

        for node_id, (cx, cy) in positions.items():
            node = node_map[node_id]
            x = cx - self.NODE_WIDTH / 2
            y = cy - self.NODE_HEIGHT / 2
            svg_parts.append(
                '<g class="workflow-node workflow-node-{kind}">'
                '<rect x="{x:.2f}" y="{y:.2f}" width="{w}" height="{h}" rx="12" ry="12" />'
                '<text x="{label_x:.2f}" y="{label_y:.2f}" class="node-label">{label}</text>'
                '<text x="{label_x:.2f}" y="{kind_y:.2f}" class="node-kind">{kind}</text>'
                '</g>'.format(
                    kind=html.escape(node.kind.lower()),
                    x=x,
                    y=y,
                    w=self.NODE_WIDTH,
                    h=self.NODE_HEIGHT,
                    label_x=cx,
                    label_y=cy - 6,
                    label=html.escape(node.label),
                    kind_y=cy + 18,
                )
            )

        svg_parts.append("</svg>")
        return "".join(svg_parts)

    def _compute_layers(
        self, graph: WorkflowGraph, node_map: Mapping[str, WorkflowNode]
    ) -> Dict[str, int]:
        in_degree: Dict[str, int] = {node_id: 0 for node_id in node_map}
        adjacency: Dict[str, List[str]] = defaultdict(list)
        for edge in graph.edges:
            if edge.source not in node_map or edge.target not in node_map:
                continue
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] += 1

        queue: deque[str] = deque(
            sorted((node_id for node_id, degree in in_degree.items() if degree == 0))
        )
        layers: Dict[str, int] = {node_id: 0 for node_id in queue}
        while queue:
            node_id = queue.popleft()
            for target in adjacency.get(node_id, []):
                proposed_layer = layers[node_id] + 1
                if proposed_layer > layers.get(target, 0):
                    layers[target] = proposed_layer
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)

        # For nodes that were part of a cycle, assign them the minimum depth of
        # their predecessors, defaulting to zero.
        for node_id in node_map:
            if node_id in layers:
                continue
            predecessors = [edge.source for edge in graph.edges if edge.target == node_id]
            if predecessors:
                depth = max(layers.get(pred, 0) for pred in predecessors)
            else:
                depth = 0
            layers[node_id] = depth
        return layers


class ReportHtmlRenderer:
    """Renders the full HTML document for the security report."""

    def __init__(self) -> None:
        self._graph_renderer = WorkflowGraphRenderer()

    def render(self, report: AgentSecurityReport) -> str:
        metadata_html = self._render_metadata(report.metadata)
        graph_html = self._graph_renderer.render(report.workflow)
        tools_html = self._render_tools(report.tools)
        mcp_html = self._render_mcp(report.mcp_servers)
        vuln_html = self._render_vulnerabilities(report.vulnerabilities)
        guards_html = self._render_guards(report.guardrail_summaries)
        evals_html = self._render_evaluations(report.evaluation_summaries)
        evidence_html = self._render_evidence(report.evidence_links)
        appendix_html = (
            f"<section id=\"appendix\"><h2>Appendix</h2><p>{html.escape(report.appendix)}</p></section>"
            if report.appendix
            else ""
        )

        return """<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<title>Security Report — {title}</title>
<style>
    body {{ font-family: "Inter", "Segoe UI", sans-serif; margin: 0; padding: 0; background: #101418; color: #f4f6f8; }}
    header {{ background: linear-gradient(120deg, #1f2a37, #111827); padding: 32px 48px; }}
    h1 {{ margin: 0; font-size: 2rem; }}
    h2 {{ margin-top: 48px; margin-bottom: 16px; border-bottom: 2px solid #2d3748; padding-bottom: 8px; }}
    section {{ padding: 0 48px 24px 48px; }}
    .metadata-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; margin-top: 24px; }}
    .metadata-item {{ background: #1f2933; border-radius: 10px; padding: 12px 16px; box-shadow: 0 2px 4px rgba(15, 23, 42, 0.4); }}
    .metadata-item span {{ display: block; color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }}
    .metadata-item strong {{ display: block; font-size: 1rem; margin-top: 4px; color: #e2e8f0; word-break: break-word; }}
    .workflow-container {{ background: #0f172a; border-radius: 12px; padding: 24px; box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.12); }}
    .workflow-graph {{ width: 100%; height: auto; max-height: 520px; }}
    .workflow-node rect {{ fill: #1f2937; stroke: #38bdf8; stroke-width: 1.5; }}
    .workflow-node-agent rect {{ stroke: #38bdf8; }}
    .workflow-node-tool rect {{ stroke: #f97316; }}
    .workflow-node-mcp rect {{ stroke: #a855f7; }}
    .workflow-node-other rect {{ stroke: #4ade80; }}
    .workflow-node text {{ fill: #e2e8f0; text-anchor: middle; font-size: 0.85rem; }}
    .workflow-node .node-kind {{ fill: #94a3b8; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    .workflow-edge {{ fill: none; stroke: #64748b; stroke-width: 1.4; opacity: 0.8; }}
    .edge-label {{ fill: #cbd5f5; font-size: 0.7rem; text-anchor: middle; }}
    table {{ width: 100%; border-collapse: collapse; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.4); }}
    thead {{ background: #1f2937; text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.78rem; color: #94a3b8; }}
    th, td {{ padding: 12px 14px; border-bottom: 1px solid rgba(148, 163, 184, 0.2); vertical-align: top; }}
    tbody tr:nth-child(even) {{ background: rgba(15, 23, 42, 0.45); }}
    tbody tr:hover {{ background: rgba(56, 189, 248, 0.12); }}
    .severity-critical {{ color: #f87171; font-weight: 600; }}
    .severity-high {{ color: #fb7185; font-weight: 600; }}
    .severity-medium {{ color: #fbbf24; font-weight: 600; }}
    .severity-low {{ color: #34d399; font-weight: 600; }}
    .chip {{ display: inline-block; padding: 4px 10px; border-radius: 999px; background: rgba(148, 163, 184, 0.18); margin-right: 6px; margin-top: 4px; font-size: 0.75rem; color: #e2e8f0; }}
    .evidence-list {{ list-style: none; padding-left: 0; }}
    .evidence-list li {{ margin-bottom: 6px; }}
    a {{ color: #38bdf8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    footer {{ padding: 32px 48px 48px 48px; color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; }}
</style>
</head>
<body>
{metadata_html}
<section id=\"workflow\">
  <h2>Agent Workflow</h2>
  <div class=\"workflow-container\">{graph_html}</div>
</section>
<section id=\"tools\">
  <h2>Tool Inventory</h2>
  {tools_html}
</section>
<section id=\"mcp\">
  <h2>MCP Servers</h2>
  {mcp_html}
</section>
<section id=\"vulnerabilities\">
  <h2>Vulnerability Mapping</h2>
  {vuln_html}
</section>
<section id=\"guards\">
  <h2>Guardrail Status</h2>
  {guards_html}
</section>
<section id=\"evaluations\">
  <h2>Evaluation Summaries</h2>
  {evals_html}
</section>
<section id=\"evidence\">
  <h2>Evidence Bundle</h2>
  {evidence_html}
</section>
{appendix_html}
<footer>Generated {generated}</footer>
</body>
</html>
""".format(
            title=html.escape(report.metadata.project_name),
            metadata_html=metadata_html,
            graph_html=graph_html,
            tools_html=tools_html,
            mcp_html=mcp_html,
            vuln_html=vuln_html,
            guards_html=guards_html,
            evals_html=evals_html,
            evidence_html=evidence_html,
            appendix_html=appendix_html,
            generated=html.escape(report.metadata.generated_at.isoformat()),
        )

    def _render_metadata(self, metadata: ReportMetadata) -> str:
        items = [
            ("Project", metadata.project_name),
            ("Environment", metadata.environment),
            ("Revision", metadata.revision),
        ]
        if metadata.policy_hash:
            items.append(("Policy Hash", metadata.policy_hash))
        if metadata.scanner_version:
            items.append(("Scanner", metadata.scanner_version))
        for key, value in metadata.additional_context.items():
            items.append((key, value))

        parts = ["<header>", "  <h1>Agentic Security Report</h1>", "  <div class=\"metadata-grid\">"]
        for label, value in items:
            parts.append(
                "    <div class=\"metadata-item\"><span>{label}</span><strong>{value}</strong></div>".format(
                    label=html.escape(label), value=html.escape(value)
                )
            )
        parts.extend(["  </div>", "</header>"])
        return "\n".join(parts)

    def _render_tools(self, tools: Sequence[ToolInventoryEntry]) -> str:
        if not tools:
            return "<p>No tools detected during the scan.</p>"
        rows = []
        for tool in tools:
            scopes = "".join(
                f"<span class=\"chip\">{html.escape(scope)}</span>" for scope in tool.scopes
            )
            permissions = "".join(
                f"<span class=\"chip\">{html.escape(perm)}</span>" for perm in tool.permissions
            )
            evidence = self._render_evidence_links(tool.evidence)
            rows.append(
                "<tr><td><strong>{name}</strong><br/><span>{desc}</span></td>"
                "<td>{version}</td><td>{source}</td><td>{scopes}</td><td>{permissions}</td><td>{evidence}</td></tr>".format(
                    name=html.escape(tool.name),
                    desc=html.escape(tool.description or ""),
                    version=html.escape(tool.version),
                    source=html.escape(tool.source),
                    scopes=scopes or "—",
                    permissions=permissions or "—",
                    evidence=evidence,
                )
            )
        return (
            "<table class=\"tools-table\"><thead><tr><th>Tool</th><th>Version</th>"
            "<th>Source</th><th>Scopes</th><th>Permissions</th><th>Evidence</th></tr></thead>"
            "<tbody>{rows}</tbody></table>"
        ).format(rows="".join(rows))

    def _render_mcp(self, servers: Sequence[MCPServer]) -> str:
        if not servers:
            return "<p>No MCP servers discovered.</p>"
        rows = []
        for server in servers:
            caps = "".join(f"<span class=\"chip\">{html.escape(cap)}</span>" for cap in server.capabilities)
            rows.append(
                "<tr><td><strong>{name}</strong><br/><span>{notes}</span></td>"
                "<td>{endpoint}</td><td>{auth}</td><td>{caps}</td></tr>".format(
                    name=html.escape(server.name),
                    notes=html.escape(server.notes or ""),
                    endpoint=html.escape(server.endpoint),
                    auth=html.escape(server.auth_mode),
                    caps=caps or "—",
                )
            )
        return (
            "<table class=\"mcp-table\"><thead><tr><th>Server</th><th>Endpoint</th><th>Auth</th><th>Capabilities</th>"
            "</tr></thead><tbody>{rows}</tbody></table>"
        ).format(rows="".join(rows))

    def _render_vulnerabilities(self, vulns: Sequence[VulnerabilityFinding]) -> str:
        if not vulns:
            return "<p>No vulnerabilities mapped to the current inventory.</p>"
        rows = []
        for finding in vulns:
            severity_class = f"severity-{finding.severity.lower()}"
            cves = ", ".join(html.escape(cve) for cve in finding.cve_ids) or "—"
            owasp_llm = "".join(
                f"<span class=\"chip\">{html.escape(item)}</span>" for item in finding.owasp_llm_categories
            ) or "—"
            owasp_agentic = "".join(
                f"<span class=\"chip\">{html.escape(item)}</span>"
                for item in finding.owasp_agentic_categories
            ) or "—"
            references = self._render_evidence_links(finding.references)
            rows.append(
                "<tr><td><strong>{component}</strong><br/><span>{notes}</span></td>"
                "<td>{version}</td><td class=\"{severity_class}\">{severity}</td>"
                "<td>{cves}</td><td>{fix}</td><td>{owasp_llm}</td><td>{owasp_agentic}</td><td>{refs}</td></tr>".format(
                    component=html.escape(finding.component),
                    notes=html.escape(finding.notes or ""),
                    version=html.escape(finding.version),
                    severity_class=html.escape(severity_class),
                    severity=html.escape(finding.severity.title()),
                    cves=cves,
                    fix=html.escape(finding.fix_version or "—"),
                    owasp_llm=owasp_llm,
                    owasp_agentic=owasp_agentic,
                    refs=references,
                )
            )
        return (
            "<table class=\"vuln-table\"><thead><tr>"
            "<th>Component</th><th>Version</th><th>Severity</th><th>CVE</th><th>Fix</th>"
            "<th>OWASP LLM</th><th>OWASP Agentic</th><th>Evidence</th>"
            "</tr></thead><tbody>{rows}</tbody></table>"
        ).format(rows="".join(rows))

    def _render_guards(self, guards: Sequence[GuardrailSummary]) -> str:
        if not guards:
            return "<p>No guardrail data provided for the reporting interval.</p>"
        rows = []
        for guard in guards:
            breakdown = "".join(
                f"<span class=\"chip\">{html.escape(level)}: {count}</span>"
                for level, count in sorted(guard.severity_breakdown.items())
            )
            rows.append(
                "<tr><td><strong>{name}</strong><br/><span>{notes}</span></td><td>{status}</td>"
                "<td>{window}</td><td>{failures}</td><td>{critical}</td><td>{breakdown}</td></tr>".format(
                    name=html.escape(guard.name),
                    notes=html.escape(guard.notes or ""),
                    status=html.escape(guard.status),
                    window=html.escape(guard.window),
                    failures=guard.total_failures,
                    critical=guard.critical_failures,
                    breakdown=breakdown or "—",
                )
            )
        return (
            "<table class=\"guard-table\"><thead><tr><th>Guardrail</th><th>Status</th><th>Window</th><th>Failures</th>"
            "<th>Critical</th><th>Severity Mix</th></tr></thead><tbody>{rows}</tbody></table>"
        ).format(rows="".join(rows))

    def _render_evaluations(self, evals: Sequence[EvaluationSummary]) -> str:
        if not evals:
            return "<p>No evaluation metrics recorded.</p>"
        rows = []
        for evaluation in evals:
            delta = (
                f"{evaluation.delta:+.2f}" if evaluation.delta is not None else "—"
            )
            rows.append(
                "<tr><td><strong>{name}</strong><br/><span>{notes}</span></td><td>{metric}</td>"
                "<td>{value:.2f}</td><td>{delta}</td><td>{window}</td></tr>".format(
                    name=html.escape(evaluation.name),
                    notes=html.escape(evaluation.notes or ""),
                    metric=html.escape(evaluation.metric),
                    value=evaluation.value,
                    delta=delta,
                    window=html.escape(evaluation.window or "—"),
                )
            )
        return (
            "<table class=\"evaluation-table\"><thead><tr><th>Evaluation</th><th>Metric</th>"
            "<th>Value</th><th>Δ</th><th>Window</th></tr></thead><tbody>{rows}</tbody></table>"
        ).format(rows="".join(rows))

    def _render_evidence(self, evidence: Sequence[EvidenceLink]) -> str:
        if not evidence:
            return "<p>No external evidence was attached.</p>"
        items = [
            "<li><a href=\"{uri}\">{desc}</a></li>".format(
                uri=html.escape(link.uri), desc=html.escape(link.description)
            )
            for link in evidence
        ]
        return "<ul class=\"evidence-list\">{items}</ul>".format(items="".join(items))

    def _render_evidence_links(self, evidence: Sequence[EvidenceLink]) -> str:
        if not evidence:
            return "—"
        return "<ul class=\"evidence-list\">{items}</ul>".format(
            items="".join(
                "<li><a href=\"{uri}\">{desc}</a></li>".format(
                    uri=html.escape(link.uri), desc=html.escape(link.description)
                )
                for link in evidence
            )
        )


def report_to_serializable(report: AgentSecurityReport) -> Dict[str, object]:
    """Convert a report into a structure that can be JSON serialized."""

    def transform(value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "__dataclass_fields__"):
            return {key: transform(getattr(value, key)) for key in value.__dataclass_fields__}
        if isinstance(value, Mapping):
            return {key: transform(val) for key, val in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [transform(item) for item in value]
        return value

    return transform(report)

