from __future__ import annotations

import hashlib
import json
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_CLINE_DOCS_URL = "https://docs.cline.bot/llms.txt"
CLINE_PROOFS_DIR = Path("build") / "proofs" / "cline"
CLINE_RUNS_DIR = CLINE_PROOFS_DIR / "runs"
CLINE_DOCS_SNAPSHOT_PATH = CLINE_PROOFS_DIR / "cline_docs_snapshot.txt"
CLINE_DOCS_SNAPSHOT_HASH_PATH = CLINE_PROOFS_DIR / "cline_docs_snapshot.sha256"
CHANNEL_PARITY_SOURCE_PATH = Path("build") / "repository_intelligence_channel_parity_summary.json"
REDACTED_SECRET_VALUE = "[REDACTED]"
SECRET_FIELD_PATTERN = re.compile(
    r"^(authorization|api[_-]?key|token|cookie|secret|password|headers?)$",
    re.IGNORECASE,
)
APPROVAL_AUTHORIZATION_KEYS = frozenset(
    {"caller", "workflow_identity", "repository_allowed", "branch_allowed"}
)


@dataclass(frozen=True)
class ClineProofContext:
    root: Path
    git_commit: str
    runtime_version: str
    parity_ledger_hash: str
    source_tree_dirty: bool
    cline_docs_snapshot_hash: str
    vendored_cline_commit: str
    algenta_commit: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _stable_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_stable_value(entry) for entry in value]
    if isinstance(value, dict):
        return {key: _stable_value(value[key]) for key in sorted(value)}
    return value


def stable_json_dumps(value: Any) -> str:
    return json.dumps(_stable_value(value), indent=2) + "\n"


