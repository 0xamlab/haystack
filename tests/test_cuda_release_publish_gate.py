#!/usr/bin/env python3
"""Dry-run proof of the CUDA release-verify publish gate: the truth table, off-CI.

`build-runtime.yml`'s publish-pypi job decides whether the CUDA-variant runtime
wheel joins the publish set, and the decision is `scripts/release/cuda_publish_gate.py`.
The only honest way to test a release gate is to run it against every input state
it can be handed -- and the real inputs are a wheel that exists (or does not), and a
`cuda-release-verdict.json` that is absent, malformed, from another schema, a
non-pass, or names different bytes. None of that needs a GPU, a VM, a PyPI token, or
a CI runner: the gate reads two directories and one JSON file, so this test FABRICATES
all three under tmp_path and asserts the include/exclude decision for each.

WHAT IS PINNED, AND WHY EACH ROW EXISTS:
  * every exclude path exits 0 -- the gate can never fail a release, it can only
    decline to add one optional wheel to it;
  * exclude leaves the publish set byte-identical -- "publish proceeds WITHOUT the
    cuda wheel" means today's behaviour, not a mutated dist-pypi;
  * include stages the verified wheel AND leaves exactly one file under the runtime
    wheel's filename, because the CUDA and CPU-variant wheels share a filename and
    PyPI has one slot per filename (two same-named files in the upload glob is the
    non-determinism build-runtime.yml's publish-pypi comment was written to avoid);
  * a verdict whose wheel_sha256 differs from the wheel in hand excludes, naming both
    hashes -- a verdict certifies BYTES, so it cannot travel to a rebuild;
  * the one genuinely indeterminate state (a matched verdict that cannot be staged
    without displacing a different wheel, under `--same-name-collision refuse`) exits
    non-zero, because there the publish set would be a guess.
The workflow-side wiring (explicit artifact name, the gate invocation, the single
twine skip-existing idempotence flag, and the compile gate staying out of the
clean-machine contract's `needs`) is asserted at the bottom, since a gate that is
correct but never called certifies nothing.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GATE_PATH = _REPO_ROOT / "scripts" / "release" / "cuda_publish_gate.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "build-runtime.yml"

# The gate's real invocation inside publish-pypi. Spelled with its `"${GATE_ARGS[@]}"` tail so that
# ordering assertions below match the COMMAND and not the prose in the job's comments, which name
# the same script several times -- a bare filename made an earlier version of these guards match a
# comment and pass for the wrong reason.
_GATE_CALL = 'cuda_publish_gate.py "${GATE_ARGS[@]}"'

# The runtime wheel's real filename shape: `algenta_runtime_native-<ver>-py3-none-<platform>.whl`.
# The CUDA-variant and CPU-variant builds produce the SAME name -- that collision is the reason
# this gate has to stage deterministically instead of letting twine's glob order decide.
_RUNTIME_WHEEL = "algenta_runtime_native-1.0.5-py3-none-manylinux_2_35_x86_64.whl"
_ALGENTA_WHEEL = "algenta-1.0.5-py3-none-any.whl"
_CUDA_BYTES = b"cuda-variant-shards" * 64
_CPU_BYTES = b"cpu-variant-shards" * 64


def _load_gate():
    spec = importlib.util.spec_from_file_location("cuda_publish_gate", _GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_GATE = _load_gate()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _verdict(
    path: Path,
    *,
    wheel_sha256: str | None = None,
    schema_version: int = 1,
    verdict: str = "pass",
    rc: int = 0,
    nested: bool = True,
) -> Path:
    """Fabricate a verdict file in the shape both emitters write.

    `nested=True` puts the hash under `wheel.sha256` (what
    scripts/release/verify_cuda_release.sh and issue_verdict_from_evidence.sh emit);
    `nested=False` uses only the flat `wheel_sha256` alias, so the reader is proven
    to accept either.
    """
    payload: dict[str, object] = {
        "schema_version": schema_version,
        "verdict": verdict,
        "rc": rc,
        "scope_statement": (
            "certifies the wheel's binary is the gate-passed binary on one H200 box; "
            "it is not a benchmark win"
        ),
        "issued_utc": "2026-10-01T00:00:00Z",
    }
    if nested:
        payload["wheel"] = {"filename": _RUNTIME_WHEEL, "sha256": wheel_sha256}
    else:
        payload["wheel_sha256"] = wheel_sha256
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def publish(tmp_path: Path) -> dict[str, Path]:
    """A publish set as clean-machine-contract leaves it: the CPU-variant linux runtime
    wheel + the algenta wheel, and a separate cuda artifact dir holding the CUDA wheel."""
    publish_dir = tmp_path / "dist-pypi"
    cuda_dir = tmp_path / "dist-pypi-cuda"
    _write(publish_dir / _RUNTIME_WHEEL, _CPU_BYTES)
    _write(publish_dir / _ALGENTA_WHEEL, b"pure-python-algenta" * 32)
    _write(cuda_dir / _RUNTIME_WHEEL, _CUDA_BYTES)
    return {
        "tmp": tmp_path,
        "publish": publish_dir,
        "cuda": cuda_dir,
        "verdict": tmp_path / "cuda-release-verdict.json",
        "decision": tmp_path / "cuda-publish-gate-decision.json",
    }


def _run(env: dict[str, Path], **kwargs: object) -> int:
    argv = [
        "--cuda-dir",
        str(env["cuda"]),
        "--publish-dir",
        str(env["publish"]),
        "--json",
        str(env["decision"]),
    ]
    verdict = kwargs.pop("verdict", env["verdict"])
    if verdict is not None:
        argv += ["--verdict", str(verdict)]
    for key, value in kwargs.items():
        argv += [f"--{key.replace('_', '-')}", str(value)]
    return _GATE.main(argv)


def _decision(env: dict[str, Path]) -> dict:
    return json.loads(env["decision"].read_text(encoding="utf-8"))


def _published(env: dict[str, Path]) -> dict[str, bytes]:
    """What `twine upload dist-pypi/*` would actually be handed."""
    return {p.name: p.read_bytes() for p in sorted(env["publish"].iterdir()) if p.is_file()}


# ── the exclude half of the truth table: every one exits 0 and changes nothing ──────────────


def test_verdict_absent_excludes_and_publishes_unchanged(publish: dict[str, Path]) -> None:
    """Today's behaviour, and the state every release is in until a battery has run."""
    before = _published(publish)
    assert _run(publish) == 0
    record = _decision(publish)
    assert record["decision"] == "exclude"
    assert record["reason"] == _GATE.REASON_VERDICT_ABSENT
    assert record["staged"] is None
    assert _published(publish) == before, "an exclude must not touch the publish set"
    assert any("no run-verified CUDA verdict" in n for n in record["notices"])


