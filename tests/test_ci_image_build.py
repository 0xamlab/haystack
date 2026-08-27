"""The image rebuild must derive everything, and must never register the builder as a runner.

`galleries/thynci/images/ci-worker/versions/1.0.0` had no source in this repository at all. That
is why five tools reached production missing in one night: with no way to rebuild, every gap gets
patched at boot instead of fixed once, and manifest.toml's rebuild_required could never go false.

Two properties are load-bearing here, and both would fail silently:

  * DERIVED, never restated. If this script carried its own package list, it would be a second
    description of one machine, drifting from CLOUD_INIT exactly the way the frozen image already
    drifted. Restating is the bug, not a shortcut.
  * The builder must NOT run the runner-registration tail. A builder that registers would claim a
    real job, run it, and be captured mid-job into the image every fleet VM then boots from.
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "infra" / "ci" / "image" / "build_image.py"
_MANIFEST = _ROOT / "infra" / "ci" / "image" / "manifest.toml"


def _load():
    spec = importlib.util.spec_from_file_location("ci_build_image", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["ci_build_image"] = module
    spec.loader.exec_module(module)
    return module


build = _load()


def test_the_builder_never_registers_itself_as_a_runner() -> None:
    """The property with the worst failure mode if it breaks.

    A builder that runs config.sh registers as a live az-ephemeral runner, is handed a real job,
    and gets captured mid-job into the image that every fleet VM subsequently boots from.
    """
    body = build.extract_cloud_init()
    for forbidden in ("config.sh --url", "run.sh", "shutdown -h now"):
        assert forbidden not in body, (
            f"the builder bootstrap still contains {forbidden!r}; it would register as a runner "
            "and be captured mid-job"
        )


def test_it_builds_from_the_full_bootstrap_not_the_fast_path() -> None:
    """CLOUD_INIT_FAST is what runs ON a golden image.

    Building an image from it would bake in nothing and repair everything at boot, forever --
    which is the state this script exists to end.
    """
    body = build.extract_cloud_init()
    assert "apt-get install" in body, "the full bootstrap installs packages; this body does not"
    # the fast path's giveaway is the per-boot repair, which must not be what we build from
    assert "ci-image-repair-done" not in body


def test_the_tier0_list_is_read_from_the_manifest() -> None:
    """Derived, not restated -- a second list would drift from the first."""
    declared = sorted(tomllib.loads(_MANIFEST.read_text("utf-8"))["tier0"])
    assert build.required_binaries() == declared
    assert "gh" in declared, "gh is the tool whose absence took down a release"


def test_the_regions_are_read_from_the_orchestrator() -> None:
    """The image must replicate to exactly the regions the fleet provisions into.

    A region the orchestrator uses but the image does not reach falls back to the full bootstrap
    on every boot -- the 3-6 minute penalty the gallery version was introduced to remove.
    """
    orchestrator = (_ROOT / "infra" / "ci" / "az_orchestrator.py").read_text("utf-8")
    regions = build._fleet_regions()  # noqa: SLF001
    assert len(regions) >= 8, regions
    for region in regions:
        assert f'"{region}"' in orchestrator


def test_the_script_source_does_not_restate_the_package_list() -> None:
    """A guard against the exact regression that would make this file useless.

    If someone adds `apt-get install -y foo` here instead of to CLOUD_INIT, the image and the
    bootstrap start describing different machines again.
    """
    source = _SCRIPT.read_text("utf-8")
    executable = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    assert "apt-get install" not in executable, (
        "build_image.py installs packages of its own. It must extract CLOUD_INIT instead -- two "
        "descriptions of one machine is the drift this whole contract exists to stop."
    )


def test_it_refuses_to_republish_the_version_already_recorded() -> None:
    """Overwriting a live gallery version in place is not something to do by accident."""
    published = tomllib.loads(_MANIFEST.read_text("utf-8"))["image"]["gallery_version"]
    with pytest.raises(SystemExit) as excinfo:
        build.main(["--version", published])
    assert "already recorded as published" in str(excinfo.value)


def test_nothing_executes_without_apply(capsys) -> None:
    """Dry-run is the default because this provisions billable infrastructure and publishes an
    artifact the whole fleet then boots from."""
    assert build.main(["--version", "9.9.9"]) == 0
    printed = capsys.readouterr().out
    assert "DRY-RUN" in printed
    assert "az vm create" in printed
    assert "--apply to execute" in printed
