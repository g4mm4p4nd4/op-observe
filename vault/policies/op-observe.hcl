# OP-Observe Vault Policy
# Grants services read-only access to their secrets and allows operators to list
# metadata for auditing.

path "kv/data/services/op-observe/*" {
  capabilities = ["read", "list"]
}

path "kv/metadata/services/op-observe/*" {
  capabilities = ["list"]
}

# Enable tokens issued via OIDC role to renew themselves while active.
path "auth/token/lookup-self" {
  capabilities = ["read"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}
