from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse

from apx.api.config import get_api_settings
from apx.persistence.config import get_persistence_settings
from apx.api.middleware import (
    RequestIDMiddleware,
    AuthMiddleware,
    AuthorizationMiddleware,
    get_request_id,
)
from apx.api.routes import health, invoices, cases, approvals, audit, metrics
from apx.persistence import init_database, close_database, get_session_factory
from apx.persistence.database import reset_database
from apx.application.services import (
    InvoiceService,
    CaseService,
    ApprovalService,
    AuditService,
    MetricsService,
    get_invoice_service,
    get_case_service,
    get_approval_service,
    get_audit_service,
    get_metrics_service,
)
from apx.persistence import (
    InvoiceRepository,
    CaseRepository,
    ApprovalRepository,
    ActionRepository,
    AuditRepository,
    SQLiteInvoiceRepository,
    SQLiteCaseRepository,
    SQLiteApprovalRepository,
    SQLiteActionRepository,
    SQLiteAuditRepository,
)
from apx.intelligence.validator import InvoiceValidator
from apx.evidence.engine import HybridContextEngine
from apx.action.pipeline import Phase4Pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger = logging.getLogger("apx.api.app")
    print("DEBUG: Lifespan started", flush=True)
    logger.info("Lifespan started")

    # Initialize database
    persistence_settings = get_persistence_settings()
    init_database(
        database_url=persistence_settings.get_database_url(),
        echo=persistence_settings.echo_sql,
        create_tables=True,
    )
    print("DEBUG: Database initialized", flush=True)
    logger.info("Database initialized")

    # Initialize core components
    validator = InvoiceValidator()
    evidence_engine = HybridContextEngine()
    pipeline = Phase4Pipeline()

    # Initialize repositories
    session_factory = get_session_factory()
    invoice_repo = SQLiteInvoiceRepository()
    case_repo = SQLiteCaseRepository()
    approval_repo = SQLiteApprovalRepository()
    action_repo = SQLiteActionRepository()
    audit_repo = SQLiteAuditRepository()

    # Initialize services - set globals in the services module
    import apx.application.services as services_module
    try:
        services_module._invoice_service = InvoiceService(
            invoice_repo=invoice_repo,
            case_repo=case_repo,
            approval_repo=approval_repo,
            audit_repo=audit_repo,
            validator=validator,
            evidence_engine=evidence_engine,
            pipeline=pipeline,
        )
        services_module._case_service = CaseService(case_repo, audit_repo)
        services_module._approval_service = ApprovalService(
            approval_repo=approval_repo,
            case_repo=case_repo,
            audit_repo=audit_repo,
        )
        services_module._audit_service = AuditService(audit_repo)
        services_module._metrics_service = MetricsService()
        logger.info(f"Services initialized: invoice={services_module._invoice_service is not None}, case={services_module._case_service is not None}, approval={services_module._approval_service is not None}, audit={services_module._audit_service is not None}, metrics={services_module._metrics_service is not None}")
        logger.info(f"Module id: {id(services_module)}, metrics_service: {services_module._metrics_service is not None}")
        # Verify the getter function can see it
        from apx.application.services import get_metrics_service
        try:
            _ = get_metrics_service()
            logger.info("Getter function can access metrics_service")
        except RuntimeError as e:
            logger.error(f"Getter function failed: {e}")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

    logger.info("APX API started successfully")

    yield

    # Cleanup
    close_database()
    logger.info("APX API shutdown complete")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    settings = get_api_settings()

    app = FastAPI(
        title=settings.title,
        version=settings.version,
        description=settings.description,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # CORS middleware (runs last in request phase)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Request ID middleware
    app.add_middleware(RequestIDMiddleware)

    # Authorization middleware
    app.add_middleware(AuthorizationMiddleware)

    # Auth middleware (runs first in request phase)
    app.add_middleware(AuthMiddleware)

    # Include routers
    app.include_router(health.router, tags=["health"])
    app.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
    app.include_router(cases.router, prefix="/cases", tags=["cases"])
    app.include_router(approvals.router, prefix="/cases", tags=["approvals"])
    app.include_router(audit.router, prefix="/cases", tags=["audit"])
    app.include_router(metrics.router, tags=["metrics"])

    # Exception handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={
                "error": "bad_request",
                "message": str(exc),
                "request_id": get_request_id(),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        error_type = "http_error"
        if exc.status_code == 404:
            error_type = "not_found"
        elif exc.status_code == 422:
            error_type = "validation_error"
        elif exc.status_code == 401:
            error_type = "unauthorized"
        elif exc.status_code == 403:
            error_type = "forbidden"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": error_type,
                "message": exc.detail,
                "request_id": get_request_id(),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "Request validation failed",
                "request_id": get_request_id(),
                "details": [
                    {"field": ".".join(str(x) for x in e["loc"]), "message": e["msg"], "value": e.get("input")}
                    for e in exc.errors()
                ],
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger = logging.getLogger("apx.api.errors")
        logger.error(
            "unhandled_exception",
            extra={"metadata": {"path": request.url.path, "error": str(exc)}}
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "request_id": get_request_id(),
            },
        )

    return app