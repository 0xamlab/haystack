from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from apps.api_server.models.data_connector import DataConnector
from apps.api_server.services.config_crypto import decrypt_config_json
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
    _ResolvedRepositorySource,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _normalize_repository_relative_path,
)
from apps.api_server.services.repository_intelligence_runtime import _worktrees_dir
from apps.api_server.services.repository_intelligence_shared import _hash_payload
from apps.api_server.services.repository_intelligence_storage import (
    _extract_archive,
    _extract_tar_handle,
    _hash_file,
)

REPOSITORY_CONNECTOR_TYPES = frozenset(
    {"github_repo", "gitlab_repo", "bitbucket_repo", "local_repo", "repo_archive"}
)


def _parse_connector_config(connector: DataConnector) -> dict[str, Any]:
    if not connector.config_json:
        return {}
    parsed = json.loads(
        decrypt_config_json(connector.config_json, org_id=connector.org_id) or "{}"
    )
    if not isinstance(parsed, dict):
        raise RepositoryIntelligenceError(
            code="invalid_repository_config",
            message="Repository connector config must be a JSON object.",
            status_code=422,
        )
    return parsed


def _require_repository_connector(connector: DataConnector) -> None:
    connector_type = str(connector.connector_type.value)
    if connector_type not in REPOSITORY_CONNECTOR_TYPES:
        raise RepositoryIntelligenceError(
            code="repository_connector_required",
            message=(
                f"Connector '{connector.id}' has type '{connector_type}' and cannot "
                "be used as a repository resource."
            ),
            status_code=409,
            details={"connector_type": connector_type},
        )


def _repo_access_token(config: dict[str, Any]) -> str | None:
    for key in ("access_token", "token", "api_token"):
        raw = str(config.get(key) or "").strip()
        if raw:
            return raw
    return None


def _repository_url(config: dict[str, Any], connector_type: str) -> str | None:
    if connector_type in {"local_repo", "repo_archive"}:
        return None
    for key in ("repository_url", "clone_url", "url"):
        raw = str(config.get(key) or "").strip()
        if raw:
            return raw
    return None


def _authenticated_repository_url(
    connector_type: str, repository_url: str, config: dict[str, Any]
) -> str:
    token = _repo_access_token(config)
    if token is None:
        return repository_url
    parsed = urlparse(repository_url)
    if parsed.scheme != "https":
        return repository_url
    if connector_type == "github_repo":
        username = "x-access-token"
    elif connector_type == "gitlab_repo":
        username = "oauth2"
    else:
        username = "x-token-auth"
    netloc = f"{username}:{quote(token, safe='')}@{parsed.netloc}"
    return parsed._replace(netloc=netloc).geturl()


def _redact_credentials(value: str) -> str:
    return re.sub(r"(https://[^:/]+:)[^@]+@", r"\1***@", value)


