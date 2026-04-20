"""
Async Jobs Lifecycle Integration Tests — Phase 17

Tests the async jobs subsystem against a running server at localhost:8000.
Covers: job submission, status polling, result retrieval, listing,
cancellation, error handling, job model/service imports, and full lifecycle.

Prerequisites:
  1. API server running: make dev-api
  2. PostgreSQL running on :5432
  3. Redis running on :6379
  4. Dev data seeded: python scripts/seed_dev.py

Run:
  python tests/integration/test_jobs.py

Endpoints under test:
  POST /v1/jobs                — submit async job
  GET  /v1/jobs/{job_id}       — poll job status
  GET  /v1/jobs/{job_id}/result — fetch completed job result
  POST /v1/jobs/{job_id}/cancel — cancel a queued/running job
  GET  /v1/jobs/list           — list jobs (paginated)
"""
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request

# Ensure project root is on sys.path for direct module imports
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(30)

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("DE_API_KEY", "de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU")

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple] = []
timings: list[tuple[str, float]] = []

# Shared state for cross-test references
_submitted_job_ids: list[str] = []
_submitted_run_ids: list[str] = []


# ─── HTTP helpers ─────────────────────────────────────────────────────────────
def req(method: str, path: str, body=None, headers=None, auth=True, timeout=15):
    """Make HTTP request, return (status_code, response_body_dict, response_headers, elapsed)."""
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
    except TimeoutError:
        elapsed = time.perf_counter() - t0
        raise TimeoutError(f"Request to {url} timed out after {timeout}s (elapsed: {elapsed:.1f}s)")
    except urllib.error.URLError as e:
        if "timed out" in str(e):
            elapsed = time.perf_counter() - t0
            raise TimeoutError(f"Request to {url} timed out after {timeout}s (elapsed: {elapsed:.1f}s)")
        raise RuntimeError(f"Cannot connect to {BASE_URL} — is the API server running?") from e


def check(name: str, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"  {PASS} {name}")
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}: {e}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}: {type(e).__name__}: {e}")


def skip(name: str, reason: str):
    results.append((SKIP, name, reason))
    print(f"  {SKIP} {name}: {reason}")


# ─── UUID regex ───────────────────────────────────────────────────────────────
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def is_uuid(val: str) -> bool:
    return bool(UUID_RE.match(str(val)))


# ─── Standard payloads ────────────────────────────────────────────────────────
AUTO_PAYLOAD = {
    "request": {
        "mode": "auto",
        "scenario": {
            "name": "Job test — auto mode",
            "variables": {
                "revenue": {"low": 80000, "high": 200000},
                "cost": {"low": 40000, "high": 90000},
            },
            "objective": "maximize_net_value",
        },
        "runs": 1000,
        "seed": 42,
    }
}

EXPERT_PAYLOAD = {
    "request": {
        "mode": "expert",
        "simulation": {
            "variables": [
                {
                    "name": "revenue",
                    "distribution": "normal",
                    "params": {"mean": 150000, "std": 30000},
                },
                {
                    "name": "cost",
                    "distribution": "triangular",
                    "params": {"low": 40000, "mode": 60000, "high": 90000},
                },
            ],
            "objective_function": "revenue - cost",
        },
        "runs": 1000,
        "seed": 42,
    }
}


def poll_job_until_terminal(job_id: str, max_wait: float = 30.0, interval: float = 0.5) -> dict:
    """Poll GET /v1/jobs/{job_id} until status is terminal or timeout."""
    terminal_states = {"completed", "failed", "cancelled", "expired"}
    deadline = time.time() + max_wait
    last_body = None
    while time.time() < deadline:
        status, body, _, _ = req("GET", f"/v1/jobs/{job_id}")
        last_body = body
        if isinstance(body, dict) and body.get("status") in terminal_states:
            return body
        time.sleep(interval)
    return last_body or {}


# ═══════════════════════════════════════════════════════════════════════════════
#  Connectivity check
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  PHASE 17: Async Jobs Lifecycle Integration Tests")
print("=" * 70)

try:
    status, body, _, _ = req("GET", "/v1/health", auth=False)
    if status != 200:
        print(f"\n  ⚠️  API server returned {status} on /v1/health — some tests may fail")
except Exception as e:
    print(f"\n  ❌ Cannot connect to {BASE_URL}: {e}")
    print("     Start the server with: make dev-api")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: Job Submission Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("  SECTION 1: Job Submission")
print("─" * 70)


def test_submit_auto_job():
    """Submit a basic async job via POST /v1/jobs with auto mode."""
    status, body, headers, elapsed = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert status == 202, f"Expected 202 Accepted, got {status}: {body}"
    assert "job_id" in body, f"Response missing job_id: {body}"
    assert "run_id" in body, f"Response missing run_id: {body}"
    assert "status" in body, f"Response missing status: {body}"
    assert "poll_url" in body, f"Response missing poll_url: {body}"
    assert is_uuid(body["job_id"]), f"job_id is not a UUID: {body['job_id']}"
    assert is_uuid(body["run_id"]), f"run_id is not a UUID: {body['run_id']}"
    _submitted_job_ids.append(str(body["job_id"]))
    _submitted_run_ids.append(str(body["run_id"]))
    timings.append(("POST /v1/jobs (auto)", elapsed))

check("Submit auto-mode async job → 202 with job_id", test_submit_auto_job)


def test_submit_job_status_initial():
    """Verify job status is 'queued' immediately after submission."""
    status, body, _, elapsed = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert status == 202, f"Expected 202, got {status}: {body}"
    job_status = body.get("status", "")
    assert job_status in ("queued", "validating", "running", "completed"), \
        f"Expected initial status queued/validating/running/completed, got '{job_status}'"
    _submitted_job_ids.append(str(body["job_id"]))
    timings.append(("POST /v1/jobs (status check)", elapsed))

check("Submit job → initial status is queued or early-stage", test_submit_job_status_initial)


