"""Normalization, request loading, streaming/render helpers.

Extracted from apps/cli/main.py during modularization.
"""
from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from pydantic import ValidationError

from apps.cli import data_commands as _data_commands
from apps.cli.support import (
    CONFIG_FILE,
    load_config,
    print_result,
    save_config,
)
from apps.cli.support import (
    arg_value as _arg_value,
)
from apps.cli.support import (
    store_api_key_secure as _store_api_key_secure,
)
from apps.cli.support import (
    strip_none as _strip_none,
)
from apps.platform_contract import PlatformContractResponse
from apps.platform_contract_fallback import (
    PlatformContractFallbackError,
    build_platform_contract_from_openapi,
)
from apps.validation_error_details import format_validation_error_message

_RUNTIME_READY_TIMEOUT_SECONDS = 3.0
_RUNTIME_READY_POLL_SECONDS = 0.1
_RUNTIME_NOT_RUNNING_MESSAGE = "Algenta Runtime is not running. Start with: de runtime start"


# Facade-routed proxies. Tests monkey-patch these on `apps.cli.main` (the
# facade) and expect the submodule call sites to see the patched values.
# Each wrapper does a fresh `from apps.cli import main as _facade` lookup so
# monkeypatch.setattr(cli_main, "X", fake) is honored.
def _load_env_api_key():
    from apps.cli import main as _facade
    return _facade._load_env_api_key()


def _private_profile_enabled():
    from apps.cli import main as _facade
    return _facade._private_profile_enabled()


def _get_base_url():
    from apps.cli import main as _facade
    return _facade._get_base_url()


def _get_dashboard_url():
    from apps.cli import main as _facade
    return _facade._get_dashboard_url()


def api_request(*args, **kwargs):
    from apps.cli import main as _facade
    return _facade.api_request(*args, **kwargs)


def api_stream_request(*args, **kwargs):
    from apps.cli import main as _facade
    return _facade.api_stream_request(*args, **kwargs)


class _RichProxy:
    """Boolean-like proxy that reads `_RICH` from the facade at access time.

    Submodule code uses `_RICH` as a boolean (`if _RICH:` or
    `rich_enabled=_RICH`); when a test monkey-patches `cli_main._RICH = False`,
    bool(_RICH) follows the new value.
    """
    __slots__ = ()

    def __bool__(self) -> bool:
        from apps.cli import main as _facade
        return bool(_facade._RICH)

    def __eq__(self, other: object) -> bool:
        return bool(self) == bool(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __repr__(self) -> str:
        return repr(bool(self))

    def __hash__(self) -> int:
        return hash(bool(self))


_RICH = _RichProxy()



def _normalize_expert_variable(variable: dict[str, Any]) -> dict[str, Any]:
    if isinstance(variable.get("params"), dict):
        params = dict(variable.get("params", {}))
    else:
        params = _strip_none(
            {
                "mean": variable.get("mean"),
                "std": variable.get("std") or variable.get("std_dev"),
                "low": variable.get("low"),
                "mode": variable.get("mode"),
                "high": variable.get("high"),
                "value": variable.get("value"),
                "min": variable.get("min"),
                "max": variable.get("max"),
                "p": variable.get("p"),
                "shape": variable.get("shape"),
                "scale": variable.get("scale"),
            }
        )
    return {
        "name": variable.get("name", "value"),
        "distribution": variable.get("distribution", "fixed"),
        "params": params,
    }


def _load_benchmark_summary(root: Path) -> tuple[dict[str, Any] | None, Path | None]:
    candidates = (
        root / "build" / "llm_rollout_parity_benchmark.json",
        root / "benchmarks" / "summary.json",
    )
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("libraries"), list):
            return payload, path
    return None, None


def _display_benchmark_source(root: Path, source_path: Path | None) -> str | None:
    if source_path is None:
        return None
    try:
        return str(source_path.relative_to(root))
    except ValueError:
        return str(source_path)


