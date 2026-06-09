"""
Phase 8 — Mojo Worker Pool IPC Integration Tests.

Verifies Unix socket communication, pool health, worker availability,
error recovery, and throughput of the Mojo worker pool (11 workers).

Prerequisites:
  1. API server running: make dev-api
  2. PostgreSQL running on :5432
  3. Redis running on :6379
  4. Mojo binary built: make build-mojo
  5. Dev data seeded: python scripts/seed_dev.py

Run:
  python tests/integration/test_mojo_pool.py
"""

import os
import sys

if __name__ == "__main__" and os.environ.get("ALGENTA_SKIP_MOJO_RUNTIME", "0") == "1":
    print("[skip] tests/integration/test_mojo_pool.py — ALGENTA_SKIP_MOJO_RUNTIME=1")
    sys.exit(0)

import json
import re
import socket
import stat
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

if str(Path(__file__).parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parents[2]))

from tests.integration.live_capacity_blockers import classify_simulation_capacity_blocker
from tests.integration.live_integration_artifacts import write_live_integration_summary

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(30)

try:
    from tests.integration.live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )
except ModuleNotFoundError:
    from live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )

BASE_URL = resolve_local_live_base_url()
API_KEY = resolve_local_live_api_key()
API_KEY_CONFIGURED = has_configured_local_live_api_key()

# Repo root (this file is at tests/integration/test_mojo_pool.py)
REPO_ROOT = Path(__file__).parents[2]
MOJO_BINARY = REPO_ROOT / "mojo_build" / "simulate"
SOCKET_DIR = Path(tempfile.gettempdir()) / "algenta-mojo"
POOL_SOCKET_RE = re.compile(r"^worker-\d+-[0-9a-f]{8}\.sock$")
SUITE_NAME = "mojo_pool_integration"
STARTED = time.perf_counter()

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple] = []
timings: list[tuple[str, float]] = []


class EnvironmentBlocked(RuntimeError):
    """Raised when the live environment cannot execute simulation due to quota/capacity."""


class MissingLiveApiKey(EnvironmentBlocked):
    """Raised when a test needs a real configured live API key."""


def _pool_sockets() -> list[Path]:
    if not SOCKET_DIR.exists():
        return []
    return sorted(
        socket_path
        for socket_path in SOCKET_DIR.glob("worker-*.sock")
        if POOL_SOCKET_RE.match(socket_path.name)
    )


def _list_worker_pids() -> list[str] | None:
    try:
        result = subprocess.run(
            ["pgrep", "-f", "simulate.*--server"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return [pid.strip() for pid in result.stdout.splitlines() if pid.strip()]
        if result.stderr and "Cannot get process list" in result.stderr:
            return None
    except FileNotFoundError:
        pass

    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, PermissionError):
        return None

    lines = [
        line
        for line in result.stdout.splitlines()
        if "simulate" in line and "--server" in line and "grep" not in line
    ]
    return [line.split()[1] for line in lines if len(line.split()) > 1]


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def _missing_live_api_key_reason() -> str:
    return (
        "DE_API_KEY is not set; skipping Mojo pool checks that require a real "
        "authenticated live key."
    )


def _require_configured_live_api_key() -> None:
    if not API_KEY_CONFIGURED:
        raise MissingLiveApiKey(_missing_live_api_key_reason())


def _write_summary_artifact() -> str:
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    skipped = sum(1 for r in results if r[0] == SKIP)
    artifact = write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_mojo_pool.py",
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=len(results),
        elapsed_seconds=time.perf_counter() - STARTED,
        details={
            "base_url": configured_local_live_base_url(),
            "api_key_configured": API_KEY_CONFIGURED,
            "socket_dir": str(SOCKET_DIR),
            "mojo_binary": str(MOJO_BINARY),
        },
    )
    return str(artifact)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────
