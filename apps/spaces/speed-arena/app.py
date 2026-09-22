"""Algenta Speed Arena — real-time benchmark duels: Mojo kernels vs incumbents.

Every duel runs REAL native Mojo kernels (manylinux wheels from the
arena-wheels release of thyn-ai/mojo-kernels) against the incumbent library
at its best configuration, live on this Space's CPU. Correctness gate first
(R1), seeded corpora (R2), cold + warm labeled (R5), median-of-5 with spread
(R6), hardware disclosed (R4). Nothing is pre-computed: every run measures
fresh, in your session, on this machine.
"""

from __future__ import annotations

import os
import queue
import threading
import time

import gradio as gr
from arena import store
from arena.card import render_card, render_fallback, render_held, render_placeholder, share_text
from arena.duels import DUELS, DUELS_BY_ID
from arena.gallery import gallery_html
from arena.harness import hardware_footer, run_sweep
from design import CSS, FORCE_DARK_JS, THEME
from shell import SHELL_CSS, render_footer, render_header

GOVERNED_SPACE = "https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls"
GOVERNED_EMBED = "https://thyn-ai-algenta-governed-tool-calls.hf.space"
KERNELS_REPO = "https://github.com/thyn-ai/mojo-kernels"

DUEL_CHOICES = [(f"{d.title}", d.duel_id) for d in DUELS]
SIZE_CHOICES = {d.duel_id: [(d.size_label(k), k) for k in d.sizes] for d in DUELS}
# The landing duel: the volatility3 registry-hive walk — the arena's widest,
# most reliable live win on cpu-basic (~1,763× in the last full remote sweep,
# vs ~1.1× for the BM25 three-way on shared 2-vCPU).
DEFAULT_DUEL = "vol-hive"

# ---------------------------------------------------------------------------
# Space-boot background work: pre-warm the bm25s numba scorer (its one-time
# JIT cost, measured and disclosed), then run one boot duel so the Arena tab
# opens with a real, freshly measured result card (never a canned one).
# ---------------------------------------------------------------------------

_BOOT = {"done": False, "card": None, "outcome": None, "numba_warm_s": None}


def _boot() -> None:
    try:
        t0 = time.perf_counter()
        try:
            import bm25s
            from arena import corpora

            tiny = corpora.bm25_corpus(corpora.BASE_SEED, 64)
            bm = bm25s.BM25(dtype="float32")
            bm.index(tiny, show_progress=False)
            bm.compile()
            bm.get_scores(["w00000"])
            _BOOT["numba_warm_s"] = time.perf_counter() - t0
        except Exception:
            _BOOT["numba_warm_s"] = None
        duel = DUELS_BY_ID[DEFAULT_DUEL]
        try:
            result = run_sweep(duel, duel.default_size)
            outcome = result.outcome
            _BOOT["outcome"] = outcome
            if outcome is not None:
                store.record(outcome)
                _BOOT["card"] = render_card(
                    outcome, duel, duel.divisor(outcome.size_key), duel.divided_label
                )
            else:
                _BOOT["card"] = _fallback_card(duel, result, boot=True)
        except Exception:
            _BOOT["outcome"] = None
    finally:
        _BOOT["done"] = True


if os.environ.get("ARENA_DISABLE_BOOT") != "1":  # tests set this to keep boards deterministic
    threading.Thread(target=_boot, daemon=True).start()


# ---------------------------------------------------------------------------
# Duel runner (streaming generator)
# ---------------------------------------------------------------------------


def _fallback_card(duel, result, boot: bool = False) -> str:
    """No configuration won this run — show the duel's latest measured win.

    Every number on the fallback card comes from a recorded leaderboard entry
    with its real timestamp; if the duel has never recorded a win on this
    Space, an honest error card with the technical reason is shown instead.
    """
    entry = store.latest_win(duel.duel_id)
    if entry is not None:
        note = "live rematch runs at next boot" if boot else "press RUN DUEL for a live rematch"
        return render_fallback(entry, note)
    reason = "no verified winning configuration to show yet — press RUN DUEL to retry"
    if result is not None and result.attempts:
        last = result.attempts[-1]
        # Technical reasons (gate, native kernel, runner error) are shown;
        # a loss never is.
        if last.held_kind != "loss" and last.held_reason:
            reason = last.held_reason
    return render_held_card(duel, duel.default_size, reason)


