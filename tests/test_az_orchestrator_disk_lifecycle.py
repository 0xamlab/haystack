"""Guard the Azure CI orchestrator's disk/nic lifecycle against silent resource leaks.

WHY THIS EXISTS
---------------
Measured on the live subscription 2026-08-28: **1411 unattached managed disks, 42,624 GB
(41.6 TiB)** — 1380 of them 30 GB Premium P4. Every one belonged to a VM that no longer existed
(1283 distinct owner names vs 4 live VMs, zero overlap), all created in the preceding four days,
i.e. ~600/day and climbing.

What that actually cost, from the portal rather than from a list-price projection: month-to-date
**$582.64 total, of which Storage was $378.65** — the single largest line, ahead of Virtual
Machines at $189.38, and 65% of the bill for a CI plane whose entire job is to run VMs. By region
centralus was $469.21 of it, which is where the warm pool and most workers land.

Two causes, both invisible from the code reading well:

  1. `_create_vm` asks for an EPHEMERAL os disk (`diffDiskSettings: {"option": "Local"}`) and
     calls it "zero storage cost". But an ephemeral os disk needs a local temp disk at least as
     large as the image, and MOST OF `SIZE_CHAIN` HAS NO TEMP DISK AT ALL. Measured in centralus:
         Standard_D8s_v5   0 MB      Standard_F8s_v2  65536 MB
         Standard_D8s_v6   0 MB      Standard_D8s_v3  65536 MB
         Standard_D8s_v4   0 MB      Standard_F4s_v2  32768 MB
         Standard_D4s_v5   0 MB      Standard_D4s_v3  32768 MB
         Standard_D4s_v4   0 MB
     The warm pool runs D8s_v5, so the optimisation was failing on the *common* case and the
     `except` branches fell back by doing `props["storageProfile"].pop("osDisk", None)` — which
     hands the platform an implicitly-created managed disk that nothing owns.
  2. `delete_vm()` deletes the vm and the nic. Never the disk.

The fix is `deleteOption: "Delete"` on the os disk and on the nic reference, so ARM cascades both
with the VM in one operation — no orphan window, unlike a sweep. `sweep_leaked_disks()` remains as
belt-and-braces for disks stranded by VMs deleted *before* the fix, and for operator deletions.

These tests are text-level on purpose: the orchestrator cannot be imported off its VM (`STATE =
"/var/lib/az-orch"` is created at module scope), and the failure mode here is a code path that
looks fine and silently bills money, so what matters is that the specific construct stays present.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ORCH = Path(__file__).resolve().parents[1] / "infra" / "ci" / "az_orchestrator.py"


@pytest.fixture(scope="module")
def source() -> str:
    return ORCH.read_text(encoding="utf-8")


def _require(source: str, needle: str, why: str) -> int:
    """Locate `needle`, failing with WHY it must be there. `.find()`, never `.index()`."""
    at = source.find(needle)
    assert at != -1, f"{needle!r} is missing from {ORCH.name} — {why}"
    return at


def test_the_os_disk_is_marked_for_deletion_with_its_vm(source: str) -> None:
    _require(
        source,
        '"deleteOption": "Delete"',
        "without it ARM keeps the managed os disk after the VM is deleted; that leaked 1411 disks "
        "(~$6.7k/month) in four days",
    )
    # The managed fallback must carry the flag, not merely appear somewhere in the file.
    at = _require(
        source,
        '_MANAGED_OS_DISK = {"createOption": "FromImage", "deleteOption": "Delete"}',
        "the fallback os disk (used whenever the size has no local temp disk) must cascade-delete",
    )
    assert at > 0
    # Every os-disk assignment must go through that constant.
    assert source.count("dict(_MANAGED_OS_DISK") >= 3, (
        "all three fallback paths (409 retry, HTTP error, generic except) plus the ephemeral "
        "attempt must assign a cascading os disk"
    )


def test_the_ephemeral_fallback_never_goes_back_to_dropping_the_os_disk(source: str) -> None:
    """`pop("osDisk")` is the exact regression that caused the leak."""
    assert 'pop("osDisk"' not in source, (
        'a bare props["storageProfile"].pop("osDisk", None) is back. That lets the platform create '
        "an implicitly-named managed disk (<vm>_disk1_<guid>) which delete_vm() does not remove. "
        "Assign `managed_os_disk` instead so the disk carries deleteOption=Delete."
    )


def test_the_nic_is_also_marked_for_deletion_with_its_vm(source: str) -> None:
    _require(
        source,
        '"networkInterfaces": [{"id": nic, "properties": {"deleteOption": "Delete"}}]',
        "the nic must cascade with the VM; sweeping it afterwards leaves an orphan window and the "
        "per-region public-IP/NIC quota fills up",
    )


def test_the_disk_sweep_exists_and_is_called_from_cleanup(source: str) -> None:
    _require(source, "def sweep_leaked_disks(", "disks stranded before the deleteOption fix need reaping")
    call = _require(
        source,
        "sweep_leaked_disks(vm_names, protected)",
        "defining the sweep without calling it from cleanup() would be dead code",
    )
    defn = source.find("def sweep_leaked_disks(")
    assert call < defn, "the call should be inside cleanup(), above the definition"


def test_the_sweep_respects_the_read_after_write_lag_guard(source: str) -> None:
    """The nic sweep learned this the hard way; the disk sweep must not relearn it."""
    start = source.find("def sweep_leaked_disks(")
    body = source[start : start + 3000]
    # Assert on CODE, not prose. A first version of this test checked `"_absent_once" in body`,
    # which the function's own DOCSTRING satisfies -- so deleting the entire guard still passed.
    # Caught by mutation-checking; the lesson is that a substring shared with a comment proves
    # nothing about behaviour.
    for construct in ("_absent_once.add(key)", "_absent_once.discard(key)"):
        assert construct in body, (
            f"{construct} is missing: the disk sweep must use the same two-pass _absent_once guard "
            "as the nic sweep. A VM just PUT may not appear in live_vms() for 15-30s, and deleting "
            "its disk in that window kills the VM (this exact race previously killed wave-2 workers)"
        )
    assert 'diskState") != "Unattached"' in body or "Unattached" in body, (
        "the sweep must only touch Unattached disks — never one attached to a running VM"
    )


def test_the_sweep_only_touches_disks_from_our_own_ephemeral_workers(source: str) -> None:
    start = source.find("def sweep_leaked_disks(")
    body = source[start : start + 3000]
    _require(
        body,
        '("ci-az-", "ci-warm-")',
        "the sweep must be scoped to our ephemeral worker prefixes; the resource group also holds "
        "ci-golden-build / probe / cidebug disks that are not ours to delete",
    )


# --- the owner-name parser, against REAL names observed in the subscription -------------------

DISK_OWNER_RE = re.compile(r"^(?P<base>.+?)_(?:disk1|OsDisk_1)_[0-9a-f]{8,}$")


@pytest.mark.parametrize(
    "disk_name, expected_owner",
    [
        # Both spellings Azure uses for an implicitly-created os disk, verbatim from the leak.
        ("ci-az-32835752920-97913140762_disk1_8416847a335a45938c024c60f9364169", "ci-az-32835752920-97913140762"),
        ("ci-az-32845926457-97799340694_OsDisk_1_9317a15e17774b90b3a82300be1e0855", "ci-az-32845926457-97799340694"),
        ("ci-warm-1787926018_disk1_53833796eb5641a683eb5aa1f29d2cc0", "ci-warm-1787926018"),
    ],
)
def test_the_parser_recovers_the_owning_vm_name(disk_name: str, expected_owner: str) -> None:
    m = DISK_OWNER_RE.match(disk_name)
    assert m is not None, f"failed to parse {disk_name}"
    assert m.group("base") == expected_owner


@pytest.mark.parametrize(
    "disk_name",
    [
        "my-precious-data-disk",          # no VM-derived suffix at all
        "somevm_disk1_short",             # guid too short to be Azure's
        "backup_snapshot_2026",           # unrelated naming
    ],
)
def test_the_parser_refuses_names_it_does_not_understand(disk_name: str) -> None:
    """A disk this cannot parse must be left alone, not guessed at."""
    assert DISK_OWNER_RE.match(disk_name) is None


@pytest.mark.parametrize(
    "disk_name, owner",
    [
        ("ci-golden-build_OsDisk_1_abc123def4567890", "ci-golden-build"),
        ("probe-e2_OsDisk_1_abc123def4567890", "probe-e2"),
        ("prod-db_disk1_deadbeefcafe1234", "prod-db"),
    ],
)
def test_parseable_but_not_ours_is_still_left_alone(disk_name: str, owner: str) -> None:
    """Parsing an owner is not permission to delete: the prefix check is the authority."""
    m = DISK_OWNER_RE.match(disk_name)
    assert m is not None and m.group("base") == owner
    assert not owner.startswith(("ci-az-", "ci-warm-")), (
        f"{owner} must NOT be treated as an ephemeral worker — these disks belong to the golden "
        "image build, one-off probes and unrelated workloads"
    )
