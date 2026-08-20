from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import PlainTextResponse

from apx.application.services import get_metrics_service
from apx.api.middleware import get_current_role

router = APIRouter()


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
    },
)
async def get_metrics(request: Request):
    """Get Prometheus-compatible metrics."""
    service = get_metrics_service()
    return service.get_prometheus_metrics()


@router.get(
    "/metrics/json",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
    },
)
async def get_metrics_json(request: Request):
    """Get metrics in JSON format."""
    service = get_metrics_service()
    return service.get_metrics()