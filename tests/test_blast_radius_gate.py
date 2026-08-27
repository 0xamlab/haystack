"""The blast-radius ratchet's decision logic.

This gate decides whether a PR is blocked, so its own failure modes matter more than most:
a gate that wrongly passes silences the very reds it exists to surface, and one that
wrongly fails blocks people for touching a neighbouring file.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "ci_blast_radius_gate.py"


def _load():
    spec = importlib.util.spec_from_file_location("ci_blast_radius_gate", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["ci_blast_radius_gate"] = module
    spec.loader.exec_module(module)
    return module


gate = _load()


# ── parsing pytest's terse summary ───────────────────────────────────────────
def test_a_parametrised_node_id_containing_spaces_survives_parsing():
    """The reason the parser cuts on ` - ` rather than whitespace: a parametrised id can
    contain spaces, and truncating it would produce a node ID that matches no baseline
    entry -- so a baselined red would read as new and block the PR."""
    out = "FAILED tests/test_x.py::test_y[a b c] - AssertionError: assert 1 == 2\n"
    assert gate.parse_reds(out) == ["tests/test_x.py::test_y[a b c]"]


def test_a_parametrised_node_id_containing_the_message_separator_survives():
    """`[a - b]` is a legal parametrised id (params come from argument reprs). Cutting at
    the FIRST ` - ` would yield `...::test_y[a`, which matches no baseline entry -- so an
    already-accepted red would read as new and block the PR. Brackets disambiguate.
    """
    out = "FAILED tests/test_x.py::test_y[a - b] - AssertionError: nope\n"
    assert gate.parse_reds(out) == ["tests/test_x.py::test_y[a - b]"]


def test_a_message_with_balanced_brackets_does_not_swallow_itself():
    """The mirror case: the cut happens before the message, so `assert [1] == [2]` must
    not be absorbed into the node ID."""
    out = "FAILED tests/test_x.py::test_y[p] - AssertionError: assert [1] == [2]\n"
    assert gate.parse_reds(out) == ["tests/test_x.py::test_y[p]"]


def test_collection_errors_are_captured_not_just_failures():
    """A never-run file's first execution often ERRORs at collection/setup rather than
    failing an assertion; missing those would let the worst case through."""
    out = "ERROR tests/test_x.py\nFAILED tests/test_y.py::test_z - boom\n"
    assert gate.parse_reds(out) == ["tests/test_x.py", "tests/test_y.py::test_z"]


def test_a_node_id_with_no_message_still_parses():
    assert gate.parse_reds("FAILED tests/test_x.py::test_y\n") == ["tests/test_x.py::test_y"]


def test_duplicates_collapse_in_first_seen_order():
    out = "FAILED tests/b.py::t - x\nFAILED tests/a.py::t - y\nFAILED tests/b.py::t - z\n"
    assert gate.parse_reds(out) == ["tests/b.py::t", "tests/a.py::t"]


def test_lines_that_merely_mention_failed_are_not_reds():
    """`FAILED` appears in prose and in progress output; only summary lines count."""
    out = "some test about FAILED states passed\n1 failed, 2 passed\n"
    assert gate.parse_reds(out) == []


# ── baseline matching ────────────────────────────────────────────────────────
def test_a_file_entry_covers_every_red_in_that_file():
    baseline = {"tests/test_x.py"}
    assert gate.is_baselined("tests/test_x.py::test_a", baseline)
    assert gate.is_baselined("tests/test_x.py", baseline)


def test_a_node_entry_does_not_excuse_a_sibling_test():
    """The core ratchet property. If baselining one test silenced the whole file, the
    baseline would stop shrinking and new regressions would hide behind old ones."""
    baseline = {"tests/test_x.py::test_a"}
    assert gate.is_baselined("tests/test_x.py::test_a", baseline)
    assert not gate.is_baselined("tests/test_x.py::test_b", baseline)


def test_comments_and_blank_lines_are_ignored_in_the_baseline():
    text = "# measured on CI, run 123\n\ntests/test_x.py::test_a  # flaky under load\n"
    assert gate.parse_baseline(text) == {"tests/test_x.py::test_a"}


def test_an_absent_baseline_means_every_red_is_new():
    out = "FAILED tests/test_x.py::test_a - boom\n"
    assert gate.new_reds(out, "") == ["tests/test_x.py::test_a"]


# ── the exit contract ────────────────────────────────────────────────────────
def _run(tmp_path: Path, output: str, baseline: str | None) -> int:
    out_file = tmp_path / "pytest.log"
    out_file.write_text(output, encoding="utf-8")
    argv = ["--pytest-output", str(out_file)]
    if baseline is not None:
        base_file = tmp_path / "baseline.txt"
        base_file.write_text(baseline, encoding="utf-8")
        argv += ["--baseline", str(base_file)]
    return gate.main(argv)


def test_exit_zero_when_every_red_is_baselined(tmp_path):
    code = _run(
        tmp_path,
        "FAILED tests/test_x.py::test_a - boom\n",
        "tests/test_x.py::test_a\n",
    )
    assert code == 0


def test_exit_one_when_a_red_is_outside_the_baseline(tmp_path):
    code = _run(
        tmp_path,
        "FAILED tests/test_x.py::test_a - boom\nFAILED tests/test_y.py::test_b - boom\n",
        "tests/test_x.py::test_a\n",
    )
    assert code == 1


def test_exit_zero_on_a_clean_run(tmp_path):
    assert _run(tmp_path, "12 passed in 3.0s\n", "tests/test_x.py::test_a\n") == 0


def test_unreadable_output_fails_closed(tmp_path):
    """If the run's own log cannot be read, nothing has been shown to be fine. Reporting
    success here is exactly the fail-open bug this gate was written after."""
    missing = tmp_path / "nope" / "pytest.log"
    assert gate.main(["--pytest-output", str(missing)]) == 1


def test_the_gate_names_each_new_red_so_the_log_is_actionable(tmp_path, capsys):
    _run(tmp_path, "FAILED tests/test_y.py::test_b - boom\n", "")
    printed = capsys.readouterr().out
    assert "tests/test_y.py::test_b" in printed
    assert "::error::" in printed


# ── the measurement universe ─────────────────────────────────────────────────
def _enumerator():
    spec = importlib.util.spec_from_file_location(
        "ci_never_run_test_files", _ROOT / "scripts" / "ci_never_run_test_files.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_never_run_and_curated_partition_the_selectable_universe():
    """The baseline is measured over `never_run`, and the gate consumes it for files the
    selector reaches. If the two sets did not partition the selectable universe exactly,
    the baseline would either carry dead weight or miss files that can block a PR.

    Counts are derived, never asserted as literals -- a hardcoded total is a line someone
    has to bump every time a test file is added.
    """
    enum = _enumerator()
    selectable = enum.selectable_test_files()
    never_run = set(enum.never_run_test_files())
    curated_selectable = enum.curated_files() & selectable

    assert never_run | curated_selectable == selectable
    assert never_run & curated_selectable == set()


def test_the_measurement_universe_excludes_subdirectories():
    """`test_impact.py` selects only top-level `tests/test_*.py`, so subdirectory suites
    are unreachable by blast radius. Measured 2026-08-26, including them would have added
    18 `tests/integration/test_algenta_client_live.py` failures -- reds that need a live
    stack and that no PR can ever trigger through selection -- to the baseline.
    """
    enum = _enumerator()
    offenders = [f for f in enum.never_run_test_files() if f.count("/") != 1]
    assert not offenders, offenders
    assert all(Path(f).name.startswith("test_") for f in enum.never_run_test_files())


def test_the_selectable_universe_has_not_collapsed():
    """A regression floor, not an exact count. If a refactor moved most tests out of the
    top level the enumerator would silently start measuring almost nothing, and an empty
    baseline reads exactly like a clean one."""
    enum = _enumerator()
    assert len(enum.selectable_test_files()) >= 900


# ── the workflow_dispatch trigger must not be a deploy button ────────────────
def test_no_publishing_job_can_run_on_workflow_dispatch():
    """`workflow_dispatch` was added to ci.yml purely to MEASURE the baseline. Every job
    that builds or ships an artifact must therefore stay gated on a real push; a job
    conditioned on the branch alone would turn a measurement run into a deploy.
    """
    yaml = pytest.importorskip("yaml")
    workflow = yaml.safe_load(
        (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    triggers = workflow[True] if True in workflow else workflow["on"]
    assert "workflow_dispatch" in triggers

    unguarded = [
        name
        for name, job in workflow["jobs"].items()
        if ("deploy" in name or name == "build")
        and "github.event_name == 'push'" not in str(job.get("if", ""))
    ]
    assert not unguarded, f"these jobs could fire on a manual dispatch: {unguarded}"


def test_the_baseline_measurement_is_dispatch_only():
    """It sweeps ~793 files; if it ever ran on a PR it would dominate every PR's runtime."""
    yaml = pytest.importorskip("yaml")
    workflow = yaml.safe_load(
        (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    measuring = [
        s
        for s in workflow["jobs"]["test"]["steps"]
        if "baseline" in (s.get("name") or "").lower()
    ]
    assert measuring, "the measurement step is gone; the ratchet has no way to be fed"
    for step in measuring:
        condition = str(step.get("if", ""))
        assert "workflow_dispatch" in condition, step.get("name")
        assert "measure_baseline" in condition, step.get("name")


# ── the baseline file itself, once it exists, must not rot ───────────────────
def test_every_baselined_path_still_exists():
    """A baseline entry for a deleted or renamed file silently widens the tolerance and
    can never be noticed by the gate itself, which only ever reads reds."""
    baseline_file = _ROOT / "tests" / "blast_radius_known_red.txt"
    if not baseline_file.is_file():
        pytest.skip("no baseline measured yet; the gate runs in advisory mode until then")
    stale = [
        entry
        for entry in sorted(gate.parse_baseline(baseline_file.read_text(encoding="utf-8")))
        if not (_ROOT / entry.split("::", 1)[0]).is_file()
    ]
    assert not stale, f"baseline names paths that no longer exist: {stale}"


def test_wrapped_progress_noise_is_not_mistaken_for_a_red():
    """pytest wraps a long node id and prints the bare status on the next line, so the log
    contains `FAILED                 [  9%]` with no path. The first measured baseline
    swallowed 18 of those as entries. They match no real red, so they can never be removed
    by fixing anything -- the baseline would just carry permanent dead weight."""
    out = (
        "FAILED                                                    [  9%]\n"
        "ERROR                                                     [ 16%]\n"
        "FAILED tests/test_x.py::test_a - boom\n"
    )
    assert gate.parse_reds(out) == ["tests/test_x.py::test_a"]


def test_a_bare_file_path_is_still_a_valid_red():
    """Collection errors have no ::test part; they must survive the path-shape check."""
    assert gate.parse_reds("ERROR tests/test_x.py\n") == ["tests/test_x.py"]
