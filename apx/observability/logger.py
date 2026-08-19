from __future__ import annotations

import json
import logging
import sys
import threading
from datetime import datetime
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field, asdict
from contextvars import ContextVar
from contextlib import contextmanager


@dataclass
class LogEntry:
    """Structured log entry for APX."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    run_id: Optional[str] = None
    invoice_id: Optional[str] = None
    phase: Optional[str] = None
    component: Optional[str] = None
    event: str = ""
    status: str = "info"
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self), default=str)


class StructuredLogger:
    """
    Structured JSON logger for APX with contextual fields.
    """

    def __init__(
        self,
        name: str = "apx",
        level: int = logging.INFO,
        output_stream = None,
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.propagate = False

        # Clear existing handlers
        self.logger.handlers.clear()

        # Create handler
        handler = logging.StreamHandler(output_stream or sys.stdout)
        handler.setLevel(level)

        # Use JSON formatter
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # Context variables for correlation
        self._run_id: ContextVar[Optional[str]] = ContextVar("run_id", default=None)
        self._invoice_id: ContextVar[Optional[str]] = ContextVar("invoice_id", default=None)
        self._phase: ContextVar[Optional[str]] = ContextVar("phase", default=None)
        self._component: ContextVar[Optional[str]] = ContextVar("component", default=None)

    def _get_context(self) -> Dict[str, Optional[str]]:
        """Get current context values."""
        return {
            "run_id": self._run_id.get(),
            "invoice_id": self._invoice_id.get(),
            "phase": self._phase.get(),
            "component": self._component.get(),
        }

    def set_context(
        self,
        run_id: Optional[str] = None,
        invoice_id: Optional[str] = None,
        phase: Optional[str] = None,
        component: Optional[str] = None,
    ) -> None:
        """Set context variables for subsequent log entries."""
        self._run_id.set(run_id)
        self._invoice_id.set(invoice_id)
        self._phase.set(phase)
        self._component.set(component)

    def clear_context(self) -> None:
        """Clear all context variables."""
        self._run_id.set(None)
        self._invoice_id.set(None)
        self._phase.set(None)
        self._component.set(None)

    @contextmanager
    def context(
        self,
        run_id: Optional[str] = None,
        invoice_id: Optional[str] = None,
        phase: Optional[str] = None,
        component: Optional[str] = None,
    ):
        """Context manager for temporary context."""
        old_context = self._get_context()
        self.set_context(run_id, invoice_id, phase, component)
        try:
            yield
        finally:
            self.set_context(
                old_context.get("run_id"),
                old_context.get("invoice_id"),
                old_context.get("phase"),
                old_context.get("component"),
            )

    def _log(
        self,
        level: int,
        event: str,
        status: str = "info",
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Internal log method."""
        context = self._get_context()
        entry = LogEntry(
            run_id=context.get("run_id"),
            invoice_id=context.get("invoice_id"),
            phase=context.get("phase"),
            component=context.get("component"),
            event=event,
            status=status,
            duration_ms=duration_ms,
            metadata={**metadata, **kwargs} if metadata else kwargs,
            error=error,
        )
        self.logger.log(level, entry.to_json())

    def debug(self, event: str, **kwargs) -> None:
        self._log(logging.DEBUG, event, status="debug", **kwargs)

    def info(self, event: str, **kwargs) -> None:
        self._log(logging.INFO, event, status="info", **kwargs)

    def warning(self, event: str, **kwargs) -> None:
        self._log(logging.WARNING, event, status="warning", **kwargs)

    def error(self, event: str, error: Optional[str] = None, **kwargs) -> None:
        self._log(logging.ERROR, event, status="error", error=error, **kwargs)

    def critical(self, event: str, error: Optional[str] = None, **kwargs) -> None:
        self._log(logging.CRITICAL, event, status="critical", error=error, **kwargs)

    def log_phase_start(
        self,
        phase: str,
        component: str,
        invoice_id: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log phase start event."""
        with self.context(run_id=run_id, invoice_id=invoice_id, phase=phase, component=component):
            self.info(f"{phase}.start", metadata=metadata)

    def log_phase_end(
        self,
        phase: str,
        component: str,
        status: str = "success",
        duration_ms: Optional[float] = None,
        invoice_id: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log phase end event."""
        with self.context(run_id=run_id, invoice_id=invoice_id, phase=phase, component=component):
            self._log(
                logging.INFO if status == "success" else logging.ERROR,
                f"{phase}.end",
                status=status,
                duration_ms=duration_ms,
                metadata=metadata,
                error=error,
            )

    def log_exception_detected(
        self,
        exception_code: str,
        severity: str,
        invoice_id: str,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log exception detection event."""
        with self.context(run_id=run_id, invoice_id=invoice_id, phase="phase1", component="validator"):
            self.info(
                "exception.detected",
                metadata={
                    "exception_code": exception_code,
                    "severity": severity,
                    **(metadata or {}),
                },
            )

    def log_action_executed(
        self,
        action_type: str,
        success: bool,
        invoice_id: str,
        run_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log action execution event."""
        with self.context(run_id=run_id, invoice_id=invoice_id, phase="phase4", component="action_executor"):
            self._log(
                logging.INFO if success else logging.ERROR,
                "action.executed",
                status="success" if success else "error",
                duration_ms=duration_ms,
                metadata={
                    "action_type": action_type,
                    **(metadata or {}),
                },
                error=error,
            )


# Global logger instance
_logger: Dict[str, StructuredLogger] = {}
_logger_lock = threading.Lock()


def get_logger(
    name: str = "apx",
    level: int = logging.INFO,
    output_stream = None,
) -> StructuredLogger:
    """Get or create the global structured logger."""
    global _logger
    with _logger_lock:
        if name not in _logger:
            _logger[name] = StructuredLogger(name=name, level=level, output_stream=output_stream)
        return _logger[name]


def set_logger(logger: StructuredLogger, name: str = "apx") -> None:
    """Set the global logger (for testing)."""
    global _logger
    with _logger_lock:
        _logger[name] = logger


def reset_logger(name: str = "apx") -> None:
    """Reset the global logger."""
    global _logger
    with _logger_lock:
        if name in _logger:
            del _logger[name]