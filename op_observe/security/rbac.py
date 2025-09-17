"""Role-based access control derived from Keycloak and Gatekeeper policies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Sequence, Tuple

from .keycloak import KeycloakClient, KeycloakUser
from .policy import Constraint, PolicyDecision, PolicyEngine, PolicyRequest, PolicyViolation


@dataclass(frozen=True)
class RBACRole:
    """Represents a role with a set of permissions."""

    name: str
    permissions: Tuple[str, ...]


@dataclass(frozen=True)
class RBACBinding:
    """Binding between a role and resource selectors."""

    role: str
    resources: Tuple[str, ...]
    actions: Tuple[str, ...]


@dataclass(frozen=True)
class RBACConfig:
    """Configuration describing roles and bindings."""

    roles: Mapping[str, RBACRole]
    bindings: Tuple[RBACBinding, ...]

    def permissions_for_roles(self, user_roles: Iterable[str]) -> Tuple[str, ...]:
        collected: list[str] = []
        for role in user_roles:
            if role in self.roles:
                collected.extend(self.roles[role].permissions)
        return tuple(sorted(set(collected)))

    def bindings_for_roles(self, user_roles: Iterable[str]) -> Tuple[RBACBinding, ...]:
        lookup = {binding.role: binding for binding in self.bindings}
        selected = []
        for role in user_roles:
            binding = lookup.get(role)
            if binding:
                selected.append(binding)
        return tuple(selected)


def load_rbac_config(config_dir: Path) -> RBACConfig:
    """Load RBAC configuration from JSON files."""

    roles_raw = json.loads((config_dir / "roles.json").read_text("utf-8"))
    bindings_raw = json.loads((config_dir / "bindings.json").read_text("utf-8"))

    roles = {
        role_data["name"]: RBACRole(
            name=role_data["name"],
            permissions=tuple(role_data.get("permissions", ())),
        )
        for role_data in roles_raw["roles"]
    }

    bindings = tuple(
        RBACBinding(
            role=binding["role"],
            resources=tuple(binding.get("resources", ())),
            actions=tuple(binding.get("actions", ())),
        )
        for binding in bindings_raw["bindings"]
    )

    return RBACConfig(roles=roles, bindings=bindings)


class RBACEnforcer:
    """Glue between Keycloak authentication and policy enforcement."""

    def __init__(
        self,
        *,
        keycloak: KeycloakClient,
        policy_engine: PolicyEngine,
        rbac_config: RBACConfig,
    ) -> None:
        self._keycloak = keycloak
        self._policy_engine = policy_engine
        self._rbac_config = rbac_config
        self._decision_cache: MutableMapping[Tuple[str, str, str], PolicyDecision] = {}

    def authorize(self, token: str, *, action: str, resource: str) -> PolicyDecision:
        """Authorize an action for the user represented by ``token``."""

        cache_key = (token, action, resource)
        if cache_key in self._decision_cache:
            return self._decision_cache[cache_key]

        user = self._keycloak.resolve_user(token)
        decision = self._evaluate(user=user, action=action, resource=resource)
        self._decision_cache[cache_key] = decision
        return decision

    def _evaluate(
        self, *, user: KeycloakUser, action: str, resource: str
    ) -> PolicyDecision:
        user_roles = user.roles
        permissions = self._rbac_config.permissions_for_roles(user_roles)

        if action not in permissions:
            return PolicyDecision(
                allowed=False,
                violations=(
                    self._deny("RBAC policy", "Action is not permitted for user roles"),
                ),
            )

        binding = self._select_binding(user_roles, action, resource)
        if binding is None:
            return PolicyDecision(
                allowed=False,
                violations=(
                    self._deny("RBAC binding", "No binding found for resource"),
                ),
            )

        policy_request = PolicyRequest(
            resource_kind="Secret",
            resource_name=resource,
            namespace="op-observe",
            annotations={"gatekeeper/approved": "true"},
            labels={},
            roles=user_roles,
            action=action,
        )
        decision = self._policy_engine.evaluate(policy_request)
        return decision

    def _select_binding(
        self, roles: Sequence[str], action: str, resource: str
    ) -> RBACBinding | None:
        for binding in self._rbac_config.bindings_for_roles(roles):
            if action in binding.actions and resource in binding.resources:
                return binding
        return None

    @staticmethod
    def _deny(source: str, message: str) -> PolicyViolation:
        return PolicyViolation(
            constraint=Constraint(
                name=source,
                kind="rbac.opobserve.io",
                parameters={},
                match={},
            ),
            reason=message,
        )
