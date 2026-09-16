"""Runner-integrity and diagnosability: prove the tarball, bound config.sh, and point at the body.

Four gaps, all downstream of the 2026-09-16 outage, where a runner version below GitHub's
registration floor took the whole plane dark for nine hours. #997 fixed the version resolution
and added the gist telemetry sink; #999 fixed the reaper. These four close what was left:

1. THE DOWNLOAD WAS NEVER VERIFIED. The guard was `[ -s /tmp/runner-new.tar.gz ]` -- "non-empty".
   An HTML error page from a failed redirect satisfies that perfectly, and the very next line ran
   `tar -xzf` over the LIVE /opt/runner tree. Extraction fails partway, leaving a runner that is
   neither the baked version nor the new one -- strictly worse than not upgrading, and invisible:
   the only symptom is config.sh misbehaving on a half-overwritten tree. Now verified against the
   `sha256_checksum` that `GET /orgs/{org}/actions/runners/downloads` publishes, before anything
   touches /opt/runner, with a `gzip -t` fallback (clearly labelled as weaker) when no checksum
   could be fetched.

2. ONE ATTEMPT, NO RETRY. A single transient failure cost the whole upgrade. Now two attempts
   covering download+verify+extract as a unit -- not the curl alone, because a corrupt tarball is
   as much a failure as a missing one and re-extracting known-bad bytes cannot help.

3. config.sh WAS THE LAST UNBOUNDED STEP. Every other network call in the bootstrap carries a
   -m/--timeout. A config.sh that stalled left the VM RUNNING and unregistered indefinitely,
   which reads to cleanup() as neither stopped nor registered: it survived to BOOT_GRACE_S and was
   reaped as orphan-no-runner with nothing on the machine saying why. That is the shape of the
   "orphan-no-runner at 782-991s" reports. Now bounded at 240s (with `-k 30`, because timeout(1)
   signals `su` and a dotnet child can ignore SIGTERM), rc=124 is called out as a HANG rather than
   a refusal, and the shutdown line names rc + resulting runner version + whether the upgrade
   succeeded.

4. THE BOOT LOG HAD NO ADDRESS. #997 made the worker PATCH /root/boot.log to a private gist, so
   the evidence survives the delete -- but the gist id lived in /root/gist.id on a machine that no
   longer exists, so "this worker never registered" was diagnosable only by guessing. The
   bootstrap now stamps `description: az-ci-worker vm=<name>` on the gist it creates, and the
   orchestrator resolves that stamp at reap time and prints the URL ON the reap line.

Items 1 and 2 are tested BEHAVIOURALLY: the real upgrade stage is extracted from the rendered
bootstrap, relocated to a temp dir, and executed against stubbed network tools. Item 3 is
structural -- bounding `su - runner` cannot be executed without a real runner user -- and item 4
is pure Python against a stubbed GitHub API.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import os
import re
import shutil
import stat
import subprocess
import tarfile
import time as _time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "infra" / "ci" / "az_orchestrator.py"

_BAKED = "2.327.1"     # what the frozen gallery image ships
_CURRENT = "2.337.0"   # what the downloads endpoint offers
_FAKE_SUBS = {
    "__SSH_PUB__": "ssh-ed25519 AAAAfakekey operator@host",
    "__GH_TOKEN__": "gho_FAKETOKENFAKETOKENFAKETOKENFAKETOK12",
    "__ORG__": "thyn-ai",
    "__RUNNERGROUP__": "az-ephemeral-pool",
    "__VMNAME__": "ci-az-1234-5678",
    "__RUNNER_PIN__": _CURRENT,
}


def _load(monkeypatch=None):
    for key in ("AZURE_SUBSCRIPTION_ID", "AZURE_TENANT_ID"):
        os.environ.setdefault(key, "00000000-0000-0000-0000-000000000000")
    os.environ.setdefault("GITHUB_CI_TOKEN", "test-token")
    spec = importlib.util.spec_from_file_location("az_orch_runner_integrity", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def _templates() -> dict[str, str]:
    tree = ast.parse(_TOOL.read_text())
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if getattr(target, "id", "") in ("CLOUD_INIT", "CLOUD_INIT_FAST"):
                    out[target.id] = node.value.value
    assert set(out) == {"CLOUD_INIT", "CLOUD_INIT_FAST"}, sorted(out)
    return out


def _render(tpl: str, name: str = "ci-az-1234-5678") -> str:
    doc = tpl
    for key, val in {**_FAKE_SUBS, "__VMNAME__": name}.items():
        doc = doc.replace(key, val)
    return doc


def _bootstrap(which: str = "CLOUD_INIT_FAST", name: str = "ci-az-1234-5678") -> str:
    parsed = yaml.safe_load(_render(_templates()[which], name))
    files = {f["path"]: f["content"] for f in parsed.get("write_files", [])}
    return files["/root/bootstrap.sh"]


def _code(text: str) -> str:
    """Comments stripped: a substring check over raw text describes the prose, not the machine,
    and this bootstrap is deliberately over-commented about the very failures it guards."""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


# ============================================================ item 4a: the gist description stamp


def test_both_templates_stamp_the_vm_name_into_the_gist_description() -> None:
    """The match key for item 4b, and the reason it is cheap.

    Without a description the only place a VM name appears is inside the gist CONTENT, and the
    listing endpoint truncates content -- so resolving one pointer would cost an extra fetch per
    gist per reap. One field at creation time makes the whole index a single listing.

    Both templates, because both create a gist and a stock-image worker is still a worker.
    """
    for which in ("CLOUD_INIT", "CLOUD_INIT_FAST"):
        boot = _bootstrap(which, name="ci-az-99-100")
        assert 'az-ci-worker vm=ci-az-99-100' in boot, (
            f"{which} does not stamp the VM name into its gist description"
        )
        # It has to be in the description FIELD of the creation payload, not merely somewhere in
        # the script, or the API stores nothing and the listing cannot match.
        payload = next(l for l in boot.splitlines() if '"public":False' in l)
        assert '"description":"az-ci-worker vm=ci-az-99-100"' in payload, payload


def test_the_stamp_survives_render_userdata(monkeypatch, tmp_path) -> None:
    """The stamp is only useful if it reaches the ARM payload, so check it post-substitution --
    the same reasoning render_userdata's own gate gives for checking the rendered document
    rather than the template."""
    mod = _load(monkeypatch)
    out = tmp_path / "w.yml"
    mod.render_userdata(mod.CLOUD_INIT_FAST, "ci-az-7-8", str(out))
    doc = out.read_text()
    assert "az-ci-worker vm=ci-az-7-8" in doc
    assert yaml.safe_load(doc)["runcmd"] == ["bash /root/bootstrap.sh"]


# ============================================================ item 4b: resolving it at reap time


def _gist(vm: str, url: str = None, desc: str = None):
    return {
        "id": hashlib.sha1(vm.encode()).hexdigest()[:20],
        "description": desc if desc is not None else f"az-ci-worker vm={vm}",
        "html_url": url if url is not None else f"https://gist.github.com/{vm[:8]}",
    }


def _gist_mod(monkeypatch, gists, *, pages_of=100):
    """A module whose gh() serves a gist listing, recording every call."""
    mod = _load(monkeypatch)
    calls: list[str] = []

    def fake_gh(path, method="GET", body=None):
        calls.append(path)
        if not path.startswith("gists"):
            return {}
        page = int(re.search(r"[&?]page=(\d+)", path).group(1))
        chunk = gists[(page - 1) * pages_of: page * pages_of]
        return chunk

    monkeypatch.setattr(mod, "gh", fake_gh)
    monkeypatch.setattr(mod, "log", lambda m: calls.append(f"LOG {m}"))
    return mod, calls


def test_gist_url_for_resolves_a_worker_by_its_description(monkeypatch) -> None:
    mod, _ = _gist_mod(monkeypatch, [_gist("ci-az-1-1"), _gist("ci-az-2-2")])
    assert mod.gist_url_for("ci-az-1-1") == "https://gist.github.com/ci-az-1-"
    assert mod.gist_url_for("ci-az-2-2") == "https://gist.github.com/ci-az-2-"


def test_an_unresolvable_pointer_is_none_never_a_guess(monkeypatch) -> None:
    """A worker booted before the stamp shipped, or older than the listing window, has no
    pointer. Reporting None (rendered as "none") is honest; synthesising a URL is not."""
    mod, _ = _gist_mod(monkeypatch, [_gist("ci-az-1-1")])
    assert mod.gist_url_for("ci-az-does-not-exist") is None


def test_a_gist_with_no_description_is_not_matched(monkeypatch) -> None:
    """Every gist created before this change has description=None. Matching those on anything
    other than the stamp would attach the wrong worker's boot log to a reap -- worse than no
    pointer, because it looks authoritative."""
    mod, _ = _gist_mod(monkeypatch, [{"id": "x", "description": None,
                                      "html_url": "https://gist.github.com/x"}])
    assert mod.gist_url_for("ci-az-1-1") is None


def test_only_fleet_prefixed_names_are_matched(monkeypatch) -> None:
    """The regex is anchored on ci-az-/ci-warm-, so a gist whose prose mentions some other VM
    cannot be matched, and ci-orch's own gists (if it ever made one) are not adoptable."""
    mod, _ = _gist_mod(monkeypatch, [
        _gist("ci-orch", desc="notes about ci-az-1-1 and vm=ci-orch"),
    ])
    assert mod.gist_url_for("ci-az-1-1") is None
    assert mod.gist_url_for("ci-orch") is None


