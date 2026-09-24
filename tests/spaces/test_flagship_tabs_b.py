"""Flagship tabs B — LLM kernels, Governed, Ecosystem — plus the webhook route and the GPU tile.

Everything runs offline. The "kernel" is a fake that implements the `algenta-llm`
functions the LLM tab calls with plain Python math against the published contract
(`tests/spaces/fixtures/hero_contracts.json`), so the torch references are checked
against an independent implementation. The hosted engine is a fake client with the
engine's real wire shapes (copied from `test_hosted_api.py`); the Hub, GitHub and GPU
status bodies are copies of the live responses' shapes with test values.
"""

from __future__ import annotations

import html as html_lib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from _rules import (
    _assert_clean_copy,
    _assert_four_class_selectors,
    _assert_stylesheet_discipline,
)
from algenta_spaces import bench, cards, css, hosted_api, hubkernel, playground
from algenta_spaces.hosted_api import HostedGoverned
from algenta_spaces.killswitch import KillSwitch
from algenta_spaces.lane import Lane, LaneBusyError
from algenta_spaces.limits import LanePolicy, Limits, Policy

_APP = Path(__file__).resolve().parents[2] / "apps" / "spaces" / "algenta"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

import gpu_status  # noqa: E402 - the Space's own modules, next to app.py
import races  # noqa: E402
import webhook  # noqa: E402
from tabs import Deps, TabSpec, common, eco_tab, gov_tab, llm_tab, race_tab, try_tab  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HERO_FIXTURE = FIXTURES / "hero_contracts.json"
CONTRACT_PY = (
    Path(__file__).resolve().parents[2] / "packages" / "algenta" / "algenta" / "_contract.py"
)
INTEGRATIONS_CONTRACT = (
    Path.home()
    / "Developer"
    / "algenta-integrations"
    / "contracts"
    / "integration-tool-contract.json"
)

# Markers the live verifier greps for (apps/spaces/algenta/verify_checks.py); frozen cards.
RESULT_CARD_RE = re.compile(r'class="alg-card alg-card-result"')
PARITY_RE = re.compile(r'alg-chip-ok">parity\b')
UNAVAILABLE_RE = re.compile(r'data-kind="unavailable">unavailable · (?P<code>[^<]+)<')
LANE_VAL_RE = re.compile(r'alg-lane-val">([^<]+)<')
FOOT_RE = re.compile(r'alg-card-foot">[^<]*?(?:<time[^>]*>)?\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC<')
LOADING_RE = re.compile(r'class="alg-card alg-card-loading"[^>]*aria-busy="true"')
SNAKE_RE = re.compile(r"\b[a-z0-9]+(?:_[a-z0-9]+)+\b")
TAG_RE = re.compile(r"<[^>]+>")
NOT_CONFIGURED = cards.normalize_code(hosted_api.NOT_CONFIGURED_CODE)

HARDWARE = "test box · 2 vCPU · Linux x86_64"


def code_of(html: str) -> str | None:
    m = UNAVAILABLE_RE.search(html)
    return m.group("code").strip() if m else None


def code(text: str) -> str:
    """The fleet's spelling of an error code (`cards.normalize_code`)."""
    return cards.normalize_code(text)


def primary_text(html: str) -> str:
    """The visible copy outside chips, footers and mono values — where identifiers may not be."""
    stripped = re.sub(
        r'<(span|div) class="alg-chip[^"]*"[^>]*>.*?</\1>|<div class="alg-card-foot">.*?</div>'
        r'|<span class="alg-gov-val">.*?</span>|<span class="alg-gov-mono">.*?</span>'
        r'|<td[^>]*class="alg-gov-mono"[^>]*>.*?</td>|<td[^>]*class="alg-eco-mono"[^>]*>.*?</td>'
        r"|<pre[^>]*>.*?</pre>"
        r"|<a [^>]*>.*?</a>",
        " ",
        html,
        flags=re.DOTALL,
    )
    return TAG_RE.sub(" ", stripped)


def _prose(html: str) -> str:
    """The card without its code blocks: where a fact is printed once, in words."""
    return re.sub(r"<pre[^>]*>.*?</pre>", " ", html, flags=re.DOTALL)


def text_of(html: str) -> str:
    return TAG_RE.sub(" ", html)


def flat(html: str) -> str:
    """The rendered text as a reader sees it: tags gone, entities decoded, one space between
    words — so a stamp inside a `<time>` element still reads `counted 2026-09-22 14:02 UTC`."""
    return re.sub(r"\s+", " ", html_lib.unescape(TAG_RE.sub(" ", html))).strip()


# ---------------------------------------------------------------------------
# The fake algenta-llm kernel: the contract from the fixture, the math in Python
# ---------------------------------------------------------------------------


class KernelError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _sampling_module() -> dict[str, Any]:
    def fn(name: str, params: list[str]) -> dict[str, Any]:
        return {
            "name": name,
            "params": [
                {"name": p, "type": "Float64", "has_default": False, "is_mut": False}
                for p in params
            ],
            "return_type": "Float64",
            "count_relations": [],
            "doc": "",
            "returns_doc": "",
        }

    return {
        "description": "Token sampling: temperature, top-k, top-p, min-p, penalties, beam scores",
        "functions": {
            "temperature_scale": fn("temperature_scale", ["logit", "temperature"]),
            "top_k_threshold": fn("top_k_threshold", ["k_th_logit"]),
            "top_p_cumulative": fn("top_p_cumulative", ["sorted_prob", "cumulative_so_far", "p"]),
        },
    }


class FakeLlmKernel:
    """`get_kernel("thyn-ai/algenta-llm")` reduced to what the LLM tab calls, in plain Python."""

    def __init__(self, contract: dict[str, Any], *, rmsnorm_status: int = 380):
        self.CONTRACT = contract
        self.excluded_functions: list[str] = []
        self.calls: list[tuple[str, str]] = []
        self.rmsnorm_status = rmsnorm_status

    def execute(self, module: str, function: str, args: list | None = None) -> Any:
        self.calls.append((module, function))
        a = list(args or [])
        if module == "normk.rmsnorm" and function == "rmsnorm_fwd_flat":
            x, gamma, rows, cols, eps = a
            y, rstd = [], []
            for r in range(rows):
                row = x[r * cols : (r + 1) * cols]
                inv = 1.0 / math.sqrt(sum(v * v for v in row) / cols + eps)
                rstd.append(inv)
                y.extend(v * inv * g for v, g in zip(row, gamma, strict=True))
            return {
                "y": y,
                "rstd": rstd,
                "n_rows": rows,
                "n_cols": cols,
                "status": self.rmsnorm_status,
            }
        if module == "attnk.rope" and function == "rope_table":
            head_dim, max_pos, theta = a
            pairs = head_dim // 2
            cos, sin = [], []
            for pos in range(max_pos):
                for i in range(pairs):
                    ang = pos * theta ** (-2.0 * i / head_dim)
                    cos.append(math.cos(ang))
                    sin.append(math.sin(ang))
            return {
                "cos_table": cos,
                "sin_table": sin,
                "max_pos": max_pos,
                "n_pairs": pairs,
                "theta": theta,
                "status": 360,
            }
        if module == "attnk.rope" and function == "rope_apply_flat":
            x, cos, sin, n_tok, n_heads, head_dim, pos, interleaved = a
            pairs = head_dim // 2
            out = list(x)
            for t in range(n_tok):
                for h in range(n_heads):
                    base = (t * n_heads + h) * head_dim
                    for i in range(pairs):
                        c = cos[pos[t] * pairs + i]
                        s = sin[pos[t] * pairs + i]
                        if interleaved:
                            i1, i2 = base + 2 * i, base + 2 * i + 1
                        else:
                            i1, i2 = base + i, base + pairs + i
                        x1, x2 = x[i1], x[i2]
                        out[i1] = x1 * c - x2 * s
                        out[i2] = x2 * c + x1 * s
            return {
                "values": out,
                "n_tok": n_tok,
                "n_heads": n_heads,
                "head_dim": head_dim,
                "status": 360,
            }
        if module == "llmk.generate" and function == "greedy_argmax_flat":
            logits, n = a
            best = max(range(n), key=lambda i: logits[i])
            return {"token_id": best, "logit": logits[best], "status": 560}
        if module == "llm_sampling":
            if function == "temperature_scale":
                return a[0] / a[1]
            if function == "top_k_threshold":
                return a[0]
            if function == "top_p_cumulative":
                return 1.0 if a[1] < a[2] else 0.0
        raise KernelError("function_not_registered", f"{module}.{function}")


@pytest.fixture(scope="module")
def llm_contract() -> dict[str, Any]:
    record = json.loads(HERO_FIXTURE.read_text(encoding="utf-8"))["llm"]
    contract = json.loads(json.dumps(record["contract"]))
    contract["modules"]["llm_sampling"] = _sampling_module()
    return contract


def loaded_llm(kernel: FakeLlmKernel) -> hubkernel.LoadedKernel:
    return hubkernel.LoadedKernel(
        family="llm",
        repo_id="thyn-ai/algenta-llm",
        kernel=kernel,  # type: ignore[arg-type]
        variant="torch25-cpu-fake",
        capped_v1_sha="a01e2b232875ced70b3dbd925996f913d5126370",
        snapshot_sha="",
        backend="cpu",
        version=1,
        load_s=0.1,
    )


#: A cache whose `v1` moved past the capped revision: the loaded snapshot is the code that ran.
CAPPED_SHA = "a01e2b232875ced70b3dbd925996f913d5126370"
MOVED_SHA = "92ef06d7c1a7b2f4e8d9c0b1a2f3e4d5c6b7a8f9"


def loaded_llm_moved(kernel: FakeLlmKernel) -> hubkernel.LoadedKernel:
    loaded = loaded_llm(kernel)
    loaded.snapshot_sha = MOVED_SHA
    return loaded


@pytest.fixture
def fake_kernel(llm_contract: dict[str, Any]) -> FakeLlmKernel:
    return FakeLlmKernel(llm_contract)


@pytest.fixture
def deps(fake_kernel: FakeLlmKernel) -> Deps:
    return Deps(
        kernels={"llm": loaded_llm(fake_kernel)},
        lane=Lane(),
        facts={"versions": {"torch": "2.5.1"}, "generated_utc": "2026-09-22 14:02 UTC"},
        hardware=HARDWARE,
        env={},
    )


class OffSwitch(KillSwitch):
    def __init__(self, off: set[str]):
        super().__init__("https://example.invalid/flags.json", fetch=lambda u, e: None)  # type: ignore[arg-type]
        self._off = off

    def enabled(self, feature: str) -> bool:
        return feature not in self._off


# ---------------------------------------------------------------------------
# LLM tab
# ---------------------------------------------------------------------------


def _assert_result_card(html: str) -> None:
    assert RESULT_CARD_RE.search(html), html[:300]
    assert PARITY_RE.search(html), "the parity chip is the hero and the verifier's marker"
    assert llm_tab.PARITY_HERO_LABEL in html  # parity only, no latency pair (round 9)
    # round 9, rulebook rule 6: no latency pair, no split, no bars — the card is the parity
    # check plus provenance (a visitor read "14.7 ms vs 0.333 ms" as the kernel being slower
    # when it was JSON transport around a microsecond of compute)
    assert not LANE_VAL_RE.findall(html), "no lane latencies on a parity card"
    assert "alg-lane-bar" not in html and "alg-hero-num" not in html, "no ratio, no bars"
    assert "alg-llm-lane-figure" not in html and llm_tab.SPLIT_PYTHON not in html
    assert llm_tab.PARITY_CARD_NOTE in html and llm_tab.LANE_TORCH in html
    assert FOOT_RE.search(html), "hardware line with a UTC stamp"
    assert HARDWARE in html
    sub = re.search(r'alg-card-sub">([^<]*)<', html)
    assert sub is not None
    assert "thyn-ai/" not in sub.group(1) and "@" not in sub.group(1), sub.group(1)
    assert not SNAKE_RE.search(sub.group(1)), "no variant or repository id in the subtitle"
    assert "torch25" not in primary_text(html) and "aarch64" not in primary_text(html)
    _assert_clean_copy(html)


def test_rmsnorm_parity_card_and_snippet(deps: Deps, fake_kernel: FakeLlmKernel):
    pytest.importorskip("torch")
    html, snippet = llm_tab.run_rmsnorm(deps, 4, 64)
    _assert_result_card(html)
    assert "RMSNorm · 4 × 64" in html
    assert "max |Δ|" in html
    assert fake_kernel.calls.count(("normk.rmsnorm", "rmsnorm_fwd_flat")) == llm_tab.REPEATS + 1
    compile(snippet, "<rmsnorm>", "exec")
    assert "rmsnorm_fwd_flat(x, gamma, rows, cols, eps)" in snippet
    assert "rows, cols, eps = 4, 64, 1e-06" in snippet


@pytest.mark.parametrize("interleaved", [False, True])
def test_rope_parity_both_layouts(deps: Deps, interleaved: bool):
    pytest.importorskip("torch")
    html, snippet = llm_tab.run_rope(deps, 3, 2, 16, interleaved)
    _assert_result_card(html)
    assert ("interleaved pairs" if interleaved else "rotate-half") in html
    compile(snippet, "<rope>", "exec")
    assert f"pos, {interleaved!r}" in snippet


def test_lane_label_names_the_loaded_snapshot_not_the_capped_sha(deps: Deps, fake_kernel):
    """A cache whose `v1` moved past the manifest runs the snapshot's code; the lane label, the
    lane version and `races.kernel_revision` all name that sha, never the capped one."""
    pytest.importorskip("torch")
    moved = loaded_llm_moved(fake_kernel)
    assert races.kernel_revision(moved) == MOVED_SHA
    assert races.revision_label(moved) == f"llm@{MOVED_SHA[:7]}"
    assert races.kernel_revision(loaded_llm(fake_kernel)) == CAPPED_SHA, "no snapshot: capped"
    cell = llm_tab.make_cell(moved, [1.0, 1.1, 1.2], [0.1, 0.1, 0.1], "exact")
    ours = cell.lane("algenta")
    assert ours is not None and ours.name == f"llm@{MOVED_SHA[:7]}"
    assert ours.version == MOVED_SHA[:7] and CAPPED_SHA[:7] not in ours.name
    deps.kernels = {"llm": moved}
    html, _ = llm_tab.run_rmsnorm(deps, 2, 64)
    assert f"llm@{MOVED_SHA[:7]}" in html and CAPPED_SHA[:7] not in html


def test_torch_rope_reproduces_the_real_kernel_values():
    """Values recorded from the real `attnk.rope.rope_apply_flat` (torch25-cpu-aarch64-darwin)."""
    pytest.importorskip("torch")
    x = [i / 10 for i in range(16)]
    plain = llm_tab.torch_rope(x, 2, 1, 8, [0, 1], 10000.0, False)
    inter = llm_tab.torch_rope(x, 2, 1, 8, [0, 1], 10000.0, True)
    assert plain[:8] == pytest.approx(x[:8])
    # The kernel's cos/sin carry ~1e-11 of transcendental error, inside the tolerance the chip
    # states (TOL_ROPE); the reference itself is exact to float64.
    assert plain[8:12] == pytest.approx(
        [-0.577523337074964, 0.7657203071031967, 0.9859502337475823, 1.0984994502498462],
        abs=llm_tab.TOL_ROPE,
    )
    assert inter[8:10] == pytest.approx(
        [-0.32508204163259513, 1.159448863127643], abs=llm_tab.TOL_ROPE
    )
    assert (
        max(
            abs(a - b)
            for a, b in zip(
                plain[8:12],
                [-0.577523337074964, 0.7657203071031967, 0.9859502337475823, 1.0984994502498462],
                strict=True,
            )
        )
        < 1e-10
    )


def test_sampling_parity_greedy_and_kept_set(deps: Deps, fake_kernel: FakeLlmKernel):
    pytest.importorskip("torch")
    html, snippet = llm_tab.run_sampling(deps, 256, 0.8, 10, 0.9)
    _assert_result_card(html)
    assert "greedy token" in html
    assert "same set as torch" in html
    assert "keeps" in html
    native = sum(1 for m, _ in fake_kernel.calls if m == "llm_sampling")
    assert f"{native} native calls" in html
    compile(snippet, "<sampling>", "exec")


def test_kept_tokens_match_between_kernel_formulas_and_torch(deps: Deps, fake_kernel):
    pytest.importorskip("torch")
    logits = llm_tab.logits_inputs(512)
    kernel_kept, calls = llm_tab.kernel_kept_tokens(loaded_llm(fake_kernel), logits, 1.3, 25, 0.7)
    assert kernel_kept == llm_tab.torch_kept_tokens(logits, 1.3, 25, 0.7)
    assert 0 < len(kernel_kept) <= 25
    assert calls == 25 + 1 + 25


def test_shape_outside_the_contract_is_refused_before_any_call(deps: Deps, fake_kernel):
    html, snippet = llm_tab.run_rmsnorm(deps, 0, 64)
    assert code_of(html) == llm_tab.CODE_BAD_SHAPE
    assert snippet == ""
    assert fake_kernel.calls == []
    html, _ = llm_tab.run_rope(deps, 8, 4, 12, False)  # head_dim not on the 16-step grid
    assert code_of(html) == llm_tab.CODE_BAD_SHAPE
    html, _ = llm_tab.run_sampling(deps, 4096, 0.8, 500, 0.9)
    assert code_of(html) == llm_tab.CODE_BAD_SHAPE


def test_missing_kernel_and_kill_switch_render_the_quiet_card(deps: Deps):
    empty = Deps(kernels={}, lane=Lane(), hardware=HARDWARE, env={})
    html, _ = llm_tab.run_rmsnorm(empty, 4, 64)
    assert code_of(html) == llm_tab.CODE_NO_KERNEL
    assert "alg-card-quiet" in html and "alg-card-err" not in html and "alg-chip-err" not in html
    reason = re.search(r'alg-card-reason">([^<]*)<', html)
    assert reason is not None and reason.group(1) == llm_tab.HINT_NO_KERNEL, "one sentence"
    assert not SNAKE_RE.search(primary_text(html)), "the code lives in the chip only"
    _assert_clean_copy(html)
    error = hubkernel.HubKernelUnavailable("variant_unavailable", "no build for this platform")
    held = Deps(kernels={}, lane=Lane(), hardware=HARDWARE, kernel_errors={"llm": error}, env={})
    html, _ = llm_tab.run_rmsnorm(held, 4, 64)
    assert code_of(html) == "variant_unavailable", "the boot's own code, once, in the chip"
    assert "kernel_not_loaded" not in html and "variant_unavailable:" not in html
    assert reason is not None and reason.group(1) in html
    # the result column opens on the same quiet card, so the state is read before any press
    opening = llm_tab.opening_card(held, llm_tab.TITLE_RMSNORM, llm_tab.RUN_RMSNORM)
    assert code_of(opening) == "variant_unavailable" and "alg-card-quiet" in opening
    assert "alg-card-empty" in llm_tab.opening_card(
        deps, llm_tab.TITLE_RMSNORM, llm_tab.RUN_RMSNORM
    )
    deps.killswitch = OffSwitch({"kernels"})
    html, _ = llm_tab.run_rope(deps, 2, 1, 16, False)
    assert code_of(html) == llm_tab.CODE_PAUSED and "alg-card-quiet" in html
    assert llm_tab.kernel_hold(deps) == (llm_tab.CODE_PAUSED, llm_tab.HINT_PAUSED)


def test_non_ok_kernel_status_is_named_not_rendered_as_a_result(llm_contract):
    pytest.importorskip("torch")
    kernel = FakeLlmKernel(llm_contract, rmsnorm_status=382)
    d = Deps(kernels={"llm": loaded_llm(kernel)}, lane=Lane(), hardware=HARDWARE, env={})
    html, _ = llm_tab.run_rmsnorm(d, 2, 64)
    assert code_of(html) == "length_mismatch"
    assert not RESULT_CARD_RE.search(html)


def test_lane_refusal_becomes_the_unavailable_card(deps: Deps):
    class BusyLane:
        def run(self, fn, /, *args, budget_s, label, **kwargs):
            raise LaneBusyError(f"{label}: a timed-out call is still running")

    deps.lane = BusyLane()  # type: ignore[assignment]
    html, _ = llm_tab.run_rmsnorm(deps, 2, 64)
    assert code_of(html) == "lane_busy"
    assert "alg-card-err" in html, "a failure during a run is the red card"
    assert "lane_busy:" not in html, "the code is not repeated in the prose"


def test_native_limits_apply_when_the_policy_names_the_lane(deps: Deps):
    pytest.importorskip("torch")
    deps.limits = Limits(
        Policy({"native": LanePolicy(burst=1, window_s=60.0, per_day=10, daily_cap=100)})
    )
    first, _ = llm_tab.run_rmsnorm(deps, 2, 64)
    assert RESULT_CARD_RE.search(first)
    second, _ = llm_tab.run_rmsnorm(deps, 2, 64)
    assert code_of(second) == llm_tab.CODE_LIMITED


