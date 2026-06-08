from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)

logger = logging.getLogger(__name__)

_RUNTIME_FALLBACK_CACHE: tuple[tuple[str | None, str, str], Path] | None = None


def _runtime_dir_writable(path: Path) -> bool:
    probe_dir = path.resolve()
    probe_file = probe_dir / ".repository-intelligence-write-test"
    try:
        probe_dir.mkdir(parents=True, exist_ok=True)
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
    except OSError:
        return False
    return True


def _runtime_fallback_candidates() -> list[Path]:
    cwd = Path.cwd().resolve()
    temp_hash = hashlib.sha256(str(cwd).encode("utf-8")).hexdigest()[:12]
    return [
        cwd / "build" / "algenta-runtime",
        Path(tempfile.gettempdir()) / "algenta-runtime" / temp_hash,
    ]


def _runtime_dir() -> Path:
    global _RUNTIME_FALLBACK_CACHE
    configured_runtime = str(os.environ.get("ALGENTA_RUNTIME_DIR") or "").strip() or None
    cache_key = (
        configured_runtime,
        str(Path.home().resolve()),
        str(Path.cwd().resolve()),
    )
    if _RUNTIME_FALLBACK_CACHE is not None and _RUNTIME_FALLBACK_CACHE[0] == cache_key:
        return _RUNTIME_FALLBACK_CACHE[1]

    if configured_runtime is not None:
        configured_path = Path(configured_runtime).expanduser().resolve()
        if not _runtime_dir_writable(configured_path):
            raise RepositoryIntelligenceError(
                code="repository_runtime_unwritable",
                message=(
                    f"Configured repository runtime directory '{configured_path}' is not writable."
                ),
                status_code=500,
                details={"runtime_dir": str(configured_path)},
            )
        _RUNTIME_FALLBACK_CACHE = (cache_key, configured_path)
        return configured_path

    default_runtime = (Path.home() / ".algenta" / "runtime").resolve()
    if _runtime_dir_writable(default_runtime):
        _RUNTIME_FALLBACK_CACHE = (cache_key, default_runtime)
        return default_runtime

    for fallback_path in _runtime_fallback_candidates():
        fallback_path = fallback_path.resolve()
        if not _runtime_dir_writable(fallback_path):
            continue
        logger.warning(
            "Repository Intelligence runtime directory '%s' is not writable; "
            "falling back to '%s'.",
            default_runtime,
            fallback_path,
        )
        _RUNTIME_FALLBACK_CACHE = (cache_key, fallback_path)
        return fallback_path

    raise RepositoryIntelligenceError(
        code="repository_runtime_unwritable",
        message=(
            "Repository Intelligence could not find a writable runtime directory. "
            "Set ALGENTA_RUNTIME_DIR to a writable path."
        ),
        status_code=500,
        details={"default_runtime_dir": str(default_runtime)},
    )


def _repo_root_dir(org_id: str, repository_id: str) -> Path:
    return _runtime_dir() / "repository_intelligence" / org_id / repository_id


def _snapshots_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "snapshots"


def _triage_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "triage"


def _decision_plans_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "decision_plans"


def _patches_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "patches"


def _patch_impact_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "patch_impacts"


def _simulations_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "simulations"


def _apply_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "apply"


def _worktrees_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "worktrees"


def _snapshot_lookup_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "snapshot_lookup"


def _triage_lookup_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "triage_lookup"


def _decision_plan_lookup_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "decision_plan_lookup"


def _simulation_lookup_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "simulation_lookup"


def _graph_query_lookup_dir(org_id: str, repository_id: str) -> Path:
    return _repo_root_dir(org_id, repository_id) / "graph_query_lookup"


def _shared_repository_intelligence_dir() -> Path:
    return _runtime_dir() / "repository_intelligence_shared"


def _file_analysis_cache_dir() -> Path:
    return _shared_repository_intelligence_dir() / "file_analysis_cache"


def _dependency_analysis_cache_dir() -> Path:
    return _shared_repository_intelligence_dir() / "dependency_analysis_cache"


def _repository_file_selection_cache_dir() -> Path:
    return _shared_repository_intelligence_dir() / "file_selection_cache"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    serialized_payload = json.dumps(payload, indent=2, sort_keys=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    for _attempt in range(2):
        _ensure_parent(path)
        temp_path.write_text(serialized_payload, encoding="utf-8")
        try:
            temp_path.replace(path)
            return
        except FileNotFoundError:
            continue
    raise RepositoryIntelligenceError(
        code="repository_cache_write_failed",
        message=f"Repository Intelligence could not persist cache file '{path}'.",
        status_code=500,
        details={"path": str(path)},
    )


def _lookup_response_payload(lookup_payload: dict[str, Any]) -> dict[str, Any] | None:
    response_payload = lookup_payload.get("response")
    if isinstance(response_payload, dict):
        return response_payload
    return None
