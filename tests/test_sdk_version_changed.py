"""scripts/sdk_version_changed.py: a hand bump is a push that MOVED `version`, not one that touched a manifest.

sdk-auto-bump.yml used to classify by file name, so #1089 (only `description` changed) and #1100
(only `[tool.ruff] target-version` changed) were both treated as hand bumps and never released.
These fixtures replay both shapes, the bot's own release commit and a version-only edit against
the classifier, then run the workflow's real `plan` shell against the same repositories so the
wiring (base fallback, exit-code cases, guard order) is tested and not just the Python.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bump_sdk_version as bump
import sdk_version_changed as svc

_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = _ROOT / ".github/workflows/sdk-auto-bump.yml"
_GIT_IDENTITY = (
    "-c",
    "user.name=t",
    "-c",
    "user.email=t@example.invalid",
    "-c",
    "commit.gpgsign=false",
)
_ZERO_SHA = "0" * 40


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *_GIT_IDENTITY, *args], check=True, capture_output=True, text=True
    )
    return proc.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _edit(repo: Path, rel: str, pattern: str, replacement: str) -> None:
    path = repo / rel
    text = path.read_text(encoding="utf-8")
    assert len(re.findall(pattern, text, re.MULTILINE)) == 1, (
        f"{rel}: {pattern!r} must match exactly once"
    )
    path.write_text(re.sub(pattern, replacement, text, flags=re.MULTILINE), encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repository holding the checked-in manifests (one commit, tagged at their version)."""
    for rel in svc.MANIFESTS:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(_ROOT / rel, dst)
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "base")
    _git(tmp_path, "tag", f"sdk-v{bump.current_version(tmp_path)}")
    return tmp_path


def _classify(repo: Path, base: str = "HEAD~1", head: str = "HEAD") -> int:
    return svc.main([base, head, "--repo", str(repo)])


# --- the classifier -----------------------------------------------------------------------------


def test_description_only_edit_is_not_a_hand_bump(repo: Path):
    """The #1089 shape: every public manifest changed, no version moved."""
    _edit(
        repo,
        "packages/python-sdk/pyproject.toml",
        r'^description = ".*"$',
        'description = "new words"',
    )
    _edit(repo, "packages/mcp/pyproject.toml", r'^description = ".*"$', 'description = "new words"')
    _edit(
        repo,
        "packages/ts-sdk/package.json",
        r'^  "description": ".*",$',
        '  "description": "new words",',
    )
    _commit(repo, "docs: reword the package descriptions")
    assert svc.changed_versions(repo, "HEAD~1", "HEAD") == {}
    assert _classify(repo) == svc.EXIT_UNCHANGED


def test_tool_config_edit_is_not_a_hand_bump(repo: Path):
    """The #1100 shape: only `[tool.ruff] target-version` moved."""
    _edit(
        repo,
        "packages/python-sdk/pyproject.toml",
        r'^target-version = "py\d+"$',
        'target-version = "py399"',
    )
    _commit(repo, "refactor: lint at a newer target")
    assert _classify(repo) == svc.EXIT_UNCHANGED


@pytest.mark.parametrize(
    "rel,pattern,replacement",
    [
        ("packages/python-sdk/pyproject.toml", r'^version = "(.*)"$', 'version = "9.9.9"'),
        ("packages/mcp/pyproject.toml", r'^version = "(.*)"$', 'version = "9.9.9"'),
        ("packages/ts-sdk/package.json", r'^  "version": "(.*)",$', '  "version": "9.9.9",'),
    ],
)
def test_a_moved_version_in_any_one_manifest_is_a_hand_bump(
    repo: Path, rel: str, pattern: str, replacement: str, capsys
):
    old = bump.current_version(repo)
    _edit(repo, rel, pattern, replacement)
    _commit(repo, "bump one manifest by hand")
    assert svc.changed_versions(repo, "HEAD~1", "HEAD") == {rel: (old, "9.9.9")}
    assert _classify(repo) == svc.EXIT_CHANGED
    assert capsys.readouterr().out.strip() == f"{rel}: {old} -> 9.9.9"


def test_the_release_commit_shape_moves_every_manifest(repo: Path):
    old = bump.current_version(repo)
    for rel in svc.MANIFESTS:
        if rel.endswith(".toml"):
            _edit(repo, rel, r'^version = "(.*)"$', 'version = "9.9.9"')
        else:
            _edit(repo, rel, r'^  "version": "(.*)",$', '  "version": "9.9.9",')
    _commit(repo, "chore(release): SDK 9.9.9")
    assert svc.changed_versions(repo, "HEAD~1", "HEAD") == dict.fromkeys(
        svc.MANIFESTS, (old, "9.9.9")
    )