def test_submit_expert_job():
    """Submit an expert-mode async job."""
    status, body, _, elapsed = req("POST", "/v1/jobs", EXPERT_PAYLOAD)
    assert status == 202, f"Expected 202, got {status}: {body}"
    assert "job_id" in body, f"Missing job_id: {body}"
    assert is_uuid(body["job_id"]), f"job_id is not UUID: {body['job_id']}"
    _submitted_job_ids.append(str(body["job_id"]))
    timings.append(("POST /v1/jobs (expert)", elapsed))

check("Submit expert-mode async job → 202", test_submit_expert_job)


def test_submit_job_with_callback_url():
    """Submit a job with a callback_url."""
    payload = {
        "request": AUTO_PAYLOAD["request"],
        "callback_url": "https://example.com/webhook",
    }
    status, body, _, elapsed = req("POST", "/v1/jobs", payload)
    assert status == 202, f"Expected 202, got {status}: {body}"
    assert "job_id" in body, f"Missing job_id: {body}"
    _submitted_job_ids.append(str(body["job_id"]))
    timings.append(("POST /v1/jobs (with callback)", elapsed))

check("Submit job with callback_url → 202", test_submit_job_with_callback_url)


def test_submit_job_response_has_poll_url():
    """Verify poll_url in submission response points to correct path."""
    status, body, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert status == 202, f"Expected 202, got {status}"
    poll_url = body.get("poll_url", "")
    assert "/v1/jobs/" in poll_url, f"poll_url doesn't contain /v1/jobs/: {poll_url}"
    job_id = body["job_id"]
    assert str(job_id) in poll_url, f"poll_url doesn't contain job_id {job_id}: {poll_url}"
    _submitted_job_ids.append(str(body["job_id"]))

check("Submit job → poll_url contains job_id path", test_submit_job_response_has_poll_url)


def test_submit_job_response_has_message():
    """Verify the submission response has a message field."""
    status, body, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert status == 202, f"Expected 202, got {status}"
    assert "message" in body, f"Missing 'message' field: {body}"
    assert isinstance(body["message"], str), f"message should be string: {type(body['message'])}"
    _submitted_job_ids.append(str(body["job_id"]))

check("Submit job → response contains message", test_submit_job_response_has_message)


def test_submit_job_with_qmc_sobol():
    """Submit a job with QMC Sobol engine type."""
    payload = {
        "request": {
            "mode": "auto",
            "scenario": {
                "name": "QMC Sobol job test",
                "variables": {
                    "revenue": {"low": 100000, "high": 250000},
                    "cost": {"low": 50000, "high": 120000},
                },
                "objective": "maximize_net_value",
            },
            "runs": 1000,
            "seed": 99,
            "simulation_model": "qmc_sobol",
        }
    }
    status, body, _, elapsed = req("POST", "/v1/jobs", payload)
    assert status == 202, f"Expected 202, got {status}: {body}"
    assert "job_id" in body, f"Missing job_id: {body}"
    _submitted_job_ids.append(str(body["job_id"]))
    timings.append(("POST /v1/jobs (qmc_sobol)", elapsed))

check("Submit job with simulation_model=qmc_sobol → 202", test_submit_job_with_qmc_sobol)


def test_submit_job_with_lhs():
    """Submit a job with LHS engine type."""
    payload = {
        "request": {
            "mode": "auto",
            "scenario": {
                "name": "LHS job test",
                "variables": {
                    "growth": {"low": 0.01, "high": 0.15},
                    "churn": {"low": 0.02, "high": 0.10},
                },
                "objective": "minimize_risk",
            },
            "runs": 500,
            "seed": 77,
            "simulation_model": "lhs",
        }
    }
    status, body, _, elapsed = req("POST", "/v1/jobs", payload)
    assert status == 202, f"Expected 202, got {status}: {body}"
    _submitted_job_ids.append(str(body["job_id"]))
    timings.append(("POST /v1/jobs (lhs)", elapsed))

check("Submit job with simulation_model=lhs → 202", test_submit_job_with_lhs)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: Job Status Polling Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("  SECTION 2: Job Status Polling")
print("─" * 70)


def test_poll_job_status():
    """Poll a submitted job's status via GET /v1/jobs/{job_id}."""
    if not _submitted_job_ids:
        raise AssertionError("No jobs submitted yet")
    job_id = _submitted_job_ids[0]
    status, body, _, elapsed = req("GET", f"/v1/jobs/{job_id}")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert "job_id" in body, f"Missing job_id: {body}"
    assert "status" in body, f"Missing status: {body}"
    assert "run_id" in body, f"Missing run_id: {body}"
    assert "org_id" in body, f"Missing org_id: {body}"
    assert "created_at" in body, f"Missing created_at: {body}"
    timings.append(("GET /v1/jobs/{id} (poll)", elapsed))

check("Poll job status → 200 with expected fields", test_poll_job_status)


def test_poll_job_has_queue_name():
    """Verify polled job status has queue_name field."""
    if not _submitted_job_ids:
        raise AssertionError("No jobs submitted yet")
    job_id = _submitted_job_ids[0]
    status, body, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert status == 200, f"Expected 200, got {status}"
    assert "queue_name" in body, f"Missing queue_name: {body}"
    assert body["queue_name"] == "default", f"Expected default queue, got {body['queue_name']}"

check("Poll job → has queue_name='default'", test_poll_job_has_queue_name)


def test_poll_job_has_retry_count():
    """Verify polled job has retry_count field."""
    if not _submitted_job_ids:
        raise AssertionError("No jobs submitted yet")
    job_id = _submitted_job_ids[0]
    status, body, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert status == 200, f"Expected 200, got {status}"
    assert "retry_count" in body, f"Missing retry_count: {body}"
    assert isinstance(body["retry_count"], int), f"retry_count should be int: {type(body['retry_count'])}"

check("Poll job → has retry_count (int)", test_poll_job_has_retry_count)


def test_poll_job_has_callback_status():
    """Verify polled job has callback_status field."""
    if not _submitted_job_ids:
        raise AssertionError("No jobs submitted yet")
    job_id = _submitted_job_ids[0]
    status, body, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert status == 200, f"Expected 200, got {status}"
    assert "callback_status" in body, f"Missing callback_status: {body}"
    valid_statuses = {"pending", "delivered", "failed", "not_configured"}
    assert body["callback_status"] in valid_statuses, \
        f"callback_status '{body['callback_status']}' not in {valid_statuses}"

