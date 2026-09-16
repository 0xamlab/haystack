"""The tier0 repair race: wait for the dpkg lock, retry once, then PROVE the verdict per tool.

WHAT WAS OBSERVED. Two workers booting in the same minute on 2026-09-16, both created from the
same gallery image version 1.0.0, reported opposite results for the same tier0 guarantee: one
had unzip and gh, the other had NEITHER. The suspected cause is contention on
/var/lib/dpkg/lock-frontend early in boot -- cloud-init runs its own package work concurrently
with the repair block, and an `apt-get install` that loses that race exits non-zero in
milliseconds.

SUSPECTED, NOT PROVEN, and this file does not pretend otherwise. What IS proven is that the old
block could not tell the two apart and told nobody: one attempt, every diagnostic redirected to
/dev/null, no re-probe, and a single `repair-done` line printing whatever `command -v` happened
to return at that instant. A VM that came up without gh therefore looked identical in telemetry
to one that came up with it, right up to the moment a job died with `gh: command not found`
(exit 127) -- the failure codna's auto-release-cli already hit once, on a VM that HAD the repair.

THE HARDENING, in three parts, each gated below:
  1. WAIT for the lock (bounded `flock -w`), best-effort -- a boot is never gated on a lock.
  2. RETRY the install once, driven by a re-probe rather than by an exit code, under its own
     hard ceiling.
  3. RE-VERIFY every tier0 tool individually and NAME anything still missing in the gist
     telemetry. Never silent: the whole cost of this bug class is that it is invisible.

The last group of tests EXECUTES the real repair block in a hermetic shell, so "the retry
recovers a lock-contention failure" is a measured result rather than a reading of the text.

AND THE BOUND. The repair BLOCKS runner registration by design (see
[notes].repair_blocks_registration in infra/ci/image/manifest.toml), so latency added here is
paid on every cold provision. tier0_repair_added_s() states the arithmetic -- two lock waits
plus one retry pass -- and the tests pin it to 90s AND pin the shell literals to the Python
constants, because CLOUD_INIT_FAST has to stay a plain string constant (the
runner-version-floor tests lift it straight out of the module AST) and so the numbers exist in
two places that can drift.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "infra" / "ci" / "az_orchestrator.py"

# Every tier0 tool the per-boot repair INSTALLS. `python` appears in the verdict line but not
# here: it is a symlink the bootstrap creates before the repair runs, not an apt package, so it
# is never part of an install attempt.
_REPAIRED = ("unzip", "rsync", "gh")


def _load(monkeypatch=None):
    """The module, imported by path like every other orchestrator test in this directory.

    Env is defaulted rather than required: the budget constants and the templates are what these
    tests read, and none of them depend on real Azure credentials.
    """
    for key in ("AZURE_SUBSCRIPTION_ID", "AZURE_TENANT_ID"):
        os.environ.setdefault(key, "00000000-0000-0000-0000-000000000000")
    os.environ.setdefault("GITHUB_CI_TOKEN", "test-token")
    spec = importlib.util.spec_from_file_location("az_orch_tier0_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- template access


def _templates() -> dict[str, str]:
    """Both cloud-init templates, lifted out of the module AST.

    Parsed rather than imported for the reason test_az_orchestrator_runner_version_floor.py
    gives, and with one extra consequence worth stating: it also proves CLOUD_INIT_FAST is still
    a plain string CONSTANT. A worker receives that exact text, so rebuilding it from parts at
    render time would make "what the fleet runs" a function of code this gate never reads.
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


def _bootstrap() -> str:
    """The /root/bootstrap.sh a golden-image worker receives, after cloud-init parses the
    document and strips the block-scalar indent."""
    doc = _templates()["CLOUD_INIT_FAST"]
    for key, val in {
        "__SSH_PUB__": "ssh-ed25519 AAAAfakekey operator@host",
        "__GH_TOKEN__": "gho_FAKETOKENFAKETOKENFAKETOKENFAKETOK12",
        "__ORG__": "thyn-ai",
        "__RUNNERGROUP__": "az-ephemeral-pool",
        "__VMNAME__": "ci-az-1234-5678",
        "__RUNNER_PIN__": "2.337.0",
    }.items():
        doc = doc.replace(key, val)
    parsed = yaml.safe_load(doc)
    files = {f["path"]: f["content"] for f in parsed.get("write_files", [])}
    return files["/root/bootstrap.sh"]


