"""Algenta Governed Agent — Real LLM.

A live open-weights LLM (Qwen3-4B-Instruct-2507, streamed from HF Inference
Providers — disclosed everywhere) calling REAL kernel-backed tools through
REAL Algenta governance running locally in this Space — zero mocks, zero
scripts, zero canned output:

- search_corpus  — BM25 over real Wikipedia lead-extract passages, bm25_mojo kernel
- score_answer   — BLEU + chrF, sacrebleu_mojo kernel (oracle cross-check live)
- simulate       — M/M/1 discrete-event simulation, signed algenta-runtime-native
- recommend      — governed recommendation + policy-gate preview (real wire shapes)
- execute_action — the three named policy gates + HMAC-signed receipt/denial

The user picks the governance profile; the profile decides which tools are even
model-facing. Every model call streams token-by-token into the chat and is
measured live (TTFT, tok/s, token counts); every tool call is measured live;
every outcome lands in the session audit log.
"""

from __future__ import annotations

import json
import threading
import time

import corpus
import gradio as gr
import space_core as core
from design import CSS, FORCE_DARK_JS, THEME
from shell import SHELL_CSS, render_footer, render_header

KERNELS_REPO = "https://github.com/thyn-ai/mojo-kernels"
WHEELS_RELEASE = f"{KERNELS_REPO}/releases/tag/arena-wheels-v0.1.0"
SDK_REPO = "https://github.com/thyn-ai/algenta-sdk"
SPEED_ARENA = "https://huggingface.co/spaces/thyn-ai/algenta-speed-arena"
AGENTS_SPACE = "https://huggingface.co/spaces/thyn-ai/algenta-for-llm-agents"
MODULES_SPACE = "https://huggingface.co/spaces/thyn-ai/algenta-llm-modules"
GOVERNED_SPACE = "https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls"

# Canonical Algenta dark-glass theme (THEME + payload CSS) lives in design.py; the
# page chrome (header/footer) is the canonical fleet shell from shell.py.

# ---------------------------------------------------------------------------
# Status pill + boot card + badges (our own HTML payloads; styled in design.py)
# ---------------------------------------------------------------------------


def _pill_html(kind: str, text: str) -> str:
    return f"<span class='pill pill-{kind}'><span class='pill-dot'></span>{text}</span>"


def _pill_for_boot(bs: dict) -> str:
    if bs["ready"]:
        probe = bs.get("probe") or {}
        ttft = probe.get("ttft_seconds")
        suffix = f" · probe TTFT {ttft}s" if ttft is not None else ""
        return _pill_html("ready", f"ready · inference via HF Inference Providers{suffix}")
    if bs["error"]:
        return _pill_html("error", f"boot failed — {bs['error']}")
    running = next((s for s in bs["stages"] if s["state"] == "running"), None)
    label = running["label"] if running else "starting…"
    return _pill_html("loading", label)


def _pill_busy() -> str:
    return _pill_html("busy", "generating — streamed live")


def _boot_card_html(bs: dict) -> str:
    stages = bs["stages"]
    done = sum(1 for s in stages if s["state"] == "done")
    pct = 100 if bs["ready"] else int(100 * done / max(1, len(stages)))
    icons = {"done": "✓", "running": "…", "pending": "○", "error": "✗"}
    rows = []
    for s in stages:
        detail = f"<span class='boot-detail'>{s['detail']}</span>" if s["detail"] else ""
        rows.append(
            f"<div class='boot-step boot-{s['state']}'>"
            f"<span class='boot-icon'>{icons[s['state']]}</span>{s['label']}{detail}</div>"
        )
    error = (
        f"<div class='boot-step boot-error'><span class='boot-icon'>✗</span>"
        f"boot error — {bs['error']}. Nothing is faked: fix the secret/quota and retry.</div>"
        if bs["error"]
        else ""
    )
    return (
        "<div class='boot-card'>"
        "<div class='boot-title'>boot sequence — real work, no splash screen</div>"
        f"<div class='boot-bar'><div class='boot-fill' style='width:{pct}%'></div></div>"
        + "".join(rows)
        + error
        + "</div>"
    )