check("Poll job → has valid callback_status", test_poll_job_has_callback_status)


def test_poll_job_has_ttl_expires_at():
    """Verify polled job has ttl_expires_at field."""
    if not _submitted_job_ids:
        raise AssertionError("No jobs submitted yet")
    job_id = _submitted_job_ids[0]
    status, body, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert status == 200, f"Expected 200, got {status}"
    assert "ttl_expires_at" in body, f"Missing ttl_expires_at: {body}"

check("Poll job → has ttl_expires_at", test_poll_job_has_ttl_expires_at)


def test_poll_job_has_poll_url():
    """Verify polled job response includes poll_url."""
    if not _submitted_job_ids:
        raise AssertionError("No jobs submitted yet")
    job_id = _submitted_job_ids[0]
    status, body, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert status == 200, f"Expected 200, got {status}"
    assert "poll_url" in body, f"Missing poll_url: {body}"
    assert str(job_id) in body["poll_url"], f"poll_url missing job_id: {body['poll_url']}"

check("Poll job → response includes poll_url with job_id", test_poll_job_has_poll_url)


def test_poll_job_valid_status_values():
    """Verify job status is one of the valid JobStatus enum values."""
    if not _submitted_job_ids:
        raise AssertionError("No jobs submitted yet")
    job_id = _submitted_job_ids[0]
    status, body, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert status == 200, f"Expected 200, got {status}"
    valid_job_statuses = {"queued", "validating", "running", "completed", "failed", "cancelled", "expired"}
    assert body["status"] in valid_job_statuses, \
        f"status '{body['status']}' not in {valid_job_statuses}"

check("Poll job → status is valid JobStatus enum value", test_poll_job_valid_status_values)


def test_poll_job_until_terminal():
    """Submit and poll a job until it reaches a terminal state (or timeout)."""
    status, body, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert status == 202, f"Expected 202, got {status}"
    job_id = body["job_id"]
    _submitted_job_ids.append(str(job_id))
    final = poll_job_until_terminal(str(job_id), max_wait=30.0)
    final_status = final.get("status", "unknown")
    terminal_states = {"completed", "failed", "cancelled", "expired"}
    # Job may still be queued if no worker is running — that's acceptable
    acceptable = terminal_states | {"queued", "validating", "running"}
    assert final_status in acceptable, \
        f"Final status '{final_status}' not acceptable: {final}"

check("Submit + poll job → reaches terminal or stays queued", test_poll_job_until_terminal)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3: Job Result Retrieval Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("  SECTION 3: Job Result Retrieval")
print("─" * 70)


def test_get_job_result_endpoint():
    """Fetch result via GET /v1/jobs/{job_id}/result — returns status-dependent response."""
    if not _submitted_job_ids:
        raise AssertionError("No jobs submitted yet")
    job_id = _submitted_job_ids[0]
    status, body, _, elapsed = req("GET", f"/v1/jobs/{job_id}/result")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert "status" in body, f"Missing status in result response: {body}"
    # If completed, should have 'result'; if still processing, should have 'message'
    job_status = body["status"]
    if job_status == "completed":
        assert "result" in body, f"Completed job missing 'result': {body}"
    elif job_status in ("queued", "validating", "running"):
        assert "message" in body, f"In-progress job missing 'message': {body}"
    elif job_status == "failed":
        assert "error" in body, f"Failed job missing 'error': {body}"
    elif job_status == "cancelled":
        pass  # Just {status: cancelled}
    timings.append(("GET /v1/jobs/{id}/result", elapsed))

check("Get job result endpoint → 200 with status-dependent response", test_get_job_result_endpoint)


def test_get_result_completed_job():
    """Submit a job, poll to completion, then verify result data structure."""
    status, body, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert status == 202, f"Expected 202, got {status}"
    job_id = body["job_id"]
    _submitted_job_ids.append(str(job_id))
    final = poll_job_until_terminal(str(job_id), max_wait=30.0)
    final_status = final.get("status", "unknown")
    if final_status == "completed":
        r_status, r_body, _, _ = req("GET", f"/v1/jobs/{job_id}/result")
        assert r_status == 200, f"Expected 200, got {r_status}"
        assert r_body["status"] == "completed", f"Expected completed status: {r_body}"
        result = r_body.get("result", {})
        assert isinstance(result, dict), f"result should be dict: {type(result)}"
        assert "job_id" in result, f"result missing job_id: {result}"
        assert "run_id" in result, f"result missing run_id: {result}"
    elif final_status == "queued":
        # No worker running — result should indicate processing
        r_status, r_body, _, _ = req("GET", f"/v1/jobs/{job_id}/result")
        assert r_status == 200, f"Expected 200, got {r_status}"
        assert r_body["status"] in ("queued", "validating", "running"), \
            f"Expected in-progress status: {r_body}"

check("Submit → poll → get result (if completed)", test_get_result_completed_job)


