"""Environment configuration utilities for OP-Observe."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional
import os


class MissingEnvironmentVariableError(RuntimeError):
    """Raised when a required environment variable is missing."""


class InvalidEnvironmentValueError(RuntimeError):
    """Raised when an environment variable cannot be parsed into the expected type."""


def _str_to_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise InvalidEnvironmentValueError(f"Cannot interpret '{value}' as boolean")


def load_dotenv_file(path: str | Path, *, override: bool = False, env: Optional[MutableMapping[str, str]] = None) -> None:
    """Load key/value pairs from a dotenv file into the provided environment mapping.

    Parameters
    ----------
    path:
        The path to the dotenv file.
    override:
        If ``True``, values from the dotenv file replace existing environment
        variables. Otherwise existing values are preserved.
    env:
        Mutable mapping that will receive the variables. Defaults to
        :data:`os.environ`.
    """

    environment: MutableMapping[str, str] = env if env is not None else os.environ
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        raise FileNotFoundError(f"Dotenv file '{dotenv_path}' does not exist")

    for raw_line in dotenv_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise InvalidEnvironmentValueError(
                f"Invalid line in dotenv file '{dotenv_path}': '{raw_line}'"
            )
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip().strip('"').strip("'")
        if key in environment and not override:
            continue
        environment[key] = value


@dataclass(slots=True)
class EnvironmentConfig:
    """Structured view of OP-Observe environment variables."""

    vault_addr: str
    vault_namespace: Optional[str]
    vault_role: str
    vault_oidc_audience: str
    vault_auth_path: str
    vault_kv_mount: str
    vault_kv_secret_path: str
    vault_verify_tls: bool

    keycloak_base_url: str
    keycloak_realm: str
    keycloak_client_id: str
    keycloak_client_secret: str
    keycloak_scope: Optional[str]
    keycloak_admin_client_id: str
    keycloak_admin_username: str
    keycloak_admin_password: str
    keycloak_verify_tls: bool

    rbac_default_group: Optional[str]
    rbac_service_roles: tuple[str, ...]

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "EnvironmentConfig":
        mapping = env if env is not None else os.environ

        def require(name: str) -> str:
            value = mapping.get(name)
            if value is None or value == "":
                raise MissingEnvironmentVariableError(
                    f"Environment variable '{name}' is required but missing"
                )
            return value

        def optional(name: str) -> Optional[str]:
            value = mapping.get(name)
            if value is None or value == "":
                return None
            return value

        def optional_bool(name: str, default: bool) -> bool:
            value = mapping.get(name)
            if value is None or value == "":
                return default
            return _str_to_bool(value)

        def optional_csv(name: str) -> tuple[str, ...]:
            value = optional(name)
            if not value:
                return tuple()
            items: Iterable[str] = (item.strip() for item in value.split(","))
            return tuple(item for item in items if item)

        return cls(
            vault_addr=require("VAULT_ADDR"),
            vault_namespace=optional("VAULT_NAMESPACE"),
            vault_role=require("VAULT_ROLE"),
            vault_oidc_audience=require("VAULT_OIDC_AUDIENCE"),
            vault_auth_path=mapping.get("VAULT_AUTH_PATH", "jwt"),
            vault_kv_mount=mapping.get("VAULT_KV_MOUNT", "kv"),
            vault_kv_secret_path=require("VAULT_KV_SECRET_PATH"),
            vault_verify_tls=optional_bool("VAULT_VERIFY_TLS", True),
            keycloak_base_url=require("KEYCLOAK_BASE_URL"),
            keycloak_realm=require("KEYCLOAK_REALM"),
            keycloak_client_id=require("KEYCLOAK_CLIENT_ID"),
            keycloak_client_secret=require("KEYCLOAK_CLIENT_SECRET"),
            keycloak_scope=optional("KEYCLOAK_SCOPE"),
            keycloak_admin_client_id=mapping.get("KEYCLOAK_ADMIN_CLIENT_ID", "admin-cli"),
            keycloak_admin_username=require("KEYCLOAK_ADMIN_USERNAME"),
            keycloak_admin_password=require("KEYCLOAK_ADMIN_PASSWORD"),
            keycloak_verify_tls=optional_bool("KEYCLOAK_VERIFY_TLS", True),
            rbac_default_group=optional("RBAC_DEFAULT_GROUP"),
            rbac_service_roles=optional_csv("RBAC_SERVICE_ROLES"),
        )
