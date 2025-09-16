"""Declarative RBAC policy management for Keycloak."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .keycloak import KeycloakAdminClient, KeycloakRequestError


@dataclass(slots=True)
class RoleDefinition:
    """Definition of a realm role."""

    name: str
    description: str
    composite: bool = False


@dataclass(slots=True)
class GroupBinding:
    """Mapping between a Keycloak group and realm roles."""

    name: str
    roles: tuple[str, ...]


@dataclass(slots=True)
class ServiceAccountBinding:
    """Assign realm roles to a Keycloak service account (client)."""

    client_id: str
    roles: tuple[str, ...]


@dataclass(slots=True)
class RBACPolicy:
    """Collection of role definitions and their bindings."""

    roles: tuple[RoleDefinition, ...]
    groups: tuple[GroupBinding, ...]
    service_accounts: tuple[ServiceAccountBinding, ...] = ()


class RBACManager:
    """Synchronize RBAC policies with Keycloak using the admin client."""

    def __init__(self, admin_client: KeycloakAdminClient):
        self._admin = admin_client

    def sync_policy(self, policy: RBACPolicy) -> dict[str, object]:
        """Apply the RBAC policy to Keycloak.

        Returns a dictionary describing the changes that were made.
        """

        changes: dict[str, object] = {
            "roles_created": [],
            "roles_updated": [],
            "groups_created": [],
            "group_role_assignments": {},
            "service_account_role_assignments": {},
        }

        role_cache: dict[str, dict[str, object]] = {}
        # Ensure roles exist and have the expected attributes.
        for role in policy.roles:
            existing = self._admin.get_realm_role(role.name)
            if existing is None:
                self._admin.create_realm_role(
                    name=role.name, description=role.description, composite=role.composite
                )
                created = self._admin.get_realm_role(role.name)
                if created is None:  # pragma: no cover - defensive guard
                    raise KeycloakRequestError(f"Role '{role.name}' was created but cannot be fetched")
                role_cache[role.name] = created
                changes["roles_created"].append(role.name)
            else:
                needs_update = (
                    (existing.get("description") or "") != role.description
                    or bool(existing.get("composite")) != role.composite
                )
                if needs_update:
                    self._admin.update_realm_role(
                        name=role.name, description=role.description, composite=role.composite
                    )
                    updated = self._admin.get_realm_role(role.name)
                    role_cache[role.name] = updated if updated else existing
                    changes["roles_updated"].append(role.name)
                else:
                    role_cache[role.name] = existing

        # Ensure group bindings exist and have the required roles.
        for group in policy.groups:
            kc_group = self._admin.find_group(group.name)
            if kc_group is None:
                kc_group = self._admin.create_group(group.name)
                changes["groups_created"].append(group.name)
            current_roles = {role["name"] for role in self._admin.get_group_realm_roles(kc_group["id"])}
            missing_role_objects = []
            for role_name in group.roles:
                if role_name not in role_cache:
                    fetched = self._admin.get_realm_role(role_name)
                    if fetched is None:
                        raise KeycloakRequestError(
                            f"Group '{group.name}' references unknown role '{role_name}'"
                        )
                    role_cache[role_name] = fetched
                if role_name not in current_roles:
                    missing_role_objects.append(role_cache[role_name])
            if missing_role_objects:
                self._admin.assign_group_realm_roles(kc_group["id"], missing_role_objects)
                changes.setdefault("group_role_assignments", {})[group.name] = [
                    role_obj["name"] for role_obj in missing_role_objects
                ]

        # Ensure service accounts have the expected realm roles.
        for binding in policy.service_accounts:
            client = self._admin.get_client_by_client_id(binding.client_id)
            if client is None:
                raise KeycloakRequestError(
                    f"Service account client '{binding.client_id}' does not exist in realm"
                )
            service_account = self._admin.get_service_account_user(client["id"])
            if service_account is None:
                raise KeycloakRequestError(
                    f"Client '{binding.client_id}' does not have an associated service account"
                )
            assigned_roles = {
                role["name"] for role in self._admin.get_user_realm_roles(service_account["id"])
            }
            missing_roles = []
            for role_name in binding.roles:
                if role_name not in role_cache:
                    fetched = self._admin.get_realm_role(role_name)
                    if fetched is None:
                        raise KeycloakRequestError(
                            f"Service account '{binding.client_id}' references unknown role '{role_name}'"
                        )
                    role_cache[role_name] = fetched
                if role_name not in assigned_roles:
                    missing_roles.append(role_cache[role_name])
            if missing_roles:
                self._admin.assign_realm_roles_to_user(service_account["id"], missing_roles)
                changes.setdefault("service_account_role_assignments", {})[
                    binding.client_id
                ] = [role["name"] for role in missing_roles]

        return changes


__all__ = [
    "RoleDefinition",
    "GroupBinding",
    "ServiceAccountBinding",
    "RBACPolicy",
    "RBACManager",
]