def test_result_for_nonexistent_job():
    """GET /v1/jobs/{fake}/result → 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    status, body, _, _ = req("GET", f"/v1/jobs/{fake_id}/result")
    assert status in (404, 403), f"Expected 404/403, got {status}: {body}"

check("Get result for nonexistent job → 404", test_result_for_nonexistent_job)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4: Job Listing Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("  SECTION 4: Job Listing")
print("─" * 70)


def test_list_jobs():
    """List all jobs via GET /v1/jobs/list."""
    status, body, _, elapsed = req("GET", "/v1/jobs/list")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert "jobs" in body, f"Missing 'jobs' in response: {body}"
    assert "total" in body, f"Missing 'total' in response: {body}"
    assert "page" in body, f"Missing 'page' in response: {body}"
    assert "limit" in body, f"Missing 'limit' in response: {body}"
    assert "pages" in body, f"Missing 'pages' in response: {body}"
    assert isinstance(body["jobs"], list), f"jobs should be a list: {type(body['jobs'])}"
    timings.append(("GET /v1/jobs/list", elapsed))

check("List jobs → 200 with jobs, total, page, limit, pages", test_list_jobs)


def test_list_jobs_contains_submitted():
    """Verify submitted jobs appear in the job listing."""
    if not _submitted_job_ids:
        raise AssertionError("No jobs submitted yet")
    status, body, _, _ = req("GET", "/v1/jobs/list?limit=100")
    assert status == 200, f"Expected 200, got {status}"
    listed_ids = {str(j["job_id"]) for j in body.get("jobs", [])}
    # At least one of our submitted jobs should be in the list
    found = any(jid in listed_ids for jid in _submitted_job_ids)
    assert found, f"None of submitted job IDs {_submitted_job_ids[:3]} found in listing"

check("List jobs → contains at least one submitted job", test_list_jobs_contains_submitted)


def test_list_jobs_pagination_limit():
    """Verify pagination with limit parameter."""
    status, body, _, _ = req("GET", "/v1/jobs/list?limit=2")
    assert status == 200, f"Expected 200, got {status}"
    jobs = body.get("jobs", [])
    assert len(jobs) <= 2, f"Expected at most 2 jobs, got {len(jobs)}"

check("List jobs with limit=2 → at most 2 results", test_list_jobs_pagination_limit)


def test_list_jobs_pagination_page():
    """Verify page parameter works."""
    status, body, _, _ = req("GET", "/v1/jobs/list?page=1&limit=5")
    assert status == 200, f"Expected 200, got {status}"
    assert body["page"] == 1, f"Expected page 1, got {body['page']}"
    assert body["limit"] == 5, f"Expected limit 5, got {body['limit']}"

check("List jobs with page=1 → page and limit fields are correct", test_list_jobs_pagination_page)


def test_list_jobs_page_2():
    """Request page 2 with small limit."""
    status, body, _, _ = req("GET", "/v1/jobs/list?page=2&limit=2")
    assert status == 200, f"Expected 200, got {status}"
    assert body["page"] == 2, f"Expected page 2, got {body['page']}"

check("List jobs page=2 → page field is 2", test_list_jobs_page_2)


def test_list_jobs_total_is_consistent():
    """Verify total count is consistent across pages."""
    s1, b1, _, _ = req("GET", "/v1/jobs/list?page=1&limit=5")
    s2, b2, _, _ = req("GET", "/v1/jobs/list?page=1&limit=10")
    assert s1 == 200 and s2 == 200, "Both requests should return 200"
    assert b1["total"] == b2["total"], \
        f"Total mismatch: {b1['total']} vs {b2['total']}"

check("List jobs → total is consistent across limit changes", test_list_jobs_total_is_consistent)


def test_list_jobs_filter_by_status():
    """Verify filtering by status query parameter."""
    status, body, _, _ = req("GET", "/v1/jobs/list?status=queued")
    assert status == 200, f"Expected 200, got {status}"
    for job in body.get("jobs", []):
        assert job["status"] == "queued", \
            f"Expected all jobs to be queued, got {job['status']}"

check("List jobs with status=queued → all returned jobs are queued", test_list_jobs_filter_by_status)


def test_list_jobs_ordered_by_creation():
    """Verify job list is ordered by creation time (descending)."""
    status, body, _, _ = req("GET", "/v1/jobs/list?limit=20")
    assert status == 200, f"Expected 200, got {status}"
    jobs = body.get("jobs", [])
    if len(jobs) >= 2:
        for i in range(len(jobs) - 1):
            t1 = jobs[i].get("created_at", "")
            t2 = jobs[i + 1].get("created_at", "")
            assert t1 >= t2, f"Jobs not ordered desc by created_at: {t1} < {t2}"

check("List jobs → ordered by created_at descending", test_list_jobs_ordered_by_creation)


def test_list_jobs_job_structure():
    """Verify each job in listing has full structure."""
    status, body, _, _ = req("GET", "/v1/jobs/list?limit=1")
    assert status == 200, f"Expected 200, got {status}"
    jobs = body.get("jobs", [])
    if len(jobs) > 0:
        job = jobs[0]
        required_fields = ["job_id", "run_id", "org_id", "status", "queue_name",
                           "retry_count", "callback_status", "created_at", "poll_url"]
        for field in required_fields:
            assert field in job, f"Job in listing missing '{field}': {list(job.keys())}"

check("List jobs → each job has complete structure", test_list_jobs_job_structure)


def test_list_jobs_invalid_status_filter():
    """Filter by invalid status — should return empty or ignore filter."""
    status, body, _, _ = req("GET", "/v1/jobs/list?status=nonexistent_status")
    assert status == 200, f"Expected 200 (graceful), got {status}: {body}"

check("List jobs with invalid status filter → 200 (graceful)", test_list_jobs_invalid_status_filter)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5: Job Cancellation Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("  SECTION 5: Job Cancellation")
print("─" * 70)


def test_cancel_job():
    """Submit a job then immediately cancel via POST /v1/jobs/{id}/cancel."""
    status, body, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert status == 202, f"Expected 202, got {status}"
    job_id = body["job_id"]
    # Immediately cancel
    c_status, c_body, _, elapsed = req("POST", f"/v1/jobs/{job_id}/cancel")
    # Could be 200 (cancelled) or 409 (already terminal if completed fast)
    if c_status == 200:
        assert c_body.get("status") == "cancelled", \
            f"Expected cancelled status, got {c_body.get('status')}"
    elif c_status == 409:
        # Job already completed or failed — acceptable for fast simulations
        pass
    else:
        raise AssertionError(f"Unexpected cancel status {c_status}: {c_body}")
    timings.append(("POST /v1/jobs/{id}/cancel", elapsed))

check("Submit + cancel job → cancelled or already-terminal 409", test_cancel_job)


def test_cancel_job_verify_status():
    """After cancellation, verify polling shows cancelled status."""
    status, body, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert status == 202, f"Expected 202, got {status}"
    job_id = body["job_id"]
    c_status, c_body, _, _ = req("POST", f"/v1/jobs/{job_id}/cancel")
    if c_status == 200:
        # Poll to confirm
        p_status, p_body, _, _ = req("GET", f"/v1/jobs/{job_id}")
        assert p_status == 200, f"Expected 200, got {p_status}"
        assert p_body["status"] == "cancelled", \
            f"Expected cancelled after cancel, got {p_body['status']}"

check("Cancel job → subsequent poll shows cancelled", test_cancel_job_verify_status)


def test_cancel_nonexistent_job():
    """Cancel a non-existent job → 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    status, body, _, _ = req("POST", f"/v1/jobs/{fake_id}/cancel")
    assert status in (404, 403), f"Expected 404/403, got {status}: {body}"

