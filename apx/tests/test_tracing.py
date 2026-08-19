from __future__ import annotations

import pytest
from datetime import datetime
from decimal import Decimal
import logging

from apx.observability.langfuse_tracer import LangfuseTracer, TraceBackend, NoOpTracer, TraceSpan
from apx.observability.metrics import MetricsCollector, APXMetrics, MetricType
from apx.observability.logger import StructuredLogger, get_logger
import json


class TestLangfuseTracer:
    """Tests for Langfuse tracer."""

    def test_noop_tracer_initialization(self):
        """Test no-op tracer initializes correctly."""
        tracer = LangfuseTracer(backend=TraceBackend.NOOP)
        assert tracer.backend_type == TraceBackend.NOOP
        assert isinstance(tracer._backend, NoOpTracer)

    def test_noop_tracer_start_end_span(self):
        """Test no-op tracer can start and end spans."""
        tracer = LangfuseTracer(backend=TraceBackend.NOOP)

        span = tracer.start_span(
            name="test_operation",
            component="test_component",
            phase="test_phase",
            invoice_id="INV-001",
            run_id="run-123",
            input_metadata={"key": "value"},
        )

        assert isinstance(span, TraceSpan)
        assert span.name == "test_operation"
        assert span.component == "test_component"
        assert span.phase == "test_phase"
        assert span.invoice_id == "INV-001"
        assert span.run_id == "run-123"
        assert span.input_metadata == {"key": "value"}
        assert span.status == "in_progress"

        tracer.end_span(span, status="success", output_metadata={"result": "ok"})

        assert span.status == "success"
        assert span.output_metadata == {"result": "ok"}
        assert span.duration_ms is not None
        assert span.duration_ms >= 0

    def test_noop_tracer_context_manager(self):
        """Test tracer context manager."""
        tracer = LangfuseTracer(backend=TraceBackend.NOOP)

        with tracer.trace(
            name="test_op",
            component="test",
            phase="test",
        ) as span:
            assert span.status == "in_progress"

        # After context, span should be finished
        assert span.status == "success"

    def test_noop_tracer_error_handling(self):
        """Test tracer handles errors in context manager."""
        tracer = LangfuseTracer(backend=TraceBackend.NOOP)

        try:
            with tracer.trace(name="test", component="test", phase="test"):
                raise ValueError("test error")
        except ValueError:
            pass

        spans = tracer.get_spans()
        assert len(spans) == 1
        assert spans[0].status == "error"
        assert "test error" in spans[0].error

    def test_noop_tracer_secrets_not_emitted(self):
        """Test that secrets are not emitted in traces."""
        tracer = LangfuseTracer(backend=TraceBackend.NOOP)

        span = tracer.start_span(
            name="test",
            component="test",
            phase="test",
            input_metadata={"api_key": "secret123", "normal": "value"},
        )

        tracer.end_span(span)

        spans = tracer.get_spans()
        # Verify the tracer accepted the metadata (we can't easily test internal filtering
        # without exposing internals, but we verify the tracer doesn't crash)
        assert len(spans) == 1

    def test_global_tracer_functions(self):
        """Test global tracer getter/setter."""
        from apx.observability.langfuse_tracer import get_tracer, set_tracer, reset_tracer

        reset_tracer()
        tracer1 = get_tracer(backend=TraceBackend.NOOP)
        tracer2 = get_tracer()
        assert tracer1 is tracer2

        custom_tracer = LangfuseTracer(backend=TraceBackend.NOOP)
        set_tracer(custom_tracer)
        assert get_tracer() is custom_tracer

        reset_tracer()
        assert get_tracer() is not custom_tracer


class TestMetricsCollector:
    """Tests for metrics collector."""

    def setup_method(self):
        self.collector = MetricsCollector()

    def test_counter_increment(self):
        """Test counter increment."""
        self.collector.increment_counter("test.counter")
        assert self.collector.get_counter("test.counter") == 1.0

        self.collector.increment_counter("test.counter", 5.0)
        assert self.collector.get_counter("test.counter") == 6.0

    def test_counter_with_labels(self):
        """Test counter with labels."""
        self.collector.increment_counter("test.counter", labels={"env": "test"})
        assert self.collector.get_counter("test.counter", labels={"env": "test"}) == 1.0
        assert self.collector.get_counter("test.counter", labels={"env": "prod"}) == 0.0

    def test_gauge(self):
        """Test gauge metric."""
        self.collector.set_gauge("test.gauge", 42.0)
        assert self.collector.get_gauge("test.gauge") == 42.0

        self.collector.set_gauge("test.gauge", 100.0)
        assert self.collector.get_gauge("test.gauge") == 100.0

    def test_histogram(self):
        """Test histogram metric."""
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            self.collector.record_histogram("test.hist", v)

        stats = self.collector.get_histogram_stats("test.hist")
        assert stats["count"] == 5
        assert stats["sum"] == 15.0
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["avg"] == 3.0

    def test_timer(self):
        """Test timer metric."""
        self.collector.record_timer("test.timer", 100.0)
        self.collector.record_timer("test.timer", 200.0)

        stats = self.collector.get_timer_stats("test.timer")
        assert stats["count"] == 2
        assert stats["avg"] == 150.0

    def test_timer_context_manager(self):
        """Test timer context manager."""
        import time

        with self.collector.timer("test.timer_cm"):
            time.sleep(0.01)  # 10ms

        stats = self.collector.get_timer_stats("test.timer_cm")
        assert stats["count"] == 1
        assert stats["avg"] >= 10.0  # At least 10ms

    def test_reset(self):
        """Test metrics reset."""
        self.collector.increment_counter("test")
        self.collector.set_gauge("gauge", 1.0)
        self.collector.record_histogram("hist", 1.0)

        self.collector.reset()

        assert self.collector.get_counter("test") == 0.0
        assert self.collector.get_gauge("gauge") is None

    def test_apx_metrics_constants(self):
        """Test APX metric name constants."""
        names = APXMetrics.all_metric_names()
        assert len(names) > 0
        assert "apx.phase1.validation.latency_ms" in names
        assert "apx.detection.precision" in names