def test_the_index_follows_pagination(monkeypatch) -> None:
    """Same reason all_runners() paginates: the fleet can create more than 100 gists inside the
    window a corpse is still reapable, and a target on page 2 that is silently skipped reads as
    "no boot log exists"."""
    filler = [_gist(f"ci-az-9-{i}") for i in range(150)]
    target = _gist("ci-az-target-1")
    mod, calls = _gist_mod(monkeypatch, filler + [target])
    assert mod.gist_url_for("ci-az-target-1") == target["html_url"]
    assert sum(1 for c in calls if c.startswith("gists")) >= 2, calls


def test_the_index_is_capped_so_a_runaway_listing_cannot_stall_a_reap(monkeypatch) -> None:
    mod = _load(monkeypatch)
    assert mod.GIST_MAX_PAGES >= 1
    huge = [_gist(f"ci-az-9-{i}") for i in range(1000)]
    calls: list[str] = []
    monkeypatch.setattr(mod, "gh", lambda p, **k: calls.append(p) or huge[:100])
    monkeypatch.setattr(mod, "log", lambda m: None)
    mod.gist_url_for("ci-az-9-0")
    assert len(calls) == mod.GIST_MAX_PAGES, calls


def test_the_index_is_listed_once_per_cycle_however_many_vms_are_reaped(monkeypatch) -> None:
    """A cycle that reaps a dozen corpses must cost ONE listing, not twelve -- cleanup() runs on
    the reconcile thread and this annotates a reap rather than being the point of it."""
    many = [_gist(f"ci-az-9-{i}") for i in range(10)]
    mod, calls = _gist_mod(monkeypatch, many)
    now = 1_800_000_000.0
    monkeypatch.setattr(mod.time, "time", lambda: now)
    for i in range(10):
        assert mod.gist_url_for(f"ci-az-9-{i}") is not None
    assert sum(1 for c in calls if c.startswith("gists")) == 1, calls


def test_the_cache_expires_so_a_new_worker_is_findable_next_cycle(monkeypatch) -> None:
    many = [_gist(f"ci-az-9-{i}") for i in range(3)]
    mod, calls = _gist_mod(monkeypatch, many)
    clock = {"t": 1_800_000_000.0}
    monkeypatch.setattr(mod.time, "time", lambda: clock["t"])
    mod.gist_url_for("ci-az-9-0")
    clock["t"] += mod.GIST_CACHE_S + 1
    mod.gist_url_for("ci-az-9-1")
    assert sum(1 for c in calls if c.startswith("gists")) == 2, calls