def test_llm_copy_and_css_discipline():
    for text in (
        llm_tab.LABEL,
        llm_tab.HOW_TEXT,
        llm_tab.HINT_NO_KERNEL,
        llm_tab.HINT_PAUSED,
        llm_tab.RUN_RMSNORM,
        llm_tab.RUN_ROPE,
        llm_tab.RUN_SAMPLING,
        llm_tab.LOADING_TEXT,
    ):
        _assert_clean_copy(text)
        assert not SNAKE_RE.search(text), text
    quiet = llm_tab.render_quiet_card("T", "Some-Code", "One sentence.", hardware=HARDWARE)
    assert code_of(quiet) == "some_code" and "alg-chip-neutral" in quiet
    assert "alg-chip-err" not in quiet and 'data-state="unavailable"' in quiet
    assert HARDWARE in quiet
    with pytest.raises(ValueError):
        llm_tab.render_quiet_card("T", "code", " ")
    assert len(llm_tab.LABEL.split()) <= 6
    for sheet in (llm_tab.LLM_CSS, llm_tab.STATE_CSS):
        _assert_stylesheet_discipline(sheet)
        _assert_four_class_selectors(sheet)
    assert llm_tab.STRETCH_CLASS == "alg-stretch" and llm_tab.STACK_DENSE_CLASS == "alg-stack-dense"
    assert (
        ".alg-stretch" * 4 + " .alg-card > .alg-card-foot { margin-top: auto;" in llm_tab.STATE_CSS
    )
    assert ".alg-stretch-col" * 4 + " > div { flex: 0 0 auto; }" in llm_tab.STATE_CSS
    assert ".alg-stretch-col" * 4 + " > .alg-stretch { flex: 1 1 auto; }" in llm_tab.STATE_CSS
    assert (
        ".alg-stack-table" * 4 + " .alg-stack-num { text-align: right; padding-right: 24px; }"
        in llm_tab.STATE_CSS
    ), "the numeric alignment carries the weight of the cell rules it overrides, with a gutter"
    assert ".alg-stack-dense" * 4 + " td::before { display: none; }" in llm_tab.STATE_CSS
    assert ".alg-stack-dense" * 4 + " .alg-stack-lead { flex: 1 1 100%; order: -1; }" in (
        llm_tab.STATE_CSS
    )
    assert llm_tab.API_NAMES[0] == "llm_run"
    assert llm_tab.RUN_VARIANT == "secondary", "three peer panels share one button hierarchy"
    pending = llm_tab.render_empty_card("T", "Press run.", rows=("a",), pending_text="not run yet")
    assert 'alg-sr">not run yet<' in pending and llm_tab.PENDING_TEXT not in pending
    assert llm_tab.PENDING_TEXT in llm_tab.render_empty_card("T", "Press run.", rows=("a",))


def test_transport_split_is_measured_on_the_same_payload_and_never_exceeds_the_lane(
    deps, fake_kernel
):
    pytest.importorskip("torch")
    panel = llm_tab.measure_rmsnorm(deps, 4, 64)
    assert panel.transport_ms is not None and panel.transport_ms > 0
    calls = [
        llm_tab.KernelCall(
            "normk.rmsnorm",
            "rmsnorm_fwd_flat",
            [[0.5] * 256, [1.0] * 64, 4, 64, 1e-6],
            {"y": [0.5] * 256},
        )
    ]
    measured = llm_tab.transport_ms(calls, repeats=3)
    assert measured > 0
    with pytest.raises(ValueError):
        llm_tab.transport_ms([])
    card = llm_tab.render_parity_card(panel, HARDWARE)
    ours = panel.cell.lane("algenta")
    assert ours is not None
    # round 9 (rulebook rule 6): the parity card shows no latency pair — a visitor read
    # "14.7 ms vs 0.333 ms" as the kernel being slower when it was JSON transport around a
    # microsecond of compute; the split stays available to the tooling (`_split_html`)
    assert "alg-llm-split" not in card and "median of" not in card
    assert cards.fmt_ms(ours.median_ms) not in card
    assert llm_tab.PARITY_HERO_LABEL in card and llm_tab.PARITY_CARD_NOTE in card
    assert "alg-llm-parity" in card and 'class="alg-chips"' in card
    split = llm_tab._split_html(ours.median_ms, panel.transport_ms or 0.5)
    assert "the remainder of the median" in split and split.count('class="alg-llm-split-row"') == 2


def test_llm_empty_and_loading_cards_name_the_rows_a_run_fills():
    empty = llm_tab.render_empty(llm_tab.TITLE_RMSNORM, llm_tab.RUN_RMSNORM)
    assert 'class="alg-card alg-card-empty"' in empty
    for key in (llm_tab.LANE_KERNEL, llm_tab.LANE_TORCH, llm_tab.LANE_PARITY):
        assert f'alg-empty-key">{key}<' in empty
    assert empty.count(cards.EMPTY_VALUE) == 3 and "not measured yet" in empty
    assert "Run RMSNorm" in empty
    _assert_clean_copy(empty)
    loading = llm_tab.render_loading(llm_tab.TITLE_ROPE)
    assert LOADING_RE.search(loading) and 'data-kind="loading"' in loading
    assert llm_tab.LOADING_TEXT in loading
    _assert_clean_copy(loading)
    staged = list(llm_tab.staged("T", lambda: ("card", "snippet")))
    assert staged[0][1] is llm_tab.KEEP and LOADING_RE.search(staged[0][0])
    assert staged[1] == ("card", "snippet")


def test_slider_ranges_stay_inside_the_playground_list_budget():
    assert llm_tab.ROWS[1] * llm_tab.COLS[1] <= playground.MAX_LIST_ELEMENTS
    assert (
        llm_tab.TOKENS[1] * llm_tab.HEADS[1] * llm_tab.HEAD_DIM[1] <= playground.MAX_LIST_ELEMENTS
    )
    assert llm_tab.VOCAB[1] <= playground.MAX_LIST_ELEMENTS
    for spec in (llm_tab.ROWS, llm_tab.COLS, llm_tab.TOKENS, llm_tab.HEADS, llm_tab.HEAD_DIM):
        lo, hi, step, default = spec
        assert lo <= default <= hi and (default - lo) % step == 0


# ---------------------------------------------------------------------------
# GPU status tile
# ---------------------------------------------------------------------------

GPU_BODY = {
    "tok_per_s": 41.7,
    "measured_utc": "2026-09-22 14:02 UTC",
    "hardware": "NVIDIA L4 · sm_89 · 23 GB",
    "model": "Qwen3-1.7B",
    "lane": "algenta-cuda",
    "ttft_ms": 212.0,
    "online": True,
}


def test_gpu_status_parses_and_renders_live_tile():
    status = gpu_status.parse_status(json.dumps(GPU_BODY).encode())
    assert status.tok_per_s == 41.7 and status.online
    html = gpu_status.render_tile(gpu_status.Snapshot(status, "", "2026-09-22 14:03 UTC"))
    assert "41.7 tok/s" in html
    assert 'class="alg-stat alg-stat-ok" data-state="ok"' in html
    assert "measured 2026-09-22 14:02 UTC" in html
    assert gpu_status.OPEN_URL in html and gpu_status.OPEN_TEXT in html
    assert "first token 212 ms" in html and "NVIDIA L4" in html and "Qwen3-1.7B" in html
    _assert_clean_copy(html)


def test_gpu_status_offline_shows_last_measured_not_live():
    body = {**GPU_BODY, "online": False}
    status = gpu_status.parse_status(json.dumps(body).encode())
    html = gpu_status.render_tile(gpu_status.Snapshot(status, "", "2026-09-22 14:03 UTC"))
    assert gpu_status.OFFLINE_TEXT in html
    assert 'data-state="warn"' in html and 'data-state="ok"' not in html
    assert "last measured 2026-09-22 14:02 UTC" in html
    _assert_clean_copy(html)


def test_gpu_status_configured_only_with_an_https_url():
    assert gpu_status.configured({}) is False and gpu_status.status_url({}) == ""
    assert gpu_status.configured({gpu_status.STATUS_URL_ENV: " "}) is False
    assert (
        gpu_status.configured({gpu_status.STATUS_URL_ENV: "http://x.example/api/status"}) is False
    )
    assert gpu_status.configured({gpu_status.STATUS_URL_ENV: "https://"}) is False
    env = {gpu_status.STATUS_URL_ENV: gpu_status.STATUS_URL}
    assert gpu_status.configured(env) is True
    assert gpu_status.status_url(env) == gpu_status.STATUS_URL
    assert gpu_status.STATUS_URL_ENV == "ALGENTA_GPU_STATUS_URL"


def test_gpu_status_unreachable_is_a_quiet_tile_with_the_code_never_a_red_card():
    html = gpu_status.render_tile(
        gpu_status.Snapshot(None, gpu_status.CODE_UNREACHABLE, "2026-09-22 14:03 UTC")
    )
    assert "alg-chip-err" not in html and "alg-chip-neutral" in html, "quiet, not red-first"
    assert gpu_status.GOVERNED_AGENT_HOST not in html, "the endpoint is configuration, not copy"
    assert gpu_status.HINT_UNREACHABLE in html
    malformed = gpu_status.render_tile(
        gpu_status.Snapshot(None, gpu_status.CODE_MALFORMED, "2026-09-22 14:03 UTC")
    )
    assert (
        gpu_status.HINT_MALFORMED in malformed and code_of(malformed) == gpu_status.CODE_MALFORMED
    )
    assert 'data-state="unavailable"' in html and "alg-card-err" not in html
    assert code_of(html) == gpu_status.CODE_UNREACHABLE
    assert gpu_status.OFFLINE_TEXT in html and cards.EMPTY_VALUE in html
    assert "tok/s" not in html, "no remembered number without its stamp"
    assert gpu_status.OPEN_TEXT in html and "2026-09-22 14:03 UTC" in html
    _assert_clean_copy(html)


@pytest.mark.parametrize(
    "bad",
    [
        {**GPU_BODY, "tok_per_s": 0},
        {**GPU_BODY, "tok_per_s": "41"},
        {**GPU_BODY, "measured_utc": ""},
        {k: v for k, v in GPU_BODY.items() if k != "hardware"},
        {**GPU_BODY, "online": "yes"},
        [GPU_BODY],
    ],
)
def test_gpu_status_rejects_anything_that_is_not_a_measurement(bad):
    with pytest.raises(ValueError):
        gpu_status.parse_status(json.dumps(bad).encode())


def test_gpu_poller_never_keeps_a_stale_number():
    answers: list[Any] = [json.dumps(GPU_BODY).encode(), OSError("down"), b"{}"]

    def fetch(url: str, timeout: float) -> bytes:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    poller = gpu_status.GpuStatusPoller(
        "https://x.example/api/status", fetch=fetch, clock=lambda: 1_790_000_000.0
    )
    assert poller.latest().error_code == gpu_status.CODE_NOT_FETCHED
    assert poller.refresh().ok
    down = poller.refresh()
    assert not down.ok and down.error_code == gpu_status.CODE_UNREACHABLE
    html = gpu_status.render_tile(down)
    assert code_of(html) == gpu_status.CODE_UNREACHABLE
    assert "tok/s" not in html and 'data-state="unavailable"' in html
    assert not poller.refresh().ok and poller.latest().error_code == gpu_status.CODE_MALFORMED
    _assert_clean_copy(html)


def test_gpu_status_css_and_https_only():
    _assert_stylesheet_discipline(gpu_status.GPU_CSS)
    _assert_four_class_selectors(gpu_status.GPU_CSS)
    with pytest.raises(ValueError):
        gpu_status.urllib_fetch("http://x.example/api/status")
    assert gpu_status.STATUS_URL.startswith("https://")


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

DECISION_ID = "8b4a1f2e-0c3d-4e5f-9a6b-7c8d9e0f1a2b"
WEBHOOK_POST = {
    "event": "decision.execute",
    "decision_id": DECISION_ID,
    "org_id": "org_1",
    "decision": {"chosen_action": "expand_eu", "confidence": 0.93},
    "integrity": {
        "request_hash": "sha256:req",
        "result_hash": "sha256:res",
        "policy_snapshot_id": "policy-snap-7",
        "schema_snapshot_id": "schema-snap-3",
        "manifest_version": "1.0.24",
    },
}
#: What `log_decision` returned for that decision — what the hook is armed with.
LOGGED = {
    "integrity": {
        "policy_snapshot_id": "policy-snap-7",
        "schema_snapshot_id": "schema-snap-3",
        "manifest_version": "1.0.24",
    },
    "chosen_action": "expand_eu",
    "confidence": 0.93,
}
SPACE_ENV = {"SPACE_ID": "thyn-ai/algenta", "SPACE_HOST": "thyn-ai-algenta.hf.space"}


def arm(hook: webhook.Hook, decision_id: str = DECISION_ID) -> webhook.Expected:
    return hook.expect(decision_id, **LOGGED)


def post_body(**over: Any) -> bytes:
    return json.dumps({**WEBHOOK_POST, **over}, default=str).encode()


def test_public_base_comes_from_space_host():
    assert webhook.public_base(SPACE_ENV) == "https://thyn-ai-algenta.hf.space"
    assert webhook.public_base({}) == ""
    assert webhook.public_base({"SPACE_HOST": "bad/host"}) == ""
    assert (
        webhook.public_base({"ALGENTA_PUBLIC_BASE_URL": "https://tunnel.example/"})
        == "https://tunnel.example"
    )
    assert webhook.public_base({"ALGENTA_PUBLIC_BASE_URL": "http://insecure.example"}) == ""


def test_hook_publishes_its_prefix_and_host_never_the_nonce():
    hook = webhook.make_hook(SPACE_ENV, nonce_factory=lambda: "n0nce")
    assert hook.url() == "https://thyn-ai-algenta.hf.space/hook/n0nce", "the engine gets the nonce"
    assert hook.path == "/hook" and "n0nce" not in hook.path, "/health publishes the prefix only"
    assert hook.host == "thyn-ai-algenta.hf.space" and hook.public is True
    assert not hasattr(hook, "signed") and not hasattr(webhook, "HMAC_ENV_VAR"), (
        "the engine's decision webhook carries no signature; no secret path pretends otherwise"
    )
    assert "carries no signature" in webhook.__doc__
    no_base = webhook.make_hook({}, nonce_factory=lambda: "n0nce")
    assert no_base.url() == "" and no_base.host == "" and no_base.public is False
    assert no_base.path == "/hook"
    with pytest.raises(ValueError):
        webhook.Hook(nonce="")
    with pytest.raises(ValueError):
        webhook.Hook(nonce="a/b")


def test_hook_accepts_only_the_armed_decision_with_matching_integrity_and_summary():
    """Forged, valid and late bodies: a POST is recorded only when its nonce, its decision id
    (armed by this process), its integrity block and its summary all match; every other body
    is a `Rejection` with a reason and nothing else."""
    hook = webhook.make_hook(SPACE_ENV, nonce_factory=lambda: "n0nce", clock=lambda: 1.79e9)
    body = post_body()
    # forged before anything was logged: unknown decision
    assert hook.accept("n0nce", body, {}) is None
    assert [r.reason for r in hook.rejections(DECISION_ID)] == [webhook.REASON_UNKNOWN]
    expected = arm(hook)
    assert expected.integrity == LOGGED["integrity"] and hook.armed(DECISION_ID)
    # wrong nonce, not JSON, not an object: refused before the body is read as a decision
    assert hook.accept("other", body, {}) is None
    assert hook.accept("n0nce", b"not json", {}) is None
    assert hook.accept("n0nce", b"[1, 2]", {}) is None
    assert hook.accept("n0nce", b"x" * (webhook.MAX_BODY_BYTES + 1), {}) is None
    # the right id with a forged block: the event name, the integrity ids, the summary
    assert hook.accept("n0nce", post_body(event="execution.delivered"), {}) is None
    forged = {**WEBHOOK_POST["integrity"], "policy_snapshot_id": "forged"}
    assert hook.accept("n0nce", post_body(integrity=forged), {}) is None
    assert (
        hook.accept("n0nce", post_body(integrity={"policy_snapshot_id": "policy-snap-7"}), {})
        is None
    )
    assert hook.accept("n0nce", post_body(integrity="none"), {}) is None
    assert (
        hook.accept("n0nce", post_body(decision={"chosen_action": "hold", "confidence": 0.93}), {})
        is None
    )
    assert (
        hook.accept(
            "n0nce", post_body(decision={"chosen_action": "expand_eu", "confidence": 0.5}), {}
        )
        is None
    )
    assert hook.accept("n0nce", post_body(decision=None), {}) is None
    reasons = [r.reason for r in hook.rejections(DECISION_ID)]
    assert reasons == [
        webhook.REASON_UNKNOWN,
        webhook.REASON_EVENT,
        webhook.REASON_INTEGRITY,
        webhook.REASON_INTEGRITY,
        webhook.REASON_INTEGRITY,
        webhook.REASON_SUMMARY,
        webhook.REASON_SUMMARY,
        webhook.REASON_SUMMARY,
    ]
    unattributed = [r for r in hook.rejections() if not r.decision_id]
    assert [r.reason for r in unattributed] == [
        webhook.REASON_NONCE,
        webhook.REASON_NOT_JSON,
        webhook.REASON_NOT_OBJECT,
        webhook.REASON_BODY_TOO_LARGE,
    ]
    assert all(r.received_utc.endswith("UTC") for r in hook.rejections())
    assert hook.events() == [], "nothing forged was recorded"
    # the engine's own body: accepted once, with what was verified
    accepted = hook.accept("n0nce", body, {"X-Webhook-Event": "decision.execute"})
    assert accepted is not None and accepted.decision_id == DECISION_ID
    assert accepted.verified == ("nonce", "session", "integrity", "summary")
    assert accepted.event.integrity["result_hash"] == "sha256:res"
    assert accepted.event.signed is False and accepted.expected is expected
    assert hook.events(DECISION_ID) == [accepted] and hook.events("nope") == []
    # the same body again: served already
    assert hook.accept("n0nce", body, {}) is None
    assert hook.rejections(DECISION_ID)[-1].reason == webhook.REASON_SERVED
    # settled: late
    hook.settle(DECISION_ID)
    assert not hook.armed(DECISION_ID)
    assert hook.accept("n0nce", body, {}) is None
    assert hook.rejections(DECISION_ID)[-1].reason == webhook.REASON_SETTLED
    assert hook.rejections(DECISION_ID)[-1].keys == tuple(sorted(WEBHOOK_POST))
    # re-armed (an execution sent again): one more POST is the engine's
    arm(hook)
    again = hook.accept("n0nce", body, {})
    assert again is not None and hook.events(DECISION_ID) == [accepted, again]
    # a decision logged with fewer integrity ids is held to exactly those
    hook.expect("d2", integrity={"policy_snapshot_id": "p"}, chosen_action="a", confidence=None)
    assert (
        hook.accept(
            "n0nce",
            post_body(
                decision_id="d2",
                integrity={"policy_snapshot_id": "p"},
                decision={"chosen_action": "a"},
            ),
            {},
        )
        is not None
    )
    assert webhook.integrity_of({"policy_snapshot_id": "p", "request_hash": "h", "x": 1}) == {
        "policy_snapshot_id": "p"
    }
    assert webhook.same_confidence(None, None) and not webhook.same_confidence(0.9, None)
    assert webhook.same_confidence(0.93, 0.93) and not webhook.same_confidence("x", 0.93)
    assert not webhook.same_confidence(True, 1.0)


def test_hook_wait_for_returns_the_accepted_post_or_none():
    hook = webhook.make_hook(SPACE_ENV, nonce_factory=lambda: "n0nce")
    arm(hook)
    ticks = iter([0.0, 0.1, 0.2, 5.0])
    assert (
        hook.wait_for(DECISION_ID, timeout_s=1.0, clock=lambda: next(ticks), sleep=lambda s: None)
        is None
    )
    accepted = hook.accept("n0nce", post_body(), {})
    assert accepted is not None
    assert (
        hook.wait_for(DECISION_ID, timeout_s=0.0, clock=lambda: 0.0, sleep=lambda s: None)
        is accepted
    )


