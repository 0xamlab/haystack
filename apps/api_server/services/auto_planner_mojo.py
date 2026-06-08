from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any


def should_use_resident_planner_mojo(
    *,
    engine_type: str,
    payload: dict[str, Any],
    resident_engines: frozenset[str],
    max_payload_bytes: int,
) -> bool:
    if engine_type not in resident_engines:
        return False
    payload_size = len(json.dumps(payload, sort_keys=True).encode("utf-8"))
    return payload_size <= max_payload_bytes


def find_mojo_binary(repo_root: Path) -> Path | None:
    candidates = [
        repo_root / "mojo_build" / "simulate",
        Path("mojo_build") / "simulate",
        Path.home() / ".algenta" / "mojo_build" / "simulate",
    ]
    for candidate in candidates:
        resolved = candidate.resolve() if candidate.exists() else None
        if (
            resolved
            and resolved.exists()
            and resolved.is_file()
            and os.access(str(resolved), os.X_OK)
        ):
            return resolved
    return None


def call_planner_mojo(
    *,
    mojo_binary: Path | None,
    payload: dict[str, Any],
    timeout: int,
    transport: str,
    shared_engines: frozenset[str],
    should_use_resident_fn: Callable[[str, dict[str, Any]], bool],
    invoke_engine_sync_fn: Callable[..., dict[str, Any] | None],
    invoke_planner_mojo_fn: Callable[..., dict[str, Any] | None],
    subprocess_run_fn: Callable[..., subprocess.CompletedProcess[bytes]],
    logger: Any,
) -> dict[str, Any] | None:
    if not mojo_binary:
        return None

    engine_type = str(payload.get("engine_type", "unknown"))
    should_try_pool = transport in {"auto", "pool"} and engine_type in shared_engines
    if should_try_pool:
        try:
            result = invoke_engine_sync_fn(payload, timeout=float(timeout))
            if result is not None and "error" not in result:
                return result
            if transport == "pool":
                return None
            logger.debug(
                "auto_planner_mojo_transport_fallback",
                engine=engine_type,
                transport="pool_to_legacy",
            )
        except Exception as exc:
            if transport == "pool":
                logger.debug(
                    "auto_planner_mojo_error",
                    error=str(exc),
                    engine=engine_type,
                    transport="pool",
                )
                return None
            logger.debug(
                "auto_planner_mojo_transport_fallback",
                error=str(exc),
                engine=engine_type,
                transport="pool_to_legacy",
            )

    should_try_resident = transport == "resident" or (
        transport == "auto" and should_use_resident_fn(engine_type, payload)
    )
    if should_try_resident:
        try:
            result = invoke_planner_mojo_fn(
                payload,
                binary_path=mojo_binary,
                timeout=float(timeout),
            )
            if result is not None and "error" not in result:
                return result
            if transport == "resident":
                return None
            logger.debug(
                "auto_planner_mojo_transport_fallback",
                engine=engine_type,
                transport="resident_to_subprocess",
            )
        except Exception as exc:
            if transport == "resident":
                logger.debug(
                    "auto_planner_mojo_error",
                    error=str(exc),
                    engine=engine_type,
                    transport="resident",
                )
                return None
            logger.debug(
                "auto_planner_mojo_transport_fallback",
                error=str(exc),
                engine=engine_type,
                transport="resident_to_subprocess",
            )

    try:
        completed = subprocess_run_fn(
            [str(mojo_binary)],
            input=json.dumps(payload).encode(),
            capture_output=True,
            timeout=timeout,
        )
        if completed.returncode == 0:
            output = json.loads(completed.stdout)
            if isinstance(output, dict) and "error" not in output:
                return output
    except Exception as exc:
        logger.debug(
            "auto_planner_mojo_error",
            error=str(exc),
            engine=engine_type,
            transport="subprocess",
        )
    return None