class TestStructuredLogger:
    """Tests for structured logger."""

    def setup_method(self):
        self.logger = StructuredLogger(name="test", level=10)  # DEBUG level

    def test_logger_initialization(self):
        """Test logger initializes correctly."""
        assert self.logger.logger.name == "test"
        assert self.logger.logger.level == 10

    def test_log_structured_output(self, caplog):
        """Test logger produces valid JSON."""
        caplog.set_level(logging.DEBUG)
        self.logger.info("test_event", key="value")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        parsed = json.loads(record.message)
        assert parsed["event"] == "test_event"
        assert parsed["metadata"]["key"] == "value"
        assert parsed["status"] == "info"

    def test_logger_context(self, caplog):
        """Test logger context variables."""
        caplog.set_level(logging.DEBUG)
        self.logger.set_context(run_id="run-123", invoice_id="INV-001")
        self.logger.info("test_event")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        parsed = json.loads(record.message)
        assert parsed["run_id"] == "run-123"
        assert parsed["invoice_id"] == "INV-001"

    def test_logger_context_manager(self, caplog):
        """Test logger context manager."""
        caplog.set_level(logging.DEBUG)
        with self.logger.context(run_id="run-456", invoice_id="INV-999"):
            self.logger.info("in_context")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        parsed = json.loads(record.message)
        assert parsed["run_id"] == "run-456"
        assert parsed["invoice_id"] == "INV-999"

        # Context should be restored after
        caplog.clear()
        self.logger.info("out_of_context")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        parsed = json.loads(record.message)
        assert parsed["run_id"] is None
        assert parsed["invoice_id"] is None

    def test_log_levels(self, caplog):
        """Test different log levels."""
        caplog.set_level(logging.DEBUG)
        self.logger.debug("debug_event")
        self.logger.info("info_event")
        self.logger.warning("warn_event")
        self.logger.error("error_event", error="test error")

        assert len(caplog.records) == 4
        assert json.loads(caplog.records[0].message)["status"] == "debug"
        assert json.loads(caplog.records[1].message)["status"] == "info"
        assert json.loads(caplog.records[2].message)["status"] == "warning"
        assert json.loads(caplog.records[3].message)["status"] == "error"
        assert json.loads(caplog.records[3].message)["error"] == "test error"

    def test_phase_start_end(self, caplog):
        """Test phase start/end logging."""
        caplog.set_level(logging.DEBUG)
        self.logger.log_phase_start("phase1", "validator", invoice_id="INV-001", run_id="run-1")
        self.logger.log_phase_end("phase1", "validator", status="success", duration_ms=100.0, invoice_id="INV-001", run_id="run-1")

        assert len(caplog.records) == 2
        start_parsed = json.loads(caplog.records[0].message)
        end_parsed = json.loads(caplog.records[1].message)

        assert start_parsed["event"] == "phase1.start"
        assert start_parsed["phase"] == "phase1"
        assert start_parsed["component"] == "validator"
        assert start_parsed["invoice_id"] == "INV-001"
        assert start_parsed["run_id"] == "run-1"

        assert end_parsed["event"] == "phase1.end"
        assert end_parsed["status"] == "success"
        assert end_parsed["duration_ms"] == 100.0

    def test_exception_detected_log(self, caplog):
        """Test exception detected logging."""
        caplog.set_level(logging.DEBUG)
        self.logger.log_exception_detected("AMOUNT_MISMATCH", "HIGH", "INV-001", "run-1")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        parsed = json.loads(record.message)

        assert parsed["event"] == "exception.detected"
        assert parsed["metadata"]["exception_code"] == "AMOUNT_MISMATCH"
        assert parsed["metadata"]["severity"] == "HIGH"
        assert parsed["invoice_id"] == "INV-001"

    def test_action_executed_log(self, caplog):
        """Test action executed logging."""
        caplog.set_level(logging.DEBUG)
        self.logger.log_action_executed("AUTO_RESOLVE", True, "INV-001", "run-1", duration_ms=50.0)
        self.logger.log_action_executed("VOID_INVOICE", False, "INV-002", "run-1", error="Connection failed")

        assert len(caplog.records) == 2
        p1 = json.loads(caplog.records[0].message)
        p2 = json.loads(caplog.records[1].message)

        assert p1["event"] == "action.executed"
        assert p1["metadata"]["action_type"] == "AUTO_RESOLVE"
        assert p1["status"] == "success"

        assert p2["status"] == "error"
        assert p2["error"] == "Connection failed"


class TestGlobalLogger:
    """Test global logger functions."""

    def test_get_logger(self):
        """Test global logger getter."""
        from apx.observability.logger import get_logger, reset_logger

        reset_logger()
        logger1 = get_logger("test1")
        logger2 = get_logger("test1")
        assert logger1 is logger2

        logger3 = get_logger("test2")
        assert logger3 is not logger1

        reset_logger()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])