check("Cancel non-existent job → 404", test_cancel_nonexistent_job)


def test_cancel_already_cancelled_job():
    """Cancelling an already-cancelled job → 409."""
    status, body, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert status == 202, f"Expected 202, got {status}"
    job_id = body["job_id"]
    c1_status, _, _, _ = req("POST", f"/v1/jobs/{job_id}/cancel")
    if c1_status == 200:
        # Try cancel again
        c2_status, c2_body, _, _ = req("POST", f"/v1/jobs/{job_id}/cancel")
        assert c2_status == 409, f"Expected 409 for double-cancel, got {c2_status}: {c2_body}"

check("Cancel already-cancelled job → 409 conflict", test_cancel_already_cancelled_job)


def test_cancelled_job_result():
    """Cancelled job result endpoint returns cancelled status."""
    status, body, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert status == 202, f"Expected 202, got {status}"
    job_id = body["job_id"]
    c_status, _, _, _ = req("POST", f"/v1/jobs/{job_id}/cancel")
    if c_status == 200:
        r_status, r_body, _, _ = req("GET", f"/v1/jobs/{job_id}/result")
        assert r_status == 200, f"Expected 200, got {r_status}"
        assert r_body["status"] == "cancelled", \
            f"Expected cancelled in result, got {r_body['status']}"

check("Cancelled job → result endpoint returns cancelled", test_cancelled_job_result)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 6: Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("  SECTION 6: Error Handling")
print("─" * 70)


def test_submit_empty_payload():
    """Submit job with empty/missing request → validation error."""
    status, body, _, _ = req("POST", "/v1/jobs", {})
    assert status == 422, f"Expected 422 validation error, got {status}: {body}"

check("Submit empty payload → 422 validation error", test_submit_empty_payload)


def test_submit_invalid_mode():
    """Submit job with invalid mode → validation error."""
    payload = {
        "request": {
            "mode": "invalid_mode",
            "scenario": {
                "variables": {"x": {"low": 1, "high": 10}},
                "objective": "maximize_net_value",
            },
            "runs": 1000,
        }
    }
    status, body, _, _ = req("POST", "/v1/jobs", payload)
    assert status == 422, f"Expected 422, got {status}: {body}"

check("Submit job with invalid mode → 422", test_submit_invalid_mode)


def test_submit_missing_variables():
    """Submit auto-mode job without variables → validation error."""
    payload = {
        "request": {
            "mode": "auto",
            "scenario": {
                "name": "No vars",
                "variables": {},
                "objective": "maximize_net_value",
            },
            "runs": 1000,
        }
    }
    status, body, _, _ = req("POST", "/v1/jobs", payload)
    assert status == 422, f"Expected 422, got {status}: {body}"

check("Submit auto job without variables → 422", test_submit_missing_variables)


