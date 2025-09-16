"""Vault integration utilities for OP-Observe."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from op_observe.utils.http import HTTPSession

from op_observe.auth.keycloak import KeycloakOIDCClient


class VaultError(RuntimeError):
    """Base exception for Vault integration errors."""


class VaultAuthenticationError(VaultError):
    """Raised when Vault authentication fails."""


class VaultRequestError(VaultError):
    """Raised when Vault operations return unexpected responses."""


@dataclass(slots=True)
class VaultClient:
    """Helper for authenticating with Vault and retrieving secrets."""

    address: str
    role: str
    oidc_audience: str
    auth_path: str = "jwt"
    namespace: Optional[str] = None
    kv_mount: str = "kv"
    verify: bool = True
    session: HTTPSession = field(default_factory=HTTPSession)
    _client_token: Optional[str] = field(default=None, init=False, repr=False)

    def _headers(self, extra: Optional[dict[str, str]] = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._client_token:
            headers["X-Vault-Token"] = self._client_token
        if self.namespace:
            headers["X-Vault-Namespace"] = self.namespace
        if extra:
            headers.update(extra)
        return headers

    def authenticate_with_oidc_token(
        self,
        jwt_token: str,
        *,
        audience: Optional[str] = None,
        role: Optional[str] = None,
    ) -> dict[str, Any]:
        """Authenticate to Vault using an external JWT (OIDC) token."""

        payload = {
            "role": role or self.role,
            "jwt": jwt_token,
        }
        if audience or self.oidc_audience:
            payload["audience"] = audience or self.oidc_audience

        response = self.session.post(
            f"{self.address}/v1/auth/{self.auth_path}/login",
            json=payload,
            headers=self._headers({"Content-Type": "application/json"}),
            verify=self.verify,
            timeout=30,
        )
        if response.status_code != 200:
            raise VaultAuthenticationError(
                f"Vault login failed: {response.status_code} {response.text}"
            )
        data = response.json()
        auth = data.get("auth") or {}
        token = auth.get("client_token")
        if not token:
            raise VaultAuthenticationError("Vault login response did not include a client token")
        self._client_token = token
        return auth

    def authenticate_with_keycloak(
        self,
        oidc_client: KeycloakOIDCClient,
        *,
        audience: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> dict[str, Any]:
        """Authenticate to Vault by obtaining a token from Keycloak."""

        token_response = oidc_client.get_token(audience=audience or self.oidc_audience, scope=scope)
        access_token = token_response.get("access_token")
        if not access_token:  # pragma: no cover - defensive guard
            raise VaultAuthenticationError("Keycloak token response missing 'access_token'")
        return self.authenticate_with_oidc_token(access_token, audience=audience)

    def _kv_data_url(self, path: str, *, mount_point: Optional[str] = None) -> str:
        mount = mount_point or self.kv_mount
        normalized_path = path.strip("/")
        return f"{self.address}/v1/{mount}/data/{normalized_path}"

    def read_secret(
        self,
        path: str,
        *,
        mount_point: Optional[str] = None,
        field: Optional[str] = None,
    ) -> Any:
        """Read a secret from Vault's KV v2 engine."""

        if not self._client_token:
            raise VaultAuthenticationError("Vault client has not been authenticated")
        response = self.session.get(
            self._kv_data_url(path, mount_point=mount_point),
            headers=self._headers(),
            verify=self.verify,
            timeout=30,
        )
        if response.status_code == 404:
            raise VaultRequestError(f"Secret '{path}' not found")
        if response.status_code != 200:
            raise VaultRequestError(
                f"Failed to read secret '{path}': {response.status_code} {response.text}"
            )
        payload = response.json()
        data = payload.get("data", {}).get("data", {})
        if field:
            if field not in data:
                raise VaultRequestError(
                    f"Field '{field}' not found in secret '{path}'"
                )
            return data[field]
        return data

    def read_secret_metadata(self, path: str, *, mount_point: Optional[str] = None) -> dict[str, Any]:
        """Retrieve metadata for a secret in KV v2."""

        if not self._client_token:
            raise VaultAuthenticationError("Vault client has not been authenticated")
        mount = mount_point or self.kv_mount
        normalized_path = path.strip("/")
        url = f"{self.address}/v1/{mount}/metadata/{normalized_path}"
        response = self.session.get(
            url,
            headers=self._headers(),
            verify=self.verify,
            timeout=30,
        )
        if response.status_code == 404:
            raise VaultRequestError(f"Metadata for secret '{path}' not found")
        if response.status_code != 200:
            raise VaultRequestError(
                f"Failed to read metadata for '{path}': {response.status_code} {response.text}"
            )
        return response.json().get("data", {})


__all__ = ["VaultClient", "VaultError", "VaultAuthenticationError", "VaultRequestError"]
