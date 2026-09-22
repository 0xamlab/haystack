"""apps/spaces/tools/deploy.py — decision logic against a fake Hub client, no network."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import deploy
import pytest
from manifest import load_manifest

from .test_verify_remote import GRADIO_PAGE, FakeHttp, _info, _stub_routes

SHA = "f" * 40
OID = "0123456789abcdef0123456789abcdef01234567"
OLD_OID = "9" * 40


@dataclass
class Runtime:
    stage: str
    hardware: str | None = None
    requested_hardware: str | None = None
    sleep_time: int | None = None


@dataclass
class Var:
    value: str


@dataclass(frozen=True)
class Commit:
    """The two CommitInfo fields deploy reads (huggingface_hub 1.26: commit_url, oid)."""

    commit_url: str
    oid: str


class Clock:
    """Fake monotonic clock advanced by the injected sleep."""

    def __init__(self) -> None:
        self.t = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


class FakeHub:
    """Records every call; `runtimes` is consumed one per get_space_runtime(), the last repeats."""

    def __init__(
        self,
        runtimes: list[Runtime] | None = None,
        variables: dict[str, str] | None = None,
        *,
        fail_reads: bool = False,
        sha: str = OID,
        sdk: str | None = None,
    ) -> None:
        self.runtimes = list(runtimes or [])
        self.variables = {k: Var(v) for k, v in (variables or {}).items()}
        self.fail_reads = fail_reads
        self.sha = sha
        self.sdk = sdk
        self.calls: list[tuple] = []
        self.commit_url = "https://huggingface.co/spaces/x/commit/1"

    def create_repo(self, repo_id, **kw):
        self.calls.append(("create_repo", repo_id, kw))

    def upload_folder(self, **kw):
        self.calls.append(("upload_folder", kw))
        return Commit(self.commit_url, OID)

    def get_space_runtime(self, repo_id):
        if self.fail_reads:
            raise PermissionError("401")
        self.calls.append(("get_space_runtime", repo_id))
        return self.runtimes.pop(0) if len(self.runtimes) > 1 else self.runtimes[0]

    def space_info(self, repo_id, **kw):
        if self.fail_reads:
            raise PermissionError("401")
        self.calls.append(("space_info", repo_id))
        return SimpleNamespace(sha=self.sha, sdk=self.sdk, card_data=None)

    def get_space_variables(self, repo_id):
        if self.fail_reads:
            raise PermissionError("401")
        return dict(self.variables)

    def request_space_hardware(self, repo_id, hardware, *, sleep_time=None):
        self.calls.append(("request_space_hardware", repo_id, hardware, sleep_time))

    def set_space_sleep_time(self, repo_id, sleep_time):
        self.calls.append(("set_space_sleep_time", repo_id, sleep_time))

    def add_space_variable(self, repo_id, key, value):
        self.calls.append(("add_space_variable", repo_id, key, value))
        self.variables[key] = Var(value)


@pytest.fixture
def mf():
    return load_manifest()


@pytest.fixture
def mf_shell(mf):
    """The fleet as it will be once every live app renders the shared footer stamp (M2)."""
    return replace(
        mf,
        spaces={n: replace(s, shared_shell=True) if s.is_live else s for n, s in mf.spaces.items()},
    )


def test_compute_diff_hardware_sleep_and_variables(mf) -> None:
    space = mf.space("governed-agent")
    state = deploy.RuntimeState(
        stage="RUNNING", hardware="cpu-basic", requested_hardware=None, sleep_time=3600
    )
    diff = deploy.compute_diff(space, state, {"ALGENTA_PROVIDER": "nscale", "OTHER": "kept"})
    assert diff.hardware == ("cpu-basic", "l4x1")
    assert diff.sleep_time == (3600, -1)
    assert diff.variables == {
        "ALGENTA_BASE_URL": (None, "https://api.algenta.ai"),
        "ALGENTA_PROVIDER_MODEL": (None, "Qwen/Qwen3-4B-Instruct-2507"),
    }
    assert not diff.empty
    assert diff.lines() == [
        "hardware: cpu-basic -> l4x1",
        "sleep_time: 3600 -> -1",
        "variable ALGENTA_BASE_URL: None -> 'https://api.algenta.ai'",
        "variable ALGENTA_PROVIDER_MODEL: None -> 'Qwen/Qwen3-4B-Instruct-2507'",
    ]


def test_compute_diff_is_empty_when_hub_matches_or_switch_is_pending(mf) -> None:
    space = mf.space("algenta")
    matching = deploy.RuntimeState("RUNNING", "cpu-upgrade", None, -1)
    assert deploy.compute_diff(space, matching, dict(space.variables)).empty
    pending = deploy.RuntimeState("BUILDING", "cpu-basic", "cpu-upgrade", -1)
    assert deploy.compute_diff(space, pending, dict(space.variables)).hardware is None
    # unreadable runtime (anonymous dry-run) -> nothing claimed about hardware, variables still compared
    diff = deploy.compute_diff(space, None, {})
    assert diff.hardware is None and diff.sleep_time is None
    assert set(diff.variables) == {"ALGENTA_BASE_URL"}
    assert deploy.compute_diff(mf.space("llm-modules"), None, None).empty
    assert deploy.Diff().lines() == ["runtime matches the manifest"]


def test_compute_diff_sdk_from_the_hub_frontmatter(mf) -> None:
    static = mf.space("for-llm-agents")
    # the Hub still runs the old app: the only change is the SDK, carried by the README
    diff = deploy.compute_diff(static, None, None, live_sdk="gradio")
    assert diff.sdk == ("gradio", "static")
    assert diff.hardware is None and diff.sleep_time is None and diff.variables == {}
    assert not diff.empty
    assert diff.lines() == [
        "sdk: gradio -> static (set by the README frontmatter in the upload; "
        "create_repo(exist_ok=True) cannot change an existing Space)"
    ]
    assert deploy.compute_diff(mf.space("llm-modules"), None, None, live_sdk="docker").sdk == (
        "docker",
        "static",
    )
    # already flipped: nothing to do; unreadable: nothing claimed
    assert deploy.compute_diff(static, None, None, live_sdk="static").empty
    assert deploy.compute_diff(static, None, None, live_sdk=None).empty
    # a live Space gets the same entry ahead of its runtime lines (speed-arena -> docker in M2)
    live = replace(mf.space("speed-arena"), sdk="docker")
    state = deploy.RuntimeState("RUNNING", "cpu-upgrade", None, -1)
    diff = deploy.compute_diff(live, state, dict(live.variables), live_sdk="gradio")
    assert diff.sdk == ("gradio", "docker") and diff.lines()[0].startswith("sdk: gradio -> docker")
    # a static Space never gets runtime entries even if a runtime is handed in
    diff = deploy.compute_diff(static, state, {"X": "1"}, live_sdk="static")
    assert diff.empty


def test_live_sdk_reads_the_hub_types() -> None:
    assert deploy.live_sdk(FakeHub(sdk="gradio"), "x/y") == "gradio"

    class CardOnly(FakeHub):
        def space_info(self, repo_id, **kw):
            return SimpleNamespace(sha=OID, sdk=None, card_data={"sdk": "docker"})

    assert deploy.live_sdk(CardOnly(), "x/y") == "docker"
    with pytest.raises(deploy.DeployError, match="returned no sdk"):
        deploy.live_sdk(FakeHub(sdk=None), "x/y")
    with pytest.raises(deploy.DeployError, match="returned no sdk"):
        deploy.live_sdk(FakeHub(sdk=""), "x/y")


def test_space_info_from_huggingface_hub_carries_sdk() -> None:
    hf_api = pytest.importorskip("huggingface_hub.hf_api")
    names = {f.name for f in __import__("dataclasses").fields(hf_api.SpaceInfo)}
    assert {"sdk", "sha", "card_data"} <= names
    info = hf_api.SpaceInfo(id="thyn-ai/algenta-for-llm-agents", sdk="gradio", sha=OID)
    assert (
        deploy.live_sdk(SimpleNamespace(space_info=lambda repo_id, **kw: info), "x/y") == "gradio"
    )


def test_read_live_reads_sdk_for_every_space_and_runtime_for_live_ones(mf) -> None:
    hub = FakeHub([Runtime("RUNNING", "cpu-upgrade", None, -1)], {"A": "1"}, sdk="gradio")
    live = deploy.read_live(hub, mf.space("for-llm-agents"))
    assert live == deploy.LiveRead("gradio", None, None, ())
    assert [c[0] for c in hub.calls] == ["space_info"], "no runtime calls for a static Space"
    hub = FakeHub([Runtime("RUNNING", "cpu-upgrade", None, -1)], {"A": "1"}, sdk="gradio")
    live = deploy.read_live(hub, mf.space("speed-arena"))
    assert live.sdk == "gradio" and live.variables == {"A": "1"} and live.notes == ()
    assert live.state == deploy.RuntimeState("RUNNING", "cpu-upgrade", None, -1)
    assert [c[0] for c in hub.calls] == ["space_info", "get_space_runtime"]
    live = deploy.read_live(FakeHub(sdk=None), mf.space("llm-modules"))
    assert live.sdk is None and live.notes == ("sdk not readable: DeployError",)


def test_apply_diff_uses_one_hardware_call_with_sleep_time(mf) -> None:
    space = mf.space("algenta")
    hub = FakeHub()
    diff = deploy.Diff(
        hardware=("cpu-basic", "cpu-upgrade"),
        sleep_time=(None, -1),
        variables={"ALGENTA_BASE_URL": (None, "https://api.algenta.ai")},
    )
    applied = deploy.apply_diff(hub, space, diff)
    assert hub.calls == [
        ("request_space_hardware", "thyn-ai/algenta", "cpu-upgrade", -1),
        ("add_space_variable", "thyn-ai/algenta", "ALGENTA_BASE_URL", "https://api.algenta.ai"),
    ]
    assert applied == [
        "request_space_hardware cpu-upgrade sleep_time=-1",
        "add_space_variable ALGENTA_BASE_URL",
    ]
    hub = FakeHub()
    deploy.apply_diff(hub, space, deploy.Diff(sleep_time=(3600, -1)))
    assert hub.calls == [("set_space_sleep_time", "thyn-ai/algenta", -1)]


def test_runtime_state_normalises_enums_and_none() -> None:
    class Enum:
        def __init__(self, value):
            self.value = value

    hub = FakeHub([Runtime(Enum("RUNNING"), Enum("cpu-upgrade"), None, -1)])
    state = deploy.runtime_state(hub, "thyn-ai/algenta")
    assert state == deploy.RuntimeState("RUNNING", "cpu-upgrade", None, -1)
    assert state.effective_hardware == "cpu-upgrade"
    assert deploy.live_variables(FakeHub(variables={"A": "1"}), "x") == {"A": "1"}


def test_wait_running_accepts_running_only_after_a_rebuild_was_seen() -> None:
    # the previous revision is still RUNNING right after the upload
    hub = FakeHub(
        [Runtime("RUNNING", "cpu-upgrade"), Runtime("BUILDING"), Runtime("RUNNING", "cpu-upgrade")]
    )
    clock = Clock()
    confirmed = deploy.wait_running(
        hub, "thyn-ai/algenta", 2400, expected_sha=OID, poll_s=20, clock=clock, sleep=clock.sleep
    )
    assert confirmed.state.stage == "RUNNING" and confirmed.state.hardware == "cpu-upgrade"
    assert confirmed.evidence == "rebuild observed"
    assert clock.slept == [20, 20]
    assert [c[0] for c in hub.calls] == ["get_space_runtime"] * 3, "no sha lookup needed"

    # a rebuild seen on the very first poll counts too
    hub = FakeHub([Runtime("BUILDING"), Runtime("APP_STARTING"), Runtime("RUNNING", "cpu-upgrade")])
    clock = Clock()
    confirmed = deploy.wait_running(
        hub, "thyn-ai/algenta", 2400, expected_sha=OID, poll_s=20, clock=clock, sleep=clock.sleep
    )
    assert confirmed.evidence == "rebuild observed" and clock.slept == [20, 20]


def test_wait_running_settles_on_the_live_sha_when_the_hub_never_leaves_running() -> None:
    hub = FakeHub([Runtime("RUNNING", "cpu-upgrade")], sha=OID)
    clock = Clock()
    confirmed = deploy.wait_running(
        hub,
        "thyn-ai/algenta",
        2400,
        expected_sha=OID,
        settle_s=90,
        poll_s=20,
        clock=clock,
        sleep=clock.sleep,
    )
    assert confirmed.state.stage == "RUNNING"
    assert confirmed.evidence == f"live sha {OID[:12]} matches the upload"
    assert clock.slept == [20] * 5, "polls until the settle window has elapsed"
    names = [c[0] for c in hub.calls]
    assert names == ["get_space_runtime"] * 6 + ["space_info"]
    assert hub.calls[-1] == ("space_info", "thyn-ai/algenta")

    hub = FakeHub([Runtime("RUNNING", "cpu-upgrade")], sha=OLD_OID)
    clock = Clock()
    with pytest.raises(deploy.DeployError, match=f"stayed RUNNING for 90s on {OLD_OID[:12]}"):
        deploy.wait_running(
            hub,
            "thyn-ai/algenta",
            2400,
            expected_sha=OID,
            settle_s=90,
            poll_s=20,
            clock=clock,
            sleep=clock.sleep,
        )
    assert [c[0] for c in hub.calls].count("space_info") == 1
    assert clock.t == 100.0, "fails at the settle window, not at the 40 min deadline"


def test_wait_running_times_out_and_stops_on_build_error() -> None:
    hub = FakeHub([Runtime("BUILDING")])
    clock = Clock()
    with pytest.raises(deploy.DeployError, match="still BUILDING after 40 min"):
        deploy.wait_running(
            hub,
            "thyn-ai/algenta",
            2400,
            expected_sha=OID,
            poll_s=600,
            clock=clock,
            sleep=clock.sleep,
        )
    assert not any(c[0] == "space_info" for c in hub.calls)
    hub = FakeHub([Runtime("BUILDING"), Runtime("BUILD_ERROR")])
    with pytest.raises(deploy.DeployError, match="entered BUILD_ERROR"):
        deploy.wait_running(
            hub,
            "thyn-ai/algenta",
            2400,
            expected_sha=OID,
            poll_s=1,
            clock=lambda: 0.0,
            sleep=lambda s: None,
        )
    # RUNNING(old) then a terminal failure on the rebuild
    hub = FakeHub([Runtime("RUNNING"), Runtime("RUNTIME_ERROR")])
    with pytest.raises(deploy.DeployError, match="entered RUNTIME_ERROR"):
        deploy.wait_running(
            hub, "x/y", 2400, expected_sha=OID, poll_s=1, clock=lambda: 0.0, sleep=lambda s: None
        )


def test_commit_oid_and_live_sha_read_the_hub_types() -> None:
    assert deploy.commit_oid(Commit("https://x/commit/1", OID)) == OID
    with pytest.raises(deploy.DeployError, match="no commit oid"):
        deploy.commit_oid(SimpleNamespace(commit_url="https://x/commit/1"))
    with pytest.raises(deploy.DeployError, match="no commit oid"):
        deploy.commit_oid(Commit("https://x/commit/1", ""))
    assert deploy.live_sha(FakeHub(sha=OLD_OID), "x/y") == OLD_OID

    class NoSha(FakeHub):
        def space_info(self, repo_id, **kw):
            return SimpleNamespace(sha=None)

    with pytest.raises(deploy.DeployError, match="returned no sha"):
        deploy.live_sha(NoSha(), "x/y")


def test_commit_info_from_huggingface_hub_carries_oid_and_commit_url() -> None:
    hf_api = pytest.importorskip("huggingface_hub.hf_api")
    info = hf_api.CommitInfo(
        commit_url=f"https://huggingface.co/spaces/thyn-ai/algenta/commit/{OID}",
        commit_message="deploy",
        commit_description="",
        oid=OID,
    )
    assert deploy.commit_oid(info) == OID
    assert "sha" in {f.name for f in __import__("dataclasses").fields(hf_api.SpaceInfo)}


def test_hf_token_from_env_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("HF_API_KEY", "hf_should_be_ignored")
    assert deploy.hf_token() is None
    monkeypatch.setenv("HF_TOKEN", "  hf_abc  ")
    assert deploy.hf_token() == "hf_abc"
    source = Path(deploy.__file__).read_text(encoding="utf-8")
    assert '".env"' not in source and "'.env'" not in source
    assert "HF_API_KEY" not in source


def test_make_api_binds_the_env_token_and_refuses_without_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hf = pytest.importorskip("huggingface_hub")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("HF_TOKEN=hf_from_dotenv_must_be_ignored\n", encoding="utf-8")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("HF_API_KEY", "hf_wrong_name")
    with pytest.raises(deploy.DeployError, match="HF_TOKEN is not set") as exc:
        deploy.make_api()
    assert "never from a .env file" in str(exc.value)

    monkeypatch.setenv("HF_TOKEN", "hf_from_env")
    api = deploy.make_api()
    assert isinstance(api, hf.HfApi) and api.token == "hf_from_env"
    assert deploy.make_api("hf_explicit").token == "hf_explicit"

    anonymous = deploy.make_api(anonymous=True)
    assert isinstance(anonymous, hf.HfApi)
    assert anonymous.token is False, "a dry run never borrows a cached login"


def test_dry_run_stages_lists_files_and_writes_nothing(mf, tmp_path: Path) -> None:
    space = mf.space("speed-arena")
    hub = FakeHub([Runtime("RUNNING", "cpu-basic", None, None)], variables={}, sdk="gradio")
    outcome = deploy.deploy_space(space, mf, hub, dry_run=True, git_sha=SHA, workdir=tmp_path)
    assert outcome.ok
    text = "\n".join(outcome.lines)
    assert "  app.py" in text and "  algenta_spaces/shell.py" in text and "  .shared_sha" in text
    assert "sdk:" not in text, "the Hub already runs the manifest sdk"
    assert "hardware: cpu-basic -> cpu-upgrade" in text
    assert "sleep_time: None -> -1" in text
    assert "secrets required on the Space (set by the owner): HF_TOKEN" in text
    assert deploy.STATIC_NOTE not in text
    assert text.endswith("dry run: nothing written")
    assert [c[0] for c in hub.calls] == ["space_info", "get_space_runtime"]
    assert list(tmp_path.iterdir()) == [], "staging directory cleaned up"


def test_dry_run_of_a_static_stub_shows_the_sdk_flip_and_no_python(mf, tmp_path: Path) -> None:
    """The pre-publish dry run: the Hub says gradio, the staged README says static."""
    space = mf.space("for-llm-agents")
    hub = FakeHub(sdk="gradio")
    outcome = deploy.deploy_space(space, mf, hub, dry_run=True, git_sha=SHA, workdir=tmp_path)
    assert outcome.ok, outcome.lines
    assert list(outcome.lines[:6]) == [
        "== for-llm-agents (thyn-ai/algenta-for-llm-agents, sdk=static)",
        f"staged 4 files at git {SHA[:12]}",
        "  .git_sha",
        "  README.md",
        "  index.html",
        "  style.css",
    ]
    assert list(outcome.lines[6:]) == [
        "sdk: gradio -> static (set by the README frontmatter in the upload; "
        "create_repo(exist_ok=True) cannot change an existing Space)",
        deploy.STATIC_NOTE,
        "dry run: nothing written",
    ]
    assert hub.calls == [("space_info", "thyn-ai/algenta-for-llm-agents")]
    assert list(tmp_path.iterdir()) == []
    # llm-modules is a docker Space on the Hub today
    outcome = deploy.deploy_space(
        mf.space("llm-modules"),
        mf,
        FakeHub(sdk="docker"),
        dry_run=True,
        git_sha=SHA,
        workdir=tmp_path,
    )
    assert any(line.startswith("sdk: docker -> static") for line in outcome.lines)
    # once published the dry run reports a match
    outcome = deploy.deploy_space(
        space, mf, FakeHub(sdk="static"), dry_run=True, git_sha=SHA, workdir=tmp_path
    )
    assert "runtime matches the manifest" in outcome.lines and deploy.STATIC_NOTE in outcome.lines


def test_dry_run_survives_anonymous_read_refusal(mf, tmp_path: Path) -> None:
    hub = FakeHub(fail_reads=True)
    outcome = deploy.deploy_space(
        mf.space("algenta"), mf, hub, dry_run=True, git_sha=SHA, workdir=tmp_path
    )
    assert outcome.ok
    assert "sdk not readable: PermissionError" in outcome.lines
    assert "runtime not readable: PermissionError" in outcome.lines
    assert "variables not readable: PermissionError" in outcome.lines
    assert hub.calls == []


def test_full_deploy_uploads_applies_diff_polls_and_verifies(mf, tmp_path: Path) -> None:
    space = mf.space("algenta")
    hub = FakeHub(
        [
            Runtime("RUNNING", "cpu-basic", None, 3600),
            Runtime("BUILDING"),
            Runtime("RUNNING", "cpu-upgrade", None, -1),
        ]
    )
    captured: dict[str, str] = {}

    def fetch(url: str, timeout: float) -> tuple[int, str]:
        if url.endswith("/gradio_api/info"):
            return 200, _info(*space.api_names)
        return 200, f'<span class="alg-shell-stamp">build {captured["sha"]}</span>'

    def sleep(s: float) -> None:
        pass

    class Hub(FakeHub):
        def upload_folder(self, **kw):
            captured["sha"] = (Path(kw["folder_path"]) / ".shared_sha").read_text().strip()
            captured["files"] = json.dumps(
                sorted(p.name for p in Path(kw["folder_path"]).iterdir())
            )
            return super().upload_folder(**kw)

    hub = Hub(hub.runtimes, {}, sdk="docker")
    outcome = deploy.deploy_space(
        space,
        mf,
        hub,
        dry_run=False,
        git_sha=SHA,
        fetch=fetch,
        clock=lambda: 0.0,
        sleep=sleep,
        workdir=tmp_path,
    )
    assert outcome.ok, outcome.lines
    assert f"uploaded: {hub.commit_url} ({OID[:12]})" in outcome.lines
    names = [c[0] for c in hub.calls]
    assert names == [
        "space_info",
        "get_space_runtime",
        "create_repo",
        "upload_folder",
        "request_space_hardware",
        "add_space_variable",
        "get_space_runtime",
        "get_space_runtime",
    ]
    create = hub.calls[2]
    assert create[1] == "thyn-ai/algenta"
    assert create[2] == {"repo_type": "space", "space_sdk": "docker", "exist_ok": True}
    up = hub.calls[3][1]
    assert up["repo_id"] == "thyn-ai/algenta" and up["repo_type"] == "space"
    assert up["commit_message"] == f"deploy {SHA}"
    assert up["delete_patterns"] == ["**"]
    assert "tests/**" in up["ignore_patterns"] and "*.whl" in up["ignore_patterns"]
    assert ".git_sha" in json.loads(captured["files"]) and "algenta_spaces" in json.loads(
        captured["files"]
    )
    assert hub.calls[4] == ("request_space_hardware", "thyn-ai/algenta", "cpu-upgrade", -1)
    assert "runtime: RUNNING on cpu-upgrade (rebuild observed)" in outcome.lines
    # algenta is not on the shared shell yet: the stamp check is skipped, loudly
    assert "  [SKIP] footer_stamp skipped: app not yet on the shared shell" in outcome.lines
    assert outcome.lines[-1] == "algenta: all checks passed; skipped: footer_stamp"


def test_deploy_confirms_a_quiet_hub_by_sha_and_fails_on_a_stale_one(mf, tmp_path: Path) -> None:
    space = mf.space("speed-arena")
    http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, "<html/>")})
    hub = FakeHub([Runtime("RUNNING", "cpu-upgrade", None, -1)], {}, sha=OID)
    clock = Clock()
    outcome = deploy.deploy_space(
        space,
        mf,
        hub,
        dry_run=False,
        git_sha=SHA,
        fetch=http,
        clock=clock,
        sleep=clock.sleep,
        workdir=tmp_path,
    )
    assert outcome.ok, outcome.lines
    assert f"runtime: RUNNING on cpu-upgrade (live sha {OID[:12]} matches the upload)" in (
        outcome.lines
    )
    assert clock.t >= deploy.SETTLE_S
    hub = FakeHub([Runtime("RUNNING", "cpu-upgrade", None, -1)], {}, sha=OLD_OID)
    http = FakeHttp({"/gradio_api/info": (200, _info(*space.api_names)), "/": (200, "<html/>")})
    clock = Clock()
    outcome = deploy.deploy_space(
        space,
        mf,
        hub,
        dry_run=False,
        git_sha=SHA,
        fetch=http,
        clock=clock,
        sleep=clock.sleep,
        workdir=tmp_path,
    )
    assert not outcome.ok
    assert outcome.lines[-1] == (
        f"runtime: thyn-ai/algenta-speed-arena stayed RUNNING for 90s on {OLD_OID[:12]}, "
        f"not the uploaded {OID[:12]}"
    )
    assert http.calls == [], "no verification against a revision that never went live"


def test_deploy_fails_on_verify_and_on_runtime_error(mf_shell, tmp_path: Path) -> None:
    mf = mf_shell
    space = mf.space("speed-arena")
    hub = FakeHub(
        [Runtime("RUNNING", "cpu-upgrade", None, -1), Runtime("RUNNING", "cpu-upgrade", None, -1)],
        {},
    )
    http = FakeHttp({"/gradio_api/info": (200, _info("nothing")), "/": (200, "<html/>")})
    clock = Clock()
    outcome = deploy.deploy_space(
        space,
        mf,
        hub,
        dry_run=False,
        git_sha=SHA,
        fetch=http,
        clock=clock,
        sleep=clock.sleep,
        workdir=tmp_path,
    )
    assert not outcome.ok
    assert "speed-arena: FAILED: expected_endpoints, footer_stamp" in outcome.lines
    hub = FakeHub([Runtime("RUNNING", "cpu-upgrade", None, -1), Runtime("RUNTIME_ERROR")], {})
    outcome = deploy.deploy_space(
        space,
        mf,
        hub,
        dry_run=False,
        git_sha=SHA,
        fetch=http,
        clock=lambda: 0.0,
        sleep=lambda s: None,
        workdir=tmp_path,
    )
    assert (
        not outcome.ok
        and outcome.lines[-1] == "runtime: thyn-ai/algenta-speed-arena entered RUNTIME_ERROR"
    )


def test_static_redirect_deploy_flips_the_sdk_by_upload_alone(mf, tmp_path: Path) -> None:
    """Publishing a stub over the old docker app: create_repo, one wiping upload, poll, verify."""
    space = mf.space("llm-modules")
    captured: dict[str, list[str]] = {}

    class Hub(FakeHub):
        def upload_folder(self, **kw):
            root = Path(kw["folder_path"])
            captured["files"] = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
            return super().upload_folder(**kw)

    hub = Hub(
        [Runtime("RUNNING"), Runtime("BUILDING"), Runtime("RUNNING", "cpu-basic")], {}, sdk="docker"
    )
    http = FakeHttp(_stub_routes(space))
    clock = Clock()
    outcome = deploy.deploy_space(
        space,
        mf,
        hub,
        dry_run=False,
        git_sha=SHA,
        fetch=http,
        clock=clock,
        sleep=clock.sleep,
        workdir=tmp_path,
    )
    assert outcome.ok, outcome.lines
    names = [c[0] for c in hub.calls]
    assert names == [
        "space_info",
        "create_repo",
        "upload_folder",
        "get_space_runtime",
        "get_space_runtime",
        "get_space_runtime",
    ], "no hardware, sleep or variable call for a static Space"
    assert hub.calls[1] == (
        "create_repo",
        "thyn-ai/algenta-llm-modules",
        {"repo_type": "space", "space_sdk": "static", "exist_ok": True},
    )
    up = hub.calls[2][1]
    assert up["repo_id"] == "thyn-ai/algenta-llm-modules" and up["repo_type"] == "space"
    assert up["delete_patterns"] == ["**"], "every old app file goes"
    assert up["commit_message"] == f"deploy {SHA}"
    assert captured["files"] == [".git_sha", "README.md", "index.html", "style.css"]
    assert any(line.startswith("sdk: docker -> static") for line in outcome.lines)
    assert deploy.STATIC_NOTE in outcome.lines
    assert "sdk static carried by README.md in the upload" in outcome.lines
    assert "runtime: RUNNING on cpu-basic (rebuild observed)" in outcome.lines
    assert http.calls == [
        f"{space.space_url}/",
        f"{space.space_url}/style.css",
        f"https://huggingface.co/spaces/{space.repo_id}/raw/main/README.md",
    ]
    assert outcome.lines[-1] == "llm-modules: all checks passed"
    assert "footer_stamp" not in "\n".join(outcome.lines)


def test_static_redirect_deploy_fails_when_the_hub_keeps_serving_the_old_app(
    mf, tmp_path: Path
) -> None:
    space = mf.space("for-llm-agents")
    hub = FakeHub([Runtime("RUNNING"), Runtime("BUILDING"), Runtime("RUNNING")], {}, sdk="gradio")
    still_gradio = _stub_routes(
        space, html=GRADIO_PAGE, css=GRADIO_PAGE, readme="---\nsdk: gradio\n---\n"
    )
    clock = Clock()
    outcome = deploy.deploy_space(
        space,
        mf,
        hub,
        dry_run=False,
        git_sha=SHA,
        fetch=FakeHttp(still_gradio),
        clock=clock,
        sleep=clock.sleep,
        workdir=tmp_path,
    )
    assert not outcome.ok
    assert outcome.lines[-1] == "for-llm-agents: FAILED: redirect_page, stylesheet, hub_sdk"
    assert any("a Gradio app is still served" in line for line in outcome.lines)
    assert any("Hub README declares sdk: gradio" in line for line in outcome.lines)


def test_stage_failure_is_an_outcome_not_a_crash(mf, tmp_path: Path) -> None:
    from dataclasses import replace

    broken = replace(mf.space("algenta"), source="does-not-exist")
    mf2 = replace(mf, spaces={**mf.spaces, "algenta": broken})
    outcome = deploy.deploy_space(
        broken, mf2, FakeHub(), dry_run=True, git_sha=SHA, workdir=tmp_path
    )
    assert not outcome.ok and outcome.lines[-1].startswith("stage failed: source directory missing")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@x", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo_with_two_manifests(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    (repo / "apps" / "spaces").mkdir(parents=True)
    _git(repo, "init", "-q")
    manifest = repo / "apps" / "spaces" / "spaces.toml"
    manifest.write_text(
        '[fleet]\norg = "thyn-ai"\nshared_package = "_shared/algenta_spaces"\nbudget_usd = 1\n',
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v1")
    v1 = _git(repo, "rev-parse", "HEAD")
    manifest.write_text(
        '[fleet]\norg = "thyn-ai"\nshared_package = "_shared/algenta_spaces"\nbudget_usd = 2\n',
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v2")
    v2 = _git(repo, "rev-parse", "HEAD")
    return repo, v1, v2


def test_resolve_rollback_checks_out_the_sha_in_a_worktree(tmp_path: Path) -> None:
    repo, v1, v2 = _repo_with_two_manifests(tmp_path)
    checkout = deploy.resolve_rollback(repo, v1[:8], tmp_path / "wt")
    try:
        assert checkout.sha == v1
        assert checkout.manifest_path.is_file()
        assert "budget_usd = 1" in checkout.manifest_path.read_text(encoding="utf-8")
        assert checkout.root.name == f"rollback-{v1[:12]}"
        assert str(checkout.root) in _git(repo, "worktree", "list")
        assert "budget_usd = 2" in (repo / "apps/spaces/spaces.toml").read_text(encoding="utf-8"), (
            "main checkout untouched"
        )
    finally:
        checkout.cleanup()
    assert not checkout.root.exists()
    assert str(checkout.root) not in _git(repo, "worktree", "list")


def test_resolve_rollback_rejects_unknown_sha_and_manifest_less_commits(tmp_path: Path) -> None:
    repo, v1, _ = _repo_with_two_manifests(tmp_path)
    with pytest.raises(deploy.DeployError, match="unknown commit"):
        deploy.resolve_rollback(repo, "deadbeef", tmp_path / "wt")
    with pytest.raises(deploy.DeployError, match="does not exist at"):
        deploy.resolve_rollback(repo, v1, tmp_path / "wt2", manifest_rel=Path("apps/other.toml"))
    assert "rollback-" not in _git(repo, "worktree", "list")


def test_repo_root_and_select_spaces(mf, apps_spaces_dir: Path) -> None:
    assert deploy.repo_root_of() == apps_spaces_dir.parents[1]
    assert [s.name for s in deploy.select_spaces(mf, None, True)] == list(mf.spaces)
    assert deploy.select_spaces(mf, "algenta", False)[0].repo_id == "thyn-ai/algenta"
    with pytest.raises(deploy.DeployError, match="--space NAME or --all"):
        deploy.select_spaces(mf, None, False)


def test_main_dry_run_all_exits_zero_without_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    made: list[tuple[str | None, bool]] = []

    def factory(token=None, *, anonymous=False):
        made.append((token, anonymous))
        return FakeHub(
            [Runtime("RUNNING", "cpu-upgrade", None, -1)],
            {"ALGENTA_BASE_URL": "https://api.algenta.ai"},
        )

    rc = deploy.main(["--all", "--dry-run"], api_factory=factory)
    out = capsys.readouterr().out
    assert rc == 0 and made == [(None, True)], "a dry run asks for an anonymous client"
    for name in (
        "algenta",
        "speed-arena",
        "governed-agent",
        "for-llm-agents",
        "governed-tool-calls",
        "llm-modules",
    ):
        assert f"== {name} (" in out
    assert out.count("dry run: nothing written") == 6


def test_main_refuses_to_deploy_without_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    rc = deploy.main(["--space", "algenta"], api_factory=lambda t=None, **kw: FakeHub())
    assert rc == 2 and "HF_TOKEN is not set" in capsys.readouterr().out


def test_main_deploys_one_space_and_propagates_failures(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    hub = FakeHub(
        [Runtime("RUNNING", "cpu-upgrade", None, -1), Runtime("RUNNING", "cpu-upgrade", None, -1)],
        {},
    )
    http = FakeHttp({"/gradio_api/info": (200, _info("wrong")), "/": (200, "<html/>")})
    clock = Clock()
    made: list[tuple[str | None, bool]] = []

    def factory(token=None, *, anonymous=False):
        made.append((token, anonymous))
        return hub

    rc = deploy.main(
        ["--space", "speed-arena"],
        api_factory=factory,
        token="hf_test",
        fetch=http,
        clock=clock,
        sleep=clock.sleep,
    )
    out = capsys.readouterr().out
    assert rc == 1 and "FAILED: speed-arena" in out
    assert made == [("hf_test", False)]
    assert any(c[0] == "upload_folder" for c in hub.calls)


def test_main_rollback_stages_from_the_requested_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    spaces = repo / "apps" / "spaces"
    (spaces / "_redirects" / "old").mkdir(parents=True)
    (spaces / "_redirects" / "old" / "index.html").write_text("<html>v1</html>", encoding="utf-8")
    (spaces / "_redirects" / "old" / "README.md").write_text("---\nsdk: static\n---\n", "utf-8")
    (spaces / "spaces.toml").write_text(
        "\n".join(
            [
                "[fleet]",
                'org = "thyn-ai"',
                'shared_package = "_shared/algenta_spaces"',
                "budget_usd = 1",
                "[spaces.old]",
                'repo_id = "thyn-ai/old"',
                'sdk = "static"',
                'source = "_redirects/old"',
                'redirect_to = "https://huggingface.co/spaces/thyn-ai/algenta"',
                'verify = "verify_remote:check_redirect"',
            ]
        ),
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v1")
    v1 = _git(repo, "rev-parse", "HEAD")
    (spaces / "_redirects" / "old" / "index.html").write_text("<html>v2</html>", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v2")

    rc = deploy.main(
        ["--space", "old", "--dry-run", "--rollback-to", v1],
        api_factory=lambda t=None, **kw: FakeHub(),
        manifest_path=spaces / "spaces.toml",
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert f"rollback: staging from {v1[:12]}" in out
    assert f"staged 3 files at git {v1[:12]}" in out
    assert "rollback-" not in _git(repo, "worktree", "list")
