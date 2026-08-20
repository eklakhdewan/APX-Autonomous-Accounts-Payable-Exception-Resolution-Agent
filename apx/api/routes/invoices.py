from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from apx.api.schemas import (
    InvoiceRequest,
    InvoiceResponse,
    InvoiceSubmitResponse,
    ProcessResponse,
    ValidationErrorResponse,
    ErrorResponse,
)
from apx.api.schemas import InvoiceLineResponse
from apx.application.services import get_invoice_service
from apx.api.middleware import get_current_role, get_request_id
from apx.persistence import CaseRepository
from apx.persistence.database import get_session_factory

router = APIRouter()


@router.post(
    "",
    response_model=InvoiceSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ValidationErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def submit_invoice(
    request: Request,
    invoice_request: InvoiceRequest,
    idempotency_key: Optional[str] = Query(None, alias="idempotency_key"),
):
    """Submit an invoice for processing."""
    # Check idempotency
    factory = get_session_factory()
    with factory() as session:
        from apx.persistence.models import CaseORM
        from sqlalchemy import select
        existing = session.execute(
            select(CaseORM).where(CaseORM.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "invoice_id": existing.invoice_id,
                    "case_id": str(existing.case_id),
                    "status": "already_exists",
                    "message": f"Invoice already processed with idempotency key {idempotency_key}",
                },
            )

    service = get_invoice_service()

    try:
        # Convert request to domain invoice
        invoice = service._request_to_invoice(invoice_request)
        result = service.submit_invoice(invoice, idempotency_key)
        return InvoiceSubmitResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def get_invoice(
    invoice_id: str,
    request: Request,
):
    """Get invoice by ID with case status."""
    service = get_invoice_service()
    result = service.get_invoice(invoice_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found",
        )
    return InvoiceResponse(**result)


@router.post(
    "/{invoice_id}/process",
    response_model=ProcessResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def process_invoice(
    invoice_id: str,
    request: Request,
    idempotency_key: Optional[str] = Query(None, alias="idempotency_key"),
):
    """Process an invoice through the full APX pipeline."""
    service = get_invoice_service()

    try:
        result = service.process_invoice(invoice_id, idempotency_key)
        return ProcessResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}",
        )