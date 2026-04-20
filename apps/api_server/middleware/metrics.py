"""
Prometheus metrics middleware for simulation latency observability.

Tracks:
  simulation_duration_seconds    — total request latency histogram (p50/p95/p99)
  mojo_compute_duration_seconds  — Mojo engine compute time only
  mojo_pool_wait_seconds         — time waiting for a worker from the pool
  simulation_errors_total        — error counter by type

Mounts at /metrics (protected — see main.py).

Usage in simulation_service.py:
  from apps.api_server.middleware.metrics import record_simulation_latency
  record_simulation_latency(total_ms=13, mojo_ms=8, pool_wait_ms=0.5)
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

# ─── Histograms ───────────────────────────────────────────────────────────────

SIMULATION_LATENCY = Histogram(
    name="simulation_duration_seconds",
    documentation="End-to-end simulation request latency (server-side only).",
    labelnames=["mode", "plan"],
    buckets=[0.005, 0.010, 0.015, 0.020, 0.030, 0.040, 0.050, 0.075, 0.100, 0.250, 0.500, 1.0],
)

MOJO_COMPUTE_LATENCY = Histogram(
    name="mojo_compute_duration_seconds",
    documentation="Mojo engine compute time (inside worker process).",
    labelnames=["engine_type"],
    buckets=[0.001, 0.003, 0.005, 0.008, 0.010, 0.015, 0.020, 0.050, 0.100, 0.500],
)

MOJO_POOL_WAIT = Histogram(
    name="mojo_pool_wait_seconds",
    documentation="Time waiting to acquire a Mojo worker from the pool.",
    labelnames=[],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.010, 0.050, 0.100, 0.500],
)

QUOTA_CHECK_LATENCY = Histogram(
    name="quota_check_duration_seconds",
    documentation="Quota check latency (Redis path vs DB fallback).",
    labelnames=["source"],   # "redis" | "db"
    buckets=[0.0005, 0.001, 0.002, 0.005, 0.010, 0.050],
)

# ─── Counters ─────────────────────────────────────────────────────────────────

SIMULATION_ERRORS = Counter(
    name="simulation_errors_total",
    documentation="Total simulation errors by type.",
    labelnames=["error_type"],   # "engine_error" | "quota_exceeded" | "rate_limit"
)

SIMULATION_TOTAL = Counter(
    name="simulations_total",
    documentation="Total successful simulations by mode and plan.",
    labelnames=["mode", "plan"],
)

MOJO_WORKER_RESTARTS = Counter(
    name="mojo_worker_restarts_total",
    documentation="Total Mojo worker process restarts (health monitor replacements).",
    labelnames=[],
)


# ─── Helper — called by simulate.py after each request ───────────────────────

def record_simulation_latency(
    *,
    total_ms: int,
    mojo_ms: int,
    pool_wait_ms: float = 0.0,
    mode: str = "auto",
    plan: str = "free",
    engine_type: str = "monte_carlo",
) -> None:
    """Record a completed simulation into all relevant metrics."""
    SIMULATION_LATENCY.labels(mode=mode, plan=plan).observe(total_ms / 1000.0)
    MOJO_COMPUTE_LATENCY.labels(engine_type=engine_type).observe(mojo_ms / 1000.0)
    if pool_wait_ms > 0:
        MOJO_POOL_WAIT.observe(pool_wait_ms / 1000.0)
    SIMULATION_TOTAL.labels(mode=mode, plan=plan).inc()


def record_simulation_error(error_type: str) -> None:
    SIMULATION_ERRORS.labels(error_type=error_type).inc()


def record_quota_check(source: str, duration_s: float) -> None:
    QUOTA_CHECK_LATENCY.labels(source=source).observe(duration_s)


def record_worker_restart() -> None:
    MOJO_WORKER_RESTARTS.inc()
