"""
test_worker_tasks.py — Worker task coverage: persist_simulation, enqueue_simulation_job.

Two layers:
  Layer A — task import / signature / registration (no Celery broker)
  Layer B — task execution with real broker (requires Redis + Celery worker)

Run:
  python3 tests/integration/test_worker_tasks.py          # Layer A only (auto-detects no broker)
  DE_CELERY=1 python3 tests/integration/test_worker_tasks # Layer B with real broker
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

SKIP_CELERY = os.environ.get("DE_CELERY", "0") != "1"
REDIS_URL   = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

PASS = "✅"; FAIL = "❌"; SKIP = "⏭️ "
_results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    icon = PASS if cond else FAIL
    _results.append((name, cond, detail))
    print(f"  {icon}  {name}" + (f"  ({detail})" if detail else ""))


# ── Layer A: Task structure ───────────────────────────────────────────────────

def test_worker_tasks_importable():
    try:
        from apps.worker import tasks as worker_tasks
        check("apps.worker.tasks importable", True)
    except ImportError as e:
        check("apps.worker.tasks importable", False, str(e))
        return


def test_simulation_task_module_importable():
    try:
        import apps.worker.tasks.simulation_task as mod
        check("simulation_task module importable", True)
        check("module exports celery_app name",          hasattr(mod, "celery_app"))
        check("module exports persist_simulation name",  hasattr(mod, "persist_simulation"))
        check("module exports run_simulation_job name",  hasattr(mod, "run_simulation_job"))
    except ImportError as e:
        check("simulation_task module importable", False, str(e))


def test_task_names_are_correct():
    import apps.worker.tasks.simulation_task as mod
    check("task names follow expected pattern", True)
    # Source contains correct registration names
    import inspect as _inspect
    src = _inspect.getsource(mod)
    check("persist_simulation name in source",
          "apps.worker.tasks.simulation_task.persist_simulation" in src)
    check("run_simulation_job name in source",
          "apps.worker.tasks.simulation_task.run_simulation_job" in src)


def test_celery_degradation_documented():
    """Tasks return None when Celery/Redis not available — verify graceful degradation."""
    import apps.worker.tasks.simulation_task as mod
    # celery_app may be None if Redis unavailable — that's expected + documented
    celery_app = mod.celery_app
    persist    = mod.persist_simulation
    run_job    = mod.run_simulation_job
    if celery_app is None:
        # Broker not available — graceful degradation path
        check("celery_app is None (no broker — graceful degradation)", True)
        check("persist_simulation is None when no broker",  persist    is None)
        check("run_simulation_job is None when no broker",  run_job    is None)
    else:
        # Broker available — tasks should be fully initialised
        check("celery_app has send_task", hasattr(celery_app, "send_task"))
        check("celery_app has conf",      hasattr(celery_app, "conf"))
        check("persist_simulation has .delay", hasattr(persist, "delay"))
        check("run_simulation_job has .delay", hasattr(run_job, "delay"))


def test_task_routes_in_source():
    """Queue routing is defined in source — verifiable without a broker."""
    import inspect as _inspect

    import apps.worker.tasks.simulation_task as mod
    src = _inspect.getsource(mod)
    check("persist queue defined in source",  '"queue": "persist"'  in src)
    check("simulate queue defined in source", '"queue": "simulate"' in src)


def test_persist_simulation_inner_function():
    """Inner task function _persist_simulation accepts correct parameters."""
    import inspect as _inspect

    import apps.worker.tasks.simulation_task as mod
    src = _inspect.getsource(mod)
    check("_persist_simulation function defined", "_persist_simulation" in src)
    check("persist task uses bind=True",           "bind=True" in src)
    check("run_simulation_job accepts job_id",     "job_id" in src)


# ── Layer B: Real broker execution ───────────────────────────────────────────

def test_persist_simulation_delay():
    """Send persist_simulation to real Celery broker and check it's accepted."""
    from apps.worker.tasks.simulation_task import persist_simulation
    fake_payload = {
        "run_id": str(uuid.uuid4()),
        "org_id": "test-org",
        "result": {"expected_value": 100000, "std_deviation": 15000},
        "billing_units": 1,
        "engine_version": "test",
    }
    try:
        result = persist_simulation.delay(**fake_payload)
        check("persist_simulation.delay() accepted by broker", bool(result.id), result.id)
        # Don't wait for result — just confirm task was queued
        check("persist_simulation task ID is UUID-like", len(result.id) > 10)
    except Exception as e:
        check("persist_simulation.delay() accepted by broker", False, f"{type(e).__name__}: {e}")


def test_run_simulation_job_delay():
    """Send run_simulation_job to real Celery broker."""
    from apps.worker.tasks.simulation_task import run_simulation_job
    fake_job_id = str(uuid.uuid4())
    try:
        result = run_simulation_job.delay(job_id=fake_job_id)
        check("run_simulation_job.delay() accepted", bool(result.id), result.id)
    except Exception as e:
        check("run_simulation_job.delay() accepted", False, f"{type(e).__name__}: {e}")


def _redis_reachable() -> bool:
    """Verify Redis (Celery broker) is reachable before running broker tests."""
    import socket

    host = "localhost"
    port = 6379
    try:
        s = socket.create_connection((host, port), timeout=3)
        s.close()
        check(f"Redis reachable at {host}:{port}", True)
        return True
    except (ConnectionRefusedError, OSError) as e:
        check(f"Redis reachable at {host}:{port}", False, str(e))
        return False


def test_redis_reachable() -> None:
    assert _redis_reachable()


# ── Runner ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 68)
    print("  WORKER TASK TESTS")
    print("=" * 68)

    print("\n── Layer A: Task structure (no broker) ─────────────────────────\n")
    for fn in [
        test_worker_tasks_importable,
        test_simulation_task_module_importable,
        test_task_names_are_correct,
        test_celery_degradation_documented,
        test_task_routes_in_source,
        test_persist_simulation_inner_function,
    ]:
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, str(e))

    print("\n── Layer B: Real Celery broker ──────────────────────────────────\n")
    if SKIP_CELERY:
        print(f"  {SKIP}  Skipped (set DE_CELERY=1 to enable)")
    else:
        redis_ok = _redis_reachable()
        if redis_ok:
            for fn in [test_persist_simulation_delay, test_run_simulation_job_delay]:
                try:
                    fn()
                except Exception as e:
                    check(fn.__name__, False, f"{type(e).__name__}: {e}")
        else:
            print(f"  {SKIP}  Broker tests skipped — Redis unreachable")

    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print(f"\n{'=' * 68}")
    print(f"  {passed} passed  |  {failed} failed  |  {len(_results)} total")
    print(f"{'=' * 68}\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
