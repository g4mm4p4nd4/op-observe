"""Policy management for OPA / Gatekeeper."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class ConstraintTemplate:
    """Representation of a Gatekeeper constraint template."""

    name: str
    kind: str
    targets: Tuple[str, ...]
    crd_spec: Mapping[str, object]


@dataclass(frozen=True)
class Constraint:
    """Gatekeeper constraint instance."""

    name: str
    kind: str
    parameters: Mapping[str, object]
    match: Mapping[str, object]


@dataclass(frozen=True)
class PolicyBundle:
    """Collection of constraint templates and constraints."""

    templates: Tuple[ConstraintTemplate, ...]
    constraints: Tuple[Constraint, ...]


@dataclass(frozen=True)
class PolicyRequest:
    """Input for evaluating Gatekeeper policies."""

    resource_kind: str
    resource_name: str
    namespace: str
    annotations: Mapping[str, str]
    labels: Mapping[str, str]
    roles: Sequence[str]
    action: str


@dataclass(frozen=True)
class PolicyViolation:
    """Result describing a policy violation."""

    constraint: Constraint
    reason: str


@dataclass(frozen=True)
class PolicyDecision:
    """Outcome of the policy evaluation."""

    allowed: bool
    violations: Tuple[PolicyViolation, ...]

    @property
    def messages(self) -> Tuple[str, ...]:
        return tuple(violation.reason for violation in self.violations)


def _load_json(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_policy_bundle(config_dir: Path) -> PolicyBundle:
    """Load a policy bundle from the given directory."""

    templates_path = config_dir / "templates.json"
    constraints_path = config_dir / "constraints.json"

    raw_templates = _load_json(templates_path)["templates"]
    raw_constraints = _load_json(constraints_path)["constraints"]

    templates = tuple(
        ConstraintTemplate(
            name=template["metadata"]["name"],
            kind=template["kind"],
            targets=tuple(
                target.get("target", "unknown")
                for target in template.get("spec", {}).get("targets", ())
            ),
            crd_spec=template.get("spec", {}).get("crd", {}),
        )
        for template in raw_templates
    )

    constraints = tuple(
        Constraint(
            name=constraint["metadata"]["name"],
            kind=constraint["kind"],
            parameters=constraint.get("spec", {}).get("parameters", {}),
            match=constraint.get("spec", {}).get("match", {}),
        )
        for constraint in raw_constraints
    )

    return PolicyBundle(templates=templates, constraints=constraints)


class PolicyEngine:
    """Tiny policy evaluator that simulates Gatekeeper decisions."""

    def __init__(self, bundle: PolicyBundle):
        self._bundle = bundle

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        violations: list[PolicyViolation] = []

        for constraint in self._bundle.constraints:
            match = constraint.match
            kinds = tuple(match.get("kinds", {}).get("kinds", ()))
            namespaces = tuple(match.get("namespaces", ()))

            if kinds and request.resource_kind not in kinds:
                continue
            if namespaces and request.namespace not in namespaces:
                continue

            parameters = constraint.parameters
            allowed_roles: Iterable[str] = parameters.get("allowedRoles", ())
            prohibited_annotations: Iterable[str] = parameters.get(
                "prohibitedAnnotations", ()
            )
            required_gatekeeper = parameters.get("requireGatekeeper", False)

            if required_gatekeeper and request.action == "create":
                if not request.annotations.get("gatekeeper/approved"):
                    violations.append(
                        PolicyViolation(
                            constraint=constraint,
                            reason=(
                                "Resource creation denied: missing Gatekeeper approval annotation"
                            ),
                        )
                    )
                    continue

            if prohibited_annotations:
                for annotation in prohibited_annotations:
                    if annotation in request.annotations:
                        violations.append(
                            PolicyViolation(
                                constraint=constraint,
                                reason=(
                                    f"Annotation '{annotation}' is prohibited by policy"
                                ),
                            )
                        )
                        break

            if allowed_roles:
                role_set = set(role.lower() for role in request.roles)
                if not any(role.lower() in role_set for role in allowed_roles):
                    violations.append(
                        PolicyViolation(
                            constraint=constraint,
                            reason="User does not satisfy allowedRoles",
                        )
                    )

        allowed = not violations
        return PolicyDecision(allowed=allowed, violations=tuple(violations))