def _repair_block() -> str:
    """Just the repair stage: `log "repair-start"` up to (not including) the `up` that ships it.

    Located by marker rather than by line number so the slice survives edits above it, and taken
    from the RENDERED bootstrap rather than from the Python source -- asserting against the
    source would let a template that never renders keep passing, which is the dead-on-arrival
    mistake tests/test_ci_image_contract.py exists to catch.
    """
    lines = _bootstrap().splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == 'log "repair-start"')
    incomplete = next(i for i, l in enumerate(lines) if "repair-incomplete" in l and i > start)
    end = next(i for i, l in enumerate(lines) if l.strip() == "up" and i > incomplete)
    return "\n".join(lines[start:end + 1])  # inclusive: shipping the telemetry IS the last step


def _fast_path_source() -> str:
    src = _TOOL.read_text()
    return src[src.index('CLOUD_INIT_FAST = """'):]


def _code(text: str) -> str:
    """Comments stripped, because a substring check over raw text describes the prose, not the
    machine. This block is deliberately over-commented -- several comments name the tools and
    the failure -- so an unstripped assertion can pass on documentation alone."""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


# ---------------------------------------------------------------------- the latency budget


def test_the_hardening_adds_at_most_ninety_seconds_to_a_boot() -> None:
    """The bound as arithmetic rather than as a promise in a comment.

    Two bounded lock waits (one per attempt) plus one bounded retry pass. The pre-existing
    install timeouts are NOT counted: they were already this block's worst case before the
    hardening, so they are not added by it.
    """
    mod = _load()
    added = mod.tier0_repair_added_s()
    assert added == 2 * mod.TIER0_LOCK_WAIT_S + mod.TIER0_RETRY_BUDGET_S
    assert mod.TIER0_ADDED_BUDGET_S == 90
    assert added <= mod.TIER0_ADDED_BUDGET_S, (
        f"the tier0 hardening now adds {added}s worst case, over the "
        f"{mod.TIER0_ADDED_BUDGET_S}s budget. Retune the waits or re-justify the number."
    )
    # Scaling either knob must move the answer, or the function is a constant wearing a name.
    assert mod.tier0_repair_added_s(lock_wait=10, retry=5) == 25


def test_the_retry_is_capped_as_a_pass_not_per_package() -> None:
    """One ceiling for the whole retry, so a boot missing all three tools pays it once.

    A per-package cap would triple silently the day a fourth tier0 tool is declared -- and
    infra/ci/image/manifest.toml, not this file, decides how many there are.
    """
    block = _code(_repair_block())
    # `$((` is arithmetic expansion, so the deadline line reads RETRY_BY=$(( $(date +%s) + N )).
    deadline = re.search(r"RETRY_BY=\$\(\(\s*\$\(date \+%s\) \+ (\d+)\s*\)\)", block)
    assert deadline, f"no shared retry deadline in the repair block:\n{block}"
    bounded = re.findall(r'timeout "\$\(secs_left "\$RETRY_BY"\)"', block)
    assert len(bounded) == 2, (
        f"expected both retry installs under the shared deadline, found {len(bounded)}:\n{block}"
    )
    retry = block[block.index("RETRY_BY="):block.index("ci-image-repair-done")]
    assert not re.search(r"timeout \d{3,}", retry), (
        f"the retry carries a fixed multi-hundred-second timeout of its own:\n{retry}"
    )


def test_the_shell_literals_match_the_python_budget() -> None:
    """THE DRIFT GATE. The numbers live in two places by necessity (see the module docstring),
    so a test holds them together -- otherwise tier0_repair_added_s() reports 90 while the
    worker waits 300, which is a gate certifying a machine nobody runs."""
    mod = _load()
    code = _code(_fast_path_source())
    assert f"flock -w {mod.TIER0_LOCK_WAIT_S} /var/lib/dpkg/lock-frontend" in code, (
        f"the shell does not wait {mod.TIER0_LOCK_WAIT_S}s on the dpkg frontend lock, so "
        f"tier0_repair_added_s() is describing a different machine"
    )
    retry = re.search(r"RETRY_BY=\$\(\(\s*\$\(date \+%s\) \+ (\d+)\s*\)\)", code)
    assert retry, "the shell no longer computes a retry deadline at all"
    assert int(retry.group(1)) == mod.TIER0_RETRY_BUDGET_S, (
        f"the retry deadline is {retry.group(1)}s in the shell but "
        f"TIER0_RETRY_BUDGET_S={mod.TIER0_RETRY_BUDGET_S}; tier0_repair_added_s() is now "
        f"reporting a budget no worker honours"
    )


