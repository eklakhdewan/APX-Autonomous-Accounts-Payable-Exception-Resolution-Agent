from __future__ import annotations

import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from contextlib import contextmanager


class MetricType(str, Enum):
    """Types of metrics supported."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricValue:
    """A single metric measurement."""
    name: str
    value: float
    metric_type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MetricsCollector:
    """
    Thread-safe metrics collector with support for counters, gauges, histograms, and timers.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timers: Dict[str, List[float]] = defaultdict(list)
        self._labels: Dict[str, Dict[str, str]] = {}

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a unique key for a metric with labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment a counter metric."""
        with self._lock:
            key = self._make_key(name, labels)
            self._counters[key] += value
            if labels:
                self._labels[key] = labels

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set a gauge metric to a specific value."""
        with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value
            if labels:
                self._labels[key] = labels

    def record_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a value in a histogram."""
        with self._lock:
            key = self._make_key(name, labels)
            self._histograms[key].append(value)
            if labels:
                self._labels[key] = labels

    def record_timer(
        self,
        name: str,
        duration_ms: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a timer duration in milliseconds."""
        with self._lock:
            key = self._make_key(name, labels)
            self._timers[key].append(duration_ms)
            if labels:
                self._labels[key] = labels

    @contextmanager
    def timer(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager for timing operations."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self.record_timer(name, duration_ms, labels)

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value."""
        with self._lock:
            key = self._make_key(name, labels)
            return self._counters.get(key, 0.0)

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get current gauge value."""
        with self._lock:
            key = self._make_key(name, labels)
            return self._gauges.get(key)

    def get_histogram_stats(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """Get histogram statistics (count, sum, min, max, avg)."""
        with self._lock:
            key = self._make_key(name, labels)
            values = self._histograms.get(key, [])
            if not values:
                return {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}
            return {
                "count": len(values),
                "sum": sum(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
            }

    def get_timer_stats(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """Get timer statistics (count, sum, min, max, avg in ms)."""
        with self._lock:
            key = self._make_key(name, labels)
            values = self._timers.get(key, [])
            if not values:
                return {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}
            return {
                "count": len(values),
                "sum": sum(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
            }

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: self.get_histogram_stats(k.replace("{", "").replace("}", "").split("{")[0],
                                            self._labels.get(k))
                    for k in self._histograms
                },
                "timers": {
                    k: self.get_timer_stats(k.replace("{", "").replace("}", "").split("{")[0],
                                            self._labels.get(k))
                    for k in self._timers
                },
            }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
            self._labels.clear()


# Pre-defined metric names for APX
class APXMetrics:
    """Standard metric names used across APX."""

    # Latency metrics
    PHASE1_VALIDATION_LATENCY = "apx.phase1.validation.latency_ms"
    PHASE2_RETRIEVAL_LATENCY = "apx.phase2.retrieval.latency_ms"
    PHASE3_INVESTIGATION_LATENCY = "apx.phase3.investigation.latency_ms"
    PHASE4_DECISION_LATENCY = "apx.phase4.decision.latency_ms"
    PHASE4_ACTION_LATENCY = "apx.phase4.action.latency_ms"
    PIPELINE_TOTAL_LATENCY = "apx.pipeline.total.latency_ms"

    # Execution metrics
    INVOICES_PROCESSED = "apx.invoices.processed"
    EXCEPTIONS_DETECTED = "apx.exceptions.detected"
    ACTIONS_EXECUTED = "apx.actions.executed"
    ACTIONS_FAILED = "apx.actions.failed"

    # Escalation/Automation metrics
    ESCALATION_COUNT = "apx.escalation.count"
    AUTOMATION_COUNT = "apx.automation.count"
    APPROVAL_REQUIRED = "apx.approval.required"
    UNAUTHORIZED_ACTION_RATE = "apx.unauthorized_action_rate"

    # Accuracy metrics
    DETECTION_PRECISION = "apx.detection.precision"
    DETECTION_RECALL = "apx.detection.recall"
    DETECTION_F1 = "apx.detection.f1"
    DECISION_ACCURACY = "apx.decision.accuracy"
    RETRIEVAL_RECALL_AT_5 = "apx.retrieval.recall_at_5"
    RETRIEVAL_RECALL_AT_10 = "apx.retrieval.recall_at_10"
    RETRIEVAL_MRR = "apx.retrieval.mrr"
    RETRIEVAL_NDCG_AT_10 = "apx.retrieval.ndcg_at_10"

    # Token/Cost metrics (for LLM phases)
    TOKEN_COUNT = "apx.llm.tokens"
    ESTIMATED_COST = "apx.llm.cost_usd"

    @classmethod
    def all_metric_names(cls) -> List[str]:
        return [v for k, v in cls.__dict__.items() if not k.startswith("_") and isinstance(v, str)]


# Global metrics collector
_metrics_collector: Optional[MetricsCollector] = None
_metrics_lock = threading.Lock()


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    with _metrics_lock:
        if _metrics_collector is None:
            _metrics_collector = MetricsCollector()
        return _metrics_collector


def set_metrics_collector(collector: MetricsCollector) -> None:
    """Set the global metrics collector (for testing)."""
    global _metrics_collector
    with _metrics_lock:
        _metrics_collector = collector


def reset_metrics_collector() -> None:
    """Reset the global metrics collector."""
    global _metrics_collector
    with _metrics_lock:
        if _metrics_collector:
            _metrics_collector.reset()
        _metrics_collector = None