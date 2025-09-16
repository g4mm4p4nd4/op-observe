"""Keycloak authentication helpers for OP-Observe."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from op_observe.utils.http import HTTPSession, HttpResponse


class KeycloakError(RuntimeError):
    """Base exception for Keycloak integration errors."""


class KeycloakAuthenticationError(KeycloakError):
    """Raised when authentication with Keycloak fails."""


class KeycloakRequestError(KeycloakError):
    """Raised when the Keycloak Admin API returns an unexpected response."""


@dataclass(slots=True)
class KeycloakOIDCClient:
    """Client credentials helper for Keycloak OIDC tokens."""

    base_url: str
    realm: str
    client_id: str
    client_secret: str
    scope: Optional[str] = None
    verify: bool = True
    session: HTTPSession = field(default_factory=HTTPSession)

    @property
    def token_endpoint(self) -> str:
        return f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/token"

    def get_token(self, *, audience: Optional[str] = None, scope: Optional[str] = None) -> dict[str, Any]:
        """Request a client-credential access token from Keycloak."""

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        final_scope = scope or self.scope
        if final_scope:
            payload["scope"] = final_scope
        if audience:
            payload["audience"] = audience

        response = self.session.post(
            self.token_endpoint,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            verify=self.verify,
            timeout=30,
        )
        if response.status_code != 200:
            raise KeycloakAuthenticationError(
                f"Failed to obtain token from Keycloak: {response.status_code} {response.text}"
            )
        data = response.json()
        if "access_token" not in data:
            raise KeycloakAuthenticationError("Keycloak response did not include an access token")
        return data


@dataclass(slots=True)
class KeycloakAdminClient:
    """Thin wrapper around the Keycloak Admin REST API."""

    base_url: str
    realm: str
    admin_client_id: str
    username: str
    password: str
    scope: Optional[str] = None
    verify: bool = True
    session: HTTPSession = field(default_factory=HTTPSession)
    _token: Optional[str] = field(default=None, init=False, repr=False)

    @property
    def token_endpoint(self) -> str:
        return f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/token"

    @property
    def admin_base_url(self) -> str:
        return f"{self.base_url}/admin/realms/{self.realm}"

    def authenticate(self) -> str:
        """Authenticate using Resource Owner Password Credentials flow."""

        payload = {
            "grant_type": "password",
            "client_id": self.admin_client_id,
            "username": self.username,
            "password": self.password,
        }
        if self.scope:
            payload["scope"] = self.scope

        response = self.session.post(
            self.token_endpoint,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            verify=self.verify,
            timeout=30,
        )
        if response.status_code != 200:
            raise KeycloakAuthenticationError(
                f"Failed to authenticate with Keycloak admin API: {response.status_code} {response.text}"
            )
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise KeycloakAuthenticationError("Keycloak admin authentication did not return an access token")
        self._token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return token

    def _ensure_token(self) -> None:
        if not self._token:
            self.authenticate()

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected_status: tuple[int, ...] = (200, 201, 204),
        **kwargs: Any,
    ) -> HttpResponse:
        self._ensure_token()
        url = f"{self.admin_base_url}/{path.lstrip('/')}"
        response = self.session.request(method, url, verify=self.verify, timeout=30, **kwargs)
        if response.status_code == 401:
            # Token expired, re-authenticate once.
            self.authenticate()
            response = self.session.request(method, url, verify=self.verify, timeout=30, **kwargs)
        if response.status_code not in expected_status:
            raise KeycloakRequestError(
                f"Keycloak admin API error {response.status_code} on {method.upper()} {url}: {response.text}"
            )
        return response

    # Realm role helpers -------------------------------------------------
    def get_realm_role(self, name: str) -> Optional[dict[str, Any]]:
        response = self._request("get", f"roles/{name}", expected_status=(200, 404))
        if response.status_code == 404:
            return None
        return response.json()

    def create_realm_role(self, *, name: str, description: str, composite: bool = False) -> None:
        self._request(
            "post",
            "roles",
            json={"name": name, "description": description, "composite": composite},
        )

    def update_realm_role(self, *, name: str, description: str, composite: bool = False) -> None:
        self._request(
            "put",
            f"roles/{name}",
            json={"name": name, "description": description, "composite": composite},
        )

    # Group helpers ------------------------------------------------------
    def find_group(self, name: str) -> Optional[dict[str, Any]]:
        response = self._request("get", "groups", params={"search": name})
        groups = response.json()
        for group in groups or []:
            if group.get("name") == name:
                return group
        return None

    def create_group(self, name: str) -> dict[str, Any]:
        self._request("post", "groups", json={"name": name})
        # Keycloak returns 201 with Location header. Fetch newly created group via search.
        group = self.find_group(name)
        if not group:
            raise KeycloakRequestError(f"Created group '{name}' but could not retrieve it")
        return group

    def get_group_realm_roles(self, group_id: str) -> list[dict[str, Any]]:
        response = self._request("get", f"groups/{group_id}/role-mappings/realm")
        return response.json() or []

    def assign_group_realm_roles(self, group_id: str, roles: Iterable[dict[str, Any]]) -> None:
        self._request(
            "post",
            f"groups/{group_id}/role-mappings/realm",
            json=list(roles),
        )

    def get_user_realm_roles(self, user_id: str) -> list[dict[str, Any]]:
        response = self._request("get", f"users/{user_id}/role-mappings/realm")
        return response.json() or []

    def assign_realm_roles_to_user(self, user_id: str, roles: Iterable[dict[str, Any]]) -> None:
        self._request(
            "post",
            f"users/{user_id}/role-mappings/realm",
            json=list(roles),
        )

    # Client helpers -----------------------------------------------------
    def get_client_by_client_id(self, client_id: str) -> Optional[dict[str, Any]]:
        response = self._request("get", "clients", params={"clientId": client_id})
        clients = response.json()
        if not clients:
            return None
        return clients[0]

    def get_client_role(self, client_uuid: str, role_name: str) -> Optional[dict[str, Any]]:
        response = self._request(
            "get",
            f"clients/{client_uuid}/roles/{role_name}",
            expected_status=(200, 404),
        )
        if response.status_code == 404:
            return None
        return response.json()

    def assign_client_roles_to_service_account(self, service_account_user_id: str, roles: Iterable[dict[str, Any]]) -> None:
        self._request(
            "post",
            f"users/{service_account_user_id}/role-mappings/clients",
            json=list(roles),
        )

    def get_service_account_user(self, client_uuid: str) -> Optional[dict[str, Any]]:
        response = self._request(
            "get",
            f"clients/{client_uuid}/service-account-user",
            expected_status=(200, 404),
        )
        if response.status_code == 404:
            return None
        return response.json()
