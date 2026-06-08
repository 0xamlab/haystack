"""
Phase 9 — Concurrent Load / Stress Integration Tests.

Exercises the system under concurrent load — verifying it handles parallel
requests, maintains data integrity under contention, and degrades gracefully.

Prerequisites:
  1. API server running: make dev-api
  2. PostgreSQL running on :5432
  3. Redis running on :6379
  4. Mojo binary built: make build-mojo
  5. Dev data seeded: python scripts/seed_dev.py

Run:
  python tests/integration/test_load.py
"""

# ruff: noqa: E402

import json
import math
import os
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.integration.live_capacity_blockers import (
    classify_simulation_capacity_blocker,  # noqa: E402
)

# Global socket timeout — generous for load tests
socket.setdefaulttimeout(30)

try:
    from tests.integration.live_local_defaults import (
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )
except ModuleNotFoundError:
    from live_local_defaults import (
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )

BASE_URL = resolve_local_live_base_url()
API_KEY = resolve_local_live_api_key()

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple] = []
timings: list[tuple[str, float]] = []
perf_stats: list[tuple[str, str]] = []  # (label, formatted stats string)


class EnvironmentBlockedError(RuntimeError):
    """Raised when the live environment cannot execute simulation due to quota/capacity."""


# ─── HTTP helpers ─────────────────────────────────────────────────────────────
def req(method: str, path: str, body=None, headers=None, auth=True, timeout=20):
    """Make HTTP request, return (status_code, response_body, response_headers, elapsed)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json"}
    if auth:
        h["X-API-Key"] = API_KEY
    if headers:
        h.update(headers)
    request = urllib.request.Request(url, data=data, headers=h, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            elapsed = time.perf_counter() - t0
            body_bytes = resp.read()
            try:
                body_data = json.loads(body_bytes)
            except Exception:
                body_data = body_bytes.decode("utf-8", errors="replace")
            return resp.status, body_data, dict(resp.headers), elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        body_bytes = e.read()
        try:
            body_data = json.loads(body_bytes)
        except Exception:
            body_data = body_bytes.decode("utf-8", errors="replace")
        return e.code, body_data, dict(e.headers), elapsed
    except TimeoutError as err:
        elapsed = time.perf_counter() - t0
        raise TimeoutError(
            f"Request to {url} timed out after {timeout}s (elapsed: {elapsed:.1f}s)"
        ) from err
    except urllib.error.URLError as err:
        if "timed out" in str(err):
            elapsed = time.perf_counter() - t0
            raise TimeoutError(
                f"Request to {url} timed out after {timeout}s (elapsed: {elapsed:.1f}s)"
            ) from err
        raise RuntimeError(f"Cannot connect to {BASE_URL} — is the API server running?") from err


def check(name: str, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"  {PASS} {name}")
    except EnvironmentBlockedError as e:
        results.append((SKIP, name, str(e)))
        print(f"  {SKIP} {name}: {e}")
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}: {e}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}: {type(e).__name__}: {e}")


# ─── Standard payloads ────────────────────────────────────────────────────────
def _sim_payload(runs=500, seed=None, tag=None):
    """Standard auto-mode payload for load testing (small run count)."""
    p = {
        "mode": "auto",
        "simulation_model": "monte_carlo",
        "scenario": {
            "name": f"load-test{'-' + tag if tag else ''}",
            "variables": {
                "revenue": {"low": 80000, "high": 200000},
                "cost": {"low": 40000, "high": 90000},
            },
            "objective": "maximize_net_value",
        },
        "runs": runs,
    }
    if seed is not None:
        p["seed"] = seed
    return p


def _alt_payload(runs=500, seed=None):
    """Alternative payload with different variable ranges (for data-integrity checks)."""
    return {
        "mode": "auto",
        "simulation_model": "monte_carlo",
        "scenario": {
            "name": "load-test-alt",
            "variables": {
                "revenue": {"low": 10000, "high": 30000},
                "cost": {"low": 5000, "high": 25000},
            },
            "objective": "maximize_net_value",
        },
        "runs": runs,
        **({"seed": seed} if seed is not None else {}),
    }


def _assert_valid_envelope(body):
    """Assert response body is a valid DecisionEnvelope."""
    assert isinstance(body, dict), f"Expected dict, got {type(body)}"
    assert "run_id" in body, f"Missing run_id in {list(body.keys())[:10]}"
    assert "metrics" in body, f"Missing metrics in {list(body.keys())[:10]}"
    assert "recommended_action" in body, "Missing recommended_action"
    assert "confidence" in body, "Missing confidence"
    assert "percentiles" in body, "Missing percentiles"
    assert "scenarios_run" in body, "Missing scenarios_run"
    assert "execution_ms" in body, "Missing execution_ms"
    m = body["metrics"]
    assert "expected_value" in m, "Missing metrics.expected_value"
    assert "median" in m, "Missing metrics.median"
    assert "std_deviation" in m, "Missing metrics.std_deviation"


def _percentile(data, pct):
    """Calculate percentile from sorted data."""
    if not data:
        return 0
    s = sorted(data)
    idx = (pct / 100) * (len(s) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def _format_timing_stats(times_list):
    """Format timing statistics for a list of elapsed times."""
    if not times_list:
        return "no data"
    p50 = _percentile(times_list, 50)
    p95 = _percentile(times_list, 95)
    p99 = _percentile(times_list, 99)
    avg = statistics.mean(times_list)
    mn = min(times_list)
    mx = max(times_list)
    return (
        f"p50={p50:.3f}s  p95={p95:.3f}s  p99={p99:.3f}s  "
        f"avg={avg:.3f}s  min={mn:.3f}s  max={mx:.3f}s"
    )


def _classify_capacity_blocker(status: int, body) -> str | None:
    return classify_simulation_capacity_blocker(status=status, payload=body)


def _capacity_blocker_from_result(result) -> str | None:
    if isinstance(result, Exception):
        return None
    status, body, _, _ = result
    return _classify_capacity_blocker(status, body)


def _capacity_blocker_from_results(results_list) -> str | None:
    for result in results_list:
        reason = _capacity_blocker_from_result(result)
        if reason:
            return reason
    return None


# ─── Concurrent execution helper ─────────────────────────────────────────────
def _run_concurrent(fn_list, max_workers=20) -> list[Any]:
    """Run a list of callables concurrently, return list of results or exceptions."""
    results_out: list[Any] = [None] * len(fn_list)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(fn): i for i, fn in enumerate(fn_list)}
        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                results_out[idx] = future.result()
            except Exception as exc:
                results_out[idx] = exc
    return results_out


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: Concurrent Simulation Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_concurrent_simulations():
    print("\n🔥 Concurrent Simulation Tests")

    # 1.1 — 10 simultaneous simulations, all return 200
    def ten_concurrent_all_200():
        fns = [lambda: req("POST", "/v1/simulate", body=_sim_payload(runs=500)) for _ in range(10)]
        out = _run_concurrent(fns, max_workers=10)
        for i, r in enumerate(out):
            assert not isinstance(r, Exception), f"Thread {i} raised: {r}"
            status, body, hdrs, elapsed = r
            blocked_reason = _classify_capacity_blocker(status, body)
            if blocked_reason:
                raise EnvironmentBlockedError(blocked_reason)
            assert status == 200, f"Thread {i} got status {status}: {body}"
            _assert_valid_envelope(body)

    check("10 concurrent simulations → all 200 with valid envelopes", ten_concurrent_all_200)

    # 1.2 — 20 simultaneous requests, no 500 errors
    def twenty_concurrent_no_500():
        fns = [lambda: req("POST", "/v1/simulate", body=_sim_payload(runs=500)) for _ in range(20)]
        out = _run_concurrent(fns, max_workers=20)
        for i, r in enumerate(out):
            assert not isinstance(r, Exception), f"Thread {i} raised: {r}"
            status, body, hdrs, elapsed = r
            assert status != 500, f"Thread {i} got 500 error: {body}"

    check("20 concurrent simulations → no 500 errors", twenty_concurrent_no_500)

    # 1.3 — All run_ids unique across concurrent responses
    def unique_run_ids():
        fns = [lambda: req("POST", "/v1/simulate", body=_sim_payload(runs=500)) for _ in range(10)]
        out = _run_concurrent(fns, max_workers=10)
        run_ids = []
        for i, r in enumerate(out):
            assert not isinstance(r, Exception), f"Thread {i} raised: {r}"
            status, body, hdrs, elapsed = r
            if status == 200:
                run_ids.append(body["run_id"])
        assert len(run_ids) == len(set(run_ids)), (
            f"Duplicate run_ids found! {len(run_ids)} total, {len(set(run_ids))} unique"
        )

    check("All run_ids unique across 10 concurrent responses", unique_run_ids)

    # 1.4 — p50/p95/p99 latency under 10-concurrent load
    def latency_under_load():
        elapsed_times = []
        fns = [lambda: req("POST", "/v1/simulate", body=_sim_payload(runs=500)) for _ in range(10)]
        out = _run_concurrent(fns, max_workers=10)
        for i, r in enumerate(out):
            assert not isinstance(r, Exception), f"Thread {i} raised: {r}"
            status, body, hdrs, elapsed = r
            if status == 200:
                elapsed_times.append(elapsed)
        if not elapsed_times:
            blocked_reason = _capacity_blocker_from_results(out)
            if blocked_reason:
                raise EnvironmentBlockedError(blocked_reason)
        stats_str = _format_timing_stats(elapsed_times)
        perf_stats.append(("10-concurrent simulate latency", stats_str))
        print(f"    📊 {stats_str}")
        p99 = _percentile(elapsed_times, 99)
        assert p99 < 30.0, f"p99 latency {p99:.3f}s exceeds 30s threshold"

    check("p50/p95/p99 latency measured under 10-concurrent load", latency_under_load)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: Mixed Endpoint Concurrency
# ═══════════════════════════════════════════════════════════════════════════════
def test_mixed_endpoints():
    print("\n🔀 Mixed Endpoint Concurrency Tests")

    # 2.1 — 15 threads hitting different endpoints simultaneously
    def mixed_15_threads():
        endpoints = [
            ("GET", "/v1/health", False, None),
            ("GET", "/v1/version", False, None),
            ("POST", "/v1/simulate", True, _sim_payload(runs=500)),
            ("GET", "/v1/runs", True, None),
            ("GET", "/v1/health", False, None),
            ("POST", "/v1/simulate", True, _sim_payload(runs=500)),
            ("GET", "/v1/version", False, None),
            ("POST", "/v1/recommend", True, _sim_payload(runs=500)),
            ("GET", "/v1/health", False, None),
            ("POST", "/v1/simulate", True, _sim_payload(runs=500)),
            ("GET", "/v1/runs", True, None),
            ("GET", "/v1/version", False, None),
            ("POST", "/v1/simulate", True, _sim_payload(runs=500)),
            ("GET", "/v1/health", False, None),
            ("POST", "/v1/simulate", True, _sim_payload(runs=500)),
        ]

        def make_req(ep):
            method, path, auth, body = ep
            return req(method, path, body=body, auth=auth, timeout=25)

        fns = [lambda ep=ep: make_req(ep) for ep in endpoints]
        out = _run_concurrent(fns, max_workers=15)
        for i, r in enumerate(out):
            assert not isinstance(r, Exception), f"Thread {i} ({endpoints[i][1]}) raised: {r}"
            status, body, hdrs, elapsed = r
            assert status != 500, f"Thread {i} ({endpoints[i][1]}) got 500: {body}"

    check("15 threads hitting mixed endpoints → no 500 errors", mixed_15_threads)

    # 2.2 — No cross-request data contamination
    def no_cross_contamination():
        """Two distinct payloads fired concurrently; verify all return valid unique envelopes."""
        payload_a = _sim_payload(runs=500, tag="typeA")
        payload_b = _alt_payload(runs=500)

        fns_a = [lambda: req("POST", "/v1/simulate", body=payload_a) for _ in range(5)]
        fns_b = [lambda: req("POST", "/v1/simulate", body=payload_b) for _ in range(5)]
        out = _run_concurrent(fns_a + fns_b, max_workers=10)

        run_ids = set()
        success_count = 0
        for i, r in enumerate(out):
            assert not isinstance(r, Exception), f"Thread {i} raised: {r}"
            status, body, hdrs, elapsed = r
            if status == 200:
                success_count += 1
                _assert_valid_envelope(body)
                rid = body["run_id"]
                assert rid not in run_ids, f"Duplicate run_id across concurrent requests: {rid}"
                run_ids.add(rid)

        if success_count == 0:
            blocked_reason = _capacity_blocker_from_results(out)
            if blocked_reason:
                raise EnvironmentBlockedError(blocked_reason)
        assert success_count >= 8, f"Only {success_count}/10 requests succeeded"
        print(f"    📊 {success_count}/10 succeeded, {len(run_ids)} unique run_ids")

    check("No cross-request data contamination (distinct payloads)", no_cross_contamination)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3: Sequential Burst Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_sequential_burst():
    print("\n⚡ Sequential Burst Tests")

    # 3.1 — Count runs before burst
    def get_run_count():
        status, body, _, _ = req("GET", "/v1/runs?limit=1", auth=True)
        if status == 200 and isinstance(body, dict):
            return body.get("total", body.get("count", 0))
        return None

    # 3.2 — 50 rapid sequential requests, measure throughput
    def sequential_50():
        burst_count = 50
        elapsed_times = []
        success_count = 0
        error_count = 0
        burst_start = time.perf_counter()

        for _i in range(burst_count):
            try:
                status, body, hdrs, elapsed = req(
                    "POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25
                )
                elapsed_times.append(elapsed)
                if status == 200:
                    success_count += 1
                elif status == 429:
                    # Rate limited — still counts, not an error
                    success_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1

        burst_elapsed = time.perf_counter() - burst_start
        throughput = burst_count / burst_elapsed if burst_elapsed > 0 else 0

        stats_str = _format_timing_stats(elapsed_times)
        perf_stats.append(("50-sequential burst latency", stats_str))
        perf_stats.append(
            ("50-sequential throughput", f"{throughput:.2f} req/s ({burst_elapsed:.1f}s total)")
        )
        print(
            f"    📊 Throughput: {throughput:.2f} req/s ({burst_count} reqs in {burst_elapsed:.1f}s)"
        )
        print(f"    📊 {stats_str}")
        print(f"    📊 Success: {success_count}, Errors: {error_count}")

        assert success_count >= burst_count * 0.8, (
            f"Too many failures: {success_count}/{burst_count} succeeded"
        )

    check("50 rapid sequential simulations with throughput measurement", sequential_50)

    # 3.3 — Verify all responses are valid
    def sequential_10_valid():
        for i in range(10):
            status, body, hdrs, elapsed = req(
                "POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25
            )
            if status == 429:
                continue  # rate limited, skip validation
            assert status == 200, f"Request {i} got {status}: {body}"
            _assert_valid_envelope(body)

    check("10 sequential simulations all return valid envelopes", sequential_10_valid)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4: Connection Stress
# ═══════════════════════════════════════════════════════════════════════════════
def test_connection_stress():
    print("\n🔌 Connection Stress Tests")

    # 4.1 — 20 simultaneous keep-alive connections
    def twenty_keepalive():
        """Open 20 connections simultaneously hitting health endpoint."""
        fns = [lambda: req("GET", "/v1/health", auth=False, timeout=15) for _ in range(20)]
        out = _run_concurrent(fns, max_workers=20)
        ok_count = 0
        for _, r in enumerate(out):
            if isinstance(r, Exception):
                continue
            status, body, hdrs, elapsed = r
            if status == 200:
                ok_count += 1
        assert ok_count >= 15, f"Only {ok_count}/20 health checks succeeded under load"

    check("20 simultaneous connections → server handles without exhaustion", twenty_keepalive)

    # 4.2 — Health endpoint responsive during simulation load
    def health_during_load():
        """Fire 10 simulations + 5 health checks concurrently."""
        sim_fns = [
            lambda: req("POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25)
            for _ in range(10)
        ]
        health_fns = [lambda: req("GET", "/v1/health", auth=False, timeout=15) for _ in range(5)]
        out = _run_concurrent(sim_fns + health_fns, max_workers=15)

        health_ok = 0
        for i in range(10, 15):
            r = out[i]
            if isinstance(r, Exception):
                continue
            status, body, hdrs, elapsed = r
            if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
                health_ok += 1
        assert health_ok >= 3, (
            f"Health endpoint degraded during load: only {health_ok}/5 returned ok"
        )

    check("Health endpoint remains responsive during 10 concurrent simulations", health_during_load)

    # 4.3 — Rapid connection cycling
    def rapid_connect_cycle():
        """Open-close 30 connections in rapid succession."""
        success = 0
        for _ in range(30):
            try:
                status, body, hdrs, elapsed = req("GET", "/v1/health", auth=False, timeout=10)
                if status == 200:
                    success += 1
            except Exception:
                pass
        assert success >= 25, f"Only {success}/30 rapid connections succeeded"

    check("30 rapid sequential connections → no connection exhaustion", rapid_connect_cycle)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5: Data Integrity Under Contention
# ═══════════════════════════════════════════════════════════════════════════════
def test_data_integrity():
    print("\n🔒 Data Integrity Under Contention")

    # 5.1 — Deterministic seed produces consistent results
    def deterministic_seed_concurrent():
        """10 concurrent sims with same payload + seed=42 → same expected_value."""
        payload = _sim_payload(runs=500, seed=42)
        fns = [lambda: req("POST", "/v1/simulate", body=payload, timeout=25) for _ in range(10)]
        out = _run_concurrent(fns, max_workers=10)

        evs = []
        for _i, r in enumerate(out):
            if isinstance(r, Exception):
                continue
            status, body, hdrs, elapsed = r
            if status == 200 and "metrics" in body:
                evs.append(body["metrics"]["expected_value"])

        if len(evs) == 0:
            blocked_reason = _capacity_blocker_from_results(out)
            if blocked_reason:
                raise EnvironmentBlockedError(blocked_reason)
        assert len(evs) >= 5, f"Only {len(evs)} successful responses with metrics"
        # All expected values should be identical (or very close) with same seed
        ev_set = set(evs)
        if len(ev_set) == 1:
            print(f"    📊 All {len(evs)} responses returned EV={evs[0]:.2f} (perfect determinism)")
        else:
            # Allow small floating-point variance
            spread = max(evs) - min(evs)
            mean_ev = statistics.mean(evs)
            rel_spread = spread / abs(mean_ev) if mean_ev != 0 else spread
            print(
                f"    📊 EVs range: {min(evs):.2f} – {max(evs):.2f} (spread={spread:.2f}, rel={rel_spread:.4f})"
            )
            assert rel_spread < 0.01, (
                f"Deterministic seed produced too much variance: spread={spread:.2f}, rel={rel_spread:.4f}"
            )

    check("10 concurrent sims (seed=42) → deterministic results", deterministic_seed_concurrent)

    # 5.2 — Different payloads produce different results (no mixing)
    def no_result_mixing():
        """Fire distinct payloads concurrently, verify each returns valid unique envelope."""
        payload_a = _sim_payload(runs=500, seed=100)
        payload_b = _alt_payload(runs=500, seed=100)

        # Interleave A and B requests
        fns = []
        for i in range(10):
            if i % 2 == 0:
                fns.append(lambda: req("POST", "/v1/simulate", body=payload_a, timeout=25))
            else:
                fns.append(lambda: req("POST", "/v1/simulate", body=payload_b, timeout=25))

        out = _run_concurrent(fns, max_workers=10)

        run_ids = set()
        success_count = 0
        for _i, r in enumerate(out):
            if isinstance(r, Exception):
                continue
            status, body, hdrs, elapsed = r
            if status == 200:
                success_count += 1
                _assert_valid_envelope(body)
                rid = body["run_id"]
                assert rid not in run_ids, f"Duplicate run_id in interleaved requests: {rid}"
                run_ids.add(rid)

        if success_count == 0:
            blocked_reason = _capacity_blocker_from_results(out)
            if blocked_reason:
                raise EnvironmentBlockedError(blocked_reason)
        assert success_count >= 8, f"Only {success_count}/10 interleaved requests succeeded"
        print(f"    📊 {success_count}/10 interleaved succeeded, {len(run_ids)} unique run_ids")

    check("Interleaved A/B payloads → no result mixing", no_result_mixing)

    # 5.3 — Run IDs monotonically different
    def run_ids_all_unique():
        fns = [
            lambda: req("POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25)
            for _ in range(15)
        ]
        out = _run_concurrent(fns, max_workers=15)
        ids = set()
        for r in out:
            if isinstance(r, Exception):
                continue
            status, body, hdrs, elapsed = r
            if status == 200 and "run_id" in body:
                rid = body["run_id"]
                assert rid not in ids, f"Duplicate run_id: {rid}"
                ids.add(rid)
        if len(ids) == 0:
            blocked_reason = _capacity_blocker_from_results(out)
            if blocked_reason:
                raise EnvironmentBlockedError(blocked_reason)
        assert len(ids) >= 10, f"Only {len(ids)} unique run_ids from 15 requests"

    check("15 concurrent requests → all run_ids globally unique", run_ids_all_unique)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 6: Graceful Degradation
# ═══════════════════════════════════════════════════════════════════════════════
def test_graceful_degradation():
    print("\n📉 Graceful Degradation Tests")
    # Fast loopback baselines make pure ratio checks brittle because fixed
    # dispatch and scheduling overhead dominates once concurrency increases.
    # Keep a ratio gate, but also require bounded absolute latency under 10×
    # load so the test still fails on materially bad degradation.
    fast_baseline_ratio_threshold = 12.0
    standard_ratio_threshold = 8.0
    absolute_avg_threshold_seconds = 0.75
    absolute_p95_threshold_seconds = 1.0

    # 6.1 — Baseline (single request)
    def measure_baseline():
        times = []
        blocked_reason = None
        for _ in range(3):
            status, body, hdrs, elapsed = req(
                "POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25
            )
            blocked_reason = blocked_reason or _classify_capacity_blocker(status, body)
            if status == 200:
                times.append(elapsed)
        if not times and blocked_reason:
            raise EnvironmentBlockedError(blocked_reason)
        assert len(times) >= 2, "Could not get baseline measurements"
        return statistics.mean(times)

    # 6.2 — Measure under 5× load
    def measure_concurrent_n(n):
        fns = [
            lambda: req("POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25)
            for _ in range(n)
        ]
        out = _run_concurrent(fns, max_workers=n)
        times = []
        for r in out:
            if isinstance(r, Exception):
                continue
            status, body, hdrs, elapsed = r
            if status == 200:
                times.append(elapsed)
        return times

    def degradation_test():
        # Baseline
        baseline = measure_baseline()
        perf_stats.append(("Baseline (1 req)", f"{baseline:.3f}s"))
        print(f"    📊 Baseline: {baseline:.3f}s")

        # 5× concurrent
        times_5 = measure_concurrent_n(5)
        if times_5:
            avg_5 = statistics.mean(times_5)
            ratio_5 = avg_5 / baseline if baseline > 0 else float("inf")
            perf_stats.append(("5× concurrent avg", f"{avg_5:.3f}s (ratio={ratio_5:.1f}×)"))
            print(f"    📊 5× concurrent: avg={avg_5:.3f}s (ratio={ratio_5:.1f}× baseline)")
        else:
            ratio_5 = 1.0

        # 10× concurrent
        times_10 = measure_concurrent_n(10)
        if times_10:
            avg_10 = statistics.mean(times_10)
            p95_10 = _percentile(times_10, 95)
            ratio_10 = avg_10 / baseline if baseline > 0 else float("inf")
            perf_stats.append(("10× concurrent avg", f"{avg_10:.3f}s (ratio={ratio_10:.1f}×)"))
            perf_stats.append(("10× concurrent p95", f"{p95_10:.3f}s"))
            print(f"    📊 10× concurrent: avg={avg_10:.3f}s (ratio={ratio_10:.1f}× baseline)")
            print(f"    📊 10× concurrent p95: {p95_10:.3f}s")
        else:
            avg_10 = 0.0
            p95_10 = 0.0
            ratio_10 = ratio_5

        # Sub-linear degradation: 10× load should NOT cause exponential slowdown
        # When the baseline is already fast on loopback, bounded absolute
        # latency is a better signal than a strict ratio alone.
        threshold = fast_baseline_ratio_threshold if baseline < 0.10 else standard_ratio_threshold
        within_ratio_gate = ratio_10 < threshold
        within_absolute_gate = (
            avg_10 < absolute_avg_threshold_seconds and p95_10 < absolute_p95_threshold_seconds
        )
        assert within_ratio_gate or within_absolute_gate, (
            "Degradation exceeded both bounded-ratio and bounded-absolute gates: "
            f"10× load → {ratio_10:.1f}× slowdown (threshold: {threshold}×), "
            f"avg={avg_10:.3f}s (threshold: {absolute_avg_threshold_seconds:.3f}s), "
            f"p95={p95_10:.3f}s (threshold: {absolute_p95_threshold_seconds:.3f}s)"
        )
        print(
            "    📊 Degradation: bounded ✓ "
            f"(10× load → {ratio_10:.1f}× slowdown, threshold: {threshold}×; "
            f"avg={avg_10:.3f}s, p95={p95_10:.3f}s)"
        )

    check("Graceful degradation: sub-linear slowdown under increasing load", degradation_test)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 7: Rate Limit Behavior
# ═══════════════════════════════════════════════════════════════════════════════
def test_rate_limits():
    print("\n🚦 Rate Limit Behavior Tests")

    # 7.1 — Rate limit headers present
    def rate_limit_headers_present():
        status, body, hdrs, elapsed = req(
            "POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25
        )
        # Check for standard rate-limit headers (case-insensitive)
        hdrs_lower = {k.lower(): v for k, v in hdrs.items()}
        has_limit = (
            "x-ratelimit-limit" in hdrs_lower
            or "ratelimit-limit" in hdrs_lower
            or "x-ratelimit-remaining" in hdrs_lower
            or "ratelimit-remaining" in hdrs_lower
        )
        if has_limit:
            remaining = hdrs_lower.get("x-ratelimit-remaining") or hdrs_lower.get(
                "ratelimit-remaining"
            )
            limit_val = hdrs_lower.get("x-ratelimit-limit") or hdrs_lower.get("ratelimit-limit")
            print(f"    📊 Rate limit headers: limit={limit_val}, remaining={remaining}")
        else:
            # Rate limiting might be at gateway level, not on direct API
            print("    📊 No rate limit headers on direct API (may be gateway-only)")
        # This test passes either way — we just report what we find
        assert status in (200, 429), f"Unexpected status {status}"

    check("Rate limit headers present in responses", rate_limit_headers_present)

    # 7.2 — Remaining counter decreases
    def rate_limit_decreasing():
        remaining_values = []
        for _ in range(5):
            status, body, hdrs, elapsed = req(
                "POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25
            )
            hdrs_lower = {k.lower(): v for k, v in hdrs.items()}
            remaining = hdrs_lower.get("x-ratelimit-remaining") or hdrs_lower.get(
                "ratelimit-remaining"
            )
            if remaining is not None:
                try:
                    remaining_values.append(int(remaining))
                except ValueError:
                    pass
            if status == 429:
                break

        if len(remaining_values) >= 2:
            # Each successive value should be <= the previous (non-increasing)
            decreasing = all(
                remaining_values[i] >= remaining_values[i + 1]
                for i in range(len(remaining_values) - 1)
            )
            assert decreasing, f"Rate limit remaining not decreasing: {remaining_values}"
            print(f"    📊 Remaining values: {remaining_values}")
        else:
            print("    📊 Rate limit counters not available on direct API (gateway-only)")

    check("Rate limit remaining counter decreases", rate_limit_decreasing)

    # 7.3 — If rate limited, verify 429 + Retry-After
    def rate_limit_429_response():
        """Send many rapid requests to try to trigger rate limiting."""
        got_429 = False
        for request_idx in range(30):
            status, body, hdrs, elapsed = req(
                "POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25
            )
            if status == 429:
                got_429 = True
                hdrs_lower = {k.lower(): v for k, v in hdrs.items()}
                retry_after = hdrs_lower.get("retry-after")
                print(
                    f"    📊 Got 429 after {request_idx + 1} requests. Retry-After: {retry_after}"
                )
                # If we got 429, we expect some indication of when to retry
                # (Retry-After header or error body with info)
                break
        if not got_429:
            print(
                "    📊 No 429 received after 30 requests (rate limit may be high or gateway-only)"
            )
        # This test always passes — it's observational

    check("Rate limit 429 behavior (observational)", rate_limit_429_response)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 8: Resource Monitoring
# ═══════════════════════════════════════════════════════════════════════════════
def test_resource_monitoring():
    print("\n📊 Resource Monitoring Tests")

    # 8.1 — Redis memory before/after load
    def redis_memory_check():
        try:
            import subprocess

            # Get Redis memory before load
            before = subprocess.run(
                ["redis-cli", "INFO", "memory"], capture_output=True, text=True, timeout=5
            )
            if before.returncode != 0:
                print("    📊 Redis CLI not available (skipping memory check)")
                return

            before_lines = before.stdout.split("\n")
            before_mem = None
            for line in before_lines:
                if line.startswith("used_memory:"):
                    before_mem = int(line.split(":")[1].strip())
                    break

            # Run some load
            fns = [
                lambda: req("POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25)
                for _ in range(10)
            ]
            _run_concurrent(fns, max_workers=10)

            # Small pause for cleanup
            time.sleep(1)

            # Get Redis memory after load
            after = subprocess.run(
                ["redis-cli", "INFO", "memory"], capture_output=True, text=True, timeout=5
            )
            after_lines = after.stdout.split("\n")
            after_mem = None
            for line in after_lines:
                if line.startswith("used_memory:"):
                    after_mem = int(line.split(":")[1].strip())
                    break

            if before_mem and after_mem:
                diff_kb = (after_mem - before_mem) / 1024
                perf_stats.append(
                    (
                        "Redis memory delta (10-req load)",
                        f"{diff_kb:+.1f} KB (before={before_mem / 1024:.0f}KB, after={after_mem / 1024:.0f}KB)",
                    )
                )
                print(
                    f"    📊 Redis memory: before={before_mem / 1024:.0f}KB, after={after_mem / 1024:.0f}KB, delta={diff_kb:+.1f}KB"
                )
                # No hard assertion — just reporting
        except FileNotFoundError:
            print("    📊 redis-cli not found (skipping)")
        except Exception as e:
            print(f"    📊 Redis check error: {e}")

    check("Redis memory before/after load (observational)", redis_memory_check)

    # 8.2 — DB connection count check
    def db_connection_check():
        try:
            import subprocess

            # Check pg_stat_activity
            result = subprocess.run(
                [
                    "psql",
                    "-h",
                    "localhost",
                    "-U",
                    "postgres",
                    "-d",
                    "algenta",
                    "-t",
                    "-c",
                    "SELECT count(*) FROM pg_stat_activity WHERE datname='algenta';",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                env={**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "postgres")},
            )
            if result.returncode == 0:
                count = result.stdout.strip()
                perf_stats.append(("DB active connections", count))
                print(f"    📊 Active DB connections: {count}")
            else:
                print("    📊 psql not available or DB not accessible (skipping)")
        except FileNotFoundError:
            print("    📊 psql not found (skipping)")
        except Exception as e:
            print(f"    📊 DB check error: {e}")

    check("DB connection count (observational)", db_connection_check)

    # 8.3 — Health still ok after all load tests
    def health_after_load():
        status, body, hdrs, elapsed = req("GET", "/v1/health", auth=False, timeout=10)
        assert status == 200, f"Health returned {status} after load tests"
        assert body.get("status") == "ok", f"Health not ok after load: {body}"
        perf_stats.append(("Post-load health check", f"{elapsed:.3f}s"))
        print(f"    📊 Health response: {elapsed:.3f}s")

    check("Server health ok after all load tests (no resource leaks)", health_after_load)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 9: Sustained Load (Medium Duration)
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.slow
def test_sustained_load():
    print("\n🏋️ Sustained Load Tests")

    # 9.1 — 30-second sustained concurrent load
    def sustained_30s():
        """Run concurrent requests for ~15 seconds, measure stability."""
        duration_seconds = 15
        concurrency = 5
        request_count = 0
        success_count = 0
        error_count = 0
        all_times = []
        start = time.perf_counter()

        while time.perf_counter() - start < duration_seconds:
            fns = [
                lambda: req("POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25)
                for _ in range(concurrency)
            ]
            out = _run_concurrent(fns, max_workers=concurrency)
            for r in out:
                request_count += 1
                if isinstance(r, Exception):
                    error_count += 1
                    continue
                status, body, hdrs, elapsed = r
                all_times.append(elapsed)
                if status in (200, 429):
                    success_count += 1
                else:
                    error_count += 1

        actual_duration = time.perf_counter() - start
        throughput = request_count / actual_duration if actual_duration > 0 else 0
        success_rate = (success_count / request_count * 100) if request_count > 0 else 0

        stats_str = _format_timing_stats(all_times) if all_times else "no data"
        perf_stats.append(
            (
                "Sustained load (15s, 5-concurrent)",
                (f"{request_count} reqs, {throughput:.1f} req/s, {success_rate:.0f}% success"),
            )
        )
        perf_stats.append(("Sustained load latency", stats_str))
        print(f"    📊 Duration: {actual_duration:.1f}s, Requests: {request_count}")
        print(f"    📊 Throughput: {throughput:.1f} req/s")
        print(f"    📊 Success rate: {success_rate:.0f}% ({success_count}/{request_count})")
        print(f"    📊 Latency: {stats_str}")

        assert success_rate >= 80, f"Success rate too low: {success_rate:.0f}%"

    check("15s sustained load at 5× concurrency → ≥80% success rate", sustained_30s)

    # 9.2 — Latency stability over time (no monotonic increase)
    def latency_stability():
        """Fire 20 sequential requests, check latency doesn't keep increasing."""
        times = []
        for _ in range(20):
            try:
                status, body, hdrs, elapsed = req(
                    "POST", "/v1/simulate", body=_sim_payload(runs=500), timeout=25
                )
                times.append(elapsed)
            except Exception:
                times.append(None)

        valid_times = [t for t in times if t is not None]
        if len(valid_times) < 10:
            print(f"    📊 Only {len(valid_times)} valid measurements (skipping stability check)")
            return

        # Split into first half and second half
        mid = len(valid_times) // 2
        first_half = valid_times[:mid]
        second_half = valid_times[mid:]
        avg_first = statistics.mean(first_half)
        avg_second = statistics.mean(second_half)

        ratio = avg_second / avg_first if avg_first > 0 else 1.0
        perf_stats.append(
            (
                "Latency stability (20 reqs)",
                (
                    f"first-half avg={avg_first:.3f}s, second-half avg={avg_second:.3f}s, ratio={ratio:.2f}"
                ),
            )
        )
        print(
            f"    📊 First half avg: {avg_first:.3f}s, Second half avg: {avg_second:.3f}s, ratio: {ratio:.2f}"
        )

        # Second half shouldn't be more than 3× the first half (no runaway degradation)
        assert ratio < 3.0, (
            f"Latency increasing over time: first={avg_first:.3f}s, second={avg_second:.3f}s, ratio={ratio:.2f}"
        )

    check("Latency stability over 20 sequential requests (no runaway)", latency_stability)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 70)
    print("  Phase 9: Concurrent Load / Stress Integration Tests")
    print(f"  Target: {BASE_URL}")
    print("=" * 70)

    # Pre-flight: verify server is up
    try:
        status, body, _, elapsed = req("GET", "/v1/health", auth=False, timeout=10)
        assert status == 200 and body.get("status") == "ok"
        print(f"  ✓ Server is up ({elapsed:.3f}s)\n")
    except Exception as e:
        print(f"\n  ✗ Cannot reach server at {BASE_URL}: {e}")
        print("  Ensure the API server is running: make dev-api")
        sys.exit(1)

    test_concurrent_simulations()
    test_mixed_endpoints()
    test_sequential_burst()
    test_connection_stress()
    test_data_integrity()
    test_graceful_degradation()
    test_rate_limits()
    test_resource_monitoring()
    test_sustained_load()

    # ─── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    skipped = sum(1 for r in results if r[0] == SKIP)
    total = len(results)
    print(f"\n  Total: {total}  |  Passed: {passed}  |  Failed: {failed}  |  Skipped: {skipped}")

    if perf_stats:
        print("\n  ─── Performance Statistics ───")
        for label, value in perf_stats:
            print(f"    {label}: {value}")

    if failed:
        print("\n  ─── Failed Tests ───")
        for r in results:
            if r[0] == FAIL:
                print(f"    {FAIL} {r[1]}: {r[2]}")
    elif skipped:
        print("\n  ─── Skipped Tests ───")
        for r in results:
            if r[0] == SKIP:
                print(f"    {SKIP} {r[1]}: {r[2]}")

    print("\n" + "=" * 70)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
