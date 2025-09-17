"""Vault integration primitives."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, MutableMapping, Protocol


class VaultTransport(Protocol):
    """Protocol describing the minimum surface required to interact with Vault."""

    def read_secret(self, path: str, *, token: str) -> Mapping[str, Any]:
        """Return the raw response for a secret path."""


@dataclass(frozen=True)
class VaultSecret:
    """Normalized representation of a Vault secret."""

    path: str
    data: Mapping[str, Any]
    metadata: Mapping[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]


class VaultClient:
    """Simple Vault client with pluggable transport for testing."""

    def __init__(self, address: str, token: str, transport: VaultTransport):
        self._address = address.rstrip("/")
        self._token = token
        self._transport = transport
        self._cache: MutableMapping[str, VaultSecret] = {}

    @property
    def address(self) -> str:
        return self._address

    def read_secret(self, path: str, *, use_cache: bool = True) -> VaultSecret:
        """Retrieve a secret from Vault.

        The method normalizes the response from both KV v1 and KV v2 engines.
        """

        if use_cache and path in self._cache:
            return self._cache[path]

        raw = self._transport.read_secret(path, token=self._token)
        if not raw:
            raise KeyError(f"Secret at path '{path}' was not found")

        if "data" in raw and isinstance(raw["data"], Mapping):
            payload = raw["data"]
            metadata = raw.get("metadata", {})
            if "data" in payload and isinstance(payload["data"], Mapping):
                # KV v2 data structure
                data = dict(payload["data"])
            else:
                data = dict(payload)
        else:
            data = dict(raw)
            metadata = {}

        secret = VaultSecret(path=path, data=data, metadata=dict(metadata))
        if use_cache:
            self._cache[path] = secret
        return secret

    def dump_cache(self) -> str:
        """Export the cached secrets for diagnostics and policy audits."""

        serialized = {
            path: {
                "data": secret.data,
                "metadata": secret.metadata,
            }
            for path, secret in self._cache.items()
        }
        return json.dumps(serialized, sort_keys=True)


class InMemoryVaultTransport:
    """Testing transport that serves secrets from a local mapping."""

    def __init__(self, secrets: Mapping[str, Mapping[str, Any]] | None = None):
        self._secrets: Dict[str, Mapping[str, Any]] = dict(secrets or {})

    def read_secret(self, path: str, *, token: str) -> Mapping[str, Any]:  # noqa: D401
        return self._secrets.get(path, {})

    def set_secret(self, path: str, data: Mapping[str, Any]) -> None:
        self._secrets[path] = data
