"""A module-filtered dispatch must never be written over the tracked artifact.

`mojo/engine/runtime_library_dispatch_generated.mojo` IS the runtime contract: one `if
function_name == ...` arm per published kernel, ~114k lines. Generating it with `--modules stats`
does not "update" it — it replaces it with the ~350 lines that one module needs and deletes every
other arm.

The failure is silent in the two ways that matter:

* The truncated file still COMPILES. It is valid Mojo, so a build succeeds.
* A module-filtered build still PASSES, because the shard it builds only needs the modules that
  survived. Nothing notices until something calls a kernel whose arm is gone, and then the answer
  is `module_not_registered` for a kernel that is plainly present in the source tree.

MEASURED: a `MOJO_RUNTIME_MODULE_FILTER=stats` build truncated the tracked file from 114,002 lines
to 397 — a would-be 113,843-line deletion. It reached neither a commit nor CI only because an
unrelated test happened to count the file's import bindings.

`scripts/build_mojo_binary.sh` does stage filtered output into a temp directory, but that guard is
nested inside `if [[ "${MOJO_SRC}" == "${DEFAULT_MOJO_SRC}" ]]`, so a caller that sets `MOJO_SRC`
walks straight past it. Guarding each caller is a losing game — there is exactly one place that
writes this path, and a filtered subset can never be correct there whatever route the caller took.
So the check lives at the sink, and these assertions pin it there.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GENERATOR = _REPO_ROOT / "scripts" / "generate_runtime_library_dispatch.py"
_TRACKED = _REPO_ROOT / "mojo" / "engine" / "runtime_library_dispatch_generated.mojo"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_GENERATOR), *args],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )


@pytest.fixture()
def tracked_unchanged():
    """Fail loudly if the assertion under test modified the tracked artifact.

    Reading the bytes rather than trusting the exit code: a guard that refuses AND writes would
    still exit non-zero, and the whole point is the file on disk.
    """
    assert _TRACKED.is_file(), "tracked dispatch missing"
    before = _TRACKED.read_bytes()
    yield
    assert _TRACKED.read_bytes() == before, (
        "the tracked dispatch was modified by a test that must not touch it"
    )


def test_a_filtered_write_to_the_tracked_artifact_is_refused(tracked_unchanged):
    """THE REGRESSION. This is the exact shape that deleted 113,843 lines."""
    result = _run("--modules", "stats")
    assert result.returncode != 0, (
        "a filtered generation over the tracked artifact must fail, not succeed quietly; "
        f"stdout={result.stdout!r}"
    )
    combined = result.stdout + result.stderr
    assert "refusing to write a module-FILTERED dispatch" in combined, combined
    # The message has to name the way out, or the next person just deletes the guard.
    assert "--output" in combined, "the refusal must say how to generate filtered output"


def test_the_refusal_names_the_modules_and_the_path(tracked_unchanged):
    """A refusal that does not say what it refused gets debugged by trial and error."""
    result = _run("--modules", "stats", "sorting")
    combined = result.stdout + result.stderr
    assert "stats" in combined and "sorting" in combined, combined
    assert "runtime_library_dispatch_generated.mojo" in combined, combined


def test_a_filtered_write_to_an_explicit_output_still_works(tmp_path, tracked_unchanged):
    """The guard must not break the legitimate use, which is how shards are built."""
    out = tmp_path / "filtered.mojo"
    result = _run("--modules", "stats", "--output", str(out))
    assert result.returncode == 0, result.stdout + result.stderr
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert 'if function_name == "compute_mean"' in text, "the filtered dispatch lost its module"
    # Small BY DESIGN -- that is the whole reason it must not land on the tracked path.
    assert len(text.splitlines()) < 5000, "a one-module dispatch should be tiny"


def test_an_unfiltered_write_to_an_explicit_output_is_the_full_table(tmp_path):
    """The guard keys on the FILTER, not on the path, so unfiltered output is unaffected.

    Written to a temp path rather than the tracked one so this suite never regenerates a
    committed artifact from whatever state the working tree happens to be in.
    """
    out = tmp_path / "full.mojo"
    result = _run("--output", str(out))
    assert result.returncode == 0, result.stdout + result.stderr
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 90_000, (
        f"an unfiltered dispatch should be the whole contract, got {len(lines)} lines"
    )


def test_the_build_script_redirects_a_filtered_dispatch_away_from_the_tracked_path():
    """The caller-side fix, so a filtered build WORKS rather than hitting the sink guard.

    Two layers on purpose. The generator refuses the combination outright, which makes silent
    truncation impossible. This redirect is what keeps the legitimate case pleasant: a filtered
    build is how a single shard compiles in seconds instead of building the monolith, so it should
    succeed, not fail with a lecture.

    Pinned as text because there is nothing else to assert against without running a full Mojo
    build. If the redirect is deleted, filtered builds start failing loudly on the sink guard --
    a usability regression rather than a correctness one, which is exactly the trade this test
    documents.
    """
    script = (_REPO_ROOT / "scripts" / "build_mojo_binary.sh").read_text(encoding="utf-8")
    assert "MOJO_RUNTIME_MODULE_FILTER_RAW" in script
    assert 'DISPATCH_OUTPUT_PATH="${BUILD_DIR}/runtime_library_dispatch_generated.mojo"' in script, (
        "build_mojo_binary.sh no longer redirects a module-filtered dispatch into BUILD_DIR, so a "
        "filtered build would ask the generator to overwrite the tracked artifact"
    )
    # The redirect must be conditional on the filter, or every build stops updating the artifact.
    assert 'if [[ -n "${MOJO_RUNTIME_MODULE_FILTER_RAW}"' in script