def _format_speedup_value(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _normalize_simulation_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "scenario" in payload or "simulation" in payload:
        return payload

    variables = payload.get("variables")
    if isinstance(variables, dict):
        normalized: dict[str, Any] = {
            "mode": "auto",
            "scenario": {
                "variables": variables,
                "objective": payload.get("objective", "maximize_net_value"),
            },
            "runs": payload.get("runs", 10_000),
        }
        if payload.get("seed") is not None:
            normalized["seed"] = payload["seed"]
        if payload.get("simulation_model") is not None:
            normalized["simulation_model"] = payload["simulation_model"]
        return normalized

    if isinstance(variables, list):
        variable_names = [v.get("name", "value") for v in variables if isinstance(v, dict)]
        objective = (
            payload.get("objective_function")
            or payload.get("objective")
            or " + ".join(variable_names)
            or "value"
        )
        normalized = {
            "mode": "expert",
            "simulation": {
                "variables": [
                    _normalize_expert_variable(v) for v in variables if isinstance(v, dict)
                ],
                "objective_function": objective,
                "scoring": payload.get("scoring", {"expected_value": 0.6, "downside_risk": 0.4}),
            },
            "runs": payload.get("runs", 10_000),
        }
        if payload.get("seed") is not None:
            normalized["seed"] = payload["seed"]
        if payload.get("simulation_model") is not None:
            normalized["simulation_model"] = payload["simulation_model"]
        return normalized

    return payload


def _normalize_recommend_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "actions" in payload:
        return payload
    if "options" not in payload:
        return payload

    normalized_actions: list[dict[str, Any]] = []
    for idx, option in enumerate(payload.get("options", []), start=1):
        name = option.get("label") or option.get("name") or f"option_{idx}"
        expected_value = float(option.get("expected_value", 0.0) or 0.0)
        risk = max(float(option.get("risk", 0.1) or 0.1), 0.05)
        spread = max(abs(expected_value) * risk, 1.0)
        normalized_actions.append(
            {
                "name": name,
                "request": {
                    "mode": "expert",
                    "simulation": {
                        "variables": [
                            {
                                "name": "outcome",
                                "distribution": "triangular",
                                "params": {
                                    "low": expected_value - spread,
                                    "mode": expected_value,
                                    "high": expected_value + spread,
                                },
                            }
                        ],
                        "objective_function": "outcome",
                        "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
                    },
                    "runs": payload.get("runs", 1000),
                },
            }
        )
    return {"actions": normalized_actions, "runs": payload.get("runs", 1000)}


def _normalize_score_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "request" in payload:
        normalized = dict(payload)
        if isinstance(normalized.get("request"), dict):
            normalized["request"] = _normalize_simulation_request(normalized["request"])
        return normalized
    return {"request": _normalize_simulation_request(payload)}


def _normalize_batch_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "items" not in payload or not isinstance(payload.get("items"), list):
        return payload
    normalized = dict(payload)
    normalized["items"] = [
        _normalize_simulation_request(item) if isinstance(item, dict) else item
        for item in normalized["items"]
    ]
    return normalized


def _normalize_compare_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "scenarios" not in payload or not isinstance(payload.get("scenarios"), list):
        return payload
    normalized = dict(payload)
    scenarios: list[dict[str, Any]] = []
    for index, scenario in enumerate(payload["scenarios"], start=1):
        if not isinstance(scenario, dict):
            continue
        if "request" in scenario and isinstance(scenario["request"], dict):
            scenarios.append(
                {
                    **scenario,
                    "request": _normalize_simulation_request(scenario["request"]),
                }
            )
            continue
        name = scenario.get("name") or scenario.get("label") or f"scenario_{index}"
        request_payload = {
            key: value
            for key, value in scenario.items()
            if key not in {"name", "label"}
        }
        scenarios.append(
            {
                "name": name,
                "request": _normalize_simulation_request(request_payload),
            }
        )
    normalized["scenarios"] = scenarios
    return normalized


def _load_request_json(filepath: str) -> dict[str, Any]:
    payload = json.loads(Path(filepath).read_text())
    if not isinstance(payload, dict):
        raise ValueError("Request payload must be a JSON object.")
    return payload


def _print_api_error_and_exit(status: int, data: Any) -> None:
    print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
    sys.exit(1)


def _print_streaming_request_error_and_exit(exc: RuntimeError) -> None:
    try:
        payload = json.loads(str(exc))
    except json.JSONDecodeError:
        print(f"❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)
    if isinstance(payload, dict) and isinstance(payload.get("status"), int):
        _print_api_error_and_exit(int(payload["status"]), payload.get("body"))
    print(f"❌ Error: {json.dumps(payload, indent=2)}", file=sys.stderr)
    sys.exit(1)


def _stream_payloads(method: str, path: str, body: Any = None) -> Iterator[dict[str, Any]]:
    try:
        yield from api_stream_request(method, path, body)
    except RuntimeError as exc:
        _print_streaming_request_error_and_exit(exc)


def _print_sse_payloads(payloads: Iterator[dict[str, Any]], *, format: str) -> None:
    if format == "json":
        for payload in payloads:
            print(json.dumps(payload, default=str))
        return
    for payload in payloads:
        print(json.dumps(payload, indent=2, default=str))


def _print_chat_stream(payloads: Iterator[dict[str, Any]], *, format: str) -> None:
    if format == "json":
        _print_sse_payloads(payloads, format=format)
        return

    completion_id: str | None = None
    model_id: str | None = None
    finish_reason: str | None = None
    content_chunks: list[str] = []

    for payload in payloads:
        completion_id = completion_id or payload.get("id")
        model_id = model_id or payload.get("model")
        choice = (payload.get("choices") or [{}])[0]
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta") or {}
        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str):
                content_chunks.append(content)
        if choice.get("finish_reason") is not None:
            finish_reason = str(choice.get("finish_reason"))

    print()
    print(f"Completion ID:  {completion_id}")
    print(f"Model:          {model_id}")
    print(f"Assistant:      {''.join(content_chunks)}")
    if finish_reason is not None:
        print(f"Finish reason:  {finish_reason}")
    print()


def _render_response_stream_table(payload: dict[str, Any]) -> str:
    event_type = payload.get("type")
    if event_type == "response.created":
        response = payload.get("response") or {}
        return (
            f"Response created: {response.get('id')} "
            f"status={response.get('status')} model={response.get('model')}"
        )
    if event_type == "response.output_item.done":
        item = payload.get("item") or {}
        output_index = payload.get("output_index")
        content = (item.get("content") or [{}])[0]
        if isinstance(content, dict):
            if content.get("text") is not None:
                rendered = content.get("text")
            elif content.get("token_count") is not None:
                rendered = f"tokens={content.get('token_count')}"
            elif content.get("embedding") is not None:
                embedding = content.get("embedding") or []
                rendered = f"embedding_dims={len(embedding)}"
            else:
                rendered = content.get("type")
        else:
            rendered = str(content)
        return f"Output item #{output_index}: {rendered}"
    if event_type == "response.completed":
        response = payload.get("response") or {}
        usage = response.get("usage") or {}
        return (
            f"Response completed: {response.get('id')} "
            f"status={response.get('status')} total_tokens={usage.get('total_tokens')}"
        )
    return json.dumps(payload, default=str)


def _print_response_stream(payloads: Iterator[dict[str, Any]], *, format: str) -> None:
    if format == "json":
        _print_sse_payloads(payloads, format=format)
        return
    print()
    for payload in payloads:
        print(_render_response_stream_table(payload))
    print()


def _render_agent_run_stream_table(payload: dict[str, Any]) -> str:
    event_type = payload.get("type")
    if event_type == "agent.run.event":
        event = payload.get("event") or {}
        return (
            f"{event.get('created_at')}  {event.get('event_type')}  "
            f"{event.get('status')}  {event.get('message')}"
        )
    if event_type == "agent.run.completed":
        return (
            f"Run completed:  {payload.get('run_id')}  "
            f"status={payload.get('status')} total_events={payload.get('total_events')}"
        )
    return json.dumps(payload, default=str)


def _print_agent_run_event_stream(payloads: Iterator[dict[str, Any]], *, format: str) -> None:
    if format == "json":
        _print_sse_payloads(payloads, format=format)
        return
    print()
    for payload in payloads:
        print(_render_agent_run_stream_table(payload))
    print()

def _load_json_object_file(filepath: str, *, context: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(filepath).read_text())
    except FileNotFoundError as exc:
        raise RuntimeError(f"{context} file not found: {filepath}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{context} file is not valid JSON: {filepath}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{context} file must contain a JSON object: {filepath}")
    return payload


def _normalize_metering_payload(payload: dict[str, Any]) -> dict[str, Any]:
    device_id = payload.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise RuntimeError("Metering request must include a non-empty device_id.")
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise RuntimeError("Metering request must include a non-empty events list.")
    allowed_keys = {
        "event_type",
        "module",
        "function",
        "engine_used",
        "latency_ms",
        "success",
        "timestamp",
        "request_id",
    }
    normalized_events: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise RuntimeError(f"Metering event {index} must be a JSON object.")
        unexpected_keys = sorted(set(event) - allowed_keys)
        if unexpected_keys:
            raise RuntimeError(
                f"Metering event {index} contains unsupported fields: {', '.join(unexpected_keys)}."
            )
        normalized_event: dict[str, Any] = {}
        for key in ("event_type", "module", "function", "engine_used", "request_id"):
            if key in event:
                value = event[key]
                if not isinstance(value, str):
                    raise RuntimeError(f"Metering event {index}.{key} must be a string.")
                normalized_event[key] = value.strip()
        for key in ("latency_ms", "timestamp"):
            if key in event:
                value = event[key]
                if isinstance(value, bool) or not isinstance(value, int | float):
                    raise RuntimeError(f"Metering event {index}.{key} must be a number.")
                normalized_event[key] = float(value)
        if "success" in event:
            value = event["success"]
            if not isinstance(value, bool):
                raise RuntimeError(f"Metering event {index}.success must be a boolean.")
            normalized_event["success"] = value
        normalized_events.append(normalized_event)
    return {"device_id": device_id.strip(), "events": normalized_events}


def _normalize_credit_refresh_payload(payload: dict[str, Any]) -> dict[str, Any]:
    device_id = payload.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise RuntimeError("Credit refresh request must include a non-empty device_id.")
    billing_period = payload.get("billing_period")
    if not isinstance(billing_period, str) or len(billing_period) != 7:
        raise RuntimeError("Credit refresh request must include a YYYY-MM billing_period.")
    year_text, dash, month_text = billing_period.partition("-")
    if (
        dash != "-"
        or not year_text.isdigit()
        or len(year_text) != 4
        or not month_text.isdigit()
        or len(month_text) != 2
    ):
        raise RuntimeError("Credit refresh request must include a YYYY-MM billing_period.")
    month = int(month_text)
    if month < 1 or month > 12:
        raise RuntimeError("Credit refresh request billing_period month must be between 01 and 12.")
    credits_used = payload.get("credits_used", 0)
    if isinstance(credits_used, bool) or not isinstance(credits_used, int) or credits_used < 0:
        raise RuntimeError("Credit refresh request credits_used must be a non-negative integer.")
    return {
        "device_id": device_id.strip(),
        "billing_period": billing_period,
        "credits_used": credits_used,
    }

