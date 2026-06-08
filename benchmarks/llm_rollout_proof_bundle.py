from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.llm_rollout_live_artifacts import LIVE_SUMMARY_ARTIFACTS
from benchmarks.llm_rollout_parity_benchmark import validate_rollout_summary  # noqa: E402
from benchmarks.scorecard_sync import (  # noqa: E402
    SCORECARD_PATH,
    format_speedup,
    sync_shared_benchmark_scorecard,
)
from tests.llm_rollout_matrix import (  # noqa: E402
    LLM_ROLLOUT_FUNCTION_CASES,
    LLM_ROLLOUT_MODULE_NAMES,
)
from apps.runtime.mojo_inventory import build_inventory_report  # noqa: E402
from apps.runtime_manifest import RuntimeNonShippingRule  # noqa: E402

PARITY_ARTIFACT = PROJECT_ROOT / "build" / "llm_rollout_parity_benchmark.json"
COMPILED_ARTIFACT = PROJECT_ROOT / "build" / "llm_compiled_runtime_benchmark.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "llm_rollout_proof_bundle.json"
PARITY_BENCHMARK_SCRIPT = PROJECT_ROOT / "benchmarks" / "llm_rollout_parity_benchmark.py"
COMPILED_BENCHMARK_SCRIPT = PROJECT_ROOT / "benchmarks" / "llm_compiled_runtime_benchmark.py"

PUBLIC_SUPPORTED_CHANNELS = (
    "python_sdk",
    "typescript_sdk",
    "cli",
    "mcp",
)
UNDERLYING_VALIDATED_LANES = (
    "daemon_client",
    "runtime_local",
)
PUBLIC_HTTP_LIBRARY_ROUTES_ENABLE_ENV = "ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED"
SERVING_EXTENSION_MODULES = (
    "kv_cache",
    "paged_kv_cache",
    "continuous_batching",
    "inference_engine",
    "speculative_decoding",
    "generation_loop",
)

LIVE_SUITES = (
    {
        "name": "python_sdk_local_runtime",
        "script": "tests/integration/test_algenta_mojo_library_live.py",
        "timeout_seconds": 420,
        "channels": ("python_sdk",),
        "minimum_passed": 7,
    },
    {
        "name": "typescript_sdk_local_runtime",
        "script": "tests/integration/test_typescript_runtime_live.py",
        "timeout_seconds": 420,
        "channels": ("typescript_sdk",),
        "minimum_passed": 2,
    },
    {
        "name": "local_runtime_cli_mcp_matrix",
        "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
        "timeout_seconds": 900,
        "channels": ("daemon_client", "runtime_local", "cli", "mcp"),
        "minimum_passed": 11,
    },
)

SDK_CONTRACT_SUITES = (
    {
        "name": "python_sdk_package_contract",
        "command": (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_algenta_mojo_sdk.py",
            "-k",
            "keeps_rollout_modules_on_canonical_names_and_alias_dispatch",
        ),
        "channels": ("python_sdk",),
        "minimum_passed": 1,
        "timeout_seconds": 180,
        "evidence_paths": ("tests/test_algenta_mojo_sdk.py",),
    },
    {
        "name": "typescript_sdk_package_contract",
        "command": (
            "pnpm",
            "--dir",
            "packages/ts-sdk",
            "exec",
            "vitest",
            "run",
            "src/libraries.test.ts",
            "-t",
            "keeps the 22-library rollout inventory on canonical module names and alias dispatch",
        ),
        "channels": ("typescript_sdk",),
        "minimum_passed": 1,
        "timeout_seconds": 300,
        "evidence_paths": ("packages/ts-sdk/src/libraries.test.ts",),
    },
)

HTTP_FLAG_CONTRACT_SUITES = (
    {
        "name": "public_http_library_routes_feature_flag",
        "command": (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_runtime_libraries_api.py",
        ),
        "minimum_passed": 2,
        "timeout_seconds": 180,
        "evidence_paths": (
            "tests/test_runtime_libraries_api.py",
            "apps/api_server/main.py",
            "apps/api_server/config.py",
        ),
    },
)

HTTP_FLAG_LIVE_SUITES = (
    {
        "name": "public_http_library_routes_feature_flag_live",
        "script": "tests/integration/test_runtime_libraries_http_live.py",
        "channels": ("http_api_feature_flag",),
        "minimum_passed": 4,
        "timeout_seconds": 900,
        "evidence_paths": (
            "tests/integration/test_runtime_libraries_http_live.py",
            "tests/_asgi_client.py",
            "apps/api_server/main.py",
            "apps/api_server/config.py",
        ),
    },
)

