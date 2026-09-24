"""LLM kernels — RMSNorm, RoPE and sampling from the `algenta-llm` Hub kernel against torch.

Three panels, one shape each, chosen by sliders inside the contract's count
relations (`x` holds `n_rows × n_cols`, `pos` holds `n_tok`, `logits` holds
`n`). Every run is two measured lanes over the same seeded inputs:

* the Hub kernel (`normk.rmsnorm.rmsnorm_fwd_flat`, `attnk.rope.rope_table` +
  `rope_apply_flat`, `llmk.generate.greedy_argmax_flat`), one warm-up then
  `REPEATS` calls through the one native lane — the time includes JSON
  marshalling across the C ABI, as every Hub-kernel time on this Space does;
* torch on the CPU, float64, the same number of calls. torch is C-backed, so
  the card is a parity check: the product is the parity chip (max |Δ|
  against a stated tolerance) with the kernel's and torch's provenance —
  no ratio, no bars, and (round 9, rulebook rule 6) no latency pair: at
  these shapes the call is JSON transport around a microsecond kernel. The kernel lane is
  split once more: the Python side of
  the transport (`json.dumps` of the request envelope the wrapper sends,
  `json.loads` of a reply of the same shape — exactly what the kernel's
  `_native.execute` does) is measured on the same payload and shown beside
  the remainder, which is the library call with its own JSON parse and
  result encode. Nothing here is estimated.

Each panel is one stack: its controls two to a row, the Run button under them (its own
width, left), then the result card across the panel's full width and the Reproduce
disclosure — so a tall result never leaves a void beside a short set of sliders,
in any state (round 3 measured 469 px under the RMSNorm controls after a run). Every
number box follows the fleet's refusal convention (Try, the Playground): it stands in its
own column with one reserved caption line under it (the message slot), a shape the form
refuses puts its sentence there — naming the box and its range, `Rows: 1 to 32` — the
status row under Run (a reserved caption line, `common.STATUS_SLOT_CLASS`) reads `Not run ·
fix the marked field`, and nothing else on the panel changes: the card and the Reproduce
snippet stay as they were (round 10: Rows 50 was told by the quiet card alone while the box
that caused it carried no word; round 11: the refusal emptied the snippet and moved the
panels below). The module's own `run_*` functions still answer the quiet `invalid_shape`
card with the sentence for a refused shape. Editing a box clears the slots and the echo. The
two-column tabs (Governed, Ecosystem) share `STRETCH_CLASS` from this module's
`STATE_CSS` instead: the row is `equal_height`, the block grows to the column and
the card's footer sits on the bottom edge.

The RoPE reference is written in torch directly (the rotate-half and the
interleaved pair forms, the `theta ** (-2i / head_dim)` frequencies), not
imported from transformers: that keeps a 500 MB dependency out of the image
and the reference readable in the Reproduce accordion. The sampling panel
times the batched greedy argmax and, alongside, runs the per-candidate
temperature / top-k / top-p formulas of `llm_sampling` over the top-k
candidates and checks the kept set against the transformers warper order
(temperature → top-k → top-p) implemented in torch.

Every handler answers at once with the loading card and then with the result,
so the page never shows Gradio's progress chrome (`show_progress="hidden"`);
before the first run each result column carries the empty card shaped like the
parity card a run paints (`render_empty`: one sentence, one provenance line, no
lane rows) — or, when the family did not load in this container, the
quiet card with that code, so a visitor knows before pressing anything. Every
Reproduce editor opens prefilled with the snippet for the default shape. The
three panels are peers, and each panel's Run is the primary action of its own
card (`RUN_VARIANT`, the gradient primary every other tab's Run wears — round 12:
three grey 240 px secondaries beside five primary Runs read as a different
control); each panel is the one stack described above (controls two to a row,
`CONTROL_MIN_WIDTH` each and one under the other on a phone, Run across the
panel, then the full-width card), so no column ever ends hundreds of pixels
above the card beside it.
The lane label on the card is `races.revision_label` — the family at the Hub
snapshot the module was imported from, never the capped sha when the cache
holds a later revision. The GPU stage tile (`gpu_status`) sits below the three
panels only where the stage is configured (`gpu_status.configured`); nothing is
polled and no tile is drawn otherwise. Nothing here imports gradio at module
level; `render` receives the module.

This module also holds what the four tabs of this milestone share on top of the
shared cards module: `render_empty_card` (`cards.empty` plus the rows a result
fills), `render_loading_card` (`cards.loading`), `render_quiet_card` and
`quiet_code_chip` (a documented state — not configured, not loaded, not fetched
— in neutral colour with the code the verifier reads), the 44 px Copy chip and
the responsive `alg-stack-table` rules in `STATE_CSS`, so every tab shows one
loading card, one empty card, one quiet card and one table shape. Primary copy
carries no identifiers: repository ids, build variants and revisions live in
chips, mono values and the Reproduce editors.
"""

from __future__ import annotations

import json
import logging
import math
import random
import statistics
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from algenta_spaces import bench, cards, hubkernel, playground
from algenta_spaces.css import block, rule, stylesheet
from algenta_spaces.hubkernel import HubKernelError, LoadedKernel
from algenta_spaces.lane import LaneError
from algenta_spaces.limits import key_from_request
from algenta_spaces.runtime import pinned_versions, utc_stamp
from algenta_spaces.shell import check_copy

import gpu_status
from races import kernel_revision, revision_label

from . import LOAD_HOOKS, NATIVE_LIMIT_KIND, TAB_LLM, Deps, TabSpec, common

log = logging.getLogger(__name__)

LABEL = "LLM kernels"
FAMILY = "llm"
API_RMSNORM = "llm_run"
API_ROPE = "llm_rope"
API_SAMPLING = "llm_sampling"
API_NAMES: tuple[str, ...] = (API_RMSNORM, API_ROPE, API_SAMPLING)

MODULE_RMSNORM = "normk.rmsnorm"
FN_RMSNORM = "rmsnorm_fwd_flat"
MODULE_ROPE = "attnk.rope"
FN_ROPE_TABLE = "rope_table"
FN_ROPE_APPLY = "rope_apply_flat"
MODULE_GENERATE = "llmk.generate"
FN_GREEDY = "greedy_argmax_flat"
MODULE_SAMPLING = "llm_sampling"
FN_TEMPERATURE = "temperature_scale"
FN_TOP_K = "top_k_threshold"
FN_TOP_P = "top_p_cumulative"

SEED = 20260922
REPEATS = 5
WARMUPS = 1
BUDGET_S = 20.0
EPS = 1e-6
THETA = 10000.0
TOL_RMSNORM = 1e-9
TOL_ROPE = 1e-8  # the kernel's cos/sin drift ~2e-11 per radian; 1.3e-9 measured at 64 tokens
FEATURE = "kernels"
TORCH = "torch"
#: Three peer panels, one hierarchy: every Run button is the primary button of its own card, as
#: on every other tab (round 12).
RUN_VARIANT = "primary"
#: A control column in a two-up row: two fit beside a card on the desktop, one per row on a
#: phone (Gradio stacks a column narrower than this).
CONTROL_MIN_WIDTH = 240
#: The width below which a two-column tab sharing this module's stretch stacks its columns.
COLUMN_MIN_WIDTH = 280
#: The shared two-column stretch (Governed, Ecosystem): the `gr.HTML` block carrying this class
#: grows to its column, the card inside fills it and the card's footer sits on the bottom edge.
STRETCH_CLASS = "alg-stretch"
#: The column that block sits in: with `gr.Row(equal_height=True)` Gradio grows every block of
#: the shorter column alike; this class lets the stretch block alone take the slack, so a
#: disclosure under the card keeps its 48 px.
STRETCH_COL_CLASS = "alg-stretch-col"
#: The shared responsive table's denser phone variant (Ecosystem): one row card per row, the
#: lead cell on its own line and the other cells inline after it, no labels — every value in
#: such a table says what it is (`1,234 functions · 12 modules`, `v1 · 92ef06d · pinned`).
STACK_DENSE_CLASS = "alg-stack-dense"
#: What a screen reader hears for an empty result row before a run.
PENDING_TEXT = "not measured yet"
#: The request envelope `_transport.call` sends through `_native.execute` (mirrored as data).
ENVELOPE_TYPE = "library_execute"

# (min, max, step, default) for every slider — the contract's count relations bound the lists
# (`x` = rows × cols, `x` = tokens × heads × head_dim, `logits` = vocab) under the playground's
# 200k-element budget; the top of each range measured 0.1–0.6 s per call on an M-series Mac.
ROWS = (1, 32, 1, 8)
COLS = (64, 1024, 64, 256)
TOKENS = (1, 64, 1, 16)
HEADS = (1, 8, 1, 4)
#: RoPE rotates pairs of dimensions: the field's own step is the kernel's real constraint (even),
#: so a typed value off the step is refused for the reason that holds (round 5: 63 read as
#: `dimension_too_large`, the frozen kernel's one status for odd, too wide and too long).
HEAD_DIM = (16, 128, 2, 64)
VOCAB = (256, 32768, 256, 4096)
TEMPERATURE = (0.1, 2.0, 0.05, 0.8)
TOP_K = (1, 100, 1, 40)
TOP_P = (0.5, 1.0, 0.01, 0.95)

