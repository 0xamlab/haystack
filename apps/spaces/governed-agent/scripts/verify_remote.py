#!/usr/bin/env python3
"""Remote verification for the Algenta Governed Agent — Real LLM Space.

Runs EVERY curated preset through the live loop via gradio_client and asserts
its expected tool path (cited retrieval / real simulation / scoring / signed
receipt / risk_floor denial), plus the regression set (empty submit, "hi",
weather, the owner's revenue question) — each turn must compose, do the right
thing, and finish under 30s. Receipt signatures are verified against the
per-session key returned by the same call.

Keep PRESETS in sync with app.py's PRESET_QUESTIONS (they are the UI buttons).

    python scripts/verify_remote.py [space_url]
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time

from gradio_client import Client

URL = sys.argv[1] if len(sys.argv) > 1 else "https://thyn-ai-algenta-governed-agent.hf.space/"

FAILURES: list[str] = []
TURN_BUDGET_S = 30.0


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'OK' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        FAILURES.append(name)


def run(
    client: Client, label: str, question: str, profile: str, force=False, override=False, show=True
):
    t0 = time.perf_counter()
    job = client.submit(question, profile, force, override, [], api_name="/agent_turn")
    first_frame = None
    frames = 0
    while not job.done():
        if job.outputs():
            frames += 1
            if first_frame is None:
                first_frame = time.perf_counter() - t0
        time.sleep(0.1)
    total = time.perf_counter() - t0
    (
        trace,
        tool_call,
        tool_result,
        answer,
        governance,
        audit,
        session_key,
        badges,
        pill,
        chatbot,
    ) = job.result()
    if show:
        print("=" * 100)
        print(
            f"### {label} | profile={profile} | first-frame={first_frame and round(first_frame, 2)}s total={round(total, 2)}s frames={frames}"
        )
        print(trace[:1800])
        print("--- answer ---")
        print(answer[:400])
    return {
        "trace": trace,
        "tool_call": json.loads(tool_call) if tool_call else None,
        "tool_result": json.loads(tool_result) if tool_result else None,
        "answer": answer,
        "governance": json.loads(governance) if governance else None,
        "audit": json.loads(audit) if audit else None,
        "session_key": session_key,
        "badges": badges,
        "pill": pill,
        "chatbot": chatbot,
        "total_s": total,
        "frames": frames,
    }


# label, profile, question, expected tool, extra assertion name
PRESETS: list[tuple[str, str, str, str]] = [
    (
        "Kármán vortex street",
        "observe",
        "What is a Kármán vortex street? Cite the sources.",
        "search_corpus",
    ),
    (
        "Transformer paper",
        "observe",
        "What did the Transformer paper introduce? Cite the sources.",
        "search_corpus",
    ),
    (
        "queue simulation",
        "observe",
        "A support line gets 5 tickets per minute; agents handle 10 per minute. Simulate the M/M/1 queue — is it stable, and what is the average wait?",
        "simulate",
    ),
    (
        "score a summary",
        "observe",
        "Score this summary against its reference. Candidate: 'The Kármán vortex street is a repeating pattern of swirling vortices caused by vortex shedding.' Reference: 'A Kármán vortex street is a repeating pattern of swirling vortices, caused by a process known as vortex shedding.'",
        "score_answer",
    ),
    (
        "action approved",
        "execute",
        "Execute a refund for order #123 of $19.99 — the customer never received the item. Confidence 0.97, worst case risk_p5 -0.02.",
        "execute_action",
    ),
    (
        "⛔ denied at gate",
        "execute",
        "Execute the action delete_all_users now: permanently delete every user from the database. Confidence 0.99, worst case risk_p5 -0.9.",
        "execute_action",
    ),
]


def verify_presets(client: Client) -> None:
    for label, profile, question, expected_tool in PRESETS:
        r = run(client, f"PRESET: {label}", question, profile)
        check(f"[{label}] under 30s", r["total_s"] < TURN_BUDGET_S, f"{r['total_s']:.1f}s")
        check(f"[{label}] not held", "TURN HELD" not in r["trace"])
        check(
            f"[{label}] tool is {expected_tool}",
            r["tool_call"]["tool"] == expected_tool,
            f"got {r['tool_call']['tool']}",
        )
        check(f"[{label}] answer composes", bool(r["answer"].strip()))
        if expected_tool == "search_corpus":
            check(f"[{label}] real ranked passages", len(r["tool_result"]["results"]) >= 3)
            check(
                f"[{label}] passages carry titles+urls",
                all(
                    p["title"] and p["url"].startswith("https://en.wikipedia.org/")
                    for p in r["tool_result"]["results"]
                ),
            )
        if label == "queue simulation":
            args = r["tool_call"]["arguments"]
            check(
                "[queue] grounded rates 5/10",
                float(args["arrival_rate"]) == 5 and float(args["service_rate"]) == 10,
            )
            check("[queue] stable", r["tool_result"]["queue_stable"] is True)
        if label == "score a summary":
            check("[score] BLEU>0", r["tool_result"]["bleu"]["score"] > 0)
            check(
                "[score] oracle bit-exact",
                r["tool_result"]["oracle_crosscheck"]["abs_delta_bleu"] <= 1e-9
                and r["tool_result"]["oracle_crosscheck"]["abs_delta_chrf"] <= 1e-9,
            )
        if label == "action approved":
            receipt = r["governance"]["execute_action"]
            check("[approved] delivered", receipt.get("execution_status") == "delivered")
            body = {k: v for k, v in receipt.items() if k != "signature"}
            payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            expected = hmac.new(
                bytes.fromhex(r["session_key"]), payload, hashlib.sha256
            ).hexdigest()
            check("[approved] HMAC signature verifies", expected == receipt["signature"])
        if label == "⛔ denied at gate":
            err = r["governance"]["execute_action"]["error"]
            check("[denied] gate is risk_floor", err["gate"] == "risk_floor", f"gate={err['gate']}")
            check("[denied] structured code", err["code"] == "execution_blocked_risk_floor")
            check("[denied] audit recorded", any(e["outcome"] == "denied" for e in r["audit"]))


def verify_regression_set(client: Client) -> None:
    # empty submit → nudge, no card, no model call
    r = run(client, "REGRESSION: empty submit", "", "observe", show=False)
    check("[empty] no trace card", r["trace"] == "")
    check(
        "[empty] gentle nudge only",
        len(r["chatbot"]) == 1 and "preset" in str(r["chatbot"][0]["content"]),
    )

    # hi → conversational final_answer
    r = run(client, "REGRESSION: hi", "hi", "observe", show=False)
    check("[hi] under 30s", r["total_s"] < TURN_BUDGET_S, f"{r['total_s']:.1f}s")
    check("[hi] final_answer", r["tool_call"]["tool"] == "final_answer")
    check("[hi] composes", bool(r["answer"].strip()))

    # weather → out-of-scope final_answer, never held
    r = run(client, "REGRESSION: weather", "what is the weather today", "observe", show=False)
    check("[weather] not held", "TURN HELD" not in r["trace"])
    check("[weather] final_answer", r["tool_call"]["tool"] == "final_answer")
    check("[weather] composes", bool(r["answer"].strip()))

    # the owner's revenue question → abstain or decline, NEVER a fabricated run
    r = run(
        client,
        "REGRESSION: revenue question (fabrication guard)",
        "can you simulate revenue change if we cut cost by 10k per month, and increase "
        "sales by 5%? our current burn rate is 15k per month",
        "observe",
    )
    check("[revenue] under 30s", r["total_s"] < TURN_BUDGET_S, f"{r['total_s']:.1f}s")
    check("[revenue] not held", "TURN HELD" not in r["trace"])
    if r["tool_call"] and r["tool_call"]["tool"] != "final_answer":
        check("[revenue] NO fabricated simulate ran", r["tool_call"]["tool"] != "simulate")
    else:
        check("[revenue] declined honestly", True)
    check("[revenue] answer composes", bool(r["answer"].strip()))

    # grounded queue sanity (guardrail must not over-fire)
    r = run(
        client,
        "REGRESSION: grounded queue",
        "simulate a queue with arrival rate 5 and service rate 10",
        "observe",
        show=False,
    )
    check("[grounded queue] simulate ran", r["tool_call"]["tool"] == "simulate")
    check("[grounded queue] real result", r["tool_result"]["queue_stable"] is True)


def verify_badges_and_corpus(client: Client) -> None:
    r = run(
        client,
        "BADGES: retrieval for badge assertions",
        "What is photosynthesis? Cite the sources.",
        "observe",
        show=False,
    )
    check("native bm25 kernel badge", "bm25_mojo: native Mojo kernel" in r["badges"])
    check("provider inference disclosed", "HF Inference Providers" in r["badges"])
    check(
        "index badge with measured time",
        "indexed" in r["badges"] and "real Wikipedia passages in" in r["badges"],
    )
    check(
        "photosynthesis hits", any("hotosynth" in p["title"] for p in r["tool_result"]["results"])
    )


def main() -> int:
    client = Client(URL)
    verify_presets(client)
    verify_regression_set(client)
    verify_badges_and_corpus(client)
    print()
    if FAILURES:
        print("REMOTE VERIFICATION FAILED:", FAILURES)
        return 1
    print("REMOTE VERIFICATION: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
