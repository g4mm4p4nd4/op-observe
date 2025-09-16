from __future__ import annotations

from unittest.mock import Mock

import pytest

from op_observe.auth.keycloak import (
    KeycloakAdminClient,
    KeycloakAuthenticationError,
    KeycloakOIDCClient,
)
from op_observe.secrets.vault import VaultAuthenticationError, VaultClient


def make_response(status_code: int, json_data: dict | None = None, text: str = "") -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.text = text
    response.headers = {}
    return response


def test_keycloak_oidc_client_get_token():
    session = Mock()
    session.headers = {}
    session.post.return_value = make_response(
        200, {"access_token": "token", "expires_in": 60}
    )

    client = KeycloakOIDCClient(
        base_url="https://kc.example.com",
        realm="op",
        client_id="service",
        client_secret="secret",
        scope="openid",
        session=session,
    )

    payload = client.get_token(audience="vault")
    assert payload["access_token"] == "token"
    call_kwargs = session.post.call_args.kwargs
    assert call_kwargs["data"]["audience"] == "vault"
    assert call_kwargs["data"]["scope"] == "openid"


def test_keycloak_admin_request_reauth_on_401():
    session = Mock()
    session.headers = {}
    session.post.side_effect = [
        make_response(200, {"access_token": "token1"}),
        make_response(200, {"access_token": "token2"}),
    ]
    session.request.side_effect = [
        make_response(401, text="expired"),
        make_response(200, {"name": "example"}),
    ]

    admin = KeycloakAdminClient(
        base_url="https://kc.example.com",
        realm="op",
        admin_client_id="admin-cli",
        username="admin",
        password="password",
        session=session,
    )

    response = admin._request("get", "roles/example")
    assert response.json()["name"] == "example"
    assert session.post.call_count == 2
    assert session.request.call_count == 2
    assert admin.session.headers["Authorization"] == "Bearer token2"


def test_vault_authenticate_with_keycloak_and_read_secret():
    keycloak_session = Mock()
    keycloak_session.headers = {}
    keycloak_session.post.return_value = make_response(200, {"access_token": "oidc-token"})

    vault_session = Mock()
    vault_session.headers = {}
    vault_session.post.return_value = make_response(
        200, {"auth": {"client_token": "vault-token"}}
    )
    vault_session.get.return_value = make_response(
        200, {"data": {"data": {"username": "svc", "password": "secret"}}}
    )

    oidc_client = KeycloakOIDCClient(
        base_url="https://kc.example.com",
        realm="op",
        client_id="service",
        client_secret="secret",
        session=keycloak_session,
    )
    vault_client = VaultClient(
        address="https://vault.example.com",
        role="op-observe",
        oidc_audience="vault",
        namespace="admin",
        session=vault_session,
    )

    auth = vault_client.authenticate_with_keycloak(oidc_client)
    assert auth["client_token"] == "vault-token"
    secret = vault_client.read_secret("services/op-observe", field="password")
    assert secret == "secret"
    vault_session.get.assert_called_once()
    assert vault_session.get.call_args.kwargs["headers"]["X-Vault-Namespace"] == "admin"


def test_vault_requires_authentication():
    vault_client = VaultClient(address="https://vault", role="role", oidc_audience="vault")
    with pytest.raises(VaultAuthenticationError):
        vault_client.read_secret("services/op-observe")


def test_keycloak_oidc_failure_raises():
    session = Mock()
    session.headers = {}
    session.post.return_value = make_response(400, {"error": "invalid_client"}, text="bad")
    client = KeycloakOIDCClient(
        base_url="https://kc.example.com",
        realm="op",
        client_id="service",
        client_secret="bad",
        session=session,
    )
    with pytest.raises(KeycloakAuthenticationError):
        client.get_token()
