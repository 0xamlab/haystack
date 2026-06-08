from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api_server.services import llm_provider_service  # noqa: E402
from apps.api_server.services.llm_api_service import (  # noqa: E402
    ChatCompletionResult,
    GeneratedEmbedding,
    LLMAPIError,
    ProviderAttemptRecord,
    ProviderExecutionMetadata,
)

DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "provider_routing_overhead_benchmark.json"
BENCHMARK_CLASS = "B8"
DEFAULT_ITERATIONS = 250
DEFAULT_WARMUP = 25
_PROVIDER_MODELS_ENV = "ALGENTA_LLM_PROVIDER_MODELS_JSON"
_FAKE_PROVIDER_API_KEY_ENV = "OPENAI_API_KEY"


def _percentile(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = int(percentile * (len(ordered) - 1))
    return ordered[index]


def _summarize_microseconds(samples_ns: list[int]) -> dict[str, float]:
    samples_us = [sample / 1000.0 for sample in samples_ns]
    return {
        "mean_us": statistics.mean(samples_us),
        "min_us": min(samples_us),
        "max_us": max(samples_us),
        "p50_us": _percentile(samples_us, 0.50),
        "p90_us": _percentile(samples_us, 0.90),
        "p95_us": _percentile(samples_us, 0.95),
        "p99_us": _percentile(samples_us, 0.99),
    }


def _scenario_result(
    *,
    name: str,
    timings_ns: list[int],
    provider_attempt_counts: list[int],
    provider_call_count: int,
    expected_attempts: int,
) -> dict[str, Any]:
    summary = _summarize_microseconds(timings_ns)
    summary.update(
        {
            "name": name,
            "iterations": len(timings_ns),
            "provider_call_count": provider_call_count,
            "mean_provider_attempts": statistics.mean(provider_attempt_counts),
            "expected_provider_attempts": expected_attempts,
        }
    )
    return summary


def _with_overhead(
    *,
    baseline: dict[str, Any],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(scenario)
    for key in ("mean_us", "p50_us", "p90_us", "p95_us", "p99_us"):
        enriched[f"{key[:-3]}_overhead_us"] = round(
            float(scenario[key]) - float(baseline[key]),
            6,
        )
    return enriched


def _provider_model_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": "provider.chat.direct",
            "backend": "openai",
            "base_url": "https://provider.example.invalid/v1",
            "api_key_env": _FAKE_PROVIDER_API_KEY_ENV,
            "model_name": "gpt-4o-mini",
            "capabilities": ["chat_completions"],
        },
        {
            "id": "provider.chat.fail-primary",
            "backend": "openai",
            "base_url": "https://provider.example.invalid/v1",
            "api_key_env": _FAKE_PROVIDER_API_KEY_ENV,
            "model_name": "gpt-4o-mini",
            "capabilities": ["chat_completions"],
        },
        {
            "id": "provider.chat.fail-secondary",
            "backend": "openai",
            "base_url": "https://provider.example.invalid/v1",
            "api_key_env": _FAKE_PROVIDER_API_KEY_ENV,
            "model_name": "gpt-4o-mini",
            "capabilities": ["chat_completions"],
        },
        {
            "id": "router.chat.single",
            "backend": "router",
            "targets": ["provider.chat.direct"],
            "capabilities": ["chat_completions"],
        },
        {
            "id": "router.chat.inner",
            "backend": "router",
            "targets": ["provider.chat.direct"],
            "capabilities": ["chat_completions"],
            "fallback_policy": "retryable_only",
        },
        {
            "id": "router.chat.nested",
            "backend": "router",
            "targets": ["router.chat.inner"],
            "capabilities": ["chat_completions"],
        },
        {
            "id": "router.chat.failover",
            "backend": "router",
            "targets": ["provider.chat.fail-primary", "provider.chat.fail-secondary"],
            "capabilities": ["chat_completions"],
            "fallback_policy": "retryable_only",
            "fallback_on": ["provider_backend_error"],
        },
        {
            "id": "provider.embed.direct",
            "backend": "openai",
            "base_url": "https://provider.example.invalid/v1",
            "api_key_env": _FAKE_PROVIDER_API_KEY_ENV,
            "model_name": "text-embedding-3-small",
            "capabilities": ["embeddings"],
        },
        {
            "id": "provider.embed.fail-primary",
            "backend": "openai",
            "base_url": "https://provider.example.invalid/v1",
            "api_key_env": _FAKE_PROVIDER_API_KEY_ENV,
            "model_name": "text-embedding-3-small",
            "capabilities": ["embeddings"],
        },
        {
            "id": "provider.embed.fail-secondary",
            "backend": "openai",
            "base_url": "https://provider.example.invalid/v1",
            "api_key_env": _FAKE_PROVIDER_API_KEY_ENV,
            "model_name": "text-embedding-3-small",
            "capabilities": ["embeddings"],
        },
        {
            "id": "router.embed.single",
            "backend": "router",
            "targets": ["provider.embed.direct"],
            "capabilities": ["embeddings"],
        },
        {
            "id": "router.embed.inner",
            "backend": "router",
            "targets": ["provider.embed.direct"],
            "capabilities": ["embeddings"],
            "fallback_policy": "retryable_only",
        },
        {
            "id": "router.embed.nested",
            "backend": "router",
            "targets": ["router.embed.inner"],
            "capabilities": ["embeddings"],
        },
        {
            "id": "router.embed.failover",
            "backend": "router",
            "targets": ["provider.embed.fail-primary", "provider.embed.fail-secondary"],
            "capabilities": ["embeddings"],
            "fallback_policy": "retryable_only",
            "fallback_on": ["provider_backend_error"],
        },
    ]