def test_a_gist_listing_failure_cannot_stop_or_crash_a_reap(monkeypatch) -> None:
    """Annotation is best-effort BY CONSTRUCTION. A GitHub 500 during a reap must cost the
    pointer, never the reap -- freeing the quota is the point of the sweep."""
    mod = _load(monkeypatch)
    logged: list[str] = []
    monkeypatch.setattr(mod, "log", lambda m: logged.append(m))

    def boom(path, method="GET", body=None):
        raise RuntimeError("502 Bad Gateway")

    monkeypatch.setattr(mod, "gh", boom)
    assert mod.gist_url_for("ci-az-1-1") is None
    assert any("gist index: listing failed" in l for l in logged), logged


def test_a_failed_listing_is_not_retried_per_reap(monkeypatch) -> None:
    """The cache timestamp is set BEFORE the call, so one failure costs one listing per cycle
    rather than one per VM -- the failure path must not be more expensive than the success path."""
    mod = _load(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(mod, "log", lambda m: None)

    def boom(path, method="GET", body=None):
        calls.append(path)
        raise RuntimeError("502")

    monkeypatch.setattr(mod, "gh", boom)
    for _ in range(5):
        assert mod.gist_url_for("ci-az-1-1") is None
    assert len(calls) == 1, calls


def test_a_non_list_response_body_is_treated_as_no_index(monkeypatch) -> None:
    """An error body, or a harness stub shaped for the runners endpoint, must not be iterated as
    if it were gists. Stop and report nothing rather than guess."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "log", lambda m: None)
    monkeypatch.setattr(mod, "gh", lambda p, **k: {"runners": [{"name": "ci-az-1-1"}]})
    assert mod.gist_url_for("ci-az-1-1") is None


def test_the_reap_line_carries_the_pointer(monkeypatch) -> None:
    """ON the reap line, not beside it: an operator reading the journal needs the evidence link
    in the same breath as the verdict, and one line per VM per cycle is this sweep's noise
    ceiling. `boot-log=none` rather than an omitted field, so "no boot log exists" is
    distinguishable from "the annotator broke"."""
    mod = _load(monkeypatch)
    logs: list[str] = []
    deleted: list[tuple] = []
    monkeypatch.setattr(mod, "log", lambda m: logs.append(m))
    monkeypatch.setattr(mod, "runner_names", lambda: set())
    monkeypatch.setattr(mod, "busy_runner_names", lambda: set())
    monkeypatch.setattr(mod, "queued_jobs", lambda: [])
    monkeypatch.setattr(mod, "_sweep_stale_registrations", lambda live: None)
    monkeypatch.setattr(mod, "vm_power_state", lambda n: "stopped")
    monkeypatch.setattr(mod, "arm", lambda *a, **k: {"value": []})
    monkeypatch.setattr(mod, "delete_vm",
                        lambda n, l, reason="", was_busy=False: deleted.append((n, reason)))
    monkeypatch.setattr(mod, "gh", lambda p, **k: [_gist("ci-az-1-1", "https://gist.github.com/abc123")])
    now = 1_800_000_000.0
    monkeypatch.setattr(mod.time, "time", lambda: now)
    monkeypatch.setattr(
        mod, "live_vms",
        lambda: [("ci-az-1-1",
                  _time.strftime("%Y-%m-%dT%H:%M:%S", _time.localtime(now - mod.BOOT_GRACE_S - 5)),
                  "centralus")])

    mod.cleanup()

    assert [n for n, _ in deleted] == ["ci-az-1-1"], deleted
    line = next(l for l in logs if l.startswith("deleting ci-az-1-1"))
    assert "boot-log=https://gist.github.com/abc123" in line, line
    assert "reason=stopped-no-runner" in line, line


def test_the_reap_line_says_none_when_there_is_no_pointer(monkeypatch) -> None:
    mod = _load(monkeypatch)
    logs: list[str] = []
    monkeypatch.setattr(mod, "log", lambda m: logs.append(m))
    monkeypatch.setattr(mod, "runner_names", lambda: set())
    monkeypatch.setattr(mod, "busy_runner_names", lambda: set())
    monkeypatch.setattr(mod, "queued_jobs", lambda: [])
    monkeypatch.setattr(mod, "_sweep_stale_registrations", lambda live: None)
    monkeypatch.setattr(mod, "vm_power_state", lambda n: "stopped")
    monkeypatch.setattr(mod, "arm", lambda *a, **k: {"value": []})
    monkeypatch.setattr(mod, "delete_vm", lambda *a, **k: None)
    monkeypatch.setattr(mod, "gh", lambda p, **k: [])
    now = 1_800_000_000.0
    monkeypatch.setattr(mod.time, "time", lambda: now)
    monkeypatch.setattr(
        mod, "live_vms",
        lambda: [("ci-az-1-1",
                  _time.strftime("%Y-%m-%dT%H:%M:%S", _time.localtime(now - mod.BOOT_GRACE_S - 5)),
                  "centralus")])
    mod.cleanup()
    line = next(l for l in logs if l.startswith("deleting ci-az-1-1"))
    assert "boot-log=none" in line, line


# ==================================================== items 1+2: structure of the upgrade stage


def test_the_tarball_is_verified_against_the_published_checksum() -> None:
    boot = _bootstrap()
    assert "actions/runners/downloads" in boot, (
        "the upgrade stage no longer asks GitHub for the asset it publishes, so there is no "
        "authoritative checksum to verify against"
    )
    assert "sha256_checksum" in boot
    code = _code(boot)
    assert "sha256sum" in code, "nothing computes the digest of what was downloaded"


def test_verification_happens_before_anything_touches_the_runner_tree() -> None:
    """THE ordering that matters. Verifying after extraction is decorating a corpse: the corrupt
    bytes have already been written over /opt/runner."""
    code = _code(_bootstrap())
    verify = code.index("sha256sum")
    extract = code.index("tar -xzf")
    assert verify < extract, (
        f"extraction at {extract} precedes verification at {verify}"
    )
    # And extraction is gated on the verification verdict, not merely preceded by it.
    gated = code[code.index("VERIFIED=0"):extract]
    assert 'if [ "$VERIFIED" = "1" ]' in gated, gated


def test_a_checksum_mismatch_is_reported_with_both_digests() -> None:
    """Got-vs-want, on the same line as the HTTP code and byte count. "The download failed" is
    not a diagnosis; "http=200 bytes=1437 sha256=MISMATCH got=... want=..." is."""
    code = _code(_bootstrap())
    line = next(l for l in code.splitlines() if "sha256=MISMATCH" in l)
    for token in ("http=$HTTP", "bytes=$BYTES", "got=${GOT:-none}", "want=$SUM"):
        assert token in line, f"{token} missing from {line!r}"
    assert "refusing to extract" in line, line


def test_the_unverifiable_fallback_says_it_is_unverifiable() -> None:
    """When the downloads endpoint is unreachable there is no checksum, so the block falls back
    to `gzip -t`. That is genuinely weaker -- it cannot detect a valid gzip of the WRONG version
    -- and must be labelled as such rather than reporting a bare success."""
    code = _code(_bootstrap())
    assert "gzip -t" in code
    weak = [l for l in code.splitlines() if "sha256=UNAVAILABLE" in l]
    assert len(weak) == 2, f"expected a labelled verdict for both gzip outcomes: {weak}"
    assert any("gzip=VALID" in l for l in weak) and any("gzip=INVALID" in l for l in weak)


def test_the_version_fallback_still_exists() -> None:
    """Losing version resolution ENTIRELY is the 2026-09-16 outage. The downloads endpoint is
    preferred because it also carries the checksum, but releases/latest must remain behind it so
    a single endpoint failure degrades to "upgrade without verification" rather than to "fleet
    cannot register"."""
    code = _code(_bootstrap())
    assert "repos/actions/runner/releases/latest" in code
    assert code.index("actions/runners/downloads") < code.index("repos/actions/runner/releases/latest")
    assert 'if [ -z "$WANT" ]' in code, "the fallback is not conditional on the primary failing"


def test_the_upgrade_is_attempted_exactly_twice() -> None:
    """Two attempts, not a loop: a third download of an asset GitHub is failing to serve buys
    nothing and spends boot time that is charged to registration."""
    code = _code(_bootstrap())
    assert "for uattempt in 1 2; do" in code
    stage = code[code.index("for uattempt in 1 2; do"):code.index("runner-upgrade-done")]
    assert "while " not in stage and "until " not in stage, stage
    assert stage.count("curl -sL -o") == 1, "the retry does not reuse the same download step"


def test_an_abandoned_upgrade_is_announced_and_does_not_abort_the_boot() -> None:
    """Degrade, do not gate: the baked runner stays and config.sh is still attempted. But it must
    be SAID, naming the version kept -- "the fleet will not register" and "the fleet will not
    register because the upgrade was abandoned and the baked runner is below the floor" are the
    same symptom with very different causes."""
    code = _code(_bootstrap())
    line = next(l for l in code.splitlines() if "ABANDONED" in l)
    assert "after 2 attempts" in line and "${HAVE:-unknown}" in line, line
    # and it must not stop the boot
    assert "exit" not in line, line


# ============================================== item 3: config.sh is bounded and fails loudly


@pytest.mark.parametrize("which", ["CLOUD_INIT_FAST", "CLOUD_INIT"])
def test_config_sh_is_bounded_in_both_templates(which: str) -> None:
    """The last unbounded step in the bootstrap. A hung config.sh left the VM running and
    unregistered until the reaper took it at BOOT_GRACE_S -- which is exactly the
    orphan-no-runner-at-782-991s population, with nothing on the machine explaining it."""
    code = _code(_bootstrap(which))
    line = next(l for l in code.splitlines() if "config.sh --url" in l)
    assert line.strip().startswith("timeout "), f"{which}: config.sh is unbounded: {line!r}"
    assert re.search(r"timeout -k \d+ 240 ", line), (
        f"{which}: no SIGKILL escalation. timeout(1) signals `su`, and a dotnet child can ignore "
        f"SIGTERM, so a TERM-only bound can leave the hang in place: {line!r}"
    )


def test_a_timeout_is_distinguished_from_a_refusal() -> None:
    """rc=124 means "never returned"; any other non-zero means GitHub answered and said no. Those
    have different causes and different fixes, and conflating them is what made the original
    outage hard to read."""
    code = _code(_bootstrap())
    assert 'if [ "$CFG_RC" = "124" ]' in code
    assert "config-TIMEOUT" in code
    line = next(l for l in code.splitlines() if "config-TIMEOUT" in l)
    assert "240s" in line, line


def test_the_shutdown_line_names_the_state_that_caused_it() -> None:
    """A reader of the journal or the gist must not have to reconstruct the failure from four
    earlier stages. The line carries the rc, the runner version that ended up installed, and
    whether the upgrade that was supposed to produce it succeeded."""
    code = _code(_bootstrap())
    line = next(l for l in code.splitlines() if l.strip().startswith('log "config-failed'))
    for token in ("$HOW", "runner-version=$(runner_version)", "${WANT:-unresolved}",
                  "${UPGRADE_OK:-not-attempted}"):
        assert token in line, f"{token} missing from the config-failed line: {line!r}"
    assert "boot-log gist" in line, line


def test_the_gist_is_flushed_before_the_machine_goes() -> None:
    """The loud shutdown is only loud if the log actually leaves the VM. `up` must sit between
    the failure line and `shutdown -h now`, or the evidence dies with the machine -- the original
    nine-hour outage.

    Matched on a line whose stripped form is exactly `up`, not on the literal "\\nup\\n": the
    flush inside this `if` block is indented two spaces after the block scalar is dedented, so a
    column-zero search silently finds an EARLIER flush and the assertion passes for the wrong
    reason.
    """
    lines = _bootstrap().splitlines()
    failed = next(i for i, l in enumerate(lines) if l.strip().startswith('log "config-failed'))
    shutdown = next(i for i, l in enumerate(lines)
                    if l.strip().startswith("shutdown -h now") and i > failed)
    flushes = [i for i, l in enumerate(lines) if l.strip() == "up" and failed < i < shutdown]
    assert flushes, (
        f"no gist flush between the config-failed line ({failed}) and shutdown ({shutdown})"
    )


def test_the_version_is_resolvable_from_the_filename_when_the_url_shape_changes() -> None:
    """Robustness of the thing that makes verification possible at all.

    `WANT` is parsed out of the downloads payload. If it comes back empty the block falls through
    to releases/latest -- which has NO checksum, so every boot silently loses verification while
    still reporting success. That is the worst available failure mode here: not an outage, just a
    fleet that stops proving its own downloads. Hence two sources, and this test.
    """
    code = _code(_bootstrap())
    line = next(l for l in code.splitlines() if l.strip().startswith("DLINFO="))
    assert '"/v([0-9][0-9.]*)/"' in line, "the url-path version source is gone"
    assert '"filename"' in line, (
        "the version has no fallback source; one GitHub url-shape change silently downgrades "
        "every boot to unverifiable"
    )
    assert " or re.search(" in line, "the two sources are not chained as alternatives"
    # The filename is `actions-runner-linux-x64-2.337.0.tar.gz`. A loose digit run matches the
    # `64` in `x64` FIRST and silently reports want=64 -- which happened, and which no
    # comparison against HAVE would ever flag as wrong, because 64 > any real version so the
    # upgrade simply never fires. Two literal dots are what make it a version.
    assert '"([0-9]+[.][0-9]+[.][0-9]+)"' in line, (
        f"the filename version regex can match the architecture digits: {line}"
    )
    # And no backslash escapes: this is a plain (non-raw) Python triple-quoted string, so a
    # `\d` here is interpreted by PYTHON, not by re -- the trap the runner-upgrade block's own
    # comment about `printf '%s\n'` documents.
    assert "\\d" not in line and "\\." not in line, line


def test_nothing_before_config_can_abort_the_boot() -> None:
    """Re-pinned against the new code: the verification and retry logic must degrade, never gate.
    Comment-stripped, because the header comment names `set -e` in order to say it is absent."""
    code = _code(_bootstrap())
    assert "set -e" not in code
    assert "exit " not in code[:code.index("config.sh --url")]


# ============================== items 1+2, behaviourally: the real stage, executed in a sandbox


_HERMETIC = ("sh", "bash", "python3", "awk", "wc", "tar", "gzip", "sort", "head",
             "tail", "date", "cat", "mkdir", "rm", "chmod", "touch")


def _relocations(root: Path) -> dict[str, str]:
    """The ONLY edits made to the extracted stage: three absolute paths moved into the sandbox.

    Asserted exhaustively below, because a test that quietly rewrites the thing it claims to be
    testing is worse than no test. Logic, ordering and every literal are the real ones.
    """
    return {
        "/opt/runner": f"{root}/opt-runner",
        "/root/boot.log": f"{root}/boot.log",
        "/tmp/runner-new.tar.gz": f"{root}/runner-new.tar.gz",
    }


def _upgrade_stage(root: Path) -> str:
    lines = _bootstrap().splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("runner_version(){"))
    end = next(i for i, l in enumerate(lines)
               if l.strip().startswith('log "runner-upgrade-done'))
    block = "\n".join(lines[start:end + 1])
    for old, new in _relocations(root).items():
        block = block.replace(old, new)
    for old in _relocations(root):
        assert old not in block, f"relocation missed {old}; the stage would touch the host"
    return block