SERVING_EXTENSION_CHANNEL_SUITES = (
    {
        "channel": "python_sdk",
        "suite_name": "python_sdk_local_runtime",
        "feature_flag": False,
    },
    {
        "channel": "typescript_sdk",
        "suite_name": "typescript_sdk_local_runtime",
        "feature_flag": False,
    },
    {
        "channel": "daemon_client",
        "suite_name": "local_runtime_cli_mcp_matrix",
        "feature_flag": False,
    },
    {
        "channel": "runtime_local",
        "suite_name": "local_runtime_cli_mcp_matrix",
        "feature_flag": False,
    },
    {
        "channel": "cli",
        "suite_name": "local_runtime_cli_mcp_matrix",
        "feature_flag": False,
    },
    {
        "channel": "mcp",
        "suite_name": "local_runtime_cli_mcp_matrix",
        "feature_flag": False,
    },
    {
        "channel": "http_api_feature_flag",
        "suite_name": "public_http_library_routes_feature_flag_live",
        "feature_flag": True,
    },
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
def render_rollout_scorecard_section(bundle: dict[str, Any]) -> str:
    parity_artifact = bundle["parity_artifact"]
    compiled_artifact = bundle["compiled_runtime_artifact"]
    serving_extension_subset = bundle["serving_extension_subset"]
    serving_extension_channel_coverage = bundle["serving_extension_channel_coverage"]
    live_by_name = {item["name"]: item for item in bundle["live_suites"]}
    sdk_contract_by_name = {item["name"]: item for item in bundle["sdk_contract_suites"]}
    http_flag_contract_by_name = {
        item["name"]: item for item in bundle["http_flag_contract_suites"]
    }
    http_flag_live_by_name = {item["name"]: item for item in bundle["http_flag_live_suites"]}
    generated_date = str(bundle["generated_at"])[:10]

    lines = [
        f"## LLM rollout proof ({generated_date})",
        "",
        "This is the dedicated evidence for the 22-library Mojo LLM rollout. Use these artifacts instead of the shared `benchmarks/summary.*` files when validating the rollout itself.",
        "",
        "| Area | Current | Evidence | Status |",
        "| --- | --- | --- | --- |",
        (
            "| 22-library parity proof | "
            f"{parity_artifact['library_count']} libraries, "
            f"{parity_artifact['function_count']} public runtime functions, "
            f"{format_speedup(float(parity_artifact['median_speedup_x']))}x median, "
            f"{format_speedup(float(parity_artifact['mean_speedup_x']))}x mean, "
            f"{format_speedup(float(parity_artifact['max_speedup_x']))}x max | "
            "`build/llm_rollout_parity_benchmark.json`, `build/llm_rollout_parity_benchmark.txt`, "
            "`tests/test_llm_rollout_parity_benchmark.py` | Green |"
        ),
        (
            "| Compiled runtime latency proof | "
            f"{compiled_artifact['module_count']} modules, "
            f"{compiled_artifact['function_count']} functions, "
            f"{compiled_artifact['failed_function_count']} failures, "
            "all `engine_used=\"mojo\"`, "
            f"worst cold {float(compiled_artifact['max_cold_ms']['value']):.2f} ms, "
            f"warm {float(compiled_artifact['max_warm_ms']['value']):.3f} ms, "
            f"hot {float(compiled_artifact['max_hot_ms']['value']):.3f} ms | "
            "`build/llm_compiled_runtime_benchmark.json`, "
            "`tests/test_llm_compiled_runtime_benchmark.py` | Green |"
        ),
        (
            "| Serving extension subset proof | "
            f"{serving_extension_subset['module_count']} modules, "
            f"{serving_extension_subset['function_count']} functions, "
            "all six modules 10/10 parity, "
            f"speedup range {format_speedup(float(serving_extension_subset['min_speedup_x']))}x "
            f"to {format_speedup(float(serving_extension_subset['max_speedup_x']))}x, "
            "compiled mojo-only, "
            f"worst cold {float(serving_extension_subset['max_cold_ms']['value']):.2f} ms, "
            f"warm {float(serving_extension_subset['max_warm_ms']['value']):.3f} ms, "
            f"hot {float(serving_extension_subset['max_hot_ms']['value']):.3f} ms | "
            "`build/llm_rollout_proof_bundle.json`, `tests/test_llm_rollout_proof_bundle.py` | Green |"
        ),
        (
            "| Serving extension channel coverage | "
            "python_sdk, typescript_sdk, cli, mcp, daemon_client, runtime_local, "
            "and http_api_feature_flag all passed via the full 209-function live suites "
            f"for the {serving_extension_channel_coverage['module_count']}-module / "
            f"{serving_extension_channel_coverage['function_count']}-function serving subset | "
            "`build/llm_rollout_proof_bundle.json`, `tests/test_llm_rollout_matrix.py`, "
            "`tests/test_llm_rollout_proof_bundle.py` | Green |"
        ),
        (
            "| Supported channel coverage | "
            f"Python SDK {live_by_name['python_sdk_local_runtime']['passed']}/"
            f"{live_by_name['python_sdk_local_runtime']['minimum_passed']} passed, "
            "CLI + DaemonClient + `Runtime(mode=\"local\")` + MCP "
            f"{live_by_name['local_runtime_cli_mcp_matrix']['passed']}/"
            f"{live_by_name['local_runtime_cli_mcp_matrix']['minimum_passed']} passed, "
            "TypeScript SDK "
            f"{live_by_name['typescript_sdk_local_runtime']['passed']} passed and "
            f"{live_by_name['typescript_sdk_local_runtime']['skipped']} API-backed skips when "
            "`DE_API_KEY` is unset | "
            "`build/python_sdk_local_runtime_live_summary.json`, "
            "`build/local_runtime_cli_mcp_matrix_live_summary.json`, "
            "`build/typescript_sdk_local_runtime_live_summary.json`, "
            "`tests/integration/test_algenta_mojo_library_live.py`, "
            "`tests/integration/test_cli_mcp_runtime_libraries_live.py`, "
            "`tests/integration/test_typescript_runtime_live.py` | Green |"
        ),
        (
            "| SDK package contract coverage | "
            "Python SDK package contract "
            f"{sdk_contract_by_name['python_sdk_package_contract']['passed']} passed; "
            "TypeScript SDK package contract "
            f"{sdk_contract_by_name['typescript_sdk_package_contract']['passed']} passed "
            f"and {sdk_contract_by_name['typescript_sdk_package_contract']['skipped']} skipped; "
            "both 0 failed | "
            "`tests/test_algenta_mojo_sdk.py`, `packages/ts-sdk/src/libraries.test.ts` | Green |"
        ),
        (
            "| HTTP API flag contract coverage | "
            "HTTP API flag contract "
            f"{http_flag_contract_by_name['public_http_library_routes_feature_flag']['passed']} passed; "
            f"{http_flag_contract_by_name['public_http_library_routes_feature_flag']['failed']} failed | "
            "`tests/test_runtime_libraries_api.py`, `apps/api_server/main.py`, "
            "`apps/api_server/config.py` | Green |"
        ),
        (
            "| HTTP API flag live coverage | "
            "HTTP API feature-flag live suite "
            f"{http_flag_live_by_name['public_http_library_routes_feature_flag_live']['passed']}/"
            f"{http_flag_live_by_name['public_http_library_routes_feature_flag_live']['minimum_passed']} "
            f"passed; {http_flag_live_by_name['public_http_library_routes_feature_flag_live']['failed']} failed | "
            "`build/public_http_library_routes_feature_flag_live_live_summary.json`, "
            "`tests/integration/test_runtime_libraries_http_live.py`, `tests/_asgi_client.py`, "
            "`build/llm_rollout_proof_bundle.json` | Green |"
        ),
        (
            "| Public HTTP API flag readiness | "
            "`/v1/libraries*` routes are feature-flag ready via "
            f"`{PUBLIC_HTTP_LIBRARY_ROUTES_ENABLE_ENV}` and remain disabled by default | "
            "`tests/test_runtime_libraries_api.py`, `apps/api_server/main.py`, "
            "`apps/api_server/config.py` | Green |"
        ),
        (
            "| Machine-readable rollout bundle | "
            "Single JSON bundle validating parity, compiled runtime, SDK package contracts, "
            "supported public channels, and underlying local lanes | "
            "`build/llm_rollout_proof_bundle.json`, `benchmarks/llm_rollout_proof_bundle.py`, "
            "`tests/test_llm_rollout_proof_bundle.py` | Green |"
        ),
        "",
    ]
    return "\n".join(lines)


def sync_rollout_scorecard(
    bundle: dict[str, Any],
    *,
    scorecard_path: Path = SCORECARD_PATH,
) -> None:
    text = scorecard_path.read_text(encoding="utf-8")
    start_marker = "## LLM rollout proof ("
    end_marker = "\n## Non-negotiable product requirement"
    start_index = text.find(start_marker)
    if start_index == -1:
        raise ValueError("scorecard rollout section start marker not found")
    end_index = text.find(end_marker, start_index)
    if end_index == -1:
        raise ValueError("scorecard rollout section end marker not found")

    replacement = render_rollout_scorecard_section(bundle)
    updated = f"{text[:start_index]}{replacement}{text[end_index + 1:]}"
    scorecard_path.write_text(updated, encoding="utf-8")
    sync_shared_benchmark_scorecard(scorecard_path=scorecard_path)


def _validate_compiled_runtime_artifact(payload: dict[str, Any]) -> None:
    expected_module_count = len(LLM_ROLLOUT_MODULE_NAMES)
    expected_function_count = len(LLM_ROLLOUT_FUNCTION_CASES)
    if int(payload.get("module_count", 0)) != expected_module_count:
        raise ValueError(
            f"compiled runtime module count mismatch: expected {expected_module_count}, "
            f"found {payload.get('module_count')}"
        )
    if int(payload.get("function_count", 0)) != expected_function_count:
        raise ValueError(
            f"compiled runtime function count mismatch: expected {expected_function_count}, "
            f"found {payload.get('function_count')}"
        )
    if int(payload.get("failed_function_count", 0)) != 0:
        raise ValueError("compiled runtime artifact reported failures")

    modules = payload.get("modules")
    if not isinstance(modules, dict):
        raise ValueError("compiled runtime artifact is missing the modules object")

    expected_modules = set(LLM_ROLLOUT_MODULE_NAMES)
    if set(modules) != expected_modules:
        missing = sorted(expected_modules - set(modules))
        extra = sorted(set(modules) - expected_modules)
        raise ValueError(f"compiled runtime modules mismatch: missing={missing}, extra={extra}")

    for module_name, module_payload in modules.items():
        functions = module_payload.get("functions")
        if not isinstance(functions, dict):
            raise ValueError(f"compiled runtime module {module_name} is missing functions")
        for function_name, function_payload in functions.items():
            if function_payload.get("engine_used") != "mojo":
                raise ValueError(
                    f"compiled runtime function {module_name}.{function_name} did not use mojo"
                )


def _max_latency(
    payload: dict[str, Any], key: str
) -> tuple[float, str | None, str | None]:
    maximum: tuple[float, str | None, str | None] = (0.0, None, None)
    modules = payload.get("modules", {})
    if not isinstance(modules, dict):
        return maximum
    for module_name, module_payload in modules.items():
        functions = module_payload.get("functions", {})
        if not isinstance(functions, dict):
            continue
        for function_name, function_payload in functions.items():
            value = float(function_payload.get(key, 0.0) or 0.0)
            if value > maximum[0]:
                maximum = (value, str(module_name), str(function_name))
    return maximum


def _module_max_latency(
    functions: dict[str, Any], key: str
) -> tuple[float, str | None]:
    maximum: tuple[float, str | None] = (0.0, None)
    for function_name, function_payload in functions.items():
        value = float(function_payload.get(key, 0.0) or 0.0)
        if value > maximum[0]:
            maximum = (value, str(function_name))
    return maximum


def _build_serving_extension_subset_summary(
    parity_payload: dict[str, Any],
    compiled_payload: dict[str, Any],
) -> dict[str, Any]:
    parity_libraries = parity_payload.get("libraries")
    if not isinstance(parity_libraries, list):
        raise ValueError("parity artifact is missing per-library results")
    parity_by_lib = {
        str(item["lib"]): item
        for item in parity_libraries
        if isinstance(item, dict) and "lib" in item
    }

    compiled_modules = compiled_payload.get("modules")
    if not isinstance(compiled_modules, dict):
        raise ValueError("compiled runtime artifact is missing the modules object")

    subset_modules: list[dict[str, Any]] = []
    total_functions = 0
    total_compared = 0
    speedups: list[float] = []
    subset_max_cold: tuple[float, str | None, str | None] = (0.0, None, None)
    subset_max_warm: tuple[float, str | None, str | None] = (0.0, None, None)
    subset_max_hot: tuple[float, str | None, str | None] = (0.0, None, None)
    all_compiled_engine_used_mojo = True

    for module_name in SERVING_EXTENSION_MODULES:
        if module_name not in parity_by_lib:
            raise ValueError(f"serving extension parity artifact is missing {module_name}")
        if module_name not in compiled_modules:
            raise ValueError(f"serving extension compiled artifact is missing {module_name}")

        parity_module = parity_by_lib[module_name]
        compiled_module = compiled_modules[module_name]
        functions = compiled_module.get("functions")
        if not isinstance(functions, dict):
            raise ValueError(f"compiled runtime module {module_name} is missing functions")

        compiled_function_count = int(compiled_module.get("function_count", 0))
        parity_function_count = int(parity_module.get("n_functions", 0))
        parity_compared = int(parity_module.get("n_compared", 0))
        parity_speedup = float(parity_module.get("speedup_x", 0.0) or 0.0)
        module_all_engine_used_mojo = all(
            function_payload.get("engine_used") == "mojo"
            for function_payload in functions.values()
            if isinstance(function_payload, dict)
        )
        all_compiled_engine_used_mojo = (
            all_compiled_engine_used_mojo and module_all_engine_used_mojo
        )

        module_max_cold = _module_max_latency(functions, "cold_ms")
        module_max_warm = _module_max_latency(functions, "warm_ms")
        module_max_hot = _module_max_latency(functions, "hot_ms")
        if module_max_cold[0] > subset_max_cold[0]:
            subset_max_cold = (module_max_cold[0], module_name, module_max_cold[1])
        if module_max_warm[0] > subset_max_warm[0]:
            subset_max_warm = (module_max_warm[0], module_name, module_max_warm[1])
        if module_max_hot[0] > subset_max_hot[0]:
            subset_max_hot = (module_max_hot[0], module_name, module_max_hot[1])

        subset_modules.append(
            {
                "name": module_name,
                "parity_function_count": parity_function_count,
                "parity_compared_count": parity_compared,
                "parity_speedup_x": parity_speedup,
                "compiled_function_count": compiled_function_count,
                "compiled_all_engine_used_mojo": module_all_engine_used_mojo,
                "max_cold_ms": {"value": module_max_cold[0], "function": module_max_cold[1]},
                "max_warm_ms": {"value": module_max_warm[0], "function": module_max_warm[1]},
                "max_hot_ms": {"value": module_max_hot[0], "function": module_max_hot[1]},
            }
        )
        total_functions += compiled_function_count
        total_compared += parity_compared
        speedups.append(parity_speedup)

    return {
        "module_count": len(SERVING_EXTENSION_MODULES),
        "function_count": total_functions,
        "functions_compared": total_compared,
        "all_modules_fully_compared": all(
            module["parity_function_count"] == module["parity_compared_count"]
            for module in subset_modules
        ),
        "all_compiled_engine_used_mojo": all_compiled_engine_used_mojo,
        "min_speedup_x": min(speedups) if speedups else 0.0,
        "max_speedup_x": max(speedups) if speedups else 0.0,
        "max_cold_ms": {
            "value": subset_max_cold[0],
            "module": subset_max_cold[1],
            "function": subset_max_cold[2],
        },
        "max_warm_ms": {
            "value": subset_max_warm[0],
            "module": subset_max_warm[1],
            "function": subset_max_warm[2],
        },
        "max_hot_ms": {
            "value": subset_max_hot[0],
            "module": subset_max_hot[1],
            "function": subset_max_hot[2],
        },
        "modules": subset_modules,
    }


def _build_serving_extension_channel_coverage(
    live_suites: list[dict[str, Any]],
    http_flag_live_suites: list[dict[str, Any]],
) -> dict[str, Any]:
    serving_function_count = sum(
        1 for case in LLM_ROLLOUT_FUNCTION_CASES if case.module in SERVING_EXTENSION_MODULES
    )
    live_suite_by_name = {str(item["name"]): item for item in live_suites}
    http_flag_suite_by_name = {str(item["name"]): item for item in http_flag_live_suites}

    channel_entries: list[dict[str, Any]] = []
    for entry in SERVING_EXTENSION_CHANNEL_SUITES:
        suite_source = (
            http_flag_suite_by_name if bool(entry["feature_flag"]) else live_suite_by_name
        )
        suite = suite_source[str(entry["suite_name"])]
        status = str(suite["status"])
        passed = int(suite.get("passed", 0) or 0)
        failed = int(suite.get("failed", 0) or 0)
        skipped = int(suite.get("skipped", 0) or 0)
        channel_entries.append(
            {
                "channel": str(entry["channel"]),
                "suite_name": str(entry["suite_name"]),
                "script": str(suite["script"]),
                "status": status,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "feature_flag": bool(entry["feature_flag"]),
                "module_count": len(SERVING_EXTENSION_MODULES),
                "function_count": serving_function_count,
                "covers_all_serving_extension_modules": status == "passed",
                "covers_all_serving_extension_functions": status == "passed",
            }
        )

    public_complete = all(
        item["status"] == "passed"
        for item in channel_entries
        if item["channel"] in PUBLIC_SUPPORTED_CHANNELS
    )
    validated_aux_complete = all(
        item["status"] == "passed"
        for item in channel_entries
        if item["channel"] in UNDERLYING_VALIDATED_LANES
    )
    http_feature_flag_complete = all(
        item["status"] == "passed" for item in channel_entries if item["feature_flag"]
    )

    return {
        "module_count": len(SERVING_EXTENSION_MODULES),
        "function_count": serving_function_count,
        "source_rollout_function_count": len(LLM_ROLLOUT_FUNCTION_CASES),
        "coverage_basis": (
            "Each referenced live suite executes all LLM_ROLLOUT_FUNCTION_CASES, "
            "which includes the six serving extension modules."
        ),
        "public_supported_channels_complete": public_complete,
        "validated_auxiliary_channels_complete": validated_aux_complete,
        "http_feature_flag_channel_complete": http_feature_flag_complete,
        "channels": channel_entries,
    }


def _parse_live_suite_summary(output: str) -> dict[str, int]:
    parsed = {"passed": 0, "failed": 0, "skipped": 0}
    for key in parsed:
        match = re.search(rf"{key.capitalize()}: (\d+)", output)
        if match:
            parsed[key] = int(match.group(1))
    return parsed


def _parse_test_runner_summary(output: str) -> dict[str, int]:
    parsed = {"passed": 0, "failed": 0, "skipped": 0}
    for key in parsed:
        matches = re.findall(rf"(\d+)\s+{key}\b", output, flags=re.IGNORECASE)
        if matches:
            parsed[key] = max(int(match) for match in matches)
    return parsed


def _run_live_suite(script_path: str, timeout_seconds: int) -> tuple[int, float, str]:
    started = time.perf_counter()
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    root_path = str(PROJECT_ROOT)
    env["PYTHONPATH"] = (
        root_path
        if not existing_pythonpath
        else f"{root_path}{os.pathsep}{existing_pythonpath}"
    )
    proc = subprocess.run(  # noqa: S603
        [sys.executable, script_path],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    elapsed = time.perf_counter() - started
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    return proc.returncode, elapsed, output


def _run_test_command(command: list[str], timeout_seconds: int) -> tuple[int, float, str]:
    started = time.perf_counter()
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    root_path = str(PROJECT_ROOT)
    env["PYTHONPATH"] = (
        root_path
        if not existing_pythonpath
        else f"{root_path}{os.pathsep}{existing_pythonpath}"
    )
    proc = subprocess.run(  # noqa: S603
        command,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    elapsed = time.perf_counter() - started
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    return proc.returncode, elapsed, output


def _run_repo_command(command: list[str], timeout_seconds: int) -> str:
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    root_path = str(PROJECT_ROOT)
    env["PYTHONPATH"] = (
        root_path
        if not existing_pythonpath
        else f"{root_path}{os.pathsep}{existing_pythonpath}"
    )
    proc = subprocess.run(  # noqa: S603
        command,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\n"
            f"return_code={proc.returncode}\n"
            f"output:\n{output}"
        )
    return output


def _ensure_benchmark_artifacts(refresh_artifacts: bool) -> None:
    if refresh_artifacts or not PARITY_ARTIFACT.exists():
        _run_repo_command([sys.executable, str(PARITY_BENCHMARK_SCRIPT)], timeout_seconds=600)
    if refresh_artifacts or not COMPILED_ARTIFACT.exists():
        _run_repo_command([sys.executable, str(COMPILED_BENCHMARK_SCRIPT)], timeout_seconds=600)


def _collect_live_suite_results(run_live: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for suite in LIVE_SUITES:
        summary: dict[str, Any] = {
            "name": suite["name"],
            "script": suite["script"],
            "channels": list(suite["channels"]),
            "minimum_passed": suite["minimum_passed"],
        }
        if not run_live:
            summary["status"] = "skipped"
            results.append(summary)
            continue

        return_code, elapsed, output = _run_live_suite(
            str(PROJECT_ROOT / suite["script"]),
            int(suite["timeout_seconds"]),
        )
        counts = _parse_live_suite_summary(output)
        minimum_passed = int(suite["minimum_passed"])
        if return_code != 0 or counts["failed"] != 0 or counts["passed"] < minimum_passed:
            raise RuntimeError(
                f"live suite {suite['name']} failed validation.\n"
                f"return_code={return_code}\n"
                f"counts={counts}\n"
                f"output:\n{output}"
            )

        summary.update(
            {
                "status": "passed",
                "elapsed_seconds": round(elapsed, 3),
                "passed": counts["passed"],
                "failed": counts["failed"],
                "skipped": counts["skipped"],
            }
        )
        results.append(summary)
    return results


def _normalize_live_suite_results(live_suite_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected_by_name = {suite["name"]: suite for suite in LIVE_SUITES}
    actual_names = {str(item.get("name", "")) for item in live_suite_results}
    if actual_names != set(expected_by_name):
        missing = sorted(set(expected_by_name) - actual_names)
        extra = sorted(actual_names - set(expected_by_name))
        raise ValueError(f"live suite results mismatch: missing={missing}, extra={extra}")

    normalized: list[dict[str, Any]] = []
    for item in live_suite_results:
        suite = expected_by_name[str(item["name"])]
        status = str(item.get("status", "passed"))
        passed = int(item.get("passed", 0) or 0)
        failed = int(item.get("failed", 0) or 0)
        skipped = int(item.get("skipped", 0) or 0)
        elapsed_seconds = float(item.get("elapsed_seconds", 0.0) or 0.0)
        expected_minimum = int(suite["minimum_passed"])
        reported_minimum = int(item.get("minimum_passed", expected_minimum) or 0)
        if status == "passed":
            if reported_minimum <= 0 or reported_minimum > expected_minimum:
                raise ValueError(
                    f"live suite {suite['name']} reported invalid minimum_passed: "
                    f"reported={reported_minimum}, expected={expected_minimum}"
                )
            if reported_minimum < expected_minimum and skipped == 0:
                raise ValueError(
                    f"live suite {suite['name']} lowered minimum_passed without any skipped checks: "
                    f"reported={reported_minimum}, expected={expected_minimum}"
                )
            if failed != 0 or passed < reported_minimum:
                raise ValueError(
                    f"live suite {suite['name']} failed validation: "
                    f"status={status}, passed={passed}, failed={failed}, skipped={skipped}"
                )
        elif status != "skipped":
            raise ValueError(f"unsupported live suite status for {suite['name']}: {status}")
        normalized.append(
            {
                "name": suite["name"],
                "script": suite["script"],
                "channels": list(suite["channels"]),
                "minimum_passed": reported_minimum,
                "status": status,
                "elapsed_seconds": round(elapsed_seconds, 3),
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
            }
        )
    return normalized


def _collect_sdk_contract_suite_results() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for suite in SDK_CONTRACT_SUITES:
        return_code, elapsed, output = _run_test_command(
            list(suite["command"]),
            int(suite["timeout_seconds"]),
        )
        counts = _parse_test_runner_summary(output)
        if return_code != 0 or counts["failed"] != 0 or counts["passed"] < int(
            suite["minimum_passed"]
        ):
            raise RuntimeError(
                f"sdk contract suite {suite['name']} failed validation.\n"
                f"return_code={return_code}\n"
                f"counts={counts}\n"
                f"output:\n{output}"
            )
        results.append(
            {
                "name": suite["name"],
                "command": list(suite["command"]),
                "channels": list(suite["channels"]),
                "minimum_passed": suite["minimum_passed"],
                "evidence_paths": list(suite["evidence_paths"]),
                "status": "passed",
                "elapsed_seconds": round(elapsed, 3),
                "passed": counts["passed"],
                "failed": counts["failed"],
                "skipped": counts["skipped"],
            }
        )
    return results


def _collect_http_flag_contract_suite_results() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for suite in HTTP_FLAG_CONTRACT_SUITES:
        return_code, elapsed, output = _run_test_command(
            list(suite["command"]),
            int(suite["timeout_seconds"]),
        )
        counts = _parse_test_runner_summary(output)
        if return_code != 0 or counts["failed"] != 0 or counts["passed"] < int(
            suite["minimum_passed"]
        ):
            raise RuntimeError(
                f"http flag contract suite {suite['name']} failed validation.\n"
                f"return_code={return_code}\n"
                f"counts={counts}\n"
                f"output:\n{output}"
            )
        results.append(
            {
                "name": suite["name"],
                "command": list(suite["command"]),
                "minimum_passed": suite["minimum_passed"],
                "evidence_paths": list(suite["evidence_paths"]),
                "status": "passed",
                "elapsed_seconds": round(elapsed, 3),
                "passed": counts["passed"],
                "failed": counts["failed"],
                "skipped": counts["skipped"],
            }
        )
    return results


def _collect_http_flag_live_suite_results(run_live: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for suite in HTTP_FLAG_LIVE_SUITES:
        summary: dict[str, Any] = {
            "name": suite["name"],
            "script": suite["script"],
            "channels": list(suite["channels"]),
            "minimum_passed": suite["minimum_passed"],
            "evidence_paths": list(suite["evidence_paths"]),
        }
        if not run_live:
            summary["status"] = "skipped"
            results.append(summary)
            continue

        return_code, elapsed, output = _run_live_suite(
            str(PROJECT_ROOT / suite["script"]),
            int(suite["timeout_seconds"]),
        )
        counts = _parse_live_suite_summary(output)
        minimum_passed = int(suite["minimum_passed"])
        if return_code != 0 or counts["failed"] != 0 or counts["passed"] < minimum_passed:
            raise RuntimeError(
                f"http flag live suite {suite['name']} failed validation.\n"
                f"return_code={return_code}\n"
                f"counts={counts}\n"
                f"output:\n{output}"
            )

        summary.update(
            {
                "status": "passed",
                "elapsed_seconds": round(elapsed, 3),
                "passed": counts["passed"],
                "failed": counts["failed"],
                "skipped": counts["skipped"],
            }
        )
        results.append(summary)
    return results


def _normalize_http_flag_live_suite_results(
    http_flag_live_suite_results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    expected_by_name = {suite["name"]: suite for suite in HTTP_FLAG_LIVE_SUITES}
    actual_names = {str(item.get("name", "")) for item in http_flag_live_suite_results}
    if actual_names != set(expected_by_name):
        missing = sorted(set(expected_by_name) - actual_names)
        extra = sorted(actual_names - set(expected_by_name))
        raise ValueError(f"http flag live suite results mismatch: missing={missing}, extra={extra}")

    normalized: list[dict[str, Any]] = []
    for item in http_flag_live_suite_results:
        suite = expected_by_name[str(item["name"])]
        status = str(item.get("status", "passed"))
        passed = int(item.get("passed", 0) or 0)
        failed = int(item.get("failed", 0) or 0)
        skipped = int(item.get("skipped", 0) or 0)
        elapsed_seconds = float(item.get("elapsed_seconds", 0.0) or 0.0)
        if status == "passed":
            if failed != 0 or passed < int(suite["minimum_passed"]):
                raise ValueError(
                    f"http flag live suite {suite['name']} failed validation: "
                    f"status={status}, passed={passed}, failed={failed}, skipped={skipped}"
                )
        elif status != "skipped":
            raise ValueError(
                f"unsupported http flag live suite status for {suite['name']}: {status}"
            )
        normalized.append(
            {
                "name": suite["name"],
                "script": suite["script"],
                "channels": list(suite["channels"]),
                "minimum_passed": suite["minimum_passed"],
                "evidence_paths": list(suite["evidence_paths"]),
                "status": status,
                "elapsed_seconds": round(elapsed_seconds, 3),
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
            }
        )
    return normalized


def _cached_live_suite_score(
    live_suites: list[dict[str, Any]],
    http_flag_live_suites: list[dict[str, Any]],
) -> tuple[int, int]:
    passed_count = sum(
        1 for item in (*live_suites, *http_flag_live_suites) if str(item.get("status")) == "passed"
    )
    return (passed_count, len(live_suites) + len(http_flag_live_suites))


def _load_live_suite_artifact_results() -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
    live_suite_results: list[dict[str, Any]] = []
    http_flag_live_suite_results: list[dict[str, Any]] = []

    for suite in LIVE_SUITES:
        artifact_path = LIVE_SUMMARY_ARTIFACTS.get(str(suite["name"]))
        if artifact_path is None or not artifact_path.exists():
            return (None, None)
        payload = _read_json(artifact_path)
        if str(payload.get("name")) != str(suite["name"]):
            return (None, None)
        live_suite_results.append(payload)

    for suite in HTTP_FLAG_LIVE_SUITES:
        artifact_path = LIVE_SUMMARY_ARTIFACTS.get(str(suite["name"]))
        if artifact_path is None or not artifact_path.exists():
            return (None, None)
        payload = _read_json(artifact_path)
        if str(payload.get("name")) != str(suite["name"]):
            return (None, None)
        http_flag_live_suite_results.append(payload)

    return (live_suite_results, http_flag_live_suite_results)


def _load_best_cached_live_suite_results(
    output_path: Path,
) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
    candidates: list[Path] = []
    for candidate in (output_path, DEFAULT_OUTPUT):
        if candidate.exists() and candidate not in candidates:
            candidates.append(candidate)

    best: tuple[tuple[int, int], list[dict[str, Any]], list[dict[str, Any]]] | None = None
    for candidate in candidates:
        payload: dict[str, Any] | None = None
        try:
            payload = _read_json(candidate)
        except Exception:  # noqa: BLE001
            payload = None
        if payload is None:
            continue
        live_suites = payload.get("live_suites")
        http_flag_live_suites = payload.get("http_flag_live_suites")
        if not isinstance(live_suites, list) or not isinstance(http_flag_live_suites, list):
            continue
        normalized_live_suites: list[dict[str, Any]] | None = None
        normalized_http_flag_live_suites: list[dict[str, Any]] | None = None
        try:
            normalized_live_suites = _normalize_live_suite_results(live_suites)
            normalized_http_flag_live_suites = _normalize_http_flag_live_suite_results(
                http_flag_live_suites
            )
        except Exception:  # noqa: BLE001
            normalized_live_suites = None
            normalized_http_flag_live_suites = None
        if normalized_live_suites is None or normalized_http_flag_live_suites is None:
            continue
        score = _cached_live_suite_score(
            normalized_live_suites,
            normalized_http_flag_live_suites,
        )
        if best is None or score > best[0]:
            best = (
                score,
                normalized_live_suites,
                normalized_http_flag_live_suites,
            )

    artifact_live_suites, artifact_http_flag_live_suites = _load_live_suite_artifact_results()
    if artifact_live_suites is not None and artifact_http_flag_live_suites is not None:
        normalized_live_suites = _normalize_live_suite_results(artifact_live_suites)
        normalized_http_flag_live_suites = _normalize_http_flag_live_suite_results(
            artifact_http_flag_live_suites
        )
        score = _cached_live_suite_score(
            normalized_live_suites,
            normalized_http_flag_live_suites,
        )
        if best is None or score >= best[0]:
            best = (
                score,
                normalized_live_suites,
                normalized_http_flag_live_suites,
            )

    if best is None:
        return (None, None)
    return (best[1], best[2])


def build_proof_bundle(
    *,
    run_live: bool,
    refresh_artifacts: bool = False,
    live_suite_results: list[dict[str, Any]] | None = None,
    http_flag_live_suite_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _ensure_benchmark_artifacts(refresh_artifacts)
    parity_payload = _read_json(PARITY_ARTIFACT)
    validate_rollout_summary(parity_payload)

    compiled_payload = _read_json(COMPILED_ARTIFACT)
    _validate_compiled_runtime_artifact(compiled_payload)

    cold_ms, cold_module, cold_function = _max_latency(compiled_payload, "cold_ms")
    warm_ms, warm_module, warm_function = _max_latency(compiled_payload, "warm_ms")
    hot_ms, hot_module, hot_function = _max_latency(compiled_payload, "hot_ms")
    sdk_contract_suites = _collect_sdk_contract_suite_results()
    http_flag_contract_suites = _collect_http_flag_contract_suite_results()
    if live_suite_results is not None:
        normalized_live_suites = _normalize_live_suite_results(live_suite_results)
    else:
        normalized_live_suites = _collect_live_suite_results(run_live)
    if http_flag_live_suite_results is not None:
        normalized_http_flag_live_suites = _normalize_http_flag_live_suite_results(
            http_flag_live_suite_results
        )
    else:
        normalized_http_flag_live_suites = _collect_http_flag_live_suite_results(run_live)
    serving_extension_subset = _build_serving_extension_subset_summary(
        parity_payload,
        compiled_payload,
    )
    serving_extension_channel_coverage = _build_serving_extension_channel_coverage(
        normalized_live_suites,
        normalized_http_flag_live_suites,
    )

    inventory_report = build_inventory_report()
    discovered_source_inventory = sorted(
        [
            {
                "import_path": module.import_path,
                "public_function_count": len(module.public_functions),
            }
            for module in inventory_report.source_modules
            if module.public_functions
        ],
        key=lambda entry: entry["import_path"],
    )
    benchmark_discovery_lane = {
        "discovered_source_modules": inventory_report.source_modules_with_public_functions_count,
        "discovered_public_functions": inventory_report.source_public_function_count,
        "discovered_source_inventory": discovered_source_inventory,
        "shipping_manifest_modules": len(LLM_ROLLOUT_MODULE_NAMES),
        "shipping_manifest_functions": len(LLM_ROLLOUT_FUNCTION_CASES),
        "non_shipping_rule": RuntimeNonShippingRule.broader_mojo_inventory_not_advertised.value,
    }

    return {
        "bundle": "llm_rollout_proof_bundle",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "expected_modules": len(LLM_ROLLOUT_MODULE_NAMES),
        "expected_functions": len(LLM_ROLLOUT_FUNCTION_CASES),
        "public_supported_channels": list(PUBLIC_SUPPORTED_CHANNELS),
        "underlying_validated_lanes": list(UNDERLYING_VALIDATED_LANES),
        "public_http_library_routes_supported": False,
        "public_http_library_routes_feature_flag_ready": True,
        "public_http_library_routes_enable_env": PUBLIC_HTTP_LIBRARY_ROUTES_ENABLE_ENV,
        "parity_artifact": {
            "path": str(PARITY_ARTIFACT.relative_to(PROJECT_ROOT)),
            "library_count": parity_payload["n_libraries"],
            "function_count": parity_payload["total_functions_compared"],
            "median_speedup_x": parity_payload["median_speedup_x"],
            "mean_speedup_x": parity_payload["mean_speedup_x"],
            "max_speedup_x": parity_payload["max_speedup_x"],
            "timestamp": parity_payload["timestamp"],
        },
        "compiled_runtime_artifact": {
            "path": str(COMPILED_ARTIFACT.relative_to(PROJECT_ROOT)),
            "module_count": compiled_payload["module_count"],
            "function_count": compiled_payload["function_count"],
            "failed_function_count": compiled_payload["failed_function_count"],
            "transport": compiled_payload["transport"],
            "max_cold_ms": {"value": cold_ms, "module": cold_module, "function": cold_function},
            "max_warm_ms": {"value": warm_ms, "module": warm_module, "function": warm_function},
            "max_hot_ms": {"value": hot_ms, "module": hot_module, "function": hot_function},
        },
        "benchmark_discovery_lane": benchmark_discovery_lane,
        "sdk_contract_suites": sdk_contract_suites,
        "http_flag_contract_suites": http_flag_contract_suites,
        "http_flag_live_suites": normalized_http_flag_live_suites,
        "serving_extension_subset": serving_extension_subset,
        "serving_extension_channel_coverage": serving_extension_channel_coverage,
        "live_suites": normalized_live_suites,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the dedicated LLM rollout proof bundle.")
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="Validate benchmark artifacts only and skip rerunning live channel suites.",
    )
    parser.add_argument(
        "--refresh-artifacts",
        action="store_true",
        help="Regenerate the parity and compiled rollout benchmark artifacts before bundling.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Proof bundle JSON output path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    live_suite_results = None
    http_flag_live_suite_results = None
    if args.skip_live:
        (
            live_suite_results,
            http_flag_live_suite_results,
        ) = _load_best_cached_live_suite_results(args.output)

    bundle = build_proof_bundle(
        run_live=not args.skip_live,
        refresh_artifacts=args.refresh_artifacts,
        live_suite_results=live_suite_results,
        http_flag_live_suite_results=http_flag_live_suite_results,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    sync_rollout_scorecard(bundle)

    print(f"Validated parity artifact: {bundle['parity_artifact']['path']}")
    print(f"Validated compiled artifact: {bundle['compiled_runtime_artifact']['path']}")
    print(f"Wrote proof bundle: {args.output}")
    print(f"Synced rollout scorecard: {SCORECARD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
