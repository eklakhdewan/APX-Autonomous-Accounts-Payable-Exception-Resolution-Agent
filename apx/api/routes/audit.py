from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from apx.api.schemas import AuditEventResponse, ErrorResponse
from apx.application.services import get_audit_service
from apx.api.middleware import get_current_role, get_request_id

router = APIRouter()


@router.get(
    "/{case_id}/audit",
    response_model=list[AuditEventResponse],
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def get_case_audit(
    case_id: str,
    request: Request,
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    """Get audit events for a case."""
    service = get_audit_service()
    events = service.get_audit_events(case_id, limit=limit, offset=offset)
    return [AuditEventResponse(**e) for e in events]


@router.get(
    "/audit",
    response_model=list[AuditEventResponse],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def list_audit_events(
    request: Request,
    event_type: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    """List all audit events with optional filtering."""
    service = get_audit_service()
    if event_type:
        events = service.get_audit_events_by_type(event_type, limit=limit, offset=offset)
    else:
        events = service.list_all_audit_events(limit=limit, offset=offset)
    return [AuditEventResponse(**e) for e in events]