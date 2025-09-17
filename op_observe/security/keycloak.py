"""Keycloak helpers for RBAC integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Protocol, Sequence, Tuple


class KeycloakTransport(Protocol):
    """Protocol for fetching role information from Keycloak."""

    def get_userinfo(self, token: str) -> Mapping[str, Any]:
        """Return the decoded token or userinfo payload."""

    def get_realm_roles(self, realm: str, user_id: str) -> Sequence[str]:
        """Return the realm-level roles for a user."""

    def get_client_roles(
        self, realm: str, client_id: str, user_id: str
    ) -> Sequence[str]:
        """Return roles scoped to a specific client."""


@dataclass(frozen=True)
class KeycloakUser:
    """Representation of a Keycloak user relevant for RBAC decisions."""

    user_id: str
    username: str
    realm_roles: Tuple[str, ...]
    client_roles: Tuple[str, ...]

    @property
    def roles(self) -> Tuple[str, ...]:
        return self.realm_roles + self.client_roles


class KeycloakClient:
    """High-level wrapper that extracts RBAC data from Keycloak tokens."""

    def __init__(self, realm: str, rbac_client: str, transport: KeycloakTransport):
        self._realm = realm
        self._client = rbac_client
        self._transport = transport

    @property
    def realm(self) -> str:
        return self._realm

    def resolve_user(self, token: str) -> KeycloakUser:
        """Resolve a Keycloak token to a :class:`KeycloakUser`."""

        payload = self._transport.get_userinfo(token)
        user_id = str(payload["sub"])
        username = payload.get("preferred_username", payload.get("email", user_id))

        realm_roles = tuple(self._transport.get_realm_roles(self._realm, user_id))
        client_roles = tuple(
            self._transport.get_client_roles(self._realm, self._client, user_id)
        )

        return KeycloakUser(
            user_id=user_id,
            username=username,
            realm_roles=realm_roles,
            client_roles=client_roles,
        )


class InMemoryKeycloakTransport:
    """Testing transport with static realm and client role assignments."""

    def __init__(
        self,
        *,
        userinfo: Mapping[str, Mapping[str, Any]] | None = None,
        realm_roles: Mapping[str, Iterable[str]] | None = None,
        client_roles: Mapping[str, Mapping[str, Iterable[str]]] | None = None,
    ) -> None:
        self._userinfo: Dict[str, Mapping[str, Any]] = dict(userinfo or {})
        self._realm_roles: Dict[str, Tuple[str, ...]] = {
            user: tuple(roles) for user, roles in (realm_roles or {}).items()
        }
        self._client_roles: Dict[str, Dict[str, Tuple[str, ...]]] = {}
        for user, mapping in (client_roles or {}).items():
            self._client_roles[user] = {
                client: tuple(roles) for client, roles in mapping.items()
            }

    def get_userinfo(self, token: str) -> Mapping[str, Any]:  # noqa: D401
        try:
            return self._userinfo[token]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unknown token '{token}'") from exc

    def get_realm_roles(self, realm: str, user_id: str) -> Sequence[str]:  # noqa: D401
        key = f"{realm}:{user_id}"
        return self._realm_roles.get(key, ())

    def get_client_roles(  # noqa: D401
        self, realm: str, client_id: str, user_id: str
    ) -> Sequence[str]:
        key = f"{realm}:{user_id}"
        client_mapping = self._client_roles.get(key, {})
        return client_mapping.get(client_id, ())
