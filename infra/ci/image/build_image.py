#!/usr/bin/env python3
"""Rebuild the az-ephemeral golden image from the bootstrap that is already the source of truth.

WHY THIS FILE EXISTS
--------------------
`git grep ci-worker` used to return exactly two hits: the ID string in az_orchestrator.py and the
manifest next to this file. No packer template, no build script, no record of how the image in
`galleries/thynci/images/ci-worker/versions/1.0.0` was made. It was a hand-captured artifact, and
manifest.toml says the consequence plainly: an image nobody can rebuild is an image nobody can
extend, so every gap gets patched at boot instead of fixed once.

That is not theoretical. In one night `python`, `unzip`, `rustfmt`, `gh` and `rsync` were each
discovered missing by a red pull request rather than by a check, and the `gh` gap took down a real
release with `gh: command not found`.

THE ONE DESIGN RULE
-------------------
This script does NOT restate the package list. It EXTRACTS `CLOUD_INIT` from az_orchestrator.py
and builds from that. Any other arrangement recreates the exact failure this is meant to end:
two descriptions of one machine, drifting apart silently. If you find yourself adding a package
here, add it to CLOUD_INIT and to manifest.toml instead -- tests/test_ci_image_contract.py
enforces that pair.

WHAT IT DOES
------------
  1. extract CLOUD_INIT (the FULL bootstrap, not CLOUD_INIT_FAST -- the fast path is what runs ON
     a golden image, so building from it would produce an image built from nothing)
  2. boot one builder VM from the stock Ubuntu jammy gen2 image with that cloud-init
  3. wait for cloud-init to finish, then VERIFY every tier0 binary the manifest declares is
     actually present on the machine -- publishing an image that does not satisfy the contract is
     the failure mode, so this refuses rather than warns
  4. deprovision, deallocate, generalize
  5. publish a new gallery image version replicated to every region in REGIONS
  6. print the exact manifest edits to land afterwards

Dry-run by default. Nothing is created, deleted or published without --apply, because this
provisions billable infrastructure and publishes an artifact the whole fleet then boots from.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MANIFEST = _HERE / "manifest.toml"
_ORCHESTRATOR = _HERE.parent / "az_orchestrator.py"

# The stock image a builder starts from -- identical to the non-golden path in
# az_orchestrator._create_vm, so a rebuilt image matches what a full bootstrap produces today.
BASE_IMAGE = "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest"


def _run(cmd: list[str], *, apply: bool, capture: bool = True) -> str:
    if not apply:
        print(f"    DRY-RUN  {' '.join(cmd)}")
        return ""
    out = subprocess.run(cmd, capture_output=capture, text=True, check=False)
    if out.returncode != 0:
        raise SystemExit(f"command failed ({out.returncode}): {' '.join(cmd)}\n{out.stderr}")
    return out.stdout


def extract_cloud_init() -> str:
    """The FULL bootstrap, verbatim from az_orchestrator.py.

    CLOUD_INIT_FAST is deliberately not used: it is what a golden-image VM runs, so building an
    image from it would bake in nothing and then repair everything at boot forever.
    """
    source = _ORCHESTRATOR.read_text("utf-8")
    match = re.search(r'^CLOUD_INIT = """(.*?)"""', source, re.S | re.M)
    if not match:
        raise SystemExit("could not find CLOUD_INIT in az_orchestrator.py -- refusing to guess")
    body = match.group(1)
    # The runner-registration tail must not run on a builder: it would register the build VM as a
    # live runner, let it claim a job, and then be captured mid-job into the image.
    for marker in ("config.sh --url", "run.sh", "shutdown -h now"):
        body = "\n".join(line for line in body.splitlines() if marker not in line)
    return body


def required_binaries() -> list[str]:
    manifest = tomllib.loads(_MANIFEST.read_text("utf-8"))
    return sorted(manifest["tier0"])


def verify_contract_on_host(vm: str, rg: str, *, apply: bool) -> None:
    """Prove the built machine satisfies tier0 BEFORE it becomes an image.

    This is the check whose absence is the whole story: the contract was written down, the
    bootstrap was edited, and nothing ever asserted the two met on a real machine.
    """
    binaries = required_binaries()
    probe = "; ".join(f'command -v {b} >/dev/null 2>&1 || echo MISSING:{b}' for b in binaries)
    print(f"  verifying {len(binaries)} tier0 binaries on the builder")
    out = _run(
        [
            "az", "vm", "run-command", "invoke", "-g", rg, "-n", vm,
            "--command-id", "RunShellScript", "--scripts", probe,
        ],
        apply=apply,
    )
    if not apply:
        return
    missing = re.findall(r"MISSING:(\S+)", out)
    if missing:
        raise SystemExit(
            f"builder is missing tier0 binaries {sorted(set(missing))}. Refusing to publish an "
            "image that does not satisfy infra/ci/image/manifest.toml -- fix CLOUD_INIT first."
        )
    print("    all tier0 binaries present")


def main(argv: list[str] | None = None) -> int:
    manifest = tomllib.loads(_MANIFEST.read_text("utf-8"))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", required=True, help="new gallery version, e.g. 1.1.0")
    parser.add_argument("--resource-group", default="thyn-ci")
    parser.add_argument("--location", default="centralus")
    parser.add_argument("--gallery", default="thynci")
    parser.add_argument("--image-definition", default="ci-worker")
    parser.add_argument("--vm-size", default="Standard_D8s_v5")
    parser.add_argument("--apply", action="store_true", help="actually create and publish")
    args = parser.parse_args(argv)

    if args.version == manifest["image"]["gallery_version"]:
        raise SystemExit(
            f"--version {args.version} is the version already recorded as published. Pick the "
            "next one; overwriting a gallery version in place is not something to do by accident."
        )

    vm = f"ci-image-builder-{args.version.replace('.', '-')}"
    cloud_init = extract_cloud_init()
    ci_path = Path(f"/tmp/{vm}.cloud-init.yml")

    print(f"\n=== rebuild ci-worker {manifest['image']['gallery_version']} -> {args.version} ===")
    print(f"  contract:       {manifest['image']['contract']}")
    print(f"  base image:     {BASE_IMAGE}")
    print(f"  bootstrap:      CLOUD_INIT from az_orchestrator.py ({len(cloud_init)} chars, "
          "registration tail stripped)")
    print(f"  tier0 to prove: {len(required_binaries())} binaries")
    print(f"  mode:           {'APPLY' if args.apply else 'DRY-RUN (pass --apply to execute)'}\n")

    if args.apply:
        ci_path.write_text(cloud_init, encoding="utf-8")

    print("  [1/5] boot the builder")
    _run(
        [
            "az", "vm", "create", "-g", args.resource_group, "-n", vm,
            "--image", BASE_IMAGE, "--size", args.vm_size, "--location", args.location,
            "--admin-username", "azureuser", "--generate-ssh-keys",
            "--custom-data", str(ci_path), "--nic-delete-option", "Delete",
            "--os-disk-delete-option", "Delete",
        ],
        apply=args.apply,
    )

    print("  [2/5] wait for cloud-init to finish")
    _run(
        [
            "az", "vm", "run-command", "invoke", "-g", args.resource_group, "-n", vm,
            "--command-id", "RunShellScript",
            "--scripts", "cloud-init status --wait || true; cloud-init status --long",
        ],
        apply=args.apply,
    )

    print("  [3/5] verify the tier0 contract on the real machine")
    verify_contract_on_host(vm, args.resource_group, apply=args.apply)

    print("  [4/5] deprovision, deallocate, generalize")
    _run(
        [
            "az", "vm", "run-command", "invoke", "-g", args.resource_group, "-n", vm,
            "--command-id", "RunShellScript",
            "--scripts", "waagent -deprovision+user -force",
        ],
        apply=args.apply,
    )
    _run(["az", "vm", "deallocate", "-g", args.resource_group, "-n", vm], apply=args.apply)
    _run(["az", "vm", "generalize", "-g", args.resource_group, "-n", vm], apply=args.apply)

    print("  [5/5] publish the gallery version, replicated to every fleet region")
    regions = _fleet_regions()
    print(f"    regions: {', '.join(regions)}")
    _run(
        [
            "az", "sig", "image-version", "create",
            "-g", args.resource_group, "--gallery-name", args.gallery,
            "--gallery-image-definition", args.image_definition,
            "--gallery-image-version", args.version,
            "--virtual-machine", vm,
            "--target-regions", *regions,
            "--replica-count", "1",
        ],
        apply=args.apply,
    )

    print("\n  AFTERWARDS, in infra/ci/image/manifest.toml:")
    print(f"    gallery_version  = \"{args.version}\"   # was {manifest['image']['gallery_version']}")
    print("    rebuild_required = false")
    print("  and delete the per-boot repair block in CLOUD_INIT_FAST. Both contract tests are")
    print("  written to follow: the repair-coverage check short-circuits once rebuild_required")
    print("  is false, and the rebuild_required check asserts it matches contract==gallery.")
    print(f"\n  Then clean up:  az vm delete -g {args.resource_group} -n {vm} --yes\n")
    return 0


def _fleet_regions() -> list[str]:
    """The regions the orchestrator provisions into -- read from it, not restated here."""
    source = _ORCHESTRATOR.read_text("utf-8")
    block = re.search(r"^REGIONS = \[(.*?)^\]", source, re.S | re.M)
    if not block:
        raise SystemExit("could not read REGIONS from az_orchestrator.py -- refusing to guess")
    return re.findall(r'\(\s*"([a-z0-9]+)"', block.group(1))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