@contextmanager
def _configured_provider_models() -> Iterator[None]:
    original_models = os.environ.get(_PROVIDER_MODELS_ENV)
    original_api_key = os.environ.get(_FAKE_PROVIDER_API_KEY_ENV)
    os.environ[_PROVIDER_MODELS_ENV] = json.dumps(_provider_model_payload())
    os.environ[_FAKE_PROVIDER_API_KEY_ENV] = "provider-routing-benchmark"
    llm_provider_service.load_provider_model_configs.cache_clear()
    try:
        yield
    finally:
        if original_models is None:
            os.environ.pop(_PROVIDER_MODELS_ENV, None)
        else:
            os.environ[_PROVIDER_MODELS_ENV] = original_models
        if original_api_key is None:
            os.environ.pop(_FAKE_PROVIDER_API_KEY_ENV, None)
        else:
            os.environ[_FAKE_PROVIDER_API_KEY_ENV] = original_api_key
        llm_provider_service.load_provider_model_configs.cache_clear()


class _FakeProviderExecutor:
    def __init__(
        self,
        *,
        chat_failures_before_success: dict[str, int] | None = None,
        embedding_failures_before_success: dict[str, int] | None = None,
    ) -> None:
        self.chat_failures_before_success = dict(chat_failures_before_success or {})
        self.embedding_failures_before_success = dict(embedding_failures_before_success or {})
        self.chat_call_count = 0
        self.embedding_call_count = 0
        self._chat_attempts: dict[str, int] = {}
        self._embedding_attempts: dict[str, int] = {}

    async def provider_chat_completion(
        self,
        *,
        config: llm_provider_service.ProviderModelConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float | None = None,
    ) -> ChatCompletionResult:
        del messages, timeout_seconds
        self.chat_call_count += 1
        attempt = self._chat_attempts.get(config.model_id, 0) + 1
        self._chat_attempts[config.model_id] = attempt
        fail_before_success = self.chat_failures_before_success.get(config.model_id, 0)
        if attempt <= fail_before_success:
            raise LLMAPIError(
                "provider_backend_error",
                f"Synthetic provider failure for {config.model_id}",
                {"model": config.model_id, "backend": config.backend},
            )
        selected_attempt = (
            ProviderAttemptRecord(
                provider_backend=config.backend,
                provider_model_id=config.model_id,
                outcome="selected",
            ),
        )
        return ChatCompletionResult(
            completion_id=f"bench_{config.model_id}_{attempt}",
            content="provider routing benchmark",
            prompt_tokens=4,
            completion_tokens=3,
            provider=ProviderExecutionMetadata(
                provider_backend=config.backend,
                provider_model_id=config.model_id,
            ),
            provider_attempts=selected_attempt,
        )

    async def provider_embeddings(
        self,
        *,
        config: llm_provider_service.ProviderModelConfig,
        inputs: list[str],
        dimensions: int,
        timeout_seconds: float | None = None,
    ) -> tuple[list[GeneratedEmbedding], int]:
        del timeout_seconds
        self.embedding_call_count += 1
        attempt = self._embedding_attempts.get(config.model_id, 0) + 1
        self._embedding_attempts[config.model_id] = attempt
        fail_before_success = self.embedding_failures_before_success.get(config.model_id, 0)
        if attempt <= fail_before_success:
            raise LLMAPIError(
                "provider_backend_error",
                f"Synthetic embedding failure for {config.model_id}",
                {"model": config.model_id, "backend": config.backend},
            )
        selected_attempt = (
            ProviderAttemptRecord(
                provider_backend=config.backend,
                provider_model_id=config.model_id,
                outcome="selected",
            ),
        )
        generated = [
            GeneratedEmbedding(
                index=index,
                embedding=[float(index + 1)] * dimensions,
                token_count=4,
                provider=ProviderExecutionMetadata(
                    provider_backend=config.backend,
                    provider_model_id=config.model_id,
                ),
                provider_attempts=selected_attempt,
            )
            for index, _ in enumerate(inputs)
        ]
        return generated, 4 * len(inputs)


