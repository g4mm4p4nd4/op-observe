from __future__ import annotations

from unittest.mock import Mock

from op_observe.auth.keycloak import KeycloakAdminClient
from op_observe.auth.rbac import (
    GroupBinding,
    RBACManager,
    RBACPolicy,
    RoleDefinition,
    ServiceAccountBinding,
)


def make_response(status_code: int, json_data: dict | None = None, text: str = "") -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.text = text
    response.headers = {}
    return response


def test_rbac_manager_sync_policy_creates_roles_groups_and_bindings():
    session = Mock()
    session.headers = {}
    session.post.return_value = make_response(200, {"access_token": "admintoken"})

    session.request.side_effect = [
        # Role "op-observe-service" not found
        make_response(404, {}),
        # Create role
        make_response(201, {}),
        # Fetch created role
        make_response(
            200,
            {
                "id": "role-service",
                "name": "op-observe-service",
                "description": "Service role",
                "composite": False,
            },
        ),
        # Role "op-observe-admin" existing but outdated
        make_response(
            200,
            {
                "id": "role-admin",
                "name": "op-observe-admin",
                "description": "Outdated",
                "composite": False,
            },
        ),
        # Update realm role
        make_response(204, {}),
        # Fetch updated role
        make_response(
            200,
            {
                "id": "role-admin",
                "name": "op-observe-admin",
                "description": "Administrative",
                "composite": False,
            },
        ),
        # Find group -> none
        make_response(200, []),
        # Create group
        make_response(201, {}),
        # Find group again -> now exists
        make_response(200, [{"id": "group-operators", "name": "op-observe-operators"}]),
        # Get existing group roles -> none
        make_response(200, []),
        # Assign group role mappings
        make_response(204, {}),
        # Get client by clientId
        make_response(200, [{"id": "client-uuid", "clientId": "op-observe-service"}]),
        # Get service account user
        make_response(200, {"id": "service-account-user"}),
        # Get service account realm roles -> none
        make_response(200, []),
        # Assign realm roles to service account
        make_response(204, {}),
    ]

    admin = KeycloakAdminClient(
        base_url="https://kc.example.com",
        realm="op",
        admin_client_id="admin-cli",
        username="admin",
        password="password",
        session=session,
    )

    policy = RBACPolicy(
        roles=(
            RoleDefinition(name="op-observe-service", description="Service role"),
            RoleDefinition(name="op-observe-admin", description="Administrative"),
        ),
        groups=(
            GroupBinding(name="op-observe-operators", roles=("op-observe-service",)),
        ),
        service_accounts=(
            ServiceAccountBinding(client_id="op-observe-service", roles=("op-observe-admin",)),
        ),
    )

    changes = RBACManager(admin).sync_policy(policy)

    assert changes["roles_created"] == ["op-observe-service"]
    assert changes["roles_updated"] == ["op-observe-admin"]
    assert changes["groups_created"] == ["op-observe-operators"]
    assert changes["group_role_assignments"] == {
        "op-observe-operators": ["op-observe-service"]
    }
    assert changes["service_account_role_assignments"] == {
        "op-observe-service": ["op-observe-admin"]
    }

    # Ensure the admin client was authenticated exactly once.
    assert session.post.call_count == 1
