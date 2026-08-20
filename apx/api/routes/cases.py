from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from apx.api.schemas import CaseResponse, ErrorResponse
from apx.application.services import get_case_service
from apx.api.middleware import get_current_role, get_request_id

router = APIRouter()


@router.get(
    "/{case_id}",
    response_model=CaseResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def get_case(
    case_id: str,
    request: Request,
):
    """Get case by ID."""
    service = get_case_service()
    result = service.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Case {case_id} not found",
        )
    return CaseResponse(**result)


@router.get(
    "",
    response_model=list[CaseResponse],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def list_cases(
    request: Request,
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List cases with optional filtering."""
    service = get_case_service()
    cases = service.list_cases(status=status, limit=limit, offset=offset)
    return [CaseResponse(**c) for c in cases]