def test_verdict_path_pointing_at_a_missing_file_excludes(publish: dict[str, Path]) -> None:
    """`--verdict` naming a file that is not there is the same state as no `--verdict`."""
    assert _run(publish, verdict=publish["tmp"] / "nope.json") == 0
    assert _decision(publish)["reason"] == _GATE.REASON_VERDICT_ABSENT


def test_verdict_unreadable_excludes(publish: dict[str, Path]) -> None:
    publish["verdict"].write_text("{not json", encoding="utf-8")
    before = _published(publish)
    assert _run(publish) == 0
    assert _decision(publish)["reason"] == _GATE.REASON_VERDICT_UNREADABLE
    assert _published(publish) == before


def test_verdict_that_is_not_an_object_excludes(publish: dict[str, Path]) -> None:
    publish["verdict"].write_text("[1, 2, 3]", encoding="utf-8")
    assert _run(publish) == 0
    assert _decision(publish)["reason"] == _GATE.REASON_VERDICT_UNREADABLE


def test_verdict_from_an_unknown_schema_excludes(publish: dict[str, Path]) -> None:
    """A newer schema is not guessed at: the gate reads schema 1 and says so."""
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES), schema_version=2)
    before = _published(publish)
    assert _run(publish) == 0
    assert _decision(publish)["reason"] == _GATE.REASON_SCHEMA_UNSUPPORTED
    assert _published(publish) == before


def test_verdict_that_is_not_a_pass_excludes(publish: dict[str, Path]) -> None:
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES), verdict="fail")
    assert _run(publish) == 0
    assert _decision(publish)["reason"] == _GATE.REASON_NOT_PASS


def test_verdict_with_a_nonzero_rc_excludes_even_when_it_says_pass(
    publish: dict[str, Path],
) -> None:
    """Defence in depth: the emitters never write a verdict on a failed gate, so a file
    that says `pass` with `rc != 0` was edited, truncated, or carried over from an
    aborted run."""
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES), rc=1)
    assert _run(publish) == 0
    assert _decision(publish)["reason"] == _GATE.REASON_NOT_PASS


