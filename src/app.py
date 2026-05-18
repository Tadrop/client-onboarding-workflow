"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .drafter.offline import install_default_offline_fallback
from .logging_setup import configure_logging, get_logger
from .review_queue.routes import router as review_router
from .state import get_store
from .webhook.routes import router as webhook_router


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = get_logger("app")
    settings = get_settings()
    # Initialize the SQLite schema eagerly.
    get_store()
    install_default_offline_fallback()
    log.info(
        "app.startup",
        env=settings.app_env,
        mock_integrations=settings.mock_integrations,
    )
    yield
    log.info("app.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Halo Onboarding Workflow",
        description="Runs the client onboarding flow when a contract is signed.",
        version="0.1.0",
        lifespan=_lifespan,
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(webhook_router)
    app.include_router(review_router)
    return app


app = create_app()