def _git_command(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float = 30.0,
    binary: bool = False,
) -> bytes | str:
    completed = subprocess.run(  # noqa: S603
        list(args),
        cwd=str(cwd) if cwd is not None else None,
        check=False,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        stderr = _redact_credentials(completed.stderr.decode("utf-8", errors="replace").strip())
        raise RepositoryIntelligenceError(
            code="git_command_failed",
            message=stderr or f"git command failed: {' '.join(args)}",
            status_code=502,
            details={"command": [_redact_credentials(str(arg)) for arg in args]},
        )
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8", errors="replace").strip()


def _is_git_repository(path: Path) -> bool:
    try:
        _git_command(["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"], timeout=10.0)
    except RepositoryIntelligenceError:
        return False
    return True


def _is_git_sha(ref: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", ref))


def _path_from_config(config: dict[str, Any], *, field: str) -> Path:
    raw = str(config.get(field) or "").strip()
    if not raw:
        raise RepositoryIntelligenceError(
            code="invalid_repository_config",
            message=f"Repository connector config requires '{field}'.",
            status_code=422,
            details={"field": field},
        )
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise RepositoryIntelligenceError(
            code="repository_source_not_found",
            message=f"Repository source path '{path}' was not found.",
            status_code=404,
        )
    return path


def _hash_directory_listing(root_path: Path) -> str:
    entries: list[tuple[str, str]] = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        entries.append((str(path.relative_to(root_path)), _hash_file(path)))
    return _hash_payload(entries)


def _git_changed_paths(root_path: Path) -> list[str]:
    commands = [
        ["git", "-C", str(root_path), "diff", "--name-only", "--relative", "--cached"],
        ["git", "-C", str(root_path), "diff", "--name-only", "--relative"],
        ["git", "-C", str(root_path), "ls-files", "--others", "--exclude-standard"],
    ]
    changed_paths: set[str] = set()
    for command in commands:
        output = str(_git_command(command, timeout=60.0))
        for raw_line in output.splitlines():
            candidate = raw_line.strip()
            if candidate:
                changed_paths.add(candidate.replace("\\", "/"))
    return sorted(changed_paths)


def _git_tracked_content_hashes(
    root_path: Path, *, candidate_paths: Sequence[str] | None = None
) -> dict[str, str]:
    candidate_path_set = (
        {
            _normalize_repository_relative_path(value)
            for value in candidate_paths
            if str(value).strip()
        }
        if candidate_paths is not None
        else None
    )
    changed_paths = set(_git_changed_paths(root_path))
    output = str(_git_command(["git", "-C", str(root_path), "ls-files", "-s"], timeout=120.0))
    tracked_hashes: dict[str, str] = {}
    for line in output.splitlines():
        metadata, separator, raw_path = line.partition("\t")
        if not separator:
            continue
        normalized_path = _normalize_repository_relative_path(raw_path)
        if candidate_path_set is not None and normalized_path not in candidate_path_set:
            continue
        if normalized_path in changed_paths:
            continue
        metadata_parts = metadata.split()
        if len(metadata_parts) < 2:
            continue
        tracked_hashes[normalized_path] = metadata_parts[1]
    return tracked_hashes


def _git_repository_relative_files(root_path: Path) -> list[str] | None:
    if not _is_git_repository(root_path):
        return None
    commands = [
        ["git", "-C", str(root_path), "ls-files"],
        ["git", "-C", str(root_path), "ls-files", "--others", "--exclude-standard"],
    ]
    relative_paths: set[str] = set()
    for command in commands:
        output = str(_git_command(command, timeout=120.0))
        for line in output.splitlines():
            normalized = _normalize_repository_relative_path(line)
            if normalized:
                relative_paths.add(normalized)
    return sorted(relative_paths)


def _local_repository_resolved_revision(root_path: Path, *, is_git: bool) -> str:
    if not is_git:
        return _hash_directory_listing(root_path)
    head_revision = str(_git_command(["git", "-C", str(root_path), "rev-parse", "HEAD"]))
    changed_paths = _git_changed_paths(root_path)
    if not changed_paths:
        return head_revision
    dirty_entries: list[dict[str, Any]] = []
    for relative_path in changed_paths:
        absolute_path = (root_path / relative_path).resolve()
        if absolute_path.exists() and absolute_path.is_file():
            dirty_entries.append(
                {
                    "path": relative_path,
                    "content_hash": _hash_file(absolute_path),
                    "byte_size": absolute_path.stat().st_size,
                }
            )
            continue
        dirty_entries.append(
            {
                "path": relative_path,
                "content_hash": None,
                "byte_size": None,
            }
        )
    return _hash_payload(
        {
            "head_revision": head_revision,
            "dirty_entries": dirty_entries,
        }
    )


@contextmanager
def resolved_repository_source(
    *,
    connector: Any,
    config: dict[str, Any],
    ref: str | None,
    allow_writes: bool = False,
    worktree_name: str | None = None,
) -> Iterator[_ResolvedRepositorySource]:
    connector_type = str(connector.connector_type.value)
    cleanup_path: Path | None = None
    root_path: Path
    repository_url = _repository_url(config, connector_type)
    is_git = connector_type != "repo_archive"
    try:
        if connector_type == "local_repo":
            root_path = _path_from_config(config, field="path")
            is_git = _is_git_repository(root_path)
            if ref:
                if not is_git:
                    raise RepositoryIntelligenceError(
                        code="repository_ref_requires_git",
                        message="Local repository ref selection requires a git working tree.",
                        status_code=409,
                    )
                resolved_revision = str(
                    _git_command(["git", "-C", str(root_path), "rev-parse", ref])
                )
                if not allow_writes:
                    cleanup_path = Path(tempfile.mkdtemp(prefix="algenta-repo-ref-"))
                    archive_bytes = _git_command(
                        ["git", "-C", str(root_path), "archive", "--format=tar", ref],
                        timeout=60.0,
                        binary=True,
                    )
                    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as handle:
                        _extract_tar_handle(
                            handle=handle,
                            archive_path=root_path / f"{ref}.tar",
                            destination=cleanup_path,
                        )
                    root_path = cleanup_path
                    is_git = False
            else:
                resolved_revision = _local_repository_resolved_revision(
                    root_path,
                    is_git=is_git,
                )
            yield _ResolvedRepositorySource(
                root_path=root_path,
                connector_type=connector_type,
                repository_url=repository_url,
                ref=ref,
                resolved_revision=resolved_revision,
                is_git=is_git,
                cleanup_path=cleanup_path,
            )
            return

        if connector_type == "repo_archive":
            archive_path = _path_from_config(config, field="path")
            cleanup_path = (
                _worktrees_dir(str(connector.org_id), str(connector.id))
                / (worktree_name or uuid.uuid4().hex)
                if allow_writes
                else Path(tempfile.mkdtemp(prefix="algenta-repo-archive-"))
            )
            cleanup_path.mkdir(parents=True, exist_ok=True)
            _extract_archive(archive_path, cleanup_path)
            yield _ResolvedRepositorySource(
                root_path=cleanup_path,
                connector_type=connector_type,
                repository_url=None,
                ref=ref,
                resolved_revision=_hash_file(archive_path),
                is_git=False,
                cleanup_path=None if allow_writes else cleanup_path,
            )
            return

        if repository_url is None:
            raise RepositoryIntelligenceError(
                code="invalid_repository_config",
                message=f"{connector_type} connector requires repository_url.",
                status_code=422,
            )
        auth_url = _authenticated_repository_url(connector_type, repository_url, config)
        cleanup_path = (
            _worktrees_dir(str(connector.org_id), str(connector.id))
            / (worktree_name or uuid.uuid4().hex)
            if allow_writes
            else Path(tempfile.mkdtemp(prefix="algenta-repo-clone-"))
        )
        cleanup_path.mkdir(parents=True, exist_ok=True)
        clone_args = ["git", "clone", "--depth", "1"]
        if ref and not _is_git_sha(ref):
            clone_args.extend(["--branch", ref])
        clone_args.extend([auth_url, str(cleanup_path)])
        _git_command(clone_args, timeout=180.0)
        if ref and _is_git_sha(ref):
            _git_command(
                ["git", "-C", str(cleanup_path), "fetch", "--depth", "1", "origin", ref],
                timeout=120.0,
            )
            _git_command(["git", "-C", str(cleanup_path), "checkout", ref], timeout=120.0)
        resolved_revision = str(_git_command(["git", "-C", str(cleanup_path), "rev-parse", "HEAD"]))
        yield _ResolvedRepositorySource(
            root_path=cleanup_path,
            connector_type=connector_type,
            repository_url=repository_url,
            ref=ref,
            resolved_revision=resolved_revision,
            is_git=True,
            cleanup_path=None if allow_writes else cleanup_path,
        )
    finally:
        if cleanup_path is not None and cleanup_path.exists() and not allow_writes:
            shutil.rmtree(cleanup_path, ignore_errors=True)
