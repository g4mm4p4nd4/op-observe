from __future__ import annotations

import json

import pytest

from op_observe.security.vault import InMemoryVaultTransport, VaultClient


@pytest.fixture
def transport() -> InMemoryVaultTransport:
    secrets = {
        "kv/data/opobserve": {
            "data": {
                "api-key": "secret-value",
                "endpoint": "https://service" 
            },
            "metadata": {
                "version": 3
            }
        }
    }
    return InMemoryVaultTransport(secrets=secrets)


def test_vault_client_reads_kv_v2_secret(transport: InMemoryVaultTransport) -> None:
    client = VaultClient("https://vault.example:8200", "token", transport)
    secret = client.read_secret("kv/data/opobserve")

    assert secret.path == "kv/data/opobserve"
    assert secret["api-key"] == "secret-value"
    assert secret.metadata["version"] == 3


def test_vault_client_cache_dump(transport: InMemoryVaultTransport) -> None:
    client = VaultClient("https://vault.example:8200", "token", transport)
    client.read_secret("kv/data/opobserve")
    dumped = json.loads(client.dump_cache())

    assert "kv/data/opobserve" in dumped
    assert dumped["kv/data/opobserve"]["data"]["endpoint"] == "https://service"


def test_vault_client_raises_for_missing_secret(transport: InMemoryVaultTransport) -> None:
    client = VaultClient("https://vault.example:8200", "token", transport)
    with pytest.raises(KeyError):
        client.read_secret("kv/data/unknown")