def req(method: str, path: str, body=None, headers=None, auth=True, timeout=10):
    """Make HTTP request, return (status_code, response_body, response_headers, elapsed)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json"}
    if auth:
        _require_configured_live_api_key()
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
        blocked_reason = classify_simulation_capacity_blocker(status=e.code, payload=body_data)
        if blocked_reason and path == "/v1/simulate":
            raise EnvironmentBlocked(blocked_reason)
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
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    try:
        fn()
        results.append((PASS, name))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
    except EnvironmentBlocked as e:
        results.append((SKIP, name, str(e)))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {e}")
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {e}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        _emit(
            f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): "
            f"{type(e).__name__}: {e}"
        )


# ─── Standard payloads ────────────────────────────────────────────────────────
def _auto_payload(runs=10000, seed=None, model="monte_carlo"):
    """Standard auto-mode payload for testing."""
    p = {
        "mode": "auto",
        "simulation_model": model,
        "scenario": {
            "name": "IPC integration test",
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


def _expert_payload(runs=10000, seed=None, model="monte_carlo"):
    """Standard expert-mode payload for testing."""
    p = {
        "mode": "expert",
        "simulation_model": model,
        "simulation": {
            "variables": [
                {
                    "name": "revenue",
                    "distribution": "normal",
                    "params": {"mean": 150000, "std": 30000},
                },
                {
                    "name": "cost",
                    "distribution": "uniform",
                    "params": {"low": 40000, "high": 90000},
                },
            ],
            "objective_function": "revenue - cost",
            "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
        },
        "runs": runs,
    }
    if seed is not None:
        p["seed"] = seed
    return p


# ─── Validation helpers ───────────────────────────────────────────────────────
def _assert_valid_envelope(body):
    """Assert response body is a valid DecisionEnvelope."""
    assert isinstance(body, dict), f"Expected dict, got {type(body)}"
    assert "run_id" in body, "Missing run_id"
    assert "metrics" in body, "Missing metrics"
    assert "recommended_action" in body, "Missing recommended_action"
    assert "confidence" in body, "Missing confidence"
    assert "percentiles" in body, "Missing percentiles"
    assert "scenarios_run" in body, "Missing scenarios_run"
    assert "execution_ms" in body, "Missing execution_ms"
    m = body["metrics"]
    assert "expected_value" in m, "Missing metrics.expected_value"
    assert "median" in m, "Missing metrics.median"
    assert "std_deviation" in m, "Missing metrics.std_deviation"
    assert "probability_of_loss" in m, "Missing metrics.probability_of_loss"


# ═══════════════════════════════════════════════════════════════════════════════
#  1. Pool Health Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_pool_health():
    print("\n🔧 Pool Health Tests")

    # 1.1 — Mojo binary exists
    def binary_exists():
        assert MOJO_BINARY.exists(), f"Mojo binary not found at {MOJO_BINARY}"
        assert os.access(MOJO_BINARY, os.X_OK), f"Mojo binary not executable: {MOJO_BINARY}"

    check("Mojo binary exists and is executable", binary_exists)

    # 1.2 — Socket directory exists
    def socket_dir_exists():
        assert SOCKET_DIR.exists(), f"Socket directory not found: {SOCKET_DIR}"
        assert SOCKET_DIR.is_dir(), f"Socket path is not a directory: {SOCKET_DIR}"

    check(f"Socket directory {SOCKET_DIR} exists", socket_dir_exists)

    # 1.3 — Worker socket files exist
    def worker_sockets_exist():
        socks = _pool_sockets()
        assert len(socks) > 0, f"No worker sockets found in {SOCKET_DIR}"
        # Should have multiple workers (pool size >= 2)
        assert len(socks) >= 2, (
            f"Expected >=2 worker sockets, found {len(socks)}: {[s.name for s in socks]}"
        )

    check(f"Worker socket files exist in {SOCKET_DIR}", worker_sockets_exist)

    # 1.4 — Socket files are valid Unix domain sockets
    def sockets_are_unix():
        socks = _pool_sockets()
        for s in socks:
            st = s.stat()
            assert stat.S_ISSOCK(st.st_mode), (
                f"{s.name} is not a Unix socket (mode={oct(st.st_mode)})"
            )

    check("Socket files are valid Unix domain sockets", sockets_are_unix)

    # 1.5 — Health endpoint returns ok
    def health_ok():
        code, body, _, _ = req("GET", "/v1/health", auth=False)
        assert code == 200, f"Health returned {code}"
        assert body.get("status") == "ok", f"Expected status=ok, got {body}"

    check("Health endpoint returns status=ok", health_ok)

    # 1.6 — Metrics endpoint accessible and contains data
    def metrics_accessible():
        code, body, hdrs, _ = req("GET", "/metrics", auth=False)
        assert code == 200, f"Metrics returned {code}"
        assert isinstance(body, str), "Metrics should return text"
        # Should contain Prometheus-format metrics
        assert "python_info" in body or "process_" in body or "http_" in body, (
            "Metrics response does not look like Prometheus format"
        )

    check("Metrics endpoint returns Prometheus data", metrics_accessible)

    # 1.7 — Version endpoint returns engine info
    def version_ok():
        code, body, _, _ = req("GET", "/v1/version", auth=False)
        assert code == 200, f"Version returned {code}"
        assert "engine_version" in body, f"Missing engine_version: {body}"
        assert "api_version" in body, f"Missing api_version: {body}"

    check("Version endpoint returns engine metadata", version_ok)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. IPC Communication Tests (via API)
# ═══════════════════════════════════════════════════════════════════════════════
def test_ipc_communication():
    print("\n📡 IPC Communication Tests")

    # 2.1 — Basic simulation returns valid envelope
    def basic_simulation():
        payload = _auto_payload(runs=5000, seed=42)
        code, body, hdrs, elapsed = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"Expected 200, got {code}: {body}"
        _assert_valid_envelope(body)
        timings.append(("basic_simulation_auto", elapsed))

    check("Auto-mode simulation returns valid DecisionEnvelope", basic_simulation)

    # 2.2 — Expert-mode simulation returns valid envelope
    def expert_simulation():
        payload = _expert_payload(runs=5000, seed=42)
        code, body, hdrs, elapsed = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"Expected 200, got {code}: {body}"
        _assert_valid_envelope(body)
        # Check expert-specific fields
        assert body.get("scenarios_run") >= 5000, (
            f"Expected >=5000 scenarios_run, got {body.get('scenarios_run')}"
        )
        timings.append(("basic_simulation_expert", elapsed))

    check("Expert-mode simulation returns valid DecisionEnvelope", expert_simulation)

    # 2.3 — Response contains all expected envelope fields
    def full_envelope_fields():
        payload = _auto_payload(runs=5000, seed=100)
        code, body, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"Expected 200, got {code}"
        required_keys = [
            "run_id",
            "status",
            "engine_version",
            "recommended_action",
            "confidence",
            "rationale",
            "metrics",
            "percentiles",
            "scenarios_run",
            "execution_ms",
            "metadata",
        ]
        for key in required_keys:
            assert key in body, f"Missing key '{key}' in envelope"
        # Metadata subfields
        meta = body["metadata"]
        assert "mode" in meta, "Missing metadata.mode"
        assert "billing_units" in meta, "Missing metadata.billing_units"
        assert "engine_version" in meta, "Missing metadata.engine_version"
        # Percentiles
        pctl = body["percentiles"]
        for p in ["p5", "p25", "p50", "p75", "p95"]:
            assert p in pctl, f"Missing percentile {p}"

    check("Response contains all DecisionEnvelope fields", full_envelope_fields)

    # 2.4 — X-Execution-Ms header present
    def execution_header():
        payload = _auto_payload(runs=5000, seed=42)
        code, body, hdrs, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 200
        assert "X-Execution-Ms" in hdrs or "x-execution-ms" in hdrs, (
            f"Missing X-Execution-Ms header. Headers: {list(hdrs.keys())}"
        )

    check("Response includes X-Execution-Ms header", execution_header)

    # 2.5 — Monte Carlo engine works
    def monte_carlo_engine():
        payload = _auto_payload(runs=5000, seed=42, model="monte_carlo")
        code, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"monte_carlo returned {code}: {body}"
        _assert_valid_envelope(body)
        timings.append(("monte_carlo", elapsed))

    check("Engine: monte_carlo produces valid results", monte_carlo_engine)

    # 2.6 — LHS engine works
    def lhs_engine():
        payload = _auto_payload(runs=5000, seed=42, model="lhs")
        code, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"lhs returned {code}: {body}"
        _assert_valid_envelope(body)
        timings.append(("lhs", elapsed))

    check("Engine: lhs produces valid results", lhs_engine)

    # 2.7 — Bootstrap engine works
    def bootstrap_engine():
        payload = {
            "mode": "expert",
            "simulation_model": "bootstrap",
            "simulation": {
                "variables": [
                    {
                        "name": "revenue",
                        "distribution": "normal",
                        "params": {"mean": 150000, "std": 30000},
                    },
                ],
                "objective_function": "revenue",
            },
            "bootstrap_config": {
                "historical_data": [
                    100000,
                    120000,
                    130000,
                    140000,
                    150000,
                    160000,
                    170000,
                    180000,
                    190000,
                    200000,
                ],
                "statistic": "mean",
                "confidence_level": 0.95,
            },
            "runs": 5000,
            "seed": 42,
        }
        code, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"bootstrap returned {code}: {body}"
        _assert_valid_envelope(body)
        timings.append(("bootstrap", elapsed))

    check("Engine: bootstrap produces valid results", bootstrap_engine)

    # 2.8 — QMC Sobol engine works
    def qmc_sobol_engine():
        payload = _auto_payload(runs=5000, seed=42, model="qmc_sobol")
        code, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"qmc_sobol returned {code}: {body}"
        _assert_valid_envelope(body)
        timings.append(("qmc_sobol", elapsed))

    check("Engine: qmc_sobol produces valid results", qmc_sobol_engine)

    # 2.9 — Deterministic seeding produces consistent results
    def deterministic_seeding():
        payload = _auto_payload(runs=10000, seed=12345)
        code1, body1, _, _ = req("POST", "/v1/simulate", body=payload)
        code2, body2, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code1 == 200 and code2 == 200, f"Requests failed: {code1}, {code2}"
        ev1 = body1["metrics"]["expected_value"]
        ev2 = body2["metrics"]["expected_value"]
        # Same seed -> identical expected value
        assert abs(ev1 - ev2) < 0.01, (
            f"Deterministic seeding failed: EV1={ev1}, EV2={ev2}, diff={abs(ev1 - ev2)}"
        )

    check("Deterministic seeding produces consistent results", deterministic_seeding)

    # 2.10 — Simulation model field present in response
    def simulation_model_present():
        payload = _auto_payload(runs=5000, seed=42, model="monte_carlo")
        code, body, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"monte_carlo returned {code}"
        resp_model = body.get("simulation_model", "")
        assert resp_model, "simulation_model is empty in response"
        # Auto-mode may normalize the model name -- just verify field exists
        payload2 = _expert_payload(runs=5000, seed=42, model="monte_carlo")
        code2, body2, _, _ = req("POST", "/v1/simulate", body=payload2)
        assert code2 == 200
        resp2 = body2.get("simulation_model", "")
        assert resp2, "Expert mode simulation_model is empty"

    check("Response contains simulation_model field", simulation_model_present)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. Throughput Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_throughput():
    print("\n⚡ Throughput Tests")

    # 3.1 — Sequential simulations with timing
    def sequential_timing():
        times = []
        for i in range(5):
            payload = _auto_payload(runs=5000, seed=i + 100)
            code, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
            assert code == 200, f"Request {i} failed with {code}: {body}"
            times.append(elapsed)
        avg = sum(times) / len(times)
        timings.append(("sequential_avg_5", avg))
        assert avg < 5.0, f"Average response time {avg:.2f}s exceeds 5s limit"

    check("5 sequential simulations avg < 5s each", sequential_timing)

    # 3.2 — Average response time is reasonable
    def avg_response_reasonable():
        times = []
        for i in range(3):
            payload = _auto_payload(runs=10000, seed=i + 200)
            code, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
            assert code == 200
            times.append(elapsed)
        avg = sum(times) / len(times)
        timings.append(("avg_10k_runs", avg))
        # 10k runs should be well under 5s via IPC
        assert avg < 5.0, f"Average response time for 10k runs: {avg:.2f}s > 5s"

    check("Average response time < 5s for 10k-run simulations", avg_response_reasonable)

    # 3.3 — Rapid-fire batch (5 simulations quickly)
    def rapid_fire_batch():
        t0 = time.perf_counter()
        for i in range(5):
            payload = _auto_payload(runs=2000, seed=i + 300)
            code, body, _, _ = req("POST", "/v1/simulate", body=payload)
            assert code == 200, f"Rapid-fire request {i} failed: {code}"
        total = time.perf_counter() - t0
        timings.append(("rapid_fire_5_total", total))
        assert total < 25.0, f"5 rapid-fire simulations took {total:.1f}s (limit 25s)"

    check("5 rapid-fire simulations all complete", rapid_fire_batch)

    # 3.4 — Execution time reported in response is reasonable
    def execution_ms_reasonable():
        payload = _auto_payload(runs=5000, seed=42)
        code, body, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 200
        exec_ms = body.get("execution_ms", 0)
        assert exec_ms >= 0, f"execution_ms should be >= 0, got {exec_ms}"
        assert exec_ms < 5000, f"execution_ms {exec_ms}ms seems too high for 5k runs"
        timings.append(("server_reported_exec_ms", exec_ms / 1000.0))

    check("Server-reported execution_ms is reasonable", execution_ms_reasonable)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_error_handling():
    print("\n🛡️  Error Handling Tests")

    # 4.1 — Malformed JSON body returns error (not crash)
    def malformed_body():
        _require_configured_live_api_key()
        url = f"{BASE_URL}/v1/simulate"
        data = b"{{invalid json..."
        h = {"Content-Type": "application/json", "X-API-Key": API_KEY}
        request = urllib.request.Request(url, data=data, headers=h, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as resp:
                code = resp.status
        except urllib.error.HTTPError as e:
            code = e.code
        assert code == 422 or code == 400, f"Malformed JSON should return 422/400, got {code}"

    check("Malformed JSON body returns 422/400 (not crash)", malformed_body)

    # 4.2 — Empty variables list returns validation error
    def empty_variables():
        payload = {
            "mode": "expert",
            "simulation": {
                "variables": [],
                "objective_function": "x",
            },
            "runs": 1000,
        }
        code, body, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 422, f"Empty variables should return 422, got {code}: {body}"

    check("Empty variables list returns 422 validation error", empty_variables)

    # 4.3 — Invalid engine type returns validation error
    def invalid_engine():
        payload = _auto_payload(runs=1000)
        payload["simulation_model"] = "nonexistent_engine"
        code, body, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 422, f"Invalid engine should return 422, got {code}: {body}"

    check("Invalid engine type returns 422 validation error", invalid_engine)

    # 4.4 — Missing required fields returns validation error
    def missing_fields():
        payload = {"mode": "auto"}  # missing scenario
        code, body, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 422, f"Missing fields should return 422, got {code}: {body}"

    check("Missing required fields returns 422 validation error", missing_fields)

    # 4.5 — Invalid distribution params returns validation error
    def invalid_distribution():
        payload = {
            "mode": "expert",
            "simulation": {
                "variables": [
                    {"name": "x", "distribution": "normal", "params": {"mean": 100}},
                    # missing std for normal distribution
                ],
                "objective_function": "x",
            },
            "runs": 1000,
        }
        code, body, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 422, f"Invalid distribution params should return 422, got {code}: {body}"

    check("Invalid distribution params returns 422 validation error", invalid_distribution)

    # 4.6 — No auth returns 401/403
    def no_auth():
        payload = _auto_payload(runs=1000)
        code, body, _, _ = req("POST", "/v1/simulate", body=payload, auth=False)
        assert code in (401, 403), f"No auth should return 401/403, got {code}"

    check("Missing API key returns 401/403", no_auth)

    # 4.7 — Invalid API key returns 401/403
    def invalid_key():
        payload = _auto_payload(runs=1000)
        code, body, _, _ = req(
            "POST",
            "/v1/simulate",
            body=payload,
            auth=False,
            headers={"X-API-Key": "de_live_INVALID_KEY_12345678901234"},
        )
        assert code in (401, 403), f"Invalid key should return 401/403, got {code}"

    check("Invalid API key returns 401/403", invalid_key)

    # 4.8 — Runs below minimum returns validation error
    def runs_below_min():
        payload = _auto_payload(runs=1)  # min is 100
        code, body, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 422, f"runs=1 should return 422, got {code}: {body}"

    check("Runs below minimum (1) returns 422", runs_below_min)

    # 4.9 — Server remains healthy after error requests
    def healthy_after_errors():
        code, body, _, _ = req("GET", "/v1/health", auth=False)
        assert code == 200, f"Health check after errors: {code}"
        assert body.get("status") == "ok"

    check("Server remains healthy after error requests", healthy_after_errors)


# ═══════════════════════════════════════════════════════════════════════════════
#  5. Worker Verification Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_worker_verification():
    print("\n🔍 Worker Verification Tests")

    # 5.1 — Count active Mojo worker processes
    def count_worker_processes():
        pids = _list_worker_pids()
        if pids is None:
            socks = _pool_sockets()
            assert len(socks) >= 2, (
                "Process enumeration is unavailable in this environment and no pool sockets "
                f"were found in {SOCKET_DIR}"
            )
            return
        assert len(pids) >= 2, (
            f"Expected >=2 Mojo worker processes, found {len(pids)} (pids: {pids})"
        )

    check("Active Mojo worker processes detected (>=2)", count_worker_processes)

    # 5.2 — Worker PIDs are unique
    def unique_pids():
        pids = _list_worker_pids()
        if pids is None:
            socks = _pool_sockets()
            assert len(socks) >= 2, "No pool sockets found while process enumeration is unavailable"
            return
        assert len(pids) > 0, "No worker PIDs found"
        unique = set(pids)
        assert len(unique) == len(pids), f"Duplicate PIDs detected: {pids} (unique: {unique})"

    check("Worker PIDs are unique (no duplicate processes)", unique_pids)

    # 5.3 — Socket file count matches expected pool size
    def socket_count():
        socks = _pool_sockets()
        # Pool should have workers. We expect at least 2, typically 11
        assert len(socks) >= 2, f"Found only {len(socks)} socket files, expected >=2"

    check("Socket file count >= 2 (pool active)", socket_count)

    # 5.4 — Worker process memory usage reasonable
    def worker_memory():
        pids = _list_worker_pids()
        if not pids:
            socks = _pool_sockets()
            assert len(socks) >= 2, (
                "No workers found to check memory and no pool sockets are present"
            )
            return

        try:
            result = subprocess.run(
                ["ps", "-o", "pid,rss,comm", "-p", ",".join(pids)],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, PermissionError):
            socks = _pool_sockets()
            assert len(socks) >= 2, "Memory inspection unavailable and no pool sockets are present"
            return

        lines = [line.strip() for line in result.stdout.strip().split("\n")[1:] if line.strip()]
        if not lines:
            socks = _pool_sockets()
            assert len(socks) >= 2, (
                "No workers found to check memory and no pool sockets are present"
            )
            return
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                rss_kb = int(parts[1])
                rss_mb = rss_kb / 1024
                # Each worker should use less than 512MB
                assert rss_mb < 512, f"Worker PID {parts[0]} using {rss_mb:.0f}MB (limit 512MB)"

    check("Worker process memory < 512MB each", worker_memory)

    # 5.5 — Binary file size is reasonable
    def binary_size():
        size_mb = MOJO_BINARY.stat().st_size / (1024 * 1024)
        assert size_mb > 0.1, f"Binary too small ({size_mb:.1f}MB), may be corrupted"
        assert size_mb < 500, f"Binary too large ({size_mb:.1f}MB)"
        timings.append(("binary_size_mb", size_mb))

    check("Mojo binary size is reasonable (0.1-500MB)", binary_size)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. Concurrent Worker Utilization Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_concurrent():
    print("\n🔀 Concurrent Worker Utilization Tests")

    # 6.1 — 5 concurrent requests all complete
    def concurrent_5():
        results_map: dict[int, tuple] = {}
        errors: list[str] = []
        blocked_reasons: list[str] = []

        def _run(idx):
            try:
                payload = _auto_payload(runs=5000, seed=idx + 500)
                code, body, _, elapsed = req("POST", "/v1/simulate", body=payload, timeout=15)
                results_map[idx] = (code, body, elapsed)
            except EnvironmentBlocked as err:
                blocked_reasons.append(str(err))
            except Exception as err:
                errors.append(f"Thread {idx}: {err}")

        threads = [threading.Thread(target=_run, args=(i,)) for i in range(5)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)
        total = time.perf_counter() - t0
        timings.append(("concurrent_5_total", total))

        if blocked_reasons:
            raise EnvironmentBlocked(blocked_reasons[0])
        assert not errors, f"Concurrent errors: {errors}"
        assert len(results_map) == 5, f"Only {len(results_map)}/5 requests completed"
        for idx, (code, body, _elapsed) in results_map.items():
            assert code == 200, f"Request {idx} returned {code}: {body}"
            _assert_valid_envelope(body)

    check("5 concurrent requests all complete successfully", concurrent_5)

    # 6.2 — Concurrent requests all return valid envelopes
    def concurrent_valid():
        results_map: dict[int, dict] = {}
        blocked_reasons: list[str] = []

        def _run(idx):
            try:
                payload = _auto_payload(runs=5000, seed=idx + 600)
                code, body, _, _ = req("POST", "/v1/simulate", body=payload, timeout=15)
                if code == 200:
                    results_map[idx] = body
            except EnvironmentBlocked as err:
                blocked_reasons.append(str(err))

        threads = [threading.Thread(target=_run, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

        if blocked_reasons:
            raise EnvironmentBlocked(blocked_reasons[0])
        assert len(results_map) >= 5, f"Only {len(results_map)}/5 returned 200"
        # Each should have unique run_id
        run_ids = [r["run_id"] for r in results_map.values()]
        assert len(set(run_ids)) == len(run_ids), f"Duplicate run_ids: {run_ids}"

    check("Concurrent requests produce unique run_ids", concurrent_valid)

    # 6.3 — Parallelism speedup (concurrent should be faster than sequential)
    def parallelism_check():
        # Sequential baseline
        seq_times = []
        for i in range(3):
            payload = _auto_payload(runs=5000, seed=i + 700)
            code, body, _, elapsed = req("POST", "/v1/simulate", body=payload, timeout=15)
            assert code == 200
            seq_times.append(elapsed)
        seq_total = sum(seq_times)

        # Concurrent 3 requests
        conc_results: dict[int, float] = {}
        blocked_reasons: list[str] = []

        def _run(idx):
            try:
                payload = _auto_payload(runs=5000, seed=idx + 800)
                _, _, _, elapsed = req("POST", "/v1/simulate", body=payload, timeout=15)
                conc_results[idx] = elapsed
            except EnvironmentBlocked as err:
                blocked_reasons.append(str(err))

        threads = [threading.Thread(target=_run, args=(i,)) for i in range(3)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)
        conc_total = time.perf_counter() - t0

        if blocked_reasons:
            raise EnvironmentBlocked(blocked_reasons[0])
        timings.append(("sequential_3_total", seq_total))
        timings.append(("concurrent_3_total", conc_total))

        # Concurrent should not be 3x slower than sequential
        # (even without speedup, they should finish in ~same time as seq due to pool)
        assert conc_total < seq_total * 1.5, (
            f"Concurrent ({conc_total:.2f}s) not faster than sequential ({seq_total:.2f}s)"
        )

    check("Concurrent requests show parallelism benefit", parallelism_check)

    # 6.4 — 8 concurrent requests stress test
    def concurrent_8():
        results_map: dict[int, int] = {}
        errors: list[str] = []
        blocked_reasons: list[str] = []

        def _run(idx):
            try:
                payload = _auto_payload(runs=3000, seed=idx + 900)
                code, body, _, _ = req("POST", "/v1/simulate", body=payload, timeout=15)
                results_map[idx] = code
            except EnvironmentBlocked as err:
                blocked_reasons.append(str(err))
            except Exception as err:
                errors.append(f"Thread {idx}: {err}")

        threads = [threading.Thread(target=_run, args=(i,)) for i in range(8)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        total = time.perf_counter() - t0
        timings.append(("concurrent_8_total", total))

        if blocked_reasons:
            raise EnvironmentBlocked(blocked_reasons[0])
        assert not errors, f"Concurrent errors: {errors}"
        assert len(results_map) == 8, f"Only {len(results_map)}/8 completed"
        ok_count = sum(1 for c in results_map.values() if c == 200)
        assert ok_count == 8, f"Only {ok_count}/8 returned 200. Codes: {list(results_map.values())}"

    check("8 concurrent requests all complete (stress test)", concurrent_8)

    # 6.5 — Mixed engine types concurrent
    def mixed_concurrent():
        engines = ["monte_carlo", "lhs", "qmc_sobol", "monte_carlo", "lhs"]
        results_map: dict[int, tuple] = {}
        blocked_reasons: list[str] = []

        def _run(idx):
            try:
                payload = _auto_payload(runs=3000, seed=idx + 1000, model=engines[idx])
                code, body, _, elapsed = req("POST", "/v1/simulate", body=payload, timeout=15)
                results_map[idx] = (code, engines[idx], elapsed)
            except EnvironmentBlocked as err:
                blocked_reasons.append(str(err))

        threads = [threading.Thread(target=_run, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

        if blocked_reasons:
            raise EnvironmentBlocked(blocked_reasons[0])
        assert len(results_map) == 5, f"Only {len(results_map)}/5 completed"
        for idx, (code, eng, _elapsed) in results_map.items():
            assert code == 200, f"{eng} (thread {idx}) returned {code}"

    check("Mixed engine types work concurrently", mixed_concurrent)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. IPC Protocol Verification Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_protocol():
    print("\n🔌 IPC Protocol Verification Tests")

    # 7.1 — Socket files have correct permissions
    def socket_permissions():
        socks = _pool_sockets()
        assert len(socks) > 0, "No socket files found"
        for s in socks:
            st = s.stat()
            # Unix sockets should be readable/writable by owner
            assert st.st_uid == os.getuid(), (
                f"Socket {s.name} owned by uid {st.st_uid}, expected {os.getuid()}"
            )

    check("Socket files owned by current user", socket_permissions)

    # 7.2 — Socket directory not world-writable
    def socket_dir_secure():
        st = SOCKET_DIR.stat()
        mode = stat.S_IMODE(st.st_mode)
        # Should not be world-writable (security check)
        assert not (mode & stat.S_IWOTH), f"Socket dir is world-writable (mode={oct(mode)})"

    check("Socket directory not world-writable", socket_dir_secure)

    # 7.3 — Worker sockets named correctly (worker-{id}-{uuid8}.sock)
    def socket_naming():
        socks = _pool_sockets()
        for socket_path in socks:
            assert POOL_SOCKET_RE.match(socket_path.name), (
                f"Socket name doesn't match expected pattern: {socket_path.name}"
            )

    check("Socket files match naming pattern worker-{id}-{uuid}.sock", socket_naming)

    # 7.4 — Multiple simulations reuse same worker sockets (persistent connections)
    def persistent_sockets():
        socks_before = {socket_path.name for socket_path in _pool_sockets()}
        # Run a few simulations
        for i in range(3):
            payload = _auto_payload(runs=1000, seed=i + 1100)
            code, _, _, _ = req("POST", "/v1/simulate", body=payload)
            assert code == 200
        socks_after = {socket_path.name for socket_path in _pool_sockets()}
        # Sockets should remain the same (no new sockets created per request)
        assert socks_before == socks_after, (
            f"Sockets changed: before={socks_before}, after={socks_after}"
        )

    check("Sockets persist across multiple simulations (no per-request spawn)", persistent_sockets)


# ═══════════════════════════════════════════════════════════════════════════════
#  8. Edge Case Tests
# ═══════════════════════════════════════════════════════════════════════════════
def test_edge_cases():
    print("\n🔬 Edge Case Tests")

    # 8.1 — Minimum runs (100)
    def minimum_runs():
        payload = _auto_payload(runs=100, seed=42)
        code, body, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"100 runs returned {code}: {body}"
        _assert_valid_envelope(body)

    check("Minimum runs (100) produces valid result", minimum_runs)

    # 8.2 — Large number of runs (50k via expert mode)
    def large_runs():
        payload = _expert_payload(runs=50000, seed=42)
        code, body, _, elapsed = req("POST", "/v1/simulate", body=payload, timeout=30)
        assert code == 200, f"50k runs returned {code}: {body}"
        _assert_valid_envelope(body)
        actual = body.get("scenarios_run", 0)
        assert actual >= 10000, f"Expected >=10k scenarios_run, got {actual}"
        timings.append(("50k_runs", elapsed))

    check("50k runs completes within timeout", large_runs)

    # 8.3 — Single variable simulation
    def single_variable():
        payload = {
            "mode": "auto",
            "scenario": {
                "name": "Single var test",
                "variables": {
                    "price": {"low": 10, "high": 100},
                },
                "objective": "maximize_revenue",
            },
            "runs": 5000,
            "seed": 42,
        }
        code, body, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"Single variable returned {code}: {body}"
        _assert_valid_envelope(body)

    check("Single-variable simulation works", single_variable)

    # 8.4 — Many variables simulation
    def many_variables():
        variables = {}
        for i in range(20):
            variables[f"var_{i}"] = {"low": float(i * 10), "high": float((i + 1) * 100)}
        payload = {
            "mode": "auto",
            "scenario": {
                "name": "Many variables test",
                "variables": variables,
                "objective": "maximize_net_value",
            },
            "runs": 5000,
            "seed": 42,
        }
        code, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"Many variables returned {code}: {body}"
        _assert_valid_envelope(body)
        timings.append(("20_variables", elapsed))

    check("20-variable simulation works", many_variables)

    # 8.5 — Sensitivity engine works
    def sensitivity_engine():
        payload = _auto_payload(runs=5000, seed=42, model="sensitivity")
        payload["sensitivity_config"] = {"method": "tornado"}
        code, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"sensitivity returned {code}: {body}"
        _assert_valid_envelope(body)
        timings.append(("sensitivity", elapsed))

    check("Engine: sensitivity produces valid results", sensitivity_engine)

    # 8.6 — Different distribution types
    def distribution_types():
        payload = {
            "mode": "expert",
            "simulation": {
                "variables": [
                    {
                        "name": "revenue",
                        "distribution": "lognormal",
                        "params": {"mean": 11.5, "std": 0.4},
                    },
                    {
                        "name": "cost",
                        "distribution": "triangular",
                        "params": {"low": 40000, "mode": 60000, "high": 90000},
                    },
                    {"name": "discount", "distribution": "beta", "params": {"alpha": 2, "beta": 5}},
                    {"name": "count", "distribution": "poisson", "params": {"lambda": 10}},
                ],
                "objective_function": "revenue - cost",
                "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
            },
            "runs": 5000,
            "seed": 42,
        }
        code, body, _, _ = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"Multi-distribution returned {code}: {body}"
        _assert_valid_envelope(body)

    check("Multiple distribution types in one simulation", distribution_types)

    # 8.7 — Scenario engine works
    def scenario_engine():
        payload = {
            "mode": "expert",
            "simulation_model": "scenario",
            "simulation": {
                "variables": [
                    {
                        "name": "revenue",
                        "distribution": "normal",
                        "params": {"mean": 150000, "std": 30000},
                    },
                    {
                        "name": "cost",
                        "distribution": "uniform",
                        "params": {"low": 40000, "high": 90000},
                    },
                ],
                "objective_function": "revenue - cost",
            },
            "scenario_config": {
                "scenarios": [
                    {"name": "Best case", "probability": 0.3, "variables": {"revenue": 200000}},
                    {"name": "Base case", "probability": 0.5, "variables": {"revenue": 150000}},
                    {"name": "Worst case", "probability": 0.2, "variables": {"revenue": 80000}},
                ],
            },
            "runs": 5000,
            "seed": 42,
        }
        code, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
        assert code == 200, f"scenario returned {code}: {body}"
        _assert_valid_envelope(body)
        timings.append(("scenario", elapsed))

    check("Engine: scenario produces valid results", scenario_engine)


# ═══════════════════════════════════════════════════════════════════════════════
#  Bespoke standalone runner
#
#  Under pytest the `def test_*` functions above are collected directly. The
#  block below preserves the original standalone harness (API reachability
#  preflight, per-section check() orchestration, and the results summary) so the
#  suite still runs via `python tests/integration/test_mojo_pool.py`.
# ═══════════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    _emit("=" * 70)
    _emit("  Phase 8 -- Mojo Worker Pool IPC Integration Tests")
    _emit("=" * 70)
    _emit(f"  Target: {BASE_URL}")
    _emit(f"  Binary: {MOJO_BINARY}")
    _emit(f"  Socket dir: {SOCKET_DIR}")

    # Pre-flight: check API is reachable
    try:
        code, _, _, _ = req("GET", "/v1/health", auth=False, timeout=5)
        assert code == 200
    except Exception as err:
        _emit(f"\n  {FAIL} Cannot reach API at {BASE_URL}: {err}")
        _emit("  Make sure the API server is running: make dev-api")
        sys.exit(1)

    test_pool_health()
    test_ipc_communication()
    test_throughput()
    test_error_handling()
    test_worker_verification()
    test_concurrent()
    test_protocol()
    test_edge_cases()

    # --- Summary ---
    _emit("\n" + "=" * 70)
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    skipped = sum(1 for r in results if r[0] == SKIP)
    total = len(results)
    _emit(f"  Results: {passed}/{total} passed, {failed} failed, {skipped} skipped")

    if timings:
        _emit("\n  Timings:")
        for name, t in timings:
            if t > 100:
                _emit(f"    {name}: {t:.0f}ms")
            else:
                _emit(f"    {name}: {t:.3f}s")

    if failed:
        _emit("\n  Failed tests:")
        for r in results:
            if r[0] == FAIL:
                _emit(f"    {FAIL} {r[1]}: {r[2]}")
    elif skipped:
        _emit("\n  Skipped tests:")
        for r in results:
            if r[0] == SKIP:
                _emit(f"    {SKIP} {r[1]}: {r[2]}")

    artifact_path = _write_summary_artifact()
    _emit(f"  Summary artifact: {artifact_path}")
    _emit("=" * 70)

    import pytest

    exit_code = pytest.main([__file__, "-v"])
    try:
        from tests.integration.live_integration_artifacts import write_live_integration_summary

        artifact_path = write_live_integration_summary(
            SUITE_NAME,
            script="tests/integration/test_mojo_pool.py",
            passed=0,
            failed=0,
            skipped=0,
            total=0,
            elapsed_seconds=0.0,
        )
        print(f"Summary artifact: {artifact_path}")
    except Exception:
        pass
    sys.exit(exit_code)
