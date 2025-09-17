"""Map dependency vulnerabilities to OWASP categories."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .base import Finding, normalise_string


LLM_CATEGORY_TITLES: Dict[str, str] = {
    "LLM01": "Prompt Injection",
    "LLM02": "Insecure Output Handling",
    "LLM03": "Training Data Poisoning",
    "LLM04": "Model Denial of Service",
    "LLM05": "Supply Chain Vulnerabilities",
    "LLM06": "Sensitive Information Disclosure",
    "LLM07": "Insecure Plugin Design",
    "LLM08": "Excessive Agency",
    "LLM09": "Overreliance",
    "LLM10": "Model Theft",
}

AGENTIC_CATEGORY_TITLES: Dict[str, str] = {
    "AA01": "Prompt & Input Integrity",
    "AA02": "Tool Misuse & Escalation",
    "AA03": "External Service Abuse",
    "AA04": "Sensitive Data Exposure",
    "AA05": "Model or Data Exfiltration",
    "AA06": "Supply Chain & Dependency Risk",
    "AA07": "Secrets & Credential Handling",
    "AA08": "Observability & Audit Gaps",
    "AA09": "Safety & Policy Violations",
    "AA10": "Resilience & Availability",
}

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "moderate": 2, "low": 1}


@dataclass
class VulnerabilityFinding(Finding):
    """Unified representation of dependency vulnerabilities."""

    package: str = ""
    version: str = ""
    ecosystem: Optional[str] = None
    vulnerability_id: str = ""
    severity: Optional[str] = None
    summary: Optional[str] = None
    aliases: Tuple[str, ...] = tuple()
    fix_versions: Tuple[str, ...] = tuple()
    references: Tuple[str, ...] = tuple()
    source: Optional[str] = None
    owasp_llm_categories: Tuple[str, ...] = tuple()
    owasp_agentic_categories: Tuple[str, ...] = tuple()


@dataclass
class MappingRule:
    """Rule that maps vulnerability attributes to OWASP categories."""

    llm_codes: Tuple[str, ...]
    agentic_codes: Tuple[str, ...]
    keywords: Tuple[str, ...] = tuple()
    package: Optional[str] = None
    ecosystem: Optional[str] = None
    id_prefixes: Tuple[str, ...] = tuple()
    severity_at_least: Optional[str] = None

    def matches(self, finding: VulnerabilityFinding) -> bool:
        if self.package and normalise_string(finding.package) != normalise_string(self.package):
            return False
        if self.ecosystem and normalise_string(finding.ecosystem) != normalise_string(self.ecosystem):
            return False
        if self.id_prefixes:
            identifier = (finding.vulnerability_id or "").upper()
            aliases = {alias.upper() for alias in finding.aliases}
            if not any(identifier.startswith(prefix.upper()) or any(alias.startswith(prefix.upper()) for alias in aliases) for prefix in self.id_prefixes):
                return False
        if self.keywords:
            haystacks = " ".join(filter(None, [finding.summary, " ".join(finding.aliases)])).lower()
            if not any(keyword.lower() in haystacks for keyword in self.keywords):
                return False
        if self.severity_at_least:
            required = SEVERITY_ORDER.get(self.severity_at_least.lower(), 0)
            actual = SEVERITY_ORDER.get((finding.severity or "").lower(), 0)
            if actual < required:
                return False
        return True


def _format_category(code: str, titles: Dict[str, str]) -> str:
    title = titles.get(code, "Unknown")
    return f"{code} - {title}"


DEFAULT_RULES: Tuple[MappingRule, ...] = (
    MappingRule(
        llm_codes=("LLM01",),
        agentic_codes=("AA01",),
        keywords=("prompt injection", "prompt-injection"),
    ),
    MappingRule(
        llm_codes=("LLM07",),
        agentic_codes=("AA02",),
        keywords=("remote code execution", "command injection", "arbitrary command"),
    ),
    MappingRule(
        llm_codes=("LLM06",),
        agentic_codes=("AA04",),
        keywords=("information disclosure", "sensitive data", "secret exposure"),
    ),
    MappingRule(
        llm_codes=("LLM04",),
        agentic_codes=("AA10",),
        keywords=("denial of service", "dos", "resource exhaustion"),
    ),
    MappingRule(
        llm_codes=("LLM07",),
        agentic_codes=("AA03",),
        keywords=("ssrf", "server-side request forgery", "unvalidated request"),
    ),
    MappingRule(
        llm_codes=("LLM05",),
        agentic_codes=("AA06",),
        keywords=("supply chain", "dependency", "package takeover"),
    ),
    MappingRule(
        llm_codes=("LLM07",),
        agentic_codes=("AA07",),
        keywords=("credential", "secret", "token leak"),
    ),
)


class OWASPMapper:
    """Apply OWASP mapping rules to vulnerability findings."""

    def __init__(
        self,
        *,
        rules: Sequence[MappingRule] = DEFAULT_RULES,
        default_llm_codes: Sequence[str] = ("LLM05",),
        default_agentic_codes: Sequence[str] = ("AA06",),
    ) -> None:
        self._rules = tuple(rules)
        self._default_llm_codes = tuple(default_llm_codes)
        self._default_agentic_codes = tuple(default_agentic_codes)

    def apply(self, finding: VulnerabilityFinding) -> VulnerabilityFinding:
        llm_codes = set()
        agentic_codes = set()
        for rule in self._rules:
            if rule.matches(finding):
                llm_codes.update(rule.llm_codes)
                agentic_codes.update(rule.agentic_codes)
        if not llm_codes:
            llm_codes.update(self._default_llm_codes)
        if not agentic_codes:
            agentic_codes.update(self._default_agentic_codes)
        finding.owasp_llm_categories = tuple(
            _format_category(code, LLM_CATEGORY_TITLES) for code in sorted(llm_codes)
        )
        finding.owasp_agentic_categories = tuple(
            _format_category(code, AGENTIC_CATEGORY_TITLES) for code in sorted(agentic_codes)
        )
        return finding


class VulnerabilityMapper:
    """Unify OSV and pip-audit results and map to OWASP categories."""

    def __init__(self, *, owasp_mapper: Optional[OWASPMapper] = None) -> None:
        self._owasp_mapper = owasp_mapper or OWASPMapper()

    # ------------------------------------------------------------------
    # OSV parsing
    # ------------------------------------------------------------------
    def from_osv(self, payload: Dict[str, Any]) -> List[VulnerabilityFinding]:
        findings: List[VulnerabilityFinding] = []
        for result in payload.get("results", []):
            source_path = _extract_source_path(result.get("source"))
            for package in result.get("packages", []):
                pkg_meta = package.get("package", {}) or {}
                package_name = pkg_meta.get("name") or "unknown"
                ecosystem = pkg_meta.get("ecosystem")
                versions = package.get("versions") or ["unknown"]
                vulnerabilities = package.get("vulnerabilities") or []
                for vuln in vulnerabilities:
                    severity = _extract_osv_severity(vuln)
                    summary = vuln.get("summary") or vuln.get("details")
                    aliases = tuple(vuln.get("aliases") or ())
                    references = tuple(
                        ref.get("url") for ref in vuln.get("references", []) if isinstance(ref, dict) and ref.get("url")
                    )
                    fix_versions = _extract_osv_fix_versions(vuln)
                    vuln_id = vuln.get("id") or aliases[0] if aliases else package_name
                    for version in versions:
                        finding = VulnerabilityFinding(
                            detector="vulnerability",
                            name=vuln_id,
                            location=source_path,
                            package=package_name,
                            version=version,
                            ecosystem=ecosystem,
                            vulnerability_id=vuln_id,
                            severity=severity,
                            summary=summary,
                            aliases=aliases,
                            fix_versions=fix_versions,
                            references=references,
                            source="osv",
                            metadata={
                                "source": "osv",
                                "path": source_path,
                            },
                        )
                        findings.append(self._owasp_mapper.apply(finding))
        return findings

    # ------------------------------------------------------------------
    # pip-audit parsing
    # ------------------------------------------------------------------
    def from_pip_audit(self, payload: Dict[str, Any]) -> List[VulnerabilityFinding]:
        findings: List[VulnerabilityFinding] = []
        for dependency in payload.get("dependencies", []):
            package_name = dependency.get("name") or "unknown"
            version = dependency.get("version") or "unknown"
            for vuln in dependency.get("vulns", []):
                vuln_id = vuln.get("id") or package_name
                aliases = tuple(vuln.get("aliases") or ())
                severity = _normalise_severity(vuln.get("severity"))
                summary = vuln.get("description") or vuln.get("summary")
                fix_versions = tuple(vuln.get("fix_versions") or ())
                references = tuple(vuln.get("references") or ())
                finding = VulnerabilityFinding(
                    detector="vulnerability",
                    name=vuln_id,
                    location="pip-audit",
                    package=package_name,
                    version=version,
                    ecosystem="PyPI",
                    vulnerability_id=vuln_id,
                    severity=severity,
                    summary=summary,
                    aliases=aliases,
                    fix_versions=fix_versions,
                    references=references,
                    source="pip-audit",
                    metadata={"source": "pip-audit"},
                )
                findings.append(self._owasp_mapper.apply(finding))
        return findings

    # ------------------------------------------------------------------
    # Deduplication & merging
    # ------------------------------------------------------------------
    def merge(self, *finding_groups: Iterable[VulnerabilityFinding]) -> List[VulnerabilityFinding]:
        merged: Dict[Tuple[str, str], VulnerabilityFinding] = {}
        for group in finding_groups:
            for finding in group:
                key = (finding.package.lower(), finding.vulnerability_id.upper())
                if key not in merged:
                    merged[key] = finding
                    continue
                existing = merged[key]
                merged[key] = _merge_findings(existing, finding, self._owasp_mapper)
        return list(merged.values())


def _extract_source_path(source: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(source, dict):
        return None
    for key in ("path", "file", "name"):
        value = source.get(key)
        if isinstance(value, str):
            return value
    return None


def _extract_osv_severity(vuln: Dict[str, Any]) -> Optional[str]:
    severities = []
    for entry in vuln.get("severity", []) or []:
        score = entry.get("score")
        if not isinstance(score, str):
            continue
        numeric_score = _score_to_float(score)
        if numeric_score is not None:
            severities.append(numeric_score)
    if severities:
        return _severity_from_score(max(severities))
    database_specific = vuln.get("database_specific") or {}
    severity = database_specific.get("severity")
    if isinstance(severity, str):
        return severity.upper()
    return None


def _extract_osv_fix_versions(vuln: Dict[str, Any]) -> Tuple[str, ...]:
    versions = set()
    for key in ("fix_versions", "fixed_versions"):
        for version in vuln.get(key) or []:
            if isinstance(version, str):
                versions.add(version)
    database_specific = vuln.get("database_specific") or {}
    for key in ("fix_versions", "fixed_versions"):
        for version in database_specific.get(key) or []:
            if isinstance(version, str):
                versions.add(version)
    for affected in vuln.get("affected", []) or []:
        ranges = affected.get("ranges") or []
        for range_entry in ranges:
            for event in range_entry.get("events", []):
                fixed = event.get("fixed")
                if isinstance(fixed, str):
                    versions.add(fixed)
    return tuple(sorted(versions))


def _score_to_float(score: str) -> Optional[float]:
    try:
        if "/" in score:
            score = score.split("/", 1)[0]
        return float(score)
    except (TypeError, ValueError):
        return None


def _severity_from_score(score: float) -> str:
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "UNKNOWN"


def _normalise_severity(severity: Optional[str]) -> Optional[str]:
    if severity is None:
        return None
    return severity.upper()


def _merge_findings(
    left: VulnerabilityFinding,
    right: VulnerabilityFinding,
    mapper: OWASPMapper,
) -> VulnerabilityFinding:
    aliases = tuple(sorted(set(left.aliases) | set(right.aliases)))
    fix_versions = tuple(sorted(set(left.fix_versions) | set(right.fix_versions)))
    references = tuple(sorted(set(left.references) | set(right.references)))
    severity = _pick_more_severe(left.severity, right.severity)
    summary = left.summary or right.summary
    metadata = {**left.metadata, **right.metadata}
    merged = VulnerabilityFinding(
        detector="vulnerability",
        name=left.name,
        location=left.location or right.location,
        package=left.package,
        version=left.version or right.version,
        ecosystem=left.ecosystem or right.ecosystem,
        vulnerability_id=left.vulnerability_id,
        severity=severity,
        summary=summary,
        aliases=aliases,
        fix_versions=fix_versions,
        references=references,
        source=left.source or right.source,
        metadata=metadata,
    )
    return mapper.apply(merged)


def _pick_more_severe(left: Optional[str], right: Optional[str]) -> Optional[str]:
    candidates = [(left or "").lower(), (right or "").lower()]
    best_level = 0
    best_value: Optional[str] = None
    fallback: Optional[str] = None
    for candidate in candidates:
        level = SEVERITY_ORDER.get(candidate, 0)
        if candidate and fallback is None:
            fallback = candidate.upper()
        if level > best_level and candidate:
            best_level = level
            best_value = candidate.upper()
    return best_value or fallback
