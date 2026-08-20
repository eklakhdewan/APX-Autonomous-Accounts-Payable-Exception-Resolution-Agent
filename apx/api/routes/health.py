from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from apx.api.schemas import HealthResponse, ReadinessResponse
from apx.persistence import get_session_factory

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Basic health check endpoint."""
    from apx.api.config import get_api_settings
    settings = get_api_settings()
    return HealthResponse(
        status="ok",
        version=settings.version,
    )


@router.get("/ready", response_model=ReadinessResponse, tags=["health"])
async def readiness_check(request: Request):
    """Readiness check - verifies dependencies are available."""
    from apx.api.config import get_api_settings
    settings = get_api_settings()

    checks = {}

    # Check database connectivity
    try:
        factory = get_session_factory()
        with factory() as session:
            session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # Check if core components can be imported/initialized
    try:
        from apx.intelligence.validator import InvoiceValidator
        _ = InvoiceValidator()
        checks["validator"] = True
    except Exception:
        checks["validator"] = False

    try:
        from apx.evidence.engine import HybridContextEngine
        _ = HybridContextEngine()
        checks["evidence_engine"] = True
    except Exception:
        checks["evidence_engine"] = False

    ready = all(checks.values())

    return ReadinessResponse(
        ready=ready,
        checks=checks,
        version=settings.version,
    )