@contextmanager
def _patched_provider_executor(executor: _FakeProviderExecutor) -> Iterator[None]:
    original_chat = llm_provider_service.provider_chat_completion
    original_embeddings = llm_provider_service.provider_embeddings
    llm_provider_service.provider_chat_completion = executor.provider_chat_completion
    llm_provider_service.provider_embeddings = executor.provider_embeddings
    try:
        yield
    finally:
        llm_provider_service.provider_chat_completion = original_chat
        llm_provider_service.provider_embeddings = original_embeddings


async def _sample_async_operation(
    *,
    warmup: int,
    iterations: int,
    operation: Callable[[], Awaitable[tuple[int, int]]],
) -> tuple[list[int], list[int]]:
    for _ in range(warmup):
        await operation()
    timings_ns: list[int] = []
    provider_attempt_counts: list[int] = []
    for _ in range(iterations):
        started_ns = time.perf_counter_ns()
        provider_attempt_count, provider_call_count = await operation()
        timings_ns.append(time.perf_counter_ns() - started_ns)
        provider_attempt_counts.append(provider_attempt_count)
        del provider_call_count
    return timings_ns, provider_attempt_counts


async def _benchmark_chat_scenario(
    *,
    model_id: str,
    iterations: int,
    warmup: int,
    chat_failures_before_success: dict[str, int] | None = None,
    expected_provider_attempts: int,
) -> dict[str, Any]:
    executor = _FakeProviderExecutor(
        chat_failures_before_success=chat_failures_before_success,
    )
    with _patched_provider_executor(executor):
        messages = [{"role": "user", "content": "alpha beta"}]

        async def _operation() -> tuple[int, int]:
            result = await llm_provider_service.routed_provider_chat_completion(
                model_id=model_id,
                messages=messages,
            )
            return len(result.provider_attempts), executor.chat_call_count

        timings_ns, provider_attempt_counts = await _sample_async_operation(
            warmup=warmup,
            iterations=iterations,
            operation=_operation,
        )
    return _scenario_result(
        name=model_id,
        timings_ns=timings_ns,
        provider_attempt_counts=provider_attempt_counts,
        provider_call_count=executor.chat_call_count,
        expected_attempts=expected_provider_attempts,
    )


async def _benchmark_embedding_scenario(
    *,
    model_id: str,
    iterations: int,
    warmup: int,
    embedding_failures_before_success: dict[str, int] | None = None,
    expected_provider_attempts: int,
) -> dict[str, Any]:
    executor = _FakeProviderExecutor(
        embedding_failures_before_success=embedding_failures_before_success,
    )
    with _patched_provider_executor(executor):
        inputs = ["alpha beta"]

        async def _operation() -> tuple[int, int]:
            generated, _ = await llm_provider_service.routed_provider_embeddings(
                model_id=model_id,
                inputs=inputs,
                dimensions=4,
            )
            return len(generated[0].provider_attempts), executor.embedding_call_count

        timings_ns, provider_attempt_counts = await _sample_async_operation(
            warmup=warmup,
            iterations=iterations,
            operation=_operation,
        )
    return _scenario_result(
        name=model_id,
        timings_ns=timings_ns,
        provider_attempt_counts=provider_attempt_counts,
        provider_call_count=executor.embedding_call_count,
        expected_attempts=expected_provider_attempts,
    )


