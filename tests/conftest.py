"""Shared pytest fixtures.

Every test gets:
  - a fresh in-memory SQLite store (no leakage between tests)
  - a fresh `IntegrationBundle` of in-process mock clients
  - the deterministic Claude offline fallback installed
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# Force mock mode + in-memory DB BEFORE any src module is imported.
os.environ.setdefault("MOCK_INTEGRATIONS", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DOCUSIGN_WEBHOOK_SECRET", "test-secret-docusign")
os.environ.setdefault("PANDADOC_WEBHOOK_SECRET", "test-secret-pandadoc")


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    """Reset caches between tests so each test sees a fresh store + clients."""
    from src import config as cfg
    from src.drafter.offline import install_default_offline_fallback
    from src.integrations import reset_clients_cache
    from src.router.classifier import get_classifier
    from src.state import reset_store_cache

    cfg.reset_settings_cache()
    reset_store_cache()
    reset_clients_cache()
    get_classifier.cache_clear()
    install_default_offline_fallback()
    yield


@pytest.fixture
def store():
    from src.state import get_store

    return get_store()


@pytest.fixture
def clients():
    from src.integrations import get_clients

    return get_clients()


@pytest.fixture
def settings():
    from src.config import get_settings

    return get_settings()
