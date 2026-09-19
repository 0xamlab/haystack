"""scripts/bump_sdk_version.py: the nine D2-lockstep version fields move together or not at all."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))
import bump_sdk_version as bump  # noqa: E402

# What the release chain reads BACK after the bump, parsed the way it parses it (tomllib / json /
# the guard's own regexes) and never through bump.LOCKSTEP's patterns -- so a field the script
# forgets fails here the way it failed live: run 35463050651 bumped 1.0.14 -> 1.0.15 and the
# lockstep guard (tests/test_sdk_package_metadata.py) then rejected _FALLBACK_VERSION 1.0.14,
# which was not in the table. Keys are "<file>" or "<file>#<field>" for multi-field files.
_GUARD_FALLBACK_RE = re.compile(r'_FALLBACK_VERSION: Final\[str\] = "([^"]+)"')  # the guard's regex
_GUARD_INIT_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)  # the guard's regex


def _release_chain_reads(root: Path) -> dict[str, str]:
    def toml_version(rel: str) -> str:
        return tomllib.loads((root / rel).read_text(encoding="utf-8"))["project"]["version"]

    def load_json(rel: str) -> dict:
        return json.loads((root / rel).read_text(encoding="utf-8"))

    def search(rel: str, pattern: re.Pattern[str]) -> str:
        match = pattern.search((root / rel).read_text(encoding="utf-8"))
        assert match, f"{rel}: {pattern.pattern!r} not found"
        return match.group(1)

    lock = load_json("packages/ts-sdk/package-lock.json")
    manifest = load_json("server.json")
    return {
        "packages/python-sdk/pyproject.toml": toml_version("packages/python-sdk/pyproject.toml"),
        "packages/python-sdk/decision_engine/__init__.py": search(
            "packages/python-sdk/decision_engine/__init__.py", _GUARD_INIT_RE),
        "packages/algenta/pyproject.toml": toml_version("packages/algenta/pyproject.toml"),
        "packages/algenta/algenta/__init__.py": search("packages/algenta/algenta/__init__.py", _GUARD_INIT_RE),
        "packages/mcp/pyproject.toml": toml_version("packages/mcp/pyproject.toml"),
        "packages/mcp/algenta_mcp/config.py": search("packages/mcp/algenta_mcp/config.py", _GUARD_FALLBACK_RE),
        "packages/ts-sdk/package.json": load_json("packages/ts-sdk/package.json")["version"],
        "packages/ts-sdk/package-lock.json#version": lock["version"],
        'packages/ts-sdk/package-lock.json#packages[""].version': lock["packages"][""]["version"],
        "server.json#version": manifest["version"],
        "server.json#packages[0].version": manifest["packages"][0]["version"],
    }


# The files above, derived from the reader itself (evaluated once on the real tree) so this list
# and the reader cannot drift apart.
_RELEASE_CHAIN_FILES = tuple(dict.fromkeys(key.split("#", 1)[0] for key in _release_chain_reads(_ROOT)))


def _copy_lockstep_tree(tmp_path: Path) -> Path:
    for rel in sorted({*bump.LOCKSTEP_FILES, *_RELEASE_CHAIN_FILES}):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(_ROOT / rel, dst)
    return tmp_path


def _versions(root: Path) -> set[str]:
    found = set()
    for rel, patterns in bump.LOCKSTEP:
        text = (root / rel).read_text(encoding="utf-8")
        for pat in patterns:
            found.update(re.findall(pat, text))
    return found


def test_repo_tree_is_in_lockstep_and_patch_bump_moves_every_field(tmp_path):
    root = _copy_lockstep_tree(tmp_path)
    old = bump.current_version(root)
    assert _versions(root) == {old}, "the checked-in tree must already be in lockstep"
    assert bump.main(["--root", str(root), "--level", "patch"]) == 0
    new = bump.next_version(old, "patch")
    assert _versions(root) == {new}
    # the repo itself is untouched
    assert bump.current_version(_ROOT) == old


@pytest.mark.parametrize("level,expected", [("patch", "1.2.4"), ("minor", "1.3.0"), ("major", "2.0.0")])
def test_next_version_levels(level, expected):
    assert bump.next_version("1.2.3", level) == expected


def test_explicit_target_and_dry_run_write_nothing(tmp_path):
    root = _copy_lockstep_tree(tmp_path)
    old = bump.current_version(root)
    assert bump.main(["--root", str(root), "--to", "9.9.9", "--dry-run"]) == 0
    assert _versions(root) == {old}


def test_half_bumped_tree_is_refused_and_untouched(tmp_path):
    root = _copy_lockstep_tree(tmp_path)
    old = bump.current_version(root)
    drift = root / "packages/mcp/pyproject.toml"
    drift.write_text(drift.read_text(encoding="utf-8").replace(f'version = "{old}"', 'version = "0.0.1"'), encoding="utf-8")
    with pytest.raises(SystemExit, match="lockstep check failed"):
        bump.main(["--root", str(root), "--level", "patch"])
    assert (root / "packages/python-sdk/pyproject.toml").read_text(encoding="utf-8").count(f'version = "{old}"') == 1


def test_bump_moves_every_field_the_release_chain_reads_back(tmp_path):
    root = _copy_lockstep_tree(tmp_path)
    old = bump.current_version(root)
    assert set(_release_chain_reads(root).values()) == {old}, "the checked-in tree must already be in lockstep"
    assert bump.main(["--root", str(root), "--level", "patch"]) == 0
    new = bump.next_version(old, "patch")
    stale = {field: version for field, version in _release_chain_reads(root).items() if version != new}
    assert not stale, f"the bump left fields the release guard reads at the old version: {stale}"
    # The two tables can only grow together: a file added to one and not the other fails here.
    assert set(_RELEASE_CHAIN_FILES) == set(bump.LOCKSTEP_FILES)


def test_workflow_stages_exactly_the_lockstep_files():
    """The script writes the files; the workflow's `git add -A -- ...` must list every one of them
    (and nothing else), or the bump commit pushed to main is itself half-bumped."""
    workflow = (_ROOT / ".github/workflows/sdk-auto-bump.yml").read_text(encoding="utf-8")
    match = re.search(r"git add -A -- ((?:[^\n\\]*\\\n)*[^\n]*)", workflow)
    assert match, "sdk-auto-bump.yml: no `git add -A -- ...` line"
    staged = set(match.group(1).replace("\\\n", " ").split())
    assert staged == set(bump.LOCKSTEP_FILES), {
        "script writes but workflow does not stage": sorted(set(bump.LOCKSTEP_FILES) - staged),
        "workflow stages but script does not write": sorted(staged - set(bump.LOCKSTEP_FILES)),
    }


def test_cli_json_output(tmp_path):
    root = _copy_lockstep_tree(tmp_path)
    out = subprocess.run([sys.executable, str(_ROOT / "scripts/bump_sdk_version.py"), "--root", str(root),
                          "--level", "minor", "--json"], check=True, capture_output=True, text=True).stdout
    data = json.loads(out)
    assert data["new"] == bump.next_version(data["old"], "minor") and len(data["files"]) == len(bump.LOCKSTEP_FILES)



def test_plan_replaces_only_the_captured_version_even_when_the_match_contains_it_elsewhere(tmp_path):
    """Codna review of #1037: the lockfile pattern spans the root block; a `name` carrying the same
    digits must survive, and only the captured version field may change."""
    root = _copy_lockstep_tree(tmp_path)
    old = bump.current_version(root)
    lock = root / "packages/ts-sdk/package-lock.json"
    text = lock.read_text(encoding="utf-8")
    text = text.replace('    "": {\n      "name": "algenta-sdk",', f'    "": {{\n      "name": "algenta-sdk-{old}",', 1)
    lock.write_text(text, encoding="utf-8")
    new = bump.next_version(old, "patch")
    changes = bump.plan(root, old, new)
    updated = changes[lock]
    assert f'"name": "algenta-sdk-{old}"' in updated          # the look-alike field is untouched
    assert f'      "version": "{new}",' in updated              # the captured field moved
    assert updated.count(old) == text.count(old) - 2           # the two version fields, nothing else
