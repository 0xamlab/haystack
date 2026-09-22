"""Backend for the Algenta Governed Agent — Real LLM Space.

Everything in this module is real, deterministic-where-possible, and labeled:

- MODEL: Qwen/Qwen3-4B-Instruct-2507 (open weights, Apache-2.0) generating
  every token live, STREAMED from HF Inference Providers (provider pinned to
  nscale, billed to the thyn-ai org) with greedy decoding. The UI discloses
  this on every page; nothing is canned, mocked, or replayed. If the
  provider is unreachable or the HF_TOKEN secret is missing, the turn is
  HELD with the real error — there is no fallback text.
- TOOLS: the model may call only the five tools registered below; each one
  executes for real IN THIS SPACE — bm25_mojo (BM25), sacrebleu_mojo
  (BLEU/chrF), the signed algenta-runtime-native Mojo runtime (M/M/1
  discrete-event simulation), and the governance path (recommend /
  execute_action) whose profile gates, policy gates, denial bodies and
  signed receipts are deterministic local code replicating the Algenta
  engine's documented wire shapes. Governance, kernels and receipts never
  leave the Space.
- LOOP: question -> streamed JSON tool call (response_format json_object +
  robust parse, one retry with the validation error fed back, both attempts
  shown) -> real tool execution -> the model composes the final answer over
  the real tool result, streamed token-by-token into the chat. TTFT, tok/s
  and token counts are measured live on every model call from the provider's
  usage chunk.
- GUARDRAIL: the engine refuses to fabricate inputs. After tool selection,
  every numeric argument must be grounded in the user's message (10k/$15k/5%
  normalized) or equal to a documented schema default disclosed as defaulted;
  un-grounded numbers are rejected with feedback, one retry, then the turn
  ABSTAINS with an honest composed decline — never a fabricated run.

Nothing in here raises into the UI: failures are returned as held cards.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
import time
from datetime import UTC, datetime
from typing import Any

import corpus

# ---------------------------------------------------------------------------
# Inference backend — HF Inference Providers (serverless), streamed, org-billed
# ---------------------------------------------------------------------------
# The live model. The provider is pinned (nscale) so routing — and the
# "served by" disclosure — is deterministic; the org to bill is pinned too.
# Env overrides exist for operators (forks, provider incidents); the defaults
# are what this Space runs and what the badges claim.

PROVIDER_MODEL = os.environ.get("ALGENTA_PROVIDER_MODEL", "Qwen/Qwen3-4B-Instruct-2507")
PROVIDER_NAME = os.environ.get("ALGENTA_PROVIDER", "nscale")
PROVIDER_BILL_TO = os.environ.get("ALGENTA_BILL_TO", "thyn-ai")
MODEL_CARD = f"https://huggingface.co/{PROVIDER_MODEL}"
MODEL_LABEL = (
    f"{PROVIDER_MODEL.rsplit('/', 1)[-1]} · streamed via HF Inference Providers "
    f"(provider: {PROVIDER_NAME}, billed to org {PROVIDER_BILL_TO}) · greedy"
)

GEN_SEED = 20260920  # kept for the local GGUF reproduction path (see below)
GEN_MAX_TOKENS_CHOICE = 220
GEN_MAX_TOKENS_ANSWER = 320

# Local reproduction pin — the open-weights GGUF anyone can run offline to
# reproduce the loop end-to-end (the "Run it yourself" tab documents it).
# This is NOT what serves the live demo above: providers serve their own
# builds, so byte-level weight pinning applies to the local path only.
GGUF_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
GGUF_FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
GGUF_REVISION = "91cad51170dc346986eccefdc2dd33a9da36ead9"
GGUF_SHA256 = "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
GGUF_BYTES = 1_117_320_736
GGUF_CARD = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct"
N_CTX = 4096

# ---------------------------------------------------------------------------
# Governance policy (mirrors the Algenta engine's documented wire shapes)
# ---------------------------------------------------------------------------

MIN_CONFIDENCE = 0.80
RISK_FLOOR = 0.05
POLICY_SNAPSHOT_ID = "policy-snap-governed-agent-1"
SCHEMA_SNAPSHOT_ID = "schema-snap-governed-agent-1"
MANIFEST_VERSION = "1.0.13"

PROFILE_DESCRIPTIONS: dict[str, str] = {
    "observe": "Read-only: search, scoring, simulation, recommendations. `execute_action` is never model-facing.",
    "govern": "Observe + decision planning and logging. Nothing can be executed.",
    "execute": "Govern + `execute_action` (human-approved execution of a logged decision).",
    "full": "Everything the connected engine's MCP registry advertises. Opt-in only.",
}

EXECUTE_PROFILES = ("execute", "full")

# ---------------------------------------------------------------------------
# Tool registry — the only tools the model may call
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "search_corpus": {
        "description": (
            "BM25 search over a corpus of REAL English Wikipedia lead-extract passages "
            "(CC BY-SA 4.0, curated categories); returns top-5 ranked passages with scores, "
            "titles and URLs. Use for factual questions about real-world topics covered by "
            "general encyclopedic knowledge."
        ),
        "arguments": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "the search query"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    "score_answer": {
        "description": (
            "Score a candidate text (hypothesis) against a reference text: corpus BLEU and chrF "
            "via the sacrebleu_mojo kernel. Use when asked to score, grade, or compare texts."
        ),
        "arguments": {
            "type": "object",
            "properties": {
                "hypothesis": {"type": "string", "description": "the candidate text to score"},
                "reference": {"type": "string", "description": "the reference text"},
            },
            "required": ["hypothesis", "reference"],
            "additionalProperties": False,
        },
    },
    "simulate": {
        "description": (
            "Run a real M/M/1 single-server queue discrete-event simulation (Poisson arrivals "
            "at arrival_rate, exponential service at service_rate) on the signed Mojo runtime; "
            "returns avg queue wait, avg system time, utilization, plus closed-form cross-checks. "
            "This scenario models QUEUES ONLY — not finances, revenue, growth, or generic what-ifs."
        ),
        "arguments": {
            "type": "object",
            "properties": {
                "scenario": {"type": "string", "enum": ["mm1_queue"]},
                "arrival_rate": {"type": "number", "exclusiveMinimum": 0},
                "service_rate": {"type": "number", "exclusiveMinimum": 0},
                "n_customers": {
                    "type": "integer",
                    "minimum": 100,
                    "maximum": 20000,
                    "description": "simulation horizon; documented default 5000 when omitted (disclosed as defaulted)",
                },
            },
            "required": ["scenario", "arrival_rate", "service_rate"],
            "additionalProperties": False,
        },
    },
    "recommend": {
        "description": (
            "Recommend a governed action WITHOUT executing it: returns the policy thresholds "
            "and a preview of which gates it would pass or fail. Use for 'should we / would it "
            "be allowed' questions."
        ),
        "arguments": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "short snake_case action name"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "risk_p5": {
                    "type": "number",
                    "minimum": -1,
                    "maximum": 1,
                    "description": "5th-percentile outcome of the action (worst case), -1..1",
                },
            },
            "required": ["action", "confidence", "risk_p5"],
            "additionalProperties": False,
        },
    },
    "execute_action": {
        "description": (
            "Execute a governed action through the Algenta policy gates (idempotency, "
            "confidence, risk_floor): signed receipt on pass, structured denial on block. "
            "Use when the user explicitly asks to perform an action (refund, delete, ...)."
        ),
        "arguments": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "short snake_case action name"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "risk_p5": {
                    "type": "number",
                    "minimum": -1,
                    "maximum": 1,
                    "description": "5th-percentile outcome of the action (worst case), -1..1",
                },
            },
            "required": ["action", "confidence", "risk_p5"],
            "additionalProperties": False,
        },
    },
}


def profile_tools(profile: str) -> list[str]:
    """The model-facing tool list for a governance profile (real filtering)."""
    base = ["search_corpus", "score_answer", "simulate", "recommend"]
    if profile in EXECUTE_PROFILES:
        base.append("execute_action")
    return base


# ---------------------------------------------------------------------------
# Argument grounding — the engine refuses to fabricate inputs
# ---------------------------------------------------------------------------
# Documented schema defaults. An omitted argument with a documented default is
# filled in and DISCLOSED as defaulted; an explicitly-passed number equal to a
# documented default is likewise disclosed. Any other numeric argument must be
# traceable to the user's own message (after k/%/$ normalization).

ARG_DEFAULTS: dict[str, dict[str, float]] = {
    "simulate": {"n_customers": 5000},
}

# $15k / 10K / 5% / -0.02 / 10,000 / #123 / 0.9 — sign, currency, thousands,
# decimal, and the k / % suffixes.
_NUM_RE = re.compile(r"-?\$?\d[\d,]*(?:\.\d+)?\s*(?:[kK%])?")


def _extract_numbers(text: str) -> list[float]:
    """All numeric literals in the user's message, normalized.

    `10k`/`$15K` → 10000/15000; `5%` contributes BOTH 5 and 0.05 (either
    interpretation is a legitimate grounding); `10,000` → 10000.
    """
    out: list[float] = []
    for raw in _NUM_RE.findall(text or ""):
        token = raw.strip().replace("$", "").replace(",", "")
        suffix = ""
        if token and token[-1] in "kK%":
            suffix = token[-1].lower()
            token = token[:-1]
        try:
            value = float(token)
        except ValueError:
            continue
        if suffix == "k":
            out.append(value * 1000.0)
        elif suffix == "%":
            out.append(value)
            out.append(value / 100.0)
        else:
            out.append(value)
    return out


def _num_close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def _grounding_check(tool: str, args: dict[str, Any], question: str) -> tuple[list[str], list[str]]:
    """The argument-grounding guardrail. Returns (ungrounded, defaulted_notes).

    Every numeric argument must be either
      - grounded: present in the user's message after normalization, or
      - defaulted: equal to a documented schema default — allowed, but
        disclosed as defaulted in the trace/result.
    Anything else is un-grounded: display strings like 'service_rate=10'.
    Non-numeric values are not checked here (schemas/enums cover them).
    """
    given = _extract_numbers(question)
    defaults = ARG_DEFAULTS.get(tool, {})
    ungrounded: list[str] = []
    defaulted_notes: list[str] = []
    for key, value in args.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        number = float(value)
        if any(_num_close(number, g) for g in given):
            continue
        if key in defaults and _num_close(number, float(defaults[key])):
            defaulted_notes.append(f"{key}: {defaults[key]} (documented default)")
            continue
        shown = int(value) if isinstance(value, int) or float(value).is_integer() else value
        ungrounded.append(f"{key}={shown}")
    return ungrounded, defaulted_notes


def _apply_defaults(tool: str, args: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Fill omitted arguments that have documented defaults. Returns the
    completed args plus disclosure notes ('n_customers: 5000 (documented default)')."""
    completed = dict(args)
    notes: list[str] = []
    for key, default in ARG_DEFAULTS.get(tool, {}).items():
        if key not in completed:
            completed[key] = default
            notes.append(f"{key}: {default} (documented default)")
    return completed, notes


