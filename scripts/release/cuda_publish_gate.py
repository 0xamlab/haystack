#!/usr/bin/env python3
"""The CUDA release-verify publish gate: does the CUDA wheel join this publish or not?

One decision, computed from two files and nothing else:

    the CUDA wheel the `build-linux-cuda` compile gate just produced, and
    a `cuda-release-verdict.json` attached to the release being published.

The wheel joins the publish set only when the verdict exists, is schema-1, says
`pass`, and names the sha256 of *this* wheel. Every other state -- verdict
absent, unreadable, from a newer schema, not a pass, or naming a different wheel
-- is an EXCLUDE, printed as a notice, and an exit 0: the release proceeds
exactly as it does today. This gate can never fail a release; the thing it gates
is one optional wheel, not the publish.

WHY THE HASH AND NOT THE TAG OR THE DATE. A verdict is a statement about a
BINARY. Attaching it to a release says "some wheel was run-verified", and only
the sha256 says *which* one: a rebuild from the same commit is not the same
bytes, and a verdict that travelled from an older build must not certify a newer
wheel. The campaign learned this the hard way and made it structural -- round 14
pinned arm hashes and made a mismatch FATAL rather than a warning, because a
rebuild silently detaches a certification from the artifact it certified (see
`benchmarks/llm_smoke/nvidia_race/chain19.sh`'s `EXPECT_DEF_SHA`). Same rule
here, one level up: the verdict names a wheel hash, this script recomputes it
from the wheel actually in hand, and a disagreement excludes.

WHY "JOIN" MEANS "TAKE THE LINUX RUNTIME SLOT", AND WHY THAT IS NOT A CHOICE.
The CUDA wheel and the shipped CPU-variant linux wheel have the SAME filename --
same distribution, same version, same `py3-none-manylinux_2_35_x86_64` tag; only
the compiled shards inside differ (`.github/workflows/build-runtime.yml`'s
publish-pypi comment has said so since the compile gate landed). PyPI therefore
has exactly ONE slot for `algenta_runtime_native-<ver>-py3-none-manylinux_2_35_x86_64.whl`
per version, and handing twine both files does not publish both: the first
upload takes the slot and `--skip-existing` silently swallows the second, so
which wheel ships would be decided by glob order. This script makes that
deterministic instead: on include, the run-verified CUDA wheel takes the slot and
the displaced CPU-variant wheel is moved aside under `displaced/` with both
hashes logged. `--same-name-collision refuse` turns the displacement into a hard
error for the day the CUDA build gets its own filename.

WHAT THIS DOES NOT CLAIM. Including the wheel says the artifact passed the
campaign's oracle gates on one H200 box under the recorded clocks. It is not a
benchmark win, not a multi-hardware certification, and not a claim about any
host without an NVIDIA driver: see `scripts/release/verify_cuda_release.sh` for
the exact scope statement the verdict itself carries.

Usage (CI, and the off-CI dry run in tests/test_cuda_release_publish_gate.py):

    python3 scripts/release/cuda_publish_gate.py \
        --cuda-dir dist-pypi-cuda --publish-dir dist-pypi \
        [--verdict /path/to/cuda-release-verdict.json] \
        [--same-name-collision replace|refuse] [--json gate-decision.json]

Exit codes: 0 = decided (include OR exclude; the release proceeds either way),
2 = the publish set is in an indeterminate state (a matched verdict could not be
staged, or `refuse` policy met a collision) and a human must look.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

SUPPORTED_SCHEMA_VERSION = 1
# The displaced CPU-variant wheel goes to a SIBLING of the publish dir, never inside it: the publish
# job uploads `dist-pypi/*`, so a `dist-pypi/displaced/` subdirectory would be handed to twine as an
# argument that is neither a wheel nor an sdist. Outside the glob, the upload line needs no change.
DISPLACED_SUFFIX = "-displaced"

# Decision reasons. Stable strings: the workflow notice prints them, the dry-run
# test asserts on them, and a future reader greps the log for them.
REASON_VERIFIED = "verdict_pass_and_wheel_sha256_matches"
REASON_VERDICT_ABSENT = "verdict_absent"
REASON_VERDICT_UNREADABLE = "verdict_unreadable"
REASON_SCHEMA_UNSUPPORTED = "verdict_schema_unsupported"
REASON_NOT_PASS = "verdict_is_not_a_pass"  # noqa: S105 - a gate verdict, not a credential
REASON_WHEEL_ABSENT = "cuda_wheel_absent"
REASON_WHEEL_AMBIGUOUS = "cuda_wheel_ambiguous"
REASON_SHA_MISMATCH = "wheel_sha256_mismatch"
REASON_VERIFIED_ENGINE = "verdict_pass_and_engine_sha256_matches"
REASON_NO_SHA_IN_VERDICT = "verdict_carries_no_wheel_sha256"
REASON_COLLISION_REFUSED = "same_name_collision_refused"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verdict_wheel_sha256(verdict: object) -> str | None:
    """The wheel sha256 a verdict names, accepting both the flat and nested shapes.

    `scripts/release/verify_cuda_release.sh` (a fresh battery) and
    `scripts/release/issue_verdict_from_evidence.sh` (a verdict re-derived from
    banked evidence) both emit the nested `wheel.sha256` plus the flat
    `wheel_sha256` alias, so one reader serves both and a hand-written verdict
    that carries only the flat key still works.
    """
    if not isinstance(verdict, dict):
        return None
    flat = verdict.get("wheel_sha256")
    if isinstance(flat, str) and len(flat) == 64:
        return flat.lower()
    wheel = verdict.get("wheel")
    if isinstance(wheel, dict):
        nested = wheel.get("sha256")
        if isinstance(nested, str) and len(nested) == 64:
            return nested.lower()
    return None


def _verdict_engine_sha256(verdict: object) -> str | None:
    """The certified ENGINE binary digest a verdict carries, from either emitter shape.

    `verify_cuda_release.sh` records the bundled engine under `binaries.engine_binaries`
    (a list, the entry named `conform_generate_cuda`); a verdict re-derived from a signed
    manifest may carry the flat `engine` block instead. The engine binary is the artifact
    the oracle gates actually ran; the wheel zip around it is a container.
    """
    if not isinstance(verdict, dict):
        return None
    engine = verdict.get("engine")
    if isinstance(engine, dict):
        sha = engine.get("sha256")
        if isinstance(sha, str) and len(sha) == 64:
            return sha.lower()
    binaries = verdict.get("binaries")
    if isinstance(binaries, dict):
        entries = binaries.get("engine_binaries")
        if isinstance(entries, list):
            named = [e for e in entries if isinstance(e, dict) and e.get("name") == "conform_generate_cuda"]
            for entry in named or [e for e in entries if isinstance(e, dict)]:
                sha = entry.get("sha256")
                if isinstance(sha, str) and len(sha) == 64:
                    return sha.lower()
    return None


def _wheel_engine_sha256(wheel: Path) -> str | None:
    """The engine digest from the signed-manifest block INSIDE the wheel, if readable.

    The bundle manifest ships in the wheel as `manifest.json` beside `manifest.sig`
    (`scripts/generate_runtime_bundle_manifest.py`); its `engine.sha256` is cross-checked
    against the real file at generation and again by `validate_runtime_release.py`, so it
    is the wheel's own statement of which engine binary it carries. A wheel that is not a
    zip (test fixtures, a truncated download) yields None: the gate then falls back to the
    wheel-sha rule alone, never to a guess.
    """
    try:
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if not name.endswith("manifest.json"):
                    continue
                try:
                    payload = json.loads(archive.read(name))
                except ValueError:
                    continue
                if not isinstance(payload, dict):
                    continue
                engine = payload.get("engine")
                if isinstance(engine, dict):
                    sha = engine.get("sha256")
                    if isinstance(sha, str) and len(sha) == 64:
                        return sha.lower()
    except (OSError, zipfile.BadZipFile):
        return None
    return None


def _verdict_issued_utc(verdict: dict) -> object:
    """The verdict's own issue time, from the flat alias or the nested timestamps block."""
    issued = verdict.get("issued_utc")
    if isinstance(issued, str) and issued:
        return issued
    stamps = verdict.get("timestamps")
    if isinstance(stamps, dict):
        return stamps.get("finished_utc") or stamps.get("issued_utc")
    return None


