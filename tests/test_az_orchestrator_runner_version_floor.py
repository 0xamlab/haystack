"""The 2026-09-16 total-plane-outage fix, and the telemetry that should have made it a 5-minute
diagnosis instead of a nine-hour one.

WHAT HAPPENED. GitHub Actions enforces a MINIMUM self-hosted-runner version at REGISTRATION
time: below the floor, POST /actions/runner-registration answers 404 with a "RUNNER UPDATE
REQUIRED" box. config.sh then exits non-zero, run.sh reports "Not configured" and exits, and
bootstrap.sh falls through to its final `shutdown -h now`. The worker powers itself off looking
exactly like one that finished its job. GitHub moved the floor to 2.329.0 over a golden image
that bakes actions/runner 2.327.1 (captured 2026-08-26), and from ~07:00Z every worker in the
fleet died that way. Nothing registered, so every queued job sat forever.

WHY IT TOOK HOURS. The golden-image path (CLOUD_INIT_FAST) -- the path every real worker takes,
in all 8 regions -- had NO telemetry. The stock path PATCHes /root/boot.log to a per-worker
private gist and always had; the fast path wrote nothing at all. So on every corpse
/root/boot.log was empty, which reads as "bootstrap never ran" and sent the investigation at
cloud-init, at the tier0 repair block, and at a suspected cost watchdog baked into the image.
All three were innocent. The failure message existed only in a cloud-init log on a VM that had
already deleted itself.

Reproduced verbatim on a live Standard_D8s_v5 created from gallery version 1.0.0 in centralus,
running the deployed bootstrap under `bash -x`:

    18:20:13 + TOKEN=...                              <- token fetch FINE, 200 in 0.28s
    18:20:36 + timeout 120 ... apt-get install unzip  <- tier0 repair FINE
    18:20:52 + su - runner -c "/opt/runner/config.sh ..."
    18:21:06 Http response code: NotFound from 'POST .../actions/runner-registration'
    18:21:06 ERROR: Your runner version is out of date and can no longer register with GitHub.
    18:21:06 The minimum runner version required to register is now 2.329.0.
    18:21:06 An error occurred: Not configured. Run config.(sh/cmd) to configure the runner.
    18:21:06 + shutdown -h now

Upgrading that same VM to 2.337.0 and re-running config.sh registered it immediately
("Runner successfully added", rc=0) -- the whole of the causal proof, on one machine.

THE FIX. Resolve actions/runner releases/latest at boot and upgrade in place. A version pinned
inside a FROZEN image is a time bomb whose fuse GitHub holds, and recapturing the image only
resets the fuse -- today's floor is 2.329.0 and it will move again. Measured on that worker:
the lookup costs 0.17s and the 226 MB tarball downloads in 1.8s in centralus, so the stage is
~8s against a ~55s bootstrap.

These tests pin the fix, the telemetry, and the two supporting gates (render_userdata, and the
VM-before-NIC delete ordering that leaked a NIC per corpse during the churn).
"""

from __future__ import annotations

import ast
import importlib.util
import re
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "infra" / "ci" / "az_orchestrator.py"

# The version GitHub refused on 2026-09-16, and the one proven to register.
_OUTDATED = "2.327.1"
_PROVEN = "2.337.0"