# ---------------------------------------------------------------------------
# Session state (per Gradio session; API callers get a fresh one per call)
# ---------------------------------------------------------------------------


def initial_state() -> dict[str, Any]:
    return {
        "decisions": {},
        "audit": [],
        "seq": 0,
        "hmac_key": os.urandom(16).hex(),
    }


def _ensure_state(state: Any) -> dict[str, Any]:
    """Normalize the state argument across UI and API callers (see hf-space)."""
    if state is None:
        return initial_state()
    if callable(state):
        return state()
    return state


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "action"


# ---------------------------------------------------------------------------
# Hardware / backend disclosure
# ---------------------------------------------------------------------------


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    import platform
    import subprocess

    if platform.system() == "Darwin":
        try:
            out = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return platform.processor() or platform.machine()


def _ram_gb() -> float:
    try:  # cgroup v2 memory limit (what the container can actually use)
        with open("/sys/fs/cgroup/memory.max", encoding="utf-8") as fh:
            raw = fh.read().strip()
            if raw != "max":
                return int(raw) / 1e9
    except (OSError, ValueError):
        pass
    try:  # cgroup v1 memory limit (ignore the "no limit" sentinel)
        with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", encoding="utf-8") as fh:
            limit = int(fh.read().strip())
            if 0 < limit < 1 << 60:
                return limit / 1e9
    except (OSError, ValueError):
        pass
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) / 1e6
    except OSError:
        pass
    import platform
    import subprocess

    if platform.system() == "Darwin":
        try:
            out = subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
            )
            return int(out.stdout.strip()) / 1e9
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return 0.0


