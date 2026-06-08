from __future__ import annotations

import pytest

from apps.runtime.mojo_library_runner import execute_runtime_library, library_runtime_available

pytestmark = pytest.mark.anyio

_WRAPPER_TIMEOUT_SECONDS = 45.0


@pytest.mark.skipif(not library_runtime_available(), reason="Mojo runtime toolchain unavailable")
@pytest.mark.parametrize(
    ("module_name", "function_name", "args", "expected"),
    [
        ("rerank_eval", "precision_at_k", [[1, 0, 1], 3], pytest.approx(2.0 / 3.0)),
        ("rerank_eval", "recall_at_k", [[1, 0, 1], 4, 3], pytest.approx(0.5)),
        ("rerank_eval", "hit_rate_at_k", [[0, 0, 1], 3], pytest.approx(1.0)),
        ("rerank_eval", "mrr_at_k", [[0, 1, 0], 3], pytest.approx(0.5)),
        ("rerank_eval", "map_at_k", [[1, 0, 1], 3], pytest.approx((1.0 + 2.0 / 3.0) / 2.0)),
        ("rerank_eval", "ndcg_at_k", [[3.0, 2.0], [3.0, 2.0], 2], pytest.approx(1.0)),
        (
            "rerank_eval",
            "pairwise_margin_accuracy",
            [[0.9, 0.7], [0.1, 0.4], 0.2],
            pytest.approx(1.0),
        ),
        (
            "rerank_eval",
            "score_separation",
            [[0.8, 0.6], [0.3, 0.1]],
            pytest.approx(0.5),
        ),
        (
            "rerank_eval",
            "latency_weighted_quality",
            [0.9, 50.0, 100.0],
            pytest.approx(0.6),
        ),
        ("inference_cost_latency", "prompt_token_estimate", [100, 4.0], 25),
        ("inference_cost_latency", "completion_token_estimate", [45, 4.0], 12),
        (
            "inference_cost_latency",
            "kv_cache_bytes",
            [2, 128, 4, 256, 2],
            pytest.approx(1048576.0),
        ),
        (
            "inference_cost_latency",
            "attention_flops",
            [2, 128, 4, 8, 64],
            pytest.approx(268435456.0),
        ),
        (
            "inference_cost_latency",
            "prefill_latency_estimate",
            [1000, 500.0, 20.0],
            pytest.approx(2020.0),
        ),
        (
            "inference_cost_latency",
            "decode_latency_estimate",
            [250, 250.0, 15.0],
            pytest.approx(1015.0),
        ),
        (
            "inference_cost_latency",
            "request_cost_estimate",
            [1000, 500, 0.002, 0.006],
            pytest.approx(0.005),
        ),
        (
            "inference_cost_latency",
            "cost_latency_frontier_score",
            [0.01, 100.0, 2.0, 0.01],
            pytest.approx(1.0 / 2.02),
        ),
        (
            "inference_cost_latency",
            "batch_efficiency_estimate",
            [4, 8],
            pytest.approx(0.5),
        ),
        (
            "inference_cost_latency",
            "queue_delay_estimate",
            [10, 5.0, 2],
            pytest.approx(1000.0),
        ),
        (
            "inference_cost_latency",
            "speculative_decode_gain_estimate",
            [0.5, 4, 100.0, 200.0],
            pytest.approx(0.5),
        ),
    ],
)
async def test_llm_rollout_kernels_happy_paths(
    module_name: str,
    function_name: str,
    args: list[object],
    expected: object,
) -> None:
    result = await execute_runtime_library(
        module_name,
        function_name,
        args,
        timeout_seconds=_WRAPPER_TIMEOUT_SECONDS,
    )
    assert result == expected


@pytest.mark.skipif(not library_runtime_available(), reason="Mojo runtime toolchain unavailable")
@pytest.mark.parametrize(
    ("module_name", "function_name", "args", "expected"),
    [
        ("rerank_eval", "precision_at_k", [[], 3], pytest.approx(0.0)),
        ("rerank_eval", "recall_at_k", [[1, 0], 0, 2], pytest.approx(0.0)),
        ("rerank_eval", "hit_rate_at_k", [[1, 1], 0], pytest.approx(0.0)),
        ("rerank_eval", "mrr_at_k", [[0, 0], 2], pytest.approx(0.0)),
        ("rerank_eval", "map_at_k", [[0, 0], 2], pytest.approx(0.0)),
        ("rerank_eval", "ndcg_at_k", [[1.0], [0.0], 1], pytest.approx(0.0)),
        ("rerank_eval", "pairwise_margin_accuracy", [[], [], 0.2], pytest.approx(0.0)),
        ("rerank_eval", "score_separation", [[], [0.1]], pytest.approx(0.0)),
        ("rerank_eval", "latency_weighted_quality", [0.9, 50.0, 0.0], pytest.approx(0.0)),
        ("inference_cost_latency", "prompt_token_estimate", [-10, 4.0], 0),
        ("inference_cost_latency", "completion_token_estimate", [10, 0.0], 0),
        ("inference_cost_latency", "kv_cache_bytes", [-2, 128, 4, 256, 2], pytest.approx(0.0)),
        (
            "inference_cost_latency",
            "prefill_latency_estimate",
            [1000, 0.0, 20.0],
            pytest.approx(0.0),
        ),
        (
            "inference_cost_latency",
            "decode_latency_estimate",
            [250, -10.0, 15.0],
            pytest.approx(0.0),
        ),
        (
            "inference_cost_latency",
            "cost_latency_frontier_score",
            [-1.0, -50.0, -2.0, -3.0],
            pytest.approx(1.0),
        ),
        (
            "inference_cost_latency",
            "batch_efficiency_estimate",
            [10, 5],
            pytest.approx(1.0),
        ),
        (
            "inference_cost_latency",
            "queue_delay_estimate",
            [10, 5.0, 0],
            pytest.approx(0.0),
        ),
        (
            "inference_cost_latency",
            "speculative_decode_gain_estimate",
            [1.2, 4, 100.0, 200.0],
            pytest.approx(2.0),
        ),
        (
            "inference_cost_latency",
            "speculative_decode_gain_estimate",
            [-0.5, 4, 100.0, 200.0],
            pytest.approx(0.0),
        ),
    ],
)
async def test_llm_rollout_kernels_edge_cases(
    module_name: str,
    function_name: str,
    args: list[object],
    expected: object,
) -> None:
    result = await execute_runtime_library(
        module_name,
        function_name,
        args,
        timeout_seconds=_WRAPPER_TIMEOUT_SECONDS,
    )
    assert result == expected
