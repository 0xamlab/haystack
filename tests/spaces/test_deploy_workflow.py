""".github/workflows/deploy-spaces.yml — the fleet deploy workflow.

Checked as data (triggers, pins, permissions, where inputs and secrets may appear) and by
execution: the plan step's script runs under bash against the real manifest, the inline Python
compiles on this interpreter, and every CLI flag the workflow passes to a tool is one that tool's
argparse defines. No network.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from _rules import FAKE_WORDS
from manifest import load_manifest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_REL = Path(".github/workflows/deploy-spaces.yml")
WORKFLOW = REPO_ROOT / WORKFLOW_REL
README = REPO_ROOT / "docs/spaces/README.md"
TOOLS = REPO_ROOT / "apps/spaces/tools"
REFERENCE_WORKFLOWS = ("build-hf-kernels.yml", "ci.yml")

ENVIRONMENT = "hf-spaces-deploy"
JOBS = ("test", "plan", "dry-run", "deploy")
PIN_RE = re.compile(
    r"^\s*(?:-\s+)?uses:\s+(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(?P<sha>[0-9a-f]{40})"
    r"\s+#\s*v\d+(?:\.\d+)*\s*$"
)
HEREDOC_RE = re.compile(r"<<'PY'\n(?P<body>.*?)\nPY\b", re.DOTALL)
FLAG_RE = re.compile(r"(--[a-z][a-z0-9-]*)")
ADD_ARGUMENT_RE = re.compile(r"""add_argument\(\s*["'](--[a-z][a-z0-9-]*)["']""")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE)


@pytest.fixture(scope="module")
def raw() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def wf(raw: str) -> dict:
    return yaml.safe_load(raw)


def _triggers(wf: dict) -> dict:
    # PyYAML reads the bare key `on` as the YAML 1.1 boolean True.
    return wf["on"] if "on" in wf else wf[True]


def _steps(wf: dict, job: str | None = None) -> Iterator[tuple[str, int, dict]]:
    for name, spec in wf["jobs"].items():
        if job is not None and name != job:
            continue
        for i, step in enumerate(spec["steps"]):
            yield name, i, step


def _uncommented(raw: str) -> str:
    return "\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("#"))


def _reference_pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    for name in REFERENCE_WORKFLOWS:
        for line in (REPO_ROOT / ".github/workflows" / name).read_text().splitlines():
            m = PIN_RE.match(line)
            if m:
                pins.setdefault(m["action"], m["sha"])
    return pins


def _tool_flags(tool: str) -> set[str]:
    return set(ADD_ARGUMENT_RE.findall((TOOLS / tool).read_text(encoding="utf-8")))


def _run_plan(tmp_path: Path, wf: dict, **env: str) -> tuple[subprocess.CompletedProcess, dict]:
    """Run the plan step's `run:` script under bash exactly as the runner would."""
    step = next(s for _, _, s in _steps(wf, "plan") if s.get("id") == "pick")
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    # The step calls `python3`; make that this interpreter (3.12 or 3.14, whichever runs pytest).
    path = f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}"
    run_env = {
        "PATH": path,
        "HOME": os.environ.get("HOME", str(tmp_path)),
        "GITHUB_OUTPUT": str(output),
        "MANIFEST": step["env"]["MANIFEST"],
        "SPACES_INPUT": "",
        "DRY_RUN_INPUT": "",
        "EVENT_NAME": "push",
        **env,
    }
    proc = subprocess.run(
        ["bash", "-c", step["run"]],
        cwd=REPO_ROOT,
        env=run_env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    outputs: dict[str, str] = {}
    for line in output.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        outputs[key] = value
    return proc, outputs


# --- shape -----------------------------------------------------------------------------------


def test_workflow_parses_with_the_planned_name_and_jobs(wf: dict) -> None:
    assert wf["name"] == "deploy-spaces"
    assert tuple(wf["jobs"]) == JOBS


def test_triggers_are_dispatch_and_push_to_main_on_the_spaces_tree(wf: dict, raw: str) -> None:
    triggers = _triggers(wf)
    assert set(triggers) == {"workflow_dispatch", "push"}
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"spaces", "dry_run", "rollback_sha"}
    assert inputs["spaces"]["type"] == "string" and inputs["spaces"]["default"] == "all"
    assert inputs["dry_run"]["type"] == "boolean" and inputs["dry_run"]["default"] is True
    assert inputs["rollback_sha"]["type"] == "string" and inputs["rollback_sha"]["default"] == ""
    push = triggers["push"]
    assert push["branches"] == ["main"]
    assert set(push["paths"]) == {"apps/spaces/**", WORKFLOW_REL.as_posix()}
    assert "pull_request_target" not in raw
    assert "pull_request" not in triggers


def test_permissions_are_minimal_and_not_widened_per_job(wf: dict) -> None:
    assert wf["permissions"] == {"contents": "read", "deployments": "write"}
    for name, job in wf["jobs"].items():
        assert "permissions" not in job, f"{name} widens permissions"


def test_concurrency_is_per_ref_and_never_cancels_a_deploy(wf: dict) -> None:
    assert wf["concurrency"]["group"] == "deploy-spaces-${{ github.ref }}"
    assert wf["concurrency"]["cancel-in-progress"] is False


# --- supply chain ----------------------------------------------------------------------------


def test_every_action_is_pinned_to_a_full_sha_with_a_version_comment(raw: str) -> None:
    uses = [line for line in raw.splitlines() if re.match(r"^\s*(?:-\s+)?uses:", line)]
    assert uses, "no `uses:` lines found"
    for line in uses:
        assert PIN_RE.match(line), f"not pinned to a 40-hex sha with a version comment: {line!r}"


def test_action_pins_match_the_repository_reference_workflows(raw: str) -> None:
    reference = _reference_pins()
    for line in raw.splitlines():
        m = PIN_RE.match(line)
        if m:
            assert m["action"] in reference, f"{m['action']} has no pin in {REFERENCE_WORKFLOWS}"
            assert m["sha"] == reference[m["action"]], f"{m['action']} drifts from the repo pin"


def test_checkout_never_persists_credentials(wf: dict) -> None:
    checkouts = [
        s for _, _, s in _steps(wf) if str(s.get("uses", "")).startswith("actions/checkout@")
    ]
    assert len(checkouts) == 4  # one per job
    for step in checkouts:
        assert step["with"]["persist-credentials"] is False


def test_python_version_is_the_pinned_314(wf: dict) -> None:
    assert wf["env"]["PYTHON_VERSION"] == "3.14"
    setups = [
        s for _, _, s in _steps(wf) if str(s.get("uses", "")).startswith("actions/setup-python@")
    ]
    assert len(setups) == 3  # test, dry-run, deploy; plan uses the runner's python3
    for step in setups:
        assert step["with"]["python-version"] == "${{ env.PYTHON_VERSION }}"


# --- expression and secret hygiene -----------------------------------------------------------


def test_run_blocks_contain_no_expressions(wf: dict) -> None:
    for job, i, step in _steps(wf):
        run = step.get("run")
        if run is None:
            continue
        assert "${{" not in run, f"{job} step {i} interpolates an expression into the shell"
        assert "inputs." not in run and "github.event" not in run, f"{job} step {i} reads inputs"


def test_inputs_reach_the_shell_only_through_env(wf: dict, raw: str) -> None:
    in_env = 0
    for _, _, step in _steps(wf):
        for value in step.get("env", {}).values():
            in_env += str(value).count("inputs.")
    total = _uncommented(raw).count("inputs.")
    assert in_env == total, "an `inputs.` reference sits outside a step env"
    assert in_env >= 3  # spaces + dry_run (plan) and rollback_sha (dry-run, deploy)


def test_secret_is_read_only_by_the_deploy_step_env(wf: dict, raw: str) -> None:
    occurrences = _uncommented(raw).count("secrets.")
    found = []
    for job, i, step in _steps(wf):
        for key, value in step.get("env", {}).items():
            if "secrets." in str(value):
                found.append((job, i, key, value))
    assert found == [("deploy", 3, "HF_TOKEN", "${{ secrets.HF_TOKEN }}")]
    assert occurrences == 1
    for job in ("test", "plan", "dry-run"):
        assert "environment" not in wf["jobs"][job]
        assert "secrets." not in yaml.safe_dump(wf["jobs"][job])


def test_deploy_job_runs_in_the_hf_spaces_deploy_environment(wf: dict) -> None:
    deploy = wf["jobs"]["deploy"]
    assert deploy["environment"] == ENVIRONMENT
    assert deploy["needs"] == ["test", "plan"]
    assert "needs.plan.outputs.dry_run == 'false'" in deploy["if"]
    assert "github.event_name == 'workflow_dispatch'" in deploy["if"]
    assert deploy["timeout-minutes"] >= 60  # the GPU runtime poll budget


def test_dry_run_job_is_anonymous_and_gated_on_the_plan(wf: dict) -> None:
    dry = wf["jobs"]["dry-run"]
    assert dry["needs"] == ["test", "plan"]
    assert dry["if"] == "needs.plan.outputs.dry_run == 'true'"
    run = dry["steps"][-1]["run"]
    assert "--dry-run" in run and "HF_TOKEN" not in yaml.safe_dump(dry)


# --- matrix ----------------------------------------------------------------------------------


@pytest.mark.parametrize("job", ["dry-run", "deploy"])
def test_matrix_derives_from_the_plan_output(wf: dict, job: str) -> None:
    strategy = wf["jobs"][job]["strategy"]
    assert strategy["fail-fast"] is False
    assert strategy["max-parallel"] == 2
    assert strategy["matrix"] == {"space": "${{ fromJson(needs.plan.outputs.matrix) }}"}
    for step in wf["jobs"][job]["steps"]:
        if "run" in step and "$SPACE" in step["run"]:
            assert step["env"]["SPACE"] == "${{ matrix.space }}"


def test_plan_step_reads_spaces_toml_through_the_strict_loader(wf: dict) -> None:
    plan = wf["jobs"]["plan"]
    assert plan["outputs"] == {
        "matrix": "${{ steps.pick.outputs.matrix }}",
        "dry_run": "${{ steps.pick.outputs.dry_run }}",
    }
    step = next(s for s in plan["steps"] if s.get("id") == "pick")
    assert step["env"]["MANIFEST"] == "apps/spaces/spaces.toml"
    assert (REPO_ROOT / step["env"]["MANIFEST"]).is_file()
    assert "load_manifest" in step["run"]
    assert step["env"]["SPACES_INPUT"] == "${{ inputs.spaces }}"
    assert step["env"]["DRY_RUN_INPUT"] == "${{ inputs.dry_run }}"
    assert step["env"]["EVENT_NAME"] == "${{ github.event_name }}"


def test_plan_on_push_dry_runs_every_space_in_the_manifest(tmp_path: Path, wf: dict) -> None:
    proc, outputs = _run_plan(tmp_path, wf, EVENT_NAME="push")
    assert proc.returncode == 0, proc.stderr
    # the fleet is the flagship alone since 2026-09-23
    assert json.loads(outputs["matrix"]) == list(load_manifest().spaces) == ["algenta"]
    assert outputs["dry_run"] == "true"
    assert proc.stdout == "dry run: algenta\n"


def test_plan_default_dispatch_names_exist_in_the_manifest(tmp_path: Path, wf: dict) -> None:
    """Every name the default dispatch (`spaces=all`) would deploy is a table in spaces.toml."""
    default = _triggers(wf)["workflow_dispatch"]["inputs"]["spaces"]["default"]
    proc, outputs = _run_plan(
        tmp_path, wf, EVENT_NAME="workflow_dispatch", SPACES_INPUT=default, DRY_RUN_INPUT="false"
    )
    assert proc.returncode == 0, proc.stderr
    manifest = load_manifest()
    names = json.loads(outputs["matrix"])
    assert names == list(manifest.spaces) == ["algenta"]
    # one docker Space: the deep-dives and the static redirect stubs left the fleet on 2026-09-23
    assert {manifest.space(n).sdk for n in names} == {"docker"}
    assert outputs["dry_run"] == "false"
    assert proc.stdout == "DEPLOY: algenta\n"


def test_plan_dispatch_dry_run_true_never_deploys(tmp_path: Path, wf: dict) -> None:
    proc, outputs = _run_plan(
        tmp_path, wf, EVENT_NAME="workflow_dispatch", SPACES_INPUT="all", DRY_RUN_INPUT="true"
    )
    assert proc.returncode == 0, proc.stderr
    assert outputs["dry_run"] == "true"


# An inline two-Space fleet for the plan step's ordering rules: the real manifest holds the
# flagship alone since 2026-09-23, so ordering across names is exercised on this file instead.
TWO_SPACE_TOML = """\
[fleet]
org = "thyn-ai"
shared_package = "_shared/algenta_spaces"
budget_usd = 10

[spaces.algenta]
repo_id = "thyn-ai/algenta"
sdk = "docker"
source = "algenta"
python = "3.14"
hardware = "cpu-upgrade"
sleep_time = -1
shared_shell = true
verify = "verify_remote:check_algenta"
api_names = ["try_run"]

[spaces.arena]
repo_id = "thyn-ai/algenta-arena"
sdk = "gradio"
source = "arena"
python = "3.12"
hardware = "cpu-upgrade"
sleep_time = -1
shared_shell = false
verify = "verify_remote:check_algenta"
api_names = ["run_duel_ui"]
"""


def test_plan_selects_named_spaces_in_order_without_duplicates(tmp_path: Path, wf: dict) -> None:
    # the same name twice on the real manifest collapses to one matrix entry
    proc, outputs = _run_plan(
        tmp_path,
        wf,
        EVENT_NAME="workflow_dispatch",
        SPACES_INPUT="algenta algenta",
        DRY_RUN_INPUT="false",
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(outputs["matrix"]) == ["algenta"]
    # request order wins and repeats collapse, on an inline two-Space manifest: only the step's
    # MANIFEST env changes, the script under bash is the workflow's own
    inline = tmp_path / "spaces.toml"
    inline.write_text(TWO_SPACE_TOML, encoding="utf-8")
    assert list(load_manifest(inline).spaces) == ["algenta", "arena"]
    proc, outputs = _run_plan(
        tmp_path,
        wf,
        EVENT_NAME="workflow_dispatch",
        SPACES_INPUT="arena algenta arena",
        DRY_RUN_INPUT="false",
        MANIFEST=str(inline),
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(outputs["matrix"]) == ["arena", "algenta"]


def test_plan_treats_an_empty_selection_as_all(tmp_path: Path, wf: dict) -> None:
    proc, outputs = _run_plan(tmp_path, wf, EVENT_NAME="workflow_dispatch", SPACES_INPUT="   ")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(outputs["matrix"]) == list(load_manifest().spaces)


def test_plan_fails_loudly_on_an_unknown_space(tmp_path: Path, wf: dict) -> None:
    proc, outputs = _run_plan(tmp_path, wf, EVENT_NAME="workflow_dispatch", SPACES_INPUT="nope")
    assert proc.returncode != 0
    assert "unknown space 'nope'" in proc.stderr
    assert outputs == {}


# --- the deploy steps drive the real tools ---------------------------------------------------


def test_deploy_steps_run_in_order_and_use_flags_the_tools_define(wf: dict) -> None:
    steps = wf["jobs"]["deploy"]["steps"]
    runs = [s.get("run", "") for s in steps]
    deploy_i = next(i for i, r in enumerate(runs) if "tools/deploy.py" in r)
    verify_i = next(i for i, r in enumerate(runs) if "verify_remote.py" in r)
    record_i = next(i for i, r in enumerate(runs) if "/deployments" in r)
    assert deploy_i < verify_i < record_i == len(steps) - 1
    for tool in ("deploy.py", "stage.py", "verify_remote.py"):
        for run in runs:
            for line in run.splitlines():
                if tool in line:
                    used = set(FLAG_RE.findall(line)) - {"--detach", "--verify"}
                    assert used <= _tool_flags(tool), f"{tool}: {used - _tool_flags(tool)}"
    assert "--dry-run" not in runs[deploy_i]
    assert '--rollback-to "$ROLLBACK_SHA"' in runs[deploy_i]
    assert '--space "$SPACE" --staged' in runs[verify_i]
    for job in ("dry-run", "deploy"):
        for step in wf["jobs"][job]["steps"]:
            if "$ROLLBACK_SHA" in step.get("run", ""):
                assert step["env"]["ROLLBACK_SHA"] == "${{ inputs.rollback_sha }}"
            if "checkout@" in step.get("uses", ""):
                assert step["with"]["fetch-depth"] == 0  # rollback needs the whole history


def test_verify_step_uses_the_tooling_of_the_deployed_revision(wf: dict) -> None:
    run = next(
        s["run"] for s in wf["jobs"]["deploy"]["steps"] if "verify_remote.py" in s.get("run", "")
    )
    assert 'src="$GITHUB_WORKSPACE"' in run
    assert 'git worktree add --detach "$src" "$ROLLBACK_SHA"' in run
    assert (
        '"$src/apps/spaces/tools/stage.py" --space "$SPACE" --out "$RUNNER_TEMP/verify-staged"'
        in run
    )
    assert (
        '"$src/apps/spaces/tools/verify_remote.py" --space "$SPACE" --staged "$RUNNER_TEMP/verify-staged"'
        in run
    )


def test_deployment_record_marks_the_last_green_sha_per_space(wf: dict) -> None:
    step = wf["jobs"]["deploy"]["steps"][-1]
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
    run = step["run"]
    assert 'gh api "repos/$GITHUB_REPOSITORY/deployments" --input -' in run
    assert 'gh api "repos/$GITHUB_REPOSITORY/deployments/$deployment_id/statuses" --input -' in run
    assert 'environment: "hf-spaces-deploy"' in run
    assert "required_contexts: []" in run and "auto_merge: false" in run
    assert '--arg task "deploy:$SPACE"' in run and '--arg desc "$SPACE"' in run
    assert 'state: "success"' in run
    assert 'ref="$GITHUB_SHA"' in run
    assert 'ref="$(git rev-parse --verify "${ROLLBACK_SHA}^{commit}")"' in run
    assert "space_url" in run and ".space_url" in run


def test_inline_python_compiles_on_this_interpreter(wf: dict) -> None:
    bodies = [m["body"] for _, _, s in _steps(wf) for m in HEREDOC_RE.finditer(s.get("run", ""))]
    assert len(bodies) == 2  # plan matrix, space_url lookup
    for body in bodies:
        compile(body, "<deploy-spaces.yml>", "exec")


def test_every_run_block_fails_fast(wf: dict) -> None:
    for job, i, step in _steps(wf):
        if "run" in step:
            assert step["run"].startswith("set -euo pipefail\n"), f"{job} step {i}"


# --- gates in the test job -------------------------------------------------------------------


def test_test_job_runs_the_documented_gates(wf: dict) -> None:
    runs = "\n".join(s.get("run", "") for s in wf["jobs"]["test"]["steps"])
    scope = "apps/spaces/_shared apps/spaces/tools tests/spaces"
    assert f"ruff check {scope}" in runs and f"ruff format --check {scope}" in runs
    # --confcutdir: the root tests/conftest.py needs the API server's dependencies, which the
    # test job does not install; the fleet tests use tests/spaces/conftest.py only.
    assert "python -m pytest tests/spaces -q -p no:cacheprovider --confcutdir=tests/spaces" in runs
    assert "copy_lint.py apps/spaces/_shared" in runs
    # the redirect stubs left the fleet on 2026-09-23: no stub directory is linted or ruffed
    assert load_manifest().redirects == [] and "_redirects" not in runs
    assert "pyyaml" in runs  # so this file's tests run in CI rather than skip


def test_pin_drift_is_report_only_because_it_fails_today() -> None:
    """The `|| echo ::warning` is justified only while pin_drift really exits non-zero.

    When the app directories are pinned exactly (M2) this test fails, and the step loses its
    fallback and becomes blocking.
    """
    step_run = next(
        s["run"]
        for _, _, s in _steps(yaml.safe_load(WORKFLOW.read_text()), "test")
        if "pin_drift.py" in s.get("run", "")
    )
    assert '|| echo "::warning' in step_run and "M2" in step_run
    # the directories the step really scans, read off its own command line
    command = next(line for line in step_run.splitlines() if "pin_drift.py" in line)
    args = shlex.split(command.rstrip(" \\"))
    app_dirs = [a for a in args if a.startswith("apps/spaces/") and not a.endswith(".py")]
    assert f"apps/spaces/{load_manifest().space('algenta').source}" in app_dirs, command
    assert all((REPO_ROOT / d).is_dir() for d in app_dirs), app_dirs
    proc = subprocess.run(
        [sys.executable, str(TOOLS / "pin_drift.py"), *app_dirs],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 1, "pin_drift is clean: make the workflow step blocking"
    assert "finding(s)" in proc.stdout


# --- copy canon ------------------------------------------------------------------------------


def test_workflow_copy_follows_the_canon(raw: str) -> None:
    assert "decision engine" not in raw.lower()
    assert EMAIL_RE.search(raw) is None
    assert FAKE_WORDS.search(raw) is None, FAKE_WORDS.search(raw)


def test_readme_documents_deploying_from_ci() -> None:
    text = README.read_text(encoding="utf-8")
    section = text.split("## Deploying from CI", 1)
    assert len(section) == 2, "docs/spaces/README.md lacks the `Deploying from CI` section"
    body = section[1].split("\n## ", 1)[0]
    for needle in (
        "deploy-spaces.yml",
        ENVIRONMENT,
        "dry_run",
        "rollback_sha",
        "workflow_dispatch",
        "gh api",
        "task=deploy:",
    ):
        assert needle in body, needle
    assert "never rolls back on its own" in body
    assert "decision engine" not in text.lower()
    assert EMAIL_RE.search(text) is None
