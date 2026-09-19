#!/usr/bin/env python3
"""gate_coverage_gemma3_round19.py -- does a gemma-3 gate JSON actually certify ALL FOUR shapes?

argv: <oracle_gate_<arm>.json>
exit 0 = FULL-SCOPE coverage proven ; exit 1 = refused, with every reason printed.

WHY THIS EXISTS AS ITS OWN EVALUATOR, and the defect it replaces. Round 19's first window logged, on
two adjacent lines at 22:29:38Z:

    GATE VERDICT FROM .../oracle_gate_R19_def.json : ALL_PASS scope=pp1024,pp256,rag4096,val550
                                                     out_of_scope=none
    *** THE GATE DID NOT COVER ALL FOUR SHAPES (1 of 4) ... NO timing, NO flip.

The refusal was correct behaviour; the COUNT was wrong. `chain19.sh` formatted that verdict line in
python and then re-parsed it in shell with

    sed -n 's/.*scope=\\([^ ]*\\).*/\\1/p'

`.*scope=` is GREEDY, so it matched the LAST `scope=` in the line -- the one inside
`out_of_scope=none` -- captured `none`, counted one element, and reported "1 of 4" for a gate that
had just enumerated four. A substring of one field name collided with another field name: the same
class of defect the `NO_GEGLUV2`-not-`NO_GEGLU_V2` opt-out spelling exists to avoid in
`scripts/audit_tc_flags.sh`, arriving in the harness instead of in the flag table.

TWO FIXES, and the structural one matters more than the regex.

1. ONE EVALUATOR, ONE VERDICT. The shell no longer re-derives a fact python already knew. Coverage is
   computed AND decided here, and the shell reads only the exit code. A greedy pattern cannot corrupt
   a verdict it is never asked to parse. Re-formatting a fact in one language and re-parsing it in
   another is precisely how one fact came to have two contradictory values on adjacent log lines.

2. COVERAGE IS COUNTED FROM THE CELLS, NOT FROM THE `scope` FIELD. `gate_any.py` writes
   `"scope": sorted(IN_SCOPE)` where `IN_SCOPE` comes from **argv[4] -- the REQUEST**. So that field
   is a statement of intent, not of evidence, and an audit that trusts it can in principle be
   satisfied by a gate that ran nothing. What actually closes the hole in `gate_any.py` is that an
   in-scope prompt with no cells on disk takes its `NOT-RUN` branch and forces `allpass = False`, so
   `all_pass=True` already entails the cells existed. This script asserts that entailment DIRECTLY
   rather than relying on it, and then requires the request-derived and cell-derived counts to AGREE.

WHAT IS ASSERTED, all of it from the JSON's own per-cell records:
  * `all_pass` is True;
  * the requested scope is exactly the four round-6 shapes and `out_of_scope_prompts` is empty;
  * every one of the four prompts carries at least one block with `ran: True` (cell-derived coverage
    == 4, counted from evidence and not from the request);
  * every evaluated block passed, and every block's oracle prefix is exact (`prefix_exact`, with the
    first divergent index named if there is one);
  * every determinism repeat is bit-identical, and there are exactly three of them -- pp256, pp1024
    and val550 at `--max-new 64` each, the `rep2` cells. rag4096's 64-cell is a single run by design
    (that is how round 6's certified shape is specified), so it contributes no repeat;
  * rag4096 stopped early ON AN EOS TOKEN and the oracle also holds EOS at that same index, i.e. the
    22/22 + EOS-stop verdict is corroborated by the reference and not merely self-consistent.

A disagreement between the requested scope and the cells on disk is a refusal WHICHEVER WAY IT
POINTS: a gate that claims four shapes but ran fewer is not a certification, and a gate that ran four
but was asked for fewer means the harness and the evaluator disagree about what was requested, which
is also not something to time on.
"""
import json
import sys

PROMPTS = ("pp256", "pp1024", "val550", "rag4096")
EXPECTED_DET_REPEATS = 3   # pp256/pp1024/val550 at maxnew64; rag4096's 64-cell is a single run


def evaluate(path):
    """Return (summary_line, [problems]). Empty problems == FULL-SCOPE coverage proven."""
    d = json.load(open(path))
    cells = d.get("cells") or {}
    claimed = sorted(d.get("scope") or [])
    oos = sorted(d.get("out_of_scope_prompts") or [])
    with_cells, problems = [], []
    ran = passed = det_repeats = det_bad = 0
    eos_ok = False

    for p in PROMPTS:
        c = cells.get(p) or {}
        if c.get("out_of_scope"):
            continue
        blocks = [c[k] for k in ("maxnew16", "maxnew64") if isinstance(c.get(k), dict)]
        live = [b for b in blocks if b.get("ran") is True]
        if not live:
            problems.append("%s: IN-SCOPE BUT NO CELLS RAN" % p)
            continue
        with_cells.append(p)
        for b in live:
            ran += 1
            if b.get("pass") is True:
                passed += 1
            else:
                problems.append("%s/maxnew%s: %s" % (p, b.get("requested"), b.get("verdict")))
            if b.get("prefix_exact") is not True:
                problems.append("%s: oracle prefix NOT exact (first_divergent_index=%s)"
                                % (p, b.get("first_divergent_index")))
            if b.get("determinism_pass") is False:
                det_bad += 1
            elif b.get("determinism_pass") is True:
                det_repeats += 1
            if p == "rag4096" and b.get("eos_stop") is True and b.get("oracle_also_eos_there") is True:
                eos_ok = True

    if not d.get("all_pass"):
        problems.append("all_pass is not True")
    if claimed != sorted(PROMPTS):
        problems.append("REQUESTED scope %s != the four round-6 shapes" % claimed)
    if oos:
        problems.append("out_of_scope_prompts not empty: %s" % oos)
    if sorted(with_cells) != sorted(PROMPTS):
        problems.append("CELL-derived coverage %s != all four" % sorted(with_cells))
    if ran != passed:
        problems.append("%d of %d evaluated cells did not pass" % (ran - passed, ran))
    if det_bad:
        problems.append("%d determinism repeat(s) DIVERGENT" % det_bad)
    if det_repeats != EXPECTED_DET_REPEATS:
        problems.append("expected %d bit-identical det repeats, found %d"
                        % (EXPECTED_DET_REPEATS, det_repeats))
    if not eos_ok:
        problems.append("rag4096 EOS-stop not corroborated by the oracle at the same index")

    summary = ("claimed_scope=%d prompts_with_cells=%d cells_ran=%d cells_pass=%d det_repeats=%d "
               "out_of_scope=%d rag_eos_stop=%d requested=[%s] cell_covered=[%s]"
               % (len(claimed), len(with_cells), ran, passed, det_repeats, len(oos), int(eos_ok),
                  ",".join(claimed), ",".join(sorted(with_cells))))
    return summary, problems


def main():
    if len(sys.argv) != 2:
        print("usage: gate_coverage_gemma3_round19.py <oracle_gate.json>", file=sys.stderr)
        return 2
    try:
        summary, problems = evaluate(sys.argv[1])
    except Exception as e:                       # a JSON we cannot read is UNKNOWN, never a pass
        print("COVERAGE_UNREADABLE: %s" % e)
        return 1
    print(summary)
    if problems:
        print("COVERAGE_REFUSAL: " + " | ".join(problems))
        return 1
    print("COVERAGE_OK: request-derived and cell-derived coverage AGREE at 4 of 4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
