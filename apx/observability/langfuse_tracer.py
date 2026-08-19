from __future__ import annotations

import os
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Dict, List
from contextvars import ContextVar


class TraceBackend(str, Enum):
    """Available tracing backends."""
    LANGFUSE = "langfuse"
    NOOP = "noop"


@dataclass
class TraceSpan:
    """Represents a single trace span."""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    name: str
    component: str
    phase: str
    invoice_id: Optional[str] = None
    run_id: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    input_metadata: Dict[str, Any] = field(default_factory=dict)
    output_metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "in_progress"
    error: Optional[str] = None

    def finish(self, status: str = "success", error: Optional[str] = None, output_metadata: Optional[Dict[str, Any]] = None) -> None:
        self.end_time = datetime.utcnow()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status = status
        self.error = error
        if output_metadata:
            self.output_metadata = output_metadata


class TracerBackend(ABC):
    """Abstract base class for tracing backends."""

    @abstractmethod
    def start_span(
        self,
        name: str,
        component: str,
        phase: str,
        invoice_id: Optional[str] = None,
        run_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        input_metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        pass

    @abstractmethod
    def end_span(self, span: TraceSpan) -> None:
        pass

    @abstractmethod
    def flush(self) -> None:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass


class NoOpTracer(TracerBackend):
    """No-op tracer for testing and offline development."""

    def __init__(self):
        self._spans: List[TraceSpan] = []

    def start_span(
        self,
        name: str,
        component: str,
        phase: str,
        invoice_id: Optional[str] = None,
        run_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        input_metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        span = TraceSpan(
            span_id=str(uuid.uuid4()),
            trace_id=run_id or str(uuid.uuid4()),
            parent_span_id=parent_span_id,
            name=name,
            component=component,
            phase=phase,
            invoice_id=invoice_id,
            run_id=run_id,
            input_metadata=input_metadata or {},
        )
        self._spans.append(span)
        return span

    def end_span(self, span: TraceSpan) -> None:
        pass

    def flush(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def get_spans(self) -> List[TraceSpan]:
        return self._spans.copy()


class LangfuseTracer:
    """
    Main tracer abstraction that supports Langfuse and no-op backends.
    """

    def __init__(
        self,
        backend: TraceBackend = TraceBackend.NOOP,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
        project_name: str = "apx",
    ):
        self.backend_type = backend
        self.project_name = project_name
        self._backend: TracerBackend
        self._langfuse_client = None
        self._active_spans: Dict[str, TraceSpan] = {}
        self._trace_context: ContextVar[Optional[str]] = ContextVar("trace_context", default=None)

        if backend == TraceBackend.LANGFUSE:
            self._init_langfuse(public_key, secret_key, host)
        else:
            self._backend = NoOpTracer()

    def _init_langfuse(self, public_key: Optional[str], secret_key: Optional[str], host: Optional[str]) -> None:
        """Initialize Langfuse client if credentials are available."""
        try:
            from langfuse import Langfuse

            public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
            secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
            host = host or os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

            if not public_key or not secret_key:
                raise ValueError("Langfuse credentials not provided")

            self._langfuse_client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
            self._backend = self._LangfuseBackend(self._langfuse_client)
        except (ImportError, ValueError):
            # Fallback to no-op if Langfuse not available or credentials missing
            self._backend = NoOpTracer()
            self.backend_type = TraceBackend.NOOP

    class _LangfuseBackend(TracerBackend):
        """Langfuse-specific backend implementation."""

        def __init__(self, client):
            self.client = client
            self._spans: Dict[str, Any] = {}

        def start_span(
            self,
            name: str,
            component: str,
            phase: str,
            invoice_id: Optional[str] = None,
            run_id: Optional[str] = None,
            parent_span_id: Optional[str] = None,
            input_metadata: Optional[Dict[str, Any]] = None,
        ) -> TraceSpan:
            trace_id = run_id or str(uuid.uuid4())
            span_id = str(uuid.uuid4())

            # Create Langfuse span
            langfuse_span = self.client.span(
                id=span_id,
                trace_id=trace_id,
                name=name,
                metadata={
                    "component": component,
                    "phase": phase,
                    "invoice_id": invoice_id,
                    **(input_metadata or {}),
                },
            )

            span = TraceSpan(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                name=name,
                component=component,
                phase=phase,
                invoice_id=invoice_id,
                run_id=run_id,
                input_metadata=input_metadata or {},
            )
            self._spans[span_id] = langfuse_span
            return span

        def end_span(self, span: TraceSpan) -> None:
            langfuse_span = self._spans.get(span.span_id)
            if langfuse_span:
                langfuse_span.end(
                    output=span.output_metadata,
                    status_message=span.error if span.status == "error" else None,
                )

        def flush(self) -> None:
            self.client.flush()

        def shutdown(self) -> None:
            self.client.shutdown()

    def start_span(
        self,
        name: str,
        component: str,
        phase: str,
        invoice_id: Optional[str] = None,
        run_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        input_metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        """Start a new trace span."""
        span = self._backend.start_span(
            name=name,
            component=component,
            phase=phase,
            invoice_id=invoice_id,
            run_id=run_id,
            parent_span_id=parent_span_id,
            input_metadata=input_metadata,
        )
        self._active_spans[span.span_id] = span
        return span

    def end_span(
        self,
        span: TraceSpan,
        status: str = "success",
        error: Optional[str] = None,
        output_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """End a trace span."""
        span.finish(status=status, error=error, output_metadata=output_metadata)
        self._backend.end_span(span)
        self._active_spans.pop(span.span_id, None)

    @contextmanager
    def trace(
        self,
        name: str,
        component: str,
        phase: str,
        invoice_id: Optional[str] = None,
        run_id: Optional[str] = None,
        input_metadata: Optional[Dict[str, Any]] = None,
    ):
        """Context manager for tracing a block of code."""
        span = self.start_span(
            name=name,
            component=component,
            phase=phase,
            invoice_id=invoice_id,
            run_id=run_id,
            input_metadata=input_metadata,
        )
        try:
            yield span
            self.end_span(span, status="success")
        except Exception as e:
            self.end_span(span, status="error", error=str(e))
            raise

    def flush(self) -> None:
        self._backend.flush()

    def shutdown(self) -> None:
        self._backend.shutdown()

    def get_spans(self) -> List[TraceSpan]:
        """Get all recorded spans (for testing)."""
        if isinstance(self._backend, NoOpTracer):
            return self._backend.get_spans()
        return list(self._active_spans.values())

    def set_trace_context(self, run_id: str) -> None:
        """Set the current trace context."""
        self._trace_context.set(run_id)

    def get_trace_context(self) -> Optional[str]:
        """Get the current trace context."""
        return self._trace_context.get()


# Global tracer instance
_tracer: Optional[LangfuseTracer] = None


def get_tracer(
    backend: TraceBackend = TraceBackend.NOOP,
    **kwargs
) -> LangfuseTracer:
    """Get or create the global tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = LangfuseTracer(backend=backend, **kwargs)
    return _tracer


def set_tracer(tracer: LangfuseTracer) -> None:
    """Set the global tracer instance (for testing)."""
    global _tracer
    _tracer = tracer


def reset_tracer() -> None:
    """Reset the global tracer instance."""
    global _tracer
    if _tracer:
        _tracer.shutdown()
    _tracer = None