"""algenta_spaces.facts — computed facts, sha resolution, atomic write and read."""

from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from pathlib import Path

import pytest
from algenta_spaces import facts, runtime

SHA = "3a7398c13a7398c13a7398c13a7398c13a7398c1"


def test_git_sha_prefers_env_then_file_then_dev(tmp_path: Path):
    assert facts.git_sha({"GIT_SHA": SHA.upper()}, tmp_path) == SHA
    assert facts.git_sha({"GITHUB_SHA": SHA}, tmp_path) == SHA
    assert facts.git_sha({"GIT_SHA": "not-a-sha"}, tmp_path) == "dev"
    (tmp_path / ".git_sha").write_text(SHA + "\n")
    assert facts.git_sha({}, tmp_path) == SHA
    assert facts.git_sha({"GIT_SHA": "abc"}, tmp_path) == SHA  # too short: falls to the file


def test_compute_facts_with_a_fake_env(tmp_path: Path):
    (tmp_path / ".shared_sha").write_text("deadbeefcafe\n")
    env = {"SPACE_ID": "thyn-ai/algenta", "SPACE_HARDWARE": "cpu-upgrade", "GIT_SHA": SHA}
    when = datetime(2026, 9, 22, 14, 2, tzinfo=UTC)
    record = facts.compute_facts(["pytest", "no-such-dist-xyz"], env=env, root=tmp_path, now=when)
    assert record["generated_utc"] == "2026-09-22 14:02 UTC"
    assert record["python"] == platform.python_version()
    assert record["implementation"] == platform.python_implementation()
    assert record["platform"] == f"{platform.system()} {platform.machine()}"
    assert record["git_sha"] == SHA
    assert record["shared_sha"] == "deadbeefcafe"
    assert record["space_id"] == "thyn-ai/algenta"
    assert record["space_hardware"] == "cpu-upgrade"
    assert list(record["versions"]) == ["no-such-dist-xyz", "pytest"]
    assert record["versions"]["no-such-dist-xyz"] is None
    assert record["versions"]["pytest"] == pytest.__version__
    json.dumps(record)  # serialisable


def test_compute_facts_defaults_are_dev_and_empty(tmp_path: Path):
    record = facts.compute_facts([], env={}, root=tmp_path)
    assert record["git_sha"] == "dev" and record["shared_sha"] == "dev"
    assert record["space_id"] == "" and record["space_hardware"] == ""
    assert record["versions"] == {}
    assert facts.package_root().name == "_shared"


def test_write_and_read_facts_atomically(tmp_path: Path):
    target = tmp_path / "out" / "facts.json"
    record = {"b": 1, "a": {"z": [1, 2]}}
    assert facts.write_facts(target, record) == target
    text = target.read_text()
    assert text.startswith('{\n  "a": {') and text.endswith("}\n")
    assert not (tmp_path / "out" / "facts.json.tmp").exists()
    assert facts.read_facts(target) == record
    target.write_text("[1, 2]")
    with pytest.raises(ValueError):
        facts.read_facts(target)


def test_runtime_helpers(tmp_path: Path):
    assert runtime.utc_stamp(datetime(2026, 1, 2, 3, 4, tzinfo=UTC)) == "2026-01-02 03:04 UTC"
    assert runtime.utc_stamp().endswith(" UTC")
    assert (
        runtime.is_sha("abcdef1") and not runtime.is_sha("abcdef") and not runtime.is_sha("G" * 8)
    )
    assert runtime.pinned_versions(["pytest"])["pytest"] == pytest.__version__
    assert runtime.read_stamp(tmp_path / "none", default="unknown") == "unknown"
