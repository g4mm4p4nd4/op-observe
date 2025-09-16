# OP-Observe Environment & Secrets Utilities

This repository provides utilities to configure environment variables, integrate with HashiCorp Vault and Keycloak, and manage RBAC policies for the OP-Observe platform. The modules are designed to be used in on-prem deployments where secure secret retrieval and role-based access control are required.

## Features

- Declarative environment configuration loader with `.env` template.
- Keycloak OIDC client for service authentication and administrative operations.
- Vault client helpers for OIDC authentication and KV secret retrieval.
- Reusable RBAC policy definitions and synchronization helpers for Keycloak.
- Tests that exercise environment parsing, OIDC token acquisition, Vault login, and RBAC reconciliation flows.

## Getting Started

1. Copy `env/.env.example` to `.env` and adjust values for your deployment.
2. Install dependencies (preferably inside a virtual environment):

   ```bash
   pip install -e .[dev]
   ```

3. Run the tests:

   ```bash
   pytest
   ```

## Project Layout

- `op_observe/config/environment.py` – Environment variable parsing helpers.
- `op_observe/auth/keycloak.py` – Keycloak OIDC and admin clients.
- `op_observe/secrets/vault.py` – Vault authentication and secret retrieval helpers.
- `op_observe/auth/rbac.py` – Declarative RBAC policy definitions and synchronization logic.
- `env/.env.example` – Template environment file.
- `vault/policies/op-observe.hcl` – Example Vault policy for OP-Observe services.
- `keycloak/rbac-policy.json` – Example Keycloak RBAC manifest.

## Licensing

This project is provided as-is for demonstration purposes within the OP-Observe platform.