def _status_badges() -> str:
    rep = core.backend_report()
    bs = core.boot_status()
    badges = [f'<span class="badge">{core.MODEL_LABEL}</span>']
    badges.append(
        '<span class="badge">governance · kernels · receipts run locally in this Space</span>'
    )
    if bs["ready"]:
        probe = bs.get("probe") or {}
        ttft = probe.get("ttft_seconds")
        badges.append(
            f'<span class="badge badge-ok">inference ready — real boot probe TTFT {ttft}s</span>'
            if ttft is not None
            else '<span class="badge badge-ok">inference ready</span>'
        )
    elif bs["error"]:
        badges.append(
            f'<span class="badge badge-bad">inference UNAVAILABLE: {bs["error"]} — turns hold, never fake</span>'
        )
    else:
        badges.append('<span class="badge badge-warn">inference: booting…</span>')
    b = rep.get("bm25_mojo", {})
    badges.append(
        '<span class="badge badge-ok">bm25_mojo: native Mojo kernel</span>'
        if b.get("native_available")
        else '<span class="badge badge-warn">bm25_mojo: pure-Python fallback on this host (labeled)</span>'
    )
    idx = corpus.index_stats()
    if idx:
        badges.append(
            f'<span class="badge badge-ok">indexed {idx["docs"]} real Wikipedia passages in {idx["build_ms"]} ms on bm25_mojo</span>'
        )
    else:
        badges.append('<span class="badge badge-warn">corpus index: building…</span>')
    s = rep.get("sacrebleu_mojo", {})
    badges.append(
        '<span class="badge badge-ok">sacrebleu_mojo: native Mojo kernel</span>'
        if s.get("native_available")
        else '<span class="badge badge-warn">sacrebleu_mojo: pure-Python fallback on this host (bit-exact, labeled)</span>'
    )
    r = rep.get("algenta_runtime", {})
    badges.append(
        '<span class="badge badge-ok">simulate: signed algenta-runtime-native (Mojo)</span>'
        if r.get("available")
        else f'<span class="badge badge-bad">simulate UNAVAILABLE: {r.get("error", "unknown")} (no fake substituted)</span>'
    )
    import os as _os

    if _os.environ.get("SPACE_ID") or _os.environ.get("HF_SPACE_ID"):
        badges.append(
            '<span class="badge">hardware: HF cpu-basic — governance local; LLM streamed from providers</span>'
        )
    else:
        badges.append(
            '<span class="badge">hardware: local run — see the footer of any run for the machine</span>'
        )
    return "\n" + "\n".join(badges)


HEADER_HTML = render_header(
    title="Algenta Governed Agent — Real LLM",
    tagline="Live open-weights LLM, real kernels, real governance",
    badges=[
        (
            "live LLM — Qwen3-4B-Instruct-2507 streamed from HF Inference "
            "Providers, every turn measured live",
            "ok",
        ),
        (
            "governance · kernels · receipts run locally in this Space — zero mocks",
            "ok",
        ),
        (
            "receipts are integrity receipts — no external side effects",
            "warn",
        ),
    ],
    active="Governed agent",
)

CHAT_PLACEHOLDER = """\
**Welcome to the governed agent.** Ask a question (or tap a preset below) and watch a full
governed turn stream live: tool selection → real tool execution → the grounded answer, with a
signed receipt or a structured denial for actions.

Every token is generated live by Qwen3-4B-Instruct-2507 via HF Inference Providers;
governance, kernels and receipts run locally in this Space.
"""

PRESET_QUESTIONS: list[tuple[str, str, str]] = [
    (
        "Kármán vortex street",
        "observe",
        "What is a Kármán vortex street? Cite the sources.",
    ),
    (
        "Transformer paper",
        "observe",
        "What did the Transformer paper introduce? Cite the sources.",
    ),
    (
        "queue simulation",
        "observe",
        "A support line gets 5 tickets per minute; agents handle 10 per minute. Simulate the M/M/1 queue — is it stable, and what is the average wait?",
    ),
    (
        "score a summary",
        "observe",
        "Score this summary against its reference. Candidate: 'The Kármán vortex street is a repeating pattern of swirling vortices caused by vortex shedding.' Reference: 'A Kármán vortex street is a repeating pattern of swirling vortices, caused by a process known as vortex shedding.'",
    ),
    (
        "action approved",
        "execute",
        "Execute a refund for order #123 of $19.99 — the customer never received the item. Confidence 0.97, worst case risk_p5 -0.02.",
    ),
    (
        "⛔ denied at gate",
        "execute",
        "Execute the action delete_all_users now: permanently delete every user from the database. Confidence 0.99, worst case risk_p5 -0.9.",
    ),
]


