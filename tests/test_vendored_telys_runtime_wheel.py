"""The vendored Telys runtime wheel must exist, be the pinned build, and be installed
into the engine image.

Why this file exists, and why none of it is skippable.

`tests/test_repository_intelligence_lexical.py` proves the code-lexical lane ranks
correctly — but its positive case is guarded by
`skipif(importlib.util.find_spec("memengine") is None)`. On a developer machine or a CI
runner where `memengine` happens to be installed, that test PASSES; where it is not, it
SKIPS. Either way it says nothing about the engine image.

That is exactly how the lane silently stopped working. PR #394 vendored the wheel and
added the install step to `Dockerfile.engine.prod`; PR #395 reverted both. Every test
stayed green, because the only thing that had changed was the *image*, and nothing
asserted anything about the image. The lane then returned `[]` forever — it is
deliberately fail-open, so there was no error either.

The assertions below check the artifact and the Dockerfile directly, so they fail on a
revert rather than skipping past it.

`telys-runtime` cannot come from PyPI: the `telys` distribution publishes
`telys-runtime; extra == "runtime"`, but `telys-runtime` itself has never been uploaded
(pypi.org/pypi/telys-runtime/json is a 404), so `pip install telys[runtime]` does not
resolve. The unrelated `memengine` 1.1.0 on PyPI is a langchain/torch package and is NOT
this one. A committed wheel is therefore the only credential-free, reproducible source,
which is what #394 concluded.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

WHEEL_NAME = "telys_runtime-0.1.0a1-py3-none-any.whl"
WHEEL_PATH = _REPO_ROOT / "vendor" / "wheels" / WHEEL_NAME
ENGINE_DOCKERFILE = _REPO_ROOT / "infra" / "docker" / "Dockerfile.engine.prod"

# Recorded in PR #394's message: built from telys 38ad036, which carries telys PR #87
# (memengine.lexical). Pinning the digest is what makes "the vendored wheel" a specific
# artifact rather than whatever happens to sit at that path.
EXPECTED_SHA256 = "9adb6850d24f834d635ab3f7d609dafeeffd543e9a142fe03063636780fc6af8"


def test_the_vendored_wheel_is_present() -> None:
    assert WHEEL_PATH.is_file(), (
        f"{WHEEL_PATH.relative_to(_REPO_ROOT)} is missing. The code-lexical triage lane "
        "imports memengine.lexical and is fail-open, so removing this wheel makes the "
        "lane silently return [] in the engine image with no test failure anywhere else."
    )


def test_the_wheel_is_the_pinned_build() -> None:
    """A digest, not just a filename — otherwise 'the wheel is there' proves nothing."""
    digest = hashlib.sha256(WHEEL_PATH.read_bytes()).hexdigest()
    assert digest == EXPECTED_SHA256, (
        f"vendored wheel digest is {digest}, expected {EXPECTED_SHA256}. If the wheel was "
        "deliberately rebuilt from newer telys source, update EXPECTED_SHA256 in this "
        "file and say which telys commit it came from in the commit message."
    )


def test_the_wheel_actually_contains_the_lexical_module() -> None:
    """The lane imports `memengine.lexical`, so that file has to be inside.

    A wheel built from telys before PR #87 installs cleanly and imports `memengine`
    fine — it just has no `.lexical`, which is the precise shape of the original bug this
    vendoring was for.
    """
    with zipfile.ZipFile(WHEEL_PATH) as archive:
        names = set(archive.namelist())
    assert "memengine/lexical.py" in names, (
        "the vendored wheel has no memengine/lexical.py — it predates telys PR #87 and "
        f"cannot serve the lane. Contents: {sorted(n for n in names if n.endswith('.py'))}"
    )
    assert "memengine/__init__.py" in names


def test_the_lexical_module_defines_the_class_the_lane_calls() -> None:
    """Read it out of the archive rather than importing, so this holds even where
    `memengine` is not installed in the test environment — which is the whole point."""
    with zipfile.ZipFile(WHEEL_PATH) as archive:
        source = archive.read("memengine/lexical.py").decode("utf-8")
    assert "class LexicalCodeIndex" in source
    # repository_intelligence_lexical.lexical_rank calls exactly these two.
    assert "def build(" in source, "LexicalCodeIndex.build is what the lane calls first"
    assert "def search(" in source, "LexicalCodeIndex.search is what the lane calls next"


def test_the_engine_image_installs_the_wheel() -> None:
    """The artifact being committed is not enough; the image has to pip install it.

    #395 removed both the wheel and these two Dockerfile lines. Asserting the Dockerfile
    is what makes a future revert fail here instead of shipping a broken image.
    """
    dockerfile = ENGINE_DOCKERFILE.read_text(encoding="utf-8")
    assert f"COPY vendor/wheels/{WHEEL_NAME}" in dockerfile, (
        "Dockerfile.engine.prod does not COPY the vendored wheel, so the engine image "
        "cannot import memengine.lexical and the triage lane degrades to a no-op."
    )
    assert f"pip install --no-cache-dir --prefix=/install /tmp/wheels/{WHEEL_NAME}" in dockerfile, (
        "the wheel is copied into the image but never installed"
    )


def test_the_lane_source_still_imports_what_the_wheel_provides() -> None:
    """Guards the other direction: the lane's import path must match the wheel's layout.

    If either side is renamed independently, the lane fails open and returns [] with no
    error — so the two are pinned to each other here.
    """
    lane = (
        _REPO_ROOT / "apps" / "api_server" / "services" / "repository_intelligence_lexical.py"
    ).read_text(encoding="utf-8")
    assert "from memengine.lexical import LexicalCodeIndex" in lane
    assert "LexicalCodeIndex().build(" in lane
