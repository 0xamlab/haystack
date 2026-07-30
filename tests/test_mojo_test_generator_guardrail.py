"""Guardrail regression tests for tests/generate_mojo_tests.py.

The generator writes ``test_<module_id>.mojo`` for every module in its plan and
unlinks every ``test_*.mojo`` it does not claim. Without protection that erases
the hand-written known-value suites in ``mojo/tests/libs/`` — and it did so
silently, because ``tests/integration/test_mojo_libraries_az.py`` used to invoke
the generator automatically.

These tests pin the protection in place. Counts are derived from the source of
truth with a regression floor, never hardcoded to a number that needs bumping.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "tests"))

import generate_mojo_tests as gen  # noqa: E402

# Regression floor: the 23 hand-written ML suites from the kernel-surface work.
# Adding hand-written suites should raise this; it must never fall.
HANDWRITTEN_FLOOR = 23


def test_handwritten_registry_meets_floor() -> None:
    assert len(gen.HANDWRITTEN_TESTS) >= HANDWRITTEN_FLOOR


def test_registered_handwritten_suites_exist_on_disk() -> None:
    missing = sorted(name for name in gen.HANDWRITTEN_TESTS if not (gen.OUT_DIR / name).is_file())
    assert not missing, f"registered hand-written suites missing from disk: {missing}"


def test_registered_handwritten_suites_are_not_generated() -> None:
    """A registered suite carrying the generated marker means it was clobbered."""
    clobbered = []
    for name in sorted(gen.HANDWRITTEN_TESTS):
        text = (gen.OUT_DIR / name).read_text(encoding="utf-8")
        if gen.GENERATED_MARKER in text[:512]:
            clobbered.append(name)
    assert not clobbered, f"hand-written suites overwritten by the generator: {clobbered}"


def test_every_unmarked_suite_on_disk_is_registered() -> None:
    """The marker scan is a backstop; the registry should still be complete."""
    unregistered = sorted(gen.protected_test_files() - gen.HANDWRITTEN_TESTS)
    assert not unregistered, (
        "hand-written suites found on disk but absent from HANDWRITTEN_TESTS "
        f"(add them): {unregistered}"
    )


def test_generation_plan_excludes_protected_suites() -> None:
    protected = gen.protected_test_files()
    planned = {f"test_{target.module_id}.mojo" for target, _ in gen.build_generation_plan()}
    assert not (planned & protected)


def test_no_module_id_collisions() -> None:
    """Two modules sharing a module_id means one's coverage is silently dropped."""
    collisions = gen._module_id_collisions(gen.discover_library_modules())
    assert not collisions, (
        "module_id collision — add a MODULE_ID_OVERRIDES entry so both modules "
        f"get a suite: {collisions}"
    )


def test_check_mode_passes_on_current_tree() -> None:
    assert gen.check(gen.discover_library_modules()) == 0


def test_full_generator_run_leaves_protected_suites_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The load-bearing test: a real generate() must not touch protected files.

    Runs against a copy of mojo/tests/libs/ so the repo tree is untouched.
    """
    sandbox = tmp_path / "libs"
    shutil.copytree(gen.OUT_DIR, sandbox)
    monkeypatch.setattr(gen, "OUT_DIR", sandbox)

    protected = gen.protected_test_files(sandbox)
    assert len(protected) >= HANDWRITTEN_FLOOR
    before = {name: (sandbox / name).read_bytes() for name in protected}

    gen.generate(gen.discover_library_modules())

    for name, original in before.items():
        path = sandbox / name
        assert path.is_file(), f"generator unlinked protected suite {name}"
        assert path.read_bytes() == original, f"generator rewrote protected suite {name}"


def test_generator_run_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = tmp_path / "libs"
    shutil.copytree(gen.OUT_DIR, sandbox)
    monkeypatch.setattr(gen, "OUT_DIR", sandbox)

    modules = gen.discover_library_modules()
    gen.generate(modules)
    first = {p.name: p.read_bytes() for p in sandbox.glob("test_*.mojo")}
    gen.generate(modules)
    second = {p.name: p.read_bytes() for p in sandbox.glob("test_*.mojo")}

    assert first == second