# The same codes and hints the Try, Playground and Races tabs print (tabs/common.py).
CODE_NO_KERNEL = common.CODE_NO_KERNEL
CODE_PAUSED = common.CODE_SWITCHED_OFF
CODE_LIMITED = common.CODE_LIMITED
CODE_BAD_SHAPE = "invalid_shape"
#: The visitor-facing name of each shape argument, said in front of a refusal.
SHAPE_LABELS: Mapping[str, str] = {
    "rows": "Rows",
    "cols": "Columns",
    "tokens": "Tokens",
    "heads": "Heads",
    "head_dim": "Head dimension",
    "vocab": "Vocabulary",
    "temperature": "Temperature",
    "top_k": "Top-k",
    "top_p": "Top-p",
}
#: The fields of each panel, in the order their boxes stand (the message slots follow it).
PANEL_FIELDS: Mapping[str, tuple[str, ...]] = {
    "rmsnorm": ("rows", "cols"),
    "rope": ("tokens", "heads", "head_dim"),
    "sampling": ("vocab", "temperature", "top_k", "top_p"),
}
HINT_HEAD_DIM_ODD = (
    f"Head dimension: an even number, {HEAD_DIM[0]} to {HEAD_DIM[1]} —"
    " RoPE rotates pairs of dimensions"
)
#: The frozen kernel answers one status for three conditions; the card says all three.
STATUS_HINTS: Mapping[tuple[str, str], str] = {
    (MODULE_ROPE, "dimension_too_large"): (
        "RoPE needs an even head dimension of at most 1,024 and at most 1,048,576 positions;"
        " the kernel reports one status for all three"
    ),
}
CODE_NO_TORCH = "torch_not_installed"
HINT_NO_KERNEL = common.NO_KERNEL_HINT
HINT_PAUSED = common.SWITCHED_OFF_HINT
HINT_NO_TORCH = "torch is not installed here, so there is no reference to compare against."
#: Documented states render the quiet card; every other failure during a run is the red one.
QUIET_CODES: frozenset[str] = frozenset({CODE_NO_KERNEL, CODE_PAUSED})

TITLE_RMSNORM = "RMSNorm"
TITLE_ROPE = "RoPE"
TITLE_SAMPLING = "Sampling"
RUN_RMSNORM = "Run RMSNorm"
RUN_ROPE = "Run RoPE"
RUN_SAMPLING = "Run sampling"
HOW_TITLE = "How this is measured"
REPRODUCE_TITLE = "Reproduce"
SNIPPET_LABEL = "kernels + torch"
NOT_A_RACE = cards.NOT_A_RACE_TEXT
LANE_KERNEL = "Hub kernel"
LANE_TORCH = "torch"
LANE_PARITY = "parity"
SPLIT_PYTHON = "JSON marshalling on the Python side"
SPLIT_LIBRARY = "Inside the library, including its own JSON"
SPLIT_NOTE = "measured on the same payload"
LOADING_TEXT = "Measuring the Hub kernel and torch on this machine."
EMPTY_TEXT = "Pick a shape and press {run}; the kernel is checked against torch on this machine."
HOW_TEXT = (
    f"Seed {SEED}, {WARMUPS} warm-up, {REPEATS} timed calls per lane, so the cell clears the "
    "rulebook; the card is a parity check and prints no time. The kernel lane is one native "
    "call at a time through the C ABI, JSON in and out; the torch lane is float64 on the CPU. "
    "Parity is the largest absolute difference between the two outputs against the tolerance "
    "printed on the chip, with the kernel's and torch's provenance beside it. torch is "
    "C-backed and at these shapes a kernel call is JSON transport around a microsecond of "
    "compute, so no latency pair is shown (rulebook rule 6: no comparison where transport "
    "dominates)."
)


@dataclass(frozen=True)
class Panel:
    """One measured comparison, ready to render."""

    title: str
    subtitle: str
    cell: bench.CellResult
    snippet: str
    extra_html: str = ""
    transport_ms: float | None = None


@dataclass(frozen=True)
class KernelCall:
    """One native call as it crossed the C ABI: what was sent and what came back."""

    module: str
    function: str
    args: list[Any]
    result: Any


class ShapeError(ValueError):
    """A shape the form refused before any call: `field` is the box that caused it (a
    `SHAPE_LABELS` key), `str(exc)` the one sentence that goes under that box and on the
    quiet card — the box's label and its range (`Rows: 1 to 32`)."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class Outcome:
    """What a run answers: the card, the Reproduce snippet ("" when nothing ran) and, for a
    shape the form refused, the box it names (`field`) and the sentence under it (`message`).
    Iterates as the `(card, snippet)` pair, which is what the tab's API endpoints answer."""

    card: str
    snippet: str
    field: str = ""
    message: str = ""

    @property
    def refused(self) -> bool:
        return bool(self.message)

    def __iter__(self) -> Iterator[str]:
        yield self.card
        yield self.snippet


# ---------------------------------------------------------------------------
# State cards shared by the four tabs of this milestone (empty rows, loading, quiet, copy chip)
# ---------------------------------------------------------------------------


def render_loading_card(title: str, detail: str = "") -> str:
    """`cards.loading`: the card a handler returns the instant it starts (title, detail, chip)."""
    return cards.loading(title, detail)


#: The quiet chip: neutral colour, normalised code, `data-kind="unavailable"` for the verifier.
quiet_code_chip = gpu_status.quiet_code_chip


def render_failure_card(title: str, code: str, hint: str, *, hardware: str = "") -> str:
    """A failure during a run — a lane refusal, a parity miss, an engine error, a fetch the
    visitor pressed for that did not answer — as the red card (`cards.render_error_card`)."""
    return cards.render_error_card(title=title, error_code=code, hint=hint, hardware=hardware)


def render_quiet_card(
    title: str, code: str, hint: str, *, hardware: str = "", state: str = "unavailable"
) -> str:
    """A documented state — not configured, not loaded here, not fetched yet — as the shared
    quiet card: hairline border, the code in a neutral chip, one human sentence, the machine
    line when there is one (`cards.render_unavailable_card`, or `render_not_configured_card`
    for `state="not_configured"`). Red is for a failure during a run; this is the page telling
    the truth at rest."""
    if not str(title).strip():
        raise ValueError("a quiet card needs a title")
    if not str(hint).strip():
        raise ValueError("a quiet card says what the state means")
    if state == "not_configured":
        return cards.render_not_configured_card(
            title=title, hint=hint, error_code=code, hardware=hardware
        )
    if state != "unavailable":
        raise ValueError(f"a quiet card is 'unavailable' or 'not_configured', not {state!r}")
    return cards.render_unavailable_card(title=title, error_code=code, hint=hint, hardware=hardware)


def render_empty_card(
    title: str, text: str, rows: Sequence[str] = (), *, pending_text: str = PENDING_TEXT
) -> str:
    """`cards.empty` plus the rows a result fills, an em dash standing where each value lands;
    `pending_text` is what a screen reader hears in place of the dash (`not measured yet` for a
    measurement, `not run yet` for the Governed tab's steps)."""
    pending = "".join(
        '<div class="alg-empty-row">'
        f'<span class="alg-empty-key">{common.esc(key)}</span>'
        f'<span class="alg-empty-val"><span class="alg-sr">{common.esc(pending_text)}</span>'
        f'<span aria-hidden="true">{cards.EMPTY_VALUE}</span></span>'
        "</div>"
        for key in rows
    )
    card = cards.empty(title, text)
    if not pending:
        return card
    return card.replace("</article>", f'<div class="alg-empty-rows">{pending}</div></article>')


def copy_chip(gr: Any, source: Any) -> Any:
    """The fleet's 44 px Copy chip under a Code block: client-side, relabels itself `Copied`."""
    with gr.Row(elem_classes=["alg-copy-row"]):
        button = gr.Button(
            common.LABEL_COPY, variant="secondary", elem_classes=["alg-chip-btn"], scale=0
        )
    button.click(
        None, [source], [button], js=common.COPY_JS, api_name=False, show_progress="hidden"
    )
    return button


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def _rng(seed: int = SEED) -> random.Random:
    return random.Random(seed)  # noqa: S311 - benchmark fixtures, not security


def rmsnorm_inputs(rows: int, cols: int, seed: int = SEED) -> tuple[list[float], list[float]]:
    rng = _rng(seed)
    x = [rng.gauss(0.0, 1.0) for _ in range(rows * cols)]
    gamma = [1.0 + 0.1 * rng.gauss(0.0, 1.0) for _ in range(cols)]
    return x, gamma


def rope_inputs(n_tok: int, n_heads: int, head_dim: int, seed: int = SEED) -> list[float]:
    rng = _rng(seed)
    return [rng.gauss(0.0, 1.0) for _ in range(n_tok * n_heads * head_dim)]


def logits_inputs(vocab: int, seed: int = SEED) -> list[float]:
    rng = _rng(seed)
    return [rng.gauss(0.0, 1.0) for _ in range(vocab)]