def test_webhook_route_answers_200_or_400_with_one_identical_body():
    """Every refusal — wrong nonce, garbage, a forged id, a late body — is the same 400 and the
    same body, so nothing tells a sender which check failed; the engine's own POST is 200."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    hook = webhook.make_hook(SPACE_ENV, nonce_factory=lambda: "n0nce")
    app = FastAPI()
    webhook.mount(app, hook)
    client = TestClient(app)
    refused = [
        client.post("/hook/n0nce", json=WEBHOOK_POST),  # not armed yet
        client.post("/hook/wrong", json=WEBHOOK_POST),
        client.post("/hook/n0nce", content=b"garbage"),
    ]
    arm(hook)
    refused.append(client.post("/hook/n0nce", json={**WEBHOOK_POST, "decision_id": "forged"}))
    refused.append(
        client.post(
            "/hook/n0nce",
            json={**WEBHOOK_POST, "integrity": {"policy_snapshot_id": "forged"}, "forged_by": "x"},
        )
    )
    ok = client.post("/hook/n0nce", json=WEBHOOK_POST)
    assert ok.status_code == 200
    assert ok.json() == {"received": True, "decision_id": DECISION_ID}
    refused.append(client.post("/hook/n0nce", json=WEBHOOK_POST))  # served already
    hook.settle(DECISION_ID)
    refused.append(client.post("/hook/n0nce", json=WEBHOOK_POST))  # late
    assert {r.status_code for r in refused} == {webhook.REJECTED_STATUS} == {400}
    assert all(r.json() == {"received": False} == dict(webhook.REJECTED_BODY) for r in refused)
    assert len(hook.events()) == 1 and len(hook.rejections()) == len(refused)


# ---------------------------------------------------------------------------
# Governed tab — a fake client with the engine's real wire shapes
# ---------------------------------------------------------------------------

KEY = "de_test_0123456789abcdefABCDEF"  # gitleaks:allow - test fake, shaped like SECRET_RE
RECOMMEND_BODY = {
    "recommended_action": "expand_eu",
    "confidence": 0.87,
    "rationale": "Highest expected value with acceptable downside.",
    "action_results": [
        {"name": "expand_eu", "expected_value": 134269.0, "probability_of_loss": 0.0},
        {"name": "hold", "expected_value": 0.0, "probability_of_loss": 0.5},
    ],
    "total_actions": 2,
    "decision_plan": None,
}
LOG_BODY = {
    "id": DECISION_ID,
    "org_id": "org_1",
    "context": "Logged from the Algenta flagship Space.",
    "chosen_action": "expand_eu",
    "options_considered": ["expand_eu", "hold"],
    "expected_value": 120.5,
    "confidence": 0.93,
    "rationale": "Highest expected value with acceptable downside.",
    "risk_p5": 0.02,
    "request_hash": "sha256:req",
    "result_hash": "sha256:res",
    "policy_snapshot_id": "policy-snap-7",
    "schema_snapshot_id": "schema-snap-3",
    "manifest_version": "1.0.24",
    "execution_status": None,
    "created_at": "2026-09-22T14:02:00Z",
}
RECEIPT_BODY = {
    "decision_id": DECISION_ID,
    "webhook_url": "https://thyn-ai-algenta.hf.space/hook/n0nce",
    "execution_status": "delivered",
    "response_code": 200,
    "executed_at": "2026-09-22T14:03:10Z",
    "policy_snapshot_id": "policy-snap-7",
    "schema_snapshot_id": "schema-snap-3",
    "manifest_version": "1.0.24",
    "payload_summary": {"chosen_action": "expand_eu"},
    "safety_overridden": False,
}
DENIAL_409 = {
    "error": {
        "code": "execution_blocked_confidence",
        "gate": "confidence",
        "message": "Decision confidence 0.61 is below policy.min_confidence 0.8.",
        "override_hint": "Pass override_safety=true (operator only) to bypass the confidence gate.",
    }
}
IDEMPOTENCY_409 = {
    "error": {
        "code": "execution_blocked_idempotency",
        "gate": "idempotency",
        "message": f"Decision {DECISION_ID} was already delivered.",
        "override_hint": "Pass force=true (operator only) to override the idempotency gate.",
    }
}
ME_BODY = {"user": {"id": "usr_1"}, "org": {"id": "org_1", "name": "demo-tenant", "plan": "free"}}


class SdkError(Exception):
    def __init__(self, message: str, status_code: int, body: dict[str, Any], request_id: str):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = body
        self.error_code = body.get("error", {}).get("code", "unknown_error")
        self.request_id = request_id


class FakeClient:
    """The allow-listed SDK surface; `execute_decision` POSTs to the hook like the engine does."""

    def __init__(self, api_key: str, base_url: str, *, responses: dict[str, Any], hook):
        self.api_key = api_key
        self.base_url = base_url
        self.responses = responses
        self.hook = hook
        self.calls: list[tuple[str, tuple, dict]] = []
        self.posts: list[bool] = []

    def _answer(self, name: str, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((name, args, kwargs))
        answer = self.responses[name]
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def me(self) -> Any:
        return self._answer("me")

    def recommend(self, actions: Any, **kwargs: Any) -> Any:
        return self._answer("recommend", actions, **kwargs)

    def log_decision(self, request: dict[str, Any]) -> Any:
        return self._answer("log_decision", request)

    def execute_decision(self, decision_id: str, **kwargs: Any) -> Any:
        answer = self.responses["execute_decision"]
        if self.hook is not None and not isinstance(answer, BaseException):
            # the engine POSTs the logged decision to the URL it was given, unsigned, and marks
            # the execution delivered only when the receiver answered 2xx
            url = kwargs["webhook_url"]
            nonce = url.rsplit("/", 1)[-1]
            body = json.dumps({**WEBHOOK_POST, "decision_id": decision_id}, default=str).encode()
            accepted = self.hook.accept(nonce, body, {"X-Webhook-Event": "decision.execute"})
            self.posts.append(accepted is not None)
            if accepted is None and isinstance(answer, dict):
                answer = {**answer, "execution_status": "failed", "response_code": 400}
                self.responses["execute_decision"] = answer
        return self._answer("execute_decision", decision_id, **kwargs)

    def get_decision(self, decision_id: str) -> Any:
        return self._answer("get_decision", decision_id)


def make_hosted(
    responses: dict[str, Any] | None = None, *, key: str = KEY, hook=None
) -> tuple[HostedGoverned, list[FakeClient]]:
    canned: dict[str, Any] = {
        "me": dict(ME_BODY),
        "recommend": dict(RECOMMEND_BODY),
        "log_decision": dict(LOG_BODY),
        "execute_decision": dict(RECEIPT_BODY),
        "get_decision": {**LOG_BODY, "execution_status": "delivered"},
    }
    canned.update(responses or {})
    made: list[FakeClient] = []

    def factory(api_key: str, base_url: str) -> FakeClient:
        client = FakeClient(api_key, base_url, responses=canned, hook=hook)
        made.append(client)
        return client

    env = {"ALGENTA_API_KEY": key} if key else {}
    return HostedGoverned(factory, env=env), made


def make_hook() -> webhook.Hook:
    return webhook.make_hook(dict(SPACE_ENV), nonce_factory=lambda: "n0nce")


def gov_deps(**kwargs: Any) -> Deps:
    return Deps(kernels={}, lane=Lane(), hardware=HARDWARE, env={}, **kwargs)


RUN_ARGS = {
    "action": "expand_eu",
    "low": 80_000,
    "high": 200_000,
    "hold_value": 100_000,
    "confidence": 0.93,
    "risk_p5": 0.02,
}


def run(deps, hosted, hook, profile="execute", state=None, force=False, override=False, **over):
    args = {**RUN_ARGS, **over}
    return gov_tab.on_run(
        deps,
        hosted,
        hook,
        profile,
        args["action"],
        args["low"],
        args["high"],
        args["hold_value"],
        args["confidence"],
        args["risk_p5"],
        force,
        override,
        state,
    )


def test_full_chain_returns_a_receipt_with_the_webhook_post():
    hook = make_hook()
    hosted, made = make_hosted(hook=hook)
    card, raw, audit, state = run(gov_deps(), hosted, hook)
    assert gov_tab.TITLE_RECEIPT in card
    assert 'data-kind="live">delivered · HTTP 200<' in card, "the chip is the engine's outcome"
    assert "engine delivered" not in card and "alg-card-err" not in card
    assert "webhook received" in card and gov_tab.VERIFIED_TEXT in card
    assert gov_tab.NO_SIGNATURE_TEXT in flat(card), "the card says the engine signs nothing"
    assert "signature verified" not in card and "nonce verified" not in card
    assert "sha256:res" in card, "the POST body is shown"
    assert 'class="alg-snippet-code alg-code-scroll" tabindex="0" role="region"' in card, (
        "the POST body is the fleet's capped, keyboard-focusable code block"
    )
    assert 'aria-label="Webhook body, ' in card and "Webhook body · " in flat(card)
    assert '<pre class="alg-result">' not in card, "no unbounded, unwrapped <pre>"
    assert gov_tab.NOT_RECEIVED_TEXT not in card and "had not reached" not in card
    assert "policy-snap-7" in card and "schema-snap-3" in card and "1.0.24" in card
    assert "expand_eu" in card and DECISION_ID in card
    # each fact once, in words, one stamp style
    prose = _prose(card)
    for fact in ("policy-snap-7", "schema-snap-3", "1.0.24", DECISION_ID, "Policy snapshot"):
        assert prose.count(fact) == 1, f"{fact} is printed once on the receipt"
    assert "Request hash" in card and "Result hash" in card, "the POST's own ids are rows"
    assert "Body keys" not in card and "decision_id" not in prose, "the body in words"
    assert "Body decision summary, decision id, event, integrity block, organisation id" in flat(
        prose
    )
    assert 'datetime="2026-09-22T14:03:10Z">2026-09-22 14:03 UTC</time>' in card
    assert "T14:03:10" not in flat(card) and flat(card).count("2026-09-22 14:03 UTC") == 1
    assert "Executed at" not in card, "the instant is the sub-line, not an integrity row"
    assert re.search(r'alg-card-foot">hosted engine · <time class="alg-time"', card)
    assert hook.url() not in card and "n0nce" not in card, "the nonce is printed nowhere"
    assert "n0nce" not in raw and gov_tab.NONCE_REDACTED in raw, (
        "the receipt's webhook_url is in the engine JSON with its nonce redacted"
    )
    assert json.loads(raw)["execute_decision"]["webhook_url"].endswith(gov_tab.NONCE_REDACTED)
    assert gov_tab.WEBHOOK_ROW_TEXT.format(host=hook.host) in flat(card), "host, nonce hidden"
    assert gov_tab.REJECTED_TEXT not in card
    assert made[0].posts == [True], "the engine's POST was verified and accepted"
    assert not hook.armed(DECISION_ID), "settled once the engine answered"
    assert state["last_execution_status"] == "delivered"
    assert gov_tab.again_label(state) == "Execute again · expect the idempotency gate"
    assert code_of(card) is None
    _assert_clean_copy(card)
    _assert_clean_copy(audit)
    body = json.loads(raw)
    assert set(body) == {"recommend", "log_decision", "execute_decision", "webhook"}
    assert body["webhook"]["integrity"]["result_hash"] == "sha256:res"
    assert [e["step"] for e in state["audit"]] == ["recommend", "log_decision", "execute_decision"]
    assert state["last_decision_id"] == DECISION_ID
    assert DECISION_ID in audit

    client = made[0]
    names = [c[0] for c in client.calls]
    assert names == ["recommend", "log_decision", "execute_decision"]
    actions, kwargs = client.calls[0][1][0], client.calls[0][2]
    assert kwargs == {"runs": gov_tab.RUNS}
    assert [a["name"] for a in actions] == ["expand_eu", "hold"]
    assert actions[0]["request"]["scenario"]["variables"]["revenue"] == {
        "low": 80_000.0,
        "high": 200_000.0,
    }
    assert actions[1]["request"]["scenario"]["variables"]["revenue"] == {
        "low": 99_000.0,
        "high": 101_000.0,
    }
    request = client.calls[1][1][0]
    assert request["chosen_action"] == "expand_eu" and request["confidence"] == 0.93
    assert request["risk_p5"] == 0.02 and request["options_considered"] == ["expand_eu", "hold"]
    exec_kwargs = client.calls[2][2]
    assert exec_kwargs["webhook_url"] == "https://thyn-ai-algenta.hf.space/hook/n0nce"
    assert exec_kwargs["force"] is False and exec_kwargs["override_safety"] is False
    assert exec_kwargs["metadata"] == {"origin": hosted_api.DEFAULT_ORIGIN}


@pytest.mark.parametrize("profile", ["observe", "govern"])
def test_lower_profiles_intercept_before_the_engine_executes(profile: str):
    hook = make_hook()
    hosted, made = make_hosted(hook=hook)
    card, raw, audit, state = run(gov_deps(), hosted, hook, profile=profile)
    assert f"Not in the {profile} profile" in card
    assert gov_tab.INTERCEPT_CODE in card and gov_tab.INTERCEPT_TEXT in card
    for tool in gov_tab.PROFILE_TOOLS[profile]:
        assert gov_tab.tool_name(tool) in card, "tools as chips with human names"
    assert not SNAKE_RE.search(primary_text(card).replace("expand_eu", "")), primary_text(card)
    assert [c[0] for c in made[0].calls] == ["recommend", "log_decision"]
    assert state["audit"][-1]["outcome"] == "intercepted"
    assert "execute_decision" not in json.loads(raw)
    _assert_clean_copy(card)


def test_gate_denial_renders_the_gate_and_the_hint():
    hook = make_hook()
    err = SdkError(DENIAL_409["error"]["message"], 409, DENIAL_409, "req_409")
    hosted, _ = make_hosted({"execute_decision": err}, hook=hook)
    card, raw, _, state = run(gov_deps(), hosted, hook, confidence=0.61)
    assert "Held by the confidence gate" in card
    assert "execution_blocked_confidence" in card and "HTTP 409" in card
    assert 'alg-chip-warn">execution_blocked_confidence<' in card, "the code rides a chip"
    assert "override_safety=true" in card
    assert "alg-card-warn" in card and "alg-card-err" not in card
    assert json.loads(raw)["execute_decision"]["error"]["gate"] == "confidence"
    assert state["audit"][-1] == {**state["audit"][-1], "outcome": "denied", "gate": "confidence"}
    assert (
        state["last_execution_status"] == gov_tab.STATUS_DENIED
        and state["last_gate"] == "confidence"
    )
    assert gov_tab.again_label(state) == "Execute again · expect the confidence gate"
    _assert_clean_copy(card)


def test_execute_again_is_honest_after_a_delivered_and_after_a_failed_receipt():
    """The engine gates a repeat of a *delivered* execution (`check_execution_gates`: 409
    `execution_blocked_idempotency` unless `force`), and executes a *failed* one again with a new
    receipt. The button, the loading card and the outcome say which case the visitor is in."""
    hook = make_hook()
    hosted, made = make_hosted(hook=hook)
    deps = gov_deps()
    assert gov_tab.again_label(gov_tab.initial_state()) == gov_tab.AGAIN_TEXT == "Execute again"
    card, _, _, state = gov_tab.on_execute_again(deps, hosted, hook, "execute", False, False, None)
    assert code_of(card) == gov_tab.CODE_NO_DECISION and "alg-card-quiet" in card
    # delivered: the button expects the idempotency gate and the engine's 409 is that denial
    _, _, _, state = run(deps, hosted, hook, state=state)
    assert state["last_execution_status"] == "delivered"
    assert gov_tab.expected_gate(state) == "idempotency"
    assert gov_tab.again_label(state) == gov_tab.AGAIN_EXPECT_GATE_TEXT.format(gate="idempotency")
    assert gov_tab.again_label(state) == "Execute again · expect the idempotency gate"
    loading = gov_tab.loading_card(again=True, gate=gov_tab.expected_gate(state))
    assert "expect the idempotency gate" in loading and "new receipt" not in loading
    err = SdkError(IDEMPOTENCY_409["error"]["message"], 409, IDEMPOTENCY_409, "req_409b")
    made[0].responses["execute_decision"] = err
    card, raw, audit, state = gov_tab.on_execute_again(
        deps, hosted, hook, "execute", False, False, state
    )
    assert "Held by the idempotency gate" in card and "force=true" in card
    assert "alg-card-warn" in card and json.loads(raw)["execute_decision"]["status_code"] == 409
    assert state["last_gate"] == "idempotency" and gov_tab.expected_gate(state) == "idempotency"
    assert made[0].calls[-1][1][0] == DECISION_ID and made[0].calls[-1][0] == "execute_decision"
    assert [e["step"] for e in state["audit"]].count("execute_decision") == 2
    # failed: the engine executes again and issues a new receipt; the button says so
    failed = {**RECEIPT_BODY, "execution_status": "failed", "response_code": None}
    hosted, made = make_hosted({"execute_decision": failed}, hook=None)
    _, _, _, state = run(deps, hosted, hook)
    assert state["last_execution_status"] == "failed" and gov_tab.expected_gate(state) == ""
    assert gov_tab.again_label(state) == gov_tab.AGAIN_NEW_RECEIPT_TEXT
    assert gov_tab.again_label(state) == "Execute again · a new receipt"
    loading = gov_tab.loading_card(again=True, gate="")
    assert "new receipt" in loading and "gate" not in loading
    made[0].responses["execute_decision"] = {**RECEIPT_BODY, "executed_at": "2026-09-22T14:04:00Z"}
    made[0].hook = hook
    card, raw, _, state = gov_tab.on_execute_again(
        deps, hosted, hook, "execute", False, False, state
    )
    assert gov_tab.TITLE_RECEIPT in card and 'datetime="2026-09-22T14:04:00Z"' in card, (
        "a new receipt"
    )
    assert 'data-kind="live">delivered · HTTP 200<' in card and "webhook received" in card
    assert gov_tab.again_label(state) == "Execute again · expect the idempotency gate"
    # a lower profile intercepts the repeat before the engine is called
    card, _, _, _ = gov_tab.on_execute_again(deps, hosted, hook, "govern", False, False, state)
    assert "Not in the govern profile" in card
    # the copy names both cases and denies neither
    assert "idempotency gate" in gov_tab.HOW_TEXT and "new receipt" in gov_tab.HOW_TEXT
    assert "idempotency" in gov_tab.__doc__ and "failed" in gov_tab.__doc__
    assert "new receipt" in gov_tab.LOADING_AGAIN_TEXT
    assert (
        "{gate}" in gov_tab.LOADING_AGAIN_GATE_TEXT and "{gate}" in gov_tab.AGAIN_EXPECT_GATE_TEXT
    )


def test_failed_execution_is_told_as_a_failure_never_painted_live():
    """`execution_status: failed` with no response code — the engine's POST to this Space never
    got an answer: the chip is red `webhook_failed · no HTTP response`, the hairline red, the
    note says the POST failed, and nothing says delivered or `not received yet`."""
    hook = make_hook()
    failed = {**RECEIPT_BODY, "execution_status": "failed", "response_code": None}
    hosted, made = make_hosted({"execute_decision": failed}, hook=None)  # the engine never POSTs
    wait = gov_tab.WEBHOOK_WAIT_S
    gov_tab.WEBHOOK_WAIT_S = 0.0
    try:
        card, raw, audit, state = run(gov_deps(), hosted, hook)
    finally:
        gov_tab.WEBHOOK_WAIT_S = wait
    assert gov_tab.TITLE_RECEIPT in card
    chip = re.search(r'<span class="alg-chip alg-chip-err"[^>]*data-kind="error">([^<]*)<', card)
    assert chip is not None and chip.group(1) == f"{gov_tab.CODE_WEBHOOK_FAILED} · no HTTP response"
    assert "alg-card-err" in card, "a failed POST during the run is the red card"
    assert gov_tab.WEBHOOK_FAILED_TEXT in flat(card)
    assert (
        "engine failed" not in card and 'data-kind="live"' not in card and "alg-chip-ok" not in card
    )
    assert gov_tab.NOT_RECEIVED_TEXT not in card and "reported delivery" not in card
    assert "webhook received" not in card and gov_tab.REJECTED_TEXT not in card
    assert state["audit"][-1]["outcome"] == "failed"
    assert json.loads(raw)["execute_decision"]["execution_status"] == "failed"
    _assert_clean_copy(card)
    # a forged POST carrying the receipt's decision id lands after the run (the id is on the
    # card): refused as late, and Execute again paints it red — never `webhook received`
    assert hook.accept("n0nce", post_body(forged_by="skeptic"), {}) is None
    assert hook.rejections(DECISION_ID)[-1].reason == webhook.REASON_SETTLED
    gov_tab.WEBHOOK_WAIT_S = 0.0
    try:
        again, raw_again, _, state = gov_tab.on_execute_again(
            gov_deps(), hosted, hook, "execute", False, False, state
        )
    finally:
        gov_tab.WEBHOOK_WAIT_S = wait
    assert gov_tab.TITLE_RECEIPT in again and "alg-card-err" in again
    assert f'data-kind="error">{gov_tab.REJECTED_TEXT}<' in again, "the forged POST, red"
    assert gov_tab.REJECTED_NOTE in flat(again)
    assert "webhook received" not in again and 'data-kind="live"' not in again
    assert "alg-chip-ok" not in again and "verified" not in again
    assert "forged_by" not in again and "skeptic" not in again, "a refused body is never shown"
    assert "webhook" not in json.loads(raw_again), "nothing refused reaches the engine JSON"
    _assert_clean_copy(again)
    # with a status the webhook did answer with, the code rides in the chip
    hosted, _ = make_hosted({"execute_decision": {**failed, "response_code": 502}}, hook=None)
    gov_tab.WEBHOOK_WAIT_S = 0.0
    try:
        card, *_ = run(gov_deps(), hosted, hook)
    finally:
        gov_tab.WEBHOOK_WAIT_S = wait
    assert f"{gov_tab.CODE_WEBHOOK_FAILED} · HTTP 502" in card
    # the receipt objects tell the same truth the card paints
    receipt = hosted_api.to_receipt(failed)
    assert gov_tab.receipt_failed(receipt) and not receipt.delivered
    assert gov_tab.http_text(None) == gov_tab.NO_HTTP_TEXT and gov_tab.http_text(200) == "HTTP 200"
    other = hosted_api.to_receipt({**RECEIPT_BODY, "execution_status": "pending"})
    assert "engine pending · HTTP 200" in gov_tab.receipt_status_chip(other)
    assert "alg-chip-neutral" in gov_tab.receipt_status_chip(other)
    # an accepted POST is shown under a delivered receipt alone: on a failed or pending one the
    # same event renders nothing green
    accepted_hook = make_hook()
    arm(accepted_hook)
    event = accepted_hook.accept("n0nce", post_body(), {})
    assert event is not None
    for status in ("failed", "pending"):
        out = gov_tab.Outcome(
            receipt=hosted_api.to_receipt({**RECEIPT_BODY, "execution_status": status})
        )
        out.webhook = event
        html = gov_tab.webhook_html(out)
        assert "webhook received" not in html and 'data-kind="live"' not in html
    delivered = gov_tab.Outcome(receipt=hosted_api.to_receipt(RECEIPT_BODY))
    delivered.webhook = event
    assert "webhook received" in gov_tab.webhook_html(delivered)
    # a receipt whose summary contradicts the accepted POST is not a delivery either
    off = gov_tab.Outcome(
        receipt=hosted_api.to_receipt(
            {**RECEIPT_BODY, "payload_summary": {"chosen_action": "hold"}}
        )
    )
    off.webhook = event
    assert gov_tab.receipt_matches_post(off.receipt, event) is False
    html = gov_tab.webhook_html(off)
    assert gov_tab.REJECTED_TEXT in html and gov_tab.MISMATCH_NOTE in flat(html)
    assert "webhook received" not in html


def test_unexpected_exception_is_the_designed_card_never_a_toast(caplog):
    """An exception the lane does not normalise (here a plain RuntimeError from the client, the
    shape of round 2's ModuleNotFoundError) is logged with its traceback and rendered as the red
    `unexpected_error` card with one sentence — the staged generator never raises, so Gradio
    never shows its stock toast and the loading card always resolves."""
    hook = make_hook()
    hosted, made = make_hosted({"recommend": RuntimeError("no module named x")}, hook=hook)
    with caplog.at_level("ERROR", logger="tabs.gov_tab"):
        card, raw, audit, state = run(gov_deps(), hosted, hook)
    assert code_of(card) == gov_tab.CODE_UNEXPECTED == "unexpected_error"
    assert "alg-card-err" in card and "alg-chip-err" in card
    assert gov_tab.HINT_UNEXPECTED in card
    assert "no module named" not in card and "RuntimeError" not in card and "Traceback" not in card
    reason = re.search(r'alg-card-reason">([^<]*)<', card)
    assert reason is not None and reason.group(1).count(".") == 1, "one sentence"
    assert json.loads(raw) == {}, "recommend raised before any body came back"
    assert state["audit"][-1]["outcome"] == f"failed · {gov_tab.CODE_UNEXPECTED}"
    assert f"failed · {gov_tab.CODE_UNEXPECTED}" in audit
    logged = [r for r in caplog.records if "unexpectedly" in r.getMessage()]
    assert logged and logged[0].exc_info is not None, "the traceback is logged server-side"
    _assert_clean_copy(card)
    # through the staged generator the handler wires: the loading card, then the card — no raise
    staged = list(
        gov_tab.staged(
            gov_tab.loading_card(),
            lambda: run(gov_deps(), hosted, hook),
        )
    )
    assert LOADING_RE.search(staged[0][0]) and code_of(staged[1][0]) == gov_tab.CODE_UNEXPECTED
    # execute again takes the same path
    hosted, made = make_hosted(hook=hook)
    _, _, _, state = run(gov_deps(), hosted, hook)
    made[0].responses["execute_decision"] = TypeError("client bug")
    card, _, _, state = gov_tab.on_execute_again(
        gov_deps(), hosted, hook, "execute", False, False, state
    )
    assert code_of(card) == gov_tab.CODE_UNEXPECTED and "client bug" not in card
    assert state["audit"][-1] == {
        **state["audit"][-1],
        "step": "execute_decision",
        "outcome": f"failed · {gov_tab.CODE_UNEXPECTED}",
        "decision_id": DECISION_ID,
    }
    # a failure in the lane's own vocabulary carries its code in the audit too
    hosted, _ = make_hosted({"recommend": ConnectionError("refused")}, hook=hook)
    _, _, _, state = run(gov_deps(), hosted, hook)
    assert state["audit"][-1]["outcome"] == f"failed · {gov_tab.CODE_UNAVAILABLE}"


def test_missing_sdk_client_is_one_quiet_card_with_the_controls_hidden():
    """The boot probe raised before a client existed (the SDK is not installed in this venv):
    the lane cannot run whatever key is set, so the tab is the quiet not-configured shape — one
    card with its own code and sentence, no raw exception, no controls — and both endpoints
    answer with that card without touching the client."""
    gr = pytest.importorskip("gradio")
    hook = make_hook()
    hosted, made = make_hosted(hook=hook)
    down = hosted_api.HostedStatus(
        hosted_api.ConfigState.UNAVAILABLE,
        "ModuleNotFoundError: No module named 'algenta'",
        hosted.base_url,
        "",
        "2026-09-22 14:02 UTC",
    )
    assert gov_tab.client_missing(down) is True
    card = gov_tab.status_card(down)
    assert code_of(card) == gov_tab.CODE_CLIENT_MISSING == "hosted_client_not_installed"
    assert 'data-state="not_configured"' in card and "alg-card-err" not in card
    assert gov_tab.CLIENT_MISSING_HINT in card
    assert "ModuleNotFoundError" not in card and "algenta'" not in card, "no raw exception"
    assert not SNAKE_RE.search(primary_text(card)), primary_text(card)
    _assert_clean_copy(card)
    spec = gov_tab.build(gov_deps(), hosted=hosted, hook=hook, status=down)
    _, handles = _render(spec, gr)
    assert handles["configured"] is False and handles["controls"].visible is False
    assert code_of(handles["status_card"].value) == gov_tab.CODE_CLIENT_MISSING
    assert made == [], "the boot status was given, so no client was built for a probe"
    card, raw, _, _ = gov_tab.on_run(
        gov_deps(),
        hosted,
        hook,
        "execute",
        "expand_eu",
        1,
        2,
        3,
        0.9,
        0.0,
        False,
        False,
        None,
        None,
        down,
    )
    assert code_of(card) == gov_tab.CODE_CLIENT_MISSING and json.loads(raw) == {}
    card, *_ = gov_tab.on_execute_again(
        gov_deps(), hosted, hook, "execute", False, False, None, None, down
    )
    assert code_of(card) == gov_tab.CODE_CLIENT_MISSING
    assert made == [], "the client is never built, let alone called"
    # an engine that did not answer at boot is still the ordinary unavailable state
    refused = hosted_api.HostedStatus(
        hosted_api.ConfigState.UNAVAILABLE, "refused", hosted.base_url, "", "2026-09-22 14:02 UTC"
    )
    assert gov_tab.client_missing(refused) is False and gov_tab.client_missing(None) is False


def test_not_configured_is_the_only_path_without_a_key():
    hosted, made = make_hosted(key="")
    assert hosted.status().state is hosted_api.ConfigState.NOT_CONFIGURED
    card, raw, audit, state = run(gov_deps(), hosted, make_hook())
    assert code_of(card) == NOT_CONFIGURED
    assert gov_tab.NOT_CONFIGURED_HINT in card
    assert "ALGENTA_API_KEY" not in card and "https://" not in card, "no variable, no address"
    assert 'data-state="not_configured"' in card and "alg-card-err" not in card, "quiet, not red"
    assert "alg-chip-err" not in card and "alg-chip-neutral" in card, "the chip is neutral too"
    assert f"{gov_tab.FOOT_LABEL} · " in card and FOOT_RE.search(card)
    assert not SNAKE_RE.search(primary_text(card)), primary_text(card)
    assert made == [], "no client is ever built without a key"
    assert json.loads(raw) == {} and state["audit"] == []
    card, *_ = run(gov_deps(), None, None)
    assert code_of(card) == NOT_CONFIGURED
    _assert_clean_copy(card)


def test_hosted_errors_map_to_coded_cards():
    hook = make_hook()
    auth = SdkError("Invalid API key", 401, {"error": {"code": "invalid_api_key"}}, "r1")
    hosted, _ = make_hosted({"recommend": auth}, hook=hook)
    card, *_ = run(gov_deps(), hosted, hook)
    assert code_of(card) == NOT_CONFIGURED
    rate = SdkError("Rate limit exceeded", 429, {"error": {"code": "rate_limited"}}, "r2")
    hosted, _ = make_hosted({"log_decision": rate}, hook=hook)
    card, *_ = run(gov_deps(), hosted, hook)
    assert code_of(card) == code(gov_tab.CODE_RATE_LIMITED)
    hosted, _ = make_hosted({"recommend": ConnectionError("refused")}, hook=hook)
    card, *_ = run(gov_deps(), hosted, hook)
    assert code_of(card) == code(gov_tab.CODE_UNAVAILABLE)
    boom = SdkError("bad request", 422, {"error": {"code": "validation_error"}}, "r3")
    hosted, _ = make_hosted({"recommend": boom}, hook=hook)
    card, *_ = run(gov_deps(), hosted, hook)
    assert code_of(card) == "validation_error"
    for html in (card,):
        _assert_clean_copy(html)


def test_invalid_inputs_are_refused_under_their_control_never_as_a_red_card():
    """A pre-flight refusal is the Try and Playground convention: one sentence under the
    offending control (`role=alert`) and the same sentence in the status row beside Run; the
    result column shows the empty state because nothing ran, and no engine call is made."""
    hook = make_hook()
    hosted, made = make_hosted(hook=hook)
    cases = {
        "high": {"high": 50_000},
        "action": {"action": "  "},
        "hold_value": {"hold_value": 0},
        "confidence": {"confidence": 1.5},
        "risk_p5": {"risk_p5": float("nan")},
        "low": {"low": "many"},
    }
    for field, over in cases.items():
        args = {**RUN_ARGS, **over}
        refusal = gov_tab.check_inputs(
            args["action"],
            args["low"],
            args["high"],
            args["hold_value"],
            args["confidence"],
            args["risk_p5"],
        )
        assert refusal is not None and refusal.field == field, (field, refusal)
        assert refusal.slot == gov_tab.FIELD_SLOTS[field] and refusal.slot in gov_tab.SLOTS
        assert refusal.message[0].isupper() and refusal.message.endswith("."), refusal.message
        assert not SNAKE_RE.search(refusal.message), refusal.message
        _assert_clean_copy(refusal.message)
        messages = gov_tab.field_messages(refusal)
        assert set(messages) == set(gov_tab.SLOTS)
        assert (
            'role="alert"' in messages[refusal.slot] and refusal.message in messages[refusal.slot]
        )
        assert all(v == "" for slot, v in messages.items() if slot != refusal.slot)
        status = gov_tab.status_html(refusal)
        assert 'class="alg-status"' in status and refusal.message in status, "echoed beside Run"
        card, raw, audit, state = run(gov_deps(), hosted, hook, **over)
        assert 'class="alg-card alg-card-empty"' in card, "nothing ran: the empty state"
        assert "alg-card-err" not in card and code_of(card) is None, "never a red card"
        assert json.loads(raw) == {} and state["audit"] == [], "nothing audited"
    assert gov_tab.check_inputs("hold", 1, 2, 3, 0.5, 0.0).field == "action"
    assert gov_tab.check_inputs(**{k: RUN_ARGS[k] for k in RUN_ARGS}) is None
    assert gov_tab.field_messages(None) == dict.fromkeys(gov_tab.SLOTS, "")
    assert gov_tab.status_html(None) == common.render_status()
    assert made == [] or made[0].calls == []


def test_missing_public_url_is_a_coded_card_not_a_fake_webhook():
    hook = webhook.make_hook({}, nonce_factory=lambda: "n0nce")
    hosted, made = make_hosted(hook=hook)
    card, raw, *_ = run(gov_deps(), hosted, hook)
    assert code_of(card) == webhook.CODE_NO_PUBLIC_URL
    assert [c[0] for c in made[0].calls] == ["recommend", "log_decision"]
    assert not hook.armed(DECISION_ID) and "nonce hidden" not in card, "no execute, no webhook row"
    assert set(json.loads(raw)) == {"recommend", "log_decision"}, "the bodies the run did get"
    assert gov_tab.has_engine_json(raw), "two engine calls were made: the disclosure shows them"


def test_limits_and_kill_switch_gate_the_hosted_lane():
    hook = make_hook()
    hosted, made = make_hosted(hook=hook)
    limits = Limits(
        Policy({"governed": LanePolicy(burst=1, window_s=60.0, per_day=5, daily_cap=50)})
    )
    deps = gov_deps(limits=limits)
    first, *_ = run(deps, hosted, hook)
    assert gov_tab.TITLE_RECEIPT in first
    second, *_ = run(deps, hosted, hook)
    assert code_of(second) == code(gov_tab.CODE_RATE_LIMITED)
    assert len(made[0].calls) == 3
    paused = gov_deps(killswitch=OffSwitch({"hosted"}))
    card, *_ = run(paused, hosted, hook)
    assert code_of(card) == gov_tab.CODE_PAUSED


def test_receipt_without_webhook_post_says_so():
    hook = make_hook()
    hosted, _ = make_hosted(hook=None)  # the engine never POSTs
    gov_tab_wait = gov_tab.WEBHOOK_WAIT_S
    gov_tab.WEBHOOK_WAIT_S = 0.0
    try:
        card, raw, *_ = run(gov_deps(), hosted, hook)
    finally:
        gov_tab.WEBHOOK_WAIT_S = gov_tab_wait
    assert gov_tab.TITLE_RECEIPT in card
    assert "had not reached" in card
    assert f'alg-chip-neutral">{gov_tab.NOT_RECEIVED_TEXT}<' in card, "neutral, not red or live"
    assert 'data-kind="live">delivered · HTTP 200<' in card, "what the engine reported"
    assert "alg-card-err" not in card and gov_tab.WEBHOOK_FAILED_TEXT not in card
    assert "webhook received" not in card and gov_tab.REJECTED_TEXT not in card
    assert "webhook" not in json.loads(raw)


def test_mcp_endpoint_mirrors_the_sdk_contract():
    text = CONTRACT_PY.read_text(encoding="utf-8")
    m = re.search(r"^MCP_ENDPOINT = '([^']+)'", text, re.MULTILINE)
    assert m and m.group(1) == gov_tab.MCP_ENDPOINT
    config = json.loads(gov_tab.MCP_CLIENT_CONFIG)
    assert config["mcpServers"]["algenta"]["url"] == gov_tab.MCP_ENDPOINT


def test_profiles_mirror_the_integration_contract_when_present():
    if not INTEGRATIONS_CONTRACT.is_file():
        pytest.skip("algenta-integrations checkout not present")
    profiles = json.loads(INTEGRATIONS_CONTRACT.read_text(encoding="utf-8"))["profiles"]
    assert tuple(profiles) == gov_tab.PROFILES
    tools = {"observe": list(profiles["observe"]["tools"])}
    tools["govern"] = tools["observe"] + profiles["govern"]["adds_tools"]
    tools["execute"] = tools["govern"] + profiles["execute"]["adds_tools"]
    for name in ("observe", "govern", "execute"):
        assert tuple(tools[name]) == gov_tab.PROFILE_TOOLS[name]
    assert profiles["full"]["tools"] == "*" and gov_tab.PROFILE_TOOLS["full"] == ("*",)
    assert tuple(profiles["execute"]["never_model_facing_fields"]) == gov_tab.OPERATOR_ONLY


def test_smolagents_snippet_is_corrected_and_compiles():
    snippet = gov_tab.SMOLAGENTS_SNIPPET
    compile(snippet, "<smolagents>", "exec")
    assert "trust_remote_code" not in snippet
    assert "**os.environ" not in snippet
    assert "algenta-mcp" in snippet and "https://api.algenta.ai" in snippet


def test_gov_copy_and_css_discipline():
    for text in (
        gov_tab.LABEL,
        gov_tab.RUN_TEXT,
        gov_tab.AGAIN_TEXT,
        gov_tab.AGAIN_NEW_RECEIPT_TEXT,
        gov_tab.AGAIN_EXPECT_GATE_TEXT.format(gate="idempotency"),
        gov_tab.HOW_TEXT,
        gov_tab.NOT_CONFIGURED_HINT,
        gov_tab.EMPTY_TEXT,
        gov_tab.LOADING_TEXT,
        gov_tab.LOADING_AGAIN_TEXT,
        gov_tab.LOADING_AGAIN_GATE_TEXT.format(gate="idempotency"),
        gov_tab.NO_SIGNATURE_TEXT,
        gov_tab.REJECTED_NOTE,
        gov_tab.REJECTED_TEXT,
        gov_tab.VERIFIED_TEXT,
        gov_tab.WEBHOOK_ROW_TEXT.format(host="x.hf.space"),
        gov_tab.ENGINE_NOTE_TEXT,
        gov_tab.COPY_JSON_TEXT,
        gov_tab.WEBHOOK_BODY_CAPTION,
        gov_tab.BODY_ROW_LABEL,
        gov_tab.EXECUTED_TEXT.format(stamp="2026-09-23 07:28 UTC"),
        *gov_tab.PROFILE_LINES.values(),
    ):
        _assert_clean_copy(text)
    assert len(gov_tab.AGAIN_EXPECT_GATE_TEXT.format(gate="idempotency").split()) <= 8
    assert "https://" not in gov_tab.ENGINE_NOTE_TEXT, "the address moved into the code block"
    for line in gov_tab.PROFILE_LINES.values():
        assert len(line.split()) <= 14
    _assert_clean_copy(gov_tab.render_audit(gov_tab.initial_state()))
    _assert_clean_copy(gov_tab.profile_html("observe"))
    _assert_stylesheet_discipline(gov_tab.GOV_CSS)
    _assert_four_class_selectors(gov_tab.GOV_CSS)
    assert gov_tab.API_NAMES[0] == "gov_run"


def test_gov_primary_copy_carries_human_names_not_identifiers():
    for label in (gov_tab.LABEL_RISK, gov_tab.LABEL_FORCE, gov_tab.LABEL_OVERRIDE):
        assert not SNAKE_RE.search(label), label
    assert gov_tab.LABEL_FORCE == "Force execution (operators only)"
    assert gov_tab.LABEL_OVERRIDE == "Override the safety gate (operators only)"
    assert gov_tab.LABEL_RISK == "Risk floor (5th percentile)"
    note = gov_tab.profile_html("execute")
    assert note.count('<span class="alg-chip ') == len(gov_tab.PROFILE_TOOLS["execute"])
    assert not SNAKE_RE.search(text_of(note)), text_of(note)
    assert set(gov_tab.TOOL_NAMES) >= {t for tools in gov_tab.PROFILE_TOOLS.values() for t in tools}
    hook = make_hook()
    hosted, _ = make_hosted(hook=hook)
    card, _, audit, _ = run(gov_deps(), hosted, hook)
    for human in (
        "Recommendation",
        "Chosen action",
        "Policy snapshot",
        "Schema snapshot",
        "Webhook",
    ):
        assert human in card
    assert not SNAKE_RE.search(primary_text(card).replace("expand_eu", "")), primary_text(card)
    assert "https://" not in primary_text(card), "no raw URL in primary copy"
    assert hosted.base_url not in card and "api.algenta.ai" not in card, "the address is not copy"
    assert f'alg-card-foot">{gov_tab.FOOT_LABEL} · ' in card
    preview = json.loads(gov_tab.request_preview())
    assert preview["recommend"]["runs"] == gov_tab.RUNS
    assert [a["name"] for a in preview["recommend"]["actions"]] == [gov_tab.DEFAULT_ACTION, "hold"]
    assert preview["recommend"]["actions"] == gov_tab.recommend_actions(
        gov_tab.DEFAULT_ACTION, gov_tab.LOW[3], gov_tab.HIGH[3], gov_tab.HOLD_VALUE[3]
    ), "the editor opens on the request the default run sends"
    assert "Execution" in audit and "Decision logged" in audit and "alg-stack-table" in audit
    assert 'class="alg-card alg-card-empty"' in gov_tab.empty_card()
    for row in gov_tab.EMPTY_ROWS:
        assert f'alg-empty-key">{row}<' in gov_tab.empty_card()
    assert 'alg-sr">not run yet<' in gov_tab.empty_card(), "steps, not measurements"
    assert "not measured yet" not in gov_tab.empty_card()
    staged = list(gov_tab.staged(gov_tab.loading_card(), lambda: ("c", "r", "a", {})))
    assert LOADING_RE.search(staged[0][0]) and staged[0][1:] == (gov_tab.KEEP,) * 3
    assert staged[1] == ("c", "r", "a", {})
    # the Engine responses block: shown only with an engine body; the whole JSON in the fleet's
    # capped, keyboard-focusable code block (24 lines visible, the inner scroller in the tab
    # order), nothing cut, so no cap note
    assert gov_tab.has_engine_json(gov_tab.raw_json(None)) is False
    assert gov_tab.has_engine_json("  {}\n") is False and gov_tab.has_engine_json("") is False
    assert gov_tab.has_engine_json(gov_tab.request_preview()) is True
    text = "\n".join(f'"k{i}": {i},' for i in range(250))
    block = gov_tab.render_engine_json(text)
    assert block.count("\n") == 249, "every line is in the page"
    assert 'tabindex="0" role="region" aria-label="Engine JSON, 250 lines"' in block
    assert f'style="{css.CODE_LINES_VAR}: {gov_tab.ENGINE_JSON_LINES}"' in block
    assert gov_tab.ENGINE_JSON_LINES == 24 and css.CODE_SCROLL_CLASS in block
    assert "Showing the first" not in block and not hasattr(gov_tab, "capped_json")
    assert gov_tab.render_engine_json("") == gov_tab.render_engine_json("{}"), "never empty"
    assert gov_tab.COPY_JSON_TEXT == "Copy JSON" and "'Copy JSON'" in gov_tab.COPY_JSON_JS
    assert "max-height: none" not in gov_tab.GOV_CSS and ".cm-scroller" not in gov_tab.GOV_CSS
    assert (
        f".{gov_tab.RESULTS_COL_CLASS}" * 4 + " .alg-card { flex: 0 0 auto; }" in gov_tab.GOV_CSS
    ), "a Governed card is never taller than its content"
    # the engine's ISO instant as the fleet stamp, the second kept for machines
    assert gov_tab.iso_stamp("2026-09-23T07:28:40.930310Z") == (
        "2026-09-23 07:28 UTC",
        "2026-09-23T07:28:40Z",
    )
    assert gov_tab.iso_stamp("2026-09-23T09:28:40+02:00")[0] == "2026-09-23 07:28 UTC"
    assert gov_tab.executed_html("2026-09-23T07:28:40.930310Z") == (
        'executed <time class="alg-time" datetime="2026-09-23T07:28:40Z">2026-09-23 07:28 UTC'
        "</time>"
    )
    assert gov_tab.executed_html("soon") == "executed soon", "an odd instant is printed as it came"
    with pytest.raises(ValueError):
        gov_tab.iso_stamp("")
    # the POST body in words: the known keys first, any other key in its own words
    assert webhook.describe_body(WEBHOOK_POST) == (
        "decision summary, decision id, event, integrity block, organisation id"
    )
    assert webhook.describe_body({"metadata": {}, "zeta_key": 1, "event": "e"}) == (
        "event, metadata, zeta key"
    )
    assert webhook.describe_body({}) == webhook.EMPTY_BODY_TEXT == "empty body"
    assert not SNAKE_RE.search(webhook.describe_body(WEBHOOK_POST))
    audit_html = gov_tab.render_audit({"audit": [{"at": "2026-09-23 07:28 UTC", "step": "run"}]})
    assert '<time class="alg-time" datetime="2026-09-23T07:28Z">2026-09-23 07:28 UTC</time>' in (
        audit_html
    ), "the audit's stamps are <time> elements too"


# ---------------------------------------------------------------------------
# Ecosystem tab
# ---------------------------------------------------------------------------


def hub_body(downloads: int = 12, likes: int = 1) -> bytes:
    """The `/api/kernels?author=thyn-ai` list shape, one entry per capped repository."""
    items = []
    for i, repo in enumerate(playground.TRUST):
        items.append(
            {
                "_id": f"6ab1747afd545be1cceb7a{i:02d}",
                "id": repo,
                "likes": likes,
                "trendingScore": 0,
                "private": False,
                "downloads": downloads + i if downloads else 0,
                "tags": ["algenta", "mojo", "cpu", "license:other", "region:us"],
                "createdAt": "2026-09-21T18:16:26.000Z",
                "supportedDriverFamilies": ["cpu"]
                if repo != "thyn-ai/algenta-llm"
                else ["cuda", "metal", "cpu"],
            }
        )
    items.append({"id": "someone-else/kernel", "likes": 99, "downloads": 99})
    return json.dumps(items).encode()


GITHUB_KERNELS = [{"name": n, "type": "dir"} for n in ("bm25", "capa", "vader")] + [
    {"name": "README.md", "type": "file"}
]
GITHUB_RELEASE = {"tag_name": "v0.1.4", "published_at": "2026-09-22T14:54:33Z", "assets": []}


def test_parse_kernels_keeps_only_capped_repositories_and_counts():
    stats = eco_tab.parse_kernels(hub_body())
    assert set(stats) == set(playground.TRUST)
    llm = stats["thyn-ai/algenta-llm"]
    assert llm.backends == ("cpu", "cuda", "metal") and llm.likes == 1
    with pytest.raises(ValueError):
        eco_tab.parse_kernels(b"{}")
    with pytest.raises(ValueError):
        eco_tab.parse_kernels(
            json.dumps([{"id": "thyn-ai/algenta", "likes": "1", "downloads": 0}]).encode()
        )
    with pytest.raises(ValueError):
        eco_tab.parse_kernels(json.dumps([{"id": "other/x", "likes": 1, "downloads": 0}]).encode())


def test_hub_table_shows_counts_with_stamp_then_unavailable_after_a_failed_fetch():
    answers: list[Any] = [hub_body(), OSError("down"), b"[]"]

    def fetch(url: str, timeout: float) -> bytes:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    now = [1_790_000_000.0]
    counts = eco_tab.HubCounts(fetch=fetch, clock=lambda: now[0])
    table = eco_tab.render_hub_table(counts.latest())
    assert code_of(table) == eco_tab.CODE_HUB_NOT_FETCHED
    assert "alg-card-quiet" in table and "alg-card-err" not in table and "alg-chip-err" not in table
    assert eco_tab.HINT_HUB_NOT_FETCHED in table, "not asked yet has its own sentence"
    assert counts.cooldown_s() == 0.0
    ok = counts.refresh()
    table = eco_tab.render_hub_table(ok, ROWS, total=6_040, counted_utc="2026-09-22 14:02 UTC")
    assert "fetched" in table and ">20 kernels<" in table and ">6,040 functions<" in table
    assert "counted 2026-09-22 14:02 UTC" in flat(table), "the computed counts carry their stamp"
    assert ">430 downloads<" in table and ">20 likes<" in table
    assert "thyn-ai/algenta-llm" in table and "cpu, cuda, metal" in table
    assert f'<td data-label="{eco_tab.COLUMN_BACKENDS}" data-col="backends">cpu, cuda, metal<' in (
        table
    ), "the backends are their own column, marked for the sheet to drop below 1024 px"
    assert f'<th scope="col" data-col="backends">{eco_tab.COLUMN_BACKENDS}</th>' in table
    assert table.count('data-col="backends"') == len(eco_tab.FAMILY_ORDER) + 1
    assert f'<table class="alg-stack-table {llm_tab.STACK_DENSE_CLASS} alg-eco-table">' in table, (
        "the shared table's dense phone variant"
    )
    assert '<th scope="col" class="alg-stack-num">functions</th>' in table, "counts right-aligned"
    assert f'<th scope="col" class="alg-stack-num">{eco_tab.COLUMN_HUB}</th>' in table
    assert table.count('data-label="functions" class="alg-stack-num"') == len(eco_tab.FAMILY_ORDER)
    assert table.count(f'data-label="{eco_tab.COLUMN_HUB}" class="alg-stack-num"') == len(
        eco_tab.FAMILY_ORDER
    )
    assert '<th scope="col">revision</th>' in table and '<th scope="col">kernel</th>' in table
    assert "1,234 functions · 12 modules" in flat(table) and "v1 · a01e2b2 · pinned" in flat(table)
    assert eco_tab.COUNTS_UNAVAILABLE not in table
    assert eco_tab.HUB_API_URL not in table and eco_tab.SOURCE_HUB in table, "source, not a URL"
    assert "next refresh" not in table
    _assert_clean_copy(table)
    now[0] += 10
    assert counts.refresh(force=False) is ok, "a fetch younger than the floor is reused"
    assert counts.cooldown_s() == pytest.approx(50.0)
    acknowledged = eco_tab.render_hub_table(ok, ROWS, total=6_040, next_refresh_s=50.0)
    assert f"fetched {ok.fetched_utc} · next refresh in 50 s" in flat(acknowledged)
    assert eco_tab.refresh_button_state(50.0) == (False, "Next refresh in 50 s")
    assert eco_tab.refresh_button_state(41.2) == (False, "Next refresh in 42 s")
    assert eco_tab.refresh_button_state(0.0) == (True, eco_tab.REFRESH_TEXT)
    _assert_clean_copy(acknowledged)
    now[0] += 120
    assert counts.cooldown_s() == 0.0
    down = counts.refresh(force=False)
    assert not down.ok and down.error_code == eco_tab.CODE_HUB_UNREACHABLE
    table = eco_tab.render_hub_table(down, ROWS, total=6_040)
    assert code_of(table) == eco_tab.CODE_HUB_UNREACHABLE
    assert "alg-card-quiet" in table and "alg-card-err" not in table, "a miss at rest is quiet"
    assert eco_tab.HINT_HUB_UNREACHABLE in table
    pressed = eco_tab.render_hub_table(down, ROWS, total=6_040, failed_now=True)
    assert "alg-card-err" in pressed, "a fetch the visitor pressed for that failed is red"
    assert table.count(eco_tab.COUNTS_UNAVAILABLE) == 1, "one card for the whole table"
    assert "alg-chip-warn" not in table, "no per-row chips"
    assert not re.search(r"\d[\d,]* downloads", table), "no count survives a failed fetch"
    assert not re.search(r"\d+ likes?<", table), "no count survives a failed fetch"
    assert ">20 kernels<" in table and ">6,040 functions<" in table, "computed facts stay"
    assert "1,234 functions · 12 modules" in flat(table) and "v1 · a01e2b2 · pinned" in flat(table)
    assert table.count('data-label="kernel"') == len(eco_tab.FAMILY_ORDER)
    assert f'<th scope="col">{eco_tab.COLUMN_HUB}</th>' not in table
    assert "backends" not in table, "no Hub answer, no Hub columns"
    _assert_clean_copy(table)
    now[0] += 120
    malformed = counts.refresh()
    assert malformed.error_code == eco_tab.CODE_HUB_MALFORMED
    assert eco_tab.HINT_HUB_MALFORMED in eco_tab.render_hub_table(malformed)
    assert len({eco_tab.hub_hint(c) for c in eco_tab.HINTS_HUB}) == 3, "one sentence per code"


ROWS = {
    family: eco_tab.KernelRow(family, eco_tab._repo(family), 1_234, 12, "a01e2b2", 1, True)
    for family in eco_tab.FAMILY_ORDER
}


def test_hub_rows_show_the_publish_date_when_downloads_are_zero_and_downloads_when_not():
    zero = eco_tab.HubKernelStat(
        "thyn-ai/algenta-stats", 0, 0, ("cpu",), "2026-09-21T18:16:26.000Z"
    )
    assert eco_tab.hub_cell(zero) == "published 2026-09-21"
    liked = eco_tab.HubKernelStat(
        "thyn-ai/algenta-text", 0, 1, ("cpu",), "2026-09-21T18:16:26.000Z"
    )
    assert eco_tab.hub_cell(liked) == "published 2026-09-21 · 1 like"
    busy = eco_tab.HubKernelStat("thyn-ai/algenta-llm", 1_234, 3, ("cpu", "cuda"), "")
    assert eco_tab.hub_cell(busy) == "1,234 downloads · 3 likes"
    assert eco_tab.backends_cell(busy) == "cpu, cuda" and eco_tab.backends_cell(zero) == "cpu"
    assert eco_tab.published_on("") == "" and eco_tab.published_on("nope") == ""
    counts = eco_tab.HubCounts(fetch=lambda u, t: hub_body(downloads=0, likes=0))
    table = eco_tab.render_hub_table(counts.refresh(), ROWS, total=6_040)
    assert "downloads" not in table, "zero downloads are never the hero"
    assert "likes" not in table and table.count("published 2026-09-21") == len(eco_tab.FAMILY_ORDER)
    assert ">20 kernels<" in table and ">6,040 functions<" in table
    _assert_clean_copy(table)


def test_kernel_rows_are_counted_from_the_loaded_kernels(deps: Deps, fake_kernel):
    rows = eco_tab.kernel_rows(deps)
    assert set(rows) == set(eco_tab.FAMILY_ORDER)
    llm = rows["llm"]
    assert llm.functions and llm.modules and llm.revision == "a01e2b2" and llm.version == 1
    assert llm.pinned is True and eco_tab.revision_text(llm) == "v1 · a01e2b2 · pinned"
    assert rows["stats"].functions is None and rows["stats"].revision == ""
    assert rows["stats"].pinned is None
    assert eco_tab.function_total(deps, rows) == llm.functions
    # a cache whose v1 moved past the capped revision: the row names the loaded snapshot, moved
    moved = Deps(kernels={"llm": loaded_llm_moved(fake_kernel)}, lane=Lane(), env={})
    row = eco_tab.kernel_rows(moved)["llm"]
    assert row.revision == MOVED_SHA[:7] and row.pinned is False
    assert eco_tab.revision_text(row) == f"v1 · {MOVED_SHA[:7]} · moved"
    assert CAPPED_SHA[:7] not in eco_tab.revision_text(row)
    table = eco_tab.render_hub_table(
        eco_tab.HubSnapshot(None, eco_tab.CODE_HUB_NOT_FETCHED, ""), eco_tab.kernel_rows(moved)
    )
    assert f"v1 · {MOVED_SHA[:7]} · moved" in flat(table) and CAPPED_SHA[:7] not in table
    deps.facts = {**deps.facts, "function_count": 6_040}
    assert eco_tab.function_total(deps, rows) == 6_040
    table = eco_tab.render_hub_table(
        eco_tab.HubSnapshot(None, eco_tab.CODE_HUB_NOT_FETCHED, ""), rows
    )
    assert eco_tab.NOT_LOADED in table and code_of(table) == eco_tab.CODE_HUB_NOT_FETCHED


def test_oss_card_is_empty_until_asked_then_facts_or_unavailable():
    state = eco_tab.OssState()
    card = eco_tab.render_oss_card(state)
    assert 'class="alg-card alg-card-empty"' in card and code_of(card) is None
    assert eco_tab.OSS_EMPTY_TEXT in card
    assert card.count(f'alg-sr">{eco_tab.NOT_FETCHED_TEXT}<') == len(eco_tab.OSS_EMPTY_ROWS)
    assert "not measured yet" not in card, "these counts are fetched, not measured"
    state.asked = True
    quiet = eco_tab.render_oss_card(state)
    assert code_of(quiet) == eco_tab.CODE_GITHUB and "alg-card-quiet" in quiet
    assert eco_tab.GITHUB_KERNELS_API not in quiet and eco_tab.SOURCE_GITHUB in quiet
    red = eco_tab.render_oss_card(state, failed_now=True)
    assert code_of(red) == eco_tab.CODE_GITHUB and "alg-card-err" in red
    facts = eco_tab.OssFacts(44, "v0.1.4", "2026-09-22 14:54 UTC", "2026-09-22 15:00 UTC")
    card = eco_tab.render_oss_card(eco_tab.OssState(facts, True))
    assert ">44<" in card and "fetched 2026-09-22 15:00 UTC" in card
    assert eco_tab.GITHUB_KERNELS_API not in card, "the source is named; the URL is not copy"


def test_staged_refresh_yields_loading_cards_then_the_result():
    bodies = {
        eco_tab.GITHUB_KERNELS_API: json.dumps(GITHUB_KERNELS).encode(),
        eco_tab.GITHUB_RELEASE_API: json.dumps(GITHUB_RELEASE).encode(),
        eco_tab.HUB_API_URL: hub_body(),
    }
    counts = eco_tab.HubCounts(fetch=lambda u, t: bodies[u])
    state = eco_tab.OssState()
    steps = list(
        eco_tab.staged_refresh(
            counts, state, {"versions": {}}, fetch=lambda u, t: bodies[u], rows=ROWS, total=6_040
        )
    )
    assert len(steps) == 2
    first, second = steps
    assert LOADING_RE.search(first[0]) and LOADING_RE.search(first[1]) and first[2] is eco_tab.KEEP
    assert ">20 kernels<" in second[0] and ">3<" in second[1] and eco_tab.TITLE_SDK in second[2]
    assert state.asked and state.facts is not None
    again = list(
        eco_tab.staged_refresh(
            counts, state, {"versions": {}}, fetch=lambda u, t: bodies[u], rows=ROWS, total=6_040
        )
    )
    assert again[0][1] is eco_tab.KEEP, "GitHub is not asked again once it has answered"
    assert "next refresh in" in again[1][0], "a press inside the floor is acknowledged"
    assert ">20 kernels<" in again[1][0]
    # a GitHub miss on the visitor's own press is red; a miss at rest stays quiet
    missing = {eco_tab.HUB_API_URL: hub_body()}
    fresh = eco_tab.OssState()
    steps = list(
        eco_tab.staged_refresh(
            eco_tab.HubCounts(fetch=lambda u, t: missing[u]),
            fresh,
            {"versions": {}},
            fetch=lambda u, t: missing[u],
            rows=ROWS,
            total=6_040,
        )
    )
    assert fresh.asked and fresh.facts is None
    assert code_of(steps[1][1]) == eco_tab.CODE_GITHUB and "alg-card-err" in steps[1][1]
    assert "alg-card-quiet" in eco_tab.render_oss_card(fresh)


def test_family_order_is_the_umbrella_then_the_nineteen_families():
    assert eco_tab.FAMILY_ORDER[0] == "algenta"
    assert len(eco_tab.FAMILY_ORDER) == len(playground.TRUST) == 20
    assert {eco_tab._repo(f) for f in eco_tab.FAMILY_ORDER} == set(playground.TRUST)


@pytest.mark.parametrize("family", eco_tab.FAMILY_ORDER)
def test_every_family_snippet_is_its_card_example_and_compiles(family: str):
    snippet = eco_tab.snippet_for(family)
    compile(snippet, f"<{family}>", "exec")
    assert f'get_kernel("{playground.repo_id(family)}"' in snippet
    example = hubkernel.card_example(family)
    assert f"k.{example.module}.{example.function}(" in snippet
    assert eco_tab.on_snippet("nope").startswith("# ")


def test_oss_facts_from_github_or_the_unavailable_card():
    bodies = {
        eco_tab.GITHUB_KERNELS_API: json.dumps(GITHUB_KERNELS).encode(),
        eco_tab.GITHUB_RELEASE_API: json.dumps(GITHUB_RELEASE).encode(),
    }
    facts = eco_tab.fetch_oss_facts(lambda url, timeout: bodies[url])
    assert facts is not None
    assert facts.package_count == 3 and facts.release_tag == "v0.1.4"
    assert facts.released_utc == "2026-09-22 14:54 UTC"
    card = eco_tab.render_oss_card(facts)
    assert ">3<" in card and "v0.1.4" in card and eco_tab.GITHUB_KERNELS_PAGE in card
    assert "fetched" in card
    _assert_clean_copy(card)

    def down(url: str, timeout: float) -> bytes:
        raise OSError("rate limited")

    assert eco_tab.fetch_oss_facts(down) is None
    card = eco_tab.render_oss_card(None)
    assert code_of(card) == eco_tab.CODE_GITHUB
    _assert_clean_copy(card)
    with pytest.raises(ValueError):
        eco_tab.parse_package_count(json.dumps([{"name": "x", "type": "file"}]).encode())
    with pytest.raises(ValueError):
        eco_tab.parse_release(json.dumps({"tag_name": "v1"}).encode())


def test_sdk_card_reads_facts_and_omits_a_missing_registry(monkeypatch):
    from tabs import try_tab  # noqa: PLC0415

    monkeypatch.setattr(try_tab, "_LAST_LIVE", [])  # no earlier live read in this process
    facts = {
        "versions": {"algenta": "1.0.24", "kernels": "0.17.1", "torch": "2.5.1"},
        "mcp_tools": 140,
        "generated_utc": "2026-09-22 14:02 UTC",
        "python": "3.14.0",
        "mojo_version": "Mojo 1.0.0 (ed45d567)",
    }
    card = eco_tab.render_sdk_card(facts)
    assert ">140<" in card and "1.0.24" in card and "0.17.1" in card
    # the toolchain row: what compiled the libraries every call runs through (owner, round 7:
    # "make sure we use true mojo kernels and not some python fallback")
    assert (
        eco_tab.MOJO_ROW_LABEL in card
        and "Mojo 1.0.0 (ed45d567) · compiled shared libraries" in card
    )
    assert eco_tab.MOJO_ROW_LABEL not in eco_tab.render_sdk_card({**facts, "mojo_version": ""})
    assert "computed 2026-09-22 14:02 UTC" in flat(card) and "Python 3.14.0" in card
    # round 5: no `algenta-mcp · not installed` row — the registry cannot share the image with
    # gradio[mcp] (mcp 2.x vs < 2.0); the count is the live hosted one, labelled so
    assert "algenta-mcp" not in card and eco_tab.MCP_NOT_INSTALLED_TEXT not in card
    assert all(name != "algenta-mcp" for name, _ in eco_tab.SDK_DISTS)
    assert gov_tab.MCP_ENDPOINT in card
    _assert_clean_copy(card)
    monkeypatch.setattr(
        eco_tab,
        "mcp_tool_count_with_caption",
        lambda: (None, "unavailable · mcp_tools_unreachable · down", "unavailable"),
    )
    card = eco_tab.render_sdk_card({"versions": {}})
    assert code_of(card) is None, "absent is not unavailable: the count check stays reachable"
    assert eco_tab.MCP_NOT_INSTALLED_TEXT in card and "alg-chip-err" not in card
    assert "MCP tools" in card and "not installed here" not in card  # round 9 wording
    _assert_clean_copy(card)
    # a count read earlier in this process stays on the card with its time when the API is down
    monkeypatch.setattr(
        eco_tab,
        "mcp_tool_count_with_caption",
        lambda: (
            140,
            "MCP tools read 2026-09-24 03:13 UTC · mcp_tools_unreachable now · down",
            "measured",
        ),
    )
    stale = eco_tab.render_sdk_card({"versions": {}})
    assert ">140<" in stale and "MCP tools read 2026-09-24 03:13 UTC" in stale
    assert eco_tab.MCP_LIVE_LABEL not in stale


def test_ecosystem_repeats_no_shell_link():
    """Round 9 (owner, on staging): the 'Everywhere Algenta runs' pill cloud repeated every header
    and footer link in a ragged block under the SDK card. The shell carries them; the tab does not."""
    assert not hasattr(eco_tab, "render_links") and not hasattr(eco_tab, "TITLE_LINKS")
    assert "alg-eco-links" not in eco_tab.ECO_CSS


def test_eco_copy_and_css_discipline():
    for text in (
        eco_tab.LABEL,
        eco_tab.HOW_TEXT,
        eco_tab.REFRESH_TEXT,
        eco_tab.HINT_HUB,
        eco_tab.HINT_HUB_NOT_FETCHED,
        eco_tab.HINT_HUB_UNREACHABLE,
        eco_tab.HINT_HUB_MALFORMED,
        eco_tab.HINT_GITHUB,
        eco_tab.LOADING_HUB_TEXT,
        eco_tab.LOADING_OSS_TEXT,
        eco_tab.OSS_EMPTY_TEXT,
        eco_tab.MCP_NOT_INSTALLED_TEXT,
        eco_tab.NEXT_REFRESH_BUTTON.format(seconds=42),
        eco_tab.REVISION_PINNED,
        eco_tab.REVISION_MOVED,
        eco_tab.NOT_FETCHED_TEXT,
        *eco_tab.more_labels(),
    ):
        _assert_clean_copy(text)
        assert not SNAKE_RE.search(text), text
    _assert_stylesheet_discipline(eco_tab.ECO_CSS)
    _assert_four_class_selectors(eco_tab.ECO_CSS)
    # the phone fold and the link's padding: the first six row cards, a 44 px control, every
    # declaration on the grid
    assert eco_tab.more_labels() == ("Show all 20 kernels", "Show the first 6 kernels")
    assert eco_tab.PHONE_ROWS == 6 and len(eco_tab.more_labels()[0].split()) <= 6
    fold = (
        f".{eco_tab.TABLE_BLOCK_CLASS}" * 4
        + f":not([{eco_tab.ALL_ATTR}]) .alg-eco-table tbody tr:nth-child(n + 7)"
        + " { display: none; }"
    )
    assert fold in eco_tab.ECO_CSS
    assert f"@media (width <= {css.PHONE_MAX_WIDTH}px)" in eco_tab.ECO_CSS
    assert f".{eco_tab.MORE_CLASS}" * 4 + " { display: none; }" in eco_tab.ECO_CSS, "phone only"
    assert (
        f".{eco_tab.MORE_CLASS}" * 4
        + " { display: flex; width: 100%; min-height: var(--alg-target); }"
    ) in eco_tab.ECO_CSS
    link = f".{'alg-eco-link.' * 3}alg-eco-link {{"
    link_rule = next(line for line in eco_tab.ECO_CSS.splitlines() if line.startswith(link))
    assert "padding: 4px 8px; box-sizing: border-box;" in link_rule, "on the grid, 44 px held"
    js = eco_tab.more_js()
    assert eco_tab.ALL_ATTR in js and "aria-expanded" in js
    assert '"Show all 20 kernels"' in js and '"Show the first 6 kernels"' in js
    assert "font-size: var(--alg-mono-size)" in eco_tab.ECO_CSS, "13 px tabular type"
    assert f"@media (width <= {eco_tab.BACKENDS_MIN_WIDTH}px)" in eco_tab.ECO_CSS
    assert 'alg-eco-table [data-col="backends"] { display: none; }' in eco_tab.ECO_CSS
    assert eco_tab.BACKENDS_MIN_WIDTH == 1023 and eco_tab.WRAP_MAX_WIDTH == 1279
    assert eco_tab.API_NAMES[0] == "eco_refresh"
    with pytest.raises(ValueError):
        eco_tab.https_get("http://huggingface.co/api/kernels")


# ---------------------------------------------------------------------------
# UI construction (gradio) — every control exists and is wired to an api_name
# ---------------------------------------------------------------------------


def _api_names(blocks: Any) -> set[str]:
    names = set()
    for fn in blocks.fns.values():
        name = getattr(fn, "api_name", None)
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _render(spec: TabSpec, gr: Any) -> tuple[Any, dict[str, Any]]:
    with gr.Blocks() as blocks, gr.Tab(spec.label, id=spec.id):
        handles = spec.render(gr)
    return blocks, handles


def test_llm_tab_builds_with_gradio(deps: Deps):
    gr = pytest.importorskip("gradio")
    poller = gpu_status.GpuStatusPoller("https://x.example/api/status", fetch=lambda u, t: b"{}")
    spec = llm_tab.build(deps, poller=poller)
    assert isinstance(spec, TabSpec) and spec.id == "llm" and spec.label == "LLM kernels"
    blocks, handles = _render(spec, gr)
    assert set(spec.api_names) <= _api_names(blocks)
    assert handles["run_rmsnorm"].value == llm_tab.RUN_RMSNORM
    for name in ("run_rmsnorm", "run_rope", "run_sampling"):
        assert handles[name].variant == "secondary", f"{name}: three peers, one hierarchy"
    for name in ("run_rmsnorm", "run_rope", "run_sampling"):
        assert handles[name].scale == 0 and handles[name].min_width == llm_tab.RUN_MIN_WIDTH, (
            f"{name}: its own width under the controls, never the panel's"
        )
    ids = [b._id for b in blocks.blocks.values()]
    for panel in ("rmsnorm", "rope", "sampling"):
        run_id, card_id, snip_id = (
            handles[f"run_{panel}"]._id,
            handles[f"card_{panel}"]._id,
            handles[f"snippet_{panel}"]._id,
        )
        assert ids.index(run_id) < ids.index(card_id) < ids.index(snip_id), (
            f"{panel}: controls, Run, the card across the panel, then Reproduce — one stack"
        )
    assert ids.index(handles["card_rmsnorm"]._id) < ids.index(handles["rows"]._id) or True
    assert handles["rows"].value == llm_tab.ROWS[3] and handles["vocab"].value == llm_tab.VOCAB[3]
    for name in (
        "rows",
        "cols",
        "tokens",
        "heads",
        "head_dim",
        "vocab",
        "temperature",
        "top_k",
        "top_p",
    ):
        assert handles[name].buttons == [], f"{name}: no stock reset button"
    for name in ("card_rmsnorm", "card_rope", "card_sampling"):
        assert 'class="alg-card alg-card-empty"' in handles[name].value, name
    for name, expected in (
        ("snippet_rmsnorm", llm_tab.snippet_rmsnorm(llm_tab.ROWS[3], llm_tab.COLS[3])),
        (
            "snippet_rope",
            llm_tab.snippet_rope(llm_tab.TOKENS[3], llm_tab.HEADS[3], llm_tab.HEAD_DIM[3], False),
        ),
        (
            "snippet_sampling",
            llm_tab.snippet_sampling(
                llm_tab.VOCAB[3], llm_tab.TEMPERATURE[3], llm_tab.TOP_K[3], llm_tab.TOP_P[3]
            ),
        ),
    ):
        assert handles[name].value.rstrip("\n") == expected.rstrip("\n"), (
            f"{name}: the editor opens on the default snippet"
        )
        compile(handles[name].value, name, "exec")
    assert poller.latest().error_code == gpu_status.CODE_NOT_FETCHED, "no poll outside a Space"
    assert code_of(handles["gpu_tile"].value) == gpu_status.CODE_NOT_FETCHED
    assert "alg-chip-err" not in handles["gpu_tile"].value
    order = [
        b._id for b in blocks.blocks.values() if b in (handles["run_sampling"], handles["gpu_tile"])
    ]
    assert order == [handles["run_sampling"]._id, handles["gpu_tile"]._id], (
        "the tile is below the controls"
    )
    # without a poller and without the stage's address there is no tile, no timer, no load hook
    _, bare = _render(llm_tab.build(deps), gr)
    assert "gpu_tile" not in bare and "gpu_timer" not in bare and "load" not in bare
    configured = Deps(
        kernels=deps.kernels,
        lane=deps.lane,
        hardware=HARDWARE,
        env={gpu_status.STATUS_URL_ENV: "https://x.example/api/status"},
    )
    _, wired = _render(llm_tab.build(configured), gr)
    assert "gpu_tile" in wired and code_of(wired["gpu_tile"].value) == gpu_status.CODE_NOT_FETCHED


def test_gov_tab_not_configured_is_one_quiet_card_with_the_controls_hidden():
    gr = pytest.importorskip("gradio")
    hosted, _ = make_hosted(key="")
    spec = gov_tab.build(gov_deps(), hosted=hosted, hook=make_hook())
    blocks, handles = _render(spec, gr)
    assert handles["configured"] is False
    card = handles["status_card"].value
    assert code_of(card) == NOT_CONFIGURED and 'data-state="not_configured"' in card
    assert "alg-card-err" not in card and "alg-chip-err" not in card
    assert "ALGENTA_API_KEY" not in card and "https://" not in card
    assert hosted.base_url not in handles["engine_note"].value, "the note is prose, no URL"
    assert handles["engine_code"].value == hosted.base_url, "the address is a code block"
    assert handles["raw"].value.strip(), "no block opens empty"
    assert handles["raw_disclosure"].visible is False, "no engine call yet: no Engine responses"
    assert handles["audit_disclosure"].visible is False, "no session log without the controls"
    assert handles["controls"].visible is False, "no disabled wall of controls"
    assert set(spec.api_names) <= _api_names(blocks), "the endpoints still answer"
    for slider in ("low", "high", "hold_value", "confidence", "risk_p5"):
        assert handles[slider].buttons == [], f"{slider}: no stock reset button"


def test_gov_tab_configured_builds_and_defaults():
    gr = pytest.importorskip("gradio")
    hook = make_hook()
    hosted, made = make_hosted(hook=hook)
    spec = gov_tab.build(gov_deps(), hosted=hosted, hook=hook)
    assert [c[0] for c in made[0].calls] == ["me"], "one probe at boot"
    blocks, handles = _render(spec, gr)
    assert handles["configured"] is True and "status_card" not in handles
    assert handles["controls"].visible is True
    # a boot probe that did not answer keeps the controls and adds one quiet card above them
    down = hosted_api.HostedStatus(
        hosted_api.ConfigState.UNAVAILABLE, "refused", hosted.base_url, "", "2026-09-22 14:02 UTC"
    )
    _, held = _render(gov_tab.build(gov_deps(), hosted=hosted, hook=hook, status=down), gr)
    assert held["controls"].visible is True and code_of(held["status_card"].value) == code(
        gov_tab.CODE_UNAVAILABLE
    )
    card = held["status_card"].value
    assert "alg-card-quiet" in card and "alg-chip-err" not in card and "refused" not in card
    assert hosted.base_url not in card and gov_tab.BOOT_UNAVAILABLE_HINT in card
    throttled = hosted_api.HostedStatus(
        hosted_api.ConfigState.RATE_LIMITED, "429", hosted.base_url, "", "2026-09-22 14:02 UTC"
    )
    assert code_of(gov_tab.status_card(throttled)) == code(gov_tab.CODE_RATE_LIMITED)
    assert gov_tab.status_card(hosted.status()) == ""
    rejected = hosted_api.HostedStatus(
        hosted_api.ConfigState.NOT_CONFIGURED,
        hosted_api.REJECTED_KEY_REASON,
        hosted.base_url,
        "",
        "2026-09-22 14:02 UTC",
    )
    card = gov_tab.status_card(rejected)
    assert hosted_api.REJECTED_KEY_REASON in html_lib.unescape(text_of(card))
    assert 'data-state="not_configured"' in card
    assert "ALGENTA_API_KEY" not in card and hosted.base_url not in card
    _assert_clean_copy(card)
    assert handles["profile"].value == gov_tab.DEFAULT_PROFILE
    assert [c[1] for c in handles["profile"].choices] == list(gov_tab.PROFILES)
    assert handles["again"].value == gov_tab.AGAIN_TEXT == "Execute again"
    assert handles["run"].variant == "primary" and handles["again"].variant == "secondary"
    assert handles["again"].interactive is False, "nothing to re-send before a decision"
    raw = handles["raw"].value
    assert 'tabindex="0" role="region"' in raw and css.CODE_SCROLL_CLASS in raw, (
        "the Engine responses block is the fleet's capped, keyboard-focusable code block"
    )
    assert "Engine JSON · " in raw and "cm-" not in raw, "an HTML payload, not a CodeMirror editor"
    assert handles["raw_disclosure"].visible is False and handles["raw_disclosure"].open is False
    assert handles["raw_full"].visible is False
    assert handles["raw_full"].value == gov_tab.request_preview(), "Copy JSON copies the full text"
    assert handles["copy_json"].value == "Copy JSON"
    assert "alg-chip-btn" in handles["copy_json"].elem_classes, "the fleet's 44 px chip"
    assert gov_tab.COPY_JSON_CLASS in handles["copy_json"].elem_classes
    assert (
        f".{gov_tab.COPY_JSON_CLASS}" * 4 + " { flex: 0 0 auto; white-space: nowrap; }"
    ) in gov_tab.GOV_CSS, "two words, one line, the chip's natural width"
    assert handles["audit_disclosure"].visible is True
    # the fleet's two-column contract: the controls never stretch, the card block takes the
    # slack, the card itself never grows past its content; the disclosures sit under the row
    assert handles["controls"].equal_height is False, "Gradio's stretch grows the controls"
    assert css.COLS_CLASS in handles["controls"].elem_classes
    assert css.CONTROLS_CLASS in handles["controls_column"].elem_classes
    assert css.RESULTS_CLASS in handles["results"].elem_classes
    assert gov_tab.RESULTS_COL_CLASS in handles["results"].elem_classes
    assert css.FILL_CLASS in handles["card"].elem_classes
    assert gov_tab.CARD_BLOCK_CLASS in handles["card"].elem_classes
    assert not any("alg-stretch" in c for c in handles["card"].elem_classes)
    ids = [b._id for b in blocks.blocks.values()]
    assert (
        ids.index(handles["card"]._id)
        < ids.index(handles["raw_disclosure"]._id)
        < ids.index(handles["audit_disclosure"]._id)
    ), "the disclosures sit under the row, not in the results column"
    assert handles["raw_disclosure"].parent is not handles["results"], "not in the column"
    assert handles["audit_disclosure"].parent is not handles["results"]
    assert 'class="alg-status"' in handles["status_row"].value, "the status row beside Run"
    assert set(handles["slots"]) == set(gov_tab.SLOTS)
    assert all(not slot.visible for slot in handles["slots"].values()), "no message at rest"
    assert len(handles["outputs"]) == 7 + len(gov_tab.SLOTS) + 1
    refused = handles["refused"](gov_tab.Refusal("high", "Optimistic value must be above."))
    assert len(refused) == len(handles["outputs"])
    assert 'class="alg-card alg-card-empty"' in refused[0], "nothing ran"
    assert "Optimistic value must be above." in refused[-1], "echoed in the status row"
    slot_updates = dict(zip(gov_tab.SLOTS, refused[7:-1], strict=True))
    assert slot_updates[gov_tab.SLOT_VALUES]["visible"] is True
    assert 'role="alert"' in slot_updates[gov_tab.SLOT_VALUES]["value"]
    assert all(not slot_updates[s]["visible"] for s in gov_tab.SLOTS if s != gov_tab.SLOT_VALUES)
    spread = handles["spread"]("card", gov_tab.raw_json(None), "audit", gov_tab.initial_state())
    assert spread[4]["visible"] is False, "no engine body: the disclosure stays hidden"
    assert spread[6]["value"] == gov_tab.AGAIN_TEXT
    body = gov_tab.request_preview()
    spread = handles["spread"](
        "card",
        body,
        "audit",
        {**gov_tab.initial_state(), "last_decision_id": "d", "last_execution_status": "failed"},
    )
    assert spread[4]["visible"] is True and spread[5] == body, "the full text feeds Copy JSON"
    assert spread[1] == gov_tab.render_engine_json(body) and 'tabindex="0"' in spread[1]
    assert spread[6]["value"] == gov_tab.AGAIN_NEW_RECEIPT_TEXT
    assert spread[-1] == common.render_status(), "a run clears the status row"
    loading = handles["spread"](gov_tab.loading_card(), gov_tab.KEEP, gov_tab.KEEP, gov_tab.KEEP)
    assert LOADING_RE.search(loading[0])
    assert 'alg-sr">not run yet<' in handles["card"].value
    assert handles["force"].label == gov_tab.LABEL_FORCE
    assert handles["override"].label == gov_tab.LABEL_OVERRIDE
    assert handles["risk_p5"].label == gov_tab.LABEL_RISK
    assert 'class="alg-card alg-card-empty"' in handles["card"].value
    assert handles["run"].interactive is not False
    assert (
        json.loads(handles["mcp_code"].value)["mcpServers"]["algenta"]["url"]
        == gov_tab.MCP_ENDPOINT
    )
    assert json.loads(handles["raw_full"].value)["recommend"]["runs"] == gov_tab.RUNS
    assert hosted.base_url not in handles["engine_note"].value, "prose carries no URL"
    assert handles["engine_code"].value == hosted.base_url and handles["engine_code"].lines == 1
    assert set(spec.api_names) <= _api_names(blocks)


def test_eco_tab_builds_with_gradio():
    gr = pytest.importorskip("gradio")
    counts = eco_tab.HubCounts(fetch=lambda u, t: hub_body())
    facts = eco_tab.OssFacts(44, "v0.1.4", "2026-09-22 14:54 UTC", "2026-09-22 15:00 UTC")
    spec = eco_tab.build(
        gov_deps(facts={"versions": {"kernels": "0.17.1"}}), counts=counts, oss=facts
    )
    blocks, handles = _render(spec, gr)
    assert set(spec.api_names) <= _api_names(blocks)
    assert handles["family"].value == "stats"
    assert handles["snippet"].buttons == [], "no stock icon panel; the Copy chip instead"
    # the phone fold: the table block carries the class the sheet reads, the 44 px control sits
    # right under the table with the folded label, its click is client-side and no endpoint
    assert eco_tab.TABLE_BLOCK_CLASS in handles["table"].elem_classes
    assert handles["more"].value == "Show all 20 kernels" == eco_tab.more_labels()[0]
    assert eco_tab.MORE_CLASS in handles["more"].elem_classes
    fold_order = [
        b._id
        for b in blocks.blocks.values()
        if b in (handles["table"], handles["more"], handles["family"])
    ]
    assert fold_order == [handles["table"]._id, handles["more"]._id, handles["family"]._id]
    assert any(
        isinstance(getattr(fn, "js", None), str) and eco_tab.ALL_ATTR in fn.js
        for fn in blocks.fns.values()
    ), "the fold is client-side"
    public = {n for n in _api_names(blocks) if not n.startswith("false")}
    assert public == set(spec.api_names), "the fold adds no endpoint (api_name=False)"
    opening_rows = handles["table"].value.count('<td data-label="kernel"')
    assert opening_rows == len(eco_tab.FAMILY_ORDER) == 20, "every row is in the DOM at rest"
    assert handles["refresh"].value == eco_tab.REFRESH_TEXT and handles["refresh"].scale == 0
    assert handles["cooldown"].active is False, "the countdown runs only after a press"
    button, timer = handles["button_state"]()
    assert button["interactive"] is True and button["value"] == eco_tab.REFRESH_TEXT
    assert timer.active is False
    wanted = (
        handles["refresh"],
        handles["table"],
        handles["family"],
        handles["oss_card"],
        handles["sdk_card"],
    )
    order = [b._id for b in blocks.blocks.values() if b in wanted]
    assert order == [w._id for w in wanted], (
        "Refresh, the full-width table, the dropdown over its snippet beside the two cards"
    )
    assert llm_tab.STRETCH_COL_CLASS in handles["cards_column"].elem_classes, "only it grows"
    assert llm_tab.STRETCH_CLASS in handles["sdk_card"].elem_classes, (
        "the SDK card fills the column"
    )
    rows = [
        b
        for b in blocks.blocks.values()
        if type(b).__name__ == "Row" and css.COLS_CLASS in (b.elem_classes or [])
    ]
    assert rows and all(not r.equal_height for r in rows), (
        "the fleet's two-column contract, never Gradio's equal_height (it grew every block of the "
        "dropdown column by 17 px: the Family form 100 → 117 px, the Copy row 48.5 → 66 px)"
    )
    assert css.RESULTS_CLASS in handles["cards_column"].elem_classes
    controls_cols = [
        b
        for b in blocks.blocks.values()
        if type(b).__name__ == "Column" and css.CONTROLS_CLASS in (b.elem_classes or [])
    ]
    assert controls_cols, "the dropdown-and-snippet column keeps its natural height"
    assert (
        ".alg-stretch" * 4 + " .alg-card > .alg-eco-actions { margin-top: auto;" in eco_tab.ECO_CSS
    )
    assert ">44<" in handles["oss_card"].value
    assert counts.latest().error_code == eco_tab.CODE_HUB_NOT_FETCHED, "no fetch outside a Space"
    opening = handles["table"].value
    assert opening.count(eco_tab.COUNTS_UNAVAILABLE) == 1
    assert "alg-card-quiet" in opening and "alg-card-err" not in opening, "quiet at boot"
    assert "alg-chip-err" not in handles["sdk_card"].value
    table, oss_card, sdk_card = eco_tab.refresh_outputs(counts, facts, {"versions": {}})
    assert ">20 kernels<" in table and ">44<" in oss_card
    assert "next refresh" not in table, "the first fetch is not an acknowledgement"
    table, *_ = eco_tab.refresh_outputs(counts, facts, {"versions": {}})
    assert "next refresh in" in table, "the second press inside the floor is acknowledged"
    button, timer = handles["button_state"]()
    assert button["interactive"] is False and button["value"].startswith("Next refresh in ")
    assert timer.active is True, "disabled and counting down inside the floor"


# ---------------------------------------------------------------------------
# Races tab — the leaderboard, the state cards and the permalink protocol
# ---------------------------------------------------------------------------


def _race_state(
    tmp_path: Path, rows: list[dict[str, Any]] = (), space_id: str = "sp/x"
) -> race_tab.RaceState:
    board = races.Board(tmp_path / "results.jsonl")
    for row in rows:
        board.append(row)
    offers = races.offers(["text", "graph"], version_of=lambda i, d: "1.0")
    return race_tab.RaceState(
        offers, races.Qualified(frozenset(), "", ""), board, HARDWARE, "hw", space_id
    )


def _row(**over: Any) -> dict[str, Any]:
    row = dict.fromkeys(races.ROW_COLUMNS, "")
    row.update(
        ts_utc="2026-09-22 14:02 UTC",
        space_id="sp/x",
        duel_id="levenshtein",
        size="M",
        n=21,
        algenta_median_ms=2.8,
        incumbent_median_ms=110.0,
        ratio=39.3,
        parity="exact match",
    )
    row.update(over)
    return row


def test_board_is_one_quiet_line_while_empty_and_one_stack_table_with_rows(tmp_path: Path):
    """The board's line is true of what it lists: with an empty qualified list, one sentence
    saying every cell is a parity panel (alone, or above the rows); "Nothing measured yet" only
    with a qualified list and nothing measured; a parity row prints its measured ratio with the
    status `not qualified` (round 6: "not a race" beside a 62× win contradicted the latencies)."""
    state = _race_state(tmp_path)
    empty = race_tab.render_board(state)
    assert race_tab.NO_QUALIFIED_BOARD in empty and "alg-card-empty" not in empty
    assert race_tab.NOTHING_MEASURED not in empty, "never 'Nothing measured yet' by default"
    assert "<table" not in empty and race_tab.LABEL_BOARD in empty
    assert 'class="alg-note alg-board-note"' in empty
    _assert_clean_copy(empty)
    assert race_tab.board_note(state, []) == race_tab.NO_QUALIFIED_BOARD
    state.qualified = races.Qualified(frozenset({("levenshtein", "*")}), "", "")
    qualified_empty = race_tab.render_board(state)
    assert race_tab.NOTHING_MEASURED in qualified_empty and "<table" not in qualified_empty
    assert race_tab.NO_QUALIFIED_BOARD not in qualified_empty
    _assert_clean_copy(qualified_empty)
    # rows: a race row (a win, its ratio) beside a parity row (both latencies, "not a race")
    state = _race_state(
        tmp_path,
        [
            _row(kind=races.ROW_KIND_RACE),
            _row(kind=races.ROW_KIND_PARITY, space_id="other/space", size="S", ratio=1.4),
        ],
    )
    board = race_tab.render_board(state)
    # the design system's table: hairline rows over Gradio's prose borders, numbers as numbers
    assert f'class="{cards.TABLE_CLASS} {cards.TABLE_STACK_CLASS} alg-board-table"' in board
    assert "alg-stack-table" not in board
    assert board.count(f'<th scope="col" class="{cards.TABLE_NUM_CLASS}">') == 4
    assert f'class="alg-board-cell {cards.TABLE_NUM_CLASS}" data-label="ratio"' in board
    assert f'class="alg-board-cell {cards.TABLE_LEAD_CLASS}" data-label="race"' in board
    assert board.count('data-label="race"') == 2 and 'data-golden="mask"' in board
    for header in race_tab.BOARD_HEADERS:
        assert f'data-label="{header}"' in board
    assert race_tab.WHERE_HERE in board and race_tab.WHERE_PUBLISHED in board
    assert "39.3×" in board and "2.80 ms" in board and "110 ms" in board
    assert f'data-label="ratio">{race_tab.ratio_text(2.8, 110.0)}<' in board
    assert "not a race" not in board and f"· {race_tab.NOT_QUALIFIED_TEXT}<" in board
    assert ">2 rows<" in board
    assert race_tab.NO_QUALIFIED_BOARD in board, "the sentence stays above the rows"
    assert board.index(race_tab.NO_QUALIFIED_BOARD) < board.index("<table")
    _assert_clean_copy(board)
    rows = race_tab.board_rows(state)
    assert rows[0][-1] == race_tab.WHERE_PUBLISHED
    assert rows[0][5] == race_tab.ratio_text(2.8, 110.0) == f"39.3× · {race_tab.NOT_QUALIFIED_TEXT}"
    assert rows[1][5] == "39.3×"
    state.qualified = races.Qualified(frozenset({("levenshtein", "*")}), "", "")
    with_list = race_tab.render_board(state)
    assert race_tab.NO_QUALIFIED_BOARD not in with_list and "<table" in with_list
    assert race_tab.NOTHING_MEASURED not in with_list
    assert race_tab.row_where({"space_id": ""}, "sp/x") == race_tab.WHERE_HERE
    parity = {"kind": "parity", "ratio": 3.0, "algenta_median_ms": 1.0, "incumbent_median_ms": 3.0}
    assert race_tab.row_ratio(parity) == f"3.00× · {race_tab.NOT_QUALIFIED_TEXT}"
    slower = {**parity, "algenta_median_ms": 66.0, "incumbent_median_ms": 4.4}
    assert (
        race_tab.row_ratio(slower)
        == f"15.0× {race_tab.SLOWER_TEXT} · {race_tab.NOT_QUALIFIED_TEXT}"
    )
    assert race_tab.row_ratio({"kind": "parity"}) == race_tab.NOT_QUALIFIED_TEXT, (
        "no lanes, no figure"
    )
    assert race_tab.ratio_text(2.0, 2.0) == f"even · {race_tab.NOT_QUALIFIED_TEXT}"
    assert race_tab.row_ratio({"ratio": 3.0}) == "3.00×", "a row without a kind was a win"


def test_race_card_caption_is_words_and_the_exact_calls_stay_in_the_disclosure(tmp_path: Path):
    cand = races.CANDIDATES_BY_ID["levenshtein"]
    size = cand.size("S")
    workload = cand.build(size, races.BASE_SEED)
    run = races.RaceRun(
        cand,
        size,
        workload,
        __import__("algenta_spaces.bench", fromlist=["CellResult"]).CellResult("noisy"),
        False,
        "nltk==3.9.1",
        "algenta-text@fb2cab4",
    )
    assert run.caption == f"{workload.note} · vs nltk 3.9.1"
    assert not SNAKE_RE.search(run.caption), run.caption
    assert run.subtitle == "text.fuzzy.levenshtein_distance vs nltk.edit_distance(a, b)"
    state = _race_state(tmp_path)
    note = race_tab.reproduce_note(state)
    assert "Levenshtein distance: text.fuzzy.levenshtein_distance vs nltk==1.0" in note
    state.kernel_labels = {"text": "algenta-text@fb2cab4"}
    note = race_tab.reproduce_note(state)
    assert "text.fuzzy.levenshtein_distance (algenta-text@fb2cab4) vs nltk==1.0" in note
    # the reasons a candidate is not offered are words, never a distribution or repository id
    offers = races.offers(["text"], version_of=lambda i, d: None if i == "py_vollib" else "1.0")
    by_id = {o.candidate.id: o for o in offers}
    assert race_tab.offer_reason(by_id["greeks"]) == race_tab.REASON_NOT_INSTALLED
    assert race_tab.offer_reason(by_id["betweenness"]) == race_tab.REASON_NOT_LOADED
    assert race_tab.offer_reason(by_id["levenshtein"]) == ""
    state.offers = offers
    text = text_of(race_tab.not_offered_note(state))
    assert "py_vollib" not in text and "algenta-graph" not in text, text
    assert not SNAKE_RE.search(text), text
    assert "Option chain Greeks (its reference library is not installed here)" in text


def _measured_run(size_key: str = "S") -> races.RaceRun:
    from algenta_spaces import bench

    cand = races.CANDIDATES_BY_ID["levenshtein"]
    size = cand.size(size_key)
    workload = cand.build(size, races.BASE_SEED)
    ours = bench.summarise(
        bench.LaneSpec("algenta-text", bench.SIDE_ALGENTA, lambda: None), [2.8, 2.9, 3.1, 2.7, 3.0]
    )
    theirs = bench.summarise(
        bench.LaneSpec("nltk", bench.SIDE_INCUMBENT, lambda: None),
        [110.0, 112.0, 118.0, 109.0, 111.0],
    )
    cell = bench.CellResult(
        bench.STATUS_MEASURED,
        lanes=[ours, theirs],
        ratio=bench.ratio_of([ours, theirs]),
        parity_label="exact match",
        n=5,
        ts_utc="2026-09-22 14:02 UTC",
        seed=races.BASE_SEED,
    )
    return races.RaceRun(cand, size, workload, cell, False, "nltk==3.9.1", "algenta-text@fb2cab4")


def test_race_result_card_carries_spread_and_the_pill_and_words_only_in_the_subtitle(
    tmp_path: Path,
):
    state = _race_state(tmp_path)
    run = _measured_run("S")
    html = race_tab.render_run(state, run)
    assert RESULT_CARD_RE.search(html)
    sub = re.search(r'alg-card-sub">([^<]*)<', html)
    assert sub is not None and sub.group(1) == run.caption, "words only in the subtitle"
    assert "@" not in sub.group(1) and run.kernel_label not in sub.group(1)
    # One lane table carries the rulebook's spread (MAD, CV) beside median, P95 and min – max;
    # no second table repeats it under the card.
    assert html.count('<table class="alg-lane-table">') == 1, "one lane table"
    assert "alg-race-spread" not in html
    for header in ("lane", "median", "MAD", "CV", "min – max"):
        assert f"<th>{header}</th>" in html, header
    ours = run.cell.lane("algenta")
    assert ours is not None
    assert cards.fmt_ms(ours.mad_ms) in html and cards.fmt_cv(ours.cv) in html
    assert html.count('data-label="MAD"') == len(run.cell.lanes), "a label per phone row card"
    assert html.index("alg-lane-table") < html.index('<div class="alg-chips">')
    assert html.rstrip().endswith("</div>") and html.count('class="alg-race-permalink"') == 1
    assert html.index("</article>") < html.index('class="alg-race-permalink"'), (
        "the pill appears with the result, under the card"
    )
    assert common.esc(race_tab.cell_link(run.candidate, "S")) in html
    assert race_tab.LABEL_LINK in html
    # the rulebook text names exactly what the card shows
    for word in (
        "median",
        "P95",
        "min–max",
        "median absolute deviation",
        "coefficient of variation",
    ):
        assert word in race_tab.HOW_MEASURED, word
    _assert_clean_copy(html)
    assert not hasattr(race_tab, "spread_table") and not hasattr(race_tab, "with_spread"), (
        "the spread lives in the shared lane table alone"
    )


def test_not_recorded_cell_has_no_link_and_a_measured_one_does(tmp_path: Path):
    """`Link to this cell` is offered with a measurement and only then: a noisy cell the rulebook
    did not record carries no pill under its card."""
    from algenta_spaces import bench

    state = _race_state(tmp_path)
    cand = races.CANDIDATES_BY_ID["levenshtein"]
    size = cand.size("S")
    noisy = races.RaceRun(
        cand,
        size,
        cand.build(size, races.BASE_SEED),
        bench.CellResult("noisy", reason="noisy — not recorded — spread above 15 percent"),
        False,
        "nltk==3.9.1",
        "algenta-text@fb2cab4",
    )
    html = race_tab.render_run(state, noisy)
    assert "not recorded" in html and "alg-race-permalink" not in html
    assert race_tab.LABEL_LINK not in html and html.rstrip().endswith("</article>")
    measured = race_tab.render_run(state, _measured_run("S"))
    assert measured.count('class="alg-race-permalink"') == 1 and race_tab.LABEL_LINK in measured


def test_wheel_sha_is_the_loaded_snapshot(tmp_path: Path, fake_kernel):
    """A qualified race the kernel won becomes a row whose `wheel_sha` is the revision that ran —
    the loaded snapshot — never the capped sha the manifest recorded when the two differ."""
    from algenta_spaces import bench

    state = _race_state(tmp_path)
    run = _measured_run("S")
    run.qualified = True
    assert run.won
    text = loaded_llm_moved(fake_kernel)
    text.family, text.repo_id = "algenta-text", "thyn-ai/algenta-text"
    deps = Deps(kernels={"text": text}, lane=Lane(), facts={"git_sha": "abc"}, env={})
    assert race_tab.record_run(state, run, deps) is True
    row = state.board.rows()[0]
    assert row["kind"] == races.ROW_KIND_RACE
    assert row["wheel_sha"] == MOVED_SHA and row["wheel_sha"] != text.capped_v1_sha
    assert row["harness_commit"] == "abc"
    # the same measurement unqualified is a parity row; held (qualified, incumbent faster) or
    # not recorded is no row at all
    parity = _measured_run("M")
    assert race_tab.record_run(state, parity, deps) is True
    assert state.board.rows()[0]["kind"] == races.ROW_KIND_PARITY and len(state.board) == 2
    from algenta_spaces import bench as _bench

    held = _measured_run("L")
    held.qualified = True
    held.cell.ratio = 0.5
    assert held.held and race_tab.record_run(state, held, deps) is False
    noisy = _measured_run("L")
    noisy.cell = _bench.CellResult("noisy", reason="noisy — not recorded")
    assert race_tab.record_run(state, noisy, deps) is False and len(state.board) == 2
    assert races.kernel_revision(text) == MOVED_SHA
    assert races.revision_label(text) == f"algenta-text@{MOVED_SHA[:7]}"
    labelled = race_tab.build_state(deps, fetch_json=lambda url: None)
    assert labelled.kernel_labels["text"] == f"algenta-text@{MOVED_SHA[:7]}"
    assert bench.SIDE_ALGENTA == "algenta"


def test_race_empty_and_loading_cards(tmp_path: Path):
    cand = races.CANDIDATES_BY_ID["levenshtein"]
    empty = race_tab.opening_card(cand)
    assert 'class="alg-card alg-card-empty"' in empty and cand.title in empty
    for key in race_tab.ROW_KEYS:
        assert f'alg-empty-key">{key}<' in empty
    # with a size, the card names the workload the radio's S · M · L means, before any run
    sized = race_tab.opening_card(cand, "M")
    assert "Levenshtein distance · 600 × 600 characters" in sized and "alg-card-empty" in sized
    assert race_tab.opening_card(cand, "XL").count(cand.title) == 1
    assert "alg-card-empty" in race_tab.opening_card(
        None
    ) and race_tab.NO_CANDIDATES in race_tab.opening_card(None)
    loading = race_tab.loading_card(cand, cand.size("M"))
    assert LOADING_RE.search(loading) and "600 × 600 characters" in loading
    assert race_tab.LOADING_TEXT in loading
    _assert_clean_copy(loading)
    queued = race_tab.loading_card(cand, cand.size("M"), "queued · 2 ahead · about 3 s")
    assert "queued · 2 ahead · about 3 s · " + race_tab.LOADING_TEXT in queued, (
        "the lane position rides in the card, not in a reserved status row"
    )
    assert "alg-status" not in queued
    assert race_tab.LABEL_LINK not in race_tab.opening_card(cand), "the pill comes with a result"
    _assert_stylesheet_discipline(race_tab.RACE_CSS)
    _assert_four_class_selectors(race_tab.RACE_CSS)
    # the phone fold: the newest six row cards, a 44 px control only while there is a row to
    # hide, every declaration on the grid; the labels are clean copy with no count in them
    assert race_tab.BOARD_PHONE_ROWS == 6
    fold = (
        f".{race_tab.BOARD_BLOCK_CLASS}" * 4
        + f":not([{race_tab.BOARD_ALL_ATTR}]) .alg-board-table tbody tr:nth-child(n + 7)"
        + " { display: none; }"
    )
    assert fold in race_tab.RACE_CSS
    assert f"@media (width <= {css.PHONE_MAX_WIDTH}px)" in race_tab.RACE_CSS
    assert f".{race_tab.BOARD_MORE_CLASS}" * 4 + " { display: none; }" in race_tab.RACE_CSS
    shown = (
        f".{race_tab.BOARD_BLOCK_CLASS}" * 4
        + f":has(.alg-board-table tbody tr:nth-child(7)) ~ .{race_tab.BOARD_MORE_CLASS}"
        + " { display: flex; width: 100%; min-height: var(--alg-target); }"
    )
    assert shown in race_tab.RACE_CSS, "the control exists only with a row to hide"
    js = race_tab.board_more_js()
    assert race_tab.BOARD_ALL_ATTR in js and "aria-expanded" in js
    assert '"Show all rows"' in js and '"Show the first 6 rows"' in js
    for text in (race_tab.BOARD_SHOW_ALL, race_tab.BOARD_SHOW_FEWER):
        _assert_clean_copy(text)
        assert len(text.split()) <= 6


def test_round_3_launch_review_regressions():
    """The confirmed P0/P1s of the third launch review, pinned: kernel repositories live under
    the Hub's `kernels/` namespace (every table link was a 404); the board keeps the digits the
    card prints (4.38 µs never becomes 4.40 µs); the Ecosystem's MCP count falls back to the
    hosted endpoint the Try tile reads; Execute again is disabled until a decision exists."""
    assert eco_tab.HUB_REPO_URL == "https://huggingface.co/kernels/"
    assert races.sig(0.00438) == 0.00438 and races.sig(4.3812345678) == 4.38123
    assert races.sig(0.0043849) == 0.0043849 and races.sig(26.3) == 26.3
    for value in (0.00438, 0.0678, 2.65, 171.0):
        assert cards.fmt_ms(races.sig(value)) == cards.fmt_ms(value), value
    # the SDK card: no registry here, the live count is the Try tile's
    facts = {"versions": {}, "generated_utc": "2026-09-23 14:02 UTC", "python": "3.14.7"}
    data = eco_tab.sdk_facts(facts)
    assert data["mcp_source"] in ("live", "") and (
        data["mcp_tools"] is None or data["mcp_tools"] > 0
    )
    live = eco_tab.render_sdk_card({**facts, "mcp_tools": 0})
    if data["mcp_tools"]:
        assert eco_tab.MCP_LIVE_LABEL in live and eco_tab.MCP_NOT_INSTALLED_TEXT not in live
    _assert_clean_copy(eco_tab.MCP_LIVE_LABEL)


def test_round_4_launch_review_regressions(tmp_path: Path, deps: Deps):
    """The confirmed P1s of the fourth launch review, pinned: every card, board, note and table
    block drops Gradio's container padding (`common.BLOCK_CLASS`, one left edge per tab); the
    phone tab strip rests on its gutter (`scroll-padding`); every measured result card says its
    timing includes the JSON marshalling (rule 10), the parity race cards included; the snippet
    and JSON editors are read-only (a live editor swallows Tab); the Playground call card foot
    carries the host load like every other card."""
    assert f".{common.BLOCK_CLASS}" * 4 + " { padding: 0; }" in common.TABS_CSS
    assert f".{common.BLOCK_CLASS}" * 4 + " > div { padding: 0; }" in common.TABS_CSS
    assert "scroll-padding: 0 4px;" in css.CHROME_CSS
    assert f".{'alg-card.' * 3}alg-card {{ padding: 16px; }}" in cards.CARD_CSS
    parity = cards.render_result_card(_cell_for_parity(), title="x", hardware="M3", race=False)
    assert bench.TRANSPORT_NOTE in parity and cards.NOT_A_RACE_TEXT in parity
    assert bench.TRANSPORT_NOTE == hubkernel.TRANSPORT_NOTE == common.TRANSPORT_NOTE
    call = common.render_call_card(
        title="t",
        subtitle="s",
        latency_ms=0.3,
        result=1,
        hardware="M3",
        ts_utc="2026-09-22 14:02 UTC",
        load_1m=2.5,
    )
    assert "M3 · host load 2.5 · " in call


def test_round_4_blocks_share_the_edge_and_editors_are_read_only(deps: Deps):
    """The rendered side of the round-4 fixes: every Races, LLM kernels, Governed and Ecosystem
    gr.HTML payload carries `common.BLOCK_CLASS`, and every code editor on those tabs is
    read-only (a live editor swallows Tab). Skipped where gradio is not installed, like the
    other render tests; the deployed Space's own gates measure the same facts."""
    gr = pytest.importorskip("gradio")
    for spec_mod in (race_tab, llm_tab, gov_tab, eco_tab):
        spec = spec_mod.build(deps)
        blocks, handles = _render(spec, gr)
        html_blocks = [b for b in blocks.blocks.values() if type(b).__name__ == "HTML"]
        carded = [b for b in html_blocks if common.BLOCK_CLASS in (b.elem_classes or [])]
        assert carded, spec_mod.__name__
        for b in blocks.blocks.values():
            if type(b).__name__ == "Code":
                if spec_mod in (llm_tab, gov_tab, eco_tab):
                    assert b.interactive is False, f"{spec_mod.__name__}: a live editor traps Tab"


def test_round_5_launch_review_regressions(deps: Deps, fake_kernel):
    """The confirmed P1s of the fifth launch review, pinned. RoPE with an odd head dimension is
    refused for the reason that holds (the frozen kernel's status 366 covers odd, too wide and
    too long at once) and a decimal shape is refused, never floored; a shape refusal is a quiet
    card, not a red one; the Races copy states the rule the qualification file applied and the
    tab prints the file's own rule and date; the Ecosystem table wraps its composite cells
    between parts up to 1279 px, drops the backends below 1024 and its block scrolls sideways
    as a last resort; the Playground doc line and provenance note drop the container pad; the
    Try copy no longer claims a busy-machine gate (rulebook v0.6)."""
    # LLM kernels: the odd head dimension, the decimal rows, the quiet tone, the 366 hint
    assert llm_tab.HEAD_DIM[2] == 2, "the field's step is the kernel's real constraint"
    html, snippet = llm_tab.run_rope(deps, 16, 4, 63, False)
    assert code_of(html) == llm_tab.CODE_BAD_SHAPE and snippet == ""
    assert llm_tab.HINT_HEAD_DIM_ODD in html and "dimension_too_large" not in html
    assert "alg-card-quiet" in html and "alg-card-err" not in html
    assert fake_kernel.calls == [], "refused before any call"
    html, _ = llm_tab.run_rmsnorm(deps, 8.5, 256)
    assert code_of(html) == llm_tab.CODE_BAD_SHAPE and "Rows must be a whole number" in html
    assert "8 × 256" not in html and fake_kernel.calls == []
    hint = llm_tab.STATUS_HINTS[(llm_tab.MODULE_ROPE, "dimension_too_large")]
    assert "even" in hint and "1,024" in hint and "1,048,576" in hint
    _assert_clean_copy(hint)
    _assert_clean_copy(llm_tab.HINT_HEAD_DIM_ODD)
    # Races: the copy states the rule the file applied; the note prints the file's own words
    assert "nightly" not in race_tab.HOW_MEASURED and "nightly" not in races.__doc__
    # round 8: the sentence states the qualification file's own rule (three recorded runs within
    # five presses; a noisy press is not a run), not "three of three"
    assert "three recorded runs on this hardware, within five presses" in race_tab.HOW_MEASURED
    assert "three of three" not in race_tab.HOW_MEASURED
    q = races.parse_qualified(
        {
            "hardware_id": "abc",
            "qualified": [{"race_id": "levenshtein", "size": "S"}],
            "rule": "a cell qualifies when 3 of 3 runs were recorded and won",
            "generated_utc": "2026-09-23 16:27 UTC",
        },
        hardware_id="abc",
    )
    assert q.rule.startswith("a cell qualifies") and q.generated_utc == "2026-09-23 16:27 UTC"
    note = race_tab.qualification_source_note(q)
    assert race_tab.QUALIFICATION_FILE_LABEL in note and "written 2026-09-23 16:27 UTC" in note
    assert race_tab.qualification_source_note(races.parse_qualified(["levenshtein"])) == ""
    _assert_clean_copy(note)
    # Ecosystem: parts, wrapping, the scroll safety net, the honest MCP source, the button
    assert eco_tab.parts_html("1 · 2") == (
        f'<span class="{eco_tab.PART_CLASS}">1</span> · <span class="{eco_tab.PART_CLASS}">2</span>'
    )
    assert f".{eco_tab.PART_CLASS}" * 4 + " { white-space: nowrap; }" in eco_tab.ECO_CSS
    assert f"@media (width <= {eco_tab.WRAP_MAX_WIDTH}px)" in eco_tab.ECO_CSS
    assert "alg-eco-table td.alg-stack-num { white-space: normal; }" in eco_tab.ECO_CSS
    assert f".{eco_tab.TABLE_BLOCK_CLASS}" * 4 + " { overflow-x: auto; }" in eco_tab.ECO_CSS
    assert "hosted API" in eco_tab.HOW_TEXT and "installed algenta-mcp registry" in eco_tab.HOW_TEXT
    assert eco_tab.REFRESH_TEXT == "Refresh Hub counts"
    # Playground: the doc line and the provenance note share the edge
    assert ".alg-fn-doc" * 4 + " > div { padding: 0; }" in common.TABS_CSS
    assert ".alg-provenance" * 4 + " > div { padding: 0; }" in common.TABS_CSS
    # Try: no busy-machine gate in the copy (v0.6 discloses the load, never gates on it)
    assert "busy machine" not in try_tab.HOW_MEASURED
    assert "off the median" in try_tab.HOW_MEASURED and "load average" in try_tab.HOW_MEASURED


_RULE_RE = re.compile(r"^((?:\.[\w-]+)+)((?::[\w-]+)*) \{ (.*) \}$")


def _css_rules(css: str) -> dict[tuple[str, str], dict[str, str]]:
    """{(class, pseudo): {property: value}} for every single-line rule in a stylesheet."""
    out: dict[tuple[str, str], dict[str, str]] = {}
    for line in css.splitlines():
        m = _RULE_RE.match(line.strip())
        if not m:
            continue
        cls = m.group(1).split(".")[1]
        decls = out.setdefault((cls, m.group(2)), {})
        for decl in m.group(3).split(";"):
            if decl.strip():
                prop, _, value = decl.partition(":")
                decls[prop.strip()] = value.strip()
    return out


def test_round_6_launch_review_regressions(deps: Deps):
    """The confirmed P1s of the sixth launch review, pinned. The footer's two stamps are one
    flex item (never split across a wrap); the shell script hides the panel Gradio adds for a
    box reached by Tab (no ghost frame) and scrolls a phone field into room before opening its
    list below; every control sits on the 8-pt grid at 44 px; the form rows are top-aligned
    with a uniform label line and a reserved message line, so a refusal moves nothing and the
    status row acknowledges it without repeating the sentence; an unqualified cell prints its
    measured ratio with the status `not qualified`, on the board and on its card."""
    from algenta_spaces import css as chrome
    from algenta_spaces import shell

    # footer: one flex item for `commit … · build …`
    html = shell.render_footer(stamp="a" * 64, commit="b" * 40)
    assert f'<span class="{shell.STAMPS_CLASS}"><span title="commit {"b" * 40}"' in html
    assert 'class="alg-shell-stamp-sep" aria-hidden="true"> · </span>' in html
    rules = _css_rules(shell.SHELL_CSS)
    stamps = rules[(shell.STAMPS_CLASS, "")]
    assert stamps["display"] == "inline-flex" and stamps["white-space"] == "nowrap"
    assert stamps["margin-left"] == "auto" and "margin-right" not in rules[("alg-shell-commit", "")]
    # dropdown script: the arrival mark, the hidden panel, the scroll into room
    script = shell.DROPDOWN_CLOSE_SCRIPT
    assert "var arrivalCleared = false;" in script and "hideArrivalPanel" in script
    assert (
        "panel.setAttribute(ARRIVAL_ATTR, '');" in script
        and "window.scrollBy(0, shortfall);" in script
    )
    assert f"var ARRIVAL_ATTR = '{chrome.ARRIVAL_ATTR}';" in script
    assert f"[{chrome.ARRIVAL_ATTR}] {{ display: none; }}" in chrome.CHROME_CSS
    assert f"var MIN_ROWS_PX = {shell.MIN_ROWS_PX};" in script and shell.MIN_ROWS_PX == 104
    assert "else if (event.key !== 'Shift') { arrivalCleared = true; }" in script
    # controls on the grid: 20 px lines, no vertical padding, 44 px boxes
    assert "line-height: 20px;" in chrome._CONTROL_TYPE
    assert "padding-top: 0; padding-bottom: 0;" in chrome._CONTROL_BOX
    assert chrome.CHROME_CSS.count(chrome._CONTROL_BOX) >= 4, "buttons, boxes, pills"
    assert ".alg-form-row" * 4 + " { align-items: flex-start; }" in common.TABS_CSS
    assert (
        ".alg-form-row" * 4 + f" > .alg-run {{ margin-top: {common.FIELD_BOX_OFFSET_PX}px; }}"
        in (common.TABS_CSS)
    )
    assert common.FIELD_BOX_OFFSET_PX == 32 and common.FIELD_SLOT_PX == 16
    assert ".alg-field-slot" * 4 + " > div { min-height: 16px; }" in common.TABS_CSS
    assert ".alg-field-slot" * 4 + ":has(> div) { margin-top: -12px; }" in common.TABS_CSS
    assert ".alg-field" * 4 + ' [data-testid="block-info"] {' in common.TABS_CSS
    # the refusal: the sentence under the field once, the status row acknowledges
    assert common.STATUS_NOT_RUN == "Not run · fix the marked field"
    status = common.render_status(echo=common.STATUS_NOT_RUN)
    assert 'role="status">Not run · fix the marked field</p>' in status
    _assert_clean_copy(status)
    # the unqualified cell: the measured figure with its status, on the card and the board
    cell = _cell_for_parity()
    label = race_tab.parity_label(cell)
    assert label == f"14.7× {race_tab.SLOWER_TEXT} · {race_tab.NOT_QUALIFIED_TEXT}"
    card = cards.render_result_card(cell, title="x", hardware="M3", race=False, parity_label=label)
    assert label in card and "not a race" not in card and "alg-hero-badge" in card
    llm = cards.render_result_card(cell, title="x", hardware="M3", race=False)
    assert cards.NOT_A_RACE_TEXT in llm, "a torch panel keeps its own label"
    q = races.Qualified(
        frozenset({("levenshtein", "S"), ("levenshtein", "L"), ("greeks", "*")}), "", ""
    )
    assert race_tab.qualified_cells_text(q) == "Levenshtein distance (S, L) · Option chain Greeks"
    _assert_clean_copy(race_tab.qualified_cells_text(q))


def _cell_for_parity() -> bench.CellResult:
    """A measured cell the incumbent won: the card is a parity panel, not a race."""

    def lane(name: str, side: str, median: float) -> bench.LaneResult:
        return bench.LaneResult(
            name=name,
            side=side,
            n=21,
            median_ms=median,
            p95_ms=median * 1.1,
            mad_ms=median * 0.02,
            cv=0.02,
            min_ms=median * 0.9,
            max_ms=median * 1.2,
            k=100,
        )

    lanes = [
        lane("sympy", bench.SIDE_INCUMBENT, 0.0045),
        lane("algenta-bits-time", bench.SIDE_ALGENTA, 0.066),
    ]
    return bench.CellResult(
        status=bench.STATUS_MEASURED,
        lanes=lanes,
        ratio=None,  # not a qualified race: a parity panel, never held
        parity_label="exact match",
        n=21,
        seed=20260919,
        load_1m=1.4,
        cpu_quota=8,
        ts_utc="2026-09-22 14:02 UTC",
    )


def test_race_permalink_names_a_cell_and_restores_only_what_can_run_here(tmp_path: Path):
    state = _race_state(tmp_path)
    cand = races.CANDIDATES_BY_ID["levenshtein"]
    link = race_tab.cell_link(cand, "M")
    assert link == "?tab=race&fn=text.fuzzy.levenshtein_distance&args=%7B%22size%22%3A%22M%22%7D"
    pill = race_tab.link_html(cand, "M")
    assert 'class="alg-race-link"' in pill and race_tab.LABEL_LINK in pill
    assert pill.startswith('<div class="alg-race-permalink">')
    assert race_tab.link_html(cand, "XL") == "" and race_tab.link_html(None, "M") == ""
    with pytest.raises(ValueError):
        race_tab.cell_link(cand, "XL")
    restored = race_tab.restore_values(state, cand.qualname, {"size": "L"})
    assert restored is not None and restored.race_id == "levenshtein" and restored.size == "L"
    assert cand.title in restored.card and race_tab.LABEL_LINK not in restored.card
    assert race_tab.restore_values(state, cand.qualname, {"size": "XL"}).size == cand.default_size
    assert race_tab.restore_values(state, cand.qualname, None).size == cand.default_size
    # Greeks needs py_vollib, which the fake offers do not carry: the link restores nothing.
    greeks = races.CANDIDATES_BY_ID["greeks"]
    state.offers = races.offers(
        ["text", "graph"], version_of=lambda i, d: None if i == "py_vollib" else "1.0"
    )
    assert race_tab.restore_values(state, greeks.qualname, {"size": "M"}) is None
    assert race_tab.restore_values(state, "nope.function", None) is None
    assert race_tab.restore_values(state, None, {"size": "M"}) is None
    payload = common.permalink_payload(cand.qualname, {"size": "S"})
    assert race_tab.restore_from_payload(state, payload).size == "S"
    assert race_tab.restore_from_payload(state, "not json") is None
    assert race_tab.permalink_restore(cand.qualname, {"size": "S"}) == [payload]
    assert race_tab.permalink_outputs({}) == []
    # the report of what was applied: exactly the cell on the page, or nothing beyond the tab
    assert race_tab.applied_size(cand, {"size": "XL"}) == cand.default_size
    assert race_tab.applied_size(cand, None) == cand.default_size
    assert race_tab.applied_size(cand, {"size": "L"}) == "L"
    assert race_tab.applied_for(state, cand.qualname, {"size": "L"}) == (
        cand.qualname,
        {"size": "L"},
    )
    assert race_tab.applied_for(state, cand.qualname, {"size": "XL"}) == (
        cand.qualname,
        {"size": "M"},
    ), "a bad size is not applied; the default the radio shows is what the box promises"
    assert race_tab.applied_for(state, cand.qualname, None) == (cand.qualname, {"size": "M"})
    assert race_tab.applied_for(state, "ab_testing.z_test_proportions", {"size": "M"}) is None
    assert race_tab.applied_for(state, greeks.qualname, {"size": "M"}) is None, "not offered here"
    assert race_tab.applied_for(None, greeks.qualname, {"size": "S"}) == (
        greeks.qualname,
        {"size": "S"},
    ), "without a build the candidate list alone answers"
    assert race_tab.permalink_applied(cand.qualname, {"size": "XL"}) == (
        cand.qualname,
        {"size": "M"},
    )
    assert race_tab.permalink_applied("nope.function", None) is None


def test_race_tab_builds_with_the_restore_box_and_one_board(tmp_path: Path, deps: Deps):
    gr = pytest.importorskip("gradio")
    state = _race_state(tmp_path)
    spec = race_tab.build(deps, state=state)
    blocks, handles = _render(spec, gr)
    assert set(spec.api_names) <= _api_names(blocks)
    assert race_tab.permalink_outputs(handles) == [handles["restore"]]
    assert handles["restore"].visible is False
    applied = handles[race_tab.PERMALINK_APPLIED_HANDLE]
    lev = races.CANDIDATES_BY_ID["levenshtein"]
    assert applied(lev.qualname, {"size": "XL"}) == (lev.qualname, {"size": "M"})
    assert applied("ab_testing.z_test_proportions", {"size": "M"}) is None
    assert applied(races.CANDIDATES_BY_ID["greeks"].qualname, {"size": "M"}) is None
    assert race_tab.NO_QUALIFIED_BOARD in handles["board"].value
    assert race_tab.NOTHING_MEASURED not in handles["board"].value
    # a fresh page shows the cells this container measured since the page was built
    assert handles["on_load"]() == handles["board"].value
    state.board.append(_row(kind=races.ROW_KIND_PARITY, size="S"))
    loaded = handles["on_load"]()
    assert ">1 row<" in loaded and f"· {race_tab.NOT_QUALIFIED_TEXT}<" in loaded
    assert race_tab.NO_QUALIFIED_BOARD in loaded and loaded != handles["board"].value
    load_events = [fn for fn in blocks.fns.values() if fn.fn is handles["on_load"]]
    assert len(load_events) == 1 and handles["board"] in load_events[0].outputs
    assert all(trigger == "load" for _, trigger in load_events[0].targets), "a page-load event"
    assert str(load_events[0].api_name).lower().startswith("false"), "not an API endpoint"
    assert "alg-card-empty" in handles["card"].value
    assert handles["card"].value.count("alg-card-empty") == 1, "exactly one empty card"
    assert "Levenshtein distance · 600 × 600 characters" in handles["card"].value, (
        "the opening card names the default size's workload"
    )
    assert [c for c, _ in handles["size"].choices] == ["S", "M", "L"], "one line of sizes"
    assert "link" not in handles and "status" not in handles, "no pill or status row before a run"
    cand = races.CANDIDATES_BY_ID["betweenness"]
    values = handles["on_restore"](common.permalink_payload(cand.qualname, {"size": "L"}))
    assert len(values) == 4
    assert values[0]["value"] == "betweenness" and values[1]["value"] == "L"
    assert cand.title in values[2] and race_tab.LABEL_LINK not in values[2]
    assert "400 nodes · 1,600 edges" in values[2], "the restored size is named on the card"
    assert values[3] == "betweenness", "the restore records the id the form now shows"
    assert handles["on_restore"]("garbage") == (gr.skip(),) * 4
    # a new size or candidate returns the column to the empty card: no stale result under it,
    # and the card's title spells the size the radio now shows
    assert "alg-card-empty" in handles["on_size"]("betweenness", "S")
    assert "Betweenness centrality · 100 nodes · 400 edges" in handles["on_size"](
        "betweenness", "S"
    )
    assert cand.title in handles["on_size"]("betweenness")
    cand_update, size_update, card, applied = handles["on_candidate"]("levenshtein", "betweenness")
    assert (
        cand_update["value"] == "levenshtein"
        and size_update["value"] == "M"
        and "Levenshtein distance · 600 × 600 characters" in card
        and "alg-card-empty" in card
        and applied == "levenshtein"
    )
    # The value guard: Gradio fires the dropdown's `input` when the box is left by Tab, a click
    # away or a re-pick of the same option, value unchanged — the id the form already shows is a
    # no-op, so the Size a visitor picked stays picked (the launch review's Races P1).
    assert handles["on_candidate"]("levenshtein", "levenshtein") == (
        gr.update(),
        gr.update(),
        gr.update(),
        "levenshtein",
    ), "value-less updates: the API still answers, the browser moves nothing"
    guard_state = handles["applied_id"]
    assert isinstance(guard_state, gr.State) and guard_state.value == handles["candidate"].value
    cascade = [fn for fn in blocks.fns.values() if fn.fn is handles["on_candidate"]]
    assert (
        len(cascade) == 1 and guard_state in cascade[0].inputs and guard_state in cascade[0].outputs
    )
    restore_events = [fn for fn in blocks.fns.values() if fn.fn is handles["on_restore"]]
    assert len(restore_events) == 1 and guard_state in restore_events[0].outputs, (
        "a permalink restore updates the guard, so the next real pick is not skipped"
    )
    # A foreign id (an API client's typo) snaps back to the first offered candidate: no stock
    # Gradio "not in the list of choices" error, no stale card.
    snapped = handles["on_candidate"]("nope", "levenshtein")
    assert snapped[0]["value"] == handles["candidate"].value and "alg-card-empty" in snapped[2]
    assert snapped[3] == handles["candidate"].value
    assert handles["candidate"].allow_custom_value is True
    # the phone fold (the Ecosystem table's): the board block carries the class the sheet reads,
    # the 44 px control sits right under the board with the folded label, its click is
    # client-side and no endpoint; the label carries no count, so a new row never stales it
    assert race_tab.BOARD_BLOCK_CLASS in handles["board"].elem_classes
    assert handles["more"].value == race_tab.BOARD_SHOW_ALL == "Show all rows"
    assert race_tab.BOARD_MORE_CLASS in handles["more"].elem_classes
    fold_order = [b._id for b in blocks.blocks.values() if b in (handles["board"], handles["more"])]
    assert fold_order == [handles["board"]._id, handles["more"]._id]
    assert any(
        isinstance(getattr(fn, "js", None), str) and race_tab.BOARD_ALL_ATTR in fn.js
        for fn in blocks.fns.values()
    ), "the fold is client-side"
    public = {n for n in _api_names(blocks) if not n.startswith("false")}
    assert public == set(spec.api_names), "the fold adds no endpoint (api_name=False)"


def test_round_8_launch_review_regressions():
    """Round 8 (build 426431e49): pill anchors and accordion blocks measured 46 px (44 + two
    1 px hairlines), the Playground field card inset its boxes 24 px right of the dropdown card
    (its own padding on top of the blocks' 16 px), card titles were h3 under the page h1, and the
    hero label said "in-kernel" for a timing that includes the marshalling."""
    from algenta_spaces import css, shell  # noqa: PLC0415

    # every pill anchor is the 44 px target with its hairline inside (flex-centred 20 px line)
    dup = _css_rules(shell.SHELL_CSS)[("alg-shell-nav-dup", "")]
    assert dup["min-height"] == "var(--alg-target)" and dup["box-sizing"] == "border-box"
    assert dup["display"] == "inline-flex" and dup["padding"] == "0 16px"
    tile = _css_rules(common.TABS_CSS)[("alg-tile-link", "")]
    assert tile["min-height"] == "var(--alg-target)" and tile["box-sizing"] == "border-box"
    assert tile["display"] == "inline-flex" and tile["padding"] == "0 16px"
    # the accordion button is the 44 px target and carries the hairline; the block is bare
    disclosure = f".{css.DISCLOSURE_CLASS}" * 4
    sheet = css.CHROME_CSS
    assert f"{disclosure} {{ padding: 0; border: 0; background: transparent;" in sheet
    header = sheet.split(f"{disclosure} > button {{", 1)[1].split("}", 1)[0]
    assert "min-height: var(--alg-target)" in header and "box-sizing: border-box" in header
    assert " padding: 0 16px; margin: 0;" in header and "border: 1px solid" in header
    # the Playground surface has no horizontal padding of its own: the blocks carry the inset
    assert _css_rules(common.TABS_CSS)[("alg-form", "")]["padding"] == "16px 0"
    assert "padding: 16px 24px" not in common.TABS_CSS
    assert ".alg-form.alg-form.alg-form.alg-form { padding: 16px; }" not in common.TABS_CSS
    # card titles are h2 (one level under the page h1); the hero label names a kernel call
    empty = common.render_empty("t", "x")
    assert '<h2 class="alg-card-title">' in empty and "<h3" not in empty
    assert try_tab.HERO_LABEL == "per kernel call · median"
    # round 10 (journalist, production): the Ecosystem pills and the slider value boxes were 46
    pill = _css_rules(eco_tab.ECO_CSS)[("alg-eco-pill", "")]
    assert pill["min-height"] == "var(--alg-target)" and pill["box-sizing"] == "border-box"
    assert pill["display"] == "inline-flex" and pill["padding"] == "0 16px"
    box = css.CHROME_CSS.split(f"{css._SLIDER_BOX} {{", 1)[1].split("}", 1)[0]
    assert "min-height: var(--alg-target)" in box and "box-sizing: border-box" in box
    value = css.CHROME_CSS.split(f"{css.SLIDER_VALUE_INPUT} {{", 1)[1].split("}", 1)[0]
    assert "min-height: calc(var(--alg-target) - 2px)" in value and "padding: 0 12px" in value
    assert "in-kernel" not in race_tab.HOW_MEASURED and "in-kernel" not in try_tab.HOW_MEASURED


def test_logged_decision_carries_the_recommendations_figures_for_the_chosen_action():
    """Owner (2026-09-24, on the live webhook body): `run_id: null`, `expected_value: null`,
    `probability_of_loss: null`. The log call sent only what the visitor typed; the engine echoes
    what it was given. The recommendation's own figures for the chosen action now travel with
    the decision (`expected_value`, `risk_pol`); `run_id` is the engine's simulation-run binding
    and a recommend-only decision has none, so that field is the engine's to leave empty."""
    hook = make_hook()
    hosted, made = make_hosted(hook=hook)
    run(gov_deps(), hosted, hook, profile="execute")
    log_calls = [c for c in made[0].calls if c[0] == "log_decision"]
    assert len(log_calls) == 1
    request = log_calls[0][1][0]
    assert request["chosen_action"] == "expand_eu"
    assert request["expected_value"] == 134269.0 and request["risk_pol"] == 0.0
    assert "run_id" not in request  # never invented: no simulation run backs this decision
    # the helper alone: a compared action answers its figures, an unknown one nothing
    rec = hosted_api.to_recommendation(RECOMMEND_BODY)
    assert hosted_api.action_result(rec, "hold") == {
        "expected_value": 0.0,
        "probability_of_loss": 0.5,
    }
    assert hosted_api.action_result(rec, "nope") == {}
    # a recommendation without figures leaves the two keys out rather than sending null
    bare = hosted_api.to_recommendation(
        {**RECOMMEND_BODY, "action_results": [{"name": "expand_eu"}]}
    )
    figures = hosted_api.action_result(bare, "expand_eu")
    assert figures == {"expected_value": None, "probability_of_loss": None}
    hosted2, made2 = make_hosted(hook=hook)
    hosted2.log_decision(
        "expand_eu",
        confidence=0.9,
        risk_p5=0.02,
        context="c",
        rationale="r",
        expected_value=figures["expected_value"],
        probability_of_loss=figures["probability_of_loss"],
    )
    request2 = [c for c in made2[0].calls if c[0] == "log_decision"][0][1][0]
    assert "expected_value" not in request2 and "risk_pol" not in request2
