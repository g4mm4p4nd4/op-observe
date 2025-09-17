import pytest

from op_observe.security.env import EnvironmentSettings


@pytest.fixture
def base_env() -> dict[str, str]:
    return {
        "VAULT_ADDR": "https://vault.example:8200",
        "VAULT_TOKEN": "token-123",
        "KEYCLOAK_URL": "https://keycloak.example/auth",
        "KEYCLOAK_REALM": "op-observe",
        "OPA_URL": "https://opa.example/v1/data/opobserve/allow",
    }


def test_environment_settings_from_env(base_env: dict[str, str]) -> None:
    base_env["OP_OBSERVE_AUDIT_TOPIC"] = "audits"
    settings = EnvironmentSettings.from_env(base_env)

    assert settings.vault_addr == "https://vault.example:8200"
    assert settings.gatekeeper_enabled is True
    assert settings.extra == {"OP_OBSERVE_AUDIT_TOPIC": "audits"}


def test_environment_settings_respects_gatekeeper_flag(base_env: dict[str, str]) -> None:
    base_env["GATEKEEPER_ENABLED"] = "false"
    settings = EnvironmentSettings.from_env(base_env)
    assert settings.gatekeeper_enabled is False


def test_environment_settings_missing_variables(base_env: dict[str, str]) -> None:
    base_env.pop("VAULT_TOKEN")
    with pytest.raises(ValueError):
        EnvironmentSettings.from_env(base_env)


def test_environment_settings_from_os_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_ADDR", "https://vault")
    monkeypatch.setenv("VAULT_TOKEN", "token")
    monkeypatch.setenv("KEYCLOAK_URL", "https://keycloak")
    monkeypatch.setenv("KEYCLOAK_REALM", "realm")
    monkeypatch.setenv("OPA_URL", "https://opa")
    settings = EnvironmentSettings.from_env()
    assert settings.vault_addr == "https://vault"
    assert settings.keycloak_realm == "realm"
