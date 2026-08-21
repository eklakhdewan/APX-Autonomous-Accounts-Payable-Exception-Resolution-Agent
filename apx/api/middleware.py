from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from apx.api.config import get_api_settings
from apx.observability.logger import get_logger
from apx.observability.metrics import get_metrics_collector, APXMetrics
from apx.observability.redaction import deep_redact, redact_headers

# Context variables for request/correlation IDs
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
traceparent_var: ContextVar[Optional[str]] = ContextVar("traceparent", default=None)
tracestate_var: ContextVar[Optional[str]] = ContextVar("tracestate", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID."""
    return request_id_var.get()


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return correlation_id_var.get()


def get_traceparent() -> Optional[str]:
    """Get the current W3C traceparent header."""
    return traceparent_var.get()


def get_tracestate() -> Optional[str]:
    """Get the current W3C tracestate header."""
    return tracestate_var.get()


def set_request_id(request_id: str) -> None:
    """Set the current request ID."""
    request_id_var.set(request_id)


def set_correlation_id(correlation_id: str) -> None:
    """Set the current correlation ID."""
    correlation_id_var.set(correlation_id)


def set_traceparent(traceparent: str) -> None:
    """Set the current W3C traceparent."""
    traceparent_var.set(traceparent)


def set_tracestate(tracestate: str) -> None:
    """Set the current W3C tracestate."""
    tracestate_var.set(tracestate)


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""
    tokens: float
    last_refill: float
    capacity: int
    refill_rate: float  # tokens per second


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID and correlation ID to requests."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.settings = get_api_settings()
        self.logger = get_logger("apx.api.middleware.request_id")

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        if request.client:
            return request.client.host
        return "unknown"

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

        # W3C Trace Context support
        traceparent = request.headers.get("traceparent")
        if traceparent:
            set_traceparent(traceparent)
        else:
            # Generate a traceparent if not present (version 00, trace-id, parent-id, flags)
            trace_id = correlation_id.replace("-", "")[:32].ljust(32, "0")
            parent_id = request_id.replace("-", "")[:16].ljust(16, "0")
            traceparent = f"00-{trace_id}-{parent_id}-01"
            set_traceparent(traceparent)

        tracestate = request.headers.get("tracestate")
        if tracestate:
            set_tracestate(tracestate)

        # Set context variables
        set_request_id(request_id)
        set_correlation_id(correlation_id)

        # Add to request state for downstream access
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.traceparent = traceparent
        request.state.tracestate = tracestate

        # Log request start
        if settings.log_requests:
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "unknown")
            self.logger.info(
                "request.start",
                metadata={
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.query_params),
                    "request_id": request_id,
                    "correlation_id": correlation_id,
                    "traceparent": traceparent,
                    "tracestate": tracestate,
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                },
            )

        start_time = time.time()

        try:
            response = await call_next(request)

            # Add headers to response
            response.headers[settings.request_id_header] = request_id
            response.headers[settings.correlation_id_header] = correlation_id
            response.headers["traceparent"] = traceparent
            if tracestate:
                response.headers["tracestate"] = tracestate

            # Log request completion
            if settings.log_requests:
                duration_ms = (time.time() - start_time) * 1000
                response_size = sum(len(v) for v in response.headers.values()) + len(str(response.status_code))
                self.logger.info(
                    "request.end",
                    metadata={
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "request_id": request_id,
                        "correlation_id": correlation_id,
                        "traceparent": traceparent,
                        "response_size_bytes": response_size,
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
                        "request_id": request_id,
                        "correlation_id": correlation_id,
                    },
                )
            raise


class APIMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect per-endpoint API metrics."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.collector = get_metrics_collector()
        self.logger = get_logger("apx.api.middleware.metrics")

    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics (replace UUIDs, IDs with placeholders)."""
        import re
        # Replace UUIDs
        path = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "{id}", path)
        # Replace numeric IDs
        path = re.sub(r"/\d+", "/{id}", path)
        # Replace invoice IDs (INV-...)
        path = re.sub(r"/INV-[A-Z0-9-]+", "/{invoice_id}", path)
        return path

    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = self._normalize_path(request.url.path)
        endpoint = f"{method} {path}"

        start_time = time.time()

        try:
            response = await call_next(request)

            duration_ms = (time.time() - start_time) * 1000
            status_code = response.status_code

            # Record metrics
            self.collector.increment_counter(
                APXMetrics.INVOICES_PROCESSED if "invoices" in path else "apx.api.requests.total",
                labels={"endpoint": endpoint, "status": str(status_code)}
            )
            self.collector.record_timer(
                "apx.api.latency_ms",
                duration_ms,
                labels={"endpoint": endpoint}
            )

            # Error metrics
            if status_code >= 400:
                self.collector.increment_counter(
                    "apx.api.errors.total",
                    labels={"endpoint": endpoint, "status": str(status_code)}
                )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.collector.increment_counter(
                "apx.api.errors.total",
                labels={"endpoint": endpoint, "status": "500"}
            )
            self.collector.record_timer(
                "apx.api.latency_ms",
                duration_ms,
                labels={"endpoint": endpoint}
            )
            raise


