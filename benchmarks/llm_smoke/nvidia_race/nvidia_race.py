"""nvidia_race.py — the NVIDIA race harness: llama.cpp (CUDA build at the campaign pin) vs the
algenta CUDA-native resident session, on the campaign's 256-token race fixture, under the race
ledger's frozen discipline (20 runs/cell, median, relative IQR <= 5%, >10%-deviation outliers
flagged; verdicts reported, never adjusted).

Cells
-----
* llama-bench (llama.cpp's own microbenchmark): pp256 / pp512 / tg128, for the F16 GGUF and the
  Q8_0 GGUF, 20 invocations each with -r 1 (one measurement per invocation => the 20-sample
  distribution the frozen table prescribes).
* llama-completion race fixture: the EXACT 256-token race prompt, -n 64 and -n 256, greedy
  (--temp 0), all layers on the GPU (-ngl 99); parses the tool's own "prompt eval time" /
  "eval time" lines. 20 invocations per gen length. (llama-completion = raw completion, no
  chat-template wrapping — keeps the fixture at exactly 256 prompt tokens.)
* algenta: qwen3_generate_cuda (oracle gate, exits nonzero on mismatch) then
  qwen3_bench_cuda_gen64 / _gen256 — each runs the frozen 20 timed generations in-process and
  prints median + rel IQR + verdict itself.

Clock evidence: an `nvidia-smi --query-gpu` sampler (500 ms) runs alongside every timed window
and its min/max samples are written into the summary.

Output: nvidia_race_summary.json + a human-readable table on stdout.

Usage (on the GPU VM):
    python3 benchmarks/llm_smoke/nvidia_race/nvidia_race.py \
        --llama-dir ~/llama.cpp --models-dir ~/models \
        --algenta-dir ~/algenta_nv --out ~/race_results
"""

import argparse
import json
import re
import signal
import subprocess
import statistics
import sys
import time
from pathlib import Path

RACE_PROMPT = "The capital of France is Paris. " * 36 + "The capital of France"

LLAMA_BENCH_CELLS = [
    # (label, prompt-tokens list, gen-tokens list)
    ("pp256", [256], []),
    ("pp512", [512], []),
    ("tg128", [], [128]),
]


def log(msg: str) -> None:
    print(f"[nvidia_race {time.strftime('%H:%M:%S')}] {msg}", flush=True)


class ClockSampler:
    """`nvidia-smi --query-gpu` at 500 ms; captures clock/power/thermal evidence for the run."""

    def __init__(self, out_path: Path):
        self.out_path = out_path
        self.proc = None

    def start(self) -> None:
        handle = self.out_path.open("w")
        self.proc = subprocess.Popen(
            [
                "nvidia-smi",
                "--query-gpu=clocks.sm,clocks.mem,temperature.gpu,power.draw,utilization.gpu",
                "--format=csv,noheader,nounits",
                "-lms", "500",
            ],
            stdout=handle, stderr=subprocess.DEVNULL,
        )
        self._handle = handle

    def stop(self) -> dict:
        if self.proc is None:
            return {}
        self.proc.send_signal(signal.SIGINT)
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self._handle.close()
        sm_clocks: list[int] = []
        powers: list[float] = []
        temps: list[int] = []
        for line in self.out_path.read_text().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                try:
                    sm_clocks.append(int(parts[0]))
                    temps.append(int(parts[2]))
                    powers.append(float(parts[3]))
                except ValueError:
                    continue
        if not sm_clocks:
            return {"error": "no clock samples captured"}
        return {
            "n_samples": len(sm_clocks),
            "sm_clock_mhz_min": min(sm_clocks),
            "sm_clock_mhz_max": max(sm_clocks),
            "temp_c_max": max(temps),
            "power_w_max": max(powers),
        }


