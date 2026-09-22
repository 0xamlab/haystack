"""Deploy one Space (or the fleet) from the manifest to the Hub.

    deploy.py --space NAME [--dry-run] [--rollback-to SHA]
    deploy.py --all [--dry-run] [--rollback-to SHA]

Steps per Space: ``stage.stage_space`` -> ``create_repo(repo_type="space", exist_ok=True)``
-> one atomic ``upload_folder(delete_patterns=["**"])`` (the scripts/hf_kernels/publish_hub.py
pattern) -> hardware / sleep / variables brought in line with the manifest when the live
runtime differs -> poll ``get_space_runtime().stage`` until the NEW revision is RUNNING
(40 min CPU, 60 min GPU) -> ``verify_remote`` against the live URL. Any failure exits non-zero.

The first RUNNING after an upload is not trusted: the Hub keeps the previous revision up
while it rebuilds, so ``wait_running`` accepts RUNNING only after it has observed a rebuild
stage (BUILDING, RUNNING_BUILDING, APP_STARTING, ...) or, when the runtime never leaves
RUNNING inside the settle window (``SETTLE_S``), only when ``space_info(repo).sha`` equals
the commit ``oid`` that ``upload_folder`` returned (``huggingface_hub.CommitInfo.oid``).

``--dry-run`` stages, prints the file list and the runtime diff (read anonymously where the
Hub allows it) and exits 0 without a single write. ``--rollback-to SHA`` stages from a
detached ``git worktree`` of that commit instead of the checkout.

The token comes from ``HF_TOKEN`` only (``make_api``); a dry run is anonymous and never
borrows a cached login. The Hub client is injected (``api_factory``) so the decision logic
runs against a fake in tests; huggingface_hub is imported lazily.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import verify_remote
from manifest import DEFAULT_MANIFEST, Manifest, Space, load_manifest
from stage import UPLOAD_IGNORE_PATTERNS, StageError, StageResult, stage_space

log = logging.getLogger(__name__)

POLL_INTERVAL_S = 20.0
SETTLE_S = 90.0
TERMINAL_FAILURE_STAGES = frozenset({"BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR", "NO_APP_FILE"})
MANIFEST_REL = Path("apps/spaces/spaces.toml")


class DeployError(RuntimeError):
    """A deploy step failed."""


class HubClient(Protocol):
    def create_repo(self, repo_id: str, **kwargs: Any) -> Any: ...

    def upload_folder(self, **kwargs: Any) -> Any: ...

    def get_space_runtime(self, repo_id: str) -> Any: ...

    def space_info(self, repo_id: str, **kwargs: Any) -> Any: ...

    def get_space_variables(self, repo_id: str) -> dict[str, Any]: ...

    def request_space_hardware(
        self, repo_id: str, hardware: str, *, sleep_time: int | None = None
    ) -> Any: ...

    def set_space_sleep_time(self, repo_id: str, sleep_time: int) -> Any: ...

    def add_space_variable(self, repo_id: str, key: str, value: str) -> Any: ...


class ApiFactory(Protocol):
    def __call__(self, token: str | None = None, *, anonymous: bool = False) -> HubClient: ...


@dataclass(frozen=True)
class RuntimeState:
    stage: str
    hardware: str | None
    requested_hardware: str | None
    sleep_time: int | None

    @property
    def effective_hardware(self) -> str | None:
        return self.requested_hardware or self.hardware


def _plain(value: Any) -> Any:
    return getattr(value, "value", value)


def runtime_state(api: HubClient, repo_id: str) -> RuntimeState:
    rt = api.get_space_runtime(repo_id)
    return RuntimeState(
        stage=str(_plain(rt.stage)),
        hardware=_plain(rt.hardware) and str(_plain(rt.hardware)),
        requested_hardware=_plain(rt.requested_hardware) and str(_plain(rt.requested_hardware)),
        sleep_time=rt.sleep_time,
    )


def live_variables(api: HubClient, repo_id: str) -> dict[str, str]:
    return {k: str(getattr(v, "value", v)) for k, v in api.get_space_variables(repo_id).items()}


@dataclass(frozen=True)
class Diff:
    hardware: tuple[str | None, str] | None = None
    sleep_time: tuple[int | None, int] | None = None
    variables: dict[str, tuple[str | None, str]] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return self.hardware is None and self.sleep_time is None and not self.variables

    def lines(self) -> list[str]:
        out: list[str] = []
        if self.hardware:
            out.append(f"hardware: {self.hardware[0]} -> {self.hardware[1]}")
        if self.sleep_time:
            out.append(f"sleep_time: {self.sleep_time[0]} -> {self.sleep_time[1]}")
        for key, (old, new) in sorted(self.variables.items()):
            out.append(f"variable {key}: {old!r} -> {new!r}")
        return out or ["runtime matches the manifest"]


def compute_diff(
    space: Space, state: RuntimeState | None, variables: dict[str, str] | None
) -> Diff:
    """What must change on the Hub so the live runtime matches the manifest."""
    if not space.is_live:
        return Diff()
    hardware = None
    sleep_time = None
    if state is not None:
        if state.effective_hardware != space.hardware:
            hardware = (state.effective_hardware, space.hardware)
        if state.sleep_time != space.sleep_time:
            sleep_time = (state.sleep_time, space.sleep_time)
    var_changes: dict[str, tuple[str | None, str]] = {}
    if variables is not None:
        for key, value in space.variables.items():
            if variables.get(key) != value:
                var_changes[key] = (variables.get(key), value)
    return Diff(hardware=hardware, sleep_time=sleep_time, variables=var_changes)


def apply_diff(api: HubClient, space: Space, diff: Diff) -> list[str]:
    applied: list[str] = []
    if diff.hardware:
        api.request_space_hardware(space.repo_id, diff.hardware[1], sleep_time=space.sleep_time)
        applied.append(f"request_space_hardware {diff.hardware[1]} sleep_time={space.sleep_time}")
    elif diff.sleep_time:
        api.set_space_sleep_time(space.repo_id, diff.sleep_time[1])
        applied.append(f"set_space_sleep_time {diff.sleep_time[1]}")
    for key, (_, value) in sorted(diff.variables.items()):
        api.add_space_variable(space.repo_id, key, value)
        applied.append(f"add_space_variable {key}")
    return applied


def commit_oid(info: Any) -> str:
    """The commit hash of an ``upload_folder`` result (``CommitInfo.oid``)."""
    oid = getattr(info, "oid", None)
    if not isinstance(oid, str) or not oid:
        raise DeployError(f"upload_folder returned no commit oid ({type(info).__name__})")
    return oid


def live_sha(api: HubClient, repo_id: str) -> str:
    """The commit the Hub currently serves for the Space (``SpaceInfo.sha``)."""
    sha = getattr(api.space_info(repo_id), "sha", None)
    if not isinstance(sha, str) or not sha:
        raise DeployError(f"space_info({repo_id}) returned no sha")
    return sha


@dataclass(frozen=True)
class Confirmed:
    """The new revision is RUNNING; ``evidence`` says how that was established."""

    state: RuntimeState
    evidence: str


def wait_running(
    api: HubClient,
    repo_id: str,
    timeout_s: float,
    *,
    expected_sha: str,
    settle_s: float = SETTLE_S,
    poll_s: float = POLL_INTERVAL_S,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Confirmed:
    """Poll until the revision ``expected_sha`` is RUNNING.

    RUNNING seen right after the upload is the previous revision still serving while the Hub
    rebuilds. It is accepted only after a non-RUNNING stage has been observed, or, when the
    runtime never leaves RUNNING for ``settle_s`` (a build too quick to catch, or a commit the
    Hub ignored), only when the Space's live sha equals ``expected_sha``; a mismatch after the
    settle window fails the deploy instead of blessing the old revision.
    """
    start = clock()
    deadline = start + timeout_s
    rebuild_seen = False
    while True:
        state = runtime_state(api, repo_id)
        if state.stage in TERMINAL_FAILURE_STAGES:
            raise DeployError(f"{repo_id} entered {state.stage}")
        if state.stage != "RUNNING":
            rebuild_seen = True
        elif rebuild_seen:
            return Confirmed(state, "rebuild observed")
        elif clock() - start >= settle_s:
            served = live_sha(api, repo_id)
            if served == expected_sha:
                return Confirmed(state, f"live sha {served[:12]} matches the upload")
            raise DeployError(
                f"{repo_id} stayed RUNNING for {settle_s:.0f}s on {served[:12]}, "
                f"not the uploaded {expected_sha[:12]}"
            )
        if clock() >= deadline:
            raise DeployError(f"{repo_id} still {state.stage} after {timeout_s / 60:.0f} min")
        log.info("%s: %s, waiting", repo_id, state.stage)
        sleep(poll_s)


def hf_token() -> str | None:
    token = os.environ.get("HF_TOKEN", "").strip()
    return token or None


def make_api(token: str | None = None, *, anonymous: bool = False) -> HubClient:
    """An ``HfApi`` bound to the deploy token, or anonymous for a dry run.

    The token is ``token`` when given, else ``HF_TOKEN`` from the environment; nothing else
    is consulted. ``anonymous=True`` passes ``token=False`` so huggingface_hub does not fall
    back to a cached login either.
    """
    from huggingface_hub import HfApi

    if anonymous:
        return HfApi(token=False)
    token = token or hf_token()
    if not token:
        raise DeployError(
            "HF_TOKEN is not set; export it in the environment "
            "(the token is read from HF_TOKEN only, never from a .env file)"
        )
    return HfApi(token=token)


def upload(api: HubClient, space: Space, staged: StageResult) -> Any:
    api.create_repo(space.repo_id, repo_type="space", space_sdk=space.sdk, exist_ok=True)
    return api.upload_folder(
        folder_path=str(staged.staged_dir),
        repo_id=space.repo_id,
        repo_type="space",
        commit_message=f"deploy {staged.git_sha}",
        delete_patterns=["**"],
        ignore_patterns=list(UPLOAD_IGNORE_PATTERNS),
    )


def read_runtime(
    api: HubClient, space: Space
) -> tuple[RuntimeState | None, dict[str, str] | None, list[str]]:
    """Runtime and variables, each None when the Hub refuses (anonymous dry-run)."""
    notes: list[str] = []
    state: RuntimeState | None = None
    variables: dict[str, str] | None = None
    if not space.is_live:
        return state, variables, notes
    try:
        state = runtime_state(api, space.repo_id)
    except Exception as exc:  # noqa: BLE001 - any Hub error means "not readable here"
        notes.append(f"runtime not readable: {type(exc).__name__}")
    try:
        variables = live_variables(api, space.repo_id)
    except Exception as exc:  # noqa: BLE001
        notes.append(f"variables not readable: {type(exc).__name__}")
    return state, variables, notes


@dataclass(frozen=True)
class RollbackCheckout:
    sha: str
    root: Path
    manifest_path: Path
    _repo_root: Path

    def cleanup(self) -> None:
        subprocess.run(  # noqa: S603
            ["git", "worktree", "remove", "--force", str(self.root)],  # noqa: S607
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        shutil.rmtree(self.root, ignore_errors=True)


def resolve_rollback(
    repo_root: Path, sha: str, tmp_root: Path, manifest_rel: Path = MANIFEST_REL
) -> RollbackCheckout:
    """Detached ``git worktree`` of ``sha`` under ``tmp_root``; the caller runs ``cleanup()``."""
    try:
        full = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--verify", f"{sha}^{{commit}}"],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise DeployError(f"unknown commit {sha!r}: {exc.stderr.strip()}") from exc
    root = Path(tmp_root) / f"rollback-{full[:12]}"
    try:
        subprocess.run(  # noqa: S603
            ["git", "worktree", "add", "--detach", str(root), full],  # noqa: S607
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        raise DeployError(f"git worktree add failed: {exc.stderr.strip()}") from exc
    manifest_path = root / manifest_rel
    if not manifest_path.is_file():
        checkout = RollbackCheckout(full, root, manifest_path, repo_root)
        checkout.cleanup()
        raise DeployError(f"{manifest_rel} does not exist at {full[:12]}")
    return RollbackCheckout(full, root, manifest_path, repo_root)


def repo_root_of(manifest_path: Path = DEFAULT_MANIFEST) -> Path:
    return manifest_path.resolve().parents[2]


@dataclass(frozen=True)
class DeployOutcome:
    space: str
    ok: bool
    lines: tuple[str, ...]


def deploy_space(
    space: Space,
    manifest: Manifest,
    api: HubClient,
    *,
    dry_run: bool,
    git_sha: str | None = None,
    fetch: verify_remote.Fetcher = verify_remote.urllib_fetch,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    workdir: Path | None = None,
) -> DeployOutcome:
    lines: list[str] = [f"== {space.name} ({space.repo_id}, sdk={space.sdk})"]
    tmp = tempfile.mkdtemp(prefix=f"stage-{space.name}-", dir=workdir)
    try:
        try:
            staged = stage_space(
                space.name, Path(tmp) / "staged", manifest=manifest, git_sha=git_sha
            )
        except StageError as exc:
            lines.append(f"stage failed: {exc}")
            return DeployOutcome(space.name, False, tuple(lines))
        lines.append(f"staged {len(staged.files)} files at git {staged.git_sha[:12]}")
        lines.extend(f"  {f}" for f in staged.files)
        if staged.shared_sha:
            lines.append(f"shared_sha {staged.shared_sha}")
        if space.secrets:
            lines.append(
                f"secrets required on the Space (set by the owner): {', '.join(space.secrets)}"
            )

        state, variables, notes = read_runtime(api, space)
        lines.extend(notes)
        diff = compute_diff(space, state, variables)
        lines.extend(diff.lines())

        if dry_run:
            lines.append("dry run: nothing written")
            return DeployOutcome(space.name, True, tuple(lines))

        info = upload(api, space, staged)
        try:
            oid = commit_oid(info)
        except DeployError as exc:
            lines.append(f"upload: {exc}")
            return DeployOutcome(space.name, False, tuple(lines))
        lines.append(f"uploaded: {getattr(info, 'commit_url', info)} ({oid[:12]})")
        lines.extend(apply_diff(api, space, diff))
        try:
            confirmed = wait_running(
                api,
                space.repo_id,
                space.poll_timeout_s,
                expected_sha=oid,
                clock=clock,
                sleep=sleep,
            )
        except DeployError as exc:
            lines.append(f"runtime: {exc}")
            return DeployOutcome(space.name, False, tuple(lines))
        final = confirmed.state
        lines.append(f"runtime: {final.stage} on {final.hardware} ({confirmed.evidence})")
        report = verify_remote.verify_space(
            space, fetch=fetch, expected_shared_sha=staged.shared_sha
        )
        lines.extend(report.lines())
        return DeployOutcome(space.name, report.ok, tuple(lines))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def select_spaces(manifest: Manifest, name: str | None, all_spaces: bool) -> list[Space]:
    if all_spaces:
        return list(manifest.spaces.values())
    if not name:
        raise DeployError("pass --space NAME or --all")
    return [manifest.space(name)]


def main(
    argv: list[str] | None = None,
    *,
    api_factory: ApiFactory = make_api,
    manifest_path: Path = DEFAULT_MANIFEST,
    token: str | None = None,
    fetch: verify_remote.Fetcher = verify_remote.urllib_fetch,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="deploy Spaces from apps/spaces/spaces.toml")
    ap.add_argument("--space", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback-to", default=None, metavar="SHA")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    token = token if token is not None else hf_token()
    if not a.dry_run and not token:
        print("HF_TOKEN is not set; refusing to deploy (use --dry-run to inspect)")
        return 2

    checkout: RollbackCheckout | None = None
    git_sha: str | None = None
    tmp_root = Path(tempfile.mkdtemp(prefix="deploy-"))
    try:
        if a.rollback_to:
            checkout = resolve_rollback(repo_root_of(manifest_path), a.rollback_to, tmp_root)
            manifest = load_manifest(checkout.manifest_path)
            git_sha = checkout.sha
            print(f"rollback: staging from {checkout.sha[:12]} at {checkout.root}")
        else:
            manifest = load_manifest(manifest_path)
        spaces = select_spaces(manifest, a.space, a.all)
        api = api_factory(None, anonymous=True) if a.dry_run else api_factory(token)
        failed: list[str] = []
        for space in spaces:
            outcome = deploy_space(
                space,
                manifest,
                api,
                dry_run=a.dry_run,
                git_sha=git_sha,
                fetch=fetch,
                clock=clock,
                sleep=sleep,
                workdir=tmp_root,
            )
            for line in outcome.lines:
                print(line)
            if not outcome.ok:
                failed.append(space.name)
        if failed:
            print(f"FAILED: {', '.join(failed)}")
            return 1
        return 0
    except DeployError as exc:
        print(f"deploy failed: {exc}")
        return 1
    finally:
        if checkout is not None:
            checkout.cleanup()
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