def _stub(dirpath: Path, name: str, body: str) -> None:
    p = dirpath / name
    p.write_text(body)
    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def upgrade_sandbox(tmp_path):
    """A hermetic runner tree + stubbed network, so the real upgrade stage can be EXECUTED.

    `curl` is a router: the downloads endpoint and releases/latest are served from files the test
    writes, and the asset download serves either a genuine tar.gz (whose sha256 the test computed
    and put in the downloads payload) or an HTML error page, switching on attempt number. That
    dial is what makes "corrupt download recovered by the retry" and "corrupt download never
    reaches the runner tree" the same test harness with different settings.
    """
    root = tmp_path
    tools = root / "tools"
    hermetic = root / "hermetic"
    for d in (tools, hermetic):
        d.mkdir()
    missing = [t for t in _HERMETIC if shutil.which(t) is None]
    if missing:
        pytest.skip(f"host lacks the utilities this sandbox needs: {missing}")
    for t in _HERMETIC:
        os.symlink(shutil.which(t), hermetic / t)
    # macOS has no sha256sum; provide a real digest via python3 rather than a canned value, so
    # MATCH/MISMATCH verdicts are computed and not simulated.
    if shutil.which("sha256sum"):
        os.symlink(shutil.which("sha256sum"), hermetic / "sha256sum")
    else:
        _stub(hermetic, "sha256sum",
              "#!/bin/sh\nexec python3 -c 'import hashlib,sys;"
              "print(hashlib.sha256(open(sys.argv[1],\"rb\").read()).hexdigest(), sys.argv[1])' \"$1\"\n")
    _stub(tools, "timeout", '#!/bin/sh\nshift\nexec "$@"\n')

    # The baked runner tree, reporting the frozen image's version.
    (root / "opt-runner" / "bin").mkdir(parents=True)
    _stub(root / "opt-runner" / "bin", "Runner.Listener",
          f'#!/bin/sh\necho "{_BAKED}"\n')
    (root / "boot.log").write_text("")

    # A genuine runner tarball: extracting it over the tree upgrades the reported version, which
    # is how the tests prove the upgrade TOOK EFFECT rather than merely ran.
    good_src = root / "good-src"
    (good_src / "bin").mkdir(parents=True)
    _stub(good_src / "bin", "Runner.Listener", f'#!/bin/sh\necho "{_CURRENT}"\n')
    good = root / "good.tar.gz"
    with tarfile.open(good, "w:gz") as tf:
        tf.add(good_src / "bin", arcname="bin")
    good_bytes = good.read_bytes()
    good_sha = hashlib.sha256(good_bytes).hexdigest()
    (root / "good.bin").write_bytes(good_bytes)
    (root / "bad.bin").write_bytes(b"<html><body>404: Not Found</body></html>\n")
    (root / "attempts").write_text("0")

    _stub(tools, "curl", f"""#!/bin/sh
out=""; url=""
prev=""
for a in "$@"; do
  if [ "$prev" = "-o" ]; then out="$a"; fi
  case "$a" in http*|https*) url="$a" ;; esac
  prev="$a"
done
case "$url" in
  *actions/runners/downloads) cat "{root}/downloads.json" 2>/dev/null || printf '%s' '[]' ;;
  *releases/latest) cat "{root}/releases.json" 2>/dev/null || printf '%s' '{{}}' ;;
  *)
    n=$(( $(cat "{root}/attempts" 2>/dev/null || echo 0) + 1 ))
    echo "$n" > "{root}/attempts"
    if [ "$n" -ge "$(cat {root}/good_on 2>/dev/null || echo 1)" ]; then
      cat "{root}/good.bin" > "$out"; printf '%s' "200"
    else
      cat "{root}/bad.bin" > "$out"; printf '%s' "404"
    fi ;;
esac
""")
    env = {
        "PATH": f"{tools}:{hermetic}",
        "HOME": str(root),
        "TOK": "gho_FAKETOKEN",
    }
    return {"root": root, "env": env, "sha": good_sha, "tools": tools, "hermetic": hermetic}