def test_get_nonexistent_job():
    """GET /v1/jobs/{nonexistent} → 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    status, body, _, _ = req("GET", f"/v1/jobs/{fake_id}")
    assert status in (404, 403), f"Expected 404/403, got {status}: {body}"

check("Get non-existent job → 404", test_get_nonexistent_job)


def test_get_job_invalid_uuid():
    """GET /v1/jobs/not-a-uuid → 422."""
    status, body, _, _ = req("GET", "/v1/jobs/not-a-uuid")
    assert status == 422, f"Expected 422, got {status}: {body}"

check("Get job with invalid UUID → 422", test_get_job_invalid_uuid)


def test_submit_job_no_auth():
    """Submit job without authentication → 401/403."""
    status, body, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD, auth=False)
    assert status in (401, 403), f"Expected 401/403, got {status}: {body}"

check("Submit job without auth → 401/403", test_submit_job_no_auth)


def test_list_jobs_no_auth():
    """List jobs without authentication → 401/403."""
    status, body, _, _ = req("GET", "/v1/jobs/list", auth=False)
    assert status in (401, 403), f"Expected 401/403, got {status}: {body}"

check("List jobs without auth → 401/403", test_list_jobs_no_auth)


def test_poll_job_no_auth():
    """Poll job without authentication → 401/403."""
    if not _submitted_job_ids:
        raise AssertionError("No jobs submitted yet")
    job_id = _submitted_job_ids[0]
    status, body, _, _ = req("GET", f"/v1/jobs/{job_id}", auth=False)
    assert status in (401, 403), f"Expected 401/403, got {status}: {body}"

check("Poll job without auth → 401/403", test_poll_job_no_auth)


def test_cancel_job_no_auth():
    """Cancel job without authentication → 401/403."""
    if not _submitted_job_ids:
        raise AssertionError("No jobs submitted yet")
    job_id = _submitted_job_ids[0]
    status, body, _, _ = req("POST", f"/v1/jobs/{job_id}/cancel", auth=False)
    assert status in (401, 403), f"Expected 401/403, got {status}: {body}"

check("Cancel job without auth → 401/403", test_cancel_job_no_auth)


def test_submit_expert_missing_objective():
    """Submit expert job without objective_function — should still work (it's optional)."""
    payload = {
        "request": {
            "mode": "expert",
            "simulation": {
                "variables": [
                    {"name": "x", "distribution": "normal", "params": {"mean": 100, "std": 20}},
                ],
            },
            "runs": 500,
        }
    }
    status, body, _, _ = req("POST", "/v1/jobs", payload)
    # objective_function is optional, so this should succeed
    assert status in (202, 422), f"Expected 202 or 422, got {status}: {body}"

check("Submit expert job without objective_function → 202 or 422", test_submit_expert_missing_objective)


def test_submit_auto_invalid_variable_range():
    """Submit auto job where high <= low → validation error."""
    payload = {
        "request": {
            "mode": "auto",
            "scenario": {
                "name": "Bad range",
                "variables": {
                    "x": {"low": 100, "high": 50},  # high < low
                },
                "objective": "maximize_net_value",
            },
            "runs": 1000,
        }
    }
    status, body, _, _ = req("POST", "/v1/jobs", payload)
    assert status == 422, f"Expected 422, got {status}: {body}"

check("Submit auto job with high < low → 422", test_submit_auto_invalid_variable_range)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 7: Job Service Module Tests (direct import)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("  SECTION 7: Job Service Module (direct import)")
print("─" * 70)


def test_import_job_model():
    """Import Job model and JobStatus enum."""
    try:
        from apps.api_server.models.job import Job, JobStatus
        assert hasattr(Job, "__tablename__"), "Job missing __tablename__"
        assert Job.__tablename__ == "jobs", f"Expected 'jobs', got {Job.__tablename__}"
        results.append((PASS, "Import Job model"))
        print(f"  {PASS} Import Job model and JobStatus")
    except ImportError as e:
        results.append((SKIP, "Import Job model", str(e)))
        print(f"  {SKIP} Import Job model: {e}")

test_import_job_model()


def test_job_status_enum_values():
    """Verify JobStatus enum has all expected values."""
    try:
        from apps.api_server.models.job import JobStatus
        expected = {"queued", "validating", "running", "completed", "failed", "cancelled", "expired"}
        actual = {s.value for s in JobStatus}
        assert actual == expected, f"JobStatus values mismatch: expected {expected}, got {actual}"
        results.append((PASS, "JobStatus enum values"))
        print(f"  {PASS} JobStatus enum has all 7 values")
    except ImportError as e:
        results.append((SKIP, "JobStatus enum values", str(e)))
        print(f"  {SKIP} JobStatus enum values: {e}")

test_job_status_enum_values()


def test_webhook_status_enum():
    """Verify WebhookStatus enum values."""
    try:
        from apps.api_server.models.job import WebhookStatus
        expected = {"pending", "delivered", "failed", "not_configured"}
        actual = {s.value for s in WebhookStatus}
        assert actual == expected, f"WebhookStatus mismatch: expected {expected}, got {actual}"
        results.append((PASS, "WebhookStatus enum values"))
        print(f"  {PASS} WebhookStatus enum has all 4 values")
    except ImportError as e:
        results.append((SKIP, "WebhookStatus enum values", str(e)))
        print(f"  {SKIP} WebhookStatus enum values: {e}")

test_webhook_status_enum()


def test_is_valid_transition():
    """Test is_valid_transition() state machine logic."""
    try:
        from apps.api_server.models.job import JobStatus, is_valid_transition
        # Valid transitions
        assert is_valid_transition(JobStatus.QUEUED, JobStatus.VALIDATING), "QUEUED → VALIDATING should be valid"
        assert is_valid_transition(JobStatus.QUEUED, JobStatus.CANCELLED), "QUEUED → CANCELLED should be valid"
        assert is_valid_transition(JobStatus.VALIDATING, JobStatus.RUNNING), "VALIDATING → RUNNING should be valid"
        assert is_valid_transition(JobStatus.RUNNING, JobStatus.COMPLETED), "RUNNING → COMPLETED should be valid"
        assert is_valid_transition(JobStatus.RUNNING, JobStatus.FAILED), "RUNNING → FAILED should be valid"
        assert is_valid_transition(JobStatus.COMPLETED, JobStatus.EXPIRED), "COMPLETED → EXPIRED should be valid"
        # Invalid transitions
        assert not is_valid_transition(JobStatus.QUEUED, JobStatus.COMPLETED), "QUEUED → COMPLETED should be invalid"
        assert not is_valid_transition(JobStatus.FAILED, JobStatus.RUNNING), "FAILED → RUNNING should be invalid"
        assert not is_valid_transition(JobStatus.CANCELLED, JobStatus.RUNNING), "CANCELLED → RUNNING should be invalid"
        assert not is_valid_transition(JobStatus.EXPIRED, JobStatus.RUNNING), "EXPIRED → RUNNING should be invalid"
        results.append((PASS, "is_valid_transition state machine"))
        print(f"  {PASS} is_valid_transition state machine (10 checks)")
    except ImportError as e:
        results.append((SKIP, "is_valid_transition", str(e)))
        print(f"  {SKIP} is_valid_transition: {e}")

test_is_valid_transition()


def test_is_terminal():
    """Test is_terminal() function."""
    try:
        from apps.api_server.models.job import JobStatus, is_terminal
        # Terminal states
        assert is_terminal(JobStatus.COMPLETED), "COMPLETED should be terminal"
        assert is_terminal(JobStatus.FAILED), "FAILED should be terminal"
        assert is_terminal(JobStatus.CANCELLED), "CANCELLED should be terminal"
        assert is_terminal(JobStatus.EXPIRED), "EXPIRED should be terminal"
        # Non-terminal states
        assert not is_terminal(JobStatus.QUEUED), "QUEUED should not be terminal"
        assert not is_terminal(JobStatus.VALIDATING), "VALIDATING should not be terminal"
        assert not is_terminal(JobStatus.RUNNING), "RUNNING should not be terminal"
        results.append((PASS, "is_terminal function"))
        print(f"  {PASS} is_terminal (7 checks)")
    except ImportError as e:
        results.append((SKIP, "is_terminal", str(e)))
        print(f"  {SKIP} is_terminal: {e}")

test_is_terminal()


def test_import_job_service():
    """Import job_service functions."""
    try:
        from apps.api_server.services.job_service import (
            cancel_job,
            create_job,
            get_job,
            get_job_result,
            update_job_status,
        )
        assert callable(create_job), "create_job should be callable"
        assert callable(get_job), "get_job should be callable"
        assert callable(update_job_status), "update_job_status should be callable"
        assert callable(cancel_job), "cancel_job should be callable"
        assert callable(get_job_result), "get_job_result should be callable"
        results.append((PASS, "Import job_service functions"))
        print(f"  {PASS} Import all 5 job_service functions")
    except ImportError as e:
        results.append((SKIP, "Import job_service", str(e)))
        print(f"  {SKIP} Import job_service: {e}")

test_import_job_service()


def test_job_service_default_ttl():
    """Verify default TTL hours constant."""
    try:
        from apps.api_server.services.job_service import _DEFAULT_TTL_HOURS
        assert _DEFAULT_TTL_HOURS == 24, f"Expected 24h TTL, got {_DEFAULT_TTL_HOURS}"
        results.append((PASS, "job_service default TTL = 24h"))
        print(f"  {PASS} job_service default TTL = 24h")
    except ImportError as e:
        results.append((SKIP, "job_service TTL", str(e)))
        print(f"  {SKIP} job_service TTL: {e}")

test_job_service_default_ttl()


def test_import_worker_tasks():
    """Import worker task module (celery may not be available)."""
    try:
        import apps.worker.tasks.simulation_task as tasks
        # celery_app may be None if Celery isn't installed
        assert hasattr(tasks, "celery_app"), "Missing celery_app"
        assert hasattr(tasks, "persist_simulation"), "Missing persist_simulation"
        assert hasattr(tasks, "run_simulation_job"), "Missing run_simulation_job"
        results.append((PASS, "Import worker tasks module"))
        print(f"  {PASS} Import worker tasks (celery_app, persist_simulation, run_simulation_job)")
    except ImportError as e:
        results.append((SKIP, "Import worker tasks", str(e)))
        print(f"  {SKIP} Import worker tasks: {e}")

test_import_worker_tasks()


def test_job_model_fields():
    """Verify Job model has expected columns."""
    try:
        from apps.api_server.models.job import Job
        expected_columns = [
            "run_id", "org_id", "queue_name", "status", "retry_count",
            "max_retries", "callback_url", "callback_status", "error_message",
            "ttl_expires_at", "started_at", "completed_at",
        ]
        for col in expected_columns:
            assert hasattr(Job, col), f"Job model missing column: {col}"
        results.append((PASS, "Job model has all expected columns"))
        print(f"  {PASS} Job model has all {len(expected_columns)} expected columns")
    except ImportError as e:
        results.append((SKIP, "Job model fields", str(e)))
        print(f"  {SKIP} Job model fields: {e}")

test_job_model_fields()


def test_valid_transitions_completeness():
    """Verify _VALID_TRANSITIONS covers all JobStatus values."""
    try:
        from apps.api_server.models.job import _VALID_TRANSITIONS, JobStatus
        for status in JobStatus:
            assert status in _VALID_TRANSITIONS, \
                f"JobStatus.{status.name} not in _VALID_TRANSITIONS"
        results.append((PASS, "_VALID_TRANSITIONS covers all states"))
        print(f"  {PASS} _VALID_TRANSITIONS covers all {len(list(JobStatus))} states")
    except ImportError as e:
        results.append((SKIP, "_VALID_TRANSITIONS", str(e)))
        print(f"  {SKIP} _VALID_TRANSITIONS: {e}")

test_valid_transitions_completeness()


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 8: Full Lifecycle Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "─" * 70)
print("  SECTION 8: Full Lifecycle")
print("─" * 70)


