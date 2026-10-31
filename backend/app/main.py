"""
SealTrail FastAPI application factory and lifespan configuration.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.logging import logger, setup_logging
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging(log_level="DEBUG" if settings.APP_ENV == "development" else "INFO")
    logger.info("application_startup", app_env=settings.APP_ENV)

    # Initialize scheduler in single worker mode if required
    # (Stage 5 will initialize APScheduler)
    try:
        from app.jobs.scheduler import start_scheduler, shutdown_scheduler
        start_scheduler()
    except (ImportError, AttributeError):
        pass

    yield

    logger.info("application_shutdown")
    try:
        from app.jobs.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except (ImportError, AttributeError):
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="SealTrail API",
        description="Tamper-evident Digital Evidence Chain-of-Custody & Case Workspace",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Request ID and timing middleware
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        # Skip noisy polling endpoints from access logs
        if request.url.path not in ("/healthz", "/readyz"):
            logger.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                request_id=request_id,
                ip=request.client.host if request.client else None,
            )
        return response

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )

    # Error envelope exception handlers
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Core routers
    app.include_router(health.router)
    from app.routers import (
        alerts,
        approvals,
        audit,
        auth,
        cases,
        custody,
        evidence,
        exports,
        integrity,
        links,
        reports,
        users,
    )
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(cases.router)
    app.include_router(evidence.router)
    app.include_router(custody.router)
    app.include_router(approvals.router)
    app.include_router(links.router)
    app.include_router(alerts.router)
    app.include_router(audit.router)
    app.include_router(integrity.router)
    app.include_router(reports.router)
    app.include_router(exports.router)

    return app


app = create_app()