def _verdict_is_pass(verdict: object) -> bool:
    """A verdict counts as a pass only when it says so AND its own rc was 0.

    The emitters refuse to write a verdict at all on a failed gate, so this is
    defence in depth rather than the primary control: a file that was edited by
    hand, truncated by a partial upload, or carried over from an aborted run
    still has to state `pass` with `rc == 0` to be believed.
    """
    if not isinstance(verdict, dict):
        return False
    if verdict.get("verdict") != "pass":
        return False
    rc = verdict.get("rc", 0)
    return rc in (0, "0")


def decide(
    *,
    cuda_dir: Path,
    publish_dir: Path,
    verdict_path: Path | None,
    same_name_collision: str = "replace",
) -> dict[str, object]:
    """Compute the include/exclude decision. Pure except for the staging it does
    on include (the copy + the displacement), so the dry-run test can call it
    against tmp_path directories with fabricated verdicts and no CI at all."""
    decision: dict[str, object] = {
        "schema_version": 1,
        "decision": "exclude",
        "reason": REASON_VERDICT_ABSENT,
        "refused": False,
        "cuda_dir": str(cuda_dir),
        "publish_dir": str(publish_dir),
        "verdict_path": str(verdict_path) if verdict_path else None,
        "engine_match": None,
        "staged": None,
        "displaced": None,
        "cuda_wheel": None,
        "verdict_summary": None,
        "notices": [],
    }
    notices: list[str] = decision["notices"]  # type: ignore[assignment]

    def exclude(reason: str, notice: str) -> dict[str, object]:
        decision["decision"] = "exclude"
        decision["reason"] = reason
        notices.append(notice)
        return decision

    # ── 1. the verdict ────────────────────────────────────────────────────────
    if verdict_path is None or not verdict_path.is_file():
        return exclude(
            REASON_VERDICT_ABSENT,
            "no run-verified CUDA verdict attached to this release; publishing without the "
            "CUDA wheel (today's behaviour). The CUDA wheel is publishable only when "
            "scripts/release/verify_cuda_release.sh has produced a fresh verdict for these "
            "exact bytes.",
        )
    try:
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return exclude(
            REASON_VERDICT_UNREADABLE,
            f"cuda-release-verdict.json is not readable JSON ({exc}); publishing without the "
            "CUDA wheel. A verdict this gate cannot parse is a verdict it cannot trust.",
        )
    if not isinstance(verdict, dict):
        return exclude(
            REASON_VERDICT_UNREADABLE,
            "cuda-release-verdict.json is not a JSON object; publishing without the CUDA wheel.",
        )
    schema = verdict.get("schema_version")
    if schema != SUPPORTED_SCHEMA_VERSION:
        return exclude(
            REASON_SCHEMA_UNSUPPORTED,
            f"cuda-release-verdict.json declares schema_version={schema!r}; this gate reads "
            f"schema_version={SUPPORTED_SCHEMA_VERSION}. Publishing without the CUDA wheel "
            "rather than guessing at a schema it was not written for.",
        )
    decision["verdict_summary"] = {
        "verdict": verdict.get("verdict"),
        "rc": verdict.get("rc"),
        "scope": verdict.get("scope_statement") or verdict.get("scope"),
        "issued_utc": _verdict_issued_utc(verdict),
        "evidence": verdict.get("evidence"),
    }
    if not _verdict_is_pass(verdict):
        return exclude(
            REASON_NOT_PASS,
            f"the attached verdict is not a pass (verdict={verdict.get('verdict')!r} "
            f"rc={verdict.get('rc')!r}); publishing without the CUDA wheel.",
        )
    want_sha = _verdict_wheel_sha256(verdict)
    if want_sha is None:
        return exclude(
            REASON_NO_SHA_IN_VERDICT,
            "the verdict names no 64-hex wheel_sha256, so it cannot be tied to these bytes; "
            "publishing without the CUDA wheel.",
        )

    # ── 2. the wheel ──────────────────────────────────────────────────────────
    wheels = sorted(p for p in cuda_dir.glob("*.whl") if p.is_file()) if cuda_dir.is_dir() else []
    if not wheels:
        return exclude(
            REASON_WHEEL_ABSENT,
            f"no CUDA wheel in {cuda_dir} (the build-linux-cuda artifact was not downloaded, or "
            "that job has not uploaded it yet); publishing without the CUDA wheel.",
        )
    if len(wheels) > 1:
        return exclude(
            REASON_WHEEL_AMBIGUOUS,
            f"{len(wheels)} wheels in {cuda_dir}: {[w.name for w in wheels]}. This gate will not "
            "pick one; publishing without the CUDA wheel.",
        )
    wheel = wheels[0]
    got_sha = _sha256(wheel)
    decision["cuda_wheel"] = {
        "filename": wheel.name,
        "sha256": got_sha,
        "sha256_16": got_sha[:16],
        "bytes": wheel.stat().st_size,
    }
    engine_match: bool | None = None
    if got_sha != want_sha:
        # The wheel zip is a CONTAINER: version metadata and the public CPU shards move on
        # any rebuild, while the certified artifact -- the engine binary the oracle gates
        # actually ran -- is content-addressed inside it via the signed manifest. Matching
        # that digest keeps the certification attached to the bytes it certified without
        # demanding the container be byte-identical across runs. Engine-source drift
        # changes the digest and excludes, exactly as a wheel-sha mismatch does.
        want_engine = _verdict_engine_sha256(verdict)
        got_engine = _wheel_engine_sha256(wheel)
        if want_engine is None or got_engine is None or want_engine != got_engine:
            return exclude(
                REASON_SHA_MISMATCH,
                f"the run-verified verdict names wheel sha256 {want_sha} but the wheel this run "
                f"built is {got_sha} ({wheel.name}), and the engine-binary fallback does not "
                f"match either (verdict engine {want_engine or 'absent'} vs wheel engine "
                f"{got_engine or 'unreadable'}). A verdict certifies BYTES, not a commit or a "
                "date, so it does not travel to a rebuild; publishing without the CUDA wheel.",
            )
        engine_match = True
        notices.append(
            f"wheel zip sha256 differs from the verdict ({got_sha[:16]} vs {want_sha[:16]}) but "
            f"the CERTIFIED ENGINE BINARY matches byte-for-byte (sha256 {got_engine[:16]}): the "
            "container moved (version metadata / CPU shards), the certified artifact did not. "
            "Including on the engine digest."
        )

    # ── 3. include: stage it, deterministically ───────────────────────────────
    publish_dir.mkdir(parents=True, exist_ok=True)
    dest = publish_dir / wheel.name
    displaced: dict[str, object] | None = None
    if dest.exists():
        existing_sha = _sha256(dest)
        if existing_sha == got_sha:
            notices.append(
                f"{wheel.name} is already in the publish set with these exact bytes; nothing to "
                "stage."
            )
        elif same_name_collision == "refuse":
            decision["decision"] = "exclude"
            decision["reason"] = REASON_COLLISION_REFUSED
            decision["refused"] = True
            notices.append(
                f"REFUSED TO STAGE: {dest} already holds a DIFFERENT wheel "
                f"(sha256 {existing_sha[:16]}) under the filename the verified CUDA wheel needs. "
                "PyPI has one slot per filename, so including would displace it; "
                "--same-name-collision refuse makes that a hard error instead of a silent swap. "
                "Nothing was staged and nothing was moved."
            )
            return decision
        else:
            displaced_dir = publish_dir.parent / f"{publish_dir.name}{DISPLACED_SUFFIX}"
            displaced_dir.mkdir(parents=True, exist_ok=True)
            displaced_path = displaced_dir / dest.name
            shutil.move(str(dest), str(displaced_path))
            displaced = {
                "filename": displaced_path.name,
                "sha256": existing_sha,
                "sha256_16": existing_sha[:16],
                "bytes": displaced_path.stat().st_size,
                "moved_to": str(displaced_path),
            }
            notices.append(
                f"DISPLACED the CPU-variant linux runtime wheel {dest.name} "
                f"(sha256 {existing_sha[:16]}) to {displaced_path}: PyPI has exactly one slot "
                f"for that filename, and the run-verified CUDA wheel (sha256 {got_sha[:16]}) is "
                "taking it. Handing twine both files would NOT publish both -- the first upload "
                "wins and --skip-existing silently swallows the second."
            )
    shutil.copy2(wheel, dest)
    decision["decision"] = "include"
    decision["reason"] = REASON_VERIFIED_ENGINE if engine_match else REASON_VERIFIED
    decision["engine_match"] = engine_match
    decision["staged"] = {
        "filename": dest.name,
        "sha256": got_sha,
        "sha256_16": got_sha[:16],
        "bytes": dest.stat().st_size,
        "path": str(dest),
    }
    decision["displaced"] = displaced
    notices.append(
        f"INCLUDING the run-verified CUDA wheel {wheel.name} (sha256 {got_sha[:16]}, "
        f"{dest.stat().st_size} bytes) in the publish set: the attached verdict names "
        + (
            "this wheel's certified engine binary byte-for-byte (the zip container differs)."
            if engine_match
            else "these exact bytes."
        )
    )
    notices.append(
        "ONE-SLOT NOTICE: because the CUDA wheel carries the shipped linux wheel's filename, this "
        "publish only lands if that filename is not ALREADY on PyPI for this version -- "
        "--skip-existing drops a re-upload silently. The verified wheel therefore has to reach "
        "PyPI on the FIRST publish of its version: bump, build, run the battery, attach the "
        "verdict, then publish."
    )
    return decision