def test_verdict_without_a_usable_hash_excludes(publish: dict[str, Path]) -> None:
    _verdict(publish["verdict"], wheel_sha256="not-a-sha256")
    assert _run(publish) == 0
    assert _decision(publish)["reason"] == _GATE.REASON_NO_SHA_IN_VERDICT


def test_verdict_for_different_bytes_excludes_and_names_both_hashes(
    publish: dict[str, Path],
) -> None:
    """The load-bearing row. A verdict from an older build (or a rebuild of the same
    commit) names other bytes, and must not certify the wheel in hand."""
    _verdict(publish["verdict"], wheel_sha256=_sha256(b"a different wheel entirely"))
    before = _published(publish)
    assert _run(publish) == 0
    record = _decision(publish)
    assert record["reason"] == _GATE.REASON_SHA_MISMATCH
    assert _published(publish) == before
    notice = " ".join(str(n) for n in record["notices"])
    assert _sha256(b"a different wheel entirely") in notice, "the verdict's hash must be printed"
    assert _sha256(_CUDA_BYTES) in notice, "the built wheel's hash must be printed"


def test_cuda_artifact_absent_excludes_even_with_a_matching_verdict(
    publish: dict[str, Path],
) -> None:
    """publish-pypi does not `needs` the compile gate's success, so a run where that job
    failed or has not uploaded yet is an exclude, not a failure."""
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES))
    for wheel in publish["cuda"].glob("*.whl"):
        wheel.unlink()
    assert _run(publish) == 0
    assert _decision(publish)["reason"] == _GATE.REASON_WHEEL_ABSENT


def test_two_wheels_in_the_cuda_artifact_excludes(publish: dict[str, Path]) -> None:
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES))
    _write(publish["cuda"] / "algenta_runtime_native-9.9.9-py3-none-any.whl", b"unexpected")
    assert _run(publish) == 0
    assert _decision(publish)["reason"] == _GATE.REASON_WHEEL_AMBIGUOUS


# ── the include half: the verified wheel takes the linux runtime slot ────────────────────────


def test_matching_verdict_includes_and_displaces_the_cpu_variant(
    publish: dict[str, Path],
) -> None:
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES))
    assert _run(publish) == 0
    record = _decision(publish)
    assert record["decision"] == "include"
    assert record["reason"] == _GATE.REASON_VERIFIED
    assert record["staged"]["sha256"] == _sha256(_CUDA_BYTES)
    assert record["staged"]["bytes"] == len(_CUDA_BYTES)
    assert record["displaced"]["sha256"] == _sha256(_CPU_BYTES)

    published = _published(publish)
    assert published[_RUNTIME_WHEEL] == _CUDA_BYTES, "the verified wheel must hold the slot"
    assert published[_ALGENTA_WHEEL] == b"pure-python-algenta" * 32, "unrelated wheels untouched"
    # ONE file per filename in the upload glob: the failure this prevents is twine being handed
    # two same-named wheels, where the first wins and skip-existing silently swallows the second.
    assert len([n for n in published if n == _RUNTIME_WHEEL]) == 1
    # The displaced wheel is preserved for the record, OUTSIDE the upload glob.
    displaced = publish["tmp"] / "dist-pypi-displaced" / _RUNTIME_WHEEL
    assert displaced.read_bytes() == _CPU_BYTES


def test_matching_verdict_via_the_flat_hash_alias_includes(publish: dict[str, Path]) -> None:
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES), nested=False)
    assert _run(publish) == 0
    assert _decision(publish)["decision"] == "include"


def test_include_is_idempotent_when_the_verified_bytes_are_already_staged(
    publish: dict[str, Path],
) -> None:
    """A re-run of the gate must not displace the wheel it just staged."""
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES))
    assert _run(publish) == 0
    first = _published(publish)
    assert _run(publish) == 0
    record = _decision(publish)
    assert record["decision"] == "include"
    assert record["displaced"] is None
    assert _published(publish) == first


def test_refuse_policy_on_a_collision_exits_nonzero_and_moves_nothing(
    publish: dict[str, Path],
) -> None:
    """The one hard error: a human asked for this wheel to ship and the publish set cannot
    take it without displacing a different wheel. That is indeterminate, so it is loud."""
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES))
    before = _published(publish)
    assert _run(publish, same_name_collision="refuse") == 2
    record = _decision(publish)
    assert record["decision"] == "exclude"
    assert record["reason"] == _GATE.REASON_COLLISION_REFUSED
    assert record["refused"] is True
    assert record["staged"] is None
    assert _published(publish) == before, "refuse must leave the publish set exactly as it was"


