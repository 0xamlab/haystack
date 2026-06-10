"""AR-OPT-1: prompt-caching + usage-capture tests for the repository planner.

The ``provider_backed_chat`` tier must place the stable evidence bundle in a
byte-identical SYSTEM block (so Anthropic prompt-caching reuses the prefix across
repeated calls) and record each LLM call's token usage — including the cache
read/write split — into the telemetry context opened by the pipeline entrypoint.
"""
from __future__ import annotations

import json

from apps.api_server.services import repository_intelligence_planner_generation as planner
from apps.api_server.services import repository_intelligence_telemetry as telemetry
from apps.api_server.services.llm_api_service import ChatCompletionResult

_DETERMINISTIC_MODEL = "repository.deterministic_local_v1"

_SNAPSHOT_MANIFEST = {
    "snapshot_id": "snap-123",
    "resolved_revision": "abc123def",
}
_TRIAGE_MANIFEST = {
    "signals": {"diagnostics": ["E001"]},
    "evidence_items": [
        {"path": "src/app.py", "score": 0.9, "snippet": "def f():\n    return 1"},
    ],
}

_PLAN_JSON = json.dumps(
    {
        "root_cause": "off-by-one in f()",
        "candidate_fixes": ["return 2 instead of 1"],
        "recommended_action": "apply patch",
        "rationale": "the test expects 2",
        "confidence": 0.7,
        "patch_diff": (
            "--- a/src/app.py\n+++ b/src/app.py\n@@ -1,2 +1,2 @@\n"
            " def f():\n-    return 1\n+    return 2\n"
        ),
    }
)


def _fake_completion(*, cache_read: int = 0, cache_write: int = 0) -> ChatCompletionResult:
    return ChatCompletionResult(
        completion_id="cmp-1",
        content=_PLAN_JSON,
        prompt_tokens=100,
        completion_tokens=20,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )


async def _run_provider_plan() -> dict:
    return await planner._generate_repository_patch_plan(
        model_id="provider.claude",
        snapshot_manifest=dict(_SNAPSHOT_MANIFEST),
        triage_manifest={k: v for k, v in _TRIAGE_MANIFEST.items()},
        deterministic_local_model_id=_DETERMINISTIC_MODEL,
    )


async def test_provider_backed_planner_builds_stable_system_bundle(monkeypatch) -> None:
    captured: list[list[dict[str, str]]] = []

    async def _fake_create_chat_completion(*, model_id, messages, max_output_tokens=None):
        captured.append({"messages": messages, "max_output_tokens": max_output_tokens})
        return None, _fake_completion()

    monkeypatch.setattr(planner, "create_chat_completion", _fake_create_chat_completion)
    monkeypatch.setattr(planner, "get_configured_provider_model", lambda _model: None)

    first = await _run_provider_plan()
    await _run_provider_plan()

    assert first["planner_execution_mode"] == "provider_backed_chat"

    # AR-OPT-5: the planner sizes a dynamic output budget (never the fixed 512).
    assert captured[0]["max_output_tokens"] is not None
    assert 1024 <= captured[0]["max_output_tokens"] <= 4096

    # Two independent calls must emit a byte-identical system block: that stable
    # prefix is exactly what Anthropic prompt-caching keys on.
    system_first = next(m["content"] for m in captured[0]["messages"] if m["role"] == "system")
    system_second = next(m["content"] for m in captured[1]["messages"] if m["role"] == "system")
    assert system_first == system_second

    # The evidence bundle lives in the SYSTEM block (cacheable), not the user turn.
    assert "snap-123" in system_first
    assert '"evidence_items"' in system_first
    user_first = next(m["content"] for m in captured[0]["messages"] if m["role"] == "user")
    assert "snap-123" not in user_first
    assert "evidence_items" not in user_first

    # The bundle is serialized deterministically (sorted keys, compact separators)
    # so the cache prefix is byte-stable regardless of source dict ordering.
    bundle_text = system_first.split("authoritative):\n", 1)[1]
    reparsed = json.loads(bundle_text)
    assert bundle_text == json.dumps(reparsed, sort_keys=True, separators=(",", ":"))


async def test_provider_backed_planner_records_token_usage(monkeypatch) -> None:
    async def _fake_create_chat_completion(*, model_id, messages, max_output_tokens=None):
        return None, _fake_completion(cache_read=80, cache_write=15)

    monkeypatch.setattr(planner, "create_chat_completion", _fake_create_chat_completion)
    monkeypatch.setattr(planner, "get_configured_provider_model", lambda _model: None)

    with telemetry.collect() as data:
        await _run_provider_plan()

    counters = data["counters"]
    assert counters["llm_input_tokens_uncached"] == 100
    assert counters["llm_input_tokens_cached_read"] == 80
    assert counters["llm_input_tokens_cached_write"] == 15
    assert counters["llm_output_tokens"] == 20
    # Token telemetry must be complete for the AR-OPT-0 CI presence gate.
    assert not telemetry.missing_fields(data, telemetry.TOKEN_FIELDS, kind="counters")
    # AR-OPT-5b: a shadow routing decision is emitted (observe-only) for this tier.
    shadow = [e for e in data["events"] if e["name"] == "routing_decision_shadow"]
    assert shadow and shadow[0]["payload"]["actual_requested_tier"] == "provider_backed_chat"


def test_provider_chat_payload_dynamic_max_tokens() -> None:
    """AR-OPT-5: the anthropic payload honors a caller-supplied output budget and
    falls back to 512 only when none is given."""
    from apps.api_server.services.llm_provider_service._config import ProviderModelConfig
    from apps.api_server.services.llm_provider_service._payload_builders import (
        _provider_chat_payload,
    )

    config = ProviderModelConfig(
        model_id="provider.claude",
        backend="anthropic",
        base_url="https://api.anthropic.com/v1",
        upstream_model="claude-3-5-sonnet-latest",
        api_key_env="ANTHROPIC_API_KEY",
        description="Provider-backed chat model.",
        capabilities=("chat_completions",),
    )
    messages = [{"role": "user", "content": "hi"}]
    assert _provider_chat_payload(config=config, messages=messages)["max_tokens"] == 512
    assert (
        _provider_chat_payload(config=config, messages=messages, max_output_tokens=2048)[
            "max_tokens"
        ]
        == 2048
    )
