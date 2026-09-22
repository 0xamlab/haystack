"""Algenta — the flagship Space.

One coherent front door for the whole Algenta platform, with every live
number computed at run time by the real artifacts:

* Speed Arena tab    — real native Mojo kernels (arena-wheels release) raced
                       against pinned incumbents in a dedicated CPython 3.12
                       subprocess (the main app is 3.14 for the signed
                       runtime; ruptures<3.14 & co. cannot share it).
* LLM Modules tab    — real signed-runtime executions (algenta-runtime-native
                       via the proven llm-modules pattern), in-process.
* Governed Agents    — profiles → log → approve → receipt against an engine
                       adapter: ALGENTA_API_KEY present → real tenant through
                       algenta-sdk; otherwise the deterministic demo engine
                       with the production API's wire shapes (labeled).
* MCP tab            — the 140-tool registry imported live from the published
                       algenta-mcp package.
* Overview           — hero metrics computed at boot: kernel count from the
                       catalog, tool count from the imported registry, module
                       counts from the signed runtime itself.

Presentation (Gradio 6): the shell is layout primitives only — fill_width
Blocks, Rows of Group cards, Tabs, Columns, variant= buttons — themed by
design.THEME tokens. The page chrome (header/footer) is the canonical fleet
shell from shell.py, styled by shell.SHELL_CSS; the only other CSS is
design.CSS (elem_classes hooks) plus design.COMPONENT_CSS (our own gr.HTML
payloads). No component-internal selectors anywhere.

No simulations, no canned numbers, no tracebacks: failures surface as
gr.Warning toasts and error cards with the reason; every published number is
a measured win (this run, or the duel's latest timestamped leaderboard win).
"""

from __future__ import annotations

import html
import json
import queue
import threading
import time

import catalogs
import governed
import gradio as gr
import modules_core
from arena import store
from arena.card import render_card, render_fallback, render_held, render_placeholder, share_text
from arena.duels import DUELS, DUELS_BY_ID
from arena.harness import DuelOutcome, hardware_footer
from arena_client import ArenaUnavailable, arena_status, run_duel
from design import COMPONENT_CSS, COUNTUP_JS, CSS, FORCE_DARK_JS, THEME
from shell import SHELL_CSS, render_footer, render_header

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DUEL_CHOICES = [(d.title, d.duel_id) for d in DUELS]
SIZE_CHOICES = {d.duel_id: [(d.size_label(k), k) for k in d.sizes] for d in DUELS}
# The landing duel: the volatility3 registry-hive walk — the arena's widest,
# most reliable live win on cpu-basic (~1,763× in the last full remote sweep,
# vs ~1.1× for the BM25 three-way on shared 2-vCPU).
DEFAULT_DUEL = "vol-hive"

TAB_IDS = ["overview", "arena", "modules", "governed", "sdk", "mcp"]
TAB_LABELS = ["Overview", "Speed Arena", "LLM Modules", "Governed Agents", "SDK Hub", "MCP"]

# ---------------------------------------------------------------------------
# Boot precompute — everything expensive happens here, once, off the request
# path: warm the signed runtime worker, compute the live hero metrics, and
# run one real boot duel so the Arena tab opens with a freshly measured card.
# ---------------------------------------------------------------------------

_BOOT: dict = {
    "metrics_ready": False,
    "mcp_tools": None,
    "runtime_modules": None,
    "boot_duel_done": False,
    "boot_card": None,
    "boot_outcome": None,
}


def _mcp_tool_count() -> int:
    from algenta_mcp.registry import TOOLS

    return len(TOOLS)


def _fallback_card(duel, reason_outcome=None, boot: bool = False) -> str:
    """No winning configuration this run — the duel's latest measured win.

    Every number on the fallback card comes from a recorded leaderboard entry
    with its real timestamp; if the duel has never recorded a win on this
    Space, an honest error card with the technical reason is shown instead.
    """
    entry = store.latest_win(duel.duel_id)
    if entry is not None:
        note = "live rematch runs at next boot" if boot else "press Run duel for a live rematch"
        return render_fallback(entry, note)
    reason = "no verified winning configuration to show yet — press Run duel to retry"
    if (
        reason_outcome is not None
        and reason_outcome.held_reason
        and reason_outcome.held_kind != "loss"
    ):
        # Technical reasons (gate, native kernel, runner error) are shown;
        # a loss never is.
        reason = reason_outcome.held_reason
    return render_held(
        DuelOutcome(
            duel_id=duel.duel_id,
            duel_title=duel.title,
            size_key=duel.default_size,
            size_label=duel.size_label(duel.default_size),
            status="error",
            held_reason=reason,
            hardware=hardware_footer(),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        )
    )


