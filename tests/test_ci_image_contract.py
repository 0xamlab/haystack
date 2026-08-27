"""The gate that was missing when the runner image and the bootstrap drifted apart.

`infra/ci/image/manifest.toml` declares what an az-ephemeral runner guarantees. Nothing
enforced that declaration against `az_orchestrator.py`, and nothing enforced either against
what workflows actually invoke. The result, measured 2026-08-26/27: three separate tools
(`python`, `unzip`, `rustfmt`) were required by CI and absent from the image, each discovered
by a red PR rather than by a check.

The specific trap these tests encode: the gallery image is a FROZEN capture of CLOUD_INIT.
Golden-image VMs boot through CLOUD_INIT_FAST, which runs zero apt, and that is the normal
path in all 8 regions. So editing CLOUD_INIT feels like fixing the fleet and changes nothing
for a real worker. Only a recapture does.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST = _ROOT / "infra" / "ci" / "image" / "manifest.toml"
_ORCHESTRATOR = _ROOT / "infra" / "ci" / "az_orchestrator.py"


def _manifest() -> dict:
    return tomllib.loads(_MANIFEST.read_text("utf-8"))


def _orchestrator_source() -> str:
    return _ORCHESTRATOR.read_text("utf-8")


def _apt_installed_packages(source: str) -> set[str]:
    """Every package name any `apt-get install` in the bootstrap passes."""
    packages: set[str] = set()
    for match in re.finditer(r"apt-get install -y -qq ([^'\"\n]+)", source):
        for token in match.group(1).split():
            if token.startswith("-"):
                break
            packages.add(token)
    return packages


def test_every_tier0_binary_is_provided_by_a_declared_package() -> None:
    """A tier-0 promise with no package behind it is a promise the image cannot keep."""
    manifest = _manifest()
    provided = {
        binary
        for binaries in manifest["bootstrap_packages"].values()
        for binary in binaries
    }
    missing = sorted(set(manifest["tier0"]) - provided - {"bash", "tar", "gzip"})
    assert not missing, (
        "tier0 declares these binaries but no package in [bootstrap_packages] provides them: "
        f"{missing}. Either map them to a package or drop the guarantee."
    )


def test_the_bootstrap_installs_every_declared_package() -> None:
    """THE DIVERGENCE GATE.

    This is the check whose absence let `unzip` and `rsync` sit undeclared. If the manifest
    promises a package and CLOUD_INIT never installs it, a full-bootstrap VM comes up without
    it and every job that needs it fails somewhere deep and unrelated-looking.
    """
    manifest = _manifest()
    declared = set(manifest["bootstrap_packages"])
    installed = _apt_installed_packages(_orchestrator_source())
    missing = sorted(declared - installed)
    assert not missing, (
        "manifest.toml declares these packages but az_orchestrator.py never apt-installs them: "
        f"{missing}. Add them to the CLOUD_INIT package set."
    )


def test_the_frozen_image_gap_is_declared_not_discovered() -> None:
    """While the captured image lags the contract, per-boot repair MUST be admitted.

    `rebuild_required` is the honest flag. Flipping it to false without recapturing the gallery
    image would assert a guarantee the running fleet does not meet -- which is exactly the
    failure this whole file exists to stop.
    """
    image = _manifest()["image"]
    lagging = image["contract"] != image["gallery_version"]
    assert image["rebuild_required"] is lagging, (
        f"contract={image['contract']} gallery_version={image['gallery_version']} but "
        f"rebuild_required={image['rebuild_required']}. Set rebuild_required=true whenever the "
        "captured image lags the contract, and only false once the image is recaptured."
    )


def test_per_boot_repair_covers_the_fast_path_while_the_image_lags() -> None:
    """A repair that only touches CLOUD_INIT is dead on arrival.

    CLOUD_INIT_FAST is the path a golden-image VM actually takes. Any tool being repaired at
    boot has to appear there too, or it never reaches a real worker -- the mistake made when
    `unzip` was first added.
    """
    manifest = _manifest()
    if not manifest["image"]["rebuild_required"]:
        return  # image is current; per-boot repair is not expected to exist
    source = _orchestrator_source()
    fast_path = source[source.index('CLOUD_INIT_FAST = """') :]
    # COMMENTS STRIPPED FIRST. A substring check over the raw block passes on the explanatory
    # comment that mentions the tool, so it stayed green when the actual `command -v unzip`
    # guard was renamed -- a test that cannot fail is worse than no test here, because this is
    # the one guarding the dead-on-arrival mistake.
    executable = "\n".join(
        line for line in fast_path.splitlines() if not line.lstrip().startswith("#")
    )
    # DERIVED from the manifest, never a hardcoded list. The earlier version checked a literal
    # ("unzip", "python") tuple, so when `gh` was declared tier0 and apt-installed in CLOUD_INIT
    # -- but never repaired here -- this test stayed green. codna's first real release after the
    # fleet move then died with `gh: command not found`, exit 127. A gate that only knows about
    # yesterday's tools cannot catch tomorrow's instance of the same mistake.
    required = sorted(set(manifest["tier0"]) - set(manifest["image"].get("baked_in", [])))
    missing = [t for t in required if f"command -v {t}" not in executable]
    assert not missing, (
        f"tier0 declares {missing} but CLOUD_INIT_FAST has no `command -v <tool>` repair for "
        "them. That is the path golden-image VMs actually run, so patching CLOUD_INIT alone "
        "changes nothing for a real worker -- it is how `gh` reached production missing. Either "
        "add the repair, or list the tool under [image].baked_in once the recaptured image "
        "genuinely ships it."
    )