def _cpu_quota() -> int:
    """Effective CPU count, cgroup-aware: os.cpu_count() reads the HOST's
    cores; inside a cpu-basic Space the container is quota-limited (2 vCPU).
    Used for the honest hardware footer."""
    try:  # cgroup v2
        with open("/sys/fs/cgroup/cpu.max", encoding="utf-8") as fh:
            parts = fh.read().split()
            if parts and parts[0] != "max":
                return max(1, int(parts[0]) // int(parts[1]))
    except (OSError, ValueError, IndexError):
        pass
    try:  # cgroup v1
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", encoding="utf-8") as fh:
            quota = int(fh.read().strip())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", encoding="utf-8") as fh:
            period = int(fh.read().strip())
        if quota > 0 and period > 0:
            return max(1, quota // period)
    except (OSError, ValueError):
        pass
    return os.cpu_count() or 2


def hardware_footer() -> str:
    import platform

    space = os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID") or ""
    host = f"HF Space {space} (cpu-basic)" if space else "local run"
    return (
        f"governance · kernels · receipts run locally on {host} · {_cpu_model()} · "
        f"{_cpu_quota()} vCPU (cgroup-effective) · {_ram_gb():.0f} GB RAM · "
        f"{platform.system()} {platform.release()} {platform.machine()} · "
        f"Python {platform.python_version()} · demo inference streamed from HF "
        f"Inference Providers (model {PROVIDER_MODEL}, provider {PROVIDER_NAME}, "
        f"billed to org {PROVIDER_BILL_TO})"
    )


def backend_report() -> dict[str, Any]:
    """Which kernels are native vs pure-Python fallback on THIS host. Honest labels."""
    report: dict[str, Any] = {}
    try:
        import bm25_mojo

        report["bm25_mojo"] = bm25_mojo.backend_info()
    except Exception as exc:  # noqa: BLE001
        report["bm25_mojo"] = {"native_available": False, "error": f"{type(exc).__name__}: {exc}"}
    try:
        import sacrebleu_mojo

        report["sacrebleu_mojo"] = sacrebleu_mojo.backend_info()
    except Exception as exc:  # noqa: BLE001
        report["sacrebleu_mojo"] = {
            "native_available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    try:
        rt = _runtime()
        report["algenta_runtime"] = {
            "available": True,
            "mode": "local (signed algenta-runtime-native)",
        }
        _ = rt  # probed lazily elsewhere
    except Exception as exc:  # noqa: BLE001
        report["algenta_runtime"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    return report


# ---------------------------------------------------------------------------
# Model runner — streamed chat completions via HF Inference Providers
# ---------------------------------------------------------------------------
# Every token the demo shows is generated live by the provider-served model
# and streamed into this Space; governance, kernels and receipts stay local.
# Token counts come from the provider's usage chunk (include_usage), TTFT and
# decode tok/s are measured here — nothing is copied from a README.

_CLIENT = None
_CLIENT_LOCK = threading.Lock()


def _client():
    """The shared InferenceClient. Raises (loudly) when inference is not
    configured — there is no fallback and no canned answer."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is not None:
            return _CLIENT
        from huggingface_hub import InferenceClient

        token = os.environ.get("HF_TOKEN") or os.environ.get("HF_API_KEY")
        if not token:
            raise RuntimeError(
                "inference is not configured: the HF_TOKEN secret is missing "
                "(Space Settings → Secrets). No fallback, no canned answers."
            )
        _CLIENT = InferenceClient(
            api_key=token,
            provider=PROVIDER_NAME,
            bill_to=PROVIDER_BILL_TO,
            timeout=120.0,
        )
        return _CLIENT


def _chat_stream(
    messages: list[dict[str, str]],
    *,
    json_mode: bool,
    max_tokens: int,
):
    """One measured, STREAMED model call, as a generator. Greedy (temp 0).

    Yields {"token": delta} for every real provider-generated delta as it
    arrives, then exactly one {"stats": {...}} as the final item with the
    assembled text and the live measurements (TTFT, decode tok/s, token
    counts from the provider's usage chunk). Determinism control is the
    greedy request; providers do not expose a seed, which is why the
    byte-exact reproduction path stays the local GGUF documented in the UI.
    """
    client = _client()
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    started = time.perf_counter()
    stream = client.chat.completions.create(
        model=PROVIDER_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.0,
        stream=True,
        stream_options={"include_usage": True},
        **kwargs,
    )
    ttft: float | None = None
    parts: list[str] = []
    usage = None
    for chunk in stream:
        if not chunk.choices:
            if getattr(chunk, "usage", None) is not None:
                usage = chunk.usage
            continue
        delta = chunk.choices[0].delta.content or ""
        if not delta:
            continue
        if ttft is None:
            ttft = time.perf_counter() - started
        parts.append(delta)
        yield {"token": delta}
    elapsed = time.perf_counter() - started
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    decode_s = elapsed - ttft if ttft is not None else 0.0
    yield {
        "stats": {
            "text": "".join(parts),
            "seconds": round(elapsed, 2),
            "ttft_seconds": round(ttft, 2) if ttft is not None else None,
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": completion,
            # decode-only rate, like the reference WebGPU Spaces report
            "tok_per_s": round(completion / decode_s, 2)
            if completion > 1 and decode_s > 0
            else 0.0,
        }
    }


# ---------------------------------------------------------------------------
# Boot sequence — explicit stages surfaced in the UI (reference-Space style)
# ---------------------------------------------------------------------------

_BOOT_LOCK = threading.Lock()
_BOOT: dict[str, Any] = {
    "started": False,
    "ready": False,
    "error": None,
    "stages": [
        {
            "id": "kernels",
            "label": "warming kernels (BM25 index · scoring oracle · signed runtime)",
            "state": "pending",
            "detail": "",
        },
        {
            "id": "inference",
            "label": "probing HF Inference Providers with a real generation",
            "state": "pending",
            "detail": "",
        },
    ],
    "probe": None,
}


def boot_status() -> dict[str, Any]:
    """A snapshot the UI polls while booting (thread-safe copy)."""
    with _BOOT_LOCK:
        return {
            "started": _BOOT["started"],
            "ready": _BOOT["ready"],
            "error": _BOOT["error"],
            "stages": [dict(s) for s in _BOOT["stages"]],
            "probe": dict(_BOOT["probe"]) if _BOOT["probe"] else None,
        }


def _set_stage(stage_id: str, state: str, detail: str = "") -> None:
    with _BOOT_LOCK:
        for stage in _BOOT["stages"]:
            if stage["id"] == stage_id:
                stage["state"] = state
                stage["detail"] = detail


def warm_kernels() -> None:
    """Build the BM25 index over the real corpus (timed — the measurement
    feeds the badge), fire the scoring kernel + oracle, spawn the signed
    runtime worker. Real warm-up work, timed and reported."""
    _set_stage("kernels", "running")
    started = time.perf_counter()
    try:
        import sacrebleu
        import sacrebleu_mojo

        corpus.mojo_index().get_scores(corpus.tokenize("karman vortex street"))
        sacrebleu_mojo.corpus_bleu(["warm up"], [["warm up"]])
        sacrebleu.corpus_bleu(["warm up"], [["warm up"]])
        warm_runtime()
        idx = corpus.index_stats() or {}
        idx_part = f"indexed {idx['docs']} real passages in {idx['build_ms']} ms · " if idx else ""
        _set_stage(
            "kernels", "done", f"{idx_part}kernels warm in {time.perf_counter() - started:.1f}s"
        )
    except Exception as exc:  # noqa: BLE001 — per-call labels stay honest; not boot-fatal
        _set_stage("kernels", "error", f"{type(exc).__name__}: {exc}")


def warm_inference() -> None:
    """A tiny REAL streamed generation through the provider: proves the
    secret, the route and org billing work, and measures a live probe TTFT.
    Boot-fatal on failure — the demo must not look ready when it is not."""
    _set_stage("inference", "running")
    try:
        stats = None
        for item in _chat_stream(
            [{"role": "user", "content": "Reply with the single word: ready"}],
            json_mode=False,
            max_tokens=8,
        ):
            if "stats" in item:
                stats = item["stats"]
        assert stats is not None
        with _BOOT_LOCK:
            _BOOT["probe"] = {
                "ttft_seconds": stats["ttft_seconds"],
                "seconds": stats["seconds"],
                "tok_per_s": stats["tok_per_s"],
                "reply": stats["text"].strip()[:32],
            }
        ttft = stats["ttft_seconds"]
        _set_stage(
            "inference",
            "done",
            f"real probe · TTFT {ttft}s" if ttft is not None else "real probe OK",
        )
    except Exception as exc:  # noqa: BLE001 — surfaced as the boot error
        _set_stage("inference", "error", f"{type(exc).__name__}: {exc}")
        with _BOOT_LOCK:
            _BOOT["error"] = f"{type(exc).__name__}: {exc}"


def boot() -> None:
    """The full boot sequence (idempotent); run in a background thread."""
    with _BOOT_LOCK:
        if _BOOT["started"]:
            return
        _BOOT["started"] = True
    warm_kernels()
    warm_inference()
    with _BOOT_LOCK:
        _BOOT["ready"] = _BOOT["error"] is None


def boot_retry() -> None:
    """Re-arm the boot sequence after a failure (operator action from the UI).

    No-op when already ready. Resets the stage checklist and re-runs boot in
    a background thread; the UI timer picks the stages up on its next tick.
    """
    with _BOOT_LOCK:
        if _BOOT["ready"]:
            return
        _BOOT["started"] = False
        _BOOT["error"] = None
        for stage in _BOOT["stages"]:
            stage["state"] = "pending"
            stage["detail"] = ""
        _BOOT["probe"] = None
    threading.Thread(target=boot, daemon=True).start()


# ---------------------------------------------------------------------------
# Runtime-native (simulate tool)
# ---------------------------------------------------------------------------

_RT = None
_RT_LOCK = threading.Lock()


def _runtime():
    global _RT
    if _RT is None:
        with _RT_LOCK:
            if _RT is None:
                from algenta.mojo_runtime import MojoRuntime

                _RT = MojoRuntime(mode="local", timeout=30.0)
    return _RT


def warm_runtime() -> None:
    """Spawn the signed runtime worker before the first visitor click."""
    try:
        _runtime().execute("simulation", "mm1_simulate", [0.5, 1.0, 200])
    except Exception:  # noqa: BLE001 — the UI surfaces the real error per call
        pass


# ---------------------------------------------------------------------------
# Tool implementations (all real; each returns (result_dict, meta_dict))
# ---------------------------------------------------------------------------


def _tool_search_corpus(args: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    import bm25_mojo

    started = time.perf_counter()
    tokens = corpus.tokenize(args["query"])
    scores = corpus.mojo_index().get_scores(tokens)
    docs = corpus.docs()
    order = sorted(range(len(docs)), key=lambda i: (-float(scores[i]), i))[:5]
    latency_ms = (time.perf_counter() - started) * 1e3
    backend = bm25_mojo.backend_info()
    results = [
        {
            "rank": r + 1,
            "doc_id": docs[i]["id"],
            "topic": docs[i]["topic"],
            "title": docs[i]["title"],
            "url": docs[i].get("url", ""),
            "bm25_score": round(float(scores[i]), 4),
            "snippet": docs[i]["text"][:240],
        }
        for r, i in enumerate(order)
    ]
    meta = {
        "latency_ms": round(latency_ms, 3),
        "backend": "native Mojo kernel"
        if backend.get("native_available")
        else "pure-Python fallback (native kernel not loadable on this host — labeled, still the real bm25_mojo package)",
        "backend_info": backend,
        "query_tokens": tokens,
    }
    return {"results": results, "n_docs": len(docs), "corpus_provenance": corpus.provenance()}, meta


def _tool_score_answer(args: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    import sacrebleu
    import sacrebleu_mojo

    hyp = args["hypothesis"]
    ref = args["reference"]
    started = time.perf_counter()
    bleu = sacrebleu_mojo.corpus_bleu([hyp], [[ref]])
    chrf = sacrebleu_mojo.corpus_chrf([hyp], [[ref]])
    latency_ms = (time.perf_counter() - started) * 1e3
    oracle_bleu = sacrebleu.corpus_bleu([hyp], [[ref]])
    oracle_chrf = sacrebleu.corpus_chrf([hyp], [[ref]])
    backend = sacrebleu_mojo.backend_info()
    result = {
        "bleu": {
            "score": round(bleu.score, 4),
            "precisions": [round(p, 2) for p in bleu.precisions],
            "brevity_penalty": round(bleu.bp, 4),
            "sys_len": bleu.sys_len,
            "ref_len": bleu.ref_len,
        },
        "chrf": {"score": round(chrf.score, 4), "char_order": 6, "word_order": 0, "beta": 2},
        "oracle_crosscheck": {
            "oracle": "sacrebleu 2.5.1",
            "abs_delta_bleu": abs(bleu.score - oracle_bleu.score),
            "abs_delta_chrf": abs(chrf.score - oracle_chrf.score),
        },
    }
    meta = {
        "latency_ms": round(latency_ms, 3),
        "backend": "native Mojo kernel"
        if backend.get("native_available")
        else "pure-Python fallback (bit-exact vs oracle — labeled)",
        "backend_info": backend,
    }
    return result, meta


def _tool_simulate(args: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    lam = float(args["arrival_rate"])
    mu = float(args["service_rate"])
    n = int(args.get("n_customers", ARG_DEFAULTS["simulate"]["n_customers"]))
    started = time.perf_counter()
    envelope = _runtime().execute("simulation", "mm1_simulate", [lam, mu, n])
    latency_ms = (time.perf_counter() - started) * 1e3
    if not envelope.get("success"):
        raise RuntimeError(
            f"simulation.mm1_simulate failed: {envelope.get('error') or envelope.get('error_code')}"
        )
    raw = envelope["result"]
    # Kernel output order probed on 2026-09-20 (linux x86_64 + macOS arm64):
    # [avg_queue_wait (Wq), avg_system_time (W), server_utilization (rho)].
    # Cross-checked against M/M/1 closed forms below on every call; the
    # identity W - Wq == 1/mu holds for the kernel output.
    wq, w, rho = float(raw[0]), float(raw[1]), float(raw[2])
    stable = lam < mu
    theory = None
    if stable:
        rho_t = lam / mu
        w_t = 1.0 / (mu - lam)
        wq_t = rho_t * w_t
        theory = {
            "server_utilization": round(rho_t, 4),
            "avg_system_time": round(w_t, 4),
            "avg_queue_wait": round(wq_t, 4),
        }
    identity_residual = abs((w - wq) - 1.0 / mu)
    result = {
        "scenario": "mm1_queue",
        "module": "simulation.mm1_simulate (algenta-runtime-native, signed Mojo runtime)",
        "inputs": {"arrival_rate": lam, "service_rate": mu, "n_customers": n},
        "simulated": {
            "avg_queue_wait": round(wq, 4),
            "avg_system_time": round(w, 4),
            "server_utilization": round(rho, 4),
        },
        "queue_stable": stable,
        "mm1_closed_form": theory,
        "identity_check": {
            "identity": "W - Wq == 1/mu (holds for a work-conserving queue)",
            "residual": round(identity_residual, 6),
        },
        "note": (
            "deterministic kernel: identical inputs reproduce identical outputs "
            "(verified by repeated execution). Finite-horizon estimates differ "
            "from the closed forms by sampling noise."
        ),
    }
    meta = {
        "latency_ms": round(latency_ms, 3),
        "backend": "signed algenta-runtime-native (Mojo), in-kernel latency "
        f"{float(envelope.get('latency_ms', 0.0)):.3f} ms",
    }
    return result, meta


def _gate_preview(confidence: float, risk_p5: float) -> list[dict[str, Any]]:
    return [
        {
            "gate": "idempotency",
            "would_pass": True,
            "reason": "first execution of this decision id",
        },
        {
            "gate": "confidence",
            "would_pass": confidence >= MIN_CONFIDENCE,
            "reason": f"confidence {round(confidence, 3)} vs policy.min_confidence {MIN_CONFIDENCE}",
        },
        {
            "gate": "risk_floor",
            "would_pass": risk_p5 >= -RISK_FLOOR,
            "reason": f"risk_p5 {round(risk_p5, 3)} vs -policy.risk_floor {-RISK_FLOOR}",
        },
    ]


def _tool_recommend(
    args: dict[str, Any], state: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    action = args["action"].strip()
    confidence = float(args["confidence"])
    risk_p5 = float(args["risk_p5"])
    result = {
        "outcome": "recommended",
        "action": action,
        "confidence": round(confidence, 3),
        "risk_p5": round(risk_p5, 3),
        "policy": {"min_confidence": MIN_CONFIDENCE, "risk_floor": RISK_FLOOR},
        "gate_preview": _gate_preview(confidence, risk_p5),
        "next": "Nothing was executed or logged. Execution requires `execute_action`, which is only "
        "model-facing under the execute/full profiles.",
    }
    state["audit"].append(
        {
            "at": _now_iso(),
            "kind": "recommend",
            "action": action,
            "outcome": "recommended",
            "gate": None,
        }
    )
    meta = {
        "latency_ms": round((time.perf_counter() - started) * 1e3, 3),
        "backend": "governance policy (deterministic local code, real wire shapes)",
    }
    return result, meta


def _denial(code: str, gate: str, message: str, override_hint: str | None) -> dict[str, Any]:
    return {
        "error": {"code": code, "gate": gate, "message": message, "override_hint": override_hint}
    }


def _sign(key_hex: str, body: dict[str, Any]) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(bytes.fromhex(key_hex), payload, hashlib.sha256).hexdigest()


def _tool_execute_action(
    args: dict[str, Any],
    profile: str,
    force: bool,
    override_safety: bool,
    state: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Log the decision, run the three named policy gates, receipt or denial.

    `force` / `override_safety` are operator-only fields: they arrive from the
    UI operator controls, never from the model's tool schema (stripped).
    """
    started = time.perf_counter()
    action = args["action"].strip()
    confidence = round(float(args["confidence"]), 3)
    risk_p5 = round(float(args["risk_p5"]), 3)
    audit = state["audit"]

    # Layer 1 — integration profile interception (before the engine is called).
    if profile not in EXECUTE_PROFILES:
        body = _denial(
            "tool_not_in_profile",
            "profile",
            f"`execute_action` is not exposed under the `{profile}` profile: every algenta-* "
            "integration filters it out of the model-facing tool list and intercepts calls to it.",
            "Raise the integration profile to `execute` to allow human-approved execution.",
        )
        audit.append(
            {
                "at": _now_iso(),
                "kind": "execute_action",
                "decision_id": None,
                "outcome": "intercepted",
                "gate": "profile",
            }
        )
        meta = {
            "latency_ms": round((time.perf_counter() - started) * 1e3, 3),
            "backend": "governance profile interception",
        }
        return {"log_decision": None, "execute_action": body}, meta

    # log_decision (real state write; re-logging keeps the delivered flag).
    base = f"decision-{_slug(action)}"
    decision_id = base
    existing = state["decisions"].get(decision_id)
    if existing is not None and existing["chosen_action"] != action:
        state["seq"] += 1
        decision_id = f"{base}-{state['seq'] + 1}"
    delivered = bool(existing and existing.get("delivered", False))
    record = {
        "decision_id": decision_id,
        "chosen_action": action,
        "confidence": confidence,
        "risk_p5": risk_p5,
        "logged_at": _now_iso(),
    }
    if delivered:
        record["delivered"] = True
    state["decisions"][decision_id] = record
    logged = {
        "outcome": "logged",
        **record,
        "policy": {"min_confidence": MIN_CONFIDENCE, "risk_floor": RISK_FLOOR},
    }

    # Layer 2 — the three named, synchronous policy gates.
    gates: list[tuple[bool, str, str, str, str | None]] = [
        (
            delivered and not force,
            "execution_blocked_idempotency",
            "idempotency",
            f"Decision `{decision_id}` was already delivered.",
            "Pass force=true (operator only) to override the idempotency gate for one re-execution.",
        ),
        (
            confidence < MIN_CONFIDENCE and not override_safety,
            "execution_blocked_confidence",
            "confidence",
            f"Decision confidence {confidence} is below policy.min_confidence {MIN_CONFIDENCE}.",
            "Pass override_safety=true (operator only) to bypass the confidence gate.",
        ),
        (
            risk_p5 < -RISK_FLOOR and not override_safety,
            "execution_blocked_risk_floor",
            "risk_floor",
            f"risk_p5 {risk_p5} is below -policy.risk_floor ({-RISK_FLOOR}).",
            "Pass override_safety=true (operator only) to bypass the risk floor gate.",
        ),
    ]
    for blocked, code, gate, message, hint in gates:
        if blocked:
            body = _denial(code, gate, message, hint)
            audit.append(
                {
                    "at": _now_iso(),
                    "kind": "execute_action",
                    "decision_id": decision_id,
                    "outcome": "denied",
                    "gate": gate,
                }
            )
            meta = {
                "latency_ms": round((time.perf_counter() - started) * 1e3, 3),
                "backend": "governance policy gates (synchronous)",
            }
            return {"log_decision": logged, "execute_action": body}, meta

    state["decisions"][decision_id]["delivered"] = True
    receipt_body = {
        "decision_id": decision_id,
        "chosen_action": action,
        "confidence": confidence,
        "risk_p5": risk_p5,
        "execution_status": "delivered",
        "response_code": 200,
        "executed_at": _now_iso(),
        "policy_snapshot_id": POLICY_SNAPSHOT_ID,
        "schema_snapshot_id": SCHEMA_SNAPSHOT_ID,
        "manifest_version": MANIFEST_VERSION,
        "payload_summary": {"chosen_action": action},
        "safety_overridden": bool(override_safety),
        "signature_scheme": "HMAC-SHA256 over canonical JSON, ephemeral per-session key",
        "signature_key_id": "ephemeral-session",
    }
    receipt = {**receipt_body, "signature": _sign(state["hmac_key"], receipt_body)}
    audit.append(
        {
            "at": _now_iso(),
            "kind": "execute_action",
            "decision_id": decision_id,
            "outcome": "delivered",
            "gate": None,
            "signature": receipt["signature"],
        }
    )
    meta = {
        "latency_ms": round((time.perf_counter() - started) * 1e3, 3),
        "backend": "governance policy gates (synchronous) + HMAC-signed receipt",
    }
    return {"log_decision": logged, "execute_action": receipt}, meta


def execute_tool(
    name: str,
    args: dict[str, Any],
    profile: str,
    force: bool,
    override_safety: bool,
    state: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if name == "search_corpus":
        return _tool_search_corpus(args)
    if name == "score_answer":
        return _tool_score_answer(args)
    if name == "simulate":
        return _tool_simulate(args)
    if name == "recommend":
        return _tool_recommend(args, state)
    if name == "execute_action":
        return _tool_execute_action(args, profile, force, override_safety, state)
    raise ValueError(f"unknown tool {name!r}")


def _outcome_line(tool: str, result: dict[str, Any]) -> str:
    """Deterministic one-line verdict derived from the REAL tool result."""
    if tool == "recommend":
        failed = [g["gate"] for g in result.get("gate_preview", []) if not g["would_pass"]]
        return "RECOMMENDED only — nothing was executed or logged. " + (
            f"Gate preview: would FAIL gate(s): {', '.join(failed)}."
            if failed
            else "Gate preview: would pass all gates."
        )
    if tool == "execute_action":
        body = result.get("execute_action", {})
        if result.get("log_decision") is None:
            return (
                "INTERCEPTED at the profile layer — the call never reached the engine; "
                "nothing was logged or executed."
            )
        if "error" in body:
            err = body["error"]
            return (
                f"DENIED at policy gate `{err['gate']}` (code {err['code']}) — "
                "no execution happened."
            )
        return (
            "APPROVED — all policy gates passed; execution_status=delivered; "
            "the receipt is HMAC-signed."
        )
    return "OK — the real result is below."


# ---------------------------------------------------------------------------
# Agent loop — tool selection (JSON mode + robust parse + one retry), real
# tool execution, streamed answer composition. Every step is returned/shown.
# ---------------------------------------------------------------------------


def _capabilities_text(profile: str) -> str:
    """The exact tool/scenario catalog for a profile — shared verbatim by the
    selection prompt and the abstain-composition prompt so the model and the
    decline writer describe the same reality."""
    lines = []
    for name in profile_tools(profile):
        schema = TOOL_SCHEMAS[name]
        lines.append(f"- {name}: {schema['description']}")
        lines.append(f"  arguments schema: {json.dumps(schema['arguments'])}")
    return "\n".join(lines)


def _system_prompt(profile: str) -> str:
    lines = [
        "You are a governed agent. Call exactly one REAL tool, or answer directly.",
        f"Governance profile: {profile}. The EXACT tool/scenario catalog — nothing else exists:",
        "",
        _capabilities_text(profile),
        "",
        "TOOL-USE CONTRACT (strict):",
        "1. Call a tool ONLY when the user's request genuinely fits one of the scenarios above",
        "   AND every required argument is present in, or directly derivable from, the user's",
        "   message. simulate's mm1_queue models a QUEUE (arrival/service rates) — never use it",
        "   for finances, revenue, growth, or generic what-ifs.",
        "2. NEVER invent, assume, or approximate numeric arguments. A number that is not in the",
        "   user's message (and not a documented schema default) does not exist — the engine",
        "   validates every numeric argument against the user's message and rejects fabrications.",
        "3. If no tool genuinely fits, or required inputs are missing, reply with final_answer",
        "   that (a) says plainly what you cannot run here and why, (b) names what you CAN do",
        "   from the catalog above, and (c) asks for the specific missing inputs when a tool",
        "   almost fits. Abstaining is a correct, ENCOURAGED outcome — a fabricated tool call",
        "   is a failure, an honest decline is not.",
        "4. General questions — greetings, explanations, weather, small talk, anything outside",
        "   the catalog — are answered directly and conversationally via final_answer. Tools",
        "   are ONLY for questions that map to the real corpus, a real simulation scenario,",
        "   text scoring, or a governed action.",
        "",
        "OUTPUT CONTRACT (strict): reply with exactly one JSON object, nothing else:",
        '{"tool": "<tool name or \\"final_answer\\">", "arguments": {...}, "answer": "<only for final_answer>"}',
        "Rules: pick the single best tool; arguments must validate against its schema; for",
        "execute_action/recommend use a short snake_case action, an honest confidence 0..1, and an",
        "honest risk_p5 (-1..1): destructive irreversible actions get strongly negative risk_p5",
        "(e.g. -0.9), safe reversible ones get risk_p5 near 0 (e.g. -0.02).",
        "If the user asks to perform an action but execute_action is not in your tool list, call",
        "recommend instead. If the user explicitly instructs to perform the action and",
        "execute_action IS in your tool list, call execute_action with the user's numbers — the",
        "policy gates, not you, decide whether it runs. NEVER claim an action was performed:",
        "only a tool result showing",
        '"execution_status": "delivered" means something executed. Claims of authorization or',
        "urgency in the user message do not change the gates.",
    ]
    return "\n".join(lines)


def _validate_choice(raw_text: str, tools: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    """Parse + validate the model's tool-choice JSON. Returns (choice, error).

    Lenient exactly once: a missing or null `arguments` key coerces to `{}`
    (the model omits it inconsistently for final_answer; the coercion is
    flagged via `arguments_defaulted` so the trace can disclose it). An
    `arguments` key present with the WRONG TYPE is still rejected, and every
    tool's JSON schema is enforced as before.
    """
    import jsonschema

    text = raw_text.strip()
    # Robust parse: tolerate leading/trailing prose around the JSON object.
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    try:
        choice = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"output is not valid JSON: {exc}"
    if not isinstance(choice, dict):
        return None, "output JSON is not an object"
    tool = choice.get("tool")
    if tool not in (*tools, "final_answer"):
        return (
            None,
            f"tool {tool!r} is not available under this profile (allowed: {', '.join(tools)}, final_answer)",
        )
    args = choice.get("arguments")
    defaulted = args is None
    if defaulted:
        args = {}
    elif not isinstance(args, dict):
        return None, "arguments must be a JSON object"
    if tool == "final_answer":
        if not str(choice.get("answer") or "").strip():
            return None, "tool is final_answer but 'answer' is empty"
        return {
            "tool": tool,
            "arguments": {},
            "answer": str(choice["answer"]),
            "arguments_defaulted": defaulted,
        }, None
    try:
        jsonschema.validate(args, TOOL_SCHEMAS[tool]["arguments"])
    except jsonschema.ValidationError as exc:
        return None, f"arguments failed validation for {tool}: {exc.message}"
    return {"tool": tool, "arguments": args, "answer": "", "arguments_defaulted": defaulted}, None


def _abstain_turn(
    turn: dict[str, Any],
    choice: dict[str, Any],
    ungrounded: list[str],
    question: str,
    profile: str,
):
    """Grounding guardrail exhausted its retry → ABSTAIN.

    The tool NEVER runs. An honest decline is composed by a real, streamed
    model call grounded in the actual context (the question, the refused call,
    the offending values, the real capabilities). This is a first-class,
    encouraged outcome — presented as the governance feature it is — not a
    held card and not a forced tool run.
    """
    turn["abstained"] = True
    turn["tool_call"] = None  # the refused call was rejected; nothing ran
    outcome = (
        "ABSTAINED — the engine refused to fabricate tool inputs "
        f"({', '.join(ungrounded)} not in the user's message and no documented default). "
        "No tool was run."
    )
    turn["outcome"] = outcome
    decline_messages = [
        {
            "role": "system",
            "content": (
                "You are the decline writer for a governed agent. The agent just REFUSED to "
                "run a tool because its numeric arguments would have been fabricated — they "
                "are not in the user's message and have no documented default. Write the "
                "user-facing decline: plain, helpful prose, at most 90 words, no JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User's question: {question}\n"
                f"Refused tool call: {json.dumps({'tool': choice['tool'], 'arguments': choice['arguments']})}\n"
                f"Un-grounded values: {', '.join(ungrounded)}\n"
                f"The agent's real capabilities (nothing else exists):\n{_capabilities_text(profile)}\n\n"
                "Write the decline: (1) say plainly that this cannot be run for real here "
                "because the inputs would have to be invented, and the engine never "
                "fabricates inputs; (2) name what CAN be done from the capabilities list; "
                "(3) ask for the specific inputs that would make the request runnable, if "
                "any capability almost fits."
            ),
        },
    ]
    step_name = "abstain composition (honest decline)"
    yield {"type": "step_start", "step": step_name, "kind": "model_call"}
    try:
        stats = None
        for item in _chat_stream(
            decline_messages, json_mode=False, max_tokens=GEN_MAX_TOKENS_ANSWER
        ):
            if "token" in item:
                yield {"type": "token", "step": step_name, "text": item["token"]}
            else:
                stats = item["stats"]
        assert stats is not None
        final = stats
    except Exception as exc:  # noqa: BLE001 — same honesty rule as composition failures
        turn["held"] = True
        turn["error"] = f"abstain composition failed: {type(exc).__name__}: {exc}"
        record = {"step": step_name, "error": turn["error"]}
        turn["steps"].append(record)
        yield {"type": "step_end", "record": record}
        yield {"type": "done", "turn": turn}
        return
    turn["answer"] = final["text"].strip()
    record = {
        "step": step_name,
        "kind": "model_call",
        "seconds": final["seconds"],
        "ttft_seconds": final["ttft_seconds"],
        "prompt_tokens": final["prompt_tokens"],
        "completion_tokens": final["completion_tokens"],
        "tok_per_s": final["tok_per_s"],
    }
    turn["steps"].append(record)
    yield {"type": "step_end", "record": record}
    yield {"type": "done", "turn": turn}


def agent_turn_events(
    question: str,
    profile: str,
    force: bool,
    override_safety: bool,
    state: dict[str, Any] | None,
):
    """One governed agent turn as a stream of REAL events (generator).

    Emits dicts in order:
      {"type": "step_start", "step": name, "kind": "model_call"}
      {"type": "token", "step": name, "text": delta}   — real provider deltas
      {"type": "step_end", "record": <the step dict appended to turn.steps>}
      {"type": "tool_start", "tool": name, "arguments": args}
      {"type": "tool_end", "record": <the step dict appended to turn.steps>}
      {"type": "done", "turn": <the completed turn dict>}

    Exactly one "done" is always emitted last. Nothing is canned: every token
    event is a live provider-generated delta, and a provider/transport failure
    ends the turn held=True with the real error — never a fallback answer.
    """
    state = _ensure_state(state)
    turn: dict[str, Any] = {
        "question": question,
        "profile": profile,
        "steps": [],
        "tool_call": None,
        "tool_result": None,
        "tool_meta": None,
        "governance": None,
        "answer": None,
        "held": False,
        "abstained": False,
    }
    question = (question or "").strip()
    if not question:
        turn["held"] = True
        turn["error"] = "empty question"
        yield {"type": "done", "turn": turn}
        return
    if profile not in PROFILE_DESCRIPTIONS:
        turn["held"] = True
        turn["error"] = f"unknown profile {profile!r}"
        yield {"type": "done", "turn": turn}
        return

    tools = profile_tools(profile)
    sys_prompt = _system_prompt(profile)
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": question},
    ]

    # ---- step 1: model selects a tool (JSON mode + robust parse + retry) ---
    # Every failure is classified: "schema" (parse/validation — held after one
    # retry) or "grounding" (fabricated numeric arguments — abstain after one
    # retry). The grounding guardrail is the governance feature: the engine
    # refuses to run fabricated inputs.
    choice = None
    last_failure_kind: str | None = None
    last_ungrounded: list[str] = []
    grounded_default_notes: list[str] = []
    for attempt in (1, 2):
        step_name = f"tool selection attempt {attempt}"
        yield {"type": "step_start", "step": step_name, "kind": "model_call"}
        try:
            stats = None
            for item in _chat_stream(messages, json_mode=True, max_tokens=GEN_MAX_TOKENS_CHOICE):
                if "token" in item:
                    yield {"type": "token", "step": step_name, "text": item["token"]}
                else:
                    stats = item["stats"]
            assert stats is not None
            call = stats
        except Exception as exc:  # noqa: BLE001
            turn["held"] = True
            turn["error"] = f"model call failed: {type(exc).__name__}: {exc}"
            record = {"step": step_name, "error": turn["error"]}
            turn["steps"].append(record)
            yield {"type": "step_end", "record": record}
            yield {"type": "done", "turn": turn}
            return
        choice, err = _validate_choice(call["text"], tools)
        failure_kind = "schema" if err else None
        ungrounded: list[str] = []
        if err is None and choice["tool"] != "final_answer":
            ungrounded, _defaulted_notes = _grounding_check(
                choice["tool"], choice["arguments"], question
            )
            if ungrounded:
                failure_kind = "grounding"
                err = (
                    f"arguments not grounded in the user's message: {', '.join(ungrounded)}. "
                    "Arguments must come from the user's message (or a documented schema "
                    "default); if the request doesn't fit a real scenario, use final_answer "
                    "and say so — never invent numbers."
                )
            else:
                grounded_default_notes = _defaulted_notes
        record = {
            "step": step_name,
            "kind": "model_call",
            "seconds": call["seconds"],
            "ttft_seconds": call["ttft_seconds"],
            "prompt_tokens": call["prompt_tokens"],
            "completion_tokens": call["completion_tokens"],
            "tok_per_s": call["tok_per_s"],
            "raw_output": call["text"],
            "valid": err is None,
        }
        if err:
            record["validation_error"] = err
            if failure_kind == "grounding":
                record["guardrail"] = ungrounded
        elif choice.get("arguments_defaulted"):
            # honest audit trail: the model omitted the arguments key
            record["arguments_defaulted"] = True
        turn["steps"].append(record)
        yield {"type": "step_end", "record": record}
        if err is None:
            break
        last_failure_kind = failure_kind
        last_ungrounded = ungrounded
        if attempt == 1:
            # one retry with the failure fed back to the model, spelling out
            # the exact contract (greedy decoding otherwise reproduces the
            # identical invalid shape)
            messages.append({"role": "assistant", "content": call["text"]})
            if failure_kind == "grounding":
                feedback = (
                    f"GROUNDING ERROR: {err} Reply again with exactly one JSON object "
                    "following the output contract — either call the tool with arguments "
                    "taken from the user's message, or answer via final_answer explaining "
                    "what you cannot run and what inputs would be needed."
                )
            else:
                feedback = (
                    f"VALIDATION ERROR: {err}. Reply again with exactly one corrected "
                    "JSON object following the output contract: "
                    '{"tool": "<tool name or \\"final_answer\\">", "arguments": {...}, '
                    '"answer": "<only for final_answer>"} — always include the '
                    '"arguments" key; use "arguments": {} when no arguments are needed.'
                )
            messages.append({"role": "user", "content": feedback})
        else:
            if last_failure_kind == "grounding":
                # Still un-grounded after feedback: ABSTAIN — compose an honest
                # decline. Not a held card, and the tool never runs.
                yield from _abstain_turn(turn, choice, last_ungrounded, question, profile)
                return
            turn["held"] = True
            turn["error"] = f"tool selection failed after retry: {err}"
            yield {"type": "done", "turn": turn}
            return

    assert choice is not None
    tool = choice["tool"]

    # ---- step 2a: direct answer (no tool) ----------------------------------
    if tool == "final_answer":
        turn["tool_call"] = {"tool": tool, "arguments": choice["arguments"]}
        turn["answer"] = choice["answer"]
        record = {"step": "final answer (model chose no tool)", "kind": "note"}
        turn["steps"].append(record)
        yield {"type": "step_end", "record": record}
        yield {"type": "done", "turn": turn}
        return

    # ---- step 2b: real tool execution --------------------------------------
    # Fill documented defaults for omitted arguments (disclosed as defaulted),
    # plus any explicit values that passed the guard only via the default rule.
    completed_args, default_notes = _apply_defaults(tool, choice["arguments"])
    default_notes = grounded_default_notes + default_notes
    turn["tool_call"] = {"tool": tool, "arguments": completed_args}
    yield {"type": "tool_start", "tool": tool, "arguments": completed_args}
    try:
        result, meta = execute_tool(tool, completed_args, profile, force, override_safety, state)
    except Exception as exc:  # noqa: BLE001
        turn["held"] = True
        turn["error"] = f"tool {tool} failed: {type(exc).__name__}: {exc}"
        record = {"step": f"tool execution: {tool}", "error": turn["error"]}
        turn["steps"].append(record)
        yield {"type": "tool_end", "record": record}
        yield {"type": "done", "turn": turn}
        return
    if default_notes:
        # the composer and the UI both see exactly which inputs were defaulted
        result = {**result, "defaults_applied": default_notes}
        meta = {**meta, "defaults_applied": default_notes}
    turn["tool_result"] = result
    turn["tool_meta"] = meta
    record = {
        "step": f"tool execution: {tool}",
        "kind": "tool_call",
        "latency_ms": meta.get("latency_ms"),
        "backend": meta.get("backend"),
    }
    if default_notes:
        record["defaults_applied"] = default_notes
    turn["steps"].append(record)
    yield {"type": "tool_end", "record": record}
    if tool in ("recommend", "execute_action"):
        turn["governance"] = result

    # ---- step 3: model composes the final answer over the real result ------
    # The deterministic outcome line is computed from the real result (not by
    # the model) and anchors the composition — the model can otherwise flip
    # denials into claimed successes.
    outcome_line = _outcome_line(tool, result)
    turn["outcome"] = outcome_line
    # Compact the result for the composition prompt (fewer prompt tokens),
    # while the full result stays visible in the UI panel.
    compact = result
    if tool == "search_corpus":
        compact = {
            "results": [
                {
                    k: r[k]
                    for k in ("rank", "doc_id", "topic", "title", "url", "bm25_score", "snippet")
                }
                for r in result["results"][:3]
            ],
            "n_docs": result["n_docs"],
        }
    compose_messages = [
        {
            "role": "system",
            "content": (
                "You are the answer writer for a governed agent. The tool call and its "
                "real execution already happened. Write the final user-facing answer "
                "grounded ONLY in the tool result the user provides: cite concrete "
                "numbers and document ids that appear in it, never invent facts, and "
                "never claim an action executed unless the result shows "
                '"execution_status": "delivered". Plain prose, at most 100 words, no JSON.'
            ),
        },
        {"role": "user", "content": question},
        {
            "role": "assistant",
            "content": json.dumps({"tool": tool, "arguments": choice["arguments"], "answer": ""}),
        },
        {
            "role": "user",
            "content": (
                f"The tool {tool} executed FOR REAL.\n"
                f"OUTCOME (deterministic ground truth — do not contradict it): {outcome_line}\n"
                f"Result JSON:\n{json.dumps(compact, indent=2)}\n\n"
                "Now answer the user's original question in at most 100 words, consistent with "
                "the OUTCOME line. Ground every claim in the result JSON — cite concrete "
                "numbers, and for retrieval cite the passage doc ids, titles and URLs, using "
                "ONLY facts that appear in the result JSON. For a denial, name the gate and "
                "why it fired. "
                "If the result genuinely cannot address the user's question (wrong scenario "
                "or unrelated data), say so honestly and name what would be needed instead — "
                "never present an unrelated result as the answer. "
                "Do not repeat the JSON. Do not invent facts."
            ),
        },
    ]
    step_name = "answer composition"
    yield {"type": "step_start", "step": step_name, "kind": "model_call"}
    try:
        stats = None
        for item in _chat_stream(
            compose_messages, json_mode=False, max_tokens=GEN_MAX_TOKENS_ANSWER
        ):
            if "token" in item:
                yield {"type": "token", "step": step_name, "text": item["token"]}
            else:
                stats = item["stats"]
        assert stats is not None
        final = stats
    except Exception as exc:  # noqa: BLE001
        turn["held"] = True
        turn["error"] = f"answer composition failed: {type(exc).__name__}: {exc}"
        record = {"step": step_name, "error": turn["error"]}
        turn["steps"].append(record)
        yield {"type": "step_end", "record": record}
        yield {"type": "done", "turn": turn}
        return
    turn["answer"] = final["text"].strip()
    record = {
        "step": step_name,
        "kind": "model_call",
        "seconds": final["seconds"],
        "ttft_seconds": final["ttft_seconds"],
        "prompt_tokens": final["prompt_tokens"],
        "completion_tokens": final["completion_tokens"],
        "tok_per_s": final["tok_per_s"],
    }
    turn["steps"].append(record)
    yield {"type": "step_end", "record": record}
    yield {"type": "done", "turn": turn}


def agent_turn(
    question: str,
    profile: str,
    force: bool,
    override_safety: bool,
    state: dict[str, Any] | None,
) -> dict[str, Any]:
    """One full agent turn. Never raises; every step is in the returned dict.

    Same contract as before — a thin blocking wrapper over
    `agent_turn_events` for tests and non-streaming callers.
    """
    turn: dict[str, Any] | None = None
    for event in agent_turn_events(question, profile, force, override_safety, state):
        if event["type"] == "done":
            turn = event["turn"]
    assert turn is not None  # the generator always emits exactly one done
    return turn


# ---------------------------------------------------------------------------
# Rendering helpers (UI + API share these)
# ---------------------------------------------------------------------------


def render_trace(turn: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"**question** — {turn.get('question', '')}")
    lines.append(f"**profile** — `{turn.get('profile')}`")
    lines.append(f"**inference** — {MODEL_LABEL} · governance, kernels and receipts local")
    for step in turn.get("steps", []):
        name = step.get("step", "step")
        if step.get("kind") == "model_call":
            if "valid" in step:
                status = (
                    "valid JSON" if step["valid"] else "INVALID — retrying with the error fed back"
                )
                status = f" · {status}"
            else:
                status = ""
            ttft = step.get("ttft_seconds")
            ttft_part = f"TTFT {ttft}s · " if ttft is not None else ""
            if step.get("completion_tokens"):
                speed = (
                    f"streamed {step['completion_tokens']} tok · {ttft_part}"
                    f"**{step['tok_per_s']} tok/s** decode · {step['seconds']}s total "
                    f"(prompt {step['prompt_tokens']} tok){status}"
                )
            else:
                speed = (
                    f"streamed · {step['seconds']}s (provider returned no usage counters){status}"
                )
            lines.append(f"**{name}** — model call · {speed}")
            raw = (step.get("raw_output") or "").strip()
            if raw:
                lines.append(f"```json\n{raw[:800]}\n```")
            if step.get("arguments_defaulted"):
                lines.append(
                    "arguments: {} (defaulted) — the model omitted the `arguments` key; "
                    "coerced to an empty object and disclosed here"
                )
            if step.get("guardrail"):
                lines.append(
                    f"**guardrail fired** — the engine refuses to fabricate inputs: "
                    f"`{', '.join(step['guardrail'])}` not in your message and no documented "
                    "default. A fabricated tool call is a failure; an honest decline is not."
                )
            if step.get("validation_error") and not step.get("guardrail"):
                lines.append(
                    f"validation error fed back to the model: `{step['validation_error']}`"
                )
            elif step.get("validation_error"):
                lines.append(f"grounding error fed back to the model: `{step['validation_error']}`")
        elif step.get("kind") == "tool_call":
            lines.append(
                f"**{name}** — executed for real in **{step.get('latency_ms')} ms** · {step.get('backend')}"
            )
            if step.get("defaults_applied"):
                lines.append("defaults applied — " + "; ".join(step["defaults_applied"]))
        elif step.get("kind") == "note":
            lines.append(f"**{name}**")
        if step.get("error"):
            lines.append(f"error: `{step['error']}`")
    if turn.get("outcome") and turn.get("governance"):
        cls = (
            "verdict-ok"
            if turn["outcome"].startswith("APPROVED")
            else "verdict-bad"
            if ("DENIED" in turn["outcome"] or "INTERCEPTED" in turn["outcome"])
            else "verdict-warn"
        )
        lines.append(f"**governance verdict** — <span class='{cls}'>{turn['outcome']}</span>")
    if turn.get("abstained"):
        lines.append(
            f"**guardrail verdict** — <span class='verdict-warn'>{turn.get('outcome', 'ABSTAINED')}</span>"
        )
    if turn.get("held"):
        lines.append(f"**TURN HELD** — {turn.get('error')}")
    return "\n\n".join(lines)


def verify_snippet() -> str:
    return (
        "import hmac, hashlib, json\n"
        "key = bytes.fromhex(SESSION_KEY)          # shown above, per-session ephemeral\n"
        "body = {k: v for k, v in receipt.items() if k != 'signature'}\n"
        "payload = json.dumps(body, sort_keys=True, separators=(',', ':')).encode()\n"
        "assert hmac.new(key, payload, hashlib.sha256).hexdigest() == receipt['signature']"
    )