def sha256_hex(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def git_output(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            check=True,
            text=True,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip()


def load_docs_snapshot(root: Path | None = None) -> tuple[str, str]:
    resolved_root = repo_root() if root is None else Path(root).resolve()
    snapshot_path = resolved_root / CLINE_DOCS_SNAPSHOT_PATH
    snapshot_hash_path = resolved_root / CLINE_DOCS_SNAPSHOT_HASH_PATH
    snapshot_text = snapshot_path.read_text(encoding="utf-8")
    declared_hash = snapshot_hash_path.read_text(encoding="utf-8").strip()
    computed_hash = sha256_hex(snapshot_text)
    if declared_hash != computed_hash:
        raise ValueError(
            "cline docs snapshot hash mismatch: "
            f"declared={declared_hash} computed={computed_hash}"
        )
    return snapshot_text, computed_hash


def fetch_live_docs_text(
    *,
    url: str = DEFAULT_CLINE_DOCS_URL,
    timeout_seconds: int = 15,
) -> tuple[str, str]:
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
        payload = response.read().decode("utf-8")
    return payload, sha256_hex(payload)


def build_proof_context(root: Path | None = None) -> ClineProofContext:
    resolved_root = repo_root() if root is None else Path(root).resolve()
    _, docs_snapshot_hash = load_docs_snapshot(resolved_root)
    git_commit = git_output(resolved_root, "rev-parse", "HEAD")
    # The vendored Cline now lives in thyn-ai/codna (the sidecar's home), not in this repo,
    # so this pathspec resolves to "" here and falls back to the algenta commit; the authoritative
    # vendored-Cline provenance is recorded by the sidecar's own proofs at runtime.
    vendored_cline_commit = (
        git_output(resolved_root, "rev-parse", "HEAD:agent-core/vendor/cline")
        or git_commit
    )
    algenta_commit = git_commit
    source_tree_dirty = git_output(resolved_root, "status", "--porcelain") != ""
    parity_input = {
        "cline_docs_snapshot_hash": docs_snapshot_hash,
        "vendored_cline_commit": vendored_cline_commit,
        "algenta_commit": algenta_commit,
    }
    parity_ledger_hash = sha256_hex(stable_json_dumps(parity_input))
    return ClineProofContext(
        root=resolved_root,
        git_commit=git_commit,
        runtime_version=vendored_cline_commit,
        parity_ledger_hash=parity_ledger_hash,
        source_tree_dirty=source_tree_dirty,
        cline_docs_snapshot_hash=docs_snapshot_hash,
        vendored_cline_commit=vendored_cline_commit,
        algenta_commit=algenta_commit,
    )


def create_artifact_provenance(
    context: ClineProofContext,
    *,
    run_id: str,
    schema_version: str,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "generated_at": utc_now_iso(),
        "run_id": run_id,
        "git_commit": context.git_commit,
        "runtime_version": context.runtime_version,
        "parity_ledger_hash": context.parity_ledger_hash,
        "source_tree_dirty": context.source_tree_dirty,
        "cline_docs_snapshot_hash": context.cline_docs_snapshot_hash,
        "vendored_cline_commit": context.vendored_cline_commit,
        "algenta_commit": context.algenta_commit,
    }


def write_json(path: Path, payload: Any) -> Path:
    resolved_path = path.resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(stable_json_dumps(payload), encoding="utf-8")
    return resolved_path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path} contains a non-object NDJSON row")
        rows.append(payload)
    return rows


def validate_artifact_provenance(
    *,
    payload: dict[str, Any],
    context: ClineProofContext,
    artifact_path: Path,
    allow_dirty_tree: bool = False,
    accepted_git_commits: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    accepted_commits = {context.git_commit}
    if accepted_git_commits:
        accepted_commits.update(accepted_git_commits)
    git_commit = payload.get("git_commit")
    if git_commit not in accepted_commits:
        errors.append(
            f"{artifact_path} git_commit mismatch: expected one of {sorted(accepted_commits)}, got {git_commit!r}"
        )
    if payload.get("runtime_version") != context.runtime_version:
        errors.append(
            f"{artifact_path} runtime_version mismatch: expected {context.runtime_version!r}, got {payload.get('runtime_version')!r}"
        )
    if payload.get("parity_ledger_hash") != context.parity_ledger_hash:
        errors.append(
            f"{artifact_path} parity_ledger_hash mismatch: expected {context.parity_ledger_hash!r}, got {payload.get('parity_ledger_hash')!r}"
        )
    if payload.get("cline_docs_snapshot_hash") != context.cline_docs_snapshot_hash:
        errors.append(
            f"{artifact_path} cline_docs_snapshot_hash mismatch: expected {context.cline_docs_snapshot_hash!r}, got {payload.get('cline_docs_snapshot_hash')!r}"
        )
    if payload.get("vendored_cline_commit") != context.vendored_cline_commit:
        errors.append(
            f"{artifact_path} vendored_cline_commit mismatch: expected {context.vendored_cline_commit!r}, got {payload.get('vendored_cline_commit')!r}"
        )
    if payload.get("algenta_commit") != context.algenta_commit:
        errors.append(
            f"{artifact_path} algenta_commit mismatch: expected {context.algenta_commit!r}, got {payload.get('algenta_commit')!r}"
        )
    if not allow_dirty_tree and bool(payload.get("source_tree_dirty")):
        errors.append(f"{artifact_path} source_tree_dirty=true is not allowed")
    errors.extend(_find_unredacted_secret_errors(payload, artifact_path=artifact_path))
    return errors


def _find_unredacted_secret_errors(
    value: Any,
    *,
    artifact_path: Path,
    current_path: str = "",
) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            next_path = f"{current_path}.{key}" if current_path else key
            if SECRET_FIELD_PATTERN.match(key):
                if _is_allowed_authorization_metadata(
                    artifact_path=artifact_path,
                    field_path=next_path,
                    value=child,
                ):
                    errors.extend(
                        _find_unredacted_secret_errors(
                            child,
                            artifact_path=artifact_path,
                            current_path=next_path,
                        )
                    )
                    continue
                if child != REDACTED_SECRET_VALUE:
                    errors.append(
                        f"{artifact_path} contains unredacted secret field at {next_path}"
                    )
                continue
            errors.extend(
                _find_unredacted_secret_errors(
                    child,
                    artifact_path=artifact_path,
                    current_path=next_path,
                )
            )
        return errors
    if isinstance(value, list):
        for index, child in enumerate(value):
            next_path = f"{current_path}[{index}]"
            errors.extend(
                _find_unredacted_secret_errors(
                    child,
                    artifact_path=artifact_path,
                    current_path=next_path,
                )
            )
    return errors


def _is_allowed_authorization_metadata(
    *,
    artifact_path: Path,
    field_path: str,
    value: Any,
) -> bool:
    if artifact_path.name != "approvals.json" or field_path != "authorization":
        return False
    if not isinstance(value, dict):
        return False
    return set(value).issubset(APPROVAL_AUTHORIZATION_KEYS)


def artifact_relative_path(root: Path, path: Path) -> str:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        return str(resolved_path.relative_to(resolved_root))
    except ValueError:
        return str(resolved_path)
