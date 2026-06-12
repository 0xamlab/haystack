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
from apps.api_server.services.connector_egress import (
    connector_host_destination,
    enforce_connector_destination,
)
from apps.api_server.services.egress_guard import EgressAuditContext
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
    _ResolvedRepositorySource,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _normalize_repository_relative_path,
)
from apps.api_server.services.repository_intelligence_runtime import _worktrees_dir
from apps.api_server.services.repository_intelligence_shared import (
    _coerce_scope_uuid,
    _hash_payload,
)
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


_GIT_REF_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z._/-]*")
_ALLOWED_CLONE_SCHEMES = frozenset({"https", "http"})


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
    # Bound each run to a single URL authority: the password class excludes '/'
    # and whitespace (our tokens are percent-encoded by quote(safe=''), so they
    # never contain a raw '/'), and the quantifiers are possessive. That stops
    # the match from sweeping across repeated "scheme://host:" segments of
    # attacker-influenced git stderr — the sweep is the polynomial blowup
    # (py/polynomial-redos). Real "user:token@" runs still redact identically.
    return re.sub(r"(https://[^:/\s]++:)[^@\s/]++@", r"\1***@", value)


def _git_command(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float = 30.0,
    binary: bool = False,
    stdin: str | None = None,
) -> bytes | str:
    completed = subprocess.run(  # noqa: S603
        list(args),
        cwd=str(cwd) if cwd is not None else None,
        check=False,
        capture_output=True,
        timeout=timeout,
        input=stdin.encode("utf-8") if stdin is not None else None,
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
        _git_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=path, timeout=10.0)
    except RepositoryIntelligenceError:
        return False
    return True


_RESOLVED_OID_RE = re.compile(r"[0-9a-f]{40}")


def _validate_ref_shape(ref: str) -> None:
    """Reject option-like / metacharacter-bearing refs (defense in depth).

    This is hygiene, not the CodeQL control: py/command-line-injection honours
    only constant-compare and models-as-data barriers, never a regex guard, so
    the real protection is that ``ref`` never reaches a git argv at all (it is
    resolved to an object id via stdin, or matched against ``ls-remote`` stdout).
    """
    if ref.startswith("-") or ".." in ref or _GIT_REF_RE.fullmatch(ref) is None:
        raise RepositoryIntelligenceError(
            code="invalid_repository_ref",
            message="Repository ref contains unsupported characters.",
            status_code=422,
        )


def _resolve_git_ref(root_path: Path, ref: str) -> str:
    """Resolve an untrusted ref to a 40-hex object id without putting it in argv.

    ``ref`` is fed to ``git cat-file --batch-check`` on STDIN, so it can never be
    parsed as a git option and never reaches a command argument vector. The
    returned object id is parsed from git's stdout (not a taint source for
    py/command-line-injection) and is re-validated to a fixed 40-hex shape.
    """
    _validate_ref_shape(ref)
    line = str(
        _git_command(
            ["git", "-C", str(root_path), "cat-file", "--batch-check=%(objectname)"],
            stdin=f"{ref}\n",
            timeout=30.0,
        )
    ).strip()
    oid = line.split(" ", 1)[0] if line else ""
    if _RESOLVED_OID_RE.fullmatch(oid) is None:
        raise RepositoryIntelligenceError(
            code="unknown_repository_ref",
            message=f"Ref '{ref}' could not be resolved in the repository.",
            status_code=422,
        )
    return oid


