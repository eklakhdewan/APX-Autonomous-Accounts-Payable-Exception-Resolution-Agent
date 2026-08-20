from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
import logging

from apx.api.schemas import ApprovalResponse, ApproveRequest, RejectRequest, ErrorResponse
from apx.application.services import get_approval_service
from apx.api.middleware import get_current_role, get_request_id
from apx.persistence.sqlite_repos import SQLiteApprovalRepository

router = APIRouter()

logger = logging.getLogger("apx.api.routes.approvals")


@router.get(
    "/{case_id}/approval",
    response_model=ApprovalResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def get_approval(
    case_id: str,
    request: Request,
):
    """Get approval for a case."""
    service = get_approval_service()
    result = service.get_approval(case_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Approval for case {case_id} not found",
        )
    return ApprovalResponse(**result)


@router.post(
    "/{case_id}/approve",
    response_model=ApprovalResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def approve_case(
    case_id: str,
    request: Request,
    approve_request: ApproveRequest,
):
    """Approve a case."""
    service = get_approval_service()
    logger = logging.getLogger("apx.api.routes.approvals")
    logger.info(f"Approving case: {case_id}, type: {type(case_id)}")
    # Check if approval exists first
    from apx.persistence.sqlite_repos import SQLiteApprovalRepository
    from uuid import UUID
    approval_repo = SQLiteApprovalRepository()
    logger.info(f"Looking up approval for case_id: {case_id}")
    approval = None
    try:
        approval = SQLiteApprovalRepository().get_by_case(UUID(case_id))
    except Exception as e:
        logger.error(f"Error looking up approval: {e}")
    logger.info(f"Approval found: {approval is not None}")
    if not approval:
        raise HTTPException(
            status_code=404,
            detail=f"Approval for case {case_id} not found",
        )
    try:
        service = get_approval_service()
        result = service.approve_case(case_id, approve_request.approver_id, approve_request.notes)
        return ApprovalResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post(
    "/{case_id}/reject",
    response_model=ApprovalResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def reject_case(
    case_id: str,
    request: Request,
    reject_request: RejectRequest,
):
    """Reject a case."""
    service = get_approval_service()
    try:
        result = service.reject_case(case_id, reject_request.approver_id, reject_request.notes)
        return ApprovalResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )