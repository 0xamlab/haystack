from __future__ import annotations

import asyncio
import contextlib
import json
import os
import statistics
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.api_server.services.cline_competitive_live_fixtures import (
    RepositoryPipelineFixture as _RepositoryPipelineFixture,
    WARM_CACHE_TASKS,
    WarmCacheTask as _WarmCacheTask,
    repository_pipeline_fixture as _repository_pipeline_fixture,
    reset_warm_cache_fixture as _reset_warm_cache_fixture,
    warm_cache_fixture as _warm_cache_fixture,
)
from apps.api_server.services.cline_competitive_measurements import (
    CURSOR_MCP_COMPARISON_PATH,
    WARM_CACHE_COMPARISON_PATH,
    build_cursor_mcp_comparison_artifact,
    build_warm_cache_comparison_artifact,
)
from apps.api_server.services.cline_proof_common import (
    CLINE_PROOFS_DIR,
    artifact_relative_path,
    build_proof_context,
    create_artifact_provenance,
    read_json,
    repo_root,
    write_json,
)
from apps.api_server.services.cline_runtime_support import (
    agent_core_runtime,
    local_api_server,
    request_json,
    request_text,
)
from apps.api_server.services.repository_intelligence_channel_envelope import (
    build_repository_pipeline_envelope,
)
from apps.mcp_server.client import request_overrides
from apps.mcp_server.tools.repositories import run_repository_pipeline_handler


COMPETITIVE_RUNS_DIR = CLINE_PROOFS_DIR / "competitive_runs"
DIRECT_REPOSITORY_PIPELINE_PATH = COMPETITIVE_RUNS_DIR / "direct_repository_pipeline.json"
MCP_REPOSITORY_PIPELINE_PATH = COMPETITIVE_RUNS_DIR / "mcp_repository_pipeline.json"
WARM_CACHE_COLD_RUN_PATH = COMPETITIVE_RUNS_DIR / "warm_cache_cold_run.json"
WARM_CACHE_WARM_RUN_PATH = COMPETITIVE_RUNS_DIR / "warm_cache_warm_run.json"

VERIFIED_AGENTIC_MODEL_ID = "repository.verified_agentic_v1"
VERIFIED_AGENT_TOOL_PROFILE = "no_exploration_no_shell"
WARM_CACHE_TOOL_PROFILE = "no_exploration_local_validation"
WARM_CACHE_MAX_ITERATIONS = 10
WARM_CACHE_PROMPT_FAMILY = "g0_repository_fix_v1"
WARM_CACHE_PROVIDER = "anthropic"
WARM_CACHE_STATUS_SUCCEEDED = "completed"


@dataclass(frozen=True)
class _MeasuredPayload:
    payload: dict[str, Any]
    wall_time_seconds: float