def test_tier1_tools_are_not_silently_promised() -> None:
    """tier0 and tier1 must not overlap.

    A tool in both reads as guaranteed while being repo-declared -- the ambiguity that made
    `rustfmt` look like an image bug when it was really an unmocked test dependency.
    """
    manifest = _manifest()
    overlap = sorted(set(manifest["tier0"]) & set(manifest["tier1"]))
    assert not overlap, f"declared in BOTH tier0 and tier1: {overlap}"


def test_tools_that_broke_the_fleet_are_now_declared() -> None:
    """Regression floor for the three that actually cost us runs, plus the two unfired ones.

    `gh` and `rsync` had not fired only because no release or sync path had run since the fleet
    went org-wide -- the first real release would have been the discovery event.
    """
    tier0 = set(_manifest()["tier0"])
    for tool in ("unzip", "gh", "rsync", "python3", "node"):
        assert tool in tier0, f"{tool!r} must be a declared tier0 guarantee"


def test_the_repair_completes_before_the_runner_registers() -> None:
    """A runner must not advertise tier0 tools it is still installing.

    This repair was briefly backgrounded to protect boot latency, and the race that choice
    accepted fired on its first real test rather than as a rare tail. Measured 2026-08-27:

        orchestrator deployed     03:52:00Z
        ci-warm-1787804191 booted 04:16:31Z   <- carried the repair
        its job started           04:17:25Z   <- 54 seconds later
        result                    gh: command not found, exit 127

    codna's release died on a VM that HAD the fix, because adding an apt repo and installing gh
    does not finish in 54 seconds. Registering first and installing after means the runner claims
    a guarantee the machine cannot yet keep -- which is the same untruth the rest of this file
    exists to prevent, just relocated into a timing window.
    """
    if not _manifest()["image"]["rebuild_required"]:
        return  # no per-boot repair to order once the image is current
    source = _orchestrator_source()
    fast_path = source[source.index('CLOUD_INIT_FAST = """') :]

    # `.find()` + an explicit assertion, never `.index()`. A missing marker means the repair
    # block was removed while rebuild_required is still true -- a real regression -- and
    # `.index()` would report it as `ValueError: substring not found`, which names nothing.
    # (Raised by `codna review` on this very file; the tool's first working review.)
    def _offset(marker: str, why: str) -> int:
        at = fast_path.find(marker)
        assert at != -1, f"CLOUD_INIT_FAST no longer contains {marker!r} -- {why}"
        return at

    repair_done = _offset(
        "ci-image-repair-done", "the per-boot repair block appears to be gone entirely"
    )
    register = _offset("config.sh --url", "the runner registration step appears to be gone")
    assert repair_done < register, (
        "the per-boot repair no longer completes before the runner registers; a job can be "
        "handed to this VM while its tier0 tools are still installing"
    )
    need = _offset("NEED=", "the repair block no longer probes for missing tools")
    assert ") &" not in fast_path[need:register], (
        "the repair subshell is backgrounded again. That is exactly what let "
        "ci-warm-1787804191 register 54s before gh existed and fail codna's release."
    )
