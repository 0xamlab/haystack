from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGENTA_PACKAGE = PROJECT_ROOT / "packages" / "algenta"
PYTHON_SDK = PROJECT_ROOT / "packages" / "python-sdk"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "algenta_connector_preview_benchmark.json"
_REDIS_PREVIEW = {"type": "redis", "url": "redis://localhost:6379"}


def _ensure_package_paths() -> None:
    for path in (str(ALGENTA_PACKAGE), str(PYTHON_SDK), str(PROJECT_ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)


def _percentile_ms(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = int(percentile * (len(ordered) - 1))
    return ordered[index]


def _summarize_ms(samples: list[float]) -> dict[str, float]:
    return {
        "mean_ms": statistics.mean(samples),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "p90_ms": _percentile_ms(samples, 0.90),
        "p95_ms": _percentile_ms(samples, 0.95),
    }


class _PreviewUnavailableError(Exception):
    status_code = 404
    error_code = "not_found"
    response_body = {"error": {"code": "not_found", "message": "Not found"}}


class _DirectPreviewClient:
    def __init__(self) -> None:
        self.calls = 0

    def preview_test_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        assert connector_type == "redis"
        assert isinstance(config, dict)
        assert str(config.get("url", "")).startswith("redis://localhost:6379")
        return {
            "success": True,
            "message": "ok",
            "latency_ms": 3,
            "status": "live",
            "error_type": None,
            "recoverable": None,
        }

    def preview_browse_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        assert connector_type == "redis"
        assert isinstance(config, dict)
        assert str(config.get("url", "")).startswith("redis://localhost:6379")
        return {
            "connector_type": "redis",
            "items": [{"id": "cache:key", "label": "cache:key", "kind": "key"}],
            "total": 1,
            "message": "1 key available.",
            "labels": {"entity_noun": "key", "row_noun": "value"},
            "discovery": {"scope_noun": "keyspace", "returned_count": 1},
        }


class _EphemeralPreviewClient:
    def __init__(self) -> None:
        self.calls = 0

    def preview_test_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        raise _PreviewUnavailableError()

    def preview_browse_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        raise _PreviewUnavailableError()

    def create_connector(self, **_kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        return {
            "id": "preview_1",
            "name": "preview",
            "connector_type": "redis",
            "status": "untested",
            "visibility": "private",
            "last_tested_at": None,
            "error_message": None,
            "created_at": None,
        }

    def test_connector(self, connector_id: str) -> dict[str, Any]:
        self.calls += 1
        assert connector_id == "preview_1"
        return {
            "success": True,
            "message": "ok",
            "latency_ms": 3,
            "status": "live",
            "error_type": None,
            "recoverable": None,
        }

    def browse_connector(self, connector_id: str) -> dict[str, Any]:
        self.calls += 1
        assert connector_id == "preview_1"
        return {
            "connector_type": "redis",
            "items": [{"id": "cache:key", "label": "cache:key", "kind": "key"}],
            "total": 1,
            "message": "1 key available.",
            "labels": {"entity_noun": "key", "row_noun": "value"},
            "discovery": {"scope_noun": "keyspace", "returned_count": 1},
        }

    def delete_connector(self, connector_id: str) -> None:
        self.calls += 1
        assert connector_id == "preview_1"


def _sample_preview_ms(fn: Callable[[], int], iterations: int) -> tuple[list[float], list[int]]:
    samples: list[float] = []
    request_counts: list[int] = []
    for _ in range(iterations):
        start = time.perf_counter()
        request_counts.append(fn())
        samples.append((time.perf_counter() - start) * 1000.0)
    return samples, request_counts


def _runtime(mode: str = "api"):
    from algenta import Runtime

    return Runtime(mode=mode, api_key="de_test_preview")


def _run_direct_test() -> int:
    runtime = _runtime()
    client = _DirectPreviewClient()
    runtime._client = lambda: client
    runtime.test_connector(connector=_REDIS_PREVIEW)
    return client.calls


def _run_fallback_test() -> int:
    runtime = _runtime()
    client = _EphemeralPreviewClient()
    runtime._client = lambda: client
    runtime.test_connector(connector=_REDIS_PREVIEW)
    return client.calls


def _run_direct_browse() -> int:
    runtime = _runtime()
    client = _DirectPreviewClient()
    runtime._client = lambda: client
    runtime.browse_connector(connector=_REDIS_PREVIEW)
    return client.calls


def _run_fallback_browse() -> int:
    runtime = _runtime()
    client = _EphemeralPreviewClient()
    runtime._client = lambda: client
    runtime.browse_connector(connector=_REDIS_PREVIEW)
    return client.calls


class _AdaptivePreviewRunner:
    def __init__(self, *, browse: bool) -> None:
        self._browse = browse
        self.runtime = _runtime()
        self.client = _EphemeralPreviewClient()
        self.runtime._client = lambda: self.client
        self.runtime._consume_inline_preview_slot = lambda: None
        self._iteration = 0

    def _preview(self) -> int:
        before = self.client.calls
        connector = {"type": "redis", "url": f"redis://localhost:6379/{self._iteration}"}
        self._iteration += 1
        if self._browse:
            self.runtime.browse_connector(connector=connector)
        else:
            self.runtime.test_connector(connector=connector)
        return self.client.calls - before


def _adaptive_preview_stats(*, browse: bool, iterations: int) -> dict[str, Any]:
    runner = _AdaptivePreviewRunner(browse=browse)
    samples, request_counts = _sample_preview_ms(runner._preview, iterations)
    return {
        "timings": _summarize_ms(samples),
        "requests_per_call": {
            "first": request_counts[0],
            "steady_state": request_counts[-1],
            "mean": statistics.mean(request_counts),
            "reduction_vs_cold_x": request_counts[0] / request_counts[-1],
        },
    }


def run_benchmark(*, iterations: int = 200) -> dict[str, Any]:
    _ensure_package_paths()

    direct_test_samples, direct_test_calls = _sample_preview_ms(_run_direct_test, iterations)
    fallback_test_samples, fallback_test_calls = _sample_preview_ms(_run_fallback_test, iterations)
    direct_browse_samples, direct_browse_calls = _sample_preview_ms(_run_direct_browse, iterations)
    fallback_browse_samples, fallback_browse_calls = _sample_preview_ms(
        _run_fallback_browse,
        iterations,
    )

    return {
        "iterations": iterations,
        "test_inline_preview": {
            "direct": _summarize_ms(direct_test_samples),
            "fallback": _summarize_ms(fallback_test_samples),
            "adaptive_fallback": _adaptive_preview_stats(browse=False, iterations=iterations),
            "requests_per_call": {
                "direct": int(statistics.mean(direct_test_calls)),
                "fallback": int(statistics.mean(fallback_test_calls)),
                "reduction_x": statistics.mean(fallback_test_calls)
                / statistics.mean(direct_test_calls),
            },
        },
        "browse_inline_preview": {
            "direct": _summarize_ms(direct_browse_samples),
            "fallback": _summarize_ms(fallback_browse_samples),
            "adaptive_fallback": _adaptive_preview_stats(browse=True, iterations=iterations),
            "requests_per_call": {
                "direct": int(statistics.mean(direct_browse_calls)),
                "fallback": int(statistics.mean(fallback_browse_calls)),
                "reduction_x": statistics.mean(fallback_browse_calls)
                / statistics.mean(direct_browse_calls),
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark direct inline preview versus ephemeral connector preview."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Number of preview calls to sample per path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the benchmark JSON artifact.",
    )
    args = parser.parse_args()

    results = run_benchmark(iterations=args.iterations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