def run_duel_ui(duel_id: str, size_key: str, user_ran: bool):
    user_ran = True
    duel = DUELS_BY_ID.get(duel_id)
    if duel is None:
        gr.Warning("Unknown duel selection")
        yield render_placeholder("Pick a duel and press RUN DUEL."), "", user_ran
        return

    q: queue.Queue = queue.Queue()
    holder: dict = {}

    def worker() -> None:
        holder["result"] = run_sweep(duel, size_key, progress=q.put)

    t0 = time.perf_counter()
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    lines = [f"⚡ {duel.title} — {duel.size_label(size_key)}"]
    while thread.is_alive() or not q.empty():
        try:
            lines.append(q.get(timeout=0.25))
        except queue.Empty:
            pass
        elapsed = time.perf_counter() - t0
        status = "\n".join(lines[-14:]) + f"\n\n_elapsed {elapsed:,.1f}s_"
        yield render_placeholder(status), "", user_ran

    result = holder.get("result")
    if result is None:
        gr.Warning("The duel runner failed unexpectedly — please retry.")
        yield render_held_card(duel, size_key, "runner died"), "", user_ran
        return

    outcome = result.outcome
    if outcome is not None:
        store.record(outcome)
        card = render_card(outcome, duel, duel.divisor(outcome.size_key), duel.divided_label)
        yield card, share_text(outcome), user_ran
        return

    yield _fallback_card(duel, result), "", user_ran


def render_held_card(duel, size_key, reason: str) -> str:
    from arena.harness import DuelOutcome
    from arena.harness import hardware_footer as hw

    return render_held(
        DuelOutcome(
            duel_id=duel.duel_id,
            duel_title=duel.title,
            size_key=size_key,
            size_label=duel.size_label(size_key),
            status="error",
            held_reason=reason,
            hardware=hw(),
        )
    )


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


def leaderboard_view():
    import pandas as pd

    rows = store.latest_per_duel()
    if not rows:
        return pd.DataFrame(columns=["duel", "size", "status", "hero speedup", "when"]), None
    df = pd.DataFrame(
        [
            {
                "duel": r["duel"],
                "size": r["size"],
                "status": r["status"],
                "hero speedup": f"{r['hero_speedup']:.2f}×" if r["hero_speedup"] else "—",
                "parity": (r["parity"][:60] + "…") if len(r["parity"]) > 60 else r["parity"],
                "when": r["ts"],
            }
            for r in rows
        ]
    )
    wins = pd.DataFrame(
        {
            "duel": [r["duel"] for r in rows if r["hero_speedup"]],
            "log10 speedup": [
                round(__import__("math").log10(r["hero_speedup"]), 3)
                for r in rows
                if r["hero_speedup"]
            ],
        }
    )
    plot = None
    if not wins.empty:
        plot = gr.BarPlot(
            wins,
            x="duel",
            y="log10 speedup",
            title="Latest measured speedups (log10 of ratio; 1.0 = 10×, 2.0 = 100×)",
            height=320,
        )
    return df, plot


# ---------------------------------------------------------------------------
# UI — canonical Algenta dark theme from design.py (THEME + payload CSS);
# the page chrome (header/footer) is the canonical fleet shell from shell.py.
# ---------------------------------------------------------------------------

HEADER_HTML = render_header(
    title="Algenta Speed Arena",
    tagline="Real-time benchmark duels — Mojo kernels vs incumbents",
    badges=[
        (
            "honest numbers only: measured live on this Space's cpu-basic "
            "2 vCPU — never copied from a README",
            "ok",
        ),
        (
            "we publish the configurations where Algenta wins — each run "
            "sweeps live and shows the best winning config",
            "warn",
        ),
    ],
    active="Speed Arena",
)