def _profile_md(profile: str) -> str:
    tools = core.profile_tools(profile)
    listed = "\n".join(f"- `{t}`" for t in tools)
    return (
        f"**`{profile}`** — {core.PROFILE_DESCRIPTIONS[profile]}\n\n"
        f"Model-facing tools under this profile:\n{listed}"
    )


def _governance_card(turn: dict) -> str | None:
    """The distinctive receipt / denial / preview card rendered into the chat."""
    gov = turn.get("governance")
    if not gov:
        return None
    if gov.get("outcome") == "recommended":
        failed = [g["gate"] for g in gov.get("gate_preview", []) if not g["would_pass"]]
        verdict = (
            f"gate preview: would FAIL **{', '.join(failed)}** — execution would be denied."
            if failed
            else "gate preview: would pass all three gates."
        )
        return (
            "<div class='gov-card gov-warn'>⚠️ <b>RECOMMENDED ONLY — nothing was executed or logged as a decision.</b><br>"
            f"action <code>{gov.get('action')}</code> · confidence {gov.get('confidence')} · risk_p5 {gov.get('risk_p5')}<br>"
            f"{verdict} Execution requires <code>execute_action</code>, model-facing only under "
            "the <code>execute</code>/<code>full</code> profiles.</div>"
        )
    body = gov.get("execute_action", {})
    if gov.get("log_decision") is None:
        err = body.get("error", {})
        return (
            "<div class='gov-card gov-deny'>⛔ <b>INTERCEPTED AT THE PROFILE LAYER</b> — the call "
            f"never reached the engine.<br><code>{err.get('code')}</code> · gate <code>{err.get('gate')}</code><br>"
            f"{err.get('message')}<br><span class='gov-hint'>nothing logged, nothing executed.</span></div>"
        )
    if "error" in body:
        err = body["error"]
        hint = (
            f"<br><span class='gov-hint'>override path: {err['override_hint']}</span>"
            if err.get("override_hint")
            else ""
        )
        return (
            f"<div class='gov-card gov-deny'>⛔ <b>DENIED AT POLICY GATE <code>{err['gate']}</code></b> "
            f"— no execution happened.<br><code>{err['code']}</code><br>{err['message']}{hint}<br>"
            "<span class='gov-hint'>the decision was logged first; the denial is in the audit tab.</span></div>"
        )
    return (
        "<div class='gov-card gov-ok'>✅ <b>APPROVED — ALL THREE POLICY GATES PASSED</b><br>"
        f"decision <code>{body.get('decision_id')}</code> · execution_status <code>{body.get('execution_status')}</code> · "
        f"response {body.get('response_code')}<br>HMAC-SHA256 signed receipt (scheme: {body.get('signature_scheme')}) — "
        "verify it yourself in the <b>Audit log</b> tab with the session key.</div>"
    )


def _composition_record(turn: dict) -> dict | None:
    for step in reversed(turn.get("steps", [])):
        if step.get("kind") == "model_call" and "composition" in str(step.get("step", "")):
            return step
    return None