def _write_payloads(sandbox, *, downloads=True, checksum=None, version=_CURRENT,
                    good_on=1, url=None):
    """Set what the stubbed GitHub endpoints answer."""
    root = sandbox["root"]
    root.joinpath("good_on").write_text(str(good_on))
    # The REAL asset URL shape, `/download/v<version>/` included. A plainer URL here once made
    # every one of these tests take the releases/latest fallback and quietly stop exercising the
    # checksum path at all -- which is why the version now has two sources and its own test.
    asset = url or (
        "https://github.com/actions/runner/releases/download/"
        f"v{version}/actions-runner-linux-x64-{version}.tar.gz"
    )
    if downloads:
        payload = [{"os": "linux", "architecture": "x64", "download_url": asset,
                    "filename": f"actions-runner-linux-x64-{version}.tar.gz",
                    "sha256_checksum": checksum if checksum is not None else sandbox["sha"]},
                   {"os": "osx", "architecture": "x64", "download_url": "https://x/ignored",
                    "sha256_checksum": "deadbeef"}]
        root.joinpath("downloads.json").write_text(__import__("json").dumps(payload))
    else:
        root.joinpath("downloads.json").write_text("[]")
    root.joinpath("releases.json").write_text(f'{{"tag_name":"v{version}"}}')