def test_exactly_two_lock_waits_so_the_arithmetic_holds() -> None:
    """Two waits, because the budget accounts for two.

    A third call site is the easiest way to break the 90s promise without touching a number:
    wait in front of each install command and the worst case becomes three waits plus the retry.
    Counted on the rendered shell by LINE (not by string search, which cannot tell two identical
    call sites apart), definition excluded, and split one-per-attempt.
    """
    lines = _code(_repair_block()).splitlines()
    retry_at = next(i for i, l in enumerate(lines) if "RETRY_BY=" in l)
    calls = [i for i, l in enumerate(lines)
             if "wait_dpkg_lock" in l and not l.strip().startswith("wait_dpkg_lock(){")]
    assert len(calls) == 2, f"expected 2 lock-wait call sites, found {len(calls)} at {calls}"
    assert sum(1 for i in calls if i < retry_at) == 1, calls
    assert sum(1 for i in calls if i > retry_at) == 1, calls


# --------------------------------------------------------------- the shape of the hardening


def test_the_lock_wait_is_bounded_and_cannot_gate_the_boot() -> None:
    """`flock -w N` is the bound; `|| true` is the guarantee.

    An absent lockfile, a timed-out wait, or a non-root shell must all fall through to the
    install. A boot that waits forever on a lock is worse than a boot with a missing tool,
    because the missing tool is at least reported.
    """
    code = _code(_repair_block())
    line = next(l for l in code.splitlines() if l.strip().startswith("wait_dpkg_lock(){"))
    assert re.search(r"flock -w \d+ /var/lib/dpkg/lock-frontend", line), line
    assert line.rstrip().endswith("|| true; }"), (
        f"a failed lock wait can abort the repair: {line!r}"
    )


def test_the_lock_wait_only_happens_when_there_is_something_to_install() -> None:
    """A healthy boot must not pay for the hardening at all.

    flock against a lock that unattended-upgrades happens to hold costs up to the full wait, so
    the wait is gated on the probe having found something missing. Pinned as text here and as
    behaviour in test_behaviour_all_tools_present_installs_nothing_and_reports_ok.
    """
    code = _code(_repair_block())
    gated = re.search(r'if \[ -n "\$NEED" \]; then\s*\n\s*wait_dpkg_lock', code)
    assert gated, f"the first lock wait is unconditional:\n{code}"


def test_the_install_is_retried_exactly_once() -> None:
    """One retry, not a loop.

    A loop keeps spending boot latency -- which this stage charges to registration -- on a
    failure whose cause (a package that does not exist, a repo that is down) does not change
    with another attempt. The same reasoning the config stage uses for its two attempts.
    """
    block = _code(_repair_block())
    assert "attempt=2of2" in block, "the retry no longer announces itself as the last attempt"
    assert "while " not in block and "until " not in block, f"the repair grew a loop:\n{block}"
    assert block.count("RETRY_BY=") == 1
    assert block.count("STILL=$(tier0_missing)") == 1


def test_the_retry_is_driven_by_a_re_probe_not_by_an_exit_code() -> None:
    """An install can exit 0 and leave the binary absent, and can exit non-zero merely because
    the lock was held. Only looking at the filesystem again distinguishes those -- which is why
    the observed race was undiagnosable rather than merely annoying."""
    block = _code(_repair_block())
    assert block.count("tier0_missing") >= 3, (
        "expected the probe to be defined and called both before and after the first attempt"
    )
    first = block.index("NEED=$(tier0_missing)")
    still = block.index("STILL=$(tier0_missing)")
    assert first < still < block.index("RETRY_BY=")
    assert re.search(r'if \[ -n "\$STILL" \]', block), (
        "the retry is not gated on what the re-probe found"
    )
    assert "$?" not in block[first:still], "the retry decision reads an exit code somewhere"


def test_the_re_probe_covers_every_tool_the_install_does() -> None:
    """A probe checking fewer tools than the install touches is how `gh` shipped missing while
    `unzip` was verified. Per-tool literals, never a loop over a list -- the image contract test
    greps for exactly `command -v <tool>` per tier0 entry, and a loop would satisfy the shell
    while leaving that gate blind."""
    block = _code(_repair_block())
    fn = block[block.index("tier0_missing(){"):block.index("NEED=$(tier0_missing)")]
    for tool in _REPAIRED:
        assert f"command -v {tool} >/dev/null 2>&1" in fn, f"the re-probe skips {tool}:\n{fn}"
    assert "for " not in fn, f"the probe loops instead of naming tools:\n{fn}"


def test_the_retry_keeps_the_gh_repository_setup() -> None:
    """The gh retry re-runs the keyring + sources.list chain, not a bare install.

    A first attempt that died at the keyring curl leaves no sources.list.d entry for a bare
    `apt-get install gh` to succeed against, so the retry would be guaranteed to fail -- and
    would report that as "gh unavailable" rather than as "the first attempt never got as far as
    adding the repo".
    """
    block = _code(_repair_block())
    retry = block[block.index("RETRY_BY="):block.index("ci-image-repair-done")]
    assert "cli.github.com/packages" in retry and "apt-get install -y -qq gh" in retry, retry
    # The retry does not re-run `apt-get update` for the DISTRO packages: the lists are warm
    # from the first attempt, and dropping it is what makes a 30s ceiling realistic.
    distro = retry[retry.index('case "$STILL" in *unzip*'):retry.index('case "$STILL" in *gh*')]
    assert "apt-get update" not in distro, distro


# ------------------------------------------------------------------- the never-silent half


def test_every_tier0_tool_gets_its_own_verdict_in_telemetry() -> None:
    """Per-tool, in the gist, as OK or MISSING.

    The old line printed whatever `command -v` returned inline, which conflated "present at
    /usr/bin/unzip" with "absent" for any reader who did not already know the paths by heart. A
    verdict an operator can grep is the difference between a five-minute diagnosis and the nine
    hours the runner-version outage cost.
    """
    block = _code(_repair_block())
    for tool in (*_REPAIRED, "python"):
        assert re.search(rf"^V_{tool}=OK; command -v {tool} >/dev/null 2>&1 \|\| V_{tool}=MISSING$",
                         block, re.M), f"no explicit OK/MISSING verdict for {tool}"
    done = next(l for l in block.splitlines() if l.strip().startswith('log "repair-done'))
    for tool in (*_REPAIRED, "python"):
        assert f"{tool}=$V_{tool}" in done, f"{tool} is not in the verdict line: {done!r}"


def test_a_tool_still_missing_after_the_retry_is_named() -> None:
    """THE never-silent requirement, as a gate on the text.

    A tier0 tool that survives a lock wait AND a retry is a broken guarantee. It has to be named
    in the one channel that outlives the VM, rather than left for a job to discover as an exit
    127 fifty seconds in. The behavioural tests below prove the line actually fires.
    """
    block = _code(_repair_block())
    line = next(l for l in block.splitlines() if "repair-incomplete" in l)
    assert "TIER0-STILL-MISSING" in line and "$GONE" in line, line
    gathered = block[block.index('GONE=""'):block.index(line)]
    for tool in (*_REPAIRED, "python"):
        assert f'[ "$V_{tool}" = "MISSING" ] && GONE="$GONE {tool}"' in gathered, (
            f"{tool} can go missing without being named:\n{gathered}"
        )


def test_the_verdicts_are_uploaded_not_just_written_locally() -> None:
    """boot.log on the worker is worthless -- the worker deletes itself. The `up` PATCH to the
    per-worker gist is what survives, and it has to come after the verdicts are in the log."""
    lines = _repair_block().splitlines()
    verdict = max(i for i, l in enumerate(lines)
                  if "repair-done" in l or "repair-incomplete" in l)
    assert lines[-1].strip() == "up", (
        f"the repair stage no longer ends by uploading its telemetry: {lines[-1]!r}"
    )
    assert verdict < len(lines) - 1, "the telemetry is uploaded before the verdicts exist"


def test_the_repair_still_completes_before_the_runner_registers() -> None:
    """Re-pin the ordering the image contract test pins, against the NEW markers.

    Hardening a blocking stage is exactly how a stage becomes accidentally non-blocking: if any
    part of the retry moved past config.sh, a runner would advertise tier0 tools it is still
    installing -- the ci-warm-1787804191 failure, reintroduced.
    """
    boot = _bootstrap()
    offsets = {}
    for marker in ("repair-start", "repair-probe", "repair-retry", "ci-image-repair-done",
                   "repair-done", "config.sh --url"):
        at = boot.find(marker)
        assert at != -1, f"{marker!r} is gone from the fast path"
        offsets[marker] = at
    order = sorted(offsets, key=offsets.get)
    assert order == ["repair-start", "repair-probe", "repair-retry",
                     "ci-image-repair-done", "repair-done", "config.sh --url"], offsets
    assert ") &" not in boot[offsets["repair-start"]:offsets["config.sh --url"]], (
        "part of the repair is backgrounded again"
    )


def test_the_timeout_floor_is_one_because_timeout_zero_means_no_timeout() -> None:
    """`timeout 0` in coreutils means UNBOUNDED, so an exhausted budget echoed as 0 would remove
    the cap from the step it was capping -- the exact inverse of the guarantee.

    Not a hypothetical shape: secs_left computes deadline-minus-now, and a retry that has already
    spent its budget computes a negative number.
    """
    block = _code(_repair_block())
    fn = next(l for l in block.splitlines() if l.strip().startswith("secs_left(){"))
    assert '[ "$d" -gt 1 ] && echo "$d" || echo 1' in fn, fn


# ---------------------------------------------------- behavioural proof, in a hermetic shell


def _stub(dirpath: Path, name: str, body: str) -> None:
    p = dirpath / name
    p.write_text(body)
    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


_HERMETIC = ("sh", "bash", "date", "cat", "chmod", "touch")


@pytest.fixture
def sandbox(tmp_path):
    """A PATH holding nothing but what this test put there.

    Hermetic because the block probes with `command -v`, which searches PATH. On an Ubuntu CI
    worker /bin IS /usr/bin, so any PATH containing a system directory makes "this tool is
    absent" undeterminable -- and the worker runs as root, so an unwritable-path assumption made
    on a laptop quietly becomes a real write to the host. Hence: curated symlinks for the few
    genuine utilities the shell needs, stubs for everything the block installs or waits on, and
    the tools under test in a third directory each scenario fills in.

    `gpg` is stubbed to FAIL, deliberately. The gh chain is
    `curl ... | gpg --dearmor -o <keyring> && echo "deb ..." > /etc/apt/sources.list.d/... &&
    apt-get ...`; a failing gpg short-circuits it before the redirect, on every platform, so the
    test can never write an apt source onto the machine running it. That also makes gh
    deterministically unrepairable HERE -- which is the point: gh is the tool used to prove the
    never-silent half, and a keyring fetch that fails is a real-world shape, not a convenience.
    """
    tools = tmp_path / "tools"
    stubs = tmp_path / "stubs"
    hermetic = tmp_path / "hermetic"
    for d in (tools, stubs, hermetic):
        d.mkdir()
    missing = [t for t in _HERMETIC if shutil.which(t) is None]
    if missing:
        pytest.skip(f"host lacks the utilities this sandbox needs: {missing}")
    for t in _HERMETIC:
        os.symlink(shutil.which(t), hermetic / t)

    _stub(stubs, "timeout", '#!/bin/sh\nshift\nexec "$@"\n')
    _stub(stubs, "flock", '#!/bin/sh\necho "flock $*" >> "$STUB_LOG"\nexit 0\n')
    _stub(stubs, "curl", "#!/bin/sh\nexit 0\n")
    _stub(stubs, "gpg", "#!/bin/sh\nexit 1\n")
    _stub(stubs, "dpkg", "#!/bin/sh\necho amd64\n")
    # apt-get: fails until the invocation counter reaches $SUCCESS_ON, then materialises the
    # named packages as executables. That is the whole scenario dial -- SUCCESS_ON=1 means "no
    # contention", SUCCESS_ON=2 means "the first attempt lost the lock and the retry won",
    # SUCCESS_ON=99 means "nothing ever installed".
    _stub(stubs, "apt-get", r"""#!/bin/sh
n=$(( $(cat "$COUNT_FILE" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$COUNT_FILE"
echo "apt-get[$n] $*" >> "$STUB_LOG"
ok=1
[ "$n" -ge "$SUCCESS_ON" ] || ok=0
sub="$1"
shift
if [ "$sub" = "update" ]; then
  [ "$ok" = "1" ] || exit 100
  exit 0
fi
for a in "$@"; do
  case "$a" in
    -*) ;;
    *) if [ "$ok" = "1" ]; then
         printf '#!/bin/sh\nexit 0\n' > "$TOOL_DIR/$a"
         chmod +x "$TOOL_DIR/$a"
       fi ;;
  esac
done
[ "$ok" = "1" ] || exit 100
exit 0
""")
    count = tmp_path / "apt-count"
    count.write_text("0")
    stub_log = tmp_path / "stub.log"
    stub_log.write_text("")
    env = {
        "PATH": f"{tools}:{stubs}:{hermetic}",
        "TOOL_DIR": str(tools),
        "STUB_LOG": str(stub_log),
        "COUNT_FILE": str(count),
        "HOME": str(tmp_path),
    }
    return {"tools": tools, "stubs": stubs, "hermetic": hermetic,
            "env": env, "stub_log": stub_log, "root": tmp_path}


def _present(sandbox, tools):
    for tool in tools:
        _stub(sandbox["tools"], tool, "#!/bin/sh\nexit 0\n")


def _run_repair(sandbox, *, success_on=1):
    """Execute the real repair block and return (boot-log lines, stub-call lines).

    The block's exit status is deliberately not asserted: its last statement is
    `[ -n "$GONE" ] && log ...`, which is 1 whenever nothing is missing, and the real bootstrap
    has no `set -e` and simply continues to the runner-upgrade stage. Completion is proven by the
    verdict line being present instead, which is the stronger claim anyway.
    """
    env = dict(sandbox["env"], SUCCESS_ON=str(success_on))
    root = sandbox["root"]
    log = root / "boot.log"
    log.write_text("")
    (root / "block.sh").write_text(_repair_block() + "\n")
    (root / "harness.sh").write_text(
        f'log(){{ echo "$*" >> "{log}"; }}\n'
        "up(){ :; }\n"
        f'. "{root / "block.sh"}"\n'
        "exit 0\n"
    )
    proc = subprocess.run([str(sandbox["hermetic"] / "bash"), str(root / "harness.sh")],
                          capture_output=True, text=True, env=env, timeout=120)
    lines = log.read_text().splitlines()
    assert any(l.startswith("repair-done") for l in lines), (
        f"the repair block did not run to completion (rc={proc.returncode})\n"
        f"stderr: {proc.stderr}\nlog: {lines}"
    )
    return lines, sandbox["stub_log"].read_text().splitlines()


def _verdicts(lines):
    line = next(l for l in lines if l.startswith("repair-done"))
    return dict(kv.split("=", 1) for kv in line.split()[1:])


def _incomplete(lines):
    return [l for l in lines if l.startswith("repair-incomplete")]


def test_behaviour_all_tools_present_installs_nothing_and_reports_ok(sandbox) -> None:
    """The common case must cost nothing: no lock wait, no install, no retry."""
    _present(sandbox, (*_REPAIRED, "python"))
    lines, calls = _run_repair(sandbox, success_on=1)
    assert calls == [], f"a healthy boot touched apt or flock: {calls}"
    assert _verdicts(lines) == {"unzip": "OK", "rsync": "OK", "gh": "OK", "python": "OK"}, lines
    assert not _incomplete(lines), lines
    assert not [l for l in lines if l.startswith("repair-retry")], lines


def test_behaviour_a_lock_contention_failure_is_recovered_by_the_retry(sandbox) -> None:
    """THE FIX, executed: attempt 1 loses the dpkg lock, the retry wins, the tools exist.

    This is the 2026-09-16 observation reproduced and then defeated. SUCCESS_ON=2 makes the first
    `apt-get update` fail -- the shape a held lock produces, since apt exits non-zero in
    milliseconds rather than waiting -- and the retry's install then succeeds.
    """
    _present(sandbox, ("python",))
    lines, calls = _run_repair(sandbox, success_on=2)

    waits = [c for c in calls if c.startswith("flock")]
    assert len(waits) == 2, f"expected one lock wait per attempt, got {waits}"
    retries = [l for l in lines if l.startswith("repair-retry")]
    assert len(retries) == 1, lines
    assert "unzip" in retries[0] and "rsync" in retries[0], retries
    v = _verdicts(lines)
    assert v["unzip"] == "OK" and v["rsync"] == "OK", (
        f"the retry did not recover the distro packages: {v}\ncalls={calls}"
    )
    assert not [l for l in _incomplete(lines) if "unzip" in l or "rsync" in l], lines


def test_behaviour_a_tool_that_never_installs_is_named_not_swallowed(sandbox) -> None:
    """The other half of the guarantee: what the retry CANNOT fix is reported by name.

    gh's chain aborts at the stubbed gpg on both attempts, so gh stays missing no matter what
    apt-get does -- a faithful stand-in for "the repo is unreachable". The old block reported
    that with the same `repair-done` line it used for success.
    """
    _present(sandbox, ("python",))
    lines, calls = _run_repair(sandbox, success_on=1)
    incomplete = _incomplete(lines)
    assert incomplete, f"a permanently missing tier0 tool was reported silently: {lines}"
    assert "TIER0-STILL-MISSING" in incomplete[0], incomplete
    assert re.search(r"gh(\s|$)", incomplete[0]), incomplete[0]
    assert _verdicts(lines)["gh"] == "MISSING", lines
    assert "apt-get" in "\n".join(calls), "nothing was even attempted"


def test_behaviour_a_total_install_failure_names_every_missing_tool(sandbox) -> None:
    """Worst case: nothing installs at all. Every tool is MISSING in the verdict line AND named
    in the incomplete report -- the exact telemetry whose absence made the observed race
    undiagnosable from the fleet side."""
    _present(sandbox, ("python",))
    lines, calls = _run_repair(sandbox, success_on=99)
    v = _verdicts(lines)
    assert v == {"unzip": "MISSING", "rsync": "MISSING", "gh": "MISSING", "python": "OK"}, lines
    incomplete = _incomplete(lines)
    assert incomplete and all(t in incomplete[0] for t in _REPAIRED), incomplete
    assert len([c for c in calls if c.startswith("flock")]) == 2, calls
    assert len([l for l in lines if l.startswith("repair-retry")]) == 1, lines


def test_behaviour_the_retry_does_not_repeat_a_successful_install(sandbox) -> None:
    """The retry is gated on the RE-PROBE, so tools the first attempt fixed are not re-installed.

    unzip and rsync succeed on attempt 1 here, so only gh survives into the retry -- and gh's
    chain aborts at the stubbed gpg before reaching apt-get, leaving exactly one install call.
    What the assertion is really about is WHICH tools the retry names: re-installing a package
    that is already present would spend the retry budget, and therefore boot latency, for
    nothing at all.
    """
    _present(sandbox, ("python",))
    lines, calls = _run_repair(sandbox, success_on=1)
    installs = [c for c in calls if " install " in c]
    assert len(installs) == 1 and "unzip rsync" in installs[0], installs
    retries = [l for l in lines if l.startswith("repair-retry")]
    assert len(retries) == 1, lines
    assert "gh" in retries[0], retries
    assert "unzip" not in retries[0] and "rsync" not in retries[0], (
        f"the retry re-installed tools the first attempt already fixed: {retries[0]!r}"
    )
    v = _verdicts(lines)
    assert v["unzip"] == "OK" and v["rsync"] == "OK", lines


def test_behaviour_the_lock_wait_arguments_are_bounded_and_aimed_at_dpkg(sandbox) -> None:
    """flock is invoked with -w and the frontend lock path -- bounded, and aimed at the lock
    `apt-get install` actually contends on. Executed rather than grepped: a `-w` that fell off
    would still satisfy a text assertion that `flock` appears."""
    _present(sandbox, ("python",))
    _, calls = _run_repair(sandbox, success_on=99)
    waits = [c for c in calls if c.startswith("flock")]
    assert waits, calls
    for w in waits:
        assert re.search(r"flock -w \d+ /var/lib/dpkg/lock-frontend", w), w
