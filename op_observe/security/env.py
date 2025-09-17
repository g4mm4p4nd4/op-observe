"""Environment variable helpers for OP-Observe security services."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping, MutableMapping


_REQUIRED_VARIABLES = {
    "VAULT_ADDR": "Address of the Vault cluster",  # for docs only
    "VAULT_TOKEN": "Token used for Vault AppRole or static auth",  # docs
    "KEYCLOAK_URL": "Base URL for the Keycloak deployment",
    "KEYCLOAK_REALM": "Realm used for OP-Observe users",
    "OPA_URL": "OPA or Gatekeeper policy endpoint",
}

_OPTIONAL_DEFAULTS = {
    "GATEKEEPER_ENABLED": "true",
    "KEYCLOAK_RBAC_CLIENT": "op-observe-control-plane",
}

_BOOLEAN_TRUE = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class EnvironmentSettings:
    """Container for security-related environment variables."""

    vault_addr: str
    vault_token: str
    keycloak_url: str
    keycloak_realm: str
    keycloak_rbac_client: str
    opa_url: str
    gatekeeper_enabled: bool
    extra: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, *, mutable: bool = False
    ) -> "EnvironmentSettings":
        """Construct settings from the provided environment mapping.

        Args:
            env: A mapping to read variables from. Defaults to ``os.environ``.
            mutable: When ``True`` the ``extra`` mapping is mutable allowing tests to
                tweak values in-place without rebuilding the dataclass.

        Raises:
            ValueError: If required variables are missing.
        """

        source: Mapping[str, str]
        if env is None:
            source = os.environ
        else:
            source = env

        missing = [var for var in _REQUIRED_VARIABLES if not source.get(var)]
        if missing:
            missing_csv = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {missing_csv}")

        resolved: MutableMapping[str, str]
        if mutable:
            resolved = dict(source)
        else:
            resolved = {k: source[k] for k in source}

        for key, default in _OPTIONAL_DEFAULTS.items():
            resolved.setdefault(key, default)

        gatekeeper_flag = resolved.get("GATEKEEPER_ENABLED", "true").lower()
        gatekeeper_enabled = gatekeeper_flag in _BOOLEAN_TRUE

        extra = {
            key: value
            for key, value in resolved.items()
            if key.startswith("OP_OBSERVE_") and key not in _REQUIRED_VARIABLES
        }

        return cls(
            vault_addr=resolved["VAULT_ADDR"],
            vault_token=resolved["VAULT_TOKEN"],
            keycloak_url=resolved["KEYCLOAK_URL"],
            keycloak_realm=resolved["KEYCLOAK_REALM"],
            keycloak_rbac_client=resolved["KEYCLOAK_RBAC_CLIENT"],
            opa_url=resolved["OPA_URL"],
            gatekeeper_enabled=gatekeeper_enabled,
            extra=extra if mutable else dict(extra),
        )

    def as_dict(self) -> Mapping[str, str]:
        """Expose the known environment values as a mapping."""

        return {
            "VAULT_ADDR": self.vault_addr,
            "VAULT_TOKEN": self.vault_token,
            "KEYCLOAK_URL": self.keycloak_url,
            "KEYCLOAK_REALM": self.keycloak_realm,
            "KEYCLOAK_RBAC_CLIENT": self.keycloak_rbac_client,
            "OPA_URL": self.opa_url,
            "GATEKEEPER_ENABLED": "true" if self.gatekeeper_enabled else "false",
            **dict(self.extra),
        }