def _run_upgrade(sandbox, *, env_extra=None):
    root = sandbox["root"]
    log = root / "captured.log"
    log.write_text("")
    (root / "stage.sh").write_text(_upgrade_stage(root) + "\n")
    (root / "harness.sh").write_text(
        f'log(){{ echo "$*" >> "{log}"; }}\n'
        "up(){ :; }\n"
        f'. "{root / "stage.sh"}"\n'
        f'echo "UPGRADE_OK=$UPGRADE_OK" >> "{log}"\n'
        f'echo "FINAL_VERSION=$(runner_version)" >> "{log}"\n'
    )
    env = dict(sandbox["env"], **(env_extra or {}))
    proc = subprocess.run([str(sandbox["hermetic"] / "bash"), str(root / "harness.sh")],
                          capture_output=True, text=True, env=env, timeout=180)
    lines = log.read_text().splitlines()
    assert lines, f"the stage produced no log (rc={proc.returncode}): {proc.stderr}"
    return lines, proc


def _kv(lines, key):
    line = next(l for l in lines if l.startswith(key))
    return line.split("=", 1)[1]


def test_behaviour_a_verified_download_upgrades_the_runner(upgrade_sandbox) -> None:
    """Happy path, executed: checksum matches, extraction happens, and the runner tree really
    does report the new version afterwards.

    The version assertion is the point. "The upgrade step ran" is not evidence; the baked
    Runner.Listener in this sandbox reports 2.327.1 and the tarball's reports 2.337.0, so
    FINAL_VERSION can only be the new one if the verified bytes were actually extracted over the
    tree.
    """
    _write_payloads(upgrade_sandbox, good_on=1)
    lines, proc = _run_upgrade(upgrade_sandbox)
    assert proc.returncode == 0, proc.stderr
    assert any("sha256=MATCH" in l for l in lines), lines
    assert any("runner-upgrade-extract attempt=1 ok" in l for l in lines), lines
    assert _kv(lines, "UPGRADE_OK") == "1", lines
    assert _kv(lines, "FINAL_VERSION") == _CURRENT, lines
    assert not any("ABANDONED" in l for l in lines), lines
    assert not any("MISMATCH" in l for l in lines), lines


def test_behaviour_a_corrupt_download_is_retried_and_recovers(upgrade_sandbox) -> None:
    """ITEM 2, executed: attempt 1 gets an HTML error page, attempt 2 gets the real tarball.

    This is the intermittent-failure shape -- one bad response out of two -- and the difference
    between a worker that registers and one that powers off. Note the retry succeeds only because
    the FIRST attempt was refused: had it extracted the error page over /opt/runner, the tree
    would already have been corrupt by the time attempt 2 ran.
    """
    _write_payloads(upgrade_sandbox, good_on=2)
    lines, proc = _run_upgrade(upgrade_sandbox)
    assert proc.returncode == 0, proc.stderr
    mismatch = [l for l in lines if "sha256=MISMATCH" in l]
    assert len(mismatch) == 1, lines
    assert "attempt=1" in mismatch[0] and "http=404" in mismatch[0], mismatch[0]
    assert "refusing to extract" in mismatch[0], mismatch[0]
    assert any("attempt=2" in l and "sha256=MATCH" in l for l in lines), lines
    assert _kv(lines, "UPGRADE_OK") == "1", lines
    assert _kv(lines, "FINAL_VERSION") == _CURRENT, lines


def test_behaviour_a_persistently_corrupt_download_never_touches_the_runner_tree(upgrade_sandbox) -> None:
    """ITEM 1's whole purpose, executed: both attempts return an error page, so the baked tree
    survives INTACT and still reports its own version.

    The old guard was `[ -s file ]`, which an HTML error page satisfies, and the next line ran
    `tar -xzf` over the live /opt/runner. So the old behaviour on this exact input was a
    half-overwritten runner -- worse than no upgrade, and invisible. Asserting the version is
    still the baked one is what proves the refusal is real rather than merely logged.
    """
    _write_payloads(upgrade_sandbox, good_on=99)
    lines, proc = _run_upgrade(upgrade_sandbox)
    assert proc.returncode == 0, proc.stderr
    assert len([l for l in lines if "sha256=MISMATCH" in l]) == 2, lines
    assert not any("runner-upgrade-extract" in l and " ok" in l for l in lines), lines
    assert any("ABANDONED after 2 attempts" in l for l in lines), lines
    assert _kv(lines, "UPGRADE_OK") == "0", lines
    assert _kv(lines, "FINAL_VERSION") == _BAKED, (
        f"the corrupt tarball reached /opt/runner: {lines}"
    )