def frozen_stats(samples: list[float]) -> dict:
    """The frozen table: median, rel IQR, >10%-deviation outlier census, PASS/FLAG verdict."""
    s = sorted(samples)
    n = len(s)
    median = statistics.median(s)

    def pct(q: float) -> float:
        pos = (n - 1) * q
        lo = int(pos)
        frac = pos - lo
        if lo >= n - 1:
            return s[-1]
        return s[lo] + frac * (s[lo + 1] - s[lo])

    p25, p75 = pct(0.25), pct(0.75)
    rel_iqr = (p75 - p25) / median
    outliers = sum(1 for x in s if abs(x - median) / median > 0.10)
    return {
        "n": n,
        "median": median,
        "p25": p25,
        "p75": p75,
        "rel_iqr": rel_iqr,
        "outliers_gt_10pct": outliers,
        "verdict": "PASS" if rel_iqr <= 0.05 else "FLAGGED",
        "samples": s,
    }


def run_llama_bench(bench_bin: Path, gguf: Path, label: str, n_prompt: int, n_gen: int,
                    runs: int) -> dict:
    """20 invocations of llama-bench with -r 1: one independent measurement per run."""
    samples = []
    for i in range(runs):
        # Defaults throughout — the configuration llama.cpp publishes its own numbers with;
        # the race fixture itself is timed separately through llama-completion.
        cmd = [str(bench_bin), "-m", str(gguf), "-r", "1"]
        if n_prompt:
            cmd += ["-p", str(n_prompt)]
        if n_gen:
            cmd += ["-n", str(n_gen)]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        # llama-bench rows: "| model | size | params | backend | ngl | test | t/s |"
        # Match the EXACT test label: `-p N` invocations ALSO run the default tg128 row, so
        # accepting any pp/tg row silently reports tg numbers for the pp cells (caught on the
        # first A100 run: pp256/pp512/tg128 all parsed to the tg128 value).
        tok_s = None
        for line in out.splitlines():
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            if len(cells) < 3:
                continue
            test_cell, rate_cell = cells[-3], cells[-2]
            if test_cell == label:
                m = re.match(r"([\d.]+)\s*[±]", rate_cell) or re.match(r"([\d.]+)", rate_cell)
                if m:
                    tok_s = float(m.group(1))
        if tok_s is None:
            raise RuntimeError(f"llama-bench {label} run {i}: could not parse a tok/s row:\n{out}")
        samples.append(tok_s)
    return frozen_stats(samples)