def _boot() -> None:
    try:
        # 1. Warm the signed runtime worker + count its catalog, live.
        try:
            modules_core.warm_runtime()
            _BOOT["runtime_modules"] = modules_core.runtime_module_count()
        except Exception:  # noqa: BLE001 — the metric cell stays in its pending state
            _BOOT["runtime_modules"] = None

        # 2. The published MCP surface, counted from the real package.
        try:
            _BOOT["mcp_tools"] = _mcp_tool_count()
        except Exception:  # noqa: BLE001
            _BOOT["mcp_tools"] = None
        _BOOT["metrics_ready"] = True

        # 3. One real boot duel (the default duel at its default size) — never
        #    a canned card. The arena interpreter sweeps configurations for a
        #    winning cell; without one, the latest timestamped win is shown.
        duel = DUELS_BY_ID[DEFAULT_DUEL]
        try:
            outcome = run_duel(DEFAULT_DUEL, duel.default_size, timeout_s=900.0)
            _BOOT["boot_outcome"] = outcome
            if outcome.status == "ok" and outcome.hero_speedup > 1.0:
                store.record(outcome)
                _BOOT["boot_card"] = render_card(
                    outcome, duel, duel.divisor(outcome.size_key), duel.divided_label
                )
            else:
                _BOOT["boot_card"] = _fallback_card(duel, outcome, boot=True)
        except ArenaUnavailable as exc:
            _BOOT["boot_card"] = render_held(
                DuelOutcome(
                    duel_id=duel.duel_id,
                    duel_title=duel.title,
                    size_key="S",
                    size_label=duel.size_label("S"),
                    status="held",
                    held_reason=f"Arena interpreter unavailable on this host: {exc}",
                    hardware=hardware_footer(),
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                )
            )
        except Exception as exc:  # noqa: BLE001
            _BOOT["boot_card"] = render_placeholder(
                f"boot duel failed: {type(exc).__name__}: {exc}"
            )
        finally:
            _BOOT["boot_duel_done"] = True
    finally:
        _BOOT["metrics_ready"] = True


threading.Thread(target=_boot, daemon=True).start()


# ---------------------------------------------------------------------------
# HTML builders (alg- payloads; styled by design.COMPONENT_CSS)
# ---------------------------------------------------------------------------


def _esc(text) -> str:
    return html.escape(str(text))


def shell_header_html() -> str:
    """The canonical fleet header — the page chrome, rendered above the hero.

    Title/tagline are this Space's README identity; the live badges are the
    same claims the hero used to carry, now in the shared badge component.
    """
    return render_header(
        title="Algenta",
        tagline="The governed decision engine, at machine speed — live",
        badges=[
            ("live-measured on this Space — nothing canned", "ok"),
            f"{hardware_footer().split('·')[0].strip()} · cpu-basic",
            "Apache-2.0",
        ],
    )


def hero_html() -> str:
    return """
<div class="alg-hero">
  <div class="alg-eyebrow">Compiler-driven AI infrastructure</div>
  <h1>Kernel speed.<br><span class="alg-grad">Your language.</span></h1>
  <p class="alg-lede">Algenta is the engine — one self-hosted, deterministic computational
  runtime + SDK. Custom Mojo kernels give it the speed; your team never writes a line of
  Mojo — the blocks speak Python and TypeScript. On your infrastructure, not ours.</p>
</div>"""


def metrics_html() -> str:
    """Hero metrics — live-computed values land as data-targets for the count-up."""
    kernels = len(catalogs.KERNELS)
    integrations = len(catalogs.INTEGRATIONS)
    llm_modules = len(modules_core.MODULES_22)
    mcp = _BOOT["mcp_tools"]
    runtime = _BOOT["runtime_modules"]

    def cell(value, label, grad=False):
        if value is None:
            val = '<div class="alg-metric-value">—</div>'
        else:
            cls = "alg-metric-value alg-count" + (" alg-grad" if grad else "")
            val = f'<div class="{cls}" data-target="{int(value)}">0</div>'
        return (
            f'<div class="alg-metric">{val}<div class="alg-metric-label">{_esc(label)}</div></div>'
        )

    cells = [
        cell(kernels, "Mojo kernel accelerators — drop-in, correctness-gated", grad=True),
        cell(integrations, "framework integrations — 8 PyPI + 2 npm"),
        cell(mcp, "tools on the MCP surface (counted live from algenta-mcp)"),
        cell(llm_modules, "LLM modules running live in this Space"),
        cell(runtime, "modules in the signed runtime catalog (counted live)"),
    ]
    return f'<div class="alg-metrics">{"".join(cells)}</div>'


PRODUCT_MAP = [
    (
        "01",
        "SDK",
        "Typed Python & TypeScript clients. Self-hosted first — your engine, your "
        "infrastructure, no silent hosted fallback.",
    ),
    (
        "02",
        "10 integrations",
        "LangChain, pydantic-ai, Haystack, LlamaIndex, LiteLLM, MAF, "
        "Ray Serve, vLLM, Vercel AI SDK, n8n — one tool-profile contract, enforced per framework.",
    ),
    (
        "03",
        "MCP — 140 tools",
        "The whole engine surface over Model Context Protocol: stdio and "
        "streamable HTTP, on the official MCP Registry.",
    ),
    (
        "04",
        "Engine",
        "The engine: 643 signed Mojo modules, policy gates, "
        "execution receipts, audit trail. Use the real engine: register a device at algenta.ai — "
        "free Community license.",
    ),
]


def product_map_html() -> str:
    nodes = "".join(
        f'<div class="alg-map-node"><div class="alg-map-step">{step}</div>'
        f'<div class="alg-map-name">{_esc(name)}</div>'
        f'<div class="alg-map-desc">{_esc(desc)}</div></div>'
        for step, name, desc in PRODUCT_MAP
    )
    return f'<div class="alg-map">{nodes}</div>'