def _check_range(name: str, value: Any, spec: tuple) -> int:
    """The value as the kernel takes it, or a `ShapeError` naming the field and its range
    (`Rows: 1 to 32`, `Rows: a whole number, 1 to 32`): a decimal for a whole-number field is
    refused here, never floored (round 5: 8.5 rows ran as 8 without a word)."""
    label = SHAPE_LABELS.get(name, name)
    lo, hi, step, _ = spec
    span = f"{lo:g} to {hi:g}"
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ShapeError(name, f"{label}: a number, {span}")
    number = float(value)
    if not lo <= number <= hi:
        raise ShapeError(name, f"{label}: {span}")
    if isinstance(step, int) and abs(number - round(number)) > 1e-9:
        raise ShapeError(name, f"{label}: a whole number, {span}")
    return int(round(number)) if isinstance(step, int) else number  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# torch references (float64, CPU)
# ---------------------------------------------------------------------------


def _torch() -> Any:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - the image pins torch
        raise HubKernelError(CODE_NO_TORCH, HINT_NO_TORCH) from exc
    return torch


def torch_version() -> str:
    return pinned_versions((TORCH,))[TORCH] or "unknown"


def torch_rmsnorm(x: Sequence[float], gamma: Sequence[float], rows: int, cols: int, eps: float):
    torch = _torch()
    t = torch.tensor(list(x), dtype=torch.float64).reshape(rows, cols)
    g = torch.tensor(list(gamma), dtype=torch.float64)
    y = t * torch.rsqrt(t.pow(2).mean(dim=-1, keepdim=True) + eps) * g
    return y.reshape(-1).tolist()


def torch_rope(
    x: Sequence[float],
    n_tok: int,
    n_heads: int,
    head_dim: int,
    pos: Sequence[int],
    theta: float,
    interleaved: bool,
) -> list[float]:
    """Rotary embedding in torch: rotate-half (LLaMA) or interleaved pairs (GPT-J)."""
    torch = _torch()
    half = head_dim // 2
    t = torch.tensor(list(x), dtype=torch.float64).reshape(n_tok, n_heads, head_dim)
    inv = theta ** (-torch.arange(0, half, dtype=torch.float64) * 2.0 / head_dim)
    angles = torch.tensor(list(pos), dtype=torch.float64)[:, None] * inv[None, :]
    cos = angles.cos()[:, None, :]
    sin = angles.sin()[:, None, :]
    if interleaved:
        x1, x2 = t[..., 0::2], t[..., 1::2]
        out = torch.stack((x1 * cos - x2 * sin, x2 * cos + x1 * sin), dim=-1)
        out = out.reshape(n_tok, n_heads, head_dim)
    else:
        x1, x2 = t[..., :half], t[..., half:]
        out = torch.cat((x1 * cos - x2 * sin, x2 * cos + x1 * sin), dim=-1)
    return out.reshape(-1).tolist()


def torch_argmax(logits: Sequence[float]) -> int:
    torch = _torch()
    return int(torch.tensor(list(logits), dtype=torch.float64).argmax().item())


def torch_kept_tokens(
    logits: Sequence[float], temperature: float, top_k: int, top_p: float
) -> list[int]:
    """Token ids kept by transformers' warper order — temperature, top-k, top-p — in torch."""
    torch = _torch()
    scores = torch.tensor(list(logits), dtype=torch.float64) / temperature
    k = min(top_k, scores.numel())
    kth = torch.topk(scores, k).values[-1]
    scores = scores.masked_fill(scores < kth, float("-inf"))
    sorted_scores, sorted_idx = torch.sort(scores, descending=False)
    cumulative = sorted_scores.softmax(dim=-1).cumsum(dim=-1)
    remove = cumulative <= (1.0 - top_p)
    remove[-1] = False  # min_tokens_to_keep = 1
    keep = torch.zeros_like(remove)
    keep[sorted_idx[~remove]] = True
    keep &= scores > float("-inf")
    return sorted(int(i) for i in keep.nonzero().reshape(-1).tolist())


# ---------------------------------------------------------------------------
# Kernel calls
# ---------------------------------------------------------------------------


def _status_ok(loaded: LoadedKernel, module: str, result: Any) -> str | None:
    """The status name when the kernel reported a non-ok status, else None."""
    if not isinstance(result, Mapping) or "status" not in result:
        return None
    name = playground.status_name(loaded.kernel, module, int(result["status"]))
    return None if playground.is_ok_status(name) else (name or f"status_{result['status']}")


def _timed(fn: Callable[[], Any], repeats: int, warmups: int) -> tuple[list[float], Any]:
    """`warmups` discarded calls, then `repeats` timed ones; returns (samples_ms, last result)."""
    result = None
    for _ in range(warmups):
        result = fn()
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        samples.append((time.perf_counter() - t0) * 1e3)
    return samples, result


def _kernel_call(loaded: LoadedKernel, module: str, function: str, args: list[Any]) -> Any:
    call = hubkernel.execute(loaded, module, function, args)
    bad = _status_ok(loaded, module, call.result)
    if bad:
        hint = STATUS_HINTS.get((module, bad), f"{module}.{function} reported status {bad}")
        raise hubkernel.HubKernelCallError(bad, hint)
    return call.result


def _kernel_rmsnorm(loaded: LoadedKernel, x, gamma, rows, cols) -> list[KernelCall]:
    args = [x, gamma, rows, cols, EPS]
    result = _kernel_call(loaded, MODULE_RMSNORM, FN_RMSNORM, args)
    return [KernelCall(MODULE_RMSNORM, FN_RMSNORM, args, result)]


def _kernel_rope(loaded: LoadedKernel, x, n_tok, n_heads, head_dim, pos, interleaved):
    table_args = [head_dim, n_tok, THETA]
    table = _kernel_call(loaded, MODULE_ROPE, FN_ROPE_TABLE, table_args)
    apply_args = [
        x,
        table["cos_table"],
        table["sin_table"],
        n_tok,
        n_heads,
        head_dim,
        pos,
        interleaved,
    ]
    applied = _kernel_call(loaded, MODULE_ROPE, FN_ROPE_APPLY, apply_args)
    return [
        KernelCall(MODULE_ROPE, FN_ROPE_TABLE, table_args, table),
        KernelCall(MODULE_ROPE, FN_ROPE_APPLY, apply_args, applied),
    ]


def _kernel_greedy(loaded: LoadedKernel, logits, n) -> list[KernelCall]:
    args = [logits, n]
    result = _kernel_call(loaded, MODULE_GENERATE, FN_GREEDY, args)
    return [KernelCall(MODULE_GENERATE, FN_GREEDY, args, result)]


def kernel_kept_tokens(
    loaded: LoadedKernel, logits: Sequence[float], temperature: float, top_k: int, top_p: float
) -> tuple[list[int], int]:
    """The kept set through `llm_sampling`'s per-candidate formulas; returns (ids, native calls)."""
    order = sorted(range(len(logits)), key=lambda i: logits[i], reverse=True)
    top = order[: min(top_k, len(order))]
    scaled = [
        float(_kernel_call(loaded, MODULE_SAMPLING, FN_TEMPERATURE, [logits[i], temperature]))
        for i in top
    ]
    calls = len(top)
    threshold = float(_kernel_call(loaded, MODULE_SAMPLING, FN_TOP_K, [scaled[-1]]))
    calls += 1
    candidates = [(i, s) for i, s in zip(top, scaled, strict=True) if s >= threshold]
    peak = max(s for _, s in candidates)
    weights = [math.exp(s - peak) for _, s in candidates]
    total = sum(weights)
    probs = [w / total for w in weights]
    kept: list[int] = []
    cumulative = 0.0
    for (token, _), prob in zip(candidates, probs, strict=True):
        include = float(_kernel_call(loaded, MODULE_SAMPLING, FN_TOP_P, [prob, cumulative, top_p]))
        calls += 1
        if include > 0.0:
            kept.append(token)
        cumulative += prob
    if not kept:
        kept.append(candidates[0][0])
    return sorted(kept), calls


# ---------------------------------------------------------------------------
# The Python side of the transport, measured on the same payload
# ---------------------------------------------------------------------------


def transport_ms(calls: Sequence[KernelCall], *, repeats: int = REPEATS) -> float:
    """Median over `repeats` of encoding each call's request envelope and decoding a reply of
    the same shape — the two Python-side steps of the kernel's `_native.execute`
    (`json.dumps(...).encode("utf-8")`, `json.loads(raw.decode("utf-8"))`)."""
    if not calls:
        raise ValueError("transport_ms needs at least one call")
    envelopes = [
        {"type": ENVELOPE_TYPE, "module": c.module, "function": c.function, "args": c.args}
        for c in calls
    ]
    replies = [
        json.dumps({"result": c.result}, ensure_ascii=False, allow_nan=False).encode("utf-8")
        for c in calls
    ]
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        for envelope, reply in zip(envelopes, replies, strict=True):
            json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode("utf-8")
            json.loads(reply.decode("utf-8"))
        samples.append((time.perf_counter() - t0) * 1e3)
    return statistics.median(samples)


# ---------------------------------------------------------------------------
# Measurement -> cell
# ---------------------------------------------------------------------------