def test_refuse_policy_without_a_collision_still_includes(publish: dict[str, Path]) -> None:
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES))
    (publish["publish"] / _RUNTIME_WHEEL).unlink()
    assert _run(publish, same_name_collision="refuse") == 0
    record = _decision(publish)
    assert record["decision"] == "include"
    assert record["staged"]["sha256"] == _sha256(_CUDA_BYTES)


def test_github_output_carries_the_decision(
    publish: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    out = publish["tmp"] / "github_output"
    out.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES))
    assert _run(publish) == 0
    text = out.read_text(encoding="utf-8")
    assert "cuda_decision=include" in text
    assert f"cuda_wheel_sha256={_sha256(_CUDA_BYTES)}" in text
    monkeypatch.delenv("GITHUB_OUTPUT")
    assert _run(publish) == 0, "the gate must not depend on GITHUB_OUTPUT being set"


def test_decision_record_carries_the_verdict_scope_statement(publish: dict[str, Path]) -> None:
    """The scope statement travels with the decision, so a reader of the publish log sees what
    the verdict does and does not claim without opening the verdict."""
    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES))
    assert _run(publish) == 0
    summary = _decision(publish)["verdict_summary"]
    assert summary["verdict"] == "pass"
    assert summary["rc"] == 0
    assert "not a benchmark win" in summary["scope"]
    assert summary["issued_utc"] == "2026-10-01T00:00:00Z"


def test_cli_exit_code_matches_main_return(publish: dict[str, Path]) -> None:
    """The workflow runs this as a subprocess, so the process exit code IS the contract."""
    import subprocess
    import sys

    _verdict(publish["verdict"], wheel_sha256=_sha256(_CUDA_BYTES))
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(_GATE_PATH),
            "--cuda-dir",
            str(publish["cuda"]),
            "--publish-dir",
            str(publish["publish"]),
            "--verdict",
            str(publish["verdict"]),
            "--json",
            str(publish["decision"]),
        ],
        capture_output=True,
        text=True,
        env={**os.environ},
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "CUDA_PUBLISH_DECISION=include" in proc.stdout


# ── the workflow wiring: a correct gate that is never called certifies nothing ───────────────


def _workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def test_publish_job_downloads_the_cuda_artifact_by_explicit_name() -> None:
    text = _workflow_text()
    publish = text.split("\n  publish-pypi:\n", 1)[1]
    assert "name: algenta-runtime-native-linux-x86_64-cuda" in publish, (
        "publish-pypi must download the CUDA wheel by EXPLICIT name; a glob merged with "
        "merge-multiple would non-deterministically overwrite one same-named wheel with the other"
    )
    assert "cuda_publish_gate.py" in publish, "publish-pypi must call the gate"
    # The gate must run BEFORE twine, or it stages nothing that the upload can see. Matched on the
    # real command line, not on "twine upload": the job's own header comment says those words too,
    # and index() would find the comment first and make this assertion meaningless. _GATE_CALL
    # carries the argument expansion for the same reason.
    assert _GATE_CALL in publish, "publish-pypi must invoke the gate as a real command"
    assert publish.index(_GATE_CALL) < publish.index("twine upload --non-interactive")


def test_publish_job_waits_for_the_cuda_artifact_but_never_on_its_success() -> None:
    """Determinism without coupling: publish must not run before the CUDA wheel exists (or the
    decision is always 'artifact absent'), and a CUDA COMPILE failure must still not block a
    release -- so the job is in `needs` for ordering and the `if:` tolerates its failure."""
    publish = _workflow_text().split("\n  publish-pypi:\n", 1)[1]
    lines = publish.splitlines()
    needs = next(line for line in lines if line.strip().startswith("needs:"))
    assert "build-linux-cuda" in needs
    assert "clean-machine-contract" in needs

    # `if: >-` is a folded block, so the condition spans this line and the next two.
    if_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("if:"))
    condition = " ".join(part.strip() for part in lines[if_idx : if_idx + 3])
    assert "needs.clean-machine-contract.result == 'success'" in condition
    assert "!cancelled()" in condition, (
        "without this, a failed/skipped compile gate would skip the publish job entirely"
    )
    assert "needs.build-linux-cuda.result" not in publish, (
        "the compile gate must stay OFF the release critical path: it is a floor, not a blocker"
    )


def test_publish_job_checks_out_the_repo_before_running_the_gate() -> None:
    """REGRESSION -- build-runtime.yml runs 35650281651 and 35634239235. publish-pypi downloaded
    artifacts and ran twine but NEVER checked the repository out, so the gate died on a script that
    was not on the runner:
        python3: can't open file '.../scripts/release/cuda_publish_gate.py': [Errno 2] No such file
        ##[error]Process completed with exit code 2.
    Run 35634239235 had build-linux-cuda GREEN and still failed here, which is the proof that this
    was not a consequence of the CUDA lane: the publish job could not run its own gate at all. A
    gate that cannot be found is indistinguishable from a gate that refuses, and it took the whole
    release train down with it either way."""
    publish = _workflow_text().split("\n  publish-pypi:\n", 1)[1]
    assert "actions/checkout@" in publish, (
        "publish-pypi must check the repo out: the release-verify gate runs a script FROM the repo"
    )
    # And checked out BEFORE the gate runs, not merely somewhere in the job. Matched on the real
    # invocation -- the `"${GATE_ARGS[@]}"` tail is what prose in the job's comments cannot
    # reproduce, so a comment that merely names the script cannot satisfy the ordering by accident.
    assert publish.index("actions/checkout@") < publish.index(_GATE_CALL)


def test_publish_job_only_invokes_repo_scripts_that_exist() -> None:
    """The general form of the bug above. Every repo-relative `scripts/*.py` that a publish-pypi
    step hands to an interpreter must exist in the checkout -- asserted from the workflow text so a
    rename or a deletion breaks THIS test off-CI, instead of breaking a release train on main."""
    import re

    publish = _workflow_text().split("\n  publish-pypi:\n", 1)[1]
    referenced = sorted(set(re.findall(r"\bscripts/[A-Za-z0-9_./-]+\.py\b", publish)))
    assert referenced, "publish-pypi is expected to invoke at least the cuda publish gate"
    missing = [path for path in referenced if not (_REPO_ROOT / path).is_file()]
    assert not missing, f"publish-pypi invokes repo scripts that do not exist: {missing}"


def test_cuda_lane_failure_degrades_to_a_cpu_only_publish() -> None:
    """The degradation chain, link by link: when build-linux-cuda fails, publish-pypi must still
    run, still tolerate the absent CUDA artifact, and still publish the CPU wheels -- with the
    gate's own `cuda_wheel_absent` notice as the only trace of the CUDA lane. Any link that
    hard-fails turns a compile-gate break into a release outage, which is what happened on main.

    Link 1 (the job runs at all despite the failed `needs` entry) is pinned by
    test_publish_job_waits_for_the_cuda_artifact_but_never_on_its_success; link 3's exit-0 arm is
    pinned behaviourally by test_cuda_artifact_absent_excludes_even_with_a_matching_verdict. This
    test covers the two wiring links in between."""
    import re

    publish = _workflow_text().split("\n  publish-pypi:\n", 1)[1]

    # Link 2: the CUDA artifact download is fail-open. `if-no-files-found` alone is NOT enough --
    # an artifact that was never uploaded is a hard error in download-artifact, and only
    # continue-on-error absorbs it (observed: "Artifact not found for name: ...-cuda").
    steps = re.split(r"^      - ", publish, flags=re.M)
    cuda_steps = [step for step in steps if "algenta-runtime-native-linux-x86_64-cuda" in step]
    assert cuda_steps, "publish-pypi must have a step that fetches the CUDA artifact"
    assert any("continue-on-error: true" in step for step in cuda_steps), (
        "the CUDA artifact download must be fail-open, or a build-linux-cuda failure fails publish"
    )

    # Link 4: the upload is not conditioned on the CUDA decision. An exclude has to leave the
    # publish set at today's CPU-only shape, not gate it.
    assert "steps.cuda-gate.outputs" not in publish, (
        "twine must not be conditioned on the CUDA decision: exclude means publish without the "
        "cuda wheel, never 'do not publish'"
    )
    assert publish.index(_GATE_CALL) < publish.index("twine upload --non-interactive"), (
        "the gate must stage before the upload globs dist-pypi"
    )


def test_compile_gate_stays_out_of_the_clean_machine_contract() -> None:
    contract = (
        _workflow_text()
        .split("\n  clean-machine-contract:\n", 1)[1]
        .split("\n  publish-pypi:\n", 1)[0]
    )
    assert "build-linux-cuda" not in contract, (
        "the clean-machine contract must keep verifying the SHIPPED CPU-variant wheel; putting "
        "the compile gate in its needs would make every release depend on the CUDA lane"
    )