def _emit_outputs(decision: dict[str, object]) -> None:
    """Print the human notice, and the machine lines CI consumes.

    `CUDA_PUBLISH_DECISION` / `CUDA_PUBLISH_REASON` are written to $GITHUB_OUTPUT
    when it is set so a later step can branch on the decision without re-parsing
    prose, and always printed so the same facts are in the job log.
    """
    for notice in decision.get("notices") or []:
        print(f"::notice::{notice}")
    print(f"CUDA_PUBLISH_DECISION={decision['decision']}")
    print(f"CUDA_PUBLISH_REASON={decision['reason']}")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write(f"cuda_decision={decision['decision']}\n")
            handle.write(f"cuda_reason={decision['reason']}\n")
            staged = decision.get("staged")
            if isinstance(staged, dict):
                handle.write(f"cuda_wheel_sha256={staged.get('sha256')}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Decide whether the run-verified CUDA runtime wheel joins this PyPI publish set."
        )
    )
    parser.add_argument(
        "--cuda-dir",
        required=True,
        type=Path,
        help="directory holding the downloaded build-linux-cuda wheel artifact",
    )
    parser.add_argument(
        "--publish-dir",
        required=True,
        type=Path,
        help="the directory twine uploads (dist-pypi); staged into on include",
    )
    parser.add_argument(
        "--verdict",
        type=Path,
        default=None,
        help="path to cuda-release-verdict.json (absent file => exclude, never a failure)",
    )
    parser.add_argument(
        "--same-name-collision",
        choices=("replace", "refuse"),
        default="replace",
        help=(
            "what to do when the publish set already holds a DIFFERENT wheel under the same "
            "filename: replace it (default; the displacement is logged with both hashes) or "
            "refuse with exit 2"
        ),
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="also write the decision record here (tests and audits read this)",
    )
    args = parser.parse_args(argv)

    try:
        decision = decide(
            cuda_dir=args.cuda_dir,
            publish_dir=args.publish_dir,
            verdict_path=args.verdict,
            same_name_collision=args.same_name_collision,
        )
    except OSError as exc:
        # Staging failed AFTER a match: the publish set may now be missing its linux runtime
        # wheel, which is indeterminate rather than "today's behaviour", so this one path is a
        # hard error. Every exclude path above still exits 0.
        print(f"::error::cuda publish gate could not stage the verified wheel: {exc}")
        return 2

    _emit_outputs(decision)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(decision, indent=2, sort_keys=True), encoding="utf-8")
    # A `refuse`-policy collision is the one non-OSError hard error: the verdict matched, so a
    # human asked for this wheel to ship, and the publish set cannot take it without displacing a
    # different wheel. That is indeterminate, not "today's behaviour", so it is loud.
    return 2 if decision.get("refused") else 0


if __name__ == "__main__":
    sys.exit(main())