def _load(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("GITHUB_CI_TOKEN", "test-token")
    spec = importlib.util.spec_from_file_location("az_orch_version_floor_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def _templates() -> dict[str, str]:
    """The two cloud-init templates, straight out of the source AST.

    Parsed rather than imported so a syntax error in the module cannot masquerade as a missing
    template, and so these tests keep working on the raw text a worker actually receives.
    """
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
    for key, val in {
        "__SSH_PUB__": "ssh-ed25519 AAAAfakekey operator@host",
        "__GH_TOKEN__": "gho_FAKETOKENFAKETOKENFAKETOKENFAKETOK12",
        "__ORG__": "thyn-ai",
        "__RUNNERGROUP__": "az-ephemeral-pool",
        "__VMNAME__": name,
        "__RUNNER_PIN__": _PROVEN,
    }.items():
        doc = doc.replace(key, val)
    return doc


def _bootstrap(tpl: str) -> str:
    """The /root/bootstrap.sh a worker actually gets, after cloud-init parses the document."""
    parsed = yaml.safe_load(_render(tpl))
    files = {f["path"]: f["content"] for f in parsed.get("write_files", [])}
    return files["/root/bootstrap.sh"]


def _code(text: str) -> str:
    """COMMENTS STRIPPED FIRST, for the reason test_ci_image_contract.py already spells out.

    A substring check over the raw text passes (or fails) on explanatory prose, so it does not
    describe the machine. Both directions bite here: the post-mortem comment deliberately names
    runner 2.327.1 and the header comment deliberately says "NO `set -e`", so an unstripped
    assertion would fail on the documentation of the bug rather than on the bug.
    """
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


# --------------------------------------------------------------------------- the version floor


def test_the_fast_path_resolves_the_runner_version_at_boot() -> None:
    """No pinned runner version survives on the path real workers take.

    A literal version in the template is the same bomb as one baked into the image; it just
    detonates on the next stock-image provision instead of the next golden-image one.
    """
    code = _code(_bootstrap(_templates()["CLOUD_INIT_FAST"]))
    assert "repos/actions/runner/releases/latest" in code, (
        "CLOUD_INIT_FAST no longer resolves the current runner release at boot, so the fleet is "
        "one GitHub floor-raise away from a total outage again"
    )
    assert _OUTDATED not in code, f"the fast path still pins runner {_OUTDATED}"


def test_neither_template_hardcodes_the_outdated_runner() -> None:
    """The stock path pinned v2.327.1 too -- the floor caught both, so both must resolve."""
    for name, tpl in _templates().items():
        assert _OUTDATED not in _code(tpl), f"{name} still pins runner {_OUTDATED}"


def test_the_stock_path_keeps_a_working_pin_as_fallback() -> None:
    """A GitHub API outage must not make the stock path undownloadable.

    The fallback is the version PROVEN to register, not a preference -- and it must sit at or
    above the floor, or the fallback IS the outage.
    """
    mod_source = _TOOL.read_text()
    pin = re.search(r'^RUNNER_PIN = "([^"]+)"', mod_source, re.M)
    assert pin, "RUNNER_PIN is gone; the stock path has no fallback if releases/latest fails"
    assert pin.group(1) == _PROVEN
    # The template must actually reach for it, and must not carry a stale literal of its own.
    tpl = _templates()["CLOUD_INIT"]
    assert "__RUNNER_PIN__" in tpl, "CLOUD_INIT no longer falls back to RUNNER_PIN"
    rendered = _render(tpl)
    assert _PROVEN in rendered, "the RUNNER_PIN fallback did not reach the rendered bootstrap"
    assert "RUNNER_VERSION=$(curl" in _bootstrap(tpl), (
        "CLOUD_INIT no longer resolves the runner version at boot"
    )


def test_the_upgrade_happens_before_the_runner_configures_itself() -> None:
    """Ordering is the whole fix: upgrading after config.sh is decorating a corpse.

    Same class of bug the image-contract test pins for the tier0 repair -- a fix that lands
    after the step it was meant to protect.
    """
    boot = _bootstrap(_templates()["CLOUD_INIT_FAST"])
    upgrade = boot.find("releases/latest")
    configure = boot.find("config.sh --url")
    assert upgrade != -1 and configure != -1
    assert upgrade < configure, "the runner is configured before it is upgraded"


def test_a_failed_upgrade_still_attempts_registration() -> None:
    """The upgrade must degrade, not gate.

    If releases/latest is unreachable the baked runner stays and config.sh is still attempted,
    so a GitHub API outage costs the previous behaviour instead of introducing a new failure.
    Pinned as: no `exit` between the upgrade stage and the config stage.
    """
    boot = _bootstrap(_templates()["CLOUD_INIT_FAST"])
    between = boot[boot.find("runner_version()"):boot.find("config.sh --url")]
    assert "exit " not in between, f"the upgrade stage can abort the boot: {between!r}"


def test_the_arch_is_detected_rather_than_assumed_x64() -> None:
    """Asset names spell amd64 as x64 and arm64 as arm64; dpkg does not agree with either.

    Hardware-agnostic by construction: a future arm64 worker must not download an x64 runner.
    """
    boot = _bootstrap(_templates()["CLOUD_INIT_FAST"])
    assert "dpkg --print-architecture" in boot
    assert "actions-runner-linux-${RARCH}-${WANT}.tar.gz" in boot


# ----------------------------------------------------------------------------- the telemetry


_STAGES = (
    "token-fetch",
    "repair-start",
    "repair-done",
    "runner-upgrade",
    "config-rc",
    "run-started",
)


def test_the_fast_path_reports_every_stage_to_the_gist_sink() -> None:
    """The nine hours this outage cost were entirely a telemetry gap.

    The stock path has always PATCHed /root/boot.log to a per-worker private gist; the golden
    path wrote nothing, so every corpse looked like "bootstrap never ran". Each stage below is
    a marker an operator can grep for, in order, from a machine that no longer exists.
    """
    boot = _bootstrap(_templates()["CLOUD_INIT_FAST"])
    assert "api.github.com/gists" in boot, "the fast path has no gist sink"
    offsets = []
    for stage in _STAGES:
        at = boot.find(stage)
        assert at != -1, f"no {stage!r} stage marker in CLOUD_INIT_FAST"
        offsets.append(at)
    assert offsets == sorted(offsets), f"stage markers out of order: {list(zip(_STAGES, offsets))}"


def test_the_token_is_never_written_to_the_log() -> None:
    """boot.log is PATCHed to a gist, so it is a secret-bearing channel.

    The LENGTH is logged because len=0 is the diagnostic (fetch failed vs parse failed vs
    succeeded); the value must never be. `${#TOKEN}` and `$TOK_RC` are the two legitimate
    neighbours of the secret and are deliberately allowed through.
    """
    code = _code(_bootstrap(_templates()["CLOUD_INIT_FAST"]))
    bare_secret = re.compile(r"\$\{?TOKEN\}?|\$\{?TOK\}?(?!_)")
    offenders = [l.strip() for l in code.splitlines()
                 if l.strip().startswith("log ") and bare_secret.search(l)]
    assert not offenders, f"a log line interpolates the token value: {offenders}"
    assert "len=${#TOKEN}" in code, "the token-fetch stage no longer reports its length"
    # The config.sh line redirects into boot.log, so its output is uploaded. config.sh does not
    # echo its --token argument, but the redirect means anything it DID print would be public
    # to the gist's readers -- which is why the token is passed as an argument and never as an
    # environment variable a child might dump.
    cfg = next(l for l in code.splitlines() if "config.sh --url" in l)
    assert ">>/root/boot.log" in cfg and "--token '$TOKEN'" in cfg


def test_config_output_is_captured_where_an_operator_can_read_it() -> None:
    """"RUNNER UPDATE REQUIRED" was invisible for nine hours.

    It went to a cloud-init log on a VM that had already deleted itself. Redirecting config.sh
    into boot.log -- which is uploaded -- is the difference between "the fleet is dark" and
    "the fleet is dark because GitHub says X".
    """
    boot = _bootstrap(_templates()["CLOUD_INIT_FAST"])
    line = next(l for l in boot.splitlines() if "config.sh --url" in l)
    assert "/root/boot.log" in line, f"config.sh output is not captured: {line!r}"
    assert "2>&1" in line, f"config.sh stderr is not captured: {line!r}"


def test_a_failed_registration_is_reported_before_the_machine_goes() -> None:
    """The final `shutdown -h now` must never be the first evidence of a failure."""
    boot = _bootstrap(_templates()["CLOUD_INIT_FAST"])
    report = boot.find("config-failed")
    shutdown = boot.find("shutdown -h now", report)
    assert report != -1 and shutdown != -1 and report < shutdown


def test_registration_is_retried_with_a_fresh_token() -> None:
    """Two attempts, and the retry re-fetches rather than replaying a spent token.

    Not a loop: if GitHub is refusing registration a third attempt will not change the answer,
    and burning boot time only delays the report that says so.
    """
    boot = _bootstrap(_templates()["CLOUD_INIT_FAST"])
    assert "for attempt in 1 2; do" in boot
    assert boot.count("get_token") >= 3, "the retry does not re-fetch the token"


def test_nothing_in_the_bootstrap_can_abort_before_config() -> None:
    """No `set -e`, and no unguarded exit ahead of the registration attempt.

    Every step before config.sh is a best-effort repair. Aborting early is how a 54-second
    failure became an undiagnosable outage. Comment-stripped, because the header comment names
    `set -e` in order to say it is deliberately absent.
    """
    code = _code(_bootstrap(_templates()["CLOUD_INIT_FAST"]))
    assert "set -e" not in code
    head = code[:code.find("config.sh --url")]
    assert "exit " not in head, "the bootstrap can exit before it ever tries to register"


# ---------------------------------------------------------------------- rendered-userdata gate


def test_both_templates_render_to_valid_parseable_userdata() -> None:
    """The gate that caught a real bug in the fix that introduced it.

    Writing the version comparison as `printf '%s\\n%s\\n'` inside a plain (non-raw) Python
    triple-quoted string turned the backslash-n into a REAL newline, split the shell line, and
    ended the YAML block scalar -- which is exactly the "invalid YAML, runcmd never runs, every
    worker is a no-op VM" failure this plane has already paid for once. render_userdata() is
    what caught it before it shipped, and this test is what keeps catching it.
    """
    for name, tpl in _templates().items():
        doc = _render(tpl)
        assert doc.isascii(), f"{name} is not ASCII; customData is latin-1 transported"
        assert not re.findall(r"__[A-Z_]+__", doc), f"{name} left a placeholder unsubstituted"
        parsed = yaml.safe_load(doc)
        assert any("/root/bootstrap.sh" in str(c) for c in parsed["runcmd"]), name
        boot = _bootstrap(tpl)
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
            fh.write(boot)
            path = fh.name
        proc = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
        assert proc.returncode == 0, f"{name} bootstrap.sh does not parse: {proc.stderr}"


def test_render_userdata_rejects_a_document_that_lost_the_bootstrap(monkeypatch, tmp_path) -> None:
    """Valid YAML is not sufficient: the bootstrap can be validly absent."""
    mod = _load(monkeypatch)
    with pytest.raises(ValueError, match="bootstrap"):
        mod.render_userdata("#cloud-config\nruncmd:\n  - echo hi\n", "ci-az-1-1",
                            str(tmp_path / "x.yml"))


def test_render_userdata_rejects_non_ascii(monkeypatch, tmp_path) -> None:
    mod = _load(monkeypatch)
    tpl = _templates()["CLOUD_INIT_FAST"].replace("fast-bootstrap-start", "start \u2014 now")
    with pytest.raises(ValueError, match="not ASCII"):
        mod.render_userdata(tpl, "ci-az-1-1", str(tmp_path / "x.yml"))


def test_render_userdata_writes_a_gated_document(monkeypatch, tmp_path) -> None:
    mod = _load(monkeypatch)
    out = tmp_path / "worker.yml"
    got = mod.render_userdata(mod.CLOUD_INIT_FAST, "ci-az-1-1", str(out))
    assert got == str(out) and out.exists()
    doc = out.read_text()
    assert "ci-az-1-1" in doc and "config.sh --url" in doc
    assert yaml.safe_load(doc)["runcmd"] == ["bash /root/bootstrap.sh"]


# ------------------------------------------------------------------- VM-before-NIC teardown


def test_delete_vm_waits_for_the_vm_before_touching_the_nic(monkeypatch) -> None:
    """The leak behind the incident's orphaned NICs.

    ARM deletes are async, so firing VM and NIC deletes back to back fails the NIC with
    NicInUse and leaks it -- nothing retries. Observed at 13:23:18.509 on 2026-08-26 and again
    seven times during the 2026-09-16 churn, once per self-powered-off corpse.
    """
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "log", lambda m: None)
    calls: list[str] = []
    monkeypatch.setattr(mod, "arm", lambda m, p, *a, **k: calls.append(f"{m} {p.split('/')[-1]}") or {})
    waited: list[str] = []
    monkeypatch.setattr(mod, "_wait_gone", lambda p, api, timeout=90: waited.append(p) or True)
    monkeypatch.setattr(mod, "_exists", lambda p, api: True)

    mod.delete_vm("ci-az-1-1", "centralus", reason="test")

    assert calls == ["DELETE ci-az-1-1", "DELETE ci-az-1-1-centralus-nic"], calls
    assert waited and waited[0].endswith("virtualMachines/ci-az-1-1"), waited
    # The wait must be BOUNDED and must precede the NIC delete: cleanup() runs on the reconcile
    # thread, so an unbounded wait per VM would stall the backstop.
    assert mod.VM_DELETE_WAIT_S <= 120


def test_delete_vm_leaves_the_nic_to_the_sweep_when_the_vm_will_not_go(monkeypatch) -> None:
    """On timeout the NIC delete is SKIPPED, not attempted-and-doomed.

    The leaked-nic sweep is the backstop for exactly this and has the two-poll _absent_once
    guard, so skipping costs one cycle of latency and avoids an error that reads like a new
    failure mode.
    """
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "log", lambda m: None)
    calls: list[str] = []
    monkeypatch.setattr(mod, "arm", lambda m, p, *a, **k: calls.append(f"{m} {p.split('/')[-1]}") or {})
    monkeypatch.setattr(mod, "_wait_gone", lambda p, api, timeout=90: False)
    monkeypatch.setattr(mod, "_exists", lambda p, api: True)

    mod.delete_vm("ci-az-1-1", "centralus", reason="test")

    assert calls == ["DELETE ci-az-1-1"], calls


def test_delete_vm_does_not_404_the_nic_when_the_cascade_took_it(monkeypatch) -> None:
    """deleteOption=Delete means ARM usually removes the NIC with the VM.

    Deleting it again anyway logged a 404 on every teardown, which is the noise that hides the
    real NicInUse.
    """
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "log", lambda m: None)
    calls: list[str] = []
    monkeypatch.setattr(mod, "arm", lambda m, p, *a, **k: calls.append(f"{m} {p.split('/')[-1]}") or {})
    monkeypatch.setattr(mod, "_wait_gone", lambda p, api, timeout=90: True)
    monkeypatch.setattr(mod, "_exists", lambda p, api: False)

    mod.delete_vm("ci-az-1-1", "centralus", reason="test")

    assert calls == ["DELETE ci-az-1-1"], calls
