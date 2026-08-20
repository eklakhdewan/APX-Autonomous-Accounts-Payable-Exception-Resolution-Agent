from __future__ import annotations

import logging
from typing import Any

from apx.observability.metrics import get_metrics_collector, APXMetrics


class MetricsService:
    """Service for exposing metrics via the API."""

    def __init__(self):
        self.logger = logging.getLogger("apx.application.services.metrics")

    def get_metrics(self) -> dict[str, Any]:
        """Get all metrics for Prometheus exposition."""
        collector = get_metrics_collector()
        return collector.get_all_metrics()

    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus text format."""
        collector = get_metrics_collector()
        all_metrics = collector.get_all_metrics()

        lines = []
        # Counters
        for name, value in all_metrics.get("counters", {}).items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")

        # Gauges
        for name, value in all_metrics.get("gauges", {}).items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")

        # Histograms
        for name, stats in all_metrics.get("histograms", {}).items():
            lines.append(f"# TYPE {name} histogram")
            lines.append(f"{name}_count {stats.get('count', 0)}")
            lines.append(f"{name}_sum {stats.get('sum', 0)}")
            lines.append(f"{name}_min {stats.get('min', 0)}")
            lines.append(f"{name}_max {stats.get('max', 0)}")
            lines.append(f"{name}_avg {stats.get('avg', 0)}")

        # Timers
        for name, stats in all_metrics.get("timers", {}).items():
            lines.append(f"# TYPE {name} summary")
            lines.append(f"{name}_count {stats.get('count', 0)}")
            lines.append(f"{name}_sum {stats.get('sum', 0)}")
            lines.append(f"{name}_min {stats.get('min', 0)}")
            lines.append(f"{name}_max {stats.get('max', 0)}")
            lines.append(f"{name}_avg {stats.get('avg', 0)}")

        return "\n".join(lines)