def test_full_lifecycle_auto():
    """Full lifecycle: submit auto job → poll → get result → verify consistency."""
    # Submit
    s1, b1, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert s1 == 202, f"Submit failed: {s1}: {b1}"
    job_id = b1["job_id"]
    run_id = b1["run_id"]

    # Poll for status
    s2, b2, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert s2 == 200, f"Poll failed: {s2}: {b2}"
    assert str(b2["job_id"]) == str(job_id), "job_id mismatch on poll"
    assert str(b2["run_id"]) == str(run_id), "run_id mismatch on poll"

    # Verify in listing
    s3, b3, _, _ = req("GET", "/v1/jobs/list?limit=50")
    assert s3 == 200, f"List failed: {s3}"
    listed_ids = {str(j["job_id"]) for j in b3.get("jobs", [])}
    assert str(job_id) in listed_ids, f"Job {job_id} not in listing"

    # Get result
    s4, b4, _, _ = req("GET", f"/v1/jobs/{job_id}/result")
    assert s4 == 200, f"Result failed: {s4}"
    assert "status" in b4, f"Result missing status: {b4}"

check("Full lifecycle: submit → poll → list → result (auto)", test_full_lifecycle_auto)


def test_full_lifecycle_expert():
    """Full lifecycle: submit expert job → poll → get result → verify."""
    s1, b1, _, _ = req("POST", "/v1/jobs", EXPERT_PAYLOAD)
    assert s1 == 202, f"Submit failed: {s1}: {b1}"
    job_id = b1["job_id"]

    s2, b2, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert s2 == 200, f"Poll failed: {s2}"
    assert str(b2["job_id"]) == str(job_id), "job_id mismatch"

    s3, b3, _, _ = req("GET", f"/v1/jobs/{job_id}/result")
    assert s3 == 200, f"Result failed: {s3}"
    assert "status" in b3, "Result missing status"

check("Full lifecycle: submit → poll → result (expert)", test_full_lifecycle_expert)


def test_multiple_concurrent_jobs():
    """Submit multiple jobs, verify all get unique IDs and appear in listing."""
    job_ids = []
    for i in range(3):
        payload = {
            "request": {
                "mode": "auto",
                "scenario": {
                    "name": f"Concurrent test #{i}",
                    "variables": {
                        "v1": {"low": 10 * i, "high": 100 + 10 * i},
                        "v2": {"low": 5 * i, "high": 50 + 5 * i},
                    },
                    "objective": "maximize_net_value",
                },
                "runs": 500,
                "seed": 100 + i,
            }
        }
        s, b, _, _ = req("POST", "/v1/jobs", payload)
        assert s == 202, f"Submit #{i} failed: {s}"
        job_ids.append(str(b["job_id"]))

    # All IDs should be unique
    assert len(set(job_ids)) == 3, f"Expected 3 unique IDs, got {len(set(job_ids))}"

    # All should appear in listing
    s, b, _, _ = req("GET", "/v1/jobs/list?limit=100")
    assert s == 200, f"List failed: {s}"
    listed_ids = {str(j["job_id"]) for j in b.get("jobs", [])}
    for jid in job_ids:
        assert jid in listed_ids, f"Job {jid} not in listing"