class RedactionMiddleware(BaseHTTPMiddleware):
    """Middleware to redact sensitive data from request/response logs."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = get_logger("apx.api.middleware.redaction")

    def _get_settings(self):
        """Get current settings (allows dynamic config changes)."""
        return get_api_settings()

    async def dispatch(self, request: Request, call_next):
        settings = self._get_settings()
        # Store original body for potential logging
        request_body = None
        if settings.log_request_body:
            try:
                body = await request.body()
                if body:
                    import json
                    request_body = json.loads(body) if body else None
                    # Re-create request with body for downstream
                    async def receive():
                        return {"type": "http.request", "body": body}
                    request._receive = receive
            except Exception:
                pass

        response = await call_next(request)

        # Log request with redacted body if enabled
        if settings.log_requests and request_body is not None:
            redacted_body = deep_redact(request_body)
            self.logger.info(
                "request.body",
                metadata={
                    "request_id": get_request_id(),
                    "correlation_id": get_correlation_id(),
                    "body": redacted_body,
                },
            )

        # Log response with redacted body if enabled
        if settings.log_response_body:
            # Note: Response body logging would require buffering
            # This is a placeholder for future enhancement
            pass

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory token bucket rate limiting middleware."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.buckets: Dict[str, RateLimitBucket] = {}
        self.logger = get_logger("apx.api.middleware.ratelimit")

    def _get_settings(self):
        """Get current settings (allows dynamic config changes)."""
        return get_api_settings()

    def _get_bucket_key(self, request: Request) -> str:
        """Get rate limit bucket key (by API key or IP)."""
        settings = self._get_settings()
        api_key = request.headers.get(settings.auth.api_key_header)
        if api_key:
            return f"apikey:{api_key[:16]}"
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    def _refill_bucket(self, bucket: RateLimitBucket) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - bucket.last_refill
        new_tokens = elapsed * bucket.refill_rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + new_tokens)
        bucket.last_refill = now

    async def dispatch(self, request: Request, call_next):
        settings = self._get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Skip rate limiting for health/readiness endpoints
        if request.url.path in ["/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        bucket_key = self._get_bucket_key(request)
        now = time.time()

        if bucket_key not in self.buckets:
            capacity = settings.rate_limit_requests_per_minute
            refill_rate = capacity / 60.0  # tokens per second
            self.buckets[bucket_key] = RateLimitBucket(
                tokens=capacity,
                last_refill=now,
                capacity=capacity,
                refill_rate=refill_rate,
            )

        bucket = self.buckets[bucket_key]
        self._refill_bucket(bucket)

        if bucket.tokens < 1:
            self.logger.warning(
                "rate_limit.exceeded",
                metadata={
                    "bucket_key": bucket_key,
                    "request_id": get_request_id(),
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": "Rate limit exceeded. Please try again later.",
                    "request_id": get_request_id(),
                },
                headers={"Retry-After": "60"},
            )

        bucket.tokens -= 1
        return await call_next(request)


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce maximum request size."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = get_logger("apx.api.middleware.request_size")

    def _get_settings(self):
        """Get current settings (allows dynamic config changes)."""
        return get_api_settings()

    async def dispatch(self, request: Request, call_next):
        settings = self._get_settings()
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > settings.max_request_size:
                    self.logger.warning(
                        "request_size.exceeded",
                        metadata={
                            "request_id": get_request_id(),
                            "content_length": size,
                            "max_allowed": settings.max_request_size,
                            "path": request.url.path,
                        },
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "payload_too_large",
                            "message": f"Request body exceeds maximum allowed size of {settings.max_request_size} bytes",
                            "request_id": get_request_id(),
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.settings = get_api_settings()
        self.logger = get_logger("apx.api.middleware.security_headers")

    def _is_https(self, request: Request) -> bool:
        """Check if request is over HTTPS."""
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            return forwarded_proto == "https"
        return request.url.scheme == "https"

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Skip security headers for docs endpoints in development
        if self.settings.debug and request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            return response

        # Content Security Policy - restrictive but allows Swagger UI
        csp_parts = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            "img-src 'self' data: https://fastapi.tiangolo.com",
            "font-src 'self' https://cdn.jsdelivr.net",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_parts)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS Protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS - only for HTTPS
        if self._is_https(request):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Remove server header for security
        if "server" in response.headers:
            del response.headers["server"]

        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for API key authentication."""

    def __init__(self, app: ASGIApp):
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

    def __init__(self, app: ASGIApp):
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
            if method == "POST":
                # Allow only specific endpoints
                allowed_paths = ["/invoices"]
                # Check for /invoices/{id}/process pattern
                is_invoice_process = path.startswith("/invoices/") and path.endswith("/process")
                if path not in allowed_paths and not is_invoice_process:
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

        # Admin: all permissions
        elif role == "admin":
            # Admin can access all endpoints
            pass

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