def test_behaviour_a_checksum_of_valid_gzip_that_is_not_a_tarball_is_still_caught(upgrade_sandbox) -> None:
    """Verification is not a gzip check wearing a costume.

    Here the published checksum is computed over the HTML error page itself, so the bytes MATCH
    and gzip-ness is not the question -- the extraction is what fails. Proves the two guards are
    independent: a matching digest does not license a broken archive, and the retry+abandon path
    still catches it.
    """
    bad = upgrade_sandbox["root"] / "bad.bin"
    # good_on=99 so the SERVED bytes are the error page, and the published checksum is computed
    # over that same page -- so verification passes and the archive is what fails. Serving the
    # good tarball here would produce a MISMATCH instead and test the other case twice.
    _write_payloads(upgrade_sandbox, good_on=99,
                    checksum=hashlib.sha256(bad.read_bytes()).hexdigest())
    lines, proc = _run_upgrade(upgrade_sandbox)
    assert proc.returncode == 0, proc.stderr
    assert any("sha256=MATCH" in l for l in lines), lines
    assert any("runner-upgrade-extract" in l and "FAILED" in l for l in lines), lines
    assert _kv(lines, "UPGRADE_OK") == "0", lines
    assert any("ABANDONED" in l for l in lines), lines
    assert _kv(lines, "FINAL_VERSION") == _BAKED, lines


def test_behaviour_no_checksum_falls_back_to_gzip_and_says_so(upgrade_sandbox) -> None:
    """The degraded path, executed: downloads endpoint empty, so releases/latest supplies the
    version and there is no digest to compare. A valid gzip is accepted -- and labelled
    UNAVAILABLE, never as a silent pass."""
    _write_payloads(upgrade_sandbox, downloads=False, good_on=1)
    lines, proc = _run_upgrade(upgrade_sandbox)
    assert proc.returncode == 0, proc.stderr
    assert any("fell back to releases/latest" in l for l in lines), lines
    verdict = [l for l in lines if "runner-upgrade-download" in l]
    assert verdict and "sha256=UNAVAILABLE gzip=VALID" in verdict[0], verdict
    assert _kv(lines, "UPGRADE_OK") == "1", lines
    assert _kv(lines, "FINAL_VERSION") == _CURRENT, lines


def test_behaviour_no_checksum_and_a_corrupt_body_is_refused(upgrade_sandbox) -> None:
    """The same degraded path with a bad body: gzip=INVALID, refused, tree intact. This is the
    exact input the old `[ -s file ]` guard waved through."""
    _write_payloads(upgrade_sandbox, downloads=False, good_on=99)
    lines, proc = _run_upgrade(upgrade_sandbox)
    assert proc.returncode == 0, proc.stderr
    assert any("sha256=UNAVAILABLE gzip=INVALID" in l for l in lines), lines
    assert any("refusing to extract" in l for l in lines), lines
    assert _kv(lines, "FINAL_VERSION") == _BAKED, lines


def test_behaviour_the_right_asset_is_selected_for_the_arch(upgrade_sandbox) -> None:
    """The downloads payload carries osx as well as linux, and the linux entry's neighbour has a
    different digest. Selecting the wrong one would verify against a checksum the downloaded
    bytes can never match -- a permanent, self-inflicted MISMATCH."""
    _write_payloads(upgrade_sandbox, good_on=1)
    lines, proc = _run_upgrade(upgrade_sandbox)
    assert proc.returncode == 0, proc.stderr
    assert any(f"sha256=MATCH" in l for l in lines), lines
    assert not any("deadbeef" in l for l in lines), lines
    start = next(l for l in lines if "runner-upgrade-start" in l)
    assert "checksum=present" in start, start


def test_behaviour_a_url_without_a_version_segment_still_verifies(upgrade_sandbox) -> None:
    """The filename fallback, executed rather than asserted about.

    Same asset, same checksum, but the URL carries no `/v<version>/` segment -- the shape change
    that used to empty WANT and drop the whole boot onto the unverifiable fallback path. The
    assertion that matters is `checksum=present`: verification survived, which is the thing the
    fallback would have cost.
    """
    _write_payloads(
        upgrade_sandbox, good_on=1,
        url="https://objects.example.invalid/runner/actions-runner-linux-x64-2.337.0.tar.gz",
    )
    lines, proc = _run_upgrade(upgrade_sandbox)
    assert proc.returncode == 0, proc.stderr
    start = next(l for l in lines if "runner-upgrade-start" in l)
    assert f"want={_CURRENT}" in start and "checksum=present" in start, start
    assert not any("fell back to releases/latest" in l for l in lines), lines
    assert any("sha256=MATCH" in l for l in lines), lines
    assert _kv(lines, "FINAL_VERSION") == _CURRENT, lines


def test_behaviour_an_already_current_runner_is_not_downgraded_or_redownloaded(upgrade_sandbox) -> None:
    """UPGRADE_NEEDED must stay false when HAVE == WANT, so a fleet whose image is current pays
    no download at all. Baked tree pre-set to the offered version."""
    _write_payloads(upgrade_sandbox, good_on=1)
    _stub(upgrade_sandbox["root"] / "opt-runner" / "bin", "Runner.Listener",
          f'#!/bin/sh\necho "{_CURRENT}"\n')
    lines, proc = _run_upgrade(upgrade_sandbox)
    assert proc.returncode == 0, proc.stderr
    assert any("runner-upgrade-skip" in l for l in lines), lines
    assert not any("runner-upgrade-download" in l for l in lines), lines
    assert (upgrade_sandbox["root"] / "attempts").read_text().strip() == "0", (
        "an asset was downloaded for a runner that was already current"
    )


# ================= the telemetry flush: a dead sink must not be indistinguishable from a live one


