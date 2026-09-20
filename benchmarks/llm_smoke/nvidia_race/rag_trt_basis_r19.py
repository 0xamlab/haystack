#!/usr/bin/env python3
"""rag_trt_basis_r19.py -- which TensorRT-LLM rag4096 comparator does round 19's rag row rest on?

argv: <trtllm_rag4096.json>   (this window's same-session re-serve; may be absent or unreadable)
prints ONE line: the chosen basis and the arithmetic that chose it. Always exits 0 -- a missing or
unreadable comparator is a fact to record, not a crash, and the caller must still be able to log which
basis it fell back to.

WHY THIS DECISION IS EXPLICIT AND RECORDED. `lv3_trtllm.sh` serves all three cells from ONE server
startup, so a fresh rag4096 comparator costs nothing extra once the server is up. Round 18 could not
re-serve at all and had to reuse round 13's same-session pair (429.400 ms) for its rag row, which made
its 1.1653x headline CROSS-SESSION -- a caveat the round-18 ledger carries and this window can retire.
The owner's rule for round 19: prefer the fresh same-session number UNLESS a single confirmation serve
drifts more than 1% from the basis round 18 used, in which case reuse round 18's pair and SAY SO.
Either way the choice is written down, because a ratio whose comparator basis is unstated is not
auditable -- and the 1% rule is the campaign's own reproduction test for a same-session re-serve, the
same threshold `summarize_gemma3_round6.py` uses to decide whether to label a column CROSS-SESSION.

It is its own file rather than an inline heredoc for two reasons that round 19 paid for: a heredoc
inside `$( )` is unsafe on macOS bash 3.2, and an inline copy cannot be regression-tested off-box.
"""
import json
import os
import statistics
import sys

# every rag4096 comparator this campaign has banked, newest first
R13 = 429.400      # round 13's same-session pair -- the basis round 18's rag row reused
R14 = 428.212      # round 14's same-session re-serve
STORED = 426.766   # round 5's stored column (the cross-session fallback)
DRIFT_RULE_PCT = 1.0
REUSE = ("REUSE round-18's pair (round 13 same-session %.3f ms) as the rag4096 comparator" % R13)


def median_ttft(path):
    """`tl_prefill_client.py` writes {"ttft_ms": {"n","median","runs",...}}; TTFT is the raced quantity."""
    d = json.loads(open(path, errors="replace").read())
    blk = d.get("ttft_ms") or {}
    v = blk.get("median")
    if v is None and isinstance(blk.get("runs"), list) and blk["runs"]:
        v = statistics.median([float(x) for x in blk["runs"]])
    if v is None:
        raise ValueError("no ttft_ms median and no runs list")
    return float(v)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    if not path or not os.path.exists(path):
        print("%s: NO fresh rag4096 re-serve JSON at %s" % (REUSE, path or "<unset>"))
        return 0
    try:
        v = median_ttft(path)
    except Exception as e:
        # Fail LOUDLY and fall back, never silently: chain14's inline parser printed "could not parse a
        # median" for all three cells because its key list did not match the real schema, so a sound
        # re-serve looked like a missing one. The class name is included so a schema change is
        # distinguishable from an absent file.
        print("%s: the fresh JSON at %s is UNREADABLE (%s: %s)" % (REUSE, path, type(e).__name__, e))
        return 0
    d13 = 100.0 * (v - R13) / R13
    d14 = 100.0 * (v - R14) / R14
    ds = 100.0 * (v - STORED) / STORED
    tail = ("fresh re-serve %.3f ms | vs round13 %.3f = %+.3f%% | vs round14 %.3f = %+.3f%%"
            " | vs round5 stored %.3f = %+.3f%%" % (v, R13, d13, R14, d14, STORED, ds))
    if abs(d13) <= DRIFT_RULE_PCT:
        # DO NOT OVER-CLAIM WHAT A FRESH COMPARATOR BUYS. Round 19 measured one, and the first cut of
        # this line said it "RETIRES round 18's cross-session rag caveat". It does not, and the
        # distinction is the whole point of the same-session rule: a ratio is same-session only if BOTH
        # sides ran in that session. Round 19 ran no rag4096 cells of ours -- its budget went to pp1024
        # and pp256 -- so the rag row still pairs round 18's 366.216 ms (measured 2026-09-19 ~20:00Z)
        # with a comparator from a later session. What the fresh serve DOES establish is that the
        # comparator is STABLE across sessions to within the 1% reproduction rule, which is evidence
        # about the server, not a licence to relabel the pair. Retiring the caveat properly costs one
        # rag4096 bracket in a window that also re-serves, and until then the row stays cross-session.
        print("FRESH SAME-SESSION rag4096 TRT = %.3f ms, and it REPRODUCES round 18's comparator basis"
              " within the %.1f%% rule (%s). NOTE: this validates the COMPARATOR's stability across"
              " sessions; it does NOT make round 18's rag row same-session, because that row's OWN"
              " cells (366.216 ms) were measured in round 18's window. The rag row stays"
              " CROSS-SESSION until a window brackets rag4096 and re-serves in the same session."
              % (v, DRIFT_RULE_PCT, tail))
    else:
        print("%s: the single confirmation serve %s, which EXCEEDS the %.1f%% drift rule, so the fresh"
              " number is not comparable with round 18's bracket and must not be mixed into its ratio"
              % (REUSE, tail, DRIFT_RULE_PCT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