def test_workflow_keeps_exactly_one_twine_idempotence_flag() -> None:
    """tests/test_sdk_package_metadata.py counts this literal; a comment that spelled it out
    would break that guard, so this asserts the invariant from both sides."""
    assert _workflow_text().count("--skip-existing") == 1


def test_workflow_documents_what_the_gate_does_not_claim() -> None:
    """The scope limit lives in the workflow, next to the step that acts on the verdict -- a reader
    deciding whether to trust a publish should not have to find the battery script first."""
    text = _workflow_text()
    lowered = text.lower()
    assert "not a benchmark win" in lowered
    assert "cuda-release-verdict.json" in text
    assert "wheel_sha256" in lowered
    assert "verify_cuda_release.sh" in text, "the workflow must name what produces a verdict"


# ── engine-binary fallback: the certification attaches to the certified artifact ────────
# The wheel zip is a container (version metadata + public CPU shards); the engine binary
# inside it is what the oracle gates ran. A verdict whose wheel sha names an older
# container but whose engine digest matches this wheel's signed manifest still certifies
# THESE bytes; anything less excludes.


def _zip_wheel_with_engine(path: Path, engine_sha: str) -> Path:
    import zipfile

    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.dumps(
        {
            "format_version": 1,
            "platform": "linux-x86_64",
            "build_variant": "cuda",
            "engine": {"name": "conform_generate_cuda", "sha256": engine_sha, "size_bytes": 1},
            "artifacts": [],
        }
    ).encode()
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("algenta_runtime_native/manifest.json", manifest)
        archive.writestr("algenta_runtime_native/worker", b"shards")
    return path


def _verdict_with_engine(path: Path, *, wheel_sha256: str, engine_sha: str, shape: str) -> Path:
    payload: dict[str, object] = {
        "schema_version": 1,
        "verdict": "pass",
        "rc": 0,
        "scope_statement": "certifies the engine binary; not a benchmark win",
        "issued_utc": "2026-10-01T00:00:00Z",
        "wheel": {"filename": _RUNTIME_WHEEL, "sha256": wheel_sha256},
    }
    if shape == "flat":
        payload["engine"] = {"name": "conform_generate_cuda", "sha256": engine_sha}
    else:
        payload["binaries"] = {
            "engine_binaries": [{"name": "conform_generate_cuda", "sha256": engine_sha, "bytes": 1}]
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


@pytest.mark.parametrize("shape", ["flat", "binaries"])
def test_engine_digest_match_includes_when_the_container_moved(publish, shape, tmp_path):
    engine_sha = _sha256(b"the certified engine bytes")
    _zip_wheel_with_engine(publish["cuda"] / _RUNTIME_WHEEL, engine_sha)
    _verdict_with_engine(
        publish["verdict"],
        wheel_sha256=_sha256(b"an older container with the same engine"),
        engine_sha=engine_sha,
        shape=shape,
    )
    decision = _GATE.decide(
        cuda_dir=publish["cuda"], publish_dir=publish["publish"], verdict_path=publish["verdict"]
    )
    assert decision["decision"] == "include"
    assert decision["reason"] == _GATE.REASON_VERIFIED_ENGINE
    assert decision["engine_match"] is True


def test_engine_digest_mismatch_excludes(publish):
    _zip_wheel_with_engine(publish["cuda"] / _RUNTIME_WHEEL, _sha256(b"engine in this wheel"))
    _verdict_with_engine(
        publish["verdict"],
        wheel_sha256=_sha256(b"some other container"),
        engine_sha=_sha256(b"a DIFFERENT engine"),
        shape="flat",
    )
    decision = _GATE.decide(
        cuda_dir=publish["cuda"], publish_dir=publish["publish"], verdict_path=publish["verdict"]
    )
    assert decision["decision"] == "exclude"
    assert decision["reason"] == _GATE.REASON_SHA_MISMATCH


def test_non_zip_wheel_cannot_claim_the_engine_fallback(publish):
    # Plain-bytes fixture: no manifest to read, so the fallback must not fire even though
    # the verdict carries a perfectly formed engine digest.
    _verdict_with_engine(
        publish["verdict"],
        wheel_sha256=_sha256(b"not these bytes"),
        engine_sha=_sha256(b"any engine"),
        shape="flat",
    )
    decision = _GATE.decide(
        cuda_dir=publish["cuda"], publish_dir=publish["publish"], verdict_path=publish["verdict"]
    )
    assert decision["decision"] == "exclude"
    assert decision["reason"] == _GATE.REASON_SHA_MISMATCH
    assert decision["engine_match"] is None
