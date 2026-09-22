#!/usr/bin/env python3
"""wheel_gate_cells.py — RUN THIS ON THE RACE VM, from verify_cuda_release_battery.sh.

It produces the campaign's oracle-gate cells (`gate_<prompt>_maxnew<K>.out`, the exact
filenames and JSON shape `vm_harness/lever3/gate_any.py` reads) by driving the SHIPPED
inference path against the binaries that came out of the CUDA wheel — not the race
session driver.

WHY THE DISTINCTION IS THE WHOLE POINT. Every gate cell the campaign has ever banked was
produced by a `gemma3_*_cuda.mojo` race binary compiled on the VM: one linked driver,
tensor-core shim objects appended, no strip. The wheel a user installs is a different
program — 27 bounded workers built by `scripts/build_runtime_shards.py` from
`mojo/engine/main.mojo` plus the generated dispatch table, `--mcpu x86-64-v3`, stripped and
signed. Certifying the race arm says nothing about the shipped artifact, which is precisely
how the contract came to advertise 142 CUDA kernels that no installed wheel could run. So
this driver:

  * sets ALGENTA_NATIVE_WORKER to the worker binary UNPACKED FROM THE WHEEL and refuses to
    run if that file is missing or is not the one the battery hashed;
  * leaves ALGENTA_RUNTIME_FALLBACK_MODE at its default `deny`, and REFUSES to run if a
    caller set it to `allow` — a gate that quietly fell back to a non-GPU path would pass
    while proving nothing about the CUDA kernels, which is the exact failure this file
    exists to prevent;
  * calls `algenta.inference.decode(...)` with `prompt_token_ids` (pure token math, no
    tokenizer) at `temperature=0`, the shipped greedy path;
  * emits one JSON line per cell carrying `generated` (the token ids), so gate_any.py's
    fp32-oracle comparison, its bit-identical determinism repeat, and its rag4096 EOS-stop
    rule all apply UNCHANGED. The evaluator is reused verbatim; only the thing being
    evaluated is new.

Cells are named exactly as gate_any.py's PLAN expects, including rag4096 having no maxnew16
cell (that is how round 6's certified shape is specified) and the `_rep2` determinism
repeats.

Usage (on the VM, inside the battery):
    python3 wheel_gate_cells.py --runs $WORK/runs --ckpt /mnt/ramblob/g3conv27b \
        --hf-checkpoint ~/gemma3-27b --worker $WORK/site-packages/.../algenta-runtime-worker \
        --specs "pp256:/tmp/g3pp256/prompt_0000.txt pp1024:/tmp/g3pp1024/prompt_0000.txt \
                 val550:/tmp/g3race500/prompt_0000.txt rag4096:/tmp/g3rag/rag4096.txt"

Exit 0 only if every requested cell was written; any exception, refusal, or empty token
stream exits non-zero, because a missing cell must read as a FAILED gate (gate_any.py's
NOT-RUN branch) and never as a passed one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

# gate_any.py's PLAN, restated as the cell schedule. Kept in step by hand rather than imported:
# gate_any.py lives in the race harness and reads its plan from module scope, and importing it here
# would execute it. The names below MUST match its labels or the gate reports NOT-RUN.
#
# EOS IS A TOKENIZER FACT, NOT A CONSTANT OF THIS FILE. 106/1 are gemma3's <end_of_turn>/<eos>;
# Qwen2.5-7B-Instruct's eos is 151645. Hardcoding gemma's pair here made `eos_stop` permanently
# False for any other engine — and `eos_stop` is exactly the field
# gate_coverage_gemma3_round19.py reads to decide whether an early stop was CORROBORATED by the
# oracle or merely self-consistent. A 7B wheel that stopped on its own eos would therefore have
# been refused for a reason that had nothing to do with its numerics. Overridable by EOS_TOKENS,
# with gemma's pair kept as the default so existing callers are unchanged.
EOS_TOKENS = tuple(
    int(tok)
    for tok in os.environ.get("EOS_TOKENS", "106,1").replace(" ", "").split(",")
    if tok
)
# Shapes certified at maxnew64 with no determinism repeat. Shared with gate_any.py's PLAN and the
# coverage evaluator's expected-repeat count so all three schedulers agree by construction.
SINGLE_RUN_SHAPES = frozenset(
    name.strip()
    for name in os.environ.get("GATE_COVERAGE_SINGLE_RUN", "rag4096").split(",")
    if name.strip()
)


def _sha256_16(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _read_ids(path: Path) -> list[int]:
    """The campaign's fixtures are comma-separated token ids on ONE line (so `wc -w` reports 1 for a
    perfectly good 4096-id fixture — a cosmetic mis-count that cost a diagnostic round trip on
    2026-09-17). Count ids, not words."""
    raw = path.read_text(encoding="utf-8", errors="replace").strip()
    ids = [int(tok) for tok in raw.replace("\n", ",").split(",") if tok.strip()]
    if not ids:
        raise SystemExit(f"fixture {path} holds no token ids")
    return ids


def _schedule(specs: list[str]) -> list[tuple[str, str, Path, int]]:
    """(prompt, label, fixture, max_new) for every cell gate_any.py will look for."""
    out: list[tuple[str, str, Path, int]] = []
    for spec in specs:
        if ":" not in spec:
            raise SystemExit(f"--specs entry is not name:path -> {spec!r}")
        name, _, fixture = spec.partition(":")
        fixture_path = Path(fixture)
        if not fixture_path.is_file():
            raise SystemExit(f"fixture missing for {name}: {fixture_path}")
        # Shapes with no 16-token cell come from GATE_COVERAGE_SINGLE_RUN -- the SAME env var
        # gate_any.py builds its PLAN from and the coverage evaluator derives its expected repeat
        # count from. It used to be the literal `name == "rag4096"` here, which is a gemma round-6
        # fact: three schedulers that each hardcode it differently is how cells get run that no
        # oracle row compares, or expected that were never scheduled.
        widths = (64,) if name in SINGLE_RUN_SHAPES else (16, 64)
        for width in widths:
            out.append((name, f"gate_{name}_maxnew{width}", fixture_path, width))
            if width == 64:
                # The determinism repeat: gate_any.py compares it bit-for-bit against the first
                # 64-token run and reports `2/2 bit-identical` or DIVERGENT.
                out.append((name, f"gate_{name}_maxnew64_rep2", fixture_path, 64))
    return out


def _emit_cell(
    label: str,
    out_path: Path,
    record: dict,
    error: str | None,
    requested: int,
    elapsed: float,
) -> None:
    """Write and print one cell in the canonical form gate_any.py reads.

    Shared by both engine paths so the two cannot drift in the one thing the evaluator depends on:
    the LAST stdout line starting with `{` and containing `"generated"` is the cell's verdict input,
    because under the battery this process runs inside cell_watchdog's cw_cell, which captures
    STDOUT into the cell file. The `--runs` copy is the audit trail for a bare invocation.
    """
    line = json.dumps(record)
    if error is not None:
        # No `generated` key on purpose: that is what makes gate_any.py take its NOT-RUN branch, so a
        # refused cell can never be read as a passed one.
        print(f"CELL {label} FAILED after {elapsed:.1f}s: {error}")
    else:
        with out_path.open("w", encoding="utf-8") as handle:
            handle.write(f"CELL {label} elapsed={elapsed:.1f}s\n")
            handle.write(line + "\n")
        generated = record.get("generated") or []
        print(
            f"CELL {label} END rc=0 n_generated={len(generated)}/{requested} "
            f"eos_stop={record.get('eos_stop')} decode_tok_s={record.get('decode_tok_s')} "
            f"elapsed={elapsed:.1f}s"
        )
    print(line)


def _run_serve_cell(
    *,
    label: str,
    name: str,
    ids: list[int],
    width: int,
    args: argparse.Namespace,
    worker_sha: str,
    wheel_sha: str,
    started: float,
):
    """One cell through `algenta serve --backend cuda --json`, the CUDA surface a user gets.

    Imported lazily and run as a SUBPROCESS per cell: each cell then gets its own engine lifetime,
    which is what makes a hang killable by cell_watchdog and what keeps one cell's state out of the
    next. Parsing lives in serve_cell_record.py so it can be unit-tested without a GPU, a wheel, or
    an engine binary.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from serve_cell_record import build_serve_command, parse_serve_output

    argv = build_serve_command(
        python=args.python,
        model=str(args.hf_checkpoint),
        converted_dir=str(args.ckpt),
        prompt_token_ids=ids,
        max_new_tokens=width,
        weights_dtype=args.weights_dtype,
        timeout=args.timeout,
    )
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=args.timeout + 60.0, check=False
        )
        returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = -1
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = "serve cell exceeded its %.0fs timeout" % (args.timeout + 60.0)
    except Exception as exc:  # noqa: BLE001 - a launch failure is a cell refusal, not a crash
        returncode = -1
        stdout = ""
        stderr = "%s: %s" % (type(exc).__name__, exc)
    elapsed = time.time() - started
    record, error = parse_serve_output(
        label=label,
        prompt=name,
        n_prompt=len(ids),
        requested=width,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        worker_sha256_16=worker_sha,
        wheel_sha256_16=wheel_sha,
        cell_seconds=elapsed,
        eos_tokens=EOS_TOKENS,
    )
    return record, error, elapsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", required=True, type=Path, help="cell output directory")
    parser.add_argument(
        "--ckpt",
        required=True,
        type=Path,
        help="the CONVERTED checkpoint dir (manifest.json + weights.blob) the shipped path loads",
    )
    parser.add_argument(
        "--hf-checkpoint",
        required=True,
        type=Path,
        help="the HF snapshot dir decode() reads config/architecture facts from",
    )
    parser.add_argument(
        "--worker",
        required=True,
        type=Path,
        help="the runtime worker binary UNPACKED FROM THE WHEEL under test",
    )
    parser.add_argument(
        "--wheel",
        required=True,
        type=Path,
        help="the wheel the worker came from (hashed into every cell line)",
    )
    parser.add_argument(
        "--specs",
        required=True,
        nargs="+",
        help="gate specs as name:/path/to/fixture.txt, one per prompt shape",
    )
    parser.add_argument(
        "--only",
        default=None,
        help=(
            "run exactly this one cell label and exit. The battery passes it so each cell runs in "
            "its own process under cell_watchdog's cw_cell, which is what gives every cell its own "
            "clocks_before/clocks_after/offpin sample instead of one sample for the whole gate."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1800.0,
        help="per-call runtime timeout in seconds (the 27B blob load dominates a cell)",
    )
    parser.add_argument(
        "--engine",
        choices=("decode", "serve"),
        default="decode",
        help=(
            "which shipped surface drives the cell. 'decode' (the DEFAULT, unchanged) calls "
            "algenta.inference.decode in-process -- that function is the METAL resident session and "
            "takes no backend argument, so it is right for the gemma/Metal lanes and cannot reach a "
            "CUDA kernel. 'serve' runs one `algenta serve --backend cuda --json` subprocess per cell, "
            "which resolves the BUNDLED conform_generate_cuda engine out of the wheel under test -- "
            "the surface a CUDA user actually gets. See serve_cell_record.py for why the two differ."
        ),
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help=(
            "interpreter for `--engine serve` (it runs `<python> -m algenta.cli`). Defaults to this "
            "process's own interpreter, which under the battery is the wheel's python3.14."
        ),
    )
    parser.add_argument(
        "--weights-dtype",
        choices=("f32", "f64"),
        default=None,
        help="forwarded to `algenta serve` in serve mode only; omitted means serve's own default",
    )
    args = parser.parse_args(argv)

    # ── REFUSALS, BEFORE ANY GPU WORK ────────────────────────────────────────────────────────
    fallback = (os.environ.get("ALGENTA_RUNTIME_FALLBACK_MODE") or "deny").strip().lower()
    if fallback != "deny":
        print(
            f"FATAL: ALGENTA_RUNTIME_FALLBACK_MODE={fallback!r}. A gate that can fall back to a "
            "non-GPU path proves nothing about the CUDA kernels, so this driver refuses to run "
            "with anything but the default `deny`.",
            file=sys.stderr,
        )
        return 2
    if not args.worker.is_file():
        print(f"FATAL: no worker binary at {args.worker}", file=sys.stderr)
        return 2
    if not args.wheel.is_file():
        print(f"FATAL: no wheel at {args.wheel}", file=sys.stderr)
        return 2
    if not args.ckpt.is_dir():
        print(f"FATAL: converted checkpoint missing at {args.ckpt}", file=sys.stderr)
        return 2
    if not (args.ckpt / "manifest.json").is_file():
        print(
            f"FATAL: {args.ckpt} has no manifest.json — the shipped path needs the CONVERTED "
            "checkpoint (manifest.json + weights.blob), not an HF snapshot.",
            file=sys.stderr,
        )
        return 2
    if not args.hf_checkpoint.is_dir():
        print(f"FATAL: HF checkpoint dir missing at {args.hf_checkpoint}", file=sys.stderr)
        return 2

    # Point the shipped loader at the wheel's binary, and prove in the log which bytes that is.
    os.environ["ALGENTA_NATIVE_WORKER"] = str(args.worker)
    os.environ["ALGENTA_RUNTIME_WORKER"] = str(args.worker)
    worker_sha = _sha256_16(args.worker)
    wheel_sha = _sha256_16(args.wheel)
    args.runs.mkdir(parents=True, exist_ok=True)

    cells = _schedule(args.specs)
    if args.only:
        cells = [c for c in cells if c[1] == args.only]
        if not cells:
            print(
                f"FATAL: --only {args.only!r} matches no cell in the schedule derived from "
                f"{args.specs}; refusing to run nothing and report success.",
                file=sys.stderr,
            )
            return 2
    print(f"wheel={args.wheel.name} wheel_sha256_16={wheel_sha}")
    print(f"worker={args.worker} worker_sha256_16={worker_sha} bytes={args.worker.stat().st_size}")
    print(f"python={platform.python_version()} fallback_mode={fallback} cells={len(cells)}")
    print(f"labels={[c[1] for c in cells]}")

    runtime = None
    decode = None
    if args.engine == "decode":
        try:
            from algenta import MojoRuntime
            from algenta.inference import decode
        except Exception as exc:  # noqa: BLE001 - an unimportable shipped path is a hard refusal
            print(f"FATAL: the shipped path is not importable: {exc}", file=sys.stderr)
            print(
                "  (PYTHONPATH must carry the wheel's unpacked site-packages and the synced tree's "
                "packages/algenta)",
                file=sys.stderr,
            )
            return 2
        runtime = MojoRuntime(mode="local", timeout=args.timeout)
    else:
        # SERVE MODE drives `<python> -m algenta.cli serve --backend cuda`, so what must be
        # importable is the CLI module, not decode(). Checked HERE rather than letting the first
        # cell fail seven times over for one missing package. decode() is deliberately NOT imported
        # in this mode: it is the metal resident session, and importing it would only invite a
        # future reader to think this path can reach a CUDA kernel.
        try:
            import algenta.cli  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            print(f"FATAL: algenta.cli is not importable, so `--engine serve` cannot run: {exc}",
                  file=sys.stderr)
            print(
                "  (PYTHONPATH must carry the wheel's unpacked site-packages and the synced tree's "
                "packages/algenta)",
                file=sys.stderr,
            )
            return 2
        print(f"engine=serve path=`algenta serve --backend cuda --json` python={args.python}")
    failures = 0
    for name, label, fixture, width in cells:
        out_path = args.runs / f"{label}.out"
        ids = _read_ids(fixture)
        started = time.time()
        print(f"CELL {label} START prompt={name} n_prompt={len(ids)} max_new={width}")
        if args.engine == "serve":
            record, error, elapsed = _run_serve_cell(
                label=label, name=name, ids=ids, width=width, args=args,
                worker_sha=worker_sha, wheel_sha=wheel_sha, started=started,
            )
            _emit_cell(label, out_path, record, error, width, elapsed)
            if error is not None:
                failures += 1
            elif not record.get("generated"):
                failures += 1
                print(f"CELL {label} EMPTY GENERATION (0 tokens) — counted as a failure")
            continue
        try:
            result = decode(
                runtime,
                checkpoint_dir=str(args.hf_checkpoint),
                converted_checkpoint_dir=str(args.ckpt),
                prompt_token_ids=ids,
                max_new_tokens=width,
                temperature=0.0,
            )
        except Exception as exc:  # noqa: BLE001 - a typed refusal must be visible, not swallowed
            failures += 1
            elapsed = time.time() - started
            print(f"CELL {label} FAILED after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
            failure = {
                "label": label,
                "error": f"{type(exc).__name__}: {exc}",
                "ran": False,
                "worker_sha256_16": worker_sha,
                "wheel_sha256_16": wheel_sha,
            }
            # Printed to stdout as well as written, because under the battery this process runs
            # inside cell_watchdog's cw_cell, which captures STDOUT into the cell file gate_any.py
            # reads. A record with no `generated` key makes the evaluator take its NOT-RUN branch —
            # a failed cell reads as a failed gate, never as a passed one.
            print(json.dumps(failure))
            out_path.write_text(json.dumps(failure) + "\n", encoding="utf-8")
            continue

        # `token_ids` is prompt tokens followed by every generated token, so the generated slice is
        # what the oracle compares. An empty generation is a failure, not a pass.
        all_ids = list(result.token_ids or [])
        generated = all_ids[result.n_prompt :] if result.n_prompt else all_ids
        elapsed = time.time() - started
        record = {
            "label": label,
            "prompt": name,
            "n_prompt": len(ids),
            "requested": width,
            "generated": generated,
            "n_generated": len(generated),
            "stopped_on_eos": bool(result.stopped_on_eos),
            "last_token": generated[-1] if generated else None,
            "eos_stop": bool(generated) and generated[-1] in EOS_TOKENS and len(generated) < width,
            "ttft_ms": (
                round(len(ids) / result.prefill_tokens_per_sec * 1000.0, 3)
                if result.prefill_tokens_per_sec > 0
                else None
            ),
            "decode_tok_s": round(result.decode_tokens_per_sec, 3),
            "dispatches_per_token": result.dispatches_per_token,
            "arm": "cuda_release_wheel",
            "worker_sha256_16": worker_sha,
            "wheel_sha256_16": wheel_sha,
            "cell_seconds": round(elapsed, 1),
        }
        with out_path.open("w", encoding="utf-8") as handle:
            handle.write(f"CELL {label} elapsed={elapsed:.1f}s\n")
            handle.write(json.dumps(record) + "\n")
        # THE CANONICAL CELL OUTPUT IS THIS STDOUT LINE. gate_any.py reads `<runs>/<label>.out`, and
        # under the battery that file is cell_watchdog's capture of this process's stdout — exactly
        # how the race driver's cells have always reached the evaluator. The `--runs` copy above is
        # the audit trail for a bare invocation, not what the gate consumes.
        print(json.dumps(record))
        if not generated:
            failures += 1
            print(f"CELL {label} EMPTY GENERATION (0 tokens) — counted as a failure")
        else:
            print(
                f"CELL {label} END rc=0 n_generated={len(generated)}/{width} "
                f"eos_stop={record['eos_stop']} decode_tok_s={record['decode_tok_s']} "
                f"elapsed={elapsed:.1f}s"
            )

    print(f"CELLS written={len(cells)} failures={failures} runs_dir={args.runs}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
