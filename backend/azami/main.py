"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from azami.config import get_settings
from azami.logging_config import configure_logging

log = logging.getLogger("azami")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from azami.auth.service import ensure_bootstrap_admin
    from azami.engagement import manager
    from azami.persistence.db import SessionLocal, init_db

    configure_logging()
    init_db()
    db = SessionLocal()
    try:
        ensure_bootstrap_admin(db)
        manager.restore_active(db)
    finally:
        db.close()
    log.info("Azami backend started (locked=%s)", manager.is_locked())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=f"{settings.app_name} API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers (added phase by phase).
    from azami.api.routers import audit, auth, engagement

    app.include_router(auth.router)
    app.include_router(engagement.router)
    app.include_router(audit.router)

    # Optional routers become available as their phases land.
    for module_name, attr in [
        ("azami.api.routers.osint", "router"),
        ("azami.api.routers.jobs", "router"),
        ("azami.api.routers.entities", "router"),
        ("azami.api.routers.wordlists", "router"),
        ("azami.api.routers.playbooks", "router"),
        ("azami.api.routers.report", "router"),
        ("azami.api.ws.jobs", "router"),
    ]:
        try:
            module = __import__(module_name, fromlist=[attr])
            app.include_router(getattr(module, attr))
        except ImportError:
            continue

    @app.get("/health", tags=["status"])
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
