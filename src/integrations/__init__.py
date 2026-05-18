"""Integration clients for every external system.

Each integration has:

  - A `Protocol` defining the surface area used by milestones
  - A `Real…Client` (placeholder where appropriate) that talks to the live API
  - A `Mock…Client` that is fully in-process and deterministic, used by
    default (`MOCK_INTEGRATIONS=true`) for local dev, demos, and CI.

The `get_clients()` factory returns a bundle of the active implementations.
"""

from .registry import IntegrationBundle, get_clients, reset_clients_cache

__all__ = ["IntegrationBundle", "get_clients", "reset_clients_cache"]
