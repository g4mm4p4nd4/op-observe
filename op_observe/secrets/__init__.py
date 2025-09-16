"""Secret management utilities for OP-Observe."""

from .vault import VaultClient, VaultError, VaultAuthenticationError, VaultRequestError

__all__ = [
    "VaultClient",
    "VaultError",
    "VaultAuthenticationError",
    "VaultRequestError",
]