def _match_remote_ref(listing: str, ref: str) -> tuple[str, str]:
    """Match an untrusted ref against ``git ls-remote`` output.

    Returns ``(kind, value)`` where kind is ``"branch"``, ``"tag"`` or ``"sha"``
    and ``value`` is taken FROM the ls-remote stdout (a branch/tag short name or
    a 40-hex oid). ``ref`` is only ever *compared* here; the returned value
    originates from git stdout, so no tainted value flows on to a git argv.
    """
    _validate_ref_shape(ref)
    sha_hit: str | None = None
    for raw in listing.splitlines():
        sha, _, refname = raw.partition("\t")
        sha = sha.strip()
        refname = refname.strip()
        if _RESOLVED_OID_RE.fullmatch(sha) is None or not refname:
            continue
        if refname == f"refs/heads/{ref}":
            return ("branch", refname[len("refs/heads/") :])
        if refname == f"refs/tags/{ref}":
            return ("tag", refname[len("refs/tags/") :])
        if sha == ref:
            sha_hit = sha
    if sha_hit is not None:
        return ("sha", sha_hit)
    raise RepositoryIntelligenceError(
        code="unknown_repository_ref",
        message="Requested ref was not found on the remote.",
        status_code=422,
    )


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
        ["git", "diff", "--name-only", "--relative", "--cached"],
        ["git", "diff", "--name-only", "--relative"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    changed_paths: set[str] = set()
    for command in commands:
        output = str(_git_command(command, cwd=root_path, timeout=60.0))
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
    output = str(_git_command(["git", "ls-files", "-s"], cwd=root_path, timeout=120.0))
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
        ["git", "ls-files"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    relative_paths: set[str] = set()
    for command in commands:
        output = str(_git_command(command, cwd=root_path, timeout=120.0))
        for line in output.splitlines():
            normalized = _normalize_repository_relative_path(line)
            if normalized:
                relative_paths.add(normalized)
    return sorted(relative_paths)


def _local_repository_resolved_revision(root_path: Path, *, is_git: bool) -> str:
    if not is_git:
        return _hash_directory_listing(root_path)
    head_revision = str(_git_command(["git", "rev-parse", "HEAD"], cwd=root_path))
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
    # NOTE: `ref` is untrusted (HTTP payload) and must NEVER reach a git argv.
    # It is resolved to an object id via stdin (_resolve_git_ref) or matched
    # against ls-remote stdout (_match_remote_ref); both also validate its shape.
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
                # Resolve the untrusted ref to an object id via stdin; only the
                # resolved oid (from git stdout) is ever placed in a git argv.
                resolved_oid = _resolve_git_ref(root_path, ref)
                resolved_revision = resolved_oid
                if not allow_writes:
                    cleanup_path = Path(tempfile.mkdtemp(prefix="algenta-repo-ref-"))
                    archive_bytes = _git_command(
                        ["git", "archive", "--format=tar", resolved_oid],
                        cwd=root_path,
                        timeout=60.0,
                        binary=True,
                    )
                    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as handle:
                        _extract_tar_handle(
                            handle=handle,
                            archive_path=root_path / f"{resolved_oid}.tar",
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
        # CodeQL barrier (py/command-line-injection): only http(s) clone URLs
        # with a host reach `git clone`; reject other schemes, a missing host,
        # or a leading "-" so the value can't become a git option/transport.
        parsed_clone = urlparse(repository_url)
        if (
            repository_url.startswith("-")
            or parsed_clone.scheme not in _ALLOWED_CLONE_SCHEMES
            or not parsed_clone.netloc
        ):
            raise RepositoryIntelligenceError(
                code="invalid_repository_url",
                message="Repository URL must be a http(s) clone URL.",
                status_code=422,
            )
        # B10: the git-transport pull below (ls-remote/clone/fetch) reaches the
        # customer-configured git host. Route it through the egress guard FIRST so the
        # self_hosted/air_gapped fail-closed policy + SSRF check apply before any socket
        # opens (Deny raises here, before auth_url is even built). The destination is the
        # cleartext repository_url host (NOT auth_url), so the embedded access token never
        # enters the policy/audit path. One enforce covers all three ops (same remote host).
        enforce_connector_destination(
            connector_host_destination(parsed_clone.hostname, port=parsed_clone.port),
            surface="repository_git_clone",
            audit_context=EgressAuditContext(org_id=_coerce_scope_uuid(connector.org_id)),
        )
        auth_url = _authenticated_repository_url(connector_type, repository_url, config)
        cleanup_path = (
            _worktrees_dir(str(connector.org_id), str(connector.id))
            / (worktree_name or uuid.uuid4().hex)
            if allow_writes
            else Path(tempfile.mkdtemp(prefix="algenta-repo-clone-"))
        )
        cleanup_path.mkdir(parents=True, exist_ok=True)
        # Resolve the untrusted ref against the remote's advertised refs WITHOUT
        # putting `ref` in any git argv: `git ls-remote` takes no ref argument,
        # and _match_remote_ref returns a branch/tag short name or oid taken from
        # that stdout (not a taint source), so only trusted values reach git.
        ref_target: tuple[str, str] | None = None
        if ref:
            listing = str(_git_command(["git", "ls-remote", auth_url], timeout=60.0))
            ref_target = _match_remote_ref(listing, ref)
        clone_args = ["git", "clone", "--depth", "1"]
        if ref_target is not None and ref_target[0] in {"branch", "tag"}:
            clone_args.extend(["--branch", ref_target[1]])
        clone_args.extend(["--", auth_url, str(cleanup_path)])
        _git_command(clone_args, timeout=180.0)
        if ref_target is not None and ref_target[0] == "sha":
            resolved_oid = ref_target[1]
            _git_command(
                ["git", "fetch", "--depth", "1", "origin", resolved_oid],
                cwd=cleanup_path,
                timeout=120.0,
            )
            _git_command(
                ["git", "checkout", "--detach", resolved_oid],
                cwd=cleanup_path,
                timeout=120.0,
            )
        resolved_revision = str(_git_command(["git", "rev-parse", "HEAD"], cwd=cleanup_path))
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