def max_abs_delta(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"outputs differ in length: {len(a)} vs {len(b)}")
    return max((abs(float(p) - float(q)) for p, q in zip(a, b, strict=True)), default=0.0)


def _lane(name: str, side: str, samples: Sequence[float], version: str) -> bench.LaneResult:
    spec = bench.LaneSpec(name=name, side=side, fn=lambda: None, version=version)
    return bench.summarise(spec, list(samples))


def make_cell(
    loaded: LoadedKernel,
    kernel_ms: Sequence[float],
    torch_ms: Sequence[float],
    parity_label: str,
    *,
    ts_utc: str | None = None,
) -> bench.CellResult:
    lanes = [
        _lane(revision_label(loaded), bench.SIDE_ALGENTA, kernel_ms, kernel_revision(loaded)[:7]),
        _lane(f"torch {torch_version()}", bench.SIDE_INCUMBENT, torch_ms, torch_version()),
    ]
    return bench.CellResult(
        status=bench.STATUS_MEASURED,
        lanes=lanes,
        ratio=bench.ratio_of(lanes),
        parity_label=parity_label,
        n=REPEATS,
        warmups=WARMUPS,
        load_1m=bench.load_1m(),
        cpu_quota=bench.cpu_quota(),
        ts_utc=utc_stamp() if ts_utc is None else ts_utc,
        seed=SEED,
    )


def _parity_label(delta: float, tol: float) -> str:
    return f"max |Δ| {delta:.1e} ≤ {tol:.0e}"


def _subtitle(loaded: LoadedKernel) -> str:
    """Words only: the repository, variant and revision are chips and mono values, not copy."""
    del loaded
    return empty_provenance()


def _through_lane(deps: Deps, label: str, fn: Callable[[], Any]) -> Any:
    return deps.lane.run(fn, budget_s=BUDGET_S, label=label)


def kernel_hold(deps: Deps) -> tuple[str, str] | None:
    """`(code, hint)` when the family cannot run here — not loaded (the boot's own code when it
    recorded one) or paused by the kill switch — else None. One human sentence; the code is the
    chip's alone."""
    if deps.kernel(FAMILY) is None:
        error = deps.kernel_errors.get(FAMILY) or deps.kernel_errors.get(f"algenta-{FAMILY}")
        return (error.code if error is not None else CODE_NO_KERNEL), HINT_NO_KERNEL
    if not deps.feature_on(FEATURE):
        return CODE_PAUSED, HINT_PAUSED
    return None


class KernelHeldError(HubKernelError):
    """The family is not available here (documented state): rendered as the quiet card."""


def _kernel(deps: Deps) -> LoadedKernel:
    hold = kernel_hold(deps)
    if hold is not None:
        raise KernelHeldError(*hold)
    loaded = deps.kernel(FAMILY)
    assert loaded is not None  # noqa: S101 - kernel_hold returned None
    return loaded


def check_rmsnorm_shape(rows: Any, cols: Any) -> tuple[int, int]:
    """The RMSNorm shape as the kernel takes it, or the `ShapeError` naming the box."""
    return _check_range("rows", rows, ROWS), _check_range("cols", cols, COLS)


def check_rope_shape(n_tok: Any, n_heads: Any, head_dim: Any) -> tuple[int, int, int]:
    """The RoPE shape as the kernel takes it: the three ranges, then the even head dimension."""
    n_tok = _check_range("tokens", n_tok, TOKENS)
    n_heads = _check_range("heads", n_heads, HEADS)
    head_dim = _check_range("head_dim", head_dim, HEAD_DIM)
    if head_dim % 2:
        raise ShapeError("head_dim", HINT_HEAD_DIM_ODD)
    return n_tok, n_heads, head_dim


def check_sampling_shape(
    vocab: Any, temperature: Any, top_k: Any, top_p: Any
) -> tuple[int, float, int, float]:
    """The sampling shape as the kernel takes it, or the `ShapeError` naming the box."""
    return (
        _check_range("vocab", vocab, VOCAB),
        _check_range("temperature", temperature, TEMPERATURE),
        _check_range("top_k", top_k, TOP_K),
        _check_range("top_p", top_p, TOP_P),
    )


def measure_rmsnorm(deps: Deps, rows: int, cols: int) -> Panel:
    rows, cols = check_rmsnorm_shape(rows, cols)
    loaded = _kernel(deps)
    x, gamma = rmsnorm_inputs(rows, cols)
    kernel_ms, calls = _through_lane(
        deps,
        f"{MODULE_RMSNORM}.{FN_RMSNORM} {rows}x{cols}",
        lambda: _timed(lambda: _kernel_rmsnorm(loaded, x, gamma, rows, cols), REPEATS, WARMUPS),
    )
    kernel_y = calls[-1].result["y"]
    torch_ms, torch_y = _timed(lambda: torch_rmsnorm(x, gamma, rows, cols, EPS), REPEATS, WARMUPS)
    delta = max_abs_delta(kernel_y, torch_y)
    if delta > TOL_RMSNORM:
        raise hubkernel.HubKernelCallError(
            "parity_failed",
            f"RMSNorm differs from torch by {delta:.2e} (tolerance {TOL_RMSNORM:g})",
        )
    cell = make_cell(loaded, kernel_ms, torch_ms, _parity_label(delta, TOL_RMSNORM))
    return Panel(
        title=f"{TITLE_RMSNORM} · {rows} × {cols}",
        subtitle=_subtitle(loaded),
        cell=cell,
        snippet=snippet_rmsnorm(rows, cols),
        transport_ms=transport_ms(calls),
    )


def measure_rope(deps: Deps, n_tok: int, n_heads: int, head_dim: int, interleaved: bool) -> Panel:
    n_tok, n_heads, head_dim = check_rope_shape(n_tok, n_heads, head_dim)
    interleaved = bool(interleaved)
    loaded = _kernel(deps)
    x = rope_inputs(n_tok, n_heads, head_dim)
    pos = list(range(n_tok))
    kernel_ms, calls = _through_lane(
        deps,
        f"{MODULE_ROPE}.{FN_ROPE_APPLY} {n_tok}x{n_heads}x{head_dim}",
        lambda: _timed(
            lambda: _kernel_rope(loaded, x, n_tok, n_heads, head_dim, pos, interleaved),
            REPEATS,
            WARMUPS,
        ),
    )
    kernel_y = calls[-1].result["values"]
    torch_ms, torch_y = _timed(
        lambda: torch_rope(x, n_tok, n_heads, head_dim, pos, THETA, interleaved), REPEATS, WARMUPS
    )
    delta = max_abs_delta(kernel_y, torch_y)
    if delta > TOL_ROPE:
        raise hubkernel.HubKernelCallError(
            "parity_failed", f"RoPE differs from torch by {delta:.2e} (tolerance {TOL_ROPE:g})"
        )
    layout = "interleaved pairs" if interleaved else "rotate-half"
    cell = make_cell(loaded, kernel_ms, torch_ms, _parity_label(delta, TOL_ROPE))
    return Panel(
        title=f"{TITLE_ROPE} · {n_tok} × {n_heads} × {head_dim}",
        subtitle=f"{layout} · θ {THETA:g} · {_subtitle(loaded)}",
        cell=cell,
        snippet=snippet_rope(n_tok, n_heads, head_dim, interleaved),
        transport_ms=transport_ms(calls),
    )