def _flush_body(which: str = "CLOUD_INIT_FAST") -> str:
    """The Python source of the bootstrap's `up()` telemetry flush, verbatim from the render.

    Lifted out of the heredoc rather than retyped, so what is executed here is what a worker
    executes. The `PY` terminator is matched exactly, which also means a template that lost the
    terminator yields nothing and the caller fails loudly instead of testing a fragment.
    """
    lines = _bootstrap(which).splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("up(){ python3 - <<PY"))
    end = next(i for i, l in enumerate(lines) if l.strip() == "PY" and i > start)
    body = "\n".join(lines[start + 1:end])
    assert body.strip(), f"{which}: the flush heredoc came out empty"
    return body


def _run_flush(tmp_path, monkeypatch, *, which, exc=None, gist_id="abc123def456"):
    """Execute the real flush against relocated paths, with urlopen stubbed to `exc`."""
    import urllib.error
    import urllib.request

    gist_file = tmp_path / "gist.id"
    boot_log = tmp_path / "boot.log"
    gist_file.write_text(gist_id + "\n")
    boot_log.write_text("T=1 +1s fast-bootstrap-start vm=ci-az-1-2\n")

    calls: list[str] = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        if exc is not None:
            raise exc
        class _R:
            status = 200

            def read(self):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _R()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    src = (_flush_body(which)
           .replace("/root/gist.id", str(gist_file))
           .replace("/root/boot.log", str(boot_log)))
    assert "/root/" not in src, "a path was not relocated; the flush would touch the host"
    exec(compile(src, f"<up:{which}>", "exec"), {})  # noqa: S102 -- the text under test
    return boot_log.read_text(), calls


def test_behaviour_a_rate_limited_flush_is_recorded_not_swallowed(tmp_path, monkeypatch) -> None:
    """THE MEASURED FAILURE. On a live worker at 2026-09-16T22:50:42Z the flush returned:

        HTTPError 403 {"message": "API rate limit exceeded for user ID 79715912. ..."}

    and `up()` answered `except Exception: pass`. So the sink #997 added to make failures
    diagnosable had been silently dead: every worker gist in the org read "init" while the
    corresponding /root/boot.log held the full story -- including one worker whose local log had
    1688 bytes of successful registration and whose gist said nothing at all. A pointer to an
    empty gist is worse than no pointer, because it looks authoritative.
    """
    import urllib.error

    err = urllib.error.HTTPError("https://api.github.com/gists/abc123def456", 403,
                                 "Forbidden", {}, None)
    log, calls = _run_flush(tmp_path, monkeypatch, which="CLOUD_INIT_FAST", exc=err)
    assert calls, "the flush never attempted the PATCH"
    assert "telemetry-flush-FAILED http=403" in log, log
    assert "abc123def456" in log, log


@pytest.mark.parametrize("which", ["CLOUD_INIT_FAST", "CLOUD_INIT"])
def test_behaviour_both_templates_report_a_failed_flush(tmp_path, monkeypatch, which) -> None:
    """Both templates, because both have a sink and both had the same `pass`."""
    import urllib.error

    err = urllib.error.HTTPError("https://api.github.com/gists/x", 403, "Forbidden", {}, None)
    log, _ = _run_flush(tmp_path, monkeypatch, which=which, exc=err)
    assert "telemetry-flush-FAILED http=403" in log, f"{which}: {log}"


def test_behaviour_a_non_http_flush_failure_is_also_recorded(tmp_path, monkeypatch) -> None:
    """A DNS failure or a timeout is a different cause than a 403 and must not be flattened into
    silence either; the exception TYPE is the part worth keeping."""
    log, _ = _run_flush(tmp_path, monkeypatch, which="CLOUD_INIT_FAST",
                        exc=OSError("temporary failure in name resolution"))
    assert "telemetry-flush-FAILED OSError" in log, log


def test_behaviour_a_successful_flush_writes_no_failure_note(tmp_path, monkeypatch) -> None:
    """The note has to be conditional, or it becomes noise that hides the real failures."""
    log, calls = _run_flush(tmp_path, monkeypatch, which="CLOUD_INIT_FAST")
    assert calls and "telemetry-flush-FAILED" not in log, log


def test_behaviour_a_missing_gist_id_is_reported_as_unknown(tmp_path, monkeypatch) -> None:
    """If creation failed, /root/gist.id may not exist. The flush must still report, naming the
    failure rather than dying on the open() -- and must not name a bogus id."""
    import urllib.error

    err = urllib.error.HTTPError("https://api.github.com/gists/x", 403, "Forbidden", {}, None)
    gist_file = tmp_path / "gist.id"
    boot_log = tmp_path / "boot.log"
    boot_log.write_text("start\n")
    assert not gist_file.exists()

    import urllib.request

    def fake_urlopen(req, timeout=None):
        raise err

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    src = (_flush_body("CLOUD_INIT_FAST")
           .replace("/root/gist.id", str(gist_file))
           .replace("/root/boot.log", str(boot_log)))
    exec(compile(src, "<up:missing-id>", "exec"), {})  # noqa: S102
    log = boot_log.read_text()
    assert "telemetry-flush-FAILED" in log and "gist=unknown" in log, log


@pytest.mark.parametrize("which", ["CLOUD_INIT_FAST", "CLOUD_INIT"])
def test_the_flush_failure_note_cannot_carry_the_token(which: str) -> None:
    """boot.log is uploaded to a gist, so it is a secret-bearing channel. The note is built from
    the HTTP code and the gist id only -- the same discipline the token-fetch stage applies by
    logging `${#TOKEN}` rather than the value."""
    body = _flush_body(which)
    notes = [l for l in body.splitlines() if "telemetry-flush-FAILED" in l]
    assert notes, f"{which} has no flush-failure note"
    for n in notes:
        assert "$TOK" not in n and "tok" not in n.lower(), n


@pytest.mark.parametrize("which", ["CLOUD_INIT_FAST", "CLOUD_INIT"])
def test_no_bare_except_pass_remains_in_the_flush(which: str) -> None:
    """The exact shape that hid a dead sink for the whole life of #997. Pinned per template so it
    cannot come back as a "simplification"."""
    body = _flush_body(which)
    assert not re.search(r"except Exception:\s*\n\s*pass", body), (
        f"{which} still swallows flush errors silently"
    )
    assert "urllib.error" in body, f"{which} cannot distinguish an HTTP failure: {body}"
