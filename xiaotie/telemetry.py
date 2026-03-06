from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict

try:
    from prometheus_client import Counter, Gauge, Histogram

    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False
    Counter = None
    Gauge = None
    Histogram = None

if _PROM_AVAILABLE:
    _RUNS_TOTAL = Counter("xiaotie_runs_total", "Total runs", ["status"])
    _LLM_CALLS_TOTAL = Counter(
        "xiaotie_llm_calls_total",
        "Total llm calls",
        ["provider", "model", "success"],
    )
    _LLM_LATENCY_SEC = Histogram(
        "xiaotie_llm_latency_seconds",
        "LLM latency seconds",
        ["provider", "model"],
    )
    _TOOL_CALLS_TOTAL = Counter(
        "xiaotie_tool_calls_total",
        "Total tool calls",
        ["tool", "success"],
    )
    _TOOL_LATENCY_SEC = Histogram(
        "xiaotie_tool_latency_seconds",
        "Tool latency seconds",
        ["tool"],
    )
    _STREAM_FLUSH_LATENCY_SEC = Histogram(
        "xiaotie_stream_flush_latency_seconds",
        "Stream flush latency seconds",
    )
    _STREAM_QUEUE_DEPTH = Gauge(
        "xiaotie_stream_queue_depth",
        "Current stream queue depth",
        ["session_id"],
    )


@dataclass
class AgentTelemetry:
    session_id: str
    max_samples: int = 2048
    started_at: float = field(default_factory=time.time)

    def __post_init__(self):
        self._lock = threading.Lock()
        self._runs_total = 0
        self._runs_success = 0
        self._runs_error = 0
        self._runs_cancelled = 0
        self._llm_calls_total = 0
        self._llm_calls_error = 0
        self._tool_calls_total = 0
        self._tool_calls_error = 0
        self._stream_flush_total = 0
        self._stream_event_total = 0
        self._last_stream_queue_depth = 0
        self._llm_latency: Deque[float] = deque(maxlen=self.max_samples)
        self._tool_latency: Deque[float] = deque(maxlen=self.max_samples)
        self._flush_latency: Deque[float] = deque(maxlen=self.max_samples)
        self._tool_calls_by_name: Dict[str, int] = {}
        self._tool_errors_by_name: Dict[str, int] = {}
        self._llm_calls_by_provider_model: Dict[str, int] = {}

    def record_run_start(self):
        with self._lock:
            self._runs_total += 1

    def record_run_end(self, status: str):
        with self._lock:
            if status == "success":
                self._runs_success += 1
            elif status == "cancelled":
                self._runs_cancelled += 1
            else:
                self._runs_error += 1
        if _PROM_AVAILABLE:
            _RUNS_TOTAL.labels(status=status).inc()

    def record_llm_call(
        self,
        provider: str,
        model: str,
        latency_sec: float,
        success: bool,
    ):
        key = f"{provider}:{model}"
        with self._lock:
            self._llm_calls_total += 1
            self._llm_latency.append(max(0.0, latency_sec))
            self._llm_calls_by_provider_model[key] = self._llm_calls_by_provider_model.get(key, 0) + 1
            if not success:
                self._llm_calls_error += 1
        if _PROM_AVAILABLE:
            _LLM_CALLS_TOTAL.labels(provider=provider, model=model, success=str(success).lower()).inc()
            _LLM_LATENCY_SEC.labels(provider=provider, model=model).observe(max(0.0, latency_sec))

    def record_tool_call(self, tool_name: str, latency_sec: float, success: bool):
        with self._lock:
            self._tool_calls_total += 1
            self._tool_latency.append(max(0.0, latency_sec))
            self._tool_calls_by_name[tool_name] = self._tool_calls_by_name.get(tool_name, 0) + 1
            if not success:
                self._tool_calls_error += 1
                self._tool_errors_by_name[tool_name] = self._tool_errors_by_name.get(tool_name, 0) + 1
        if _PROM_AVAILABLE:
            _TOOL_CALLS_TOTAL.labels(tool=tool_name, success=str(success).lower()).inc()
            _TOOL_LATENCY_SEC.labels(tool=tool_name).observe(max(0.0, latency_sec))

    def record_stream_flush(self, event_count: int, latency_sec: float):
        with self._lock:
            self._stream_flush_total += 1
            self._stream_event_total += max(0, event_count)
            self._flush_latency.append(max(0.0, latency_sec))
        if _PROM_AVAILABLE:
            _STREAM_FLUSH_LATENCY_SEC.observe(max(0.0, latency_sec))

    def record_stream_queue_depth(self, queue_depth: int):
        with self._lock:
            self._last_stream_queue_depth = max(0, queue_depth)
        if _PROM_AVAILABLE:
            _STREAM_QUEUE_DEPTH.labels(session_id=self.session_id).set(max(0, queue_depth))

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            llm_avg, llm_p95 = _avg_p95(self._llm_latency)
            tool_avg, tool_p95 = _avg_p95(self._tool_latency)
            flush_avg, flush_p95 = _avg_p95(self._flush_latency)
            llm_calls_total = self._llm_calls_total
            tool_calls_total = self._tool_calls_total
            runs_total = self._runs_total

            uptime_sec = max(0.0, time.time() - self.started_at)
            llm_error_rate = _safe_rate(self._llm_calls_error, llm_calls_total)
            tool_error_rate = _safe_rate(self._tool_calls_error, tool_calls_total)
            run_error_rate = _safe_rate(self._runs_error, runs_total)
            run_cancel_rate = _safe_rate(self._runs_cancelled, runs_total)
            stream_events_per_flush = (
                self._stream_event_total / self._stream_flush_total if self._stream_flush_total > 0 else 0.0
            )

            return {
                "session_id": self.session_id,
                "uptime_sec": round(uptime_sec, 3),
                "runs_total": runs_total,
                "runs_success": self._runs_success,
                "runs_error": self._runs_error,
                "runs_cancelled": self._runs_cancelled,
                "run_error_rate": round(run_error_rate, 4),
                "run_cancel_rate": round(run_cancel_rate, 4),
                "llm_calls_total": llm_calls_total,
                "llm_calls_error": self._llm_calls_error,
                "llm_error_rate": round(llm_error_rate, 4),
                "llm_latency_avg_sec": round(llm_avg, 4),
                "llm_latency_p95_sec": round(llm_p95, 4),
                "llm_calls_by_provider_model": dict(self._llm_calls_by_provider_model),
                "tool_calls_total": tool_calls_total,
                "tool_calls_error": self._tool_calls_error,
                "tool_error_rate": round(tool_error_rate, 4),
                "tool_latency_avg_sec": round(tool_avg, 4),
                "tool_latency_p95_sec": round(tool_p95, 4),
                "tool_calls_by_name": dict(self._tool_calls_by_name),
                "tool_errors_by_name": dict(self._tool_errors_by_name),
                "stream_flush_total": self._stream_flush_total,
                "stream_event_total": self._stream_event_total,
                "stream_events_per_flush": round(stream_events_per_flush, 3),
                "stream_flush_latency_avg_sec": round(flush_avg, 4),
                "stream_flush_latency_p95_sec": round(flush_p95, 4),
                "stream_queue_depth": self._last_stream_queue_depth,
                "prometheus_enabled": _PROM_AVAILABLE,
            }


def _avg_p95(values: Deque[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    series = sorted(values)
    avg = sum(series) / len(series)
    idx = max(0, math.ceil(len(series) * 0.95) - 1)
    return avg, series[idx]


def _safe_rate(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return num / den