def measure_sampling(deps: Deps, vocab: int, temperature: float, top_k: int, top_p: float) -> Panel:
    vocab, temperature, top_k, top_p = check_sampling_shape(vocab, temperature, top_k, top_p)
    loaded = _kernel(deps)
    logits = logits_inputs(vocab)
    kernel_ms, calls = _through_lane(
        deps,
        f"{MODULE_GENERATE}.{FN_GREEDY} n={vocab}",
        lambda: _timed(lambda: _kernel_greedy(loaded, logits, vocab), REPEATS, WARMUPS),
    )
    kernel_token = int(calls[-1].result["token_id"])
    torch_ms, torch_token = _timed(lambda: torch_argmax(logits), REPEATS, WARMUPS)
    if kernel_token != torch_token:
        raise hubkernel.HubKernelCallError(
            "parity_failed", f"greedy token {kernel_token} differs from torch {torch_token}"
        )
    kernel_kept, native_calls = _through_lane(
        deps,
        f"{MODULE_SAMPLING} top-k {top_k} top-p {top_p:g}",
        lambda: kernel_kept_tokens(loaded, logits, temperature, top_k, top_p),
    )
    torch_kept = torch_kept_tokens(logits, temperature, top_k, top_p)
    if kernel_kept != torch_kept:
        raise hubkernel.HubKernelCallError(
            "parity_failed",
            f"top-k/top-p kept {len(kernel_kept)} tokens, torch kept {len(torch_kept)}",
        )
    cell = make_cell(loaded, kernel_ms, torch_ms, f"greedy token {kernel_token} · exact")
    extra = render_sampling_note(len(kernel_kept), top_k, top_p, temperature, native_calls)
    return Panel(
        title=f"{TITLE_SAMPLING} · {vocab:,} logits",
        subtitle=f"greedy argmax · {_subtitle(loaded)}",
        cell=cell,
        snippet=snippet_sampling(vocab, temperature, top_k, top_p),
        extra_html=extra,
        transport_ms=transport_ms(calls),
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _spread(lane: bench.LaneResult) -> str:
    """`median of 5 · max 8.55 ms` (P95 once a lane has 20 samples, as the rulebook prints)."""
    tail = "P95" if lane.n >= bench.P95_MIN_N else "max"
    return f"median of {lane.n} · {tail} {cards.fmt_ms(lane.p95_ms)}"


def _lane_row(label: str, lane: bench.LaneResult, *, split: str = "") -> str:
    return (
        '<div class="alg-llm-lane">'
        f'<div class="alg-llm-lane-head"><span class="alg-llm-lane-label">{common.esc(label)}'
        f'</span><span class="alg-llm-lane-name">{common.esc(lane.name)}</span></div>'
        f'<div class="alg-llm-lane-figure"><span class="alg-lane-val">'
        f"{cards.fmt_ms(lane.median_ms)}</span>"
        f'<span class="alg-llm-lane-meta">{common.esc(_spread(lane))}</span></div>'
        f"{split}"
        "</div>"
    )


def _split_html(kernel_median_ms: float, python_ms: float) -> str:
    """The kernel lane split: the measured Python-side JSON step and the remainder."""
    python_ms = min(python_ms, kernel_median_ms)
    inside_ms = max(kernel_median_ms - python_ms, 0.0)
    return (
        '<div class="alg-llm-split">'
        '<div class="alg-llm-split-row">'
        f'<span class="alg-llm-split-key">{SPLIT_PYTHON}</span>'
        f'<span class="alg-llm-split-val">{cards.fmt_ms(python_ms)}</span>'
        f'<span class="alg-llm-split-note">{SPLIT_NOTE}</span></div>'
        '<div class="alg-llm-split-row">'
        f'<span class="alg-llm-split-key">{SPLIT_LIBRARY}</span>'
        f'<span class="alg-llm-split-val">{cards.fmt_ms(inside_ms)}</span>'
        '<span class="alg-llm-split-note">the remainder of the median</span></div>'
        "</div>"
    )


PARITY_HERO_LABEL = "compiled Mojo kernel · checked against torch"
#: Why the card shows no latency pair (rulebook rule 6): at these shapes the call is JSON
#: transport around a microsecond kernel, and torch's single C call is not what a visitor
#: would take a per-op comparison to be about (owner, 2026-09-24: "user will see it as we are
#: slower"). The timing still runs (the cell must clear the rulebook to count as measured);
#: the card prints parity, provenance and the machine line.
PARITY_CARD_NOTE = "parity check · no timing shown at this shape"


def render_parity_card(panel: Panel, hardware: str) -> str:
    """A parity panel: the parity chip is the hero; provenance chips; no latencies (rule 6)."""
    cell = panel.cell
    if not cell.measured:
        return cards.render_not_recorded_card(cell, title=panel.title, hardware=hardware)
    ours = cell.lane(bench.SIDE_ALGENTA)
    theirs = cell.lane(bench.SIDE_INCUMBENT)
    if ours is None or theirs is None:
        raise ValueError("a parity panel needs both lanes")
    hero = (
        '<div class="alg-hero alg-llm-hero">'
        f'<span class="alg-llm-parity alg-chip alg-chip-ok">{LANE_PARITY} '
        f"{common.esc(cell.parity_label)}</span>"
        f'<div class="alg-hero-label">{PARITY_HERO_LABEL}</div>'
        "</div>"
    )
    chips = [
        common.chip(f"{LANE_KERNEL} · {common.esc(ours.name)}"),
        common.chip(f"{LANE_TORCH} · {common.esc(theirs.name)}"),
        common.chip(f"seed {cell.seed}"),
        common.chip(f"n = {cell.n}"),
        common.chip(PARITY_CARD_NOTE),
        cards.status_chip("measured", f"measured {cell.ts_utc}"),
    ]
    return (
        '<div class="alg-llm-card"><article class="alg-card alg-card-result">'
        '<div class="alg-card-head">'
        f'<div><h2 class="alg-card-title">{common.esc(panel.title)}</h2>'
        f'<div class="alg-card-sub">{common.esc(panel.subtitle)}</div></div>'
        f"{hero}</div>"
        f'<div class="alg-chips">{"".join(chips)}</div>'
        f"{cards.foot_html(hardware, cell.ts_utc, cell.load_1m)}"
        "</article></div>"
    )


def render_panel(panel: Panel, hardware: str) -> str:
    return render_parity_card(panel, hardware) + panel.extra_html


def render_sampling_note(
    kept: int, top_k: int, top_p: float, temperature: float, calls: int
) -> str:
    chips = "".join(
        f'<span class="alg-chip alg-chip-{tone}">{text}</span>'
        for text, tone in (
            (f"temperature {temperature:g}", "neutral"),
            (f"top-k {top_k}", "neutral"),
            (f"top-p {top_p:g}", "neutral"),
            (f"keeps {kept} tokens", "neutral"),
            ("same set as torch", "ok"),
            (f"{calls} native calls", "neutral"),
        )
    )
    return f'<div class="alg-llm-note"><div class="alg-chips">{chips}</div></div>'


def empty_provenance() -> str:
    """The one line the empty card carries under its sentence: what a run compares, in the
    measured card's own subtitle words (`_subtitle`) — never a lane row with a dash where a
    figure would land, since the measured card prints no figure (round 11: the empty state
    advertised two timed lanes, `Hub kernel · —` and `torch · —`, that no run ever fills)."""
    return f"Hub kernel against torch {torch_version()} on the CPU, float64"


def render_empty(title: str, run_label: str) -> str:
    """The result column before its first run, shaped like the parity card it becomes: the
    title, one sentence, one provenance line — no lane rows, no dashes, no timing promise."""
    card = render_empty_card(title, EMPTY_TEXT.format(run=run_label))
    line = f'<p class="alg-empty-provenance">{common.esc(empty_provenance())}</p>'
    return card.replace("</article>", f"{line}</article>")


def opening_card(deps: Deps, title: str, run_label: str) -> str:
    """What a result column shows at boot: the empty card, or the quiet card when the family
    did not load here — the visitor reads the state before pressing anything."""
    hold = kernel_hold(deps)
    if hold is None:
        return render_empty(title, run_label)
    code, hint = hold
    return render_quiet_card(title, code, hint, hardware=deps.hardware)


def render_loading(title: str) -> str:
    return render_loading_card(title, LOADING_TEXT)


def render_error(title: str, code: str, hint: str, hardware: str) -> str:
    """A failure during a run: the red card (`render_failure_card`)."""
    return render_failure_card(title, code, hint, hardware=hardware)


def _error_card(title: str, exc: BaseException, hardware: str) -> str:
    if isinstance(exc, KernelHeldError):
        return render_quiet_card(title, exc.code, exc.message, hardware=hardware)
    if isinstance(exc, LaneError):
        return render_error(title, exc.code, exc.hint or exc.message, hardware)
    if isinstance(exc, HubKernelError):
        return render_error(title, exc.code, exc.message, hardware)
    if isinstance(exc, ValueError):
        # a shape the form refused is a documented state, not a failure during a run: quiet
        return render_quiet_card(title, CODE_BAD_SHAPE, str(exc), hardware=hardware)
    raise exc


def _limited(deps: Deps, request: Any) -> str | None:
    """The limits' reason when the visitor is over the native allowance, else None."""
    limits = deps.limits
    if limits is None or NATIVE_LIMIT_KIND not in limits.policy.lanes:
        return None
    key = visitor_key(request)
    decision = limits.check(key, NATIVE_LIMIT_KIND)
    return None if decision.allowed else decision.reason


def request_hint(fn: Callable[..., Any], gr: Any) -> Callable[..., Any]:
    """Mark `fn`'s `request` parameter as `gr.Request` so Gradio injects it.

    The tab modules never import gradio at module level, and `from __future__ import
    annotations` would leave a string Gradio cannot resolve; the class itself is set here.
    """
    fn.__annotations__["request"] = gr.Request
    return fn


def visitor_key(request: Any) -> str:
    """`<ip>|<session>` from a `gr.Request`; a fixed key when there is no request (tests, API)."""
    if request is None:
        return "local|-"
    headers = getattr(request, "headers", None) or {}
    client = getattr(request, "client", None)
    host = str(getattr(client, "host", "") or "")
    session = str(getattr(request, "session_hash", "") or "")
    return key_from_request(dict(headers), client_host=host, session_hash=session)


def _run(deps: Deps, title: str, measure: Callable[[], Panel], request: Any) -> Outcome:
    reason = _limited(deps, request)
    if reason:
        # A refusal by the visitor allowance is a documented state, not a failure: quiet.
        return Outcome(render_quiet_card(title, CODE_LIMITED, reason, hardware=deps.hardware), "")
    try:
        panel = measure()
    except ShapeError as exc:
        # the quiet card with the code, and the sentence for the slot under the box it names
        return Outcome(_error_card(title, exc, deps.hardware), "", exc.field, str(exc))
    except (LaneError, HubKernelError, ValueError) as exc:
        return Outcome(_error_card(title, exc, deps.hardware), "")
    return Outcome(render_panel(panel, deps.hardware), panel.snippet)


def field_messages(outcome: Outcome, fields: Sequence[str]) -> tuple[str, ...]:
    """One message slot per field, in `fields` order: the refusal's sentence (as the alert,
    `common.render_field_message`) under the box it names — the first box when the sentence
    names none of them — and nothing under the others; every slot empty when nothing was
    refused, so a run that went through clears an earlier refusal."""
    if not fields:
        raise ValueError("a panel has at least one field")
    if not outcome.refused:
        return tuple("" for _ in fields)
    field = outcome.field if outcome.field in fields else fields[0]
    return tuple(common.render_field_message(outcome.message) if f == field else "" for f in fields)


def status_row(outcome: Outcome) -> str:
    """The status row under Run: `STATUS_NOT_RUN` after a refusal (the sentence itself is
    under the box, never said twice), else the empty live region that takes no space."""
    if outcome.refused:
        return common.render_status(echo=common.STATUS_NOT_RUN)
    return common.render_status()


def run_rmsnorm(deps: Deps, rows: int, cols: int, request: Any = None) -> Outcome:
    """The card and snippet (and the refused field, if any) — the handler behind `llm_run`."""
    return _run(deps, TITLE_RMSNORM, lambda: measure_rmsnorm(deps, rows, cols), request)


def run_rope(
    deps: Deps, n_tok: int, n_heads: int, head_dim: int, interleaved: bool, request: Any = None
) -> Outcome:
    return _run(
        deps, TITLE_ROPE, lambda: measure_rope(deps, n_tok, n_heads, head_dim, interleaved), request
    )


def run_sampling(
    deps: Deps, vocab: int, temperature: float, top_k: int, top_p: float, request: Any = None
) -> Outcome:
    return _run(
        deps,
        TITLE_SAMPLING,
        lambda: measure_sampling(deps, vocab, temperature, top_k, top_p),
        request,
    )


#: Sentinel a staged handler yields for an output it leaves as it is (rendered as no update).
KEEP = object()


def staged(title: str, run: Callable[[], Any]) -> Iterator[Any]:
    """The loading card at once (snippet untouched), then the result and its snippet."""
    yield render_loading(title), KEEP
    yield run()


def panel_updates(
    title: str,
    fields: Sequence[str],
    run: Callable[[], Outcome],
    keep: Any,
    *,
    check: Callable[[], Outcome | None],
) -> Iterator[tuple[Any, ...]]:
    """What a panel's handler yields into `[card, snippet, status, *slots]`.

    A refused shape is told where the fleet tells it — the sentence under the box it names,
    `STATUS_NOT_RUN` beside Run — and nothing else on the panel changes: the card stays what
    it was (the empty card, or the last measured shape, whose title carries its own shape) and
    the Reproduce editor keeps its snippet, so the panel keeps its height (round 11: the
    refusal's empty snippet made Gradio paint its stock empty-editor placeholder — 384 px with
    a live Copy button — and the quiet card and the echo moved the panels below). So the
    loading card is never shown for a refusal either: the shape is checked first, and only a
    shape that passes gets the loading card and then the outcome. A run that failed after the
    check (the visitor allowance, a kernel error) keeps its card — that is what happened — and
    leaves the editor alone: nothing ran, so there is nothing new to reproduce.
    `Outcome.__iter__` still answers `(card, snippet)` for the module's own callers.

    `check` answers the refusal for the shape before anything runs (`shape_refusal`), or None
    when the shape passes; `run` then measures."""
    outcome = check()
    if outcome is not None and outcome.refused:
        yield keep, keep, status_row(outcome), *field_messages(outcome, fields)
        return
    yield render_loading(title), keep, keep, *(keep for _ in fields)
    outcome = run()
    if outcome.refused:
        # `run` re-checks the shape and cannot refuse what `check` passed; a caller wiring a
        # different check still gets the fleet's answer, with the loading card replaced
        yield outcome.card, keep, status_row(outcome), *field_messages(outcome, fields)
        return
    snippet = outcome.snippet if outcome.snippet else keep
    yield outcome.card, snippet, status_row(outcome), *field_messages(outcome, fields)


def shape_refusal(deps: Deps, title: str, check: Callable[[], Any]) -> Outcome | None:
    """The refused `Outcome` — the quiet card, the box and its sentence — when `check` (one of
    `check_*_shape`, the range checks every `measure_*` runs first) raises `ShapeError`; None
    when the shape passes. Nothing runs either way."""
    try:
        check()
    except ShapeError as exc:
        return Outcome(_error_card(title, exc, deps.hardware), "", exc.field, str(exc))
    return None


# ---------------------------------------------------------------------------
# Snippets — valid Python that reproduces the visitor's shapes with the same seed
# ---------------------------------------------------------------------------


def _snippet_head() -> str:
    trust = "".join(f'    "{repo}",\n' for repo in playground.TRUST)
    return (
        f"# {playground.PIP_KERNELS}\n"
        "import random\n\n"
        "import torch\n"
        "from kernels import get_kernel\n\n"
        f"TRUST = [\n{trust}]\n"
        f'k = get_kernel("{playground.repo_id(FAMILY)}", version={playground.KERNEL_VERSION}, '
        f'backend="{playground.BACKEND}", trust_remote_code=TRUST)\n'
        f"rng = random.Random({SEED})\n"
    )


def snippet_rmsnorm(rows: int, cols: int) -> str:
    return (
        _snippet_head() + f"rows, cols, eps = {rows}, {cols}, {EPS!r}\n"
        "x = [rng.gauss(0.0, 1.0) for _ in range(rows * cols)]\n"
        "gamma = [1.0 + 0.1 * rng.gauss(0.0, 1.0) for _ in range(cols)]\n\n"
        f"out = k.{MODULE_RMSNORM}.{FN_RMSNORM}(x, gamma, rows, cols, eps)\n"
        'y = torch.tensor(out["y"], dtype=torch.float64)\n\n'
        "t = torch.tensor(x, dtype=torch.float64).reshape(rows, cols)\n"
        "ref = t * torch.rsqrt(t.pow(2).mean(-1, keepdim=True) + eps)"
        " * torch.tensor(gamma, dtype=torch.float64)\n"
        "print((y - ref.reshape(-1)).abs().max().item())\n"
    )


def snippet_rope(n_tok: int, n_heads: int, head_dim: int, interleaved: bool) -> str:
    return (
        _snippet_head()
        + f"n_tok, n_heads, head_dim, theta = {n_tok}, {n_heads}, {head_dim}, {THETA!r}\n"
        "x = [rng.gauss(0.0, 1.0) for _ in range(n_tok * n_heads * head_dim)]\n"
        "pos = list(range(n_tok))\n\n"
        f"table = k.{MODULE_ROPE}.{FN_ROPE_TABLE}(head_dim, n_tok, theta)\n"
        f"out = k.{MODULE_ROPE}.{FN_ROPE_APPLY}(\n"
        '    x, table["cos_table"], table["sin_table"], n_tok, n_heads, head_dim, pos, '
        f"{interleaved!r}\n)\n"
        'y = torch.tensor(out["values"], dtype=torch.float64)\n\n'
        "t = torch.tensor(x, dtype=torch.float64).reshape(n_tok, n_heads, head_dim)\n"
        "half = head_dim // 2\n"
        "inv = theta ** (-torch.arange(0, half, dtype=torch.float64) * 2.0 / head_dim)\n"
        "ang = torch.tensor(pos, dtype=torch.float64)[:, None] * inv[None, :]\n"
        "cos, sin = ang.cos()[:, None, :], ang.sin()[:, None, :]\n"
        f"if {interleaved!r}:\n"
        "    x1, x2 = t[..., 0::2], t[..., 1::2]\n"
        "    ref = torch.stack((x1 * cos - x2 * sin, x2 * cos + x1 * sin), -1).reshape(t.shape)\n"
        "else:\n"
        "    x1, x2 = t[..., :half], t[..., half:]\n"
        "    ref = torch.cat((x1 * cos - x2 * sin, x2 * cos + x1 * sin), -1)\n"
        "print((y - ref.reshape(-1)).abs().max().item())\n"
    )


def snippet_sampling(vocab: int, temperature: float, top_k: int, top_p: float) -> str:
    return (
        _snippet_head() + f"vocab, temperature, top_k, top_p = {vocab}, {temperature!r}, "
        f"{top_k}, {top_p!r}\n"
        "logits = [rng.gauss(0.0, 1.0) for _ in range(vocab)]\n\n"
        f"greedy = k.{MODULE_GENERATE}.{FN_GREEDY}(logits, vocab)\n"
        'print(greedy["token_id"], int(torch.tensor(logits).argmax()))\n\n'
        "top = sorted(range(vocab), key=lambda i: logits[i], reverse=True)[:top_k]\n"
        f"scaled = [k.{MODULE_SAMPLING}.{FN_TEMPERATURE}(logits[i], temperature) for i in top]\n"
        f"threshold = k.{MODULE_SAMPLING}.{FN_TOP_K}(scaled[-1])\n"
        "probs = torch.tensor(scaled).softmax(-1).tolist()\n"
        "kept, seen = [], 0.0\n"
        "for token, prob in zip(top, probs, strict=True):\n"
        f"    if k.{MODULE_SAMPLING}.{FN_TOP_P}(prob, seen, top_p) > 0.0:\n"
        "        kept.append(token)\n"
        "    seen += prob\n"
        "print(sorted(kept))\n"
    )


# ---------------------------------------------------------------------------
# CSS — alg-llm-* for this tab; alg-card-loading, alg-empty-*, alg-sr and alg-stack-table for
# the four tabs of this milestone. css.rule() repeats each class four times; tokens from
# design.py; spacing on the 8-pt scale; colour only for meaning.
# ---------------------------------------------------------------------------

_CAPTION = "font-size: var(--alg-caption-size); line-height: var(--alg-caption-line);"
_BODY = "font-size: var(--alg-body-size); line-height: var(--alg-body-line);"
_MONO = "font-family: var(--alg-font-mono); font-variant-numeric: tabular-nums;"
_CELL = (
    "text-align: left; padding: 8px 8px 8px 0; border: 0;"
    " border-bottom: 1px solid var(--alg-hairline); vertical-align: top;"
)

STATE_CSS = stylesheet(
    # the empty card's provenance line: the measured card's subtitle face, under the sentence
    rule("alg-empty-provenance", f"{_CAPTION} color: var(--alg-text-2); margin: 8px 0 0;"),
    rule("alg-empty-rows", "display: flex; flex-direction: column; gap: 4px; margin: 12px 0 0;"),
    rule(
        "alg-empty-row",
        f"display: flex; justify-content: space-between; gap: 16px; {_CAPTION}"
        " padding: 4px 0; border-bottom: 1px solid var(--alg-hairline);",
    ),
    rule("alg-empty-key", "color: var(--alg-text-2);"),
    rule("alg-empty-val", f"{_MONO} color: var(--alg-text-2);"),
    rule(
        "alg-sr",
        "position: absolute; width: 1px; height: 1px; padding: 0; margin: 0; overflow: hidden;"
        " clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;",
    ),
    rule(
        "alg-stack-table",
        f"width: 100%; border-collapse: collapse; border: 0; {_CAPTION} margin: 8px 0 0;"
        " color: var(--alg-text);",
    ),
    rule("alg-stack-table", f"{_CELL} color: var(--alg-text-2); font-weight: 500;", suffix=" th"),
    rule("alg-stack-table", _CELL, suffix=" td"),
    rule("alg-stack-table", "border-bottom: 0;", suffix=" tbody tr:last-child td"),
    rule("alg-stack-num", f"{_MONO} text-align: right; white-space: nowrap;"),
    # the cell rules carry an element in their selector; a numeric column's alignment needs
    # the same weight, or the cell's `text-align: left` wins (round 3: five columns, all left)
    rule("alg-stack-table", "text-align: right; padding-right: 24px;", suffix=" .alg-stack-num"),
    rule("alg-stack-table", "display: none;", suffix=" td::before"),
    # the two-column stretch: the block, its two wrappers and the card grow to the column;
    # every other block in that column keeps its own height
    rule(STRETCH_COL_CLASS, "flex: 0 0 auto;", suffix=" > div"),
    rule(STRETCH_COL_CLASS, "flex: 1 1 auto;", suffix=f" > .{STRETCH_CLASS}"),
    rule(STRETCH_CLASS, "flex: 1 1 auto; display: flex; flex-direction: column;"),
    rule(STRETCH_CLASS, "flex: 1 1 auto; display: flex; flex-direction: column;", suffix=" > div"),
    rule(
        STRETCH_CLASS,
        "flex: 1 1 auto; display: flex; flex-direction: column;",
        suffix=" > div > div",
    ),
    rule(
        STRETCH_CLASS, "flex: 1 1 auto; display: flex; flex-direction: column;", suffix=" .alg-card"
    ),
    rule(
        STRETCH_CLASS,
        "margin-top: auto; padding-top: 12px;",
        suffix=" .alg-card > .alg-card-foot",
    ),
    block(
        "@media (width <= 768px)",
        rule("alg-stack-table", "display: block;"),
        rule("alg-stack-table", "display: none;", suffix=" thead"),
        rule("alg-stack-table", "display: block;", suffix=" tbody"),
        rule(
            "alg-stack-table",
            "display: flex; flex-direction: column; border: 1px solid var(--alg-hairline);"
            " border-radius: var(--alg-radius-card); padding: 8px 16px; margin: 0 0 8px;"
            " background: var(--alg-surface);",
            suffix=" tbody tr",
        ),
        rule(
            "alg-stack-table",
            "display: flex; justify-content: space-between; align-items: baseline; gap: 16px;"
            " padding: 4px 0; border-bottom: 1px solid var(--alg-hairline);",
            suffix=" td",
        ),
        rule("alg-stack-table", "border-bottom: 0;", suffix=" td:last-child"),
        rule(
            "alg-stack-table",
            "display: inline; content: attr(data-label); color: var(--alg-text-2); flex: 0 0 auto;",
            suffix=" td::before",
        ),
        rule("alg-stack-table", "text-align: right; padding-right: 0;", suffix=" .alg-stack-num"),
        rule("alg-stack-lead", "order: -1; font-weight: 600;"),
        # the dense variant: the row card keeps its frame, the lead takes the first line and
        # the other cells follow inline, wrapping, without labels
        rule(
            STACK_DENSE_CLASS,
            "flex-direction: row; flex-wrap: wrap; align-items: baseline; gap: 0 12px;",
            suffix=" tbody tr",
        ),
        rule(
            STACK_DENSE_CLASS,
            "display: inline-flex; gap: 4px; padding: 0; border-bottom: 0; text-align: left;",
            suffix=" td",
        ),
        rule(STACK_DENSE_CLASS, "display: none;", suffix=" td::before"),
        rule(STACK_DENSE_CLASS, "flex: 1 1 100%; order: -1;", suffix=" .alg-stack-lead"),
    ),
)

#: The shell collects every `*_CSS` string a tab module declares; the tile's own sheet rides here.
GPU_CSS = gpu_status.GPU_CSS

LLM_CSS = stylesheet(
    rule("alg-llm-note", "margin: 8px 0 0;"),
    rule("alg-llm-panel", "display: flex; flex-direction: column; gap: 16px; margin: 24px 0 0;"),
    # The title block takes the slack and its subtitle wraps, so a long subtitle never pushes the
    # parity hero under the title on one card while the neighbours keep it on the right.
    rule(
        "alg-llm-card",
        "flex: 1 1 240px; min-width: 0;",
        suffix=" .alg-card-head > div:first-child",
    ),
    rule("alg-llm-hero", "text-align: right; display: flex; flex-direction: column; gap: 4px;"),
    rule("alg-llm-hero", "align-items: flex-end; flex: 0 1 auto;"),
    rule("alg-llm-parity", "display: inline-block; font-weight: 600;"),
    rule("alg-llm-lanes", "display: flex; flex-direction: column; gap: 12px; margin: 16px 0 0;"),
    rule(
        "alg-llm-lane",
        "display: flex; flex-direction: column; gap: 4px; padding: 12px 0;"
        " border-top: 1px solid var(--alg-hairline);",
    ),
    rule("alg-llm-lane-head", f"display: flex; flex-wrap: wrap; gap: 4px 12px; {_CAPTION}"),
    rule("alg-llm-lane-label", "color: var(--alg-text-2);"),
    rule("alg-llm-lane-name", f"{_MONO} color: var(--alg-text);"),
    rule(
        "alg-llm-lane-figure",
        "display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 16px;",
    ),
    rule(
        "alg-llm-lane-figure",
        f"{_MONO} font-size: var(--alg-title-size); line-height: var(--alg-title-line);"
        " letter-spacing: var(--alg-title-tracking); font-weight: 600; color: var(--alg-text);"
        " flex: 0 0 auto; white-space: nowrap; text-align: left;",
        suffix=" .alg-lane-val",
    ),
    rule("alg-llm-lane-meta", f"{_CAPTION} color: var(--alg-text-2);"),
    rule("alg-llm-split", "display: flex; flex-direction: column; gap: 4px; margin: 4px 0 0;"),
    rule(
        "alg-llm-split-row",
        f"display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; {_CAPTION}",
    ),
    rule("alg-llm-split-key", "color: var(--alg-text-2); flex: 1 1 240px;"),
    rule(
        "alg-llm-split-val",
        f"{_MONO} color: var(--alg-text); min-width: 64px; text-align: right;",
    ),
    rule("alg-llm-split-note", "color: var(--alg-text-2); flex: 1 1 100%;"),
)


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------


def build(deps: Deps, *, poller: gpu_status.GpuStatusPoller | None = None) -> TabSpec:
    """The tab spec. The GPU tile is drawn only with a `poller` (tests) or when the stage is
    configured for this Space (`gpu_status.configured(deps.env)`); otherwise there is no tile,
    no timer and no load hook — a stage that was never wired up is not "unavailable"."""
    gpu = poller
    if gpu is None and gpu_status.configured(deps.env):
        gpu = gpu_status.shared_poller(gpu_status.status_url(deps.env))
    for text in (LABEL, TITLE_RMSNORM, TITLE_ROPE, TITLE_SAMPLING, RUN_RMSNORM, RUN_ROPE):
        check_copy(text, max_words=6, what="llm tab label")
    check_copy(RUN_SAMPLING, max_words=6, what="llm tab label")
    check_copy(HOW_TEXT, what="llm how text")
    check_copy(LOADING_TEXT, what="llm loading text")

    def render(gr: Any) -> dict[str, Any]:
        handles: dict[str, Any] = {}
        if gpu is not None and deps.env.get("SPACE_ID", "").strip():
            gpu.start()
        native = {
            "concurrency_id": "native",
            "concurrency_limit": 1,
            "show_progress": "hidden",
        }

        def slider(spec: tuple, label: str) -> Any:
            # a number box, not a slider: a typed value above the range must be refused with a
            # field message, never clamped in silence (round 9: Rows 50 kept '50' in the box while
            # the slider and the run used 32); the handlers' range checks answer
            return gr.Number(value=spec[3], label=label, step=spec[2], precision=None)

        def pair(slots_out: list[Any], *builders: Callable[[], Any]) -> list[Any]:
            """Two controls side by side, one field column each, one under the other on a
            phone (`alg-form-row` top-aligns them, so a filled slot grows its own column
            alone). Every number box gets a message slot right under it, appended to
            `slots_out` in box order — the fleet's one reserved caption line, empty until a
            refusal, so the sentence fills the line and moves nothing (Try, the Playground);
            a checkbox has nothing to refuse and gets none."""
            made = []
            with gr.Row(elem_classes=["alg-form-row"]):
                for build_control in builders:
                    with gr.Column(elem_classes=["alg-field"], min_width=CONTROL_MIN_WIDTH):
                        control = build_control()
                        made.append(control)
                        if isinstance(control, gr.Number):
                            slots_out.append(
                                gr.HTML("", elem_classes=["alg-status-row", "alg-field-slot"])
                            )
            return made

        def panel(
            key: str,
            run_label: str,
            title: str,
            controls: Callable[[list[Any]], list[Any]],
            snippet_text: str,
        ):
            """One stack: the controls (each number box over its message slot), Run under them
            with the status row, the card across the full width, then Reproduce — the result
            never sits beside a shorter column. Returns the inputs, the slots (one per
            `PANEL_FIELDS[key]` entry, in order), Run, the status row, the card, the editor."""
            slots: list[Any] = []
            inputs = controls(slots)
            if len(slots) != len(PANEL_FIELDS[key]):
                raise ValueError(f"{key}: {len(slots)} slots for {len(PANEL_FIELDS[key])} fields")
            # the panel's primary action across the panel, as the Playground's Run is (round 12)
            run = gr.Button(run_label, variant=RUN_VARIANT, elem_classes=["alg-run"])
            # the refusal's echo lands here (`STATUS_NOT_RUN`) in the reserved caption line
            # under Run (`common.STATUS_SLOT_CLASS`), so the panels below never move
            status = gr.HTML(common.render_status(), elem_classes=[common.STATUS_SLOT_CLASS])
            card = gr.HTML(opening_card(deps, title, run_label), elem_classes=[common.BLOCK_CLASS])
            with gr.Accordion(REPRODUCE_TITLE, open=False, elem_classes=["alg-disclosure"]):
                snippet = gr.Code(
                    value=snippet_text,
                    language="python",
                    label=SNIPPET_LABEL,
                    wrap_lines=True,
                    buttons=[],
                    interactive=False,
                )
                copy_chip(gr, snippet)
            return inputs, slots, run, status, card, snippet

        (rows, cols), slots1, run1, status1, card1, snip1 = panel(
            "rmsnorm",
            RUN_RMSNORM,
            TITLE_RMSNORM,
            lambda s: pair(s, lambda: slider(ROWS, "Rows"), lambda: slider(COLS, "Columns")),
            snippet_rmsnorm(ROWS[3], COLS[3]),
        )
        (tokens, heads, head_dim, interleaved), slots2, run2, status2, card2, snip2 = panel(
            "rope",
            RUN_ROPE,
            TITLE_ROPE,
            lambda s: [
                *pair(s, lambda: slider(TOKENS, "Tokens"), lambda: slider(HEADS, "Heads")),
                *pair(
                    s,
                    lambda: slider(HEAD_DIM, "Head dimension"),
                    lambda: gr.Checkbox(value=False, label="Interleaved pairs"),
                ),
            ],
            snippet_rope(TOKENS[3], HEADS[3], HEAD_DIM[3], False),
        )
        (vocab, temperature, top_k, top_p), slots3, run3, status3, card3, snip3 = panel(
            "sampling",
            RUN_SAMPLING,
            TITLE_SAMPLING,
            lambda s: [
                *pair(
                    s,
                    lambda: slider(VOCAB, "Vocabulary"),
                    lambda: slider(TEMPERATURE, "Temperature"),
                ),
                *pair(s, lambda: slider(TOP_K, "Top-k"), lambda: slider(TOP_P, "Top-p")),
            ],
            snippet_sampling(VOCAB[3], TEMPERATURE[3], TOP_K[3], TOP_P[3]),
        )

        if gpu is not None:
            poller = gpu
            tile = gr.HTML(
                value=gpu_status.render_tile(poller.latest()),
                elem_classes=["alg-llm-panel", common.BLOCK_CLASS],
            )
            timer = gr.Timer(gpu_status.POLL_S)

            def refresh_tile() -> str:
                return gpu_status.render_tile(poller.latest())

            timer.tick(refresh_tile, None, tile, api_name=False, show_progress="hidden")
            handles.update(gpu_tile=tile, gpu_timer=timer)
            handles[LOAD_HOOKS] = [(refresh_tile, tile)]

        with gr.Accordion(HOW_TITLE, open=False, elem_classes=["alg-disclosure"]):
            gr.HTML(common.render_note(HOW_TEXT))

        def _emit(key: str, title: str, check: Callable[[], Any], run: Callable[[], Outcome]):
            yield from panel_updates(
                title,
                PANEL_FIELDS[key],
                run,
                gr.update(),
                check=lambda: shape_refusal(deps, title, check),
            )

        # the values reach `_check_range` as typed: a decimal in a whole-number field is
        # refused with a sentence, never floored on the way in (round 5)
        def on_rmsnorm(r: float, c: float, request=None):
            yield from _emit(
                "rmsnorm",
                TITLE_RMSNORM,
                lambda: check_rmsnorm_shape(r, c),
                lambda: run_rmsnorm(deps, r, c, request),
            )

        def on_rope(t: float, h: float, d: float, inter: bool, request=None):
            yield from _emit(
                "rope",
                TITLE_ROPE,
                lambda: check_rope_shape(t, h, d),
                lambda: run_rope(deps, t, h, d, bool(inter), request),
            )

        def on_sampling(v: float, temp: float, k: float, p: float, request=None):
            yield from _emit(
                "sampling",
                TITLE_SAMPLING,
                lambda: check_sampling_shape(v, temp, k, p),
                lambda: run_sampling(deps, v, float(temp), k, float(p), request),
            )

        for handler in (on_rmsnorm, on_rope, on_sampling):
            request_hint(handler, gr)

        quiet = {"api_name": False, "show_progress": "hidden"}
        # editing a box clears the refusal: the sentence under it and the echo beside Run
        for status, slots, boxes in (
            (status1, slots1, (rows, cols)),
            (status2, slots2, (tokens, heads, head_dim)),
            (status3, slots3, (vocab, temperature, top_k, top_p)),
        ):
            cleared = (common.render_status(), *("" for _ in slots))
            for box in boxes:
                box.input(lambda cleared=cleared: cleared, None, [status, *slots], **quiet)

        run1.click(
            on_rmsnorm,
            [rows, cols],
            [card1, snip1, status1, *slots1],
            api_name=API_RMSNORM,
            **native,
        )
        run2.click(
            on_rope,
            [tokens, heads, head_dim, interleaved],
            [card2, snip2, status2, *slots2],
            api_name=API_ROPE,
            **native,
        )
        run3.click(
            on_sampling,
            [vocab, temperature, top_k, top_p],
            [card3, snip3, status3, *slots3],
            api_name=API_SAMPLING,
            **native,
        )
        handles.update(
            rows=rows,
            cols=cols,
            run_rmsnorm=run1,
            status_rmsnorm=status1,
            slots_rmsnorm=slots1,
            card_rmsnorm=card1,
            tokens=tokens,
            heads=heads,
            head_dim=head_dim,
            interleaved=interleaved,
            run_rope=run2,
            status_rope=status2,
            slots_rope=slots2,
            card_rope=card2,
            vocab=vocab,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            run_sampling=run3,
            status_sampling=status3,
            slots_sampling=slots3,
            card_sampling=card3,
            snippet_rmsnorm=snip1,
            snippet_rope=snip2,
            snippet_sampling=snip3,
            on_rmsnorm=on_rmsnorm,
            on_rope=on_rope,
            on_sampling=on_sampling,
        )
        return handles

    return TabSpec(id=TAB_LLM, label=LABEL, render=render, api_names=API_NAMES)