def test_a_manifest_added_by_the_push_counts_as_changed(repo: Path):
    """Absent at base, present at head: the conservative side (the old file-name test said hand bump too)."""
    rel = "packages/ts-sdk/package.json"
    (repo / rel).unlink()
    _commit(repo, "drop package.json")
    shutil.copy(_ROOT / rel, repo / rel)
    _commit(repo, "restore package.json")
    assert svc.changed_versions(repo, "HEAD~1", "HEAD") == {rel: (None, bump.current_version(repo))}
    assert _classify(repo) == svc.EXIT_CHANGED


def test_an_unresolvable_revision_is_an_error_not_a_verdict(repo: Path, capsys):
    """github.event.before can be all zeros; the classifier must refuse, and the workflow falls back."""
    assert _classify(repo, base=_ZERO_SHA) == svc.EXIT_ERROR
    assert f"{_ZERO_SHA}: not a commit" in capsys.readouterr().err
    with pytest.raises(svc.CompareError, match=f"{_ZERO_SHA}: not a commit"):
        svc.changed_versions(repo, _ZERO_SHA, "HEAD")


def test_a_manifest_that_is_not_utf8_is_exit_2(repo: Path, capsys):
    """A blob the release chain could not read as UTF-8 is a CompareError from blob_at itself,
    not a UnicodeDecodeError left for main()'s catch-all (or for a direct caller) to meet."""
    rel = "packages/python-sdk/pyproject.toml"
    raw = (repo / rel).read_bytes()
    assert raw.count(b'description = "') == 1
    # 0xE9 is a Latin-1 "e-acute" and, followed by ASCII, never valid UTF-8.
    (repo / rel).write_bytes(raw.replace(b'description = "', b'description = "\xe9', 1))
    _commit(repo, "commit a manifest with a latin-1 byte")
    assert _classify(repo) == svc.EXIT_ERROR
    assert "not UTF-8" in capsys.readouterr().err
    with pytest.raises(svc.CompareError, match=f"HEAD:{rel}: not UTF-8"):
        svc.changed_versions(repo, "HEAD~1", "HEAD")


@pytest.mark.parametrize(
    "rel,text",
    [
        ("packages/mcp/pyproject.toml", "this is not toml = ["),
        ("packages/mcp/pyproject.toml", '[project]\nname = "algenta-mcp"\n'),  # parses; no version
        ("packages/ts-sdk/package.json", "{not json"),
        ("packages/ts-sdk/package.json", '{"name": "algenta-sdk"}'),  # parses; no version
    ],
)
def test_an_unreadable_manifest_is_exit_2_never_exit_1(repo: Path, rel: str, text: str, capsys):
    """Exit 1 means "unchanged -> bump" to the workflow, so a parse failure must never surface as 1
    (an uncaught exception would). Both the malformed and the version-less shapes are exit 2."""
    (repo / rel).write_text(text, encoding="utf-8")
    _commit(repo, "break a manifest")
    assert _classify(repo) == svc.EXIT_ERROR
    assert rel in capsys.readouterr().err
    with pytest.raises(svc.CompareError, match="cannot read version"):
        svc.changed_versions(repo, "HEAD~1", "HEAD")


def test_a_git_failure_that_is_not_absence_is_exit_2(repo: Path, capsys):
    """Only `git ls-tree` listing nothing means "absent"; an unreadable object is an error."""
    rel = "packages/ts-sdk/package.json"
    _edit(repo, rel, r'^  "version": "(.*)",$', '  "version": "9.9.9",')
    _commit(repo, "bump one manifest by hand")
    blob = _git(repo, "rev-parse", f"HEAD:{rel}")
    (repo / ".git/objects" / blob[:2] / blob[2:]).unlink()  # a fresh repo stores it loose
    assert _classify(repo) == svc.EXIT_ERROR
    err = capsys.readouterr().err
    assert "git show" in err and rel in err, err
    with pytest.raises(svc.CompareError, match="git show"):
        svc.changed_versions(repo, "HEAD~1", "HEAD")


