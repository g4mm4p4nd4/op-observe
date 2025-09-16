from __future__ import annotations

import os

import pytest

from op_observe.config import EnvironmentConfig, load_dotenv_file
from op_observe.config.environment import InvalidEnvironmentValueError, MissingEnvironmentVariableError


def test_load_dotenv_file(tmp_path):
    env_file = tmp_path / "config.env"
    env_file.write_text(
        """
        # comment line
        FOO=bar
        BAR="quoted value"
        BAZ='another value'
        """
    )
    env: dict[str, str] = {"EXISTING": "keep"}
    load_dotenv_file(env_file, env=env)
    assert env["FOO"] == "bar"
    assert env["BAR"] == "quoted value"
    assert env["BAZ"] == "another value"
    assert env["EXISTING"] == "keep"

    env["FOO"] = "orig"
    load_dotenv_file(env_file, env=env, override=False)
    assert env["FOO"] == "orig"

    load_dotenv_file(env_file, env=env, override=True)
    assert env["FOO"] == "bar"


def test_load_dotenv_invalid_line(tmp_path):
    env_file = tmp_path / "bad.env"
    env_file.write_text("FOO\n")
    with pytest.raises(InvalidEnvironmentValueError):
        load_dotenv_file(env_file)


def test_environment_config_from_env():
    env = {
        "VAULT_ADDR": "https://vault",
        "VAULT_NAMESPACE": "admin",
        "VAULT_ROLE": "op-observe",
        "VAULT_OIDC_AUDIENCE": "vault",
        "VAULT_AUTH_PATH": "jwt",
        "VAULT_KV_MOUNT": "kv",
        "VAULT_KV_SECRET_PATH": "services/op-observe",
        "VAULT_VERIFY_TLS": "true",
        "KEYCLOAK_BASE_URL": "https://kc",
        "KEYCLOAK_REALM": "op",
        "KEYCLOAK_CLIENT_ID": "client",
        "KEYCLOAK_CLIENT_SECRET": "secret",
        "KEYCLOAK_SCOPE": "openid profile",
        "KEYCLOAK_ADMIN_CLIENT_ID": "admin-cli",
        "KEYCLOAK_ADMIN_USERNAME": "admin",
        "KEYCLOAK_ADMIN_PASSWORD": "password",
        "KEYCLOAK_VERIFY_TLS": "false",
        "RBAC_DEFAULT_GROUP": "operators",
        "RBAC_SERVICE_ROLES": "op-observe-service,op-observe-admin",
    }
    config = EnvironmentConfig.from_env(env)
    assert config.vault_addr == "https://vault"
    assert config.vault_namespace == "admin"
    assert config.vault_verify_tls is True
    assert config.keycloak_verify_tls is False
    assert config.rbac_service_roles == ("op-observe-service", "op-observe-admin")


def test_environment_config_missing_required(monkeypatch):
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    with pytest.raises(MissingEnvironmentVariableError):
        EnvironmentConfig.from_env({})
