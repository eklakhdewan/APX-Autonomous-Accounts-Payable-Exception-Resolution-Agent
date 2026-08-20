from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from apx.api.config import get_api_settings
from apx.observability.logger import get_logger

# Context variables for request/correlation IDs
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID."""
    return request_id_var.get()


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return correlation_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the current request ID."""
    request_id_var.set(request_id)


def set_correlation_id(correlation_id: str) -> None:
    """Set the current correlation ID."""
    correlation_id_var.set(correlation_id)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID and correlation ID to requests."""

    def __init__(self, app):
        super().__init__(app)
        self.settings = get_api_settings()
        self.logger = get_logger("apx.api.middleware.request_id")

    async def dispatch(self, request: Request, call_next):
        settings = self.settings

        # Get or generate request ID
        request_id = request.headers.get(settings.request_id_header)
        if not request_id:
            request_id = str(uuid.uuid4())

        # Get or generate correlation ID
        correlation_id = request.headers.get(settings.correlation_id_header)
        if not correlation_id:
            correlation_id = request_id

        # Set context variables
        set_request_id(request_id)
        set_correlation_id(correlation_id)

        # Add to request state for downstream access
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        # Log request start
        if settings.log_requests:
            self.logger.info(
                "request.start",
                metadata={
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.query_params),
                },
            )

        start_time = time.time()

        try:
            response = await call_next(request)

            # Add headers to response
            response.headers[settings.request_id_header] = request_id
            response.headers[settings.correlation_id_header] = correlation_id

            # Log request completion
            if settings.log_requests:
                duration_ms = (time.time() - start_time) * 1000
                self.logger.info(
                    "request.end",
                    metadata={
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    },
                )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            if settings.log_requests:
                self.logger.error(
                    "request.error",
                    error=str(e),
                    metadata={
                        "duration_ms": duration_ms,
                    },
                )
            raise


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for API key authentication."""

    def __init__(self, app):
        super().__init__(app)
        self.settings = get_api_settings()
        self.logger = get_logger("apx.api.middleware.auth")

    async def dispatch(self, request: Request, call_next):
        settings = self.settings
        auth_settings = settings.auth

        # Skip auth for health/readiness endpoints
        if request.url.path in ["/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # Check for API key
        api_key = request.headers.get(auth_settings.api_key_header)
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "API key required",
                    "request_id": get_request_id(),
                },
            )

        # Validate API key
        valid_keys = auth_settings.get_keys_with_roles()
        if api_key not in valid_keys:
            self.logger.warning(
                "auth.invalid_key",
                metadata={"key_prefix": api_key[:8] + "..."},
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Invalid API key",
                    "request_id": get_request_id(),
                },
            )

        # Store role in request state
        role = valid_keys[api_key]
        request.state.api_key = api_key
        request.state.role = role

        return await call_next(request)


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """Middleware for role-based authorization."""

    def __init__(self, app):
        super().__init__(app)
        self.settings = get_api_settings()

    async def dispatch(self, request: Request, call_next):
        # Skip auth for health/readiness endpoints
        if request.url.path in ["/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # Check if role is set (should be set by AuthMiddleware)
        role = getattr(request.state, "role", None)
        if not role:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Authentication required",
                    "request_id": get_request_id(),
                },
            )

        # Define role permissions
        path = request.url.path
        method = request.method

        # Reader: GET endpoints only
        if role == "reader":
            if method != "GET":
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "forbidden",
                        "message": "Reader role only permits GET requests",
                        "request_id": get_request_id(),
                    },
                )

        # Operator: reader + POST /invoices and POST /invoices/{id}/process
        elif role == "operator":
            if method == "POST" and path not in ["/invoices", "/invoices/{invoice_id}/process"]:
                # Need to check if path matches pattern
                if path.startswith("/invoices/") and "/process" not in path:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "forbidden",
                            "message": "Operator role not permitted for this endpoint",
                            "request_id": get_request_id(),
                        },
                    )

        # Approver: reader + POST /cases/{id}/approve, /reject
        elif role == "approver":
            if method == "POST" and not (path.endswith("/approve") or path.endswith("/reject")):
                if not path.startswith("/invoices") and not path.startswith("/cases") and not path.startswith("/health") and not path.startswith("/ready") and not path.startswith("/metrics"):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "forbidden",
                            "message": "Approver role not permitted for this endpoint",
                            "request_id": get_request_id(),
                        },
                    )

        # Admin: all permissions (if we add admin role later)
        # For now, unknown role = denied
        else:
            if role not in ["reader", "operator", "approver"]:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "forbidden",
                        "message": f"Unknown role: {role}",
                        "request_id": get_request_id(),
                    },
                )

        return await call_next(request)


def get_current_role(request: Request) -> str:
    """Get the current user's role from request state."""
    return getattr(request.state, "role", "unknown")


def get_current_api_key(request: Request) -> Optional[str]:
    """Get the current user's API key from request state."""
    return getattr(request.state, "api_key", None)