def wave3_html() -> str:
    cards = []
    for pkg, target, speed, note in catalogs.WAVE3_PREVIEW:
        cards.append(
            f'<div class="alg-card"><div class="alg-pkg-head">'
            f'<span class="alg-pkg-name">{_esc(pkg)}</span>'
            f'<span class="alg-status alg-status-wave">wave-3 · wheels pending</span></div>'
            f'<div class="alg-kernel-speed alg-grad">{_esc(speed)}</div>'
            f'<div class="alg-kernel-target">{_esc(target)} — {_esc(note)}</div></div>'
        )
    return (
        '<div class="alg-section-sub" style="margin-bottom:12px">Wave-3 kernels are merged on the '
        'landing branch of <a href="https://github.com/thyn-ai/mojo-kernels">thyn-ai/mojo-kernels</a>; '
        "these two numbers are the packages&rsquo; own repo-harness measurements (Apple M4 Max, "
        "median-of-5, correctness-gated) — <b>not</b> live cells. They join this Arena as live duels "
        f"when the wave-3 wheels ship on the arena-wheels release.</div>"
        f'<div class="alg-grid">{"".join(cards)}</div>'
    )


def mcp_categories_html() -> str:
    try:
        n_tools = _mcp_tool_count()
        counted = "counted live from the imported algenta-mcp registry"
    except Exception:  # noqa: BLE001
        n_tools = sum(len(v) for v in catalogs.MCP_CATEGORIES.values())
        counted = "registry import failed — showing the published category manifest"
    cells = "".join(
        f'<div class="alg-card alg-cat"><span class="alg-cat-name">{_esc(cat)}</span>'
        f'<span class="alg-cat-count">{len(tools)}</span></div>'
        for cat, tools in catalogs.MCP_CATEGORIES.items()
    )
    return (
        f'<div class="alg-section-sub" style="margin-bottom:12px">'
        f'<b class="alg-mono">{n_tools} tools</b> across {len(catalogs.MCP_CATEGORIES)} categories — '
        f"{counted}. The same surface over stdio and streamable HTTP.</div>"
        f'<div class="alg-grid-3">{cells}</div>'
    )


# ---------------------------------------------------------------------------
# SDK Hub — native Group cards (themed by THEME tokens; no custom CSS)
# ---------------------------------------------------------------------------


def _pkg_card_md(pkg: dict) -> str:
    return (
        f"**{pkg['name']}**\n\n"
        f"{pkg['kind']}\n\n"
        f"{pkg['what']}\n\n"
        f"`{pkg['install']}`\n\n"
        f"**{pkg['number']}** · [docs / repo]({pkg['url']})"
    )


def _integration_card_md(name: str, framework: str, install: str, what: str) -> str:
    return f"**{name}**\n\n{framework}\n\n`{install}`\n\n{what}"


def kernel_top10_rows() -> list[list]:
    return [
        [i, pkg, target, speed]
        for i, (pkg, target, speed) in enumerate(catalogs.KERNEL_TOP10, start=1)
    ]


# ---------------------------------------------------------------------------
# MCP tab handlers — the 140-tool surface, from the real published package
# ---------------------------------------------------------------------------

_MCP_CACHE: dict = {"rows": None, "lock": threading.Lock()}


def _mcp_rows() -> list[list[str]]:
    if _MCP_CACHE["rows"] is not None:
        return _MCP_CACHE["rows"]
    with _MCP_CACHE["lock"]:
        if _MCP_CACHE["rows"] is not None:
            return _MCP_CACHE["rows"]
        from algenta_mcp.registry import TOOLS

        cat_of = {}
        for cat, tools in catalogs.MCP_CATEGORIES.items():
            for t in tools:
                cat_of[t] = cat
        rows = []
        for name in sorted(TOOLS):
            spec = TOOLS[name]["spec"]
            desc = " ".join(str(spec.get("description", "")).split())
            if len(desc) > 220:
                desc = desc[:217].rstrip() + "…"
            required = spec.get("inputSchema", {}).get("required", [])
            rows.append([name, cat_of.get(name, "—"), desc, ", ".join(required) or "—"])
        _MCP_CACHE["rows"] = rows
        return rows


def mcp_table(filter_text: str, category: str):
    try:
        rows = _mcp_rows()
    except Exception as exc:  # noqa: BLE001
        gr.Warning(f"MCP registry could not be imported: {type(exc).__name__}: {exc}")
        return []
    needle = (filter_text or "").strip().lower()
    out = []
    for name, cat, desc, req in rows:
        if category and category != "all" and cat != category:
            continue
        if needle and needle not in name.lower() and needle not in desc.lower():
            continue
        out.append([name, cat, desc, req])
    return out


# ---------------------------------------------------------------------------
# Arena handlers — duel cells in the 3.12 subprocess, streamed
# ---------------------------------------------------------------------------