def _run_turn_stream(question, profile, force, override_safety, state, history):
    """UI handler: one governed turn, STREAMED. Never raises.

    Consumes core.agent_turn_events and re-renders the chat, trace and raw
    panels on every real event (token deltas included), coalesced to ~12fps
    between step boundaries. The API keeps the original output order
    (trace, tool_call, tool_result, answer, governance, audit, key, state,
    badges) with status_pill and chatbot appended.
    """
    state = core._ensure_state(state)
    msgs = list(history or [])
    q = (question or "").strip()

    def frame(trace_md, tc, tr, ans, gov, pill, messages):
        return (
            trace_md,
            tc,
            tr,
            ans,
            gov,
            json.dumps(state["audit"], indent=2),
            state["hmac_key"],
            state,
            _status_badges(),
            pill,
            messages,
        )

    # Defense in depth (the composer also disables Run on blank input): an
    # empty/whitespace question gets a gentle nudge — NEVER a governed-turn
    # card, NEVER a model call, nothing in the audit log.
    if not q:
        msgs.append(
            gr.ChatMessage(
                role="assistant",
                content="Ask a question or tap a preset below — empty turns never call the model.",
            )
        )
        yield frame("", "", "", "", "", _pill_for_boot(core.boot_status()), msgs)
        return

    msgs.append(gr.ChatMessage(role="user", content=q))
    trace_msg = gr.ChatMessage(
        role="assistant",
        content="_starting the governed turn…_",
        metadata={"title": f"🛠 governed turn — profile `{profile}`"},
    )
    msgs.append(trace_msg)

    live_turn: dict = {"question": q, "profile": profile, "steps": [], "held": False}
    streamed_answer = ""
    answer_msg: gr.ChatMessage | None = None
    turn: dict | None = None
    last_yield = 0.0

    yield frame(core.render_trace(live_turn), "", "", "", "", _pill_busy(), msgs)

    for event in core.agent_turn_events(q, profile, bool(force), bool(override_safety), state):
        etype = event["type"]
        if etype == "step_start":
            if "composition" in event["step"]:
                answer_msg = gr.ChatMessage(role="assistant", content="_composing…_")
                msgs.append(answer_msg)
            trace_msg.content = core.render_trace(live_turn) + f"\n\n*{event['step']} — running…*"
        elif etype == "token":
            if "composition" in event["step"] and answer_msg is not None:
                streamed_answer += event["text"]
                answer_msg.content = streamed_answer
        elif etype in ("step_end", "tool_end"):
            live_turn["steps"].append(event["record"])
            trace_msg.content = core.render_trace(live_turn)
        elif etype == "done":
            turn = event["turn"]
            break
        now = time.perf_counter()
        if now - last_yield >= 0.08:
            last_yield = now
            yield frame(
                trace_msg.content,
                "",
                "",
                streamed_answer,
                "",
                _pill_busy(),
                msgs,
            )

    assert turn is not None
    trace_md = (
        core.render_trace(turn) + f"\n\n<span class='muted small'>{core.hardware_footer()}</span>"
    )
    trace_msg.content = trace_md
    tool_call = json.dumps(turn.get("tool_call"), indent=2) if turn.get("tool_call") else ""
    tool_result = json.dumps(turn.get("tool_result"), indent=2) if turn.get("tool_result") else ""
    governance = json.dumps(turn.get("governance"), indent=2) if turn.get("governance") else ""

    if turn.get("answer"):
        if answer_msg is None:
            answer_msg = gr.ChatMessage(role="assistant", content=turn["answer"])
            msgs.append(answer_msg)
        else:
            answer_msg.content = turn["answer"]
        rec = _composition_record(turn)
        if rec:
            ttft = rec.get("ttft_seconds")
            meta_bits = []
            if rec.get("completion_tokens"):
                meta_bits.append(f"{rec['completion_tokens']} tok")
            if ttft is not None:
                meta_bits.append(f"TTFT {ttft}s")
            if rec.get("tok_per_s"):
                meta_bits.append(f"{rec['tok_per_s']} tok/s")
            if meta_bits:
                title_verb = (
                    "abstained — engine refuses to fabricate inputs"
                    if turn.get("abstained")
                    else "answer — streamed live"
                )
                answer_msg.metadata = {"title": title_verb + " · " + " · ".join(meta_bits)}
    elif turn.get("held"):
        msgs.append(
            gr.ChatMessage(
                role="assistant",
                content=f"*(turn held — no answer composed; the real reason is in the trace: {turn.get('error')})*",
            )
        )

    card = _governance_card(turn)
    if card:
        msgs.append(
            gr.ChatMessage(
                role="assistant", content=card, metadata={"title": "governance decision"}
            )
        )

    answer_text = turn.get("answer") or (
        "*(held — no answer composed)*" if turn.get("held") else ""
    )
    bs = core.boot_status()
    yield frame(trace_md, tool_call, tool_result, answer_text, governance, _pill_for_boot(bs), msgs)