METHODOLOGY_MD = """
**How a duel works (the rulebook, enforced by the harness):** correctness gate before timing — if the
kernel's output doesn't match the oracle, no number is shown · seeded corpus, same bytes to every
lane · incumbent at its best legitimate config, printed on the card · cold first call + warm
median-of-5 with min–max spread, lanes interleaved A/B/A/B · end-to-end calls only (materialized
answers, no lazy iterators) · hardware disclosed in the card footer ·
full harness = this Space's `arena/` source + the repo's `benchmarks/` ·
every number measured live on this Space; we publish the configurations where Algenta wins.
"""


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Algenta Speed Arena", fill_width=True) as demo:
        gr.HTML(HEADER_HTML)
        user_ran = gr.State(False)

        with gr.Tabs():
            # ------------------------------------------------ Arena tab ----
            with gr.Tab("Arena"):
                with gr.Row():
                    with gr.Column(scale=2):
                        duel_radio = gr.Radio(
                            choices=DUEL_CHOICES,
                            value=DEFAULT_DUEL,
                            label="Duel",
                            info=DUELS_BY_ID[DEFAULT_DUEL].blurb,
                        )
                        size_radio = gr.Radio(
                            choices=SIZE_CHOICES[DEFAULT_DUEL],
                            value=DUELS_BY_ID[DEFAULT_DUEL].default_size,
                            label="Size (one cell per run, ~30s budget)",
                        )
                        run_btn = gr.Button("RUN DUEL", variant="primary", size="lg")
                    with gr.Column(scale=3):
                        card = gr.HTML(
                            render_placeholder(
                                "Warming up — the boot duel is being measured live on this Space right now…"
                            )
                        )
                        share = gr.Textbox(
                            label="share this result",
                            buttons=["copy"],
                            lines=3,
                            placeholder="run a duel — a pre-written factual post with the live numbers appears here",
                        )
                        with gr.Row():
                            gr.Markdown(f"<span class='card-hw'>{hardware_footer()}</span>")

                duel_radio.change(
                    lambda d: gr.update(
                        choices=SIZE_CHOICES[d],
                        value=DUELS_BY_ID[d].default_size,
                        info=DUELS_BY_ID[d].blurb,
                    ),
                    duel_radio,
                    size_radio,
                )
                duel_radio.change(
                    lambda d: gr.update(info=DUELS_BY_ID[d].blurb), duel_radio, duel_radio
                )

                run_btn.click(
                    run_duel_ui,
                    [duel_radio, size_radio, user_ran],
                    [card, share, user_ran],
                    show_progress="minimal",
                )

                # Show the boot-measured card once it is ready (only until the
                # visitor runs their own duel — the timer then stops).
                boot_timer = gr.Timer(5, active=True)

                def _show_boot(ran):
                    if ran or not _BOOT["done"]:
                        return gr.update(), gr.update()
                    if _BOOT["card"]:
                        return _BOOT["card"], gr.Timer(active=False)
                    return gr.update(), gr.Timer(active=False)

                boot_timer.tick(_show_boot, [user_ran], [card, boot_timer])

                with gr.Accordion("methodology (the defensibility rulebook)", open=False):
                    gr.Markdown(METHODOLOGY_MD)

            # ------------------------------------------- Leaderboard tab ----
            with gr.Tab("Leaderboard"):
                gr.Markdown(
                    "Latest measured winning result per duel, with its measurement time (UTC). "
                    "Persists in a JSON file inside the Space; resets when the Space restarts/rebuilds."
                )
                board = gr.Dataframe(label="latest per duel", interactive=False)
                wins_plot = gr.BarPlot(label="biggest wins")
                lb_timer = gr.Timer(15, active=True)
                lb_timer.tick(leaderboard_view, None, [board, wins_plot])
                demo.load(leaderboard_view, None, [board, wins_plot])

            # ------------------------------------------ Kernel gallery tab ----
            with gr.Tab("Kernel gallery"):
                gr.HTML(gallery_html(), sandbox=False)
                gr.Markdown(
                    f"Every kernel is open source (Apache-2.0) at [{KERNELS_REPO}]({KERNELS_REPO}) — "
                    "raw Mojo source, differential test suites and the full benchmark harness included. "
                    "Port your own bottleneck: the repo's FFI quickstart gets a first kernel running in minutes."
                )

            # ------------------------------------------ Governed agents tab ----
            with gr.Tab("Governed agents"):
                gr.Markdown(
                    f"""
The same team ships **governed tool calls for AI agents**: every tool call is allowed or denied by a
governance profile and emits a tamper-evident execution receipt.

* **Live demo:** [{GOVERNED_SPACE}]({GOVERNED_SPACE})
* **SDK:** `pip install algenta-sdk` — [github.com/thyn-ai/algenta-sdk](https://github.com/thyn-ai/algenta-sdk)
* **Integrations (LangChain and friends):** [github.com/thyn-ai/algenta-integrations](https://github.com/thyn-ai/algenta-integrations)
* **MCP Registry:** entry `io.github.thyn-ai/algenta` on [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io)
* **Self-host the engine free** under the Algenta Community license.

```bash
pip install algenta-sdk
```
```python
from algenta import GovernedAgent          # receipts on every tool call
agent = GovernedAgent(profile="default-deny")
result = agent.call("fs.read", {{"path": "/etc/passwd"}})
print(result.receipt)                      # signed allow/deny evidence
```
"""
                )
                gr.HTML(
                    f'<iframe src="{GOVERNED_EMBED}" style="width:100%; height:640px; '
                    'border:1px solid #e2e8f0; border-radius:12px;" loading="lazy"></iframe>',
                    sandbox=False,
                )

        gr.HTML(render_footer())

    return demo


demo = build_app()

if __name__ == "__main__":
    demo.queue(max_size=16, default_concurrency_limit=1).launch(
        theme=THEME, css=CSS + "\n" + SHELL_CSS, js=FORCE_DARK_JS
    )
