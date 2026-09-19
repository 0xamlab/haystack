"""scripts/bump_sdk_version.py: the eight D2-lockstep version fields move together or not at all."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))
import bump_sdk_version as bump  # noqa: E402


def _copy_lockstep_tree(tmp_path: Path) -> Path:
    for rel in bump.LOCKSTEP_FILES:
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


def test_repo_tree_is_in_lockstep_and_patch_bump_moves_all_eight_fields(tmp_path):
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