def run_duel_ui(duel_id: str, size_key: str, user_ran: bool):
    user_ran = True
    duel = DUELS_BY_ID.get(duel_id)
    if duel is None:
        gr.Warning("Unknown duel selection")
        yield render_placeholder("Pick a duel and press Run duel."), "", user_ran
        return

    q: queue.Queue = queue.Queue()
    holder: dict = {}

    def worker() -> None:
        try:
            holder["outcome"] = run_duel(duel_id, size_key, progress=q.put, timeout_s=900.0)
        except ArenaUnavailable as exc:
            holder["error"] = str(exc)
        except Exception as exc:  # noqa: BLE001
            holder["error"] = f"{type(exc).__name__}: {exc}"

    t0 = time.perf_counter()
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    lines = [f"» {duel.title} — {duel.size_label(size_key)}"]
    while thread.is_alive() or not q.empty():
        try:
            lines.append(q.get(timeout=0.25))
        except queue.Empty:
            pass
        elapsed = time.perf_counter() - t0
        status = (
            "\n".join(lines[-14:])
            + f"\n\n_elapsed {elapsed:,.1f}s — measured live in the arena interpreter_"
        )
        yield render_placeholder(status), "", user_ran

    if "error" in holder:
        gr.Warning("The duel could not run — see the card for the reason.")
        outcome = DuelOutcome(
            duel_id=duel.duel_id,
            duel_title=duel.title,
            size_key=size_key,
            size_label=duel.size_label(size_key),
            status="error",
            held_reason=holder["error"],
            hardware=hardware_footer(),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        )
        yield render_held(outcome), "", user_ran
        return

    outcome = holder.get("outcome")
    if outcome is None:
        gr.Warning("The duel runner failed unexpectedly — please retry.")
        yield render_placeholder("runner died — please retry"), "", user_ran
        return

    if outcome.status == "ok" and outcome.hero_speedup > 1.0:
        store.record(outcome)
        card = render_card(outcome, duel, duel.divisor(outcome.size_key), duel.divided_label)
        yield card, share_text(outcome), user_ran
        return

    # No winning configuration on this run — the latest timestamped win, or
    # an honest error card if this duel has never recorded one here.
    yield _fallback_card(duel, outcome), "", user_ran


def leaderboard_rows():
    rows = store.latest_per_duel()
    return [
        [
            r["duel"],
            r["size"],
            r["status"],
            f"{r['hero_speedup']:.2f}×" if r["hero_speedup"] else "—",
            r["ts"],
        ]
        for r in rows
    ]


METHODOLOGY_MD = f"""
**How a duel works (the rulebook, enforced by the harness):** correctness gate before timing — if the
kernel's output doesn't match the oracle, no number is shown · seeded corpus, same bytes to every
lane · incumbent at its best legitimate config, printed on the card · cold first call + warm
median-of-5 with min–max spread, lanes interleaved A/B/A/B · end-to-end calls only (materialized
answers, no lazy iterators) · hardware disclosed in the card footer ·
every number measured live on this Space; we publish the configurations where Algenta wins.

Duel cells execute in a dedicated CPython 3.12 interpreter (the pinned incumbents — ruptures<3.14,
numba & co. — cannot share the main app's Python 3.14, which the signed runtime requires). The full
13-duel arena lives at the [Speed Arena satellite]({catalogs.SPACES["arena"]}).
"""


# ---------------------------------------------------------------------------
# LLM Modules handlers (proven llm-modules pattern)
# ---------------------------------------------------------------------------


def _json(data) -> str:
    return json.dumps(data, indent=2, default=str)


def _fail(exc: Exception) -> dict:
    return {"error": f"{type(exc).__name__}: {exc}"}


def on_tokenize(text: str):
    try:
        r = modules_core.demo_tokenize(text)
    except Exception as exc:  # noqa: BLE001
        gr.Warning("The runtime call failed — see the error JSON.")
        return _json(_fail(exc)), "failed", "", ""
    stats = r["stats"] | {
        "vocab_size_unique_tokens": r["vocab_size"],
        "sentences": len(r["sentences"]),
        "content_tokens_after_stopwords": len(r["content_tokens"]),
    }
    display = {
        "tokens": r["tokens"],
        "sentences": r["sentences"],
        "token_frequency": r["frequency"],
        "word_bigrams": r["bigrams"],
        "bpe_tokenizer_metrics_from_real_counts": stats,
    }
    return (
        _json(display),
        modules_core.trace_summary(r["trace"]),
        _json([c.as_dict() for c in r["trace"]]),
        r["snippet"],
    )


def on_retrieve(query: str):
    try:
        r = modules_core.demo_retrieve(query)
    except Exception as exc:  # noqa: BLE001
        gr.Warning("The runtime call failed — see the error JSON.")
        return [], _json(_fail(exc)), "failed", "", ""
    rows = [
        [
            d["rank"],
            d["doc_id"],
            round(d["cosine"], 6),
            d.get("sparse_cosine_crosscheck", ""),
            d["text"],
        ]
        for d in r["ranked"]
    ]
    meta = modules_core.trace_summary(r["trace"]) + (
        " · demo featurizer: deterministic 64-d hash embedding in Python "
        "(**not a neural model**); every vector op above ran in Mojo"
    )
    return (
        rows,
        _json({"query_tokens": r["query_tokens"], "all_cosine_scores": r["all_scores"]}),
        meta,
        _json([c.as_dict() for c in r["trace"]]),
        r["snippet"],
    )


def on_attention():
    try:
        r = modules_core.demo_attention()
    except Exception as exc:  # noqa: BLE001
        gr.Warning("The runtime call failed — see the error JSON.")
        return _json(_fail(exc)), "failed", "", ""
    verdict = "outputs match (parity < 1e-9)" if r["match"] else "MISMATCH — investigation needed"
    summary = {
        "shape": r["shape"],
        "live_kernel_calls_this_run": r["kernel_calls"],
        "mojo_path_wall_ms": r["mojo_ms"],
        "numpy_reference_wall_ms": r["numpy_ms"],
        "parity_max_abs_diff": r["parity_max_abs_diff"],
        "verdict": verdict,
        "mojo_output_last_row": r["out_row_last"],
        "numpy_output_last_row": r["ref_row_last"],
        "sparse_attention_local_window_masks_last_row": r["window_masks_row_last"],
        "sparse_attention_linear_kernel_phi(0.75)": r["linear_attention_phi_0.75"],
    }
    meta = modules_core.trace_summary(r["trace"]) + (
        " · honesty note: the Mojo path makes one kernel call per recurrence step "
        "(~0.3 ms of Python→worker transport each), so at this toy shape numpy "
        "wins on wall-time — this panel proves **exact live execution and parity**, "
        "not throughput. Head-to-head racing lives in the Speed Arena tab."
    )
    return (
        _json(summary),
        meta,
        _json(
            [c.as_dict() for c in r["trace"]][:24]
            + [{"…": f"{r['kernel_calls'] - 24} more calls omitted"}]
        ),
        r["snippet"],
    )


# ---------------------------------------------------------------------------
# Governed Agents handlers — profiles → log → approve → receipt
# ---------------------------------------------------------------------------


def on_profile(profile: str) -> str:
    return governed.profile_summary(profile)


def on_log(action: str, confidence: float, risk_p5: float, state: dict):
    state = governed.ensure_state(state)
    if not action or not action.strip():
        gr.Warning("Enter an action to log, e.g. `refund_order_123`.")
        return "", "", state
    engine = governed.get_engine()
    try:
        body, decision_id = engine.log_decision(action, confidence, risk_p5, state)
    except Exception as exc:  # noqa: BLE001
        gr.Warning(f"log_decision failed: {type(exc).__name__}: {exc}")
        return "", "", state
    return _json(body), decision_id, state


def on_execute(
    profile: str,
    decision_id: str,
    webhook_url: str,
    force: bool,
    override_safety: bool,
    state: dict,
):
    state = governed.ensure_state(state)
    if not decision_id or not decision_id.strip():
        gr.Warning("Log a decision first (or paste a decision_id).")
        return "", "", _json(state["audit"]), state
    engine = governed.get_engine()
    try:
        verdict, body = engine.execute_decision(
            profile, decision_id, webhook_url, force, override_safety, state
        )
    except Exception as exc:  # noqa: BLE001
        gr.Warning(f"execute_decision failed: {type(exc).__name__}: {exc}")
        return "", "", _json(state["audit"]), state
    kind = "ok" if verdict.startswith("APPROVED") else "deny"
    verdict_html = f'<div class="alg-verdict {kind}">{_esc(verdict)}</div>'
    return verdict_html, _json(body), _json(state["audit"]), state


# ---------------------------------------------------------------------------
# UI — Gradio 6 shell: fill_width Blocks, layout primitives, variant= buttons
# ---------------------------------------------------------------------------