def test_an_unforeseen_exception_is_exit_2_never_exit_1(repo: Path, monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated")

    monkeypatch.setattr(svc, "changed_versions", boom)
    assert _classify(repo) == svc.EXIT_ERROR
    assert "unexpected RuntimeError: simulated" in capsys.readouterr().err


def test_manifests_are_the_lockstep_version_manifests():
    """The classifier reads exactly the pyproject/package.json files the bump script moves."""
    lockstep_manifests = {
        f for f in bump.LOCKSTEP_FILES if f.endswith(("pyproject.toml", "package.json"))
    }
    assert set(svc.MANIFESTS) == lockstep_manifests


# --- the workflow's `plan` step, run for real -----------------------------------------------------


def _plan_shell() -> str:
    """The `run:` block of the 'Decide whether (and how far) to bump' step, dedented."""
    text = _WORKFLOW.read_text(encoding="utf-8")
    match = re.search(
        r"- name: Decide whether \(and how far\) to bump\n.*?run: \|\n(.*?)\n      - name:",
        text,
        re.DOTALL,
    )
    assert match, "sdk-auto-bump.yml: the plan step's run block was not found"
    lines = match.group(1).splitlines()
    indent = min(len(line) - len(line.lstrip()) for line in lines if line.strip())
    return "\n".join(line[indent:] for line in lines)


def _run_plan(
    repo: Path, tmp_path: Path, *, before: str, after: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    """Execute the step's shell in `repo` the way the runner does: env from the workflow, a stub `gh`."""
    scripts = repo / "scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copy(_ROOT / "scripts/sdk_version_changed.py", scripts / "sdk_version_changed.py")
    stub_bin = tmp_path / "stub-bin"
    stub_bin.mkdir(exist_ok=True)
    (stub_bin / "gh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (stub_bin / "gh").chmod(0o755)
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{stub_bin}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "GH_TOKEN": "stub",
        "GITHUB_REPOSITORY": "thyn-ai/algenta",
        "GITHUB_OUTPUT": str(output),
        "EVENT": "push",
        "LEVEL_INPUT": "",
        "BEFORE": before,
        "AFTER": after,
    }
    proc = subprocess.run(
        ["bash", "-c", _plan_shell()],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    outputs = dict(
        line.split("=", 1)
        for line in output.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    return proc, outputs


def test_plan_bumps_after_a_description_only_push(repo: Path, tmp_path: Path):
    """#1089 replayed against the real shell: mode=bump, not the hand-bump noop."""
    before = _git(repo, "rev-parse", "HEAD")
    _edit(
        repo,
        "packages/python-sdk/pyproject.toml",
        r'^description = ".*"$',
        'description = "new words"',
    )
    after = _commit(repo, "docs: reword the description (#1089)")
    proc, outputs = _run_plan(repo, tmp_path, before=before, after=after)
    assert proc.returncode == 0, proc.stderr
    assert outputs["mode"] == "bump" and outputs["level"] == "patch", (proc.stdout, outputs)
    assert "hand bump" not in proc.stdout


def test_plan_falls_back_to_the_parent_when_before_is_all_zeros(repo: Path, tmp_path: Path):
    _edit(
        repo,
        "packages/python-sdk/pyproject.toml",
        r'^target-version = "py\d+"$',
        'target-version = "py399"',
    )
    after = _commit(repo, "refactor: lint at a newer target (#1100)")
    proc, outputs = _run_plan(repo, tmp_path, before=_ZERO_SHA, after=after)
    assert proc.returncode == 0, proc.stderr
    assert outputs["mode"] == "bump", (proc.stdout, outputs)


def test_plan_leaves_a_hand_bump_to_auto_tag(repo: Path, tmp_path: Path):
    before = _git(repo, "rev-parse", "HEAD")
    for rel in svc.MANIFESTS:
        if rel.endswith(".toml"):
            _edit(repo, rel, r'^version = "(.*)"$', 'version = "9.9.9"')
        else:
            _edit(repo, rel, r'^  "version": "(.*)",$', '  "version": "9.9.9",')
    after = _commit(repo, "fix: bump by hand")
    proc, outputs = _run_plan(repo, tmp_path, before=before, after=after)
    assert proc.returncode == 0, proc.stderr
    assert outputs["mode"] == "noop" and "a hand bump" in proc.stdout, (proc.stdout, outputs)


def test_plan_recognises_its_own_release_commit_before_classifying(repo: Path, tmp_path: Path):
    """The subject guard stays first: the bot's commit never reaches the classifier (no double bump)."""
    before = _git(repo, "rev-parse", "HEAD")
    _edit(repo, "packages/python-sdk/pyproject.toml", r'^version = "(.*)"$', 'version = "9.9.9"')
    after = _commit(repo, "chore(release): SDK 9.9.9")
    proc, outputs = _run_plan(repo, tmp_path, before=before, after=after)
    assert proc.returncode == 0, proc.stderr
    assert outputs["mode"] == "noop" and "own bump commit" in proc.stdout, (proc.stdout, outputs)


def test_workflow_classifies_by_version_value_and_keeps_every_other_guard():
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "python3 scripts/sdk_version_changed.py" in text
    assert (
        "packages/(python-sdk|algenta|mcp)/pyproject.toml|packages/ts-sdk/package.json" not in text
    ), "the file-name classifier is back: #1089/#1100 would be misclassified again"
    for guard in (
        '"chore(release): SDK "*) noop "HEAD is this workflow\'s own bump commit"',
        "release:none",
        "is not tagged yet",
        "nothing to release",
    ):
        assert guard in text, f"guard removed from sdk-auto-bump.yml: {guard!r}"
