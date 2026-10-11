"""FastAPI application factory."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.middleware import RequestIdMiddleware

DESCRIPTION = """
FinTrace is a **portfolio prototype** for transaction monitoring and investigation.

* Data is synthetic (PaySim-style). Do not use with real customer data.
* Risk scores are triage signals for human review, not proof of wrongdoing.
* Not production-ready, not regulatory-certified, not validated for real AML decisions.
"""


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO)

    app = FastAPI(
        title="FinTrace API",
        version=__version__,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