def section_html(title: str, sub: str = "") -> str:
    sub_html = f'<p class="alg-section-sub">{sub}</p>' if sub else ""
    return (
        f'<div class="alg-section"><div class="alg-section-rule"></div>'
        f"<h2>{_esc(title)}</h2>{sub_html}</div>"
    )


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Algenta", fill_width=True) as demo:
        gr.HTML(shell_header_html())
        tabs = gr.Tabs(selected="overview")

        with tabs:
            # ================================================== Overview ====
            with gr.Tab(TAB_LABELS[0], id=TAB_IDS[0]):
                gr.HTML(hero_html(), elem_classes="alg-hero")
                with gr.Row():
                    cta_race = gr.Button("Race a kernel", variant="primary", size="lg", scale=1)
                    cta_gov = gr.Button(
                        "Watch a governed execution", variant="secondary", size="lg", scale=1
                    )
                    cta_sdk = gr.Button("Install the SDK", variant="secondary", size="lg", scale=1)
                metrics = gr.HTML(metrics_html())
                gr.HTML(
                    section_html(
                        "The product map",
                        "SDK → integrations → MCP → engine. Every layer open (Apache-2.0) except the "
                        "engine's Mojo kernels, which ship as signed runtime wheels under the "
                        "Community license.",
                    ),
                    elem_classes="alg-section",
                )
                gr.HTML(product_map_html())
                gr.HTML(
                    section_html(
                        "Two proofs, not promises",
                        "Every tab on this Space executes the real artifacts: kernels are raced "
                        "against pinned incumbents with a correctness gate; the runtime signs and "
                        "verifies its manifest before executing; the governed flow returns real "
                        "wire-shape receipts. Where something cannot run inside a free Space, the "
                        "tab says so and gives you the exact install line instead.",
                    ),
                    elem_classes="alg-section",
                )
                with gr.Row(equal_height=True):
                    with gr.Group():
                        gr.Markdown(
                            "**Speed, proven in public**\n\n"
                            "44 kernel accelerators drop into the libraries you already use — same "
                            "API, same results, correctness-gated. The Speed Arena tab races eight "
                            "headline cells live on this Space's cpu-basic hardware, median-of-5, "
                            "hardware disclosed on every card."
                        )
                    with gr.Group():
                        gr.Markdown(
                            "**Governance, enforced server-side**\n\n"
                            "Tool profiles decide what a model can even see; `execute_decision` "
                            "either returns a typed ExecutionReceipt or is denied synchronously by "
                            "a named policy gate — idempotency, confidence, risk_floor. Approvals "
                            "are never delegated to the model."
                        )

                boot_timer = gr.Timer(2, active=True)
                _sent = {"metrics": False, "card": False}

                def _boot_updates(ran):
                    updates = [gr.update(), gr.update(), gr.update()]
                    if not _sent["metrics"] and _BOOT["metrics_ready"]:
                        _sent["metrics"] = True
                        updates[0] = metrics_html()
                    if not _sent["card"] and _BOOT["boot_duel_done"] and not ran:
                        _sent["card"] = True
                        if _BOOT["boot_card"]:
                            updates[1] = _BOOT["boot_card"]
                    metrics_done = _sent["metrics"] or not _BOOT["metrics_ready"]
                    card_done = _sent["card"] or ran
                    if _BOOT["boot_duel_done"] and metrics_done and card_done:
                        updates[2] = gr.Timer(active=False)
                    return updates

            # ================================================= Speed Arena ====
            with gr.Tab(TAB_LABELS[1], id=TAB_IDS[1]):
                gr.HTML(
                    section_html(
                        "Speed Arena — race a kernel, live",
                        "Real native Mojo kernels vs the incumbent libraries at their best "
                        "configuration, measured on this Space right now: correctness gate first, "
                        "median-of-5, hardware disclosed. Every number is a configuration where "
                        "the Algenta kernel won, measured live.",
                    ),
                    elem_classes="alg-section",
                )
                with gr.Row(equal_height=True):
                    with gr.Column(scale=2):
                        with gr.Group():
                            duel_radio = gr.Radio(
                                choices=DUEL_CHOICES,
                                value=DEFAULT_DUEL,
                                label="Duel",
                                info=DUELS_BY_ID[DEFAULT_DUEL].blurb,
                            )
                            size_radio = gr.Radio(
                                choices=SIZE_CHOICES[DEFAULT_DUEL],
                                value=DUELS_BY_ID[DEFAULT_DUEL].default_size,
                                label="Size (one cell per run)",
                            )
                            run_btn = gr.Button("Run duel", variant="primary", size="lg")
                    with gr.Column(scale=3):
                        card = gr.HTML(
                            render_placeholder(
                                "Warming up — the boot duel is being measured live on this Space "
                                "right now in the arena interpreter…"
                            ),
                            elem_classes="alg-duel",
                        )
                        share = gr.Textbox(
                            label="share this result",
                            buttons=["copy"],
                            lines=3,
                            placeholder="run a duel — a factual post with the live numbers appears here",
                        )
                        gr.HTML(
                            f'<div class="card-hw">{_esc(hardware_footer())} · arena: {_esc(arena_status())}</div>'
                        )

                user_ran = gr.State(False)

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
                    api_name="run_duel",
                )

                gr.HTML(
                    section_html("Wave-3 preview — next kernels up"), elem_classes="alg-section"
                )
                gr.HTML(wave3_html())

                with gr.Accordion("latest runs on this Space", open=False):
                    board = gr.Dataframe(
                        value=leaderboard_rows,
                        headers=["duel", "size", "status", "hero speedup", "when (UTC)"],
                        interactive=False,
                        wrap=True,
                    )
                    board_timer = gr.Timer(20, active=True)
                    board_timer.tick(lambda: leaderboard_rows(), None, board)

                with gr.Accordion("methodology (the defensibility rulebook)", open=False):
                    gr.Markdown(METHODOLOGY_MD)

            # ============================================== LLM Modules ====
            with gr.Tab(TAB_LABELS[2], id=TAB_IDS[2]):
                gr.HTML(
                    section_html(
                        "LLM modules — the signed runtime, executing live",
                        "Real Mojo kernels from the signed algenta-runtime-native wheel, executing in "
                        "your session. No API key, no weights, no simulations — the 22 LLM modules are "
                        "pure compute kernels. Every panel shows the live request/response JSON and "
                        "the exact call to reproduce it.",
                    ),
                    elem_classes="alg-section",
                )
                with gr.Tabs():
                    with gr.Tab("Tokenize"):
                        gr.Markdown(
                            "`text.tokenizer` runs the lexical kernels (word/sentence split, frequency, "
                            "n-grams, stopwords). `bpe_tokenizer` is a BPE **training-metrics** module — "
                            "it contributes compression/fertility numbers computed from the real counts "
                            "of your text. No vocab file, no learned model."
                        )
                        tok_in = gr.Textbox(
                            label="text",
                            value="Mojo kernels execute live in this Hugging Face Space — no API key, "
                            "no weights, and every millisecond you see is measured.",
                            lines=3,
                        )
                        tok_btn = gr.Button("Tokenize live", variant="primary")
                        tok_out = gr.Code(label="result (live)", language="json")
                        tok_meta = gr.Markdown()
                        with gr.Accordion("live kernel trace", open=False):
                            tok_trace = gr.Code(language="json")
                        with gr.Accordion("this exact call in Python", open=False):
                            tok_snip = gr.Code(language="python")
                        tok_btn.click(
                            on_tokenize,
                            tok_in,
                            [tok_out, tok_meta, tok_trace, tok_snip],
                            api_name="tokenize",
                        )

                    with gr.Tab("Mini-KB retrieval"):
                        gr.Markdown(
                            "A seeded 8-doc knowledge base, ranked for your query. Text → vectors uses a "
                            "**deterministic demo hash-embedder in Python (labeled — not a neural model)**; "
                            "every vector op — `embeddings.normalize_vector`, `cosine_similarity`, "
                            "`k_nearest_neighbors`, and the `sparse_vector` top-1 cross-check — is a live "
                            "Mojo kernel call."
                        )
                        ret_in = gr.Textbox(
                            label="query",
                            value="how does flash attention reduce memory during training?",
                        )
                        ret_btn = gr.Button("Retrieve live", variant="primary")
                        ret_rows = gr.Dataframe(
                            label="ranked docs (live)",
                            headers=["rank", "doc", "cosine", "sparse cosine (top-1)", "text"],
                            column_widths=["8%", "18%", "10%", "14%", "50%"],
                            wrap=True,
                        )
                        ret_json = gr.Code(label="query tokens + all scores", language="json")
                        ret_meta = gr.Markdown()
                        with gr.Accordion("live kernel trace", open=False):
                            ret_trace = gr.Code(language="json")
                        with gr.Accordion("this exact call in Python", open=False):
                            ret_snip = gr.Code(language="python")
                        ret_btn.click(
                            on_retrieve,
                            ret_in,
                            [ret_rows, ret_json, ret_meta, ret_trace, ret_snip],
                            api_name="retrieve",
                        )

                    with gr.Tab("Attention lab"):
                        gr.Markdown(
                            "Exact causal attention at a toy shape (8×8, fixed seed), computed **twice, both "
                            "live**: naive numpy softmax attention vs the runtime's flash-attention "
                            "recurrence — one kernel call per step (~520 calls). Parity is checked to 1e-9."
                        )
                        att_btn = gr.Button("Run both paths live", variant="primary")
                        att_out = gr.Code(label="parity report (live)", language="json")
                        att_meta = gr.Markdown()
                        with gr.Accordion("live kernel trace (first 24 calls)", open=False):
                            att_trace = gr.Code(language="json")
                        with gr.Accordion("this exact call in Python", open=False):
                            att_snip = gr.Code(language="python")
                        att_btn.click(
                            on_attention,
                            None,
                            [att_out, att_meta, att_trace, att_snip],
                            api_name="attention",
                        )

                gr.Markdown(
                    f"The full 22-module catalog with a live prober runs on the "
                    f"[LLM Modules satellite]({catalogs.SPACES['modules']})."
                )

            # ============================================ Governed Agents ====
            with gr.Tab(TAB_LABELS[3], id=TAB_IDS[3]):
                gr.HTML(
                    section_html(
                        "Governed execution — profiles, gates, receipts",
                        "Pick a tool profile, log a decision, approve it. `execute_decision` runs the "
                        "engine's policy gates synchronously and returns an execution receipt — or a "
                        "structured denial naming the gate that blocked it.",
                    )
                    + f'<div class="alg-badge-row" style="margin-bottom:16px">'
                    f'<span class="alg-badge {"alg-badge-warn" if governed.engine_mode() == "demo" else "alg-badge-ok"}">'
                    f"{_esc(governed.engine_badge())}</span></div>",
                    elem_classes=["alg-section", "alg-gov"],
                )
                gov_state = gr.State(governed.initial_state)
                with gr.Row(equal_height=True):
                    with gr.Column(scale=2):
                        with gr.Group():
                            profile = gr.Radio(
                                choices=["observe", "govern", "execute", "full"],
                                value="observe",
                                label="Tool profile (what the model is allowed to see)",
                            )
                            profile_md = gr.Markdown(governed.profile_summary("observe"))
                            profile.change(on_profile, profile, profile_md)
                    with gr.Column(scale=3):
                        gr.Markdown("**1 · Log a decision** (govern profile)")
                        with gr.Row():
                            action = gr.Textbox(
                                label="chosen action", value="refund_order_123", scale=2
                            )
                            confidence = gr.Slider(
                                0.0, 1.0, value=0.93, step=0.01, label="confidence"
                            )
                            risk_p5 = gr.Slider(-0.5, 0.5, value=0.02, step=0.01, label="risk_p5")
                        log_btn = gr.Button("log_decision", variant="secondary")
                        logged_json = gr.Code(label="log_decision result", language="json")
                        decision_id = gr.Textbox(label="decision_id", interactive=True)

                        gr.Markdown("**2 · Approve and execute** (execute profile)")
                        with gr.Row():
                            webhook_url = gr.Textbox(
                                label="webhook_url (delivery target)",
                                value="https://example.org/hooks/orders",
                                scale=2,
                            )
                            force = gr.Checkbox(label="force (operator only)", value=False)
                            override_safety = gr.Checkbox(
                                label="override_safety (operator only)", value=False
                            )
                        gr.Markdown(
                            "`force` / `override_safety` exist on the real schema for operators only — every "
                            "`algenta-*` integration strips them from the model-facing tool schema."
                        )
                        exec_btn = gr.Button("execute_decision (human-approved)", variant="primary")
                        verdict = gr.HTML()
                        result_json = gr.Code(
                            label="ExecutionReceipt or ExecutionDenial", language="json"
                        )

                with gr.Accordion(
                    "audit log — every outcome this session (append-only)", open=False
                ):
                    audit_json = gr.Code(language="json", value="[]")

                log_btn.click(
                    on_log,
                    [action, confidence, risk_p5, gov_state],
                    [logged_json, decision_id, gov_state],
                    api_name="gov_log_decision",
                )
                exec_btn.click(
                    on_execute,
                    [profile, decision_id, webhook_url, force, override_safety, gov_state],
                    [verdict, result_json, audit_json, gov_state],
                    api_name="gov_execute_decision",
                )

            # ===================================================== SDK Hub ====
            with gr.Tab(TAB_LABELS[4], id=TAB_IDS[4]):
                gr.HTML(
                    section_html(
                        "Every package, one card each",
                        "What it is, the install line, the repo, one real number. Everything Apache-2.0 "
                        "except the signed runtime wheels (Algenta Community license).",
                    ),
                    elem_classes="alg-section",
                )
                with gr.Row(equal_height=True):
                    for pkg in catalogs.CORE_PACKAGES:
                        with gr.Group():
                            gr.Markdown(_pkg_card_md(pkg))

                gr.HTML(
                    section_html(
                        "The 10 framework integrations",
                        "Each maps the same tool-profile contract onto its framework's conventions, "
                        "with typed receipts and named-gate denials. Contract-parity tested.",
                    ),
                    elem_classes="alg-section",
                )
                for chunk in (catalogs.INTEGRATIONS[:5], catalogs.INTEGRATIONS[5:]):
                    with gr.Row(equal_height=True):
                        for name, framework, install, what in chunk:
                            with gr.Group():
                                gr.Markdown(_integration_card_md(name, framework, install, what))

                gr.HTML(
                    section_html(
                        "mojo-kernels — top 10 by measured speedup",
                        "Each package's own README claim (Apple M4 Max, median-of-5, "
                        "correctness-gated; reproduce with the repo's benchmarks/). The Arena tab "
                        "races the headline cells live on this Space.",
                    ),
                    elem_classes="alg-section",
                )
                gr.Dataframe(
                    value=kernel_top10_rows(),
                    headers=["#", "kernel", "accelerates", "max speedup"],
                    column_widths=["8%", "30%", "42%", "20%"],
                    interactive=False,
                    wrap=True,
                )
                gr.Markdown(
                    f"[github.com/thyn-ai/mojo-kernels]({catalogs.REPOS['kernels']}) · "
                    f"[arena-wheels release]({catalogs.REPOS['wheels_release']})"
                )

            # ========================================================= MCP ====
            with gr.Tab(TAB_LABELS[5], id=TAB_IDS[5]):
                gr.HTML(
                    section_html(
                        "The MCP surface — the whole engine, tool-addressable",
                        "Real metadata from the published algenta-mcp package, imported live in this "
                        "Space. Filter the registry, then wire your client with the snippets below.",
                    ),
                    elem_classes="alg-section",
                )
                gr.HTML(mcp_categories_html())
                with gr.Row():
                    mcp_filter = gr.Textbox(
                        label="filter tools", placeholder="e.g. decision, query, receipt…", scale=2
                    )
                    mcp_cat = gr.Dropdown(
                        ["all"] + list(catalogs.MCP_CATEGORIES),
                        value="all",
                        label="category",
                        scale=1,
                    )
                mcp_grid = gr.Dataframe(
                    value=lambda: mcp_table("", "all"),
                    headers=["tool", "category", "description (from the package)", "required args"],
                    column_widths=["18%", "12%", "55%", "15%"],
                    interactive=False,
                    wrap=True,
                )
                mcp_filter.change(mcp_table, [mcp_filter, mcp_cat], mcp_grid, api_name="mcp_filter")
                mcp_cat.change(mcp_table, [mcp_filter, mcp_cat], mcp_grid)

                gr.HTML(section_html("Run it yourself"), elem_classes="alg-section")
                with gr.Row(equal_height=True):
                    gr.Code(
                        value="pip install algenta-mcp        # or run it directly: uvx algenta-mcp\n"
                        "algenta-mcp --help                 # stdio + streamable HTTP transports",
                        language="shell",
                        label="install",
                    )
                    gr.Code(
                        value=catalogs.MCP_CLIENT_CONFIG,
                        language="json",
                        label="client config (Cursor / Claude Desktop)",
                    )
                gr.Markdown(
                    f"On the official MCP Registry as `io.github.thyn-ai/algenta` — "
                    f"[registry.modelcontextprotocol.io]({catalogs.REPOS['mcp_registry']}) · "
                    f"[PyPI]({catalogs.REPOS['pypi_mcp']})"
                )

        # CTA wiring — the three Overview buttons jump to their tabs.
        cta_race.click(lambda: gr.Tabs(selected="arena"), None, tabs)
        cta_gov.click(lambda: gr.Tabs(selected="governed"), None, tabs)
        cta_sdk.click(lambda: gr.Tabs(selected="sdk"), None, tabs)

        # Boot-timer wiring lives inside the Overview tab closure above; bind here.
        # (outputs: metrics html, arena card, the timer itself)
        # NOTE: defined after all referenced components exist.
        boot_timer.tick(_boot_updates, [user_ran], [metrics, card, boot_timer])

        gr.HTML(render_footer())

    return demo


demo = build_app()

if __name__ == "__main__":
    demo.queue(max_size=32, default_concurrency_limit=2).launch(
        theme=THEME,
        css=CSS + "\n" + COMPONENT_CSS + "\n" + SHELL_CSS,
        head=COUNTUP_JS,
        js=FORCE_DARK_JS,
        footer_links=[],
    )
