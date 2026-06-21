"""
Tracker

In-memory request log for monitoring LLM usage.
Tracks every completion: model, tokens, cost, latency.

In production this would write to a database or time-series store.
For this project, it's an in-memory list with a size cap.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock

from providers import CompletionResult


@dataclass
class RequestRecord:
    """A single logged API request."""
    request_id: int
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    total_cost: float
    stop_reason: str
    timestamp: float = field(default_factory=time.time)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "request_id":    self.request_id,
            "provider":      self.provider,
            "model":         self.model,
            "input_tokens":  self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens":  self.input_tokens + self.output_tokens,
            "latency_ms":    round(self.latency_ms, 2),
            "total_cost":    self.total_cost,
            "stop_reason":   self.stop_reason,
            "timestamp":     self.timestamp,
            "error":         self.error,
        }


class RequestTracker:
    """
    Thread-safe in-memory request log.

    Tracks:
    - Every request with full metadata
    - Running totals: requests, tokens, cost
    - Per-model and per-provider breakdowns
    - Recent request history (capped at max_records)
    """

    def __init__(self, max_records: int = 1000):
        self._records: list[RequestRecord] = []
        self._next_id = 1
        self._max_records = max_records
        self._lock = Lock()

        # Running totals — updated on every log() call
        self._total_requests = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0
        self._total_errors = 0

        # Per-model breakdown
        self._by_model: dict[str, dict] = defaultdict(lambda: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
        })

    def log(self, result: CompletionResult) -> RequestRecord:
        """Record a completed LLM request."""
        with self._lock:
            record = RequestRecord(
                request_id=self._next_id,
                provider=result.provider,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                total_cost=result.cost.get("total_cost", 0.0),
                stop_reason=result.stop_reason,
            )
            self._next_id += 1

            # Store (cap at max_records — drop oldest)
            self._records.append(record)
            if len(self._records) > self._max_records:
                self._records.pop(0)

            # Update running totals
            self._total_requests += 1
            self._total_input_tokens  += result.input_tokens
            self._total_output_tokens += result.output_tokens
            self._total_cost += result.cost.get("total_cost", 0.0)

            # Update per-model breakdown
            m = self._by_model[result.model]
            m["requests"]      += 1
            m["input_tokens"]  += result.input_tokens
            m["output_tokens"] += result.output_tokens
            m["total_cost"]    += result.cost.get("total_cost", 0.0)

            return record

    def log_error(self, provider: str, model: str, error: str) -> None:
        """Record a failed request."""
        with self._lock:
            self._total_errors += 1
            self._records.append(RequestRecord(
                request_id=self._next_id,
                provider=provider,
                model=model,
                input_tokens=0,
                output_tokens=0,
                latency_ms=0.0,
                total_cost=0.0,
                stop_reason="error",
                error=error,
            ))
            self._next_id += 1

    def recent(self, n: int = 20) -> list[dict]:
        """Return the n most recent records."""
        with self._lock:
            return [r.to_dict() for r in self._records[-n:]]

    def summary(self) -> dict:
        """Return aggregate statistics."""
        with self._lock:
            avg_latency = 0.0
            if self._records:
                latencies = [r.latency_ms for r in self._records if not r.error]
                avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

            return {
                "total_requests":      self._total_requests,
                "total_input_tokens":  self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "total_tokens":        self._total_input_tokens + self._total_output_tokens,
                "total_cost_usd":      round(self._total_cost, 6),
                "total_errors":        self._total_errors,
                "avg_latency_ms":      round(avg_latency, 2),
                "by_model":            dict(self._by_model),
            }

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._next_id = 1
            self._total_requests = 0
            self._total_input_tokens = 0
            self._total_output_tokens = 0
            self._total_cost = 0.0
            self._total_errors = 0
            self._by_model.clear()