def _required_string_env(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {env_name}")
    return value


def _required_mapping(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise RuntimeError(f"{field_name} must be an object")
    return value


def _numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _auth_headers(api_key: str) -> dict[str, str]:
    normalized_api_key = api_key.strip()
    if not normalized_api_key:
        raise RuntimeError("api_key must be a non-empty string")
    return {"Authorization": f"Bearer {normalized_api_key}"}


def _serialize_error_payload(status_code: int, payload: dict[str, Any]) -> str:
    try:
        serialized = json.dumps(payload, sort_keys=True)
    except TypeError:
        serialized = repr(payload)
    return f"status={status_code} payload={serialized}"


def _usage_from_agent_block(payload: dict[str, Any]) -> dict[str, float]:
    agent = _required_mapping(payload, "agent")
    usage = _required_mapping(agent, "usage")
    input_tokens = _numeric(usage.get("input_tokens"))
    output_tokens = _numeric(usage.get("output_tokens"))
    cache_read_tokens = _numeric(usage.get("cache_read_tokens"))
    cache_write_tokens = _numeric(usage.get("cache_write_tokens"))
    if input_tokens is None or output_tokens is None:
        raise RuntimeError("payload agent usage must include input_tokens and output_tokens")
    if input_tokens <= 0 or output_tokens <= 0:
        raise RuntimeError("payload agent usage must contain non-zero input/output tokens")
    if cache_read_tokens is None:
        cache_read_tokens = 0.0
    if cache_write_tokens is None:
        cache_write_tokens = 0.0
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
    }


def _assert_verified_agentic_envelope(payload: dict[str, Any], *, channel: str) -> None:
    usage = _usage_from_agent_block(payload)
    agent = _required_mapping(payload, "agent")
    pipeline = _required_mapping(payload, "pipeline")
    gate = _required_mapping(payload, "gate")
    if agent.get("runtime_kind") != "cline":
        raise RuntimeError(f"{channel} payload runtime_kind must be cline")
    if agent.get("is_stub") is True:
        raise RuntimeError(f"{channel} payload must not come from a stub runtime")
    if not isinstance(agent.get("agent_run_id"), str) or not str(agent["agent_run_id"]).strip():
        raise RuntimeError(f"{channel} payload must include agent_run_id")
    if not isinstance(agent.get("session_id"), str) or not str(agent["session_id"]).strip():
        raise RuntimeError(f"{channel} payload must include session_id")
    if not isinstance(pipeline.get("plan_id"), str) or not str(pipeline["plan_id"]).strip():
        raise RuntimeError(f"{channel} payload must include plan_id")
    if not isinstance(pipeline.get("simulation_id"), str) or not str(pipeline["simulation_id"]).strip():
        raise RuntimeError(f"{channel} payload must include simulation_id")
    if gate.get("decision") not in {"apply_allowed", "apply_blocked"}:
        raise RuntimeError(f"{channel} payload gate decision must be apply_allowed/apply_blocked")
    if usage["input_tokens"] <= usage["cache_read_tokens"]:
        raise RuntimeError(f"{channel} payload must include uncached billed input tokens")


def _usage_from_payload(payload: dict[str, Any]) -> dict[str, float]:
    return _usage_from_agent_block(payload)


def _usage_summary(sample: _MeasuredPayload) -> dict[str, float]:
    return _usage_from_payload(sample.payload)


def _pair_wall_overhead(
    *,
    direct_sample: _MeasuredPayload,
    mcp_sample: _MeasuredPayload,
) -> float:
    return (mcp_sample.wall_time_seconds - direct_sample.wall_time_seconds) / direct_sample.wall_time_seconds


def _paired_token_overhead(
    *,
    direct_sample: _MeasuredPayload,
    mcp_sample: _MeasuredPayload,
) -> float:
    direct_usage = _usage_summary(direct_sample)
    mcp_usage = _usage_summary(mcp_sample)
    direct_total_tokens = direct_usage["input_tokens"] + direct_usage["output_tokens"]
    mcp_total_tokens = mcp_usage["input_tokens"] + mcp_usage["output_tokens"]
    return (mcp_total_tokens - direct_total_tokens) / direct_total_tokens


def _representative_pair_index(
    *,
    direct_samples: list[_MeasuredPayload],
    mcp_samples: list[_MeasuredPayload],
) -> int:
    if not direct_samples or len(direct_samples) != len(mcp_samples):
        raise RuntimeError("paired competitive measurements require equal direct and mcp samples")
    wall_overheads = [
        _pair_wall_overhead(direct_sample=direct_samples[index], mcp_sample=mcp_samples[index])
        for index in range(len(direct_samples))
    ]
    token_overheads = [
        _paired_token_overhead(direct_sample=direct_samples[index], mcp_sample=mcp_samples[index])
        for index in range(len(direct_samples))
    ]
    median_wall_overhead = statistics.median(wall_overheads)
    median_token_overhead = statistics.median(token_overheads)
    return min(
        range(len(direct_samples)),
        key=lambda index: (
            abs(wall_overheads[index] - median_wall_overhead),
            abs(token_overheads[index] - median_token_overhead),
        ),
    )


def _measurement_artifact_payload(
    *,
    representative: _MeasuredPayload,
    samples: list[_MeasuredPayload],
    representative_pair_index: int,
    channel: str,
) -> tuple[dict[str, Any], float]:
    payload = json.loads(json.dumps(representative.payload))
    payload["measurement_strategy"] = "paired_repetitions_median_overhead"
    payload["repetition_count"] = len(samples)
    payload["representative_pair_index"] = representative_pair_index
    payload["measurement_channel"] = channel
    payload["samples"] = [
        {
            "wall_time_seconds": round(sample.wall_time_seconds, 6),
            "usage": _usage_summary(sample),
            "agent_run_id": sample.payload["agent"]["agent_run_id"],
            "session_id": sample.payload["agent"]["session_id"],
        }
        for sample in samples
    ]
    return payload, representative.wall_time_seconds


def _write_measurement_artifact(
    *,
    root: Path,
    output_path: Path,
    run_id: str,
    schema_version: str,
    channel: str,
    payload: dict[str, Any],
    wall_time_seconds: float,
) -> dict[str, Any]:
    context = build_proof_context(root)
    artifact_payload = {
        **create_artifact_provenance(
            context,
            run_id=run_id,
            schema_version=schema_version,
        ),
        "channel": channel,
        "wall_time_seconds": round(float(wall_time_seconds), 6),
        **payload,
    }
    write_json(output_path, artifact_payload)
    artifact_payload["artifact_path"] = artifact_relative_path(root, output_path)
    return artifact_payload
@contextlib.contextmanager
def _repository_connector(
    *,
    base_url: str,
    api_key: str,
    connector_request: dict[str, Any],
) -> str:
    status_code, payload = request_json(
        "POST",
        f"{base_url}/v1/connectors",
        payload=connector_request,
        headers=_auth_headers(api_key),
        timeout_seconds=60,
    )
    if status_code != 201 or not isinstance(payload, dict):
        raise RuntimeError(
            "failed to create repository connector: "
            + _serialize_error_payload(status_code, payload if isinstance(payload, dict) else {})
        )
    connector_id = payload.get("id")
    if not isinstance(connector_id, str) or not connector_id.strip():
        raise RuntimeError("repository connector create response missing id")
    try:
        yield connector_id
    finally:
        status_code, _ = request_text(
            "DELETE",
            f"{base_url}/v1/connectors/{connector_id}",
            headers=_auth_headers(api_key),
            timeout_seconds=60,
        )
        if status_code not in {200, 204, 404}:
            raise RuntimeError(f"failed to delete repository connector {connector_id}: {status_code}")


def _measure_direct_repository_pipeline(
    *,
    base_url: str,
    api_key: str,
    fixture: _RepositoryPipelineFixture,
) -> _MeasuredPayload:
    with _repository_connector(
        base_url=base_url,
        api_key=api_key,
        connector_request=fixture.connector_request,
    ) as connector_id:
        started_at = time.perf_counter()
        status_code, response = request_json(
            "POST",
            f"{base_url}/v1/repositories/{connector_id}/pipeline",
            payload=fixture.pipeline_request(model_id=VERIFIED_AGENTIC_MODEL_ID),
            headers=_auth_headers(api_key),
            timeout_seconds=180,
        )
        wall_time_seconds = time.perf_counter() - started_at
        if status_code != 200 or not isinstance(response, dict):
            raise RuntimeError(
                "repository pipeline direct run failed: "
                + _serialize_error_payload(status_code, response if isinstance(response, dict) else {})
            )
        envelope = build_repository_pipeline_envelope(
            repository_id=connector_id,
            response=response,
        )
        _assert_verified_agentic_envelope(envelope, channel="direct")
        return _MeasuredPayload(payload=envelope, wall_time_seconds=wall_time_seconds)


async def _run_mcp_pipeline(arguments: dict[str, Any]) -> dict[str, Any]:
    payload = await run_repository_pipeline_handler(arguments)
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise RuntimeError("mcp repository pipeline handler did not return an object")
    return parsed


def _measure_mcp_repository_pipeline(
    *,
    base_url: str,
    api_key: str,
    fixture: _RepositoryPipelineFixture,
) -> _MeasuredPayload:
    with _repository_connector(
        base_url=base_url,
        api_key=api_key,
        connector_request=fixture.connector_request,
    ) as connector_id:
        started_at = time.perf_counter()
        with request_overrides(api_key=api_key, base_url=base_url):
            envelope = asyncio.run(
                _run_mcp_pipeline(
                    {
                        "repository_id": connector_id,
                        **fixture.pipeline_request(model_id=VERIFIED_AGENTIC_MODEL_ID),
                    }
                )
            )
        wall_time_seconds = time.perf_counter() - started_at
        _assert_verified_agentic_envelope(envelope, channel="mcp")
        return _MeasuredPayload(payload=envelope, wall_time_seconds=wall_time_seconds)


def _sidecar_run(
    *,
    base_url: str,
    work_dir: Path,
    provider: str,
    model: str,
    prompt: str,
    injected_context: str,
    tool_profile: str,
    max_iterations: int,
) -> dict[str, Any]:
    request_payload = {
        "working_dir": str(work_dir),
        "prompt": prompt,
        "injected_context": injected_context,
        "suppress_exploration": True,
        "provider": provider,
        "model": model,
        "tool_profile": tool_profile,
        "limits": {"maxIterations": max_iterations},
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/run",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    final_frame: dict[str, Any] | None = None
    with urllib.request.urlopen(request, timeout=400) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            frame = json.loads(line)
            if isinstance(frame, dict) and frame.get("type") == "final":
                final_frame = frame
    if final_frame is None:
        raise RuntimeError("agent-core /run did not emit a final frame")
    telemetry = final_frame.get("telemetry")
    if not isinstance(telemetry, dict):
        raise RuntimeError("agent-core final frame missing telemetry")
    input_uncached = _numeric(telemetry.get("tokens_in_uncached")) or 0.0
    output_tokens = _numeric(telemetry.get("tokens_out")) or 0.0
    cache_read_tokens = _numeric(telemetry.get("cache_read_tokens")) or 0.0
    cache_write_tokens = _numeric(telemetry.get("cache_write_tokens")) or 0.0
    return {
        "status": final_frame.get("status"),
        "terminal_state": final_frame.get("status"),
        "provider": provider,
        "model": model,
        "prompt_family": WARM_CACHE_PROMPT_FAMILY,
        "tool_profile": tool_profile,
        "usage": {
            "inputTokens": input_uncached + cache_read_tokens + cache_write_tokens,
            "outputTokens": output_tokens,
            "cacheReadTokens": cache_read_tokens,
            "cacheWriteTokens": cache_write_tokens,
            "costUsd": _numeric(telemetry.get("total_cost")),
        },
        "event_derived_usage": {
            "input_tokens_uncached": input_uncached,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens,
            "cache_write_tokens": cache_write_tokens,
            "turns": _numeric(telemetry.get("turns")) or 0.0,
        },
    }


def _assert_warm_cache_payload(payload: dict[str, Any], *, label: str) -> None:
    if payload.get("status") != WARM_CACHE_STATUS_SUCCEEDED:
        raise RuntimeError(f"{label} warm-cache run did not complete successfully")
    usage = _required_mapping(payload, "usage")
    input_tokens = _numeric(usage.get("inputTokens"))
    output_tokens = _numeric(usage.get("outputTokens"))
    if input_tokens is None or output_tokens is None:
        raise RuntimeError(f"{label} warm-cache payload must include usage totals")
    if input_tokens <= 0 or output_tokens <= 0:
        raise RuntimeError(f"{label} warm-cache payload must include non-zero usage")


def _aggregate_warm_cache_payload(
    *,
    samples: list[_MeasuredPayload],
) -> tuple[dict[str, Any], float]:
    if not samples:
        raise RuntimeError("warm-cache aggregation requires at least one sample")
    representative = samples[0].payload
    total_usage = {
        "inputTokens": sum(
            _numeric(_required_mapping(sample.payload, "usage").get("inputTokens")) or 0.0
            for sample in samples
        ),
        "outputTokens": sum(
            _numeric(_required_mapping(sample.payload, "usage").get("outputTokens")) or 0.0
            for sample in samples
        ),
        "cacheReadTokens": sum(
            _numeric(_required_mapping(sample.payload, "usage").get("cacheReadTokens")) or 0.0
            for sample in samples
        ),
        "cacheWriteTokens": sum(
            _numeric(_required_mapping(sample.payload, "usage").get("cacheWriteTokens")) or 0.0
            for sample in samples
        ),
        "costUsd": sum(
            _numeric(_required_mapping(sample.payload, "usage").get("costUsd")) or 0.0
            for sample in samples
        ),
    }
    total_event_usage = {
        "input_tokens_uncached": sum(
            _numeric(_required_mapping(sample.payload, "event_derived_usage").get("input_tokens_uncached"))
            or 0.0
            for sample in samples
        ),
        "output_tokens": sum(
            _numeric(_required_mapping(sample.payload, "event_derived_usage").get("output_tokens"))
            or 0.0
            for sample in samples
        ),
        "cache_read_tokens": sum(
            _numeric(_required_mapping(sample.payload, "event_derived_usage").get("cache_read_tokens"))
            or 0.0
            for sample in samples
        ),
        "cache_write_tokens": sum(
            _numeric(_required_mapping(sample.payload, "event_derived_usage").get("cache_write_tokens"))
            or 0.0
            for sample in samples
        ),
        "turns": sum(
            _numeric(_required_mapping(sample.payload, "event_derived_usage").get("turns")) or 0.0
            for sample in samples
        ),
    }
    payload = {
        "status": WARM_CACHE_STATUS_SUCCEEDED,
        "terminal_state": WARM_CACHE_STATUS_SUCCEEDED,
        "provider": representative["provider"],
        "model": representative["model"],
        "prompt_family": representative["prompt_family"],
        "tool_profile": representative["tool_profile"],
        "usage": total_usage,
        "event_derived_usage": total_event_usage,
        "measurement_strategy": "suite_sum_across_tasks",
        "task_count": len(samples),
        "samples": [
            {
                "task_name": sample.payload.get("task_name"),
                "wall_time_seconds": round(sample.wall_time_seconds, 6),
                "usage": _required_mapping(sample.payload, "usage"),
            }
            for sample in samples
        ],
    }
    wall_time_seconds = sum(sample.wall_time_seconds for sample in samples)
    return payload, wall_time_seconds


def _warm_billed_input_tokens(sample: _MeasuredPayload) -> float:
    usage = _required_mapping(sample.payload, "usage")
    input_tokens = _numeric(usage.get("inputTokens")) or 0.0
    cache_read_tokens = _numeric(usage.get("cacheReadTokens")) or 0.0
    return input_tokens - cache_read_tokens


def _representative_warm_pair_index(
    *,
    cold_samples: list[_MeasuredPayload],
    warm_samples: list[_MeasuredPayload],
) -> int:
    if not cold_samples or len(cold_samples) != len(warm_samples):
        raise RuntimeError("warm-cache repetitions require equal cold and warm sample counts")
    ratios = [
        _warm_billed_input_tokens(warm_samples[index]) / _warm_billed_input_tokens(cold_samples[index])
        for index in range(len(cold_samples))
    ]
    median_ratio = statistics.median(ratios)
    return min(
        range(len(cold_samples)),
        key=lambda index: abs(ratios[index] - median_ratio),
    )


def _warm_suite_artifact_payload(
    *,
    representative: _MeasuredPayload,
    samples: list[_MeasuredPayload],
    representative_pair_index: int,
    label: str,
) -> tuple[dict[str, Any], float]:
    payload = json.loads(json.dumps(representative.payload))
    payload["measurement_strategy"] = "paired_suite_repetitions_median_ratio"
    payload["repetition_count"] = len(samples)
    payload["representative_pair_index"] = representative_pair_index
    payload["measurement_label"] = label
    payload["samples"] = [
        {
            "wall_time_seconds": round(sample.wall_time_seconds, 6),
            "task_count": sample.payload.get("task_count"),
            "usage": _required_mapping(sample.payload, "usage"),
        }
        for sample in samples
    ]
    return payload, representative.wall_time_seconds


def collect_live_cursor_mcp_comparison_artifact(
    *,
    api_key: str,
    root: Path | str | None = None,
    g0_artifact_path: Path | str | None = None,
    repetitions: int = 4,
    output_path: Path | str | None = None,
    direct_output_path: Path | str | None = None,
    mcp_output_path: Path | str | None = None,
) -> dict[str, Any]:
    if repetitions <= 0:
        raise RuntimeError("repetitions must be positive")
    resolved_root = repo_root() if root is None else Path(root).resolve()
    resolved_g0_artifact_path = (
        resolved_root / "build" / "proofs" / "cline" / "g0_token_benchmark.json"
        if g0_artifact_path is None
        else Path(g0_artifact_path).resolve()
    )
    g0_payload = read_json(resolved_g0_artifact_path)
    if not isinstance(g0_payload, dict):
        raise RuntimeError("g0 benchmark artifact must contain a JSON object")
    anthropic_api_key = _required_string_env("ANTHROPIC_API_KEY")
    resolved_output_path = (
        resolved_root / CURSOR_MCP_COMPARISON_PATH
        if output_path is None
        else Path(output_path).resolve()
    )
    resolved_direct_output_path = (
        resolved_root / DIRECT_REPOSITORY_PIPELINE_PATH
        if direct_output_path is None
        else Path(direct_output_path).resolve()
    )
    resolved_mcp_output_path = (
        resolved_root / MCP_REPOSITORY_PIPELINE_PATH
        if mcp_output_path is None
        else Path(mcp_output_path).resolve()
    )

    with agent_core_runtime(
        resolved_root,
        extra_env={"ANTHROPIC_API_KEY": anthropic_api_key},
    ) as agent_base_url:
        with local_api_server(
            resolved_root,
            extra_env={
                "ALGENTA_REPOSITORIES_PIPELINE_ENABLED": "true",
                "ALGENTA_AGENT_CORE_URL": agent_base_url,
                "ALGENTA_REPOSITORY_AGENT_TOOL_PROFILE": VERIFIED_AGENT_TOOL_PROFILE,
            },
        ) as api_base_url:
            direct_samples: list[_MeasuredPayload] = []
            mcp_samples: list[_MeasuredPayload] = []
            for index in range(repetitions):
                direct_first = index % 2 == 0
                if direct_first:
                    with _repository_pipeline_fixture(f"direct-{index + 1}") as direct_fixture:
                        direct_samples.append(
                            _measure_direct_repository_pipeline(
                                base_url=api_base_url,
                                api_key=api_key,
                                fixture=direct_fixture,
                            )
                        )
                    with _repository_pipeline_fixture(f"mcp-{index + 1}") as mcp_fixture:
                        mcp_samples.append(
                            _measure_mcp_repository_pipeline(
                                base_url=api_base_url,
                                api_key=api_key,
                                fixture=mcp_fixture,
                            )
                        )
                    continue
                with _repository_pipeline_fixture(f"mcp-{index + 1}") as mcp_fixture:
                    mcp_samples.append(
                        _measure_mcp_repository_pipeline(
                            base_url=api_base_url,
                            api_key=api_key,
                            fixture=mcp_fixture,
                        )
                    )
                with _repository_pipeline_fixture(f"direct-{index + 1}") as direct_fixture:
                    direct_samples.append(
                        _measure_direct_repository_pipeline(
                            base_url=api_base_url,
                            api_key=api_key,
                            fixture=direct_fixture,
                        )
                    )

    representative_pair_index = _representative_pair_index(
        direct_samples=direct_samples,
        mcp_samples=mcp_samples,
    )
    direct_payload, direct_wall_time_seconds = _measurement_artifact_payload(
        representative=direct_samples[representative_pair_index],
        samples=direct_samples,
        representative_pair_index=representative_pair_index,
        channel="direct",
    )
    mcp_payload, mcp_wall_time_seconds = _measurement_artifact_payload(
        representative=mcp_samples[representative_pair_index],
        samples=mcp_samples,
        representative_pair_index=representative_pair_index,
        channel="mcp",
    )

    direct_artifact_payload = _write_measurement_artifact(
        root=resolved_root,
        output_path=resolved_direct_output_path,
        run_id="direct_repository_pipeline",
        schema_version="cline-competitive-direct-repository-pipeline/v1",
        channel="api",
        payload=direct_payload,
        wall_time_seconds=direct_wall_time_seconds,
    )
    mcp_artifact_payload = _write_measurement_artifact(
        root=resolved_root,
        output_path=resolved_mcp_output_path,
        run_id="mcp_repository_pipeline",
        schema_version="cline-competitive-mcp-repository-pipeline/v1",
        channel="mcp",
        payload=mcp_payload,
        wall_time_seconds=mcp_wall_time_seconds,
    )
    artifact = build_cursor_mcp_comparison_artifact(
        g0_payload=g0_payload,
        direct_payload=direct_artifact_payload,
        mcp_payload=mcp_artifact_payload,
        direct_wall_time_seconds=direct_wall_time_seconds,
        mcp_wall_time_seconds=mcp_wall_time_seconds,
        root=resolved_root,
        output_path=resolved_output_path,
        direct_source_path=resolved_direct_output_path,
        mcp_source_path=resolved_mcp_output_path,
    )
    artifact["artifact_path"] = artifact_relative_path(resolved_root, resolved_output_path)
    return artifact


def collect_live_warm_cache_comparison_artifact(
    *,
    root: Path | str | None = None,
    g0_artifact_path: Path | str | None = None,
    warm_repetitions: int = 5,
    output_path: Path | str | None = None,
    cold_output_path: Path | str | None = None,
    warm_output_path: Path | str | None = None,
) -> dict[str, Any]:
    if warm_repetitions <= 0:
        raise RuntimeError("warm_repetitions must be positive")
    resolved_root = repo_root() if root is None else Path(root).resolve()
    resolved_g0_artifact_path = (
        resolved_root / "build" / "proofs" / "cline" / "g0_token_benchmark.json"
        if g0_artifact_path is None
        else Path(g0_artifact_path).resolve()
    )
    g0_payload = read_json(resolved_g0_artifact_path)
    if not isinstance(g0_payload, dict):
        raise RuntimeError("g0 benchmark artifact must contain a JSON object")
    provider = str(g0_payload.get("provider") or WARM_CACHE_PROVIDER)
    model = str(g0_payload.get("model") or _required_string_env("G0_ANTHROPIC_MODEL"))
    anthropic_api_key = _required_string_env("ANTHROPIC_API_KEY")
    resolved_output_path = (
        resolved_root / WARM_CACHE_COMPARISON_PATH
        if output_path is None
        else Path(output_path).resolve()
    )
    resolved_cold_output_path = (
        resolved_root / WARM_CACHE_COLD_RUN_PATH
        if cold_output_path is None
        else Path(cold_output_path).resolve()
    )
    resolved_warm_output_path = (
        resolved_root / WARM_CACHE_WARM_RUN_PATH
        if warm_output_path is None
        else Path(warm_output_path).resolve()
    )

    cold_repetition_samples: list[_MeasuredPayload] = []
    warm_repetition_samples: list[_MeasuredPayload] = []

    with agent_core_runtime(
        resolved_root,
        extra_env={"ANTHROPIC_API_KEY": anthropic_api_key},
    ) as agent_base_url:
        for repetition_index in range(warm_repetitions):
            cold_task_samples: list[_MeasuredPayload] = []
            warm_task_samples: list[_MeasuredPayload] = []
            for task in WARM_CACHE_TASKS:
                cache_series_id = (
                    f"cline-warm-cache-{repetition_index + 1}-{task.name}-{time.time_ns()}"
                )
                injected_context = (
                    f"{task.injected_context}\nCACHE_SERIES_ID={cache_series_id}\n"
                )
                with _warm_cache_fixture(task) as fixture_dir:
                    cold_started_at = time.perf_counter()
                    cold_payload = _sidecar_run(
                        base_url=agent_base_url,
                        work_dir=fixture_dir,
                        provider=provider,
                        model=model,
                        prompt=task.prompt,
                        injected_context=injected_context,
                        tool_profile=WARM_CACHE_TOOL_PROFILE,
                        max_iterations=WARM_CACHE_MAX_ITERATIONS,
                    )
                    cold_wall_time_seconds = time.perf_counter() - cold_started_at
                    cold_payload["task_name"] = task.name
                    _assert_warm_cache_payload(cold_payload, label=f"cold:{task.name}")
                    cold_task_samples.append(
                        _MeasuredPayload(
                            payload=cold_payload,
                            wall_time_seconds=cold_wall_time_seconds,
                        )
                    )
                    _reset_warm_cache_fixture(fixture_dir, task)

                    warm_started_at = time.perf_counter()
                    warm_payload = _sidecar_run(
                        base_url=agent_base_url,
                        work_dir=fixture_dir,
                        provider=provider,
                        model=model,
                        prompt=task.prompt,
                        injected_context=injected_context,
                        tool_profile=WARM_CACHE_TOOL_PROFILE,
                        max_iterations=WARM_CACHE_MAX_ITERATIONS,
                    )
                    warm_wall_time_seconds = time.perf_counter() - warm_started_at
                    warm_payload["task_name"] = task.name
                    _assert_warm_cache_payload(warm_payload, label=f"warm:{task.name}")
                    warm_task_samples.append(
                        _MeasuredPayload(
                            payload=warm_payload,
                            wall_time_seconds=warm_wall_time_seconds,
                        )
                    )
            cold_repetition_payload, cold_repetition_wall = _aggregate_warm_cache_payload(
                samples=cold_task_samples
            )
            warm_repetition_payload, warm_repetition_wall = _aggregate_warm_cache_payload(
                samples=warm_task_samples
            )
            cold_repetition_samples.append(
                _MeasuredPayload(
                    payload=cold_repetition_payload,
                    wall_time_seconds=cold_repetition_wall,
                )
            )
            warm_repetition_samples.append(
                _MeasuredPayload(
                    payload=warm_repetition_payload,
                    wall_time_seconds=warm_repetition_wall,
                )
            )

    representative_pair_index = _representative_warm_pair_index(
        cold_samples=cold_repetition_samples,
        warm_samples=warm_repetition_samples,
    )
    cold_payload, cold_wall_time_seconds = _warm_suite_artifact_payload(
        representative=cold_repetition_samples[representative_pair_index],
        samples=cold_repetition_samples,
        representative_pair_index=representative_pair_index,
        label="cold",
    )
    warm_payload, warm_wall_time_seconds = _warm_suite_artifact_payload(
        representative=warm_repetition_samples[representative_pair_index],
        samples=warm_repetition_samples,
        representative_pair_index=representative_pair_index,
        label="warm",
    )

    cold_artifact_payload = _write_measurement_artifact(
        root=resolved_root,
        output_path=resolved_cold_output_path,
        run_id="warm_cache_cold_run",
        schema_version="cline-warm-cache-live-run/v1",
        channel="agent_core_direct",
        payload=cold_payload,
        wall_time_seconds=cold_wall_time_seconds,
    )
    warm_artifact_payload = _write_measurement_artifact(
        root=resolved_root,
        output_path=resolved_warm_output_path,
        run_id="warm_cache_warm_run",
        schema_version="cline-warm-cache-live-run/v1",
        channel="agent_core_direct",
        payload=warm_payload,
        wall_time_seconds=warm_wall_time_seconds,
    )
    artifact = build_warm_cache_comparison_artifact(
        g0_payload=g0_payload,
        cold_payload=cold_artifact_payload,
        warm_payload=warm_artifact_payload,
        root=resolved_root,
        output_path=resolved_output_path,
        cold_source_path=resolved_cold_output_path,
        warm_source_path=resolved_warm_output_path,
    )
    artifact["artifact_path"] = artifact_relative_path(resolved_root, resolved_output_path)
    return artifact