HOW_IT_WORKS_MD = f"""\
## How it works — the real architecture, no invented numbers

### The loop (every step is real, streamed, and shown)

```
your question + governance profile
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 1 · TOOL SELECTION — Qwen3-4B-Instruct-2507                 │
│    streamed from HF Inference Providers (org-billed)        │
│    system prompt carries the profile-filtered tool schemas  │
│    output in JSON mode → parse + validate against each      │
│    tool's JSON schema → on failure: ONE retry with the      │
│    error fed back (both attempts shown)                     │
└─────────────────────────────────────────────────────────────┘
        │ tool call (or final_answer)
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 2 · REAL TOOL EXECUTION — local in this Space (measured,    │
│    backend labeled)                                         │
│    search_corpus  → bm25_mojo.BM25Okapi.get_scores          │
│    score_answer   → sacrebleu_mojo corpus_bleu / corpus_chrf│
│    simulate       → algenta runtime simulation.mm1_simulate │
│    recommend      → policy-gate preview (wire shapes)       │
│    execute_action → profile interception → 3 policy gates   │
│                     → HMAC-signed receipt OR structured     │
│                     denial naming the gate                  │
└─────────────────────────────────────────────────────────────┘
        │ real tool result JSON
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 3 · ANSWER COMPOSITION — the same model writes the final    │
│    answer grounded on the tool result (citations), streamed │
│    token-by-token into the chat.                            │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
  session audit log (tab 3) — every recommend/execute outcome,
  with the signature key to verify receipts yourself
```

### Components — versions and pins (static facts, verifiable)

| component | what it is | pin |
|---|---|---|
| live language model | {core.PROVIDER_MODEL}, open weights (Apache-2.0), ungated | served via HF Inference Providers — provider `{core.PROVIDER_NAME}`, billed to org `{core.PROVIDER_BILL_TO}` |
| inference call | streamed chat completions, greedy (temperature 0), `stream_options.include_usage` | TTFT + decode tok/s + token counts measured live per call, shown in the trace |
| local reproduction | Qwen2.5-1.5B-Instruct GGUF Q4_K_M via llama.cpp (tab 4) | `{core.GGUF_REPO}` revision `{core.GGUF_REVISION[:12]}…`, sha256 `{core.GGUF_SHA256[:16]}…` |
| retrieval kernel | bm25_mojo 0.1.2 (BM25Okapi), GitHub release `arena-wheels-v0.1.0` | native Mojo where loadable, else labeled pure-Python fallback |
| scoring kernel | sacrebleu_mojo 0.1.2, same release; oracle cross-check vs sacrebleu 2.5.1 on every call | same fallback rule |
| simulation runtime | algenta 1.0.17 + algenta-runtime-native 1.0.5 (signed, verified before first execution) | CPython 3.14 only — why this Space's image is python:3.14-slim |
| governance | profile gates + policy gates, deterministic local code replicating the engine's documented wire shapes | min_confidence {core.MIN_CONFIDENCE}, risk_floor {core.RISK_FLOOR} |
| receipt integrity | HMAC-SHA256 over canonical JSON, ephemeral per-session key (shown in tab 3) | verifiable in-session; not a long-term identity key |

### Governance semantics (the real contract)

- **Profiles** — `observe` exposes search/scoring/simulation/recommend; `govern` adds decision
  logging semantics; `execute` / `full` additionally expose `execute_action` to the model.
  The model literally never sees tools outside its profile: the system prompt's tool list is
  rebuilt per request, and a hallucinated call to a non-exposed tool is intercepted anyway.
- **Argument-grounding guardrail** — after the model picks a tool, the engine validates that
  every numeric argument is grounded in the user's message (after `10k`→10000, `$15k`→15000,
  `5%`→5 or 0.05 normalization) or equal to a documented schema default disclosed as defaulted.
  Un-grounded numbers are rejected with feedback naming the offending values; one retry; still
  un-grounded → the turn **abstains** with an honest decline (a real streamed generation) —
  never a fabricated run, never a held card. The engine refuses to fabricate inputs: a
  fabricated tool call is a failure, an honest decline is not.
- **Honest abstention is first-class** — the selection prompt carries the exact tool/scenario
  catalog (`simulate` = M/M/1 queue with arrival/service-rate semantics ONLY) and instructs the
  model to answer via `final_answer` — saying what it can't run, what it can do, and which
  inputs are missing — whenever nothing genuinely fits.
- **Policy gates** — `execute_action` logs the decision, then runs three named synchronous
  gates in order: **idempotency** (no double delivery), **confidence** (≥ {core.MIN_CONFIDENCE}),
  **risk_floor** (risk_p5 ≥ −{core.RISK_FLOOR}). First failing gate wins; the denial body names
  it. All gates pass → a receipt is returned synchronously.
- **Operator-only fields** — `force` / `override_safety` exist for operators only; they are
  stripped from the model-facing schema and arrive only from the UI checkboxes.
- **Receipts** — carry the policy/schema snapshot ids, manifest version, and an HMAC-SHA256
  signature under a per-session ephemeral key (tab 3 shows the key + a 4-line verifier).

### Honesty labels — what runs where, and why

- **Demo inference runs on HF Inference Providers** (serverless, provider `{core.PROVIDER_NAME}`,
  billed to org `{core.PROVIDER_BILL_TO}`) — the model genuinely generates every token, streamed;
  this Space previously ran a 1.5B GGUF on cpu-basic and a single turn measured **232 s warm**
  (0.57–2.78 tok/s). After the move, the same class of turn measured live on the deployed
  Space (2026-09-21, client-side): **first visible token ≈0.8–1.1 s, full turn 2.2–4.7 s**.
  Governance, kernels, gates and receipts are unaffected: they run locally in this Space on
  every turn.
- **Greedy decoding is requested** (temperature 0). Providers do not expose a seed or the
  served weights' bytes, so byte-exact reproduction is the local GGUF path in tab 4 — the
  governance story (tools, gates, receipts) is deterministic local code on both paths.
- **Kernel backends are labeled per call.** If a Mojo wheel cannot load its native library on
  the host, the pure-Python fallback inside the same pinned package answers and the UI says so
  (on this Space's linux/x86_64 image the native kernels load; the badge row at the top shows
  the live status).
- **The corpus is REAL.** {corpus.provenance()} License: {corpus.license_line()}. The BM25
  index is rebuilt live at every boot on `bm25_mojo`; the measured index-build time is in the
  badge row.
- **Numbers in the trace are measured live** — TTFT, decode tok/s and token counts come from
  the provider's stream and usage chunk; tool latencies are timed here. Nothing is copied
  from a README.
- **Receipts are integrity receipts**, not delivery proof: `execute_action` performs no
  external side effect (no real refund, no real deletion). The governance decision — gates,
  denial, signature, audit — is the real artifact being demonstrated.
"""