async def _run_async_benchmark(*, iterations: int, warmup: int) -> dict[str, Any]:
    with _configured_provider_models():
        direct_chat = await _benchmark_chat_scenario(
            model_id="provider.chat.direct",
            iterations=iterations,
            warmup=warmup,
            expected_provider_attempts=1,
        )
        router_chat_single = await _benchmark_chat_scenario(
            model_id="router.chat.single",
            iterations=iterations,
            warmup=warmup,
            expected_provider_attempts=1,
        )
        router_chat_nested = await _benchmark_chat_scenario(
            model_id="router.chat.nested",
            iterations=iterations,
            warmup=warmup,
            expected_provider_attempts=1,
        )
        router_chat_failover = await _benchmark_chat_scenario(
            model_id="router.chat.failover",
            iterations=iterations,
            warmup=warmup,
            chat_failures_before_success={"provider.chat.fail-primary": iterations + warmup},
            expected_provider_attempts=2,
        )

        direct_embeddings = await _benchmark_embedding_scenario(
            model_id="provider.embed.direct",
            iterations=iterations,
            warmup=warmup,
            expected_provider_attempts=1,
        )
        router_embeddings_single = await _benchmark_embedding_scenario(
            model_id="router.embed.single",
            iterations=iterations,
            warmup=warmup,
            expected_provider_attempts=1,
        )
        router_embeddings_nested = await _benchmark_embedding_scenario(
            model_id="router.embed.nested",
            iterations=iterations,
            warmup=warmup,
            expected_provider_attempts=1,
        )
        router_embeddings_failover = await _benchmark_embedding_scenario(
            model_id="router.embed.failover",
            iterations=iterations,
            warmup=warmup,
            embedding_failures_before_success={"provider.embed.fail-primary": iterations + warmup},
            expected_provider_attempts=2,
        )

    return {
        "benchmark_class": BENCHMARK_CLASS,
        "iterations": iterations,
        "warmup_iterations": warmup,
        "chat": {
            "baseline": direct_chat,
            "single_hop_router": _with_overhead(
                baseline=direct_chat,
                scenario=router_chat_single,
            ),
            "nested_router": _with_overhead(
                baseline=direct_chat,
                scenario=router_chat_nested,
            ),
            "retryable_failover_router": _with_overhead(
                baseline=direct_chat,
                scenario=router_chat_failover,
            ),
        },
        "embeddings": {
            "baseline": direct_embeddings,
            "single_hop_router": _with_overhead(
                baseline=direct_embeddings,
                scenario=router_embeddings_single,
            ),
            "nested_router": _with_overhead(
                baseline=direct_embeddings,
                scenario=router_embeddings_nested,
            ),
            "retryable_failover_router": _with_overhead(
                baseline=direct_embeddings,
                scenario=router_embeddings_failover,
            ),
        },
    }


def run_benchmark(*, iterations: int = DEFAULT_ITERATIONS, warmup: int = DEFAULT_WARMUP) -> dict[str, Any]:
    if iterations <= 0:
        raise ValueError("iterations must be a positive integer.")
    if warmup < 0:
        raise ValueError("warmup must be zero or a positive integer.")
    result = asyncio.run(_run_async_benchmark(iterations=iterations, warmup=warmup))
    result["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark deterministic provider-routing overhead over direct provider execution.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="Measured iterations per scenario.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=DEFAULT_WARMUP,
        help="Warm-up iterations per scenario before timing.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the JSON benchmark artifact.",
    )
    args = parser.parse_args()

    results = run_benchmark(iterations=args.iterations, warmup=args.warmup)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))
    print(f"Wrote benchmark artifact to {args.output}")


if __name__ == "__main__":
    main()
