from __future__ import annotations

from pathlib import Path

import pytest

from op_observe.security import (
    InMemoryKeycloakTransport,
    KeycloakClient,
    PolicyEngine,
    PolicyRequest,
    RBACEnforcer,
    load_policy_bundle,
    load_rbac_config,
)


@pytest.fixture(scope="module")
def config_root() -> Path:
    return Path(__file__).resolve().parents[1] / "config"


@pytest.fixture(scope="module")
def policy_engine(config_root: Path) -> PolicyEngine:
    bundle = load_policy_bundle(config_root / "policy")
    return PolicyEngine(bundle)


@pytest.fixture(scope="module")
def rbac_config(config_root: Path):
    return load_rbac_config(config_root / "rbac")


@pytest.fixture
def keycloak_transport() -> InMemoryKeycloakTransport:
    return InMemoryKeycloakTransport(
        userinfo={
            "token-admin": {"sub": "1", "preferred_username": "alice"},
            "token-analyst": {"sub": "2", "preferred_username": "bob"},
            "token-observer": {"sub": "3", "preferred_username": "carol"},
        },
        realm_roles={
            "op-observe:1": ("platform-admin",),
            "op-observe:2": ("security-analyst",),
            "op-observe:3": ("observer",),
        },
        client_roles={
            "op-observe:1": {"op-observe-control-plane": ("platform-admin",)},
            "op-observe:2": {"op-observe-control-plane": ("security-analyst",)},
            "op-observe:3": {"op-observe-control-plane": ("observer",)},
        },
    )


@pytest.fixture
def rbac_enforcer(
    policy_engine: PolicyEngine,
    rbac_config,
    keycloak_transport: InMemoryKeycloakTransport,
) -> RBACEnforcer:
    keycloak = KeycloakClient(
        realm="op-observe",
        rbac_client="op-observe-control-plane",
        transport=keycloak_transport,
    )
    return RBACEnforcer(
        keycloak=keycloak,
        policy_engine=policy_engine,
        rbac_config=rbac_config,
    )


def test_policy_engine_requires_gatekeeper_annotation(policy_engine: PolicyEngine) -> None:
    request = PolicyRequest(
        resource_kind="Secret",
        resource_name="vault:kv/app",
        namespace="op-observe",
        annotations={},
        labels={},
        roles=("platform-admin",),
        action="create",
    )
    decision = policy_engine.evaluate(request)
    assert decision.allowed is False
    assert any(
        "missing Gatekeeper approval" in message for message in decision.messages
    )


def test_rbac_enforcer_allows_authorized_access(rbac_enforcer: RBACEnforcer) -> None:
    decision = rbac_enforcer.authorize(
        "token-admin", action="secrets:read", resource="vault:kv/app"
    )
    assert decision.allowed is True


def test_rbac_enforcer_rejects_disallowed_role(rbac_enforcer: RBACEnforcer) -> None:
    decision = rbac_enforcer.authorize(
        "token-observer", action="secrets:read", resource="vault:kv/app"
    )
    assert decision.allowed is False
    assert "allowedRoles" in " ".join(decision.messages)


def test_rbac_enforcer_rejects_missing_permission(rbac_enforcer: RBACEnforcer) -> None:
    decision = rbac_enforcer.authorize(
        "token-analyst", action="secrets:write", resource="vault:kv/app"
    )
    assert decision.allowed is False
    assert "not permitted" in " ".join(decision.messages)