def run_llama_cli_fixture(cli_bin: Path, gguf: Path, prompt_file: Path, gen: int,
                          runs: int) -> dict:
    """20 invocations of llama-completion on the exact race fixture; parses its own timing.

    llama-completion (RAW completion, no conversation mode), NOT llama-cli: the race fixture is
    256 raw tokens, and llama-cli defaults to conversation mode, which wraps the prompt in the
    Qwen3 chat template (im_start/im_end) and inflates the prompt past 256 tokens — a scope
    mismatch. This mirrors how the Apple Silicon race measured llama.cpp (llama-server
    /completion, raw tokens). The GGUF carries a chat template even for the Base model, so any
    conversation-aware tool would apply it; llama-completion does not.

    Scope alignment with the algenta bench (stated, not hidden): algenta's PREFILL covers the
    256 prompt tokens INCLUDING the lm_head+argmax that yields the first generated token, and
    its DECODE covers `gen` autoregressive steps AFTER prefill. llama-completion's prompt-eval
    phase likewise processes the 256 prompt tokens and samples the first generated token, then
    its `eval` phase covers the subsequent tokens. We pass `-n gen+1` so the eval phase spans
    exactly `gen` tokens, matching algenta's decode window token-for-token; the observed eval
    token count is recorded in the cell so the scope is auditable rather than assumed.
    """
    pf_samples, tg_samples = [], []
    eval_counts = set()
    for i in range(runs):
        cmd = [
            str(cli_bin), "-m", str(gguf), "-f", str(prompt_file),
            "-n", str(gen + 1), "--temp", "0.0", "-ngl", "99",
            # -no-cnv is LOAD-BEARING: with the GGUF's chat template present, conversation
            # mode auto-enables, wraps the prompt in the template (>256 tokens), and waits
            # interactively after generation. Run-verified: with -no-cnv the prompt eval
            # spans exactly 256 tokens and the tool exits cleanly.
            "-no-cnv", "--no-display-prompt",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        # llama-cli prints the llama_print_timings block to stderr; the generated text to
        # stdout. Join both so the timing regexes are robust to either stream.
        out = proc.stdout + "\n" + proc.stderr
        if proc.returncode != 0:
            raise RuntimeError(f"llama-cli run {i} rc={proc.returncode}: {out[-800:]}")
        pf = re.search(r"prompt eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens", out)
        # Negative lookbehind so "eval time" does not match inside "prompt eval time".
        tg = re.search(r"(?<!prompt )eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)", out)
        if not pf or not tg:
            raise RuntimeError(
                f"llama-cli run {i} (gen={gen}): timing lines missing. tail:\n{out[-800:]}"
            )
        pf_ms, pf_tokens = float(pf.group(1)), int(pf.group(2))
        tg_ms, tg_tokens = float(tg.group(1)), int(tg.group(2))
        eval_counts.add(tg_tokens)
        if pf_tokens != 256:
            raise RuntimeError(f"llama-cli run {i}: prompt tokens off ({pf_tokens} != 256)")
        pf_samples.append(pf_tokens / (pf_ms / 1000.0))
        tg_samples.append(tg_tokens / (tg_ms / 1000.0))
    return {
        "prefill": frozen_stats(pf_samples),
        "decode": frozen_stats(tg_samples),
        "observed_eval_tokens": sorted(eval_counts),
        "requested_gen": gen,
    }


def run_algenta(oracle_bin: Path, bench_bin: Path) -> dict:
    """The algenta side: oracle gate first (nonzero exit = mismatch), then the bench driver,
    which runs the frozen 20 timed generations in-process and reports its own stats."""
    oracle = subprocess.run([str(oracle_bin)], capture_output=True, text=True)
    oracle_ok = oracle.returncode == 0 and "RESULT: PASS" in oracle.stdout

    bench = subprocess.run([str(bench_bin)], capture_output=True, text=True)
    out = bench.stdout + "\n" + bench.stderr
    pf = re.search(r"RESULT prefill_tok_per_s:\s*([\d.]+)", out)
    dc = re.search(r"RESULT decode_tok_per_s:\s*([\d.]+)", out)
    pf_iqr = re.search(r"prefill: median [\d.]+ ms \| p25 [\d.]+ \| p75 [\d.]+ \| rel IQR ([\d.]+) % \| outliers \(>10% dev\): (\d+) \| (PASS|FLAGGED)", out)
    dc_iqr = re.search(r"decode: median [\d.]+ ms \| p25 [\d.]+ \| p75 [\d.]+ \| rel IQR ([\d.]+) % \| outliers \(>10% dev\): (\d+) \| (PASS|FLAGGED)", out)
    if bench.returncode != 0 or not pf or not dc:
        raise RuntimeError(f"algenta bench failed rc={bench.returncode}\n{out[-2000:]}")
    return {
        "oracle_pass": oracle_ok,
        "prefill_tok_s": float(pf.group(1)),
        "decode_tok_s": float(dc.group(1)),
        "prefill_rel_iqr_pct": float(pf_iqr.group(1)) if pf_iqr else None,
        "prefill_outliers": int(pf_iqr.group(2)) if pf_iqr else None,
        "prefill_verdict": pf_iqr.group(3) if pf_iqr else None,
        "decode_rel_iqr_pct": float(dc_iqr.group(1)) if dc_iqr else None,
        "decode_outliers": int(dc_iqr.group(2)) if dc_iqr else None,
        "decode_verdict": dc_iqr.group(3) if dc_iqr else None,
        "raw_output": out,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llama-dir", default="~/llama.cpp")
    ap.add_argument("--models-dir", default="~/models")
    ap.add_argument("--algenta-dir", default="~/algenta_nv")
    ap.add_argument("--out", default="~/race_results")
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--skip-algenta", action="store_true")
    ap.add_argument("--skip-llama", action="store_true")
    args = ap.parse_args()

    llama_dir = Path(args.llama_dir).expanduser()
    models_dir = Path(args.models_dir).expanduser()
    algenta_dir = Path(args.algenta_dir).expanduser()
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    bench_bin = llama_dir / "build/bin/llama-bench"
    # llama-completion, not llama-cli: raw completion without conversation/chat-template
    # wrapping, so the fixture stays exactly 256 prompt tokens (see run_llama_cli_fixture).
    cli_bin = llama_dir / "build/bin/llama-completion"
    if not cli_bin.is_file():
        raise SystemExit(
            f"missing {cli_bin}: build it with `cmake --build <build> --target llama-completion`"
        )
    f16_gguf = models_dir / "qwen3-0.6b-f16.gguf"
    q8_gguf = models_dir / "qwen3-0.6b-q8_0.gguf"
    prompt_file = out_dir / "race_prompt.txt"
    prompt_file.write_text(RACE_PROMPT)

    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,pci.bus_id",
         "--format=csv,noheader"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    log(f"GPU: {gpu}")

    sampler = ClockSampler(out_dir / "clocks.csv")
    sampler.start()
    results: dict = {"gpu": gpu, "runs_per_cell": args.runs, "cells": {}}

    try:
        if not args.skip_llama:
            for fmt_label, gguf in (("f16", f16_gguf), ("q8_0", q8_gguf)):
                for label, ps, ns in LLAMA_BENCH_CELLS:
                    n_p = ps[0] if ps else 0
                    n_g = ns[0] if ns else 0
                    log(f"llama-bench {fmt_label} {label} x{args.runs}")
                    results["cells"][f"llama_bench_{fmt_label}_{label}"] = run_llama_bench(
                        bench_bin, gguf, label, n_p, n_g, args.runs
                    )
            for fmt_label, gguf in (("f16", f16_gguf), ("q8_0", q8_gguf)):
                for gen in (64, 256):
                    log(f"llama-completion fixture {fmt_label} gen={gen} x{args.runs}")
                    results["cells"][
                        f"llama_completion_fixture_{fmt_label}_gen{gen}"
                    ] = run_llama_cli_fixture(cli_bin, gguf, prompt_file, gen, args.runs)

        if not args.skip_algenta:
            for gen in (64, 256):
                suffix = "gen64" if gen == 64 else "gen256"
                log(f"algenta oracle + bench {suffix}")
                results["cells"][f"algenta_{suffix}"] = run_algenta(
                    algenta_dir / "qwen3_generate_cuda",
                    algenta_dir / f"qwen3_bench_cuda_{suffix}",
                )
    finally:
        results["clocks"] = sampler.stop()

    summary_path = out_dir / "nvidia_race_summary.json"
    summary_path.write_text(json.dumps(results, indent=2))
    log(f"wrote {summary_path}")

    # ── human-readable table ──
    print("\n=== NVIDIA race summary ===")
    print(f"GPU: {gpu}")
    print(f"clocks: {results['clocks']}")
    for name, cell in results["cells"].items():
        if "median" in cell:
            print(f"  {name:38s} median={cell['median']:9.1f} tok/s "
                  f"relIQR={cell['rel_iqr'] * 100:5.2f}% {cell['verdict']} "
                  f"(outliers={cell['outliers_gt_10pct']})")
        elif "prefill" in cell and "decode" in cell:
            pf, dc = cell["prefill"], cell["decode"]
            scope = f" eval_tokens={cell.get('observed_eval_tokens')}" \
                if "observed_eval_tokens" in cell else ""
            print(f"  {name:38s} pf median={pf['median']:9.1f} ({pf['verdict']}) "
                  f"dc median={dc['median']:9.1f} ({dc['verdict']}){scope}")
        else:
            print(f"  {name:38s} oracle={cell.get('oracle_pass')} "
                  f"pf={cell.get('prefill_tok_s')} dc={cell.get('decode_tok_s')} "
                  f"pfIQR={cell.get('prefill_rel_iqr_pct')}% dcIQR={cell.get('decode_rel_iqr_pct')}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
