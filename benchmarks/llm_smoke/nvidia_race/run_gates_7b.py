"""run_gates_7b.py — the 7B-lane gate (a)/(b) runner: token identity vs the transformers fp32
reference (ref_tokens.json) on ALL five chat prompts AND the 256-token fixture, BOTH arms.

For each arm (f32, p3) and each of the six prompts it runs
    qwen25_7b_p3_graph_cuda --checkpoint <ckpt> --arm <arm> --gen-only 16 \
        --prompt-ids <ids> --oracle <ref ids> --dump <file>
and diffs the dumped 16-token stream against ref_tokens.json. Gate (a) of the campaign brief
requires 16/16 identity on every prompt for both arms; gate (b) (first-token sanity) is the
strict subset of that. Exit 0 only when every prompt passes for both arms.

Usage (on the VM; the driver binary is found by NAME -- qwen25_7b_p3_graph_cuda -- in
$BENCH_BIN_DIR, then PATH, through benchmarks/bench_tools.py, copied beside this file):
    BENCH_BIN_DIR=~/w7b_bins python3 run_gates_7b.py --ckpt /tmp/w7b/ckpt --workdir /tmp/w7b/gate
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # in-repo benchmarks/
sys.path.insert(0, str(Path(__file__).resolve().parent))  # a standalone copy beside this file
from bench_tools import ToolError, run_tool, tool_path

N_TOKENS = 16
DRIVER_TOOL = "qwen25_7b_p3_graph_cuda"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="/tmp/w7b/ckpt")
    ap.add_argument("--workdir", default="/tmp/w7b/gate")
    ap.add_argument("--arms", default="f32,p3")
    args = ap.parse_args()
    try:
        driver = tool_path(DRIVER_TOOL)
    except ToolError as exc:
        raise SystemExit(f"{ap.prog}: error: {exc}") from None
    print(f"driver: {driver}", flush=True)

    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    prompts = json.loads((Path(args.ckpt) / "prompts.json").read_text())
    ref = json.loads((work / "ref_tokens.json").read_text())

    cases = [("fixture", prompts["fixture"]["ids"], ref["fixture"]["generated_ids"])]
    for idx, entry in enumerate(prompts["chat_prompts"]):
        name = f"chat_{idx}"
        cases.append((name, entry["ids"], ref[name]["generated_ids"]))

    all_pass = True
    for arm in args.arms.split(","):
        print(f"==== arm={arm} ====", flush=True)
        for name, ids, ref_ids in cases:
            id_csv = ",".join(str(int(t)) for t in ids)
            oracle_csv = ",".join(str(int(t)) for t in ref_ids[:N_TOKENS])
            dump = work / f"gate_{arm}_{name}.txt"
            r = run_tool(driver, "--checkpoint", args.ckpt, "--arm", arm,
                         "--gen-only", str(N_TOKENS), "--prompt-ids", id_csv,
                         "--oracle", oracle_csv, "--dump", dump,
                         capture_output=True, text=True)
            if r.returncode != 0 or "GEN_ONLY DONE" not in r.stdout:
                print(f"{arm}/{name}: RUN FAILED rc={r.returncode}", flush=True)
                print(r.stdout[-1500:], flush=True)
                print(r.stderr[-1500:], flush=True)
                all_pass = False
                continue
            got = [int(line) for line in dump.read_text().split() if line.strip()]
            want = ref_ids[:N_TOKENS]
            ok = got[:N_TOKENS] == want
            if not ok:
                all_pass = False
                first = next((i for i in range(min(len(got), N_TOKENS))
                              if got[i] != want[i]), min(len(got), N_TOKENS))
                print(f"{arm}/{name}: FAIL — first mismatch at token {first}: "
                      f"got {got[:8]} want {want[:8]}", flush=True)
            else:
                print(f"{arm}/{name}: PASS {N_TOKENS}/{N_TOKENS} "
                      f"({len(ids)} prompt tokens)", flush=True)

    print("GATE (a) RESULT:", "PASS — token identity on all prompts, both arms"
          if all_pass else "FAIL", flush=True)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