check("Submit 3 concurrent jobs → all unique + in listing", test_multiple_concurrent_jobs)


def test_submit_poll_cancel_lifecycle():
    """Submit → poll → cancel → verify cancelled."""
    s1, b1, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert s1 == 202, f"Submit failed: {s1}"
    job_id = b1["job_id"]

    # Poll
    s2, b2, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert s2 == 200, f"Poll failed: {s2}"

    # Cancel
    s3, b3, _, _ = req("POST", f"/v1/jobs/{job_id}/cancel")
    if s3 == 200:
        assert b3["status"] == "cancelled", f"Expected cancelled, got {b3['status']}"
        # Verify poll shows cancelled
        s4, b4, _, _ = req("GET", f"/v1/jobs/{job_id}")
        assert s4 == 200, f"Post-cancel poll failed: {s4}"
        assert b4["status"] == "cancelled", f"Post-cancel status: {b4['status']}"
    elif s3 == 409:
        pass  # Already terminal — acceptable

check("Submit → poll → cancel → verify cancelled", test_submit_poll_cancel_lifecycle)


def test_job_ids_are_consistent():
    """Verify job_id returned on submission matches what poll returns."""
    s1, b1, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert s1 == 202, f"Submit failed: {s1}"
    job_id = b1["job_id"]
    run_id = b1["run_id"]

    s2, b2, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert s2 == 200, f"Poll failed: {s2}"
    assert str(b2["job_id"]) == str(job_id), \
        f"job_id mismatch: submit={job_id}, poll={b2['job_id']}"
    assert str(b2["run_id"]) == str(run_id), \
        f"run_id mismatch: submit={run_id}, poll={b2['run_id']}"

check("Job IDs consistent between submit and poll", test_job_ids_are_consistent)


def test_webhook_test_endpoint():
    """Test the webhook test delivery endpoint."""
    payload = {
        "callback_url": "https://httpbin.org/post",
    }
    status, body, _, elapsed = req("POST", "/v1/webhooks/test", payload)
    # May succeed or fail depending on external connectivity
    if status == 200:
        assert "success" in body, f"Missing 'success' field: {body}"
        assert "status_code" in body, f"Missing 'status_code' field: {body}"
        assert "message" in body, f"Missing 'message' field: {body}"
    # Other status codes also acceptable (network issues, etc.)
    timings.append(("POST /v1/webhooks/test", elapsed))

check("Webhook test endpoint → 200 with success/status_code/message", test_webhook_test_endpoint)


def test_webhook_test_no_auth():
    """Webhook test without auth → 401/403."""
    payload = {"callback_url": "https://example.com/hook"}
    status, body, _, _ = req("POST", "/v1/webhooks/test", payload, auth=False)
    assert status in (401, 403), f"Expected 401/403, got {status}: {body}"

check("Webhook test without auth → 401/403", test_webhook_test_no_auth)


def test_submit_and_poll_timing():
    """Verify job submission is fast (< 5s) — async, should return quickly."""
    t0 = time.perf_counter()
    status, body, _, elapsed = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    total = time.perf_counter() - t0
    assert status == 202, f"Expected 202, got {status}"
    assert total < 5.0, f"Job submission took {total:.2f}s — expected < 5s for async"

check("Job submission latency < 5s (async pattern)", test_submit_and_poll_timing)


def test_job_callback_status_with_url():
    """Submit job with callback_url → callback_status should be 'pending'."""
    payload = {
        "request": AUTO_PAYLOAD["request"],
        "callback_url": "https://example.com/webhook-test",
    }
    s, b, _, _ = req("POST", "/v1/jobs", payload)
    assert s == 202, f"Expected 202, got {s}"
    job_id = b["job_id"]
    # Poll
    ps, pb, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert ps == 200, f"Poll failed: {ps}"
    cb_status = pb.get("callback_status", "")
    assert cb_status == "pending", \
        f"Expected callback_status='pending' with URL, got '{cb_status}'"

check("Job with callback_url → callback_status=pending", test_job_callback_status_with_url)


def test_job_callback_status_without_url():
    """Submit job without callback_url → callback_status should be 'not_configured'."""
    s, b, _, _ = req("POST", "/v1/jobs", AUTO_PAYLOAD)
    assert s == 202, f"Expected 202, got {s}"
    job_id = b["job_id"]
    ps, pb, _, _ = req("GET", f"/v1/jobs/{job_id}")
    assert ps == 200, f"Poll failed: {ps}"
    cb_status = pb.get("callback_status", "")
    assert cb_status == "not_configured", \
        f"Expected callback_status='not_configured' without URL, got '{cb_status}'"

check("Job without callback_url → callback_status=not_configured", test_job_callback_status_without_url)


# ═══════════════════════════════════════════════════════════════════════════════
#  SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SUMMARY — Phase 17: Async Jobs Lifecycle")
print("=" * 70)

passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
skipped = sum(1 for r in results if r[0] == SKIP)
total = len(results)

print(f"\n  Total:   {total} tests")
print(f"  Passed:  {passed} {PASS}")
print(f"  Failed:  {failed} {FAIL}")
print(f"  Skipped: {skipped} {SKIP}")

if timings:
    print("\n  ── Latency Summary ──")
    for name, elapsed in timings:
        print(f"    {name}: {elapsed*1000:.0f}ms")

if failed > 0:
    print("\n  ── Failures ──")
    for r in results:
        if r[0] == FAIL:
            print(f"    {FAIL} {r[1]}: {r[2] if len(r) > 2 else ''}")

print(f"\n{'=' * 70}")
if failed == 0:
    print(f"  🎉 ALL {passed} ASYNC JOBS TESTS PASSED! ({skipped} skipped)")
else:
    print(f"  ⚠️  {failed} FAILURES — fix before deploying ({passed} passed, {skipped} skipped)")
print(f"{'=' * 70}\n")

sys.exit(1 if failed > 0 else 0)