def _run_it_yourself_md() -> str:
    return f"""\
## Run it yourself — every component is public

### The live model path (what this Space runs)

```bash
pip install "huggingface_hub>=1.30"
export HF_TOKEN=...   # a token with Inference Providers access
```

```python
from huggingface_hub import InferenceClient

client = InferenceClient(provider="{core.PROVIDER_NAME}", bill_to="{core.PROVIDER_BILL_TO}")
stream = client.chat.completions.create(
    model="{core.PROVIDER_MODEL}",
    messages=[{{"role": "user", "content": "Say hello in one sentence."}}],
    max_tokens=64, temperature=0.0, stream=True,
    stream_options={{"include_usage": True}},
)
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

Model card: [{core.PROVIDER_MODEL}]({core.MODEL_CARD}) · license: Apache-2.0, open weights.

### The local model path (byte-exact reproduction, no network)

The loop also runs fully offline on a pinned GGUF — the same weights this Space used to serve
before provider inference, pinned by revision and SHA-256:

```bash
pip install llama-cpp-python==0.3.35 "huggingface_hub>=1.30"
```

```python
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

path = hf_hub_download(
    "{core.GGUF_REPO}", "{core.GGUF_FILE}",
    revision="{core.GGUF_REVISION}",   # immutable pin
)
llm = Llama(model_path=path, n_ctx={core.N_CTX}, seed={core.GEN_SEED}, verbose=False)
out = llm.create_chat_completion(
    messages=[{{"role": "user", "content": "Say hello in one sentence."}}],
    temperature=0.0, seed={core.GEN_SEED},
)
print(out["choices"][0]["message"]["content"])
```

Model card: [Qwen/Qwen2.5-1.5B-Instruct]({core.GGUF_CARD}) · GGUF build:
[Qwen/Qwen2.5-1.5B-Instruct-GGUF](https://huggingface.co/{core.GGUF_REPO}) · license: Qwen (see repo).

### The kernels (Mojo, manylinux x86_64)

```bash
pip install \\
  https://github.com/thyn-ai/mojo-kernels/releases/download/arena-wheels-v0.1.0/bm25_mojo-0.1.2-py3-none-manylinux_2_35_x86_64.whl \\
  https://github.com/thyn-ai/mojo-kernels/releases/download/arena-wheels-v0.1.0/sacrebleu_mojo-0.1.2-py3-none-manylinux_2_35_x86_64.whl
```

```python
import bm25_mojo, sacrebleu_mojo
bm25 = bm25_mojo.BM25Okapi([["hello", "world"], ["hello", "mojo"]])
print(bm25.get_scores(["hello"]))          # native kernel where loadable
print(bm25_mojo.backend_info())            # says which backend answered
print(sacrebleu_mojo.corpus_bleu(["a b c"], [["a b c"]]).score)
```

Release: [{WHEELS_RELEASE}]({WHEELS_RELEASE}) · repo: [{KERNELS_REPO}]({KERNELS_REPO})

### The simulation runtime (signed, CPython 3.14)

```bash
pip install algenta==1.0.17 algenta-runtime-native==1.0.5   # CPython 3.14, linux x86_64 / macOS arm64
```

```python
from algenta import MojoRuntime
rt = MojoRuntime(mode="local")
print(rt.execute("simulation", "mm1_simulate", [0.9, 1.0, 5000])["result"])
```

### The governance layer (production path)

```bash
pip install algenta-sdk algenta-mcp    # SDK + MCP server (MCP Registry: io.github.thyn-ai/algenta)
```

- SDK: [{SDK_REPO}]({SDK_REPO}) · PyPI: [algenta-sdk](https://pypi.org/project/algenta-sdk/), [algenta-mcp](https://pypi.org/project/algenta-mcp/)
- Hosted engine: `https://api.algenta.ai` — the profile gates and receipt wire shapes this Space
  demonstrates are the ones `algenta-mcp` and the hosted API return.

### Sister Spaces

[Speed Arena]({SPEED_ARENA}) · [Algenta for LLM Agents]({AGENTS_SPACE}) ·
[LLM Modules Live]({MODULES_SPACE}) · [Governed tool calls]({GOVERNED_SPACE})
"""


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Algenta Governed Agent — Real LLM", fill_width=True) as demo:
        gr.HTML(HEADER_HTML)
        with gr.Row():
            status_pill = gr.HTML(_pill_html("loading", "starting…"))
        boot_card = gr.HTML(_boot_card_html(core.boot_status()))
        retry_boot_btn = gr.Button("Retry boot", size="sm", visible=False)
        status_badges = gr.Markdown(_status_badges())
        state = gr.State(core.initial_state)

        with gr.Tabs():
            # ============================== Tab 1 · agent chat ==============
            with gr.Tab("Agent chat"):
                with gr.Row():
                    with gr.Column(scale=3):
                        chatbot = gr.Chatbot(
                            label="governed turns — streamed live",
                            layout="bubble",
                            height=560,
                            placeholder=CHAT_PLACEHOLDER,
                            group_consecutive_messages=False,
                            buttons=["copy"],
                        )
                        with gr.Row():
                            question = gr.Textbox(
                                placeholder="Ask the governed agent… (Enter to send)",
                                show_label=False,
                                lines=2,
                                scale=5,
                            )
                            run = gr.Button(
                                "loading model…",
                                variant="primary",
                                size="lg",
                                interactive=False,
                                scale=1,
                            )
                        gr.Markdown(
                            "<span class='muted small'>presets — click to load and run:</span>"
                        )
                        preset_btns = []
                        for row_start in (0, 3):
                            with gr.Row():
                                for label, _, _ in PRESET_QUESTIONS[row_start : row_start + 3]:
                                    preset_btns.append(
                                        gr.Button(label, size="sm", interactive=False)
                                    )
                    with gr.Column(scale=2):
                        profile = gr.Radio(
                            choices=["observe", "govern", "execute", "full"],
                            value="observe",
                            label="governance profile — decides which tools are even model-facing",
                        )
                        profile_md = gr.Markdown(_profile_md("observe"))
                        with gr.Row():
                            force = gr.Checkbox(value=False, label="force (operator only)")
                            override_safety = gr.Checkbox(
                                value=False, label="override_safety (operator only)"
                            )
                        gr.Markdown(
                            "<span class='muted small'>`force` / `override_safety` are stripped "
                            "from the model-facing schema — the model can never set them; they "
                            "arrive only from these operator controls.</span>"
                        )
                        with gr.Accordion(
                            "raw turn outputs — trace · tool call · result · receipt/denial",
                            open=False,
                        ):
                            trace = gr.Markdown(label="turn trace", elem_classes=["panel"])
                            answer = gr.Markdown(label="final answer", elem_classes=["panel"])
                            tool_call = gr.Code(
                                label="model's tool call (raw, parsed)", language="json"
                            )
                            tool_result = gr.Code(label="real tool result", language="json")
                            governance = gr.Code(
                                label="governance envelope — receipt or structured denial",
                                language="json",
                            )

                profile.change(_profile_md, profile, profile_md)

            # ========================== Tab 2 · how it works ================
            with gr.Tab("How it works"):
                gr.Markdown(HOW_IT_WORKS_MD)
                gr.Markdown(f"<footer class='muted small'>{core.hardware_footer()}</footer>")

            # ============================ Tab 3 · audit log =================
            with gr.Tab("Audit log"):
                gr.Markdown(
                    "Every `recommend` / `execute_action` outcome of **this session** — append-only. "
                    "Receipts are HMAC-SHA256 signed under the per-session ephemeral key below; "
                    "verify any receipt yourself:"
                )
                session_key = gr.Code(
                    label="session signature key (ephemeral, per session)", language="python"
                )
                gr.Code(
                    value=core.verify_snippet(),
                    language="python",
                    label="verify a receipt (4 lines)",
                )
                audit_json = gr.Code(label="audit entries", language="json", value="[]")

            # ========================= Tab 4 · run it yourself ==============
            with gr.Tab("Run it yourself"):
                gr.Markdown(_run_it_yourself_md())

        # Wiring that spans tabs is registered after every component exists.
        run_turn_inputs = [question, profile, force, override_safety, state, chatbot]
        run_turn_outputs = [
            trace,
            tool_call,
            tool_result,
            answer,
            governance,
            audit_json,
            session_key,
            state,
            status_badges,
            status_pill,
            chatbot,
        ]
        run.click(
            _run_turn_stream,
            run_turn_inputs,
            run_turn_outputs,
            api_name="agent_turn",
            show_progress="minimal",
        ).then(lambda: "", None, question)
        question.submit(
            _run_turn_stream,
            run_turn_inputs,
            run_turn_outputs,
            show_progress="minimal",
        ).then(lambda: "", None, question)
        for btn, (label, prof, q) in zip(preset_btns, PRESET_QUESTIONS, strict=False):
            btn.click(
                lambda p=prof, qq=q: (qq, p),
                None,
                [question, profile],
            ).then(
                _run_turn_stream,
                run_turn_inputs,
                run_turn_outputs,
                show_progress="minimal",
            ).then(lambda: "", None, question)

        # ---- boot sequence: poll real boot status until ready -------------
        def _run_gate(question_text):
            """Run is clickable only when boot is ready AND the composer has
            non-blank text — empty/whitespace questions can never be sent."""
            ready = core.boot_status()["ready"]
            has_text = bool((question_text or "").strip())
            if not ready:
                return gr.update(value="loading model…", interactive=False)
            return gr.update(value="Run governed turn", interactive=has_text)

        def _poll_boot(question_text=""):
            bs = core.boot_status()
            ready = bool(bs["ready"])
            error = bs["error"]
            card = "" if ready else _boot_card_html(bs)
            pill = _pill_for_boot(bs)
            run_update = _run_gate(question_text)
            preset_updates = [gr.update(interactive=ready) for _ in PRESET_QUESTIONS]
            return (
                card,
                pill,
                _status_badges(),
                run_update,
                gr.update(visible=bool(error) and not ready),
                *preset_updates,
                gr.Timer(active=not ready),
            )

        question.change(_run_gate, question, run)

        def _retry_boot():
            core.boot_retry()
            return gr.Timer(active=True)

        timer = gr.Timer(0.75, active=True)
        timer.tick(
            _poll_boot,
            question,
            [boot_card, status_pill, status_badges, run, retry_boot_btn, *preset_btns, timer],
        )
        retry_boot_btn.click(_retry_boot, None, timer)

        def _on_load(s):
            s = core._ensure_state(s)
            bs = core.boot_status()
            return (
                json.dumps(s["audit"], indent=2),
                s["hmac_key"],
                _status_badges(),
                _boot_card_html(bs),
                _pill_for_boot(bs),
            )

        demo.load(_on_load, state, [audit_json, session_key, status_badges, boot_card, status_pill])

        gr.HTML(render_footer())

    return demo


# Boot the kernels and the inference probe in the background so the first
# click isn't cold; the UI polls boot_status() and gates the Run button on it.
threading.Thread(target=core.boot, daemon=True).start()

demo = build_app()

if __name__ == "__main__":
    import os

    demo.queue(default_concurrency_limit=4).launch(
        server_name=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
        show_error=True,
        theme=THEME,
        css=CSS + "\n" + SHELL_CSS,
        js=FORCE_DARK_JS,
    )
