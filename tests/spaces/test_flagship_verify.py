"""apps/spaces/algenta/verify_checks.py and tests/spaces/visual/_goldens.py — against fakes.

No network, no browser, no gradio: the endpoint checks see a fake `gradio_client` whose
outputs are real cards rendered by `algenta_spaces.cards` for made-up measurements, the
page checks see a fake HTTP fetcher, and the browser checks see a prepared `Audit`.
The whole set runs through `verify_remote.run_checks`, the M1 runner, exactly as the
deploy will run it once the one-line registration lands.
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
import verify_remote as vr
from algenta_spaces import bench, cards, hosted_api
from manifest import load_manifest

REPO = Path(__file__).resolve().parents[2]
ALGENTA_DIR = REPO / "apps" / "spaces" / "algenta"
VISUAL_DIR = REPO / "tests" / "spaces" / "visual"
RUN_SCRIPT = ALGENTA_DIR / "scripts" / "spaces-flagship-run.sh"
FAKE_WORDS = re.compile(
    r"TODO|FIXME|XXX|placeholder|lorem|coming soon|\bmock|\bDemo|Simulated|NotImplementedError",
    re.IGNORECASE,
)
SHARED = "c" * 64
HW = "2 vCPU (quota 2) · x86_64 · glibc 2.36"
TS = "2026-09-22 14:02 UTC"


def _import(name: str, directory: Path):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    return importlib.import_module(name)


vc = _import("verify_checks", ALGENTA_DIR)


# ---------------------------------------------------------------------------
# Fixtures: cards, info, fake client, fake http
# ---------------------------------------------------------------------------


def _lane(name: str, side: str, median: float, n: int = 21) -> bench.LaneResult:
    return bench.LaneResult(
        name=name,
        side=side,
        n=n,
        median_ms=median,
        p95_ms=median * 1.2,
        mad_ms=median * 0.05,
        cv=0.04,
        min_ms=median * 0.9,
        max_ms=median * 1.3,
        version="1.0.0",
    )


def _cell(algenta_ms: float, incumbent_ms: float, parity: str = "1e-12") -> bench.CellResult:
    return bench.CellResult(
        status=bench.STATUS_MEASURED,
        lanes=[
            _lane("algenta", bench.SIDE_ALGENTA, algenta_ms),
            _lane("networkx 3.3", bench.SIDE_INCUMBENT, incumbent_ms),
        ],
        ratio=incumbent_ms / algenta_ms,
        parity_label=parity,
        n=21,
        seed=20260919,
        ts_utc=TS,
    )


HERO_CARD = cards.render_result_card(
    _cell(0.4, 1.9), title="ab_testing.z_test_proportions", hardware=HW, race=False
)
RACE_CARD = cards.render_result_card(_cell(3.1, 41.0), title="betweenness", hardware=HW)
HELD_CARD = cards.render_result_card(_cell(50.0, 40.0), title="betweenness", hardware=HW)
NOT_RECORDED_CARD = cards.render_result_card(
    bench.CellResult(status=bench.STATUS_NOISY, reason="noisy — not recorded", n=21, ts_utc=TS),
    title="betweenness",
    hardware=HW,
)
UNAVAILABLE_CARD = cards.render_unavailable_card(
    title="Races", error_code="lane_timeout", hint="The native lane did not answer.", hardware=HW
)
NOT_CONFIGURED_CARD = hosted_api.render_status_card(
    hosted_api.HostedStatus(
        hosted_api.ConfigState.NOT_CONFIGURED,
        hosted_api.NOT_CONFIGURED_REASON,
        hosted_api.DEFAULT_BASE_URL,
        "",
        TS,
    )
)
LLM_CARD = cards.render_result_card(
    _cell(5.0, 1.2, parity="max abs diff 2e-7"), title="normk.rmsnorm", hardware=HW, race=False
)
NO_PARITY_CARD = cards.render_result_card(
    _cell(5.0, 1.2, parity=""), title="normk.rmsnorm", hardware=HW, race=False
)


def _param(name: str, default, component: str = "Textbox") -> dict:
    return {
        "label": name,
        "parameter_name": name,
        "parameter_has_default": True,
        "parameter_default": default,
        "component": component,
    }


def _endpoint(*params: dict) -> dict:
    return {"parameters": list(params), "returns": [{"component": "Html"}]}


INFO = {
    "named_endpoints": {
        "/try_run": _endpoint(
            _param("successes_a", 200, "Number"),
            _param("n_a", 1000, "Number"),
            _param("successes_b", 260, "Number"),
            _param("n_b", 1000, "Number"),
        ),
        "/play_run": _endpoint(
            _param("family", "stats", "Dropdown"),
            _param("module", "ab_testing", "Dropdown"),
            _param("function", "z_test_proportions", "Dropdown"),
            _param("args_json", "{}", "Code"),
        ),
        "/race_run": _endpoint(
            _param("duel", "betweenness", "Radio"), _param("size", "M", "Radio")
        ),
        "/llm_run": _endpoint(_param("rows", 64, "Number"), _param("cols", 1024, "Number")),
        "/gov_run": _endpoint(_param("amount", 120.0, "Number")),
        "/eco_refresh": _endpoint(),
    },
    "unnamed_endpoints": {},
}

LEVENSHTEIN_OUTPUTS = (
    f'<article class="alg-card alg-card-result"><div class="alg-hero-num">{vc.LEVENSHTEIN_EXPECTED}'
    f'</div><div class="alg-card-foot">{HW} · {TS}</div></article>',
    {"result": vc.LEVENSHTEIN_EXPECTED, "latency_ms": 0.31},
)
HAVERSINE_SENT = list(vc.DECIMALS_ARGS.values())
HAVERSINE_KM = vc.haversine_km(*HAVERSINE_SENT)
HAVERSINE_OUTPUTS = (
    '<span class="alg-chip alg-chip-neutral">done in 0.26 ms</span>',
    '<article class="alg-card alg-card-result"><h2 class="alg-card-title">'
    f'geodesy.haversine_distance</h2><div class="alg-hero-num">0.26 ms</div><pre class="alg-result">'
    f'{HAVERSINE_KM!r}</pre><div class="alg-card-foot">{HW} · {TS}</div></article>',
    json.dumps(
        {"module": "geodesy", "function": "haversine_distance", "args": HAVERSINE_SENT}, indent=2
    ),
    json.dumps({"result": HAVERSINE_KM, "elapsed_ms": 0.262}, indent=2),
    "# pip install kernels torch\n",
)


UNKNOWN_FAMILY_CARD = cards.render_unavailable_card(
    title="Playground", error_code="unknown_family", hint="That family is not loaded here."
)


def play_run(**kwargs: object) -> object:
    """The Playground answers the call it was given: kitten/sitting, London–Paris, or the
    z-test with the arguments echoed exactly (the exact-integer probe reads the echo); a family
    this container never loaded gets the coded card, as `play_tab.run_call` answers it."""
    if kwargs.get("family") == vc.FOREIGN_FAMILY:
        return (UNKNOWN_FAMILY_CARD, UNKNOWN_FAMILY_CARD, "", "", "")
    if kwargs.get("function") == vc.LEVENSHTEIN_FUNCTION:
        return LEVENSHTEIN_OUTPUTS
    if kwargs.get("function") == vc.EXACT_INT_FUNCTION:
        args = json.loads(str(kwargs.get("args_json") or "{}"))
        return (
            '<span class="alg-chip alg-chip-neutral">done in 0.20 ms</span>',
            '<article class="alg-card alg-card-result"><h2 class="alg-card-title">'
            f'ab_testing.z_test_proportions</h2><div class="alg-card-foot">{HW} · {TS}</div>'
            "</article>",
            json.dumps({"module": "ab_testing", "function": "z_test_proportions", "args": args}),
            json.dumps({"result": [-3.1, 0.001], "elapsed_ms": 0.2}),
            "# pip install kernels torch\n",
        )
    return HAVERSINE_OUTPUTS


DEFAULT_OUTPUTS: dict[str, object] = {
    "/try_run": (HERO_CARD, {"z": -3.01, "p": 0.0026}),
    "/play_run": play_run,
    "/race_run": RACE_CARD,
    "/llm_run": LLM_CARD,
    "/gov_run": NOT_CONFIGURED_CARD,
    "/eco_refresh": (
        '<section class="alg-eco"><div class="alg-eco-tile">6,024 functions</div>'
        '<div class="alg-eco-tile">19 families</div>'
        f'<div class="alg-card-foot">huggingface.co · {TS}</div></section>'
    ),
}
#: One family's native proof as `hubkernel.native_proof` writes it: the compiled Mojo library,
#: its ABI, the toolchain, and `loaded` from the live ctypes handle.
NATIVE_PROOF = {
    "library": "libalgenta_algenta_stats.so",
    "abi_version": 1,
    "mojo_version": "Mojo 1.0.0 (ed45d567)",
    "source_commit": "9069cc4",
    "platform": "x86_64-linux",
    "sha256": "0123456789ab",
    "loaded": True,
    "loader": "ctypes",
    "abi_answered": 1,
}
HEALTH_FACTS = {
    "families_loaded": ["stats", "text"],
    "kernels": {
        "stats": {"native": NATIVE_PROOF},
        "text": {"native": {**NATIVE_PROOF, "library": "libalgenta_algenta_text.so"}},
    },
    "mojo_version": "Mojo 1.0.0 (ed45d567)",
}
HEALTH_READY = json.dumps(
    {
        "ready": True,
        "error": None,
        "elapsed_s": 41.2,
        "stages": [{"id": "kernels"}],
        "facts": HEALTH_FACTS,
    }
)
#: A snapshot as `BootRegistry.snapshot()` writes it: `elapsed_s` is the uptime (1,296 s after a
#: long QA session), the stages carry the boot's own start and end times (41 s apart).
HEALTH_UPTIME = json.dumps(
    {
        "ready": True,
        "error": None,
        "elapsed_s": 1296.4,
        "stages": [
            {"id": "host", "started_at": 1000.0, "finished_at": 1000.1},
            {"id": "kernels", "started_at": 1000.1, "finished_at": 1038.0},
            {"id": "hero", "started_at": 1038.0, "finished_at": 1041.0},
        ],
    }
)
HEALTH_BOOTING = json.dumps({"ready": False, "error": None, "elapsed_s": 3.0, "stages": []})
PAGE = (
    'window.gradio_config = {"components": [{"value": "<span class=\\"alg-shell-stamp\\">build '
    + SHARED
    + '</span>"}]};'
)
PAGE_ESCAPED = (
    'window.gradio_config = {"components": [{"value": "\\u003cspan class=\\"alg-shell-stamp\\"'
    "\\u003ebuild " + SHARED + '\\u003c/span\\u003e"}]};'
)
FOOTER_PLAIN = f'<footer><span class="alg-shell-stamp">build {SHARED}</span></footer>'


class FakeClient:
    def __init__(self, outputs: dict[str, object]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[str, dict]] = []

    def predict(self, *, api_name: str, **kwargs):
        self.calls.append((api_name, kwargs))
        try:
            answer = self.outputs[api_name]
        except KeyError:
            raise RuntimeError(f"no such endpoint {api_name}") from None
        return answer(**kwargs) if callable(answer) else answer


class FakeHttp:
    def __init__(self, routes: dict[str, tuple[int, str]]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float) -> tuple[int, str]:
        self.calls.append(url)
        path = url.split("127.0.0.1:7860", 1)[1] or "/"
        return self.routes.get(path, (404, "not here"))


CLEAN_ECO_TABLE = vc.EcoTableAudit(
    samples=[
        f"{w} px: table 48–{48 + 800} in block 48–{48 + 928}, backends"
        f" {'shown' if w >= 1024 else 'dropped'}"
        for w in vc.ECO_TABLE_WIDTHS
    ]
)
CLEAN_AUDIT = vc.Audit(
    tabs=["landing", "try", "play", "race", "llm", "gov", "eco"],
    targets_checked=48,
    axe_ran=True,
    contrast_samples=30,
    button_contrast_samples=120,
    code_contrast_samples=64,
    value_boxes_checked=18,
    chrome_runs=["desktop/light/try Run", "desktop/light/eco Refresh counts"],
    chrome_samples=6,
    nav_rows_checked=6,
    checkboxes_checked=4,
    listboxes_opened=20,
    copy_nodes=210,
    toast_samples=34,
    run_presses=[
        "desktop/light/try Run",
        "desktop/light/play Run",
        "desktop/light/race Run the race",
        "desktop/light/llm Run RMSNorm",
        "desktop/light/gov Run governed execution (disabled)",
        "desktop/light/eco Refresh counts",
        "desktop/dark/try Run",
        "desktop/dark/eco Refresh counts",
    ],
    dismissals=15,
    reopens=10,
    boot_rows=[
        {"stage": "kernels", "elapsed": "41.2 s", "detail": "20 families warm in 41.2 s"},
        {
            "stage": "hero",
            "elapsed": "0.0 s",
            "detail": f"{cards.fmt_ms(0.4104)} per kernel call, n = 21 · statsmodels agrees",
        },
    ],
    boot_foot=f"booted in 41.2 s · finished {TS}",
    boot_hero={"status": "measured", "kernel_ms": 0.4104, "n": 21, "attempts": 1},
    axe_views=28,
    code_blocks=9,
    void_samples=14,
    stamp_samples=[
        {
            "where": "phone/light/landing",
            "text": f"build {SHARED[:12]}",
            "w": 156,
            "h": 20,
            "lines": 1,
        },
        {
            "where": "phone/dark/landing",
            "text": f"build {SHARED[:12]}",
            "w": 156,
            "h": 20,
            "lines": 1,
        },
    ],
)
CLEAN_PERMALINKS = vc.PermalinkAudit(
    loads=[
        f"{label}/{theme} {name} box '?tab=…'"
        for label, _w, _h, theme in vc.PERMALINK_CONTEXTS
        for name, _q, _full in vc.PERMALINK_SHAPES
    ]
)
CLEAN_EXACT_INT = vc.ExactIntAudit(typed=str(vc.EXACT_INT), request=str(vc.EXACT_INT))
CLEAN_REFUSALS = vc.RefusalAudit(
    probes=[
        f"{label}/{theme}/{slug} '{control}'={value}: 2 message(s) — refused"
        for label, _w, _h, theme in vc.REFUSAL_CONTEXTS
        for slug, control, value, _word in vc.REFUSAL_PROBES
        if slug != "gov"
    ],
    skipped=[
        f"{label}/{theme}/gov: no form to refuse (hosted_not_configured)"
        for label, _w, _h, theme in vc.REFUSAL_CONTEXTS
    ],
)
CLEAN_CLS = vc.ClsAudit(
    loads=[
        f"{vp}/{tab} #{n} 0.0012"
        for vp in ("desktop", "phone")
        for tab in vc.TAB_SLUGS
        for n in (1, 2, 3)
    ],
    worst=0.0012,
)


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch):
    """Every test starts without cached clients or audits, with the tool's signal classes,
    without importable tabs (the frozen fallback contract) and with a clean browser audit."""
    vc.reset_clients()
    monkeypatch.setitem(vc._SIGNALS, "fail", vr.VerifyError)
    monkeypatch.setitem(vc._SIGNALS, "skip", vr.VerifySkipped)
    monkeypatch.setitem(vc._PHASE, "value", vc.PHASE_NOKEY)
    monkeypatch.setattr(vc, "tab_api_names", lambda tabs_dir=None: {})
    monkeypatch.setattr(vc, "run_audit", lambda base_url, slugs=None: CLEAN_AUDIT)
    monkeypatch.setattr(vc, "run_cls_audit", lambda base_url, slugs=None: CLEAN_CLS)
    monkeypatch.setattr(vc, "run_permalink_audit", lambda base_url: CLEAN_PERMALINKS)
    monkeypatch.setattr(vc, "run_exact_int_audit", lambda base_url: CLEAN_EXACT_INT)
    monkeypatch.setattr(vc, "run_refusal_audit", lambda base_url: CLEAN_REFUSALS)
    monkeypatch.setattr(vc, "run_eco_table_audit", lambda base_url: CLEAN_ECO_TABLE)
    posts: list[tuple[str, dict]] = []

    def refused_post(url: str, body, timeout: float) -> tuple[int, str]:
        posts.append((url, dict(body)))
        return 404, '{"error": "not_found"}'

    monkeypatch.setattr(vc, "post_json", refused_post)
    monkeypatch.setattr(vc, "_TEST_POSTS", posts, raising=False)
    yield
    vc.reset_clients()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    fake = FakeClient(dict(DEFAULT_OUTPUTS))
    monkeypatch.setattr(vc, "CLIENT_FACTORY", lambda base_url: fake)
    return fake


@pytest.fixture
def http() -> FakeHttp:
    return FakeHttp(
        {
            "/gradio_api/info": (200, json.dumps(INFO)),
            "/health": (200, HEALTH_READY),
            "/": (200, PAGE),
        }
    )


@pytest.fixture
def ctx(http: FakeHttp) -> vr.VerifyContext:
    space = load_manifest().space("algenta")
    return vr.VerifyContext(
        space=space, fetch=http, base_url="http://127.0.0.1:7860", expected_shared_sha=SHARED
    )


def _snake(code: str) -> str:
    """The card's spelling of an error code: lowercase snake_case."""
    return code.lower().replace("-", "_")


def _run(ctx: vr.VerifyContext, *names: str) -> vr.VerifyReport:
    selected = [(n, fn) for n, fn in vc.checks_for() if not names or n in names]
    return vr.run_checks(ctx, selected)


def _detail(report: vr.VerifyReport, name: str) -> str:
    return next(r.detail for r in report.results if r.name == name)


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


def test_manifest_puts_the_flagship_on_the_shared_shell() -> None:
    assert load_manifest().space("algenta").shared_shell is True


def test_fallback_contract_covers_the_six_tabs() -> None:
    assert vc.tab_slugs() == ("try", "play", "race", "llm", "gov", "eco")
    names = vc.expected_api_names()
    assert all(len(v) >= 1 for v in names.values())
    assert vc.all_expected() == frozenset(
        {"try_run", "play_run", "race_run", "llm_run", "gov_run", "eco_refresh"}
    )
    for slug, api_names in names.items():
        assert all(n.startswith(f"{slug}_") for n in api_names), (slug, api_names)


def test_tab_modules_drive_the_expected_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.undo()  # the autouse fixture pinned tab_api_names to {}; use the real reader
    pkg = tmp_path / "tabs"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "try_tab.py").write_text(
        'API_NAMES = ("try_hero", "try_race_link")\nLABEL = "Try it"\n', encoding="utf-8"
    )
    (pkg / "eco_tab.py").write_text('API_NAMES = "eco_counts"\n', encoding="utf-8")
    (pkg / "gov_tab.py").write_text("raise ImportError('needs algenta')\n", encoding="utf-8")
    (pkg / "common.py").write_text("HELPER = 1\n", encoding="utf-8")
    for name in list(sys.modules):
        if name == "tabs" or name.startswith("tabs."):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.syspath_prepend(str(tmp_path))
    found = vc.tab_api_names(tmp_path)
    assert found == {"try": ("try_hero", "try_race_link"), "eco": ("eco_counts",)}
    expected = vc.expected_api_names(tmp_path)
    assert expected["try"] == ("try_hero", "try_race_link")
    assert expected["eco"] == ("eco_counts",)
    assert expected["gov"] == vc.FALLBACK_API_NAMES["gov"]  # the module that failed to import
    assert expected["play"] == vc.FALLBACK_API_NAMES["play"]  # no module at all
    assert vc.tab_slugs(tmp_path) == vc.TAB_SLUGS
    assert vc.tab_api_names(tmp_path / "elsewhere") == {}
    assert vc.tab_labels(tmp_path) == {"try": "Try it"}
    assert vc.tab_labels(tmp_path / "elsewhere") == {}


def test_the_landed_tab_modules_agree_with_the_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every tab module the flagship has today declares api names under its own id prefix."""
    monkeypatch.undo()  # the autouse fixture pins tab_api_names to {}; read the real modules
    for name in list(sys.modules):
        if name == "tabs" or name.startswith("tabs."):
            del sys.modules[name]
    found = vc.tab_api_names()
    assert set(found) == set(vc.TAB_SLUGS), f"tab modules found: {sorted(found)}"
    assert set(vc.tab_labels()) <= set(found)  # a LABEL is optional; the strip is the source
    for slug, names in found.items():
        assert slug in vc.TAB_SLUGS, slug
        assert names, slug
        assert all(n.startswith(f"{slug}_") for n in names), (slug, names)
        assert vc.FALLBACK_API_NAMES[slug][0] in names, (
            f"{slug}: the fallback name {vc.FALLBACK_API_NAMES[slug][0]!r} is not among {names};"
            " update FALLBACK_API_NAMES in verify_checks.py"
        )


def test_build_kwargs_prefers_exact_then_substring_then_default() -> None:
    info = INFO["named_endpoints"]["/play_run"]
    kwargs = vc.build_kwargs(
        info,
        {
            "family": "text",
            "module": "text.fuzzy",
            "function": "levenshtein_distance",
            "args": "{}",
        },
    )
    assert kwargs == {
        "family": "text",
        "module": "text.fuzzy",
        "function": "levenshtein_distance",
        "args_json": "{}",
    }
    # a one-letter key never matches by substring ("a" is inside "family")
    assert "family" not in vc.build_kwargs(info, {"a": "kitten"}) or (
        vc.build_kwargs(info, {"a": "kitten"})["family"] == "stats"
    )
    hero = vc.build_kwargs(INFO["named_endpoints"]["/try_run"], {})
    assert hero == {"successes_a": 200, "n_a": 1000, "successes_b": 260, "n_b": 1000}
    untouched = {
        "parameters": [
            {"parameter_name": "x", "component": "Number"},
            {"parameter_name": "flag", "component": "Checkbox"},
            {"parameter_name": "note", "component": "Textbox"},
        ]
    }
    assert vc.build_kwargs(untouched, {}) == {"x": None, "flag": False, "note": None}


def test_endpoint_lookup_prefers_the_run_endpoint(ctx, client, monkeypatch) -> None:
    assert vc.endpoint_for(ctx, "try")[0] == "try_run"
    # the tab module lists its cascade endpoints first; the run endpoint is still the target
    monkeypatch.setattr(
        vc,
        "tab_api_names",
        lambda tabs_dir=None: {"play": ("play_modules", "play_form", "play_run")},
    )
    ctx._info = {
        "named_endpoints": {
            "/play_modules": {"parameters": []},
            "/play_form": {"parameters": []},
            "/play_run": {"parameters": []},
        }
    }
    assert vc.endpoint_for(ctx, "play")[0] == "play_run"
    ctx._info = {"named_endpoints": {"/play_modules": {"parameters": []}, "/play_form": {}}}
    assert vc.endpoint_for(ctx, "play")[0] == "play_modules"
    ctx._info = {
        "named_endpoints": {"/race_board": {"parameters": []}, "/race_cell": {"parameters": []}}
    }
    assert vc.endpoint_for(ctx, "race")[0] == "race_board"
    with pytest.raises(vr.VerifyError, match="no endpoint for tab 'gov'"):
        vc.endpoint_for(ctx, "gov")


# ---------------------------------------------------------------------------
# The whole set through the M1 runner
# ---------------------------------------------------------------------------


def test_every_check_passes_on_a_healthy_flagship(ctx, client, http) -> None:
    report = _run(ctx)
    assert report.ok, report.lines()
    assert not report.skipped
    assert [r.name for r in report.results] == [
        "expected_api_names",
        "hero_result",
        "playground_levenshtein",
        "playground_decimals",
        "family_dropdown_foreign_value",
        "race_cell",
        "llm_rmsnorm_parity",
        "governed_lane",
        "receipt_tone",
        "webhook_privacy",
        "ecosystem_counts",
        "every_endpoint_answers",
        "health_ready",
        "shared_stamp",
        "native_only",
        "console_clean",
        "no_horizontal_scroll",
        "targets_44px",
        "axe_serious_critical",
        "contrast_hero",
        "contrast_buttons",
        "contrast_code",
        "value_boxes_unclipped",
        "no_stock_chrome",
        "no_stock_code_labels",
        "no_toasts",
        "dropdown_dismissal",
        "dropdown_reopens",
        "boot_card_timings",
        "boot_row_live",
        "voids",
        "footer_stamp_one_line",
        "nav_separators",
        "checkboxes_dark_unfilled",
        "no_identifiers_in_copy",
        "cls_budget",
        "permalink_truth",
        "exact_integers",
        "refusal_convention",
        "eco_table_fits",
    ]
    assert _detail(report, "receipt_tone").startswith(
        f"/gov_run {_snake(hosted_api.NOT_CONFIGURED_CODE)}: no key on this Space"
    )
    assert _detail(report, "no_toasts") == (
        "0 toasts in 34 samples over 7 run presses (eco, llm, play, race, try);"
        " not pressed, disabled: desktop/light/gov Run governed execution (disabled)"
    )
    assert _detail(report, "dropdown_dismissal") == (
        "15 dismissals (click-away, Tab, Escape) over 5 dropdowns, form unchanged"
    )
    assert _detail(report, "native_only") == (
        "2 families execute through their compiled Mojo libraries (Mojo 1.0.0 (ed45d567)),"
        " ABI 1, ctypes handles live"
    )
    assert _detail(report, "dropdown_reopens") == (
        "10 clicks on a focused, closed dropdown reopened its list, form unchanged"
    )
    assert _detail(report, "eco_table_fits") == (
        "the Hub table fits its block at 900, 1024, 1152, 1200, 1440 px (5 loads)"
    )
    assert _detail(report, "boot_card_timings") == (
        "2 stages: 41.2 + 0.0 = 41.2 s, foot 41.2 s, /health — s"
    )
    assert _detail(report, "boot_row_live") == (
        f"hero row '{cards.fmt_ms(0.4104)} per kernel call, n = 21 · statsmodels agrees' == /health"
        f" hero measured {cards.fmt_ms(0.4104)} per kernel call, n = 21, attempt 1"
    )
    assert _detail(report, "family_dropdown_foreign_value") == (
        f"/play_run family={vc.FOREIGN_FAMILY!r} → unavailable · unknown_family;"
        " no family cascade endpoint to probe"
    )
    assert _detail(report, "webhook_privacy") == (
        "/health names /hook/… without the nonce; /gov_run hosted_not_configured, no receipt to"
        " print a URL; POST /hook/<guessed> → 404, POST /hook → 404"
    )
    assert _detail(report, "axe_serious_critical") == (
        "axe: 0 serious or critical over 28 tab views (nokey phase)"
    )
    assert _detail(report, "no_stock_code_labels") == (
        "9 Code blocks, no stock label or line-number gutter"
    )
    assert _detail(report, "voids") == "14 column samples at 1440 px, no gap over 240 px"
    assert _detail(report, "refusal_convention") == (
        "9 refusals on llm, play, try: field message under the control + status-row echo, no red"
        " card, no toast; nothing moved at 1440, 1024, 375 px, the Reproduce editor kept its"
        " lines; not shown: desktop/light/gov: no form to refuse"
        " (hosted_not_configured); tablet/light/gov: no form to refuse (hosted_not_configured)"
    )
    assert _detail(report, "footer_stamp_one_line") == (
        "stamp 12 hex, one line at 375 px in 2 contexts (156x20 px)"
    )
    assert _detail(report, "permalink_truth") == (
        "10 link shapes × 2 contexts, box == restored state (20 loads)"
    )
    assert _detail(report, "exact_integers") == (
        f"API path echoes {vc.EXACT_INT} exactly; browser: typed {vc.EXACT_INT},"
        f" request {vc.EXACT_INT}"
    )
    assert "parity chip" in _detail(report, "hero_result")
    assert HW in _detail(report, "hero_result")
    assert TS in _detail(report, "hero_result")
    assert "= 3" in _detail(report, "playground_levenshtein")
    assert _detail(report, "playground_decimals").startswith(
        "/play_run haversine args echoed exactly · 343."
    )
    assert "3.10 ms vs 41.0 ms" in _detail(report, "race_cell")
    assert _snake(hosted_api.NOT_CONFIGURED_CODE) in _detail(report, "governed_lane")
    assert "largest 6,024" in _detail(report, "ecosystem_counts")
    assert _detail(report, "health_ready").startswith("ready, 1 stages")
    assert _detail(report, "shared_stamp") == f"shared {SHARED[:12]}"
    assert report.lines()[-1] == "algenta: all checks passed"
    # the playground calls carried the real inputs, the hero call the app's defaults
    play_calls = [kwargs for name, kwargs in client.calls if name == "/play_run"]
    assert play_calls == [
        {
            "family": "text",
            "module": "text.fuzzy",
            "function": "levenshtein_distance",
            "args_json": json.dumps({"a": "kitten", "b": "sitting"}),
        },
        {
            "family": "geometry",
            "module": "geodesy",
            "function": "haversine_distance",
            "args_json": json.dumps(dict(vc.DECIMALS_ARGS)),
        },
        {  # the foreign-family probe keeps the app's defaults for everything else
            "family": vc.FOREIGN_FAMILY,
            "module": "ab_testing",
            "function": "z_test_proportions",
            "args_json": "{}",
        },
        {
            "family": "stats",
            "module": "ab_testing",
            "function": "z_test_proportions",
            "args_json": json.dumps(dict(vc.EXACT_INT_ARGS)),
        },
    ]
    calls = dict(client.calls)
    assert calls["/try_run"] == {"successes_a": 200, "n_a": 1000, "successes_b": 260, "n_b": 1000}
    # info is fetched once and cached on the context
    assert http.calls.count("http://127.0.0.1:7860/gradio_api/info") == 1


def test_install_registers_every_check_under_the_flagship() -> None:
    registry: dict[str, list[str]] = {}

    def register(*names: str):
        def wrap(fn):
            for n in names:
                registry.setdefault(n, []).append(fn.__name__)
            return fn

        return wrap

    installed = vc.install(register, vr.VerifyError, vr.VerifySkipped)
    assert list(registry) == ["algenta"]
    assert registry["algenta"] == installed == [n for n, _ in vc.checks_for()]
    assert len(set(installed)) == len(installed)
    assert vc._SIGNALS == {"fail": vr.VerifyError, "skip": vr.VerifySkipped}
    with pytest.raises(ValueError, match="belong to 'algenta'"):
        vc.checks_for("speed-arena")


def test_no_check_name_collides_with_the_tool_s_own() -> None:
    ours = {n for n, _ in vc.checks_for()}
    theirs = {n for n, _ in vr.CHECKS["algenta"]}
    assert not ours & theirs, ours & theirs


# ---------------------------------------------------------------------------
# Endpoint checks: failures and documented states
# ---------------------------------------------------------------------------


def test_expected_set_reports_missing_and_extra(ctx, client) -> None:
    ctx._info = {"named_endpoints": {"/try_run": {}, "/race_run": {}, "/legacy_tokenize": {}}}
    report = _run(ctx, "expected_api_names")
    assert report.failures == ["expected_api_names"]
    detail = _detail(report, "expected_api_names")
    assert "missing eco_refresh, gov_run, llm_run, play_run" in detail
    assert "unexpected legacy_tokenize" in detail


def test_hero_needs_parity_chip_hardware_and_stamp(ctx, client) -> None:
    client.outputs["/try_run"] = NOT_RECORDED_CARD
    report = _run(ctx, "hero_result")
    assert report.ok, "the rulebook's honest answer on a loaded host is a documented state"
    detail = _detail(report, "hero_result")
    assert detail.startswith("/try_run not recorded (documented state")
    assert "noisy — not recorded" in detail, "the card's reason travels with the verdict"
    client.outputs["/try_run"] = NO_PARITY_CARD
    assert "no parity chip" in _detail(_run(ctx, "hero_result"), "hero_result")
    footless = re.sub(r'<div class="alg-card-foot">.*?</div>', "", HERO_CARD)
    assert footless != HERO_CARD
    client.outputs["/try_run"] = footless
    assert "no hardware line" in _detail(_run(ctx, "hero_result"), "hero_result")
    client.outputs["/try_run"] = UNAVAILABLE_CARD
    assert "unavailable card (lane_timeout)" in _detail(_run(ctx, "hero_result"), "hero_result")
    client.outputs["/try_run"] = "<p>4.2</p>"
    assert "no result card" in _detail(_run(ctx, "hero_result"), "hero_result")


def test_playground_overrides_follow_the_generated_form() -> None:
    """The live Playground: fam/mod/fn dropdowns, then four slots per field (Number, Checkbox,
    Textbox, Code); levenshtein's two strings land in the first two Textbox slots."""
    info = _endpoint(
        {
            "parameter_name": "fam",
            "component": "Dropdown",
            "parameter_has_default": True,
            "parameter_default": "algenta-bits-time",
            "type": {"enum": ["algenta-bits-time", "algenta-text", "algenta-stats"]},
        },
        _param("mod", "agent_runtime", "Dropdown"),
        _param("fn", "action_value_estimate", "Dropdown"),
        _param("param_3", None, "Number"),
        _param("param_4", False, "Checkbox"),
        _param("param_5", None, "Textbox"),
        _param("param_6", None, "Code"),
        _param("param_7", None, "Number"),
        _param("param_8", False, "Checkbox"),
        _param("param_9", None, "Textbox"),
        _param("param_10", None, "Code"),
        _param("param_11", None, "Number"),
        _param("param_13", None, "Textbox"),
    )
    assert vc.playground_overrides(info) == {
        "fam": "algenta-text",
        "mod": "text.fuzzy",
        "fn": "levenshtein_distance",
        "param_5": "kitten",
        "param_9": "sitting",
    }
    kwargs = vc.build_kwargs(info, vc.playground_overrides(info))
    assert kwargs["param_13"] is None and kwargs["param_4"] is False
    # the M2-A fake form: named family/module/function and one JSON args control
    assert vc.playground_overrides(INFO["named_endpoints"]["/play_run"]) == {
        "family": "text",
        "module": "text.fuzzy",
        "function": "levenshtein_distance",
        "args_json": json.dumps({"a": "kitten", "b": "sitting"}),
    }


def test_decimals_overrides_and_the_haversine_reference() -> None:
    """The London–Paris call lands its four floats in the first four Number fields after the
    function selector; the reference distance is the textbook haversine on 6,371 km."""
    info = _endpoint(
        {
            "parameter_name": "fam",
            "component": "Dropdown",
            "parameter_has_default": True,
            "parameter_default": "algenta-stats",
            "type": {"enum": ["algenta-stats", "algenta-geometry", "algenta-text"]},
        },
        _param("mod", "ab_testing", "Dropdown"),
        _param("fn", "z_test_proportions", "Dropdown"),
        _param("param_3", None, "Number"),
        _param("param_4", False, "Checkbox"),
        _param("param_5", None, "Textbox"),
        _param("param_6", None, "Code"),
        _param("param_7", None, "Number"),
        _param("param_11", None, "Number"),
        _param("param_15", None, "Number"),
        _param("param_19", None, "Number"),
    )
    assert vc.decimals_overrides(info) == {
        "fam": "algenta-geometry",
        "mod": "geodesy",
        "fn": "haversine_distance",
        "param_3": 51.5074,
        "param_7": -0.1278,
        "param_11": 48.8566,
        "param_15": 2.3522,
    }
    assert vc.decimals_overrides(INFO["named_endpoints"]["/play_run"])["args_json"] == json.dumps(
        dict(vc.DECIMALS_ARGS)
    )
    km = vc.haversine_km(*HAVERSINE_SENT)
    assert 343.5 < km < 343.6, km  # London–Paris on a 6,371 km sphere
    assert vc.haversine_km(0, 0, 0, 0) == 0.0
    assert abs(vc.haversine_km(0, 0, 0, 180) - vc.EARTH_RADIUS_KM * 3.141592653589793) < 1e-9
    assert vc.json_documents(["{not json", '{"a": 1}', {"b": 2}, "x", None]) == [
        {"a": 1},
        {"b": 2},
    ]


def test_decimals_must_be_echoed_exactly_and_agree_with_the_formula(ctx, client) -> None:
    report = _run(ctx, "playground_decimals")
    assert report.ok, report.lines()
    detail = _detail(report, "playground_decimals")
    assert detail.startswith("/play_run haversine args echoed exactly · 343.")
    assert "the formula agrees to 0.0e+00" in detail
    # a form that rounded the boxes to whole degrees echoes 52, 0, 49, 2: the round-1 defect
    rounded = list(HAVERSINE_OUTPUTS)
    rounded[2] = json.dumps(
        {"module": "geodesy", "function": "haversine_distance", "args": [52.0, 0.0, 49.0, 2.0]}
    )
    rounded[3] = json.dumps({"result": 362.30238306162124, "elapsed_ms": 0.262})
    client.outputs["/play_run"] = tuple(rounded)
    detail = _detail(_run(ctx, "playground_decimals"), "playground_decimals")
    assert detail.startswith(
        "/play_run: geodesy.haversine_distance echoed args [52.0, 0.0, 49.0, 2.0], sent [51.5074"
    )
    assert "rounded the decimals away" in detail
    # the args survive but the number is not the haversine on 6,371 km
    wrong = list(HAVERSINE_OUTPUTS)
    wrong[3] = json.dumps({"result": HAVERSINE_KM * 1.001, "elapsed_ms": 0.262})
    client.outputs["/play_run"] = tuple(wrong)
    detail = _detail(_run(ctx, "playground_decimals"), "playground_decimals")
    assert "the formula gives" in detail and "relative difference 1.00e-03" in detail
    # no request JSON among the outputs
    client.outputs["/play_run"] = (HAVERSINE_OUTPUTS[1],)
    assert "no Request-and-response JSON" in _detail(
        _run(ctx, "playground_decimals"), "playground_decimals"
    )
    client.outputs["/play_run"] = UNAVAILABLE_CARD
    assert "unavailable card (lane_timeout)" in _detail(
        _run(ctx, "playground_decimals"), "playground_decimals"
    )
    # the live tab refreshes its Code blocks with gr.update(value=…): the JSON rides inside
    as_updates = tuple(
        {"visible": True, "value": text, "__type__": "update"} if i in (2, 3) else text
        for i, text in enumerate(HAVERSINE_OUTPUTS)
    ) + ({"visible": False, "props": {"__type__": "update"}, "__type__": "update"},)
    client.outputs["/play_run"] = as_updates
    report = _run(ctx, "playground_decimals")
    assert report.ok, report.lines()
    assert vc.unwrap_update({"__type__": "update", "value": "x"}) == "x"
    assert vc.unwrap_update({"__type__": "update", "visible": False}) is None
    assert vc.unwrap_update({"result": 3}) == {"result": 3} and vc.unwrap_update("s") == "s"
    assert vc.texts_of([{"__type__": "update", "value": "<p>a</p>"}, {"__type__": "update"}]) == [
        "<p>a</p>"
    ]
    # a request that names its arguments is echoed by name
    named = list(HAVERSINE_OUTPUTS)
    named[2] = json.dumps(
        {"module": "geodesy", "function": "haversine_distance", "args": dict(vc.DECIMALS_ARGS)}
    )
    client.outputs["/play_run"] = tuple(named)
    assert _run(ctx, "playground_decimals").ok


def test_playground_must_return_three(ctx, client) -> None:
    client.outputs["/play_run"] = ('<div class="alg-hero-num">4</div>', {"result": 4})
    report = _run(ctx, "playground_levenshtein")
    assert report.failures == ["playground_levenshtein"]
    assert "did not return 3" in _detail(report, "playground_levenshtein")
    client.outputs["/play_run"] = {"result": [3], "latency_ms": 13.0}
    assert _run(ctx, "playground_levenshtein").ok
    client.outputs["/play_run"] = "<td>13 ms</td><td>3</td>"
    assert _run(ctx, "playground_levenshtein").ok
    client.outputs["/play_run"] = "<td>13 ms</td><td>30</td>"
    assert not _run(ctx, "playground_levenshtein").ok


def test_race_accepts_every_documented_state_and_nothing_else(ctx, client) -> None:
    for card, word in (
        (HELD_CARD, "held"),
        (NOT_RECORDED_CARD, "not recorded"),
        (UNAVAILABLE_CARD, "lane_timeout"),
    ):
        client.outputs["/race_run"] = card
        report = _run(ctx, "race_cell")
        assert report.ok, report.lines()
        assert word in _detail(report, "race_cell")
        assert "documented state" in _detail(report, "race_cell")
    client.outputs["/race_run"] = "<article class='alg-card'>3.2×</article>"
    assert "neither a result card nor a documented state" in _detail(
        _run(ctx, "race_cell"), "race_cell"
    )
    one_lane = RACE_CARD.replace('<div class="alg-lane-val">41.0 ms</div>', "", 1)
    assert one_lane != RACE_CARD
    client.outputs["/race_run"] = one_lane
    assert "needs both" in _detail(_run(ctx, "race_cell"), "race_cell")


def test_llm_parity_is_strict(ctx, client) -> None:
    client.outputs["/llm_run"] = UNAVAILABLE_CARD
    assert "unavailable card" in _detail(_run(ctx, "llm_rmsnorm_parity"), "llm_rmsnorm_parity")
    client.outputs["/llm_run"] = NO_PARITY_CARD
    assert "no parity chip" in _detail(_run(ctx, "llm_rmsnorm_parity"), "llm_rmsnorm_parity")
    client.outputs["/llm_run"] = LLM_CARD
    assert (
        _detail(_run(ctx, "llm_rmsnorm_parity"), "llm_rmsnorm_parity")
        == f"/llm_run parity chip · {HW}"
    )


def test_governed_lane_reads_the_snake_case_code(ctx, client) -> None:
    """The cards print lowercase snake_case codes; the hosted-API constant is upper-case."""
    client.outputs["/gov_run"] = cards.render_unavailable_card(
        title="Hosted API", error_code="hosted_not_configured", hint="The tenant key is not set."
    )
    report = _run(ctx, "governed_lane")
    assert report.ok and _detail(report, "governed_lane") == (
        "/gov_run hosted_not_configured (no key on this Space)"
    )
    client.outputs["/gov_run"] = cards.render_unavailable_card(
        title="Hosted API", error_code="hosted_rate_limited", hint="Try again in a minute."
    )
    assert "throttled" in _detail(_run(ctx, "governed_lane"), "governed_lane")


def test_governed_lane_outcomes(ctx, client) -> None:
    client.outputs["/gov_run"] = (
        '<article class="alg-card"><h3>Receipt</h3><code>execution_id: exe_01</code></article>',
        {"receipt": {"execution_id": "exe_01", "integrity": "hmac-sha256:..."}},
    )
    assert _detail(_run(ctx, "governed_lane"), "governed_lane") == "/gov_run receipt"
    client.outputs["/gov_run"] = (
        '<article class="alg-card alg-card-warn">Denied by gate min_confidence</article>'
    )
    assert _detail(_run(ctx, "governed_lane"), "governed_lane") == "/gov_run gate denial"
    client.outputs["/gov_run"] = cards.render_unavailable_card(
        title="Hosted API", error_code="HOSTED-RATE-LIMITED", hint="Try again in a minute."
    )
    assert _run(ctx, "governed_lane").ok
    client.outputs["/gov_run"] = cards.render_unavailable_card(
        title="Hosted API", error_code="HOSTED-UNAVAILABLE", hint="The engine answered 503."
    )
    assert "hosted_unavailable" in _detail(_run(ctx, "governed_lane"), "governed_lane")
    assert not _run(ctx, "governed_lane").ok
    client.outputs["/gov_run"] = "<p>Thinking</p>"
    assert "neither" in _detail(_run(ctx, "governed_lane"), "governed_lane")


# The Governed card exactly as the tab renders it — never a hand-built card: round 3's gate
# expected an `engine <status>` chip the tab never paints and failed on every real receipt.
gov_tab = _import("tabs.gov_tab", ALGENTA_DIR)
webhook = _import("webhook", ALGENTA_DIR)
GOV_DECISION = "8b4a1f2e-0c3d-4e5f-9a6b-7c8d9e0f1a2b"
GOV_INTEGRITY = {
    "policy_snapshot_id": "policy-snap-7",
    "schema_snapshot_id": "schema-snap-3",
    "manifest_version": "1.0.24",
}
GOV_HOSTED = hosted_api.HostedGoverned(lambda key, base: None, env={"ALGENTA_API_KEY": "k"})


def _real_receipt(status: str, code: int | None) -> hosted_api.Receipt:
    return hosted_api.Receipt(
        decision_id=GOV_DECISION,
        webhook_url="https://thyn-ai-algenta.hf.space/hook/n0nce",
        execution_status=status,
        response_code=code,
        executed_at="2026-09-22T14:02:00Z",
        policy_snapshot_id=GOV_INTEGRITY["policy_snapshot_id"],
        schema_snapshot_id=GOV_INTEGRITY["schema_snapshot_id"],
        manifest_version=GOV_INTEGRITY["manifest_version"],
        payload_summary={},
        safety_overridden=False,
        raw={"execution_status": status, "response_code": code},
    )


def _engine_post() -> object:
    """The engine's POST accepted by the real hook: armed for the decision, then delivered with
    the same integrity block and summary — the only way a `webhook received` block is drawn."""
    hook = webhook.make_hook(
        {"SPACE_ID": "thyn-ai/algenta", "SPACE_HOST": "thyn-ai-algenta.hf.space"},
        nonce_factory=lambda: "n0nce",
    )
    hook.expect(GOV_DECISION, integrity=GOV_INTEGRITY, chosen_action="expand_eu", confidence=0.87)
    body = {
        "event": webhook.WEBHOOK_EVENT,
        "decision_id": GOV_DECISION,
        "decision": {"chosen_action": "expand_eu", "confidence": 0.87},
        "integrity": {**GOV_INTEGRITY, "result_hash": "sha256:res"},
    }
    event = hook.accept("n0nce", json.dumps(body).encode(), {})
    assert event is not None, "the real hook accepts the engine's own POST"
    return event


def _rendered_receipt(status: str, code: int | None, *, webhook_event: object = None) -> str:
    out = gov_tab.Outcome(receipt=_real_receipt(status, code))
    if webhook_event is not None:
        out.webhook = webhook_event
    return gov_tab.render_receipt(out, GOV_HOSTED)


def test_receipt_status_reads_the_tabs_own_chip() -> None:
    """`receipt_status` parses the chip `gov_tab.receipt_status_chip` renders — delivered, failed
    (`webhook_failed`, with or without an HTTP code) and any other engine status."""
    assert vc.receipt_status(_rendered_receipt("delivered", 200)) == (
        "delivered",
        cards.CHIP_KINDS["live"],
        "delivered · HTTP 200",
    )
    assert vc.receipt_status(_rendered_receipt("failed", None)) == (
        "failed",
        cards.ERROR_TONE,
        "webhook_failed · no HTTP response",
    )
    assert vc.receipt_status(_rendered_receipt("failed", 502)) == (
        "failed",
        cards.ERROR_TONE,
        "webhook_failed · HTTP 502",
    )
    assert vc.receipt_status(_rendered_receipt("queued", 202)) == (
        "queued",
        "neutral",
        "engine queued · HTTP 202",
    )
    assert vc.receipt_status(NOT_CONFIGURED_CARD) is None
    assert (
        vc.receipt_status("<article class='alg-card'>Held by the confidence gate</article>") is None
    )
    assert vc.RECEIPT_TITLE == gov_tab.TITLE_RECEIPT
    assert vc.STATUS_DELIVERED == gov_tab.STATUS_DELIVERED
    assert vc.STATUS_FAILED == gov_tab.STATUS_FAILED
    assert vc.CODE_WEBHOOK_FAILED == gov_tab.CODE_WEBHOOK_FAILED
    assert vc.DELIVERY_CLAIM in gov_tab.WEBHOOK_MISSED_TEXT


def test_receipt_tone_matches_the_execution_status(ctx, client) -> None:
    """On the cards `gov_tab.render_receipt` renders: a delivered execution is the live chip on
    the quiet card; a failed one the red chip on the red card, no delivery claim; `webhook
    received` is painted on a delivered receipt alone; a failure during the run is the red
    card; without a key the not-configured card is the documented state."""
    delivered = _rendered_receipt("delivered", 200)
    client.outputs["/gov_run"] = (delivered, "{}", "", {})
    report = _run(ctx, "receipt_tone")
    assert report.ok and _detail(report, "receipt_tone") == (
        "/gov_run receipt 'delivered · HTTP 200' painted ok"
    )
    assert "alg-card-err" not in delivered
    for code, chip in ((None, "no HTTP response"), (502, "HTTP 502")):
        failed = _rendered_receipt("failed", code)
        assert "alg-card-err" in failed and vc.WEBHOOK_RECEIVED_TEXT not in failed
        assert vc.DELIVERY_CLAIM not in vc.plain_text(failed)
        client.outputs["/gov_run"] = (failed, "{}", "", {})
        report = _run(ctx, "receipt_tone")
        assert report.ok and _detail(report, "receipt_tone") == (
            f"/gov_run receipt 'webhook_failed · {chip}' painted err"
        )
    # an engine status that is neither: the neutral chip, and never `webhook received`
    queued = _rendered_receipt("queued", 202)
    client.outputs["/gov_run"] = (queued, "{}", "", {})
    report = _run(ctx, "receipt_tone")
    assert report.ok and _detail(report, "receipt_tone") == (
        "/gov_run receipt 'engine queued · HTTP 202' painted neutral"
    )
    # the engine's POST accepted by the real hook: on a delivered receipt it is the block the
    # gate allows; on a failed one the same block is a lie the gate must catch
    event = _engine_post()
    delivered_with_post = _rendered_receipt("delivered", 200, webhook_event=event)
    assert vc.WEBHOOK_RECEIVED_TEXT in vc.plain_text(delivered_with_post)
    client.outputs["/gov_run"] = (delivered_with_post, "{}", "", {})
    report = _run(ctx, "receipt_tone")
    assert report.ok and _detail(report, "receipt_tone") == (
        "/gov_run receipt 'delivered · HTTP 200' painted ok, webhook received"
    )
    failed_with_post = _rendered_receipt("failed", None, webhook_event=event)
    client.outputs["/gov_run"] = (failed_with_post, "{}", "", {})
    report = _run(ctx, "receipt_tone")
    if vc.WEBHOOK_RECEIVED_TEXT in vc.plain_text(failed_with_post):
        assert not report.ok
        assert "'webhook received' painted on a failed receipt" in _detail(report, "receipt_tone")
    else:  # the tab keeps the block off a failed receipt — the rule the gate asserts
        assert report.ok and "painted err" in _detail(report, "receipt_tone")
    # a failure during the run: the red card passes, the quiet card does not
    client.outputs["/gov_run"] = gov_tab.render_error(
        hosted_api.EngineError(webhook.HINT_NO_PUBLIC_URL, code=webhook.CODE_NO_PUBLIC_URL),
        GOV_HOSTED,
    )
    report = _run(ctx, "receipt_tone")
    assert report.ok and _detail(report, "receipt_tone") == (
        "/gov_run webhook_url_unavailable on the red card"
    )
    client.outputs["/gov_run"] = cards.render_unavailable_card(
        title="Governed", error_code="webhook_url_unavailable", hint="No public https address."
    )
    assert _detail(_run(ctx, "receipt_tone"), "receipt_tone") == (
        "/gov_run webhook_url_unavailable: a failure during the run on a quiet card, not the red one"
    )
    # documented states and the denial, rendered by the tab
    client.outputs["/gov_run"] = gov_tab.not_configured_card(GOV_HOSTED)
    report = _run(ctx, "receipt_tone")
    assert report.ok and "no key on this Space" in _detail(report, "receipt_tone")
    client.outputs["/gov_run"] = gov_tab.render_error(
        hosted_api.RateLimitedError("Throttled.", retry_after_s=60), GOV_HOSTED
    )
    assert _run(ctx, "receipt_tone").ok
    denial = gov_tab.Outcome(
        denial=hosted_api.Denial(
            code="execution_blocked_confidence",
            gate="confidence",
            message="Confidence 0.61 is below the floor.",
            status_code=409,
        )
    )
    client.outputs["/gov_run"] = gov_tab.render_denial(denial, GOV_HOSTED)
    assert _detail(_run(ctx, "receipt_tone"), "receipt_tone") == (
        "/gov_run gate denial (held), no receipt to tone"
    )
    client.outputs["/gov_run"] = "<p>Thinking</p>"
    assert "neither" in _detail(_run(ctx, "receipt_tone"), "receipt_tone")


def test_keyed_phase_turns_the_not_configured_card_into_a_failure(ctx, client, monkeypatch) -> None:
    """With `--phase keyed` the tool was told a key is loaded: the not-configured card is a
    broken precondition on every Governed gate, and `KEYED_REQUIRED` stays selected."""
    monkeypatch.setitem(vc._PHASE, "value", vc.PHASE_KEYED)
    assert vc.keyed() and vc.phase() == "keyed"
    for name in ("governed_lane", "receipt_tone", "webhook_privacy"):
        report = _run(ctx, name)
        assert not report.ok, name
        assert "in the keyed phase" in _detail(report, name)
    # a real receipt passes in the keyed phase as it does without one
    client.outputs["/gov_run"] = (_rendered_receipt("delivered", 200), "{}", "", {})
    assert _run(ctx, "governed_lane", "receipt_tone").ok
    # --only cannot drop what the key unlocks
    names = [n for n, _ in vc.select_checks({"health_ready"})]
    assert names[0] == "governed_lane" or "health_ready" in names
    assert set(vc.KEYED_REQUIRED) <= set(names) and "health_ready" in names
    assert [n for n, _ in vc.select_checks(set())] == [n for n, _ in vc.checks_for()]
    monkeypatch.setitem(vc._PHASE, "value", vc.PHASE_NOKEY)
    assert [n for n, _ in vc.select_checks({"health_ready"})] == ["health_ready"]
    with pytest.raises(ValueError, match="phase must be one of"):
        vc.set_phase("maybe")
    assert vc.set_phase("keyed") == "keyed" and vc.keyed()
    # axe in the keyed phase needs the Governed controls on the page it audited
    report = _run(ctx, "axe_serious_critical")
    assert not report.ok and "never saw the Governed controls" in _detail(
        report, "axe_serious_critical"
    )
    _with_audit(
        monkeypatch,
        run_presses=[p for p in CLEAN_AUDIT.run_presses if "/gov" not in p]
        + ["desktop/light/gov Run governed execution"],
    )
    report = _run(ctx, "axe_serious_critical")
    assert report.ok and _detail(report, "axe_serious_critical") == (
        "axe: 0 serious or critical over 28 tab views (keyed phase, Governed controls included)"
    )
    # the refusal probe must have found the Governed form
    report = _run(ctx, "refusal_convention")
    assert not report.ok and "gov: no form to refuse" in _detail(report, "refusal_convention")
    assert "in the keyed phase" in _detail(report, "refusal_convention")


def test_webhook_privacy_fails_on_each_leak(ctx, client, monkeypatch) -> None:
    nonce = "CTd0spedChhS89CmhN6tCgDyosxUDUX1"
    ctx.fetch.routes["/health"] = (
        200,
        json.dumps({"ready": True, "webhook": {"path": f"/hook/{nonce}", "public": False}}),
    )
    detail = _detail(_run(ctx, "webhook_privacy"), "webhook_privacy")
    assert detail.startswith("/health publishes the webhook path with its nonce (/hook/CTd0sp…)")
    ctx.fetch.routes["/health"] = (
        200,
        json.dumps({"ready": True, "webhook": {"prefix": "/hook", "public": True}}),
    )
    report = _run(ctx, "webhook_privacy")
    assert report.ok and _detail(report, "webhook_privacy").startswith("/health names /hook/…")
    posted = vc._TEST_POSTS
    assert posted[-2][0] == f"http://127.0.0.1:7860/hook/{vc.GUESSED_NONCE}"
    assert posted[-1][0] == "http://127.0.0.1:7860/hook"
    assert posted[-1][1]["forged_by"] == "verify"
    # the receipt card prints the webhook URL with its nonce
    receipt = gov_tab.Outcome(receipt=_real_receipt("delivered", 200))
    receipt.webhook_url = f"https://thyn-ai-algenta.hf.space/hook/{nonce}"
    card = gov_tab.render_receipt(receipt, GOV_HOSTED)
    client.outputs["/gov_run"] = (card, "{}", "", {})
    report = _run(ctx, "webhook_privacy")
    if vc.HOOK_URL_RE.search(vc.plain_text(card)):
        assert not report.ok and "prints the webhook URL with its nonce" in _detail(
            report, "webhook_privacy"
        )
    else:  # the tab no longer prints the row — the rule the gate asserts
        assert report.ok and "prints no webhook URL" in _detail(report, "webhook_privacy")
    # a guessed POST that is accepted
    client.outputs["/gov_run"] = NOT_CONFIGURED_CARD
    monkeypatch.setattr(vc, "post_json", lambda url, body, timeout: (200, '{"received": true}'))
    detail = _detail(_run(ctx, "webhook_privacy"), "webhook_privacy")
    assert "POST /hook/<guessed nonce> answered 200, not 400 or 404" in detail
    assert "POST /hook answered 200" in detail
    # a 503 snapshot (a container that lost its kernels) is read all the same
    monkeypatch.setattr(vc, "post_json", lambda url, body, timeout: (404, ""))
    ctx.fetch.routes["/health"] = (503, json.dumps({"webhook": {"prefix": "/hook"}}))
    report = _run(ctx, "webhook_privacy")
    assert report.ok and _detail(report, "webhook_privacy").startswith("/health (HTTP 503) names")
    ctx.fetch.routes["/health"] = (503, json.dumps({"webhook": {"path": f"/hook/{nonce}"}}))
    assert "publishes the webhook path" in _detail(_run(ctx, "webhook_privacy"), "webhook_privacy")
    ctx.fetch.routes["/health"] = (503, "not json")
    assert "answered 503 and is not JSON" in _detail(
        _run(ctx, "webhook_privacy"), "webhook_privacy"
    )
    assert vc._hook_prefix({"webhook": {"path": "/hook/abc"}}) == "/hook"
    assert vc._hook_prefix({"webhook": {"path": "/hook"}}) == "/hook"
    assert vc._hook_prefix({"webhook": {"prefix": "/engine-hook"}}) == "/engine-hook"
    assert vc._hook_prefix({}) == hosted_api.HOOK_PREFIX


def test_foreign_family_needs_a_coded_card_not_a_stock_error(ctx, client) -> None:
    class StockError(Exception):
        pass

    def stock(**kwargs: object) -> object:
        if kwargs.get("family") == vc.FOREIGN_FAMILY:
            raise StockError(f"Value: {vc.FOREIGN_FAMILY} {vc.CHOICES_REFUSAL}: []")
        return play_run(**kwargs)

    client.outputs["/play_run"] = stock
    detail = _detail(_run(ctx, "family_dropdown_foreign_value"), "family_dropdown_foreign_value")
    assert detail.startswith("/play_run family='nope_family' raised Gradio's stock error")
    assert "coded card" in detail
    client.outputs["/play_run"] = lambda **kwargs: HAVERSINE_OUTPUTS
    detail = _detail(_run(ctx, "family_dropdown_foreign_value"), "family_dropdown_foreign_value")
    assert detail == "/play_run ran a call for 'nope_family', a family this container never loaded"
    client.outputs["/play_run"] = lambda **kwargs: "<p>nothing</p>"
    assert "neither a coded card nor a result" in _detail(
        _run(ctx, "family_dropdown_foreign_value"), "family_dropdown_foreign_value"
    )
    # the cascade endpoint, when the app exposes one: a stock error fails it, a no-op passes
    client.outputs["/play_run"] = play_run
    ctx._info = {
        "named_endpoints": {
            **INFO["named_endpoints"],
            "/play_modules": _endpoint(_param("family", "stats", "Dropdown")),
        }
    }
    client.outputs["/play_modules"] = ({"__type__": "update"}, {"__type__": "update"})
    report = _run(ctx, "family_dropdown_foreign_value")
    assert report.ok and _detail(report, "family_dropdown_foreign_value").endswith(
        "/play_modules → no-op (nothing to cascade to)"
    )

    def stock_cascade(**kwargs: object) -> object:
        raise StockError(f"Value: {vc.FOREIGN_FAMILY} {vc.CHOICES_REFUSAL}: []")

    client.outputs["/play_modules"] = stock_cascade
    detail = _detail(_run(ctx, "family_dropdown_foreign_value"), "family_dropdown_foreign_value")
    assert "/play_modules raised StockError (is not in the list of choices)" in detail


def test_round_4_browser_gates_fail_on_each_defect(ctx, client, monkeypatch) -> None:
    # stock code chrome: the </> label and the line-number gutter
    _with_audit(
        monkeypatch,
        stock_code_chrome=[
            "desktop/light/eco stock block label with the </> icon 'Kernel snippet'",
            "desktop/light/eco line-number gutter (19 lines)",
        ],
    )
    detail = _detail(_run(ctx, "no_stock_code_labels"), "no_stock_code_labels")
    assert detail.startswith("2 stock element(s) on 9 Code blocks: desktop/light/eco stock block")
    assert "line-number gutter (19 lines)" in detail
    _with_audit(monkeypatch, code_blocks=0)
    assert "no Code block" in _detail(_run(ctx, "no_stock_code_labels"), "no_stock_code_labels")
    # voids: a column ending far above its row after a run, and a gap between elements
    _with_audit(
        monkeypatch,
        voids=[
            "desktop/light/llm after Run RMSNorm: column 1 of 2 ends 469 px above the row's bottom",
            "desktop/light/gov at rest: column 2 of 2: 300 px between elements 1 and 2",
        ],
    )
    detail = _detail(_run(ctx, "voids"), "voids")
    assert detail.startswith("2 void(s) over 240 px in 14 column samples: desktop/light/llm after")
    _with_audit(monkeypatch, void_samples=0)
    assert "no multi-column row" in _detail(_run(ctx, "voids"), "voids")
    # the boot card's hero row froze while the tracker recorded
    _with_audit(
        monkeypatch,
        boot_rows=[
            {
                "stage": "hero",
                "elapsed": "12.0 s",
                "detail": "noisy — not recorded — spread above 15 percent · attempt 6 · measured again every 60 s until it records",
            },
        ],
        boot_hero={"status": "measured", "kernel_ms": 0.1217, "n": 21, "attempts": 18},
    )
    detail = _detail(_run(ctx, "boot_row_live"), "boot_row_live")
    assert detail.startswith("the boot card's hero row reads 'noisy — not recorded")
    assert (
        f"/health says measured {cards.fmt_ms(0.1217)} per kernel call, n = 21, attempt 18"
        in detail
    )
    assert detail.endswith("the row froze at the stage's end")
    _with_audit(
        monkeypatch,
        boot_rows=[
            {
                "stage": "hero",
                "elapsed": "1.8 s",
                "detail": f"{cards.fmt_ms(0.1217)} per kernel call, n = 21",
            }
        ],
        boot_hero={"status": "noisy", "kernel_ms": None, "n": 21, "attempts": 6},
    )
    detail = _detail(_run(ctx, "boot_row_live"), "boot_row_live")
    assert (
        f"reads '{cards.fmt_ms(0.1217)} per kernel call, n = 21' while /health says the hero is noisy,"
        " attempt 6" in detail
    )
    _with_audit(
        monkeypatch,
        boot_rows=[
            {"stage": "hero", "elapsed": "1.8 s", "detail": "noisy — not recorded · attempt 6"}
        ],
        boot_hero={"status": "noisy", "kernel_ms": None, "n": 21, "attempts": 6},
    )
    report = _run(ctx, "boot_row_live")
    assert report.ok and _detail(report, "boot_row_live") == (
        "hero row 'noisy — not recorded · attempt 6' == /health hero noisy, attempt 6"
    )
    # no hero in /health: the row must say the family did not load (the torch-less venv)
    _with_audit(
        monkeypatch,
        boot_rows=[
            {
                "stage": "hero",
                "elapsed": "0.0 s",
                "detail": "stats did not load · variant_unavailable",
            }
        ],
        boot_hero=None,
    )
    report = _run(ctx, "boot_row_live")
    assert report.ok and _detail(report, "boot_row_live") == (
        "hero row 'stats did not load · variant_unavailable' == /health hero null (the hero"
        " family did not load)"
    )
    _with_audit(monkeypatch, boot_hero=None)
    detail = _detail(_run(ctx, "boot_row_live"), "boot_row_live")
    assert detail.startswith(
        "/health carried no hero when the boot card was read, yet the row reads"
    )
    _with_audit(monkeypatch, boot_rows=[])
    assert "no hero row" in _detail(_run(ctx, "boot_row_live"), "boot_row_live")
    # the refusal convention: a message in one place only, a red card, a toast
    vc.reset_clients()
    broken = vc.RefusalAudit(
        probes=list(CLEAN_REFUSALS.probes),
        failures=[
            "desktop/light/try 'Successes A'=5000: no field message under the control ('Successes A cannot exceed Trials A.' elsewhere)",
            "desktop/light/play 'successes_a'=-5: no echo in the status row beside the action",
        ],
    )
    monkeypatch.setattr(vc, "run_refusal_audit", lambda base_url: broken)
    detail = _detail(_run(ctx, "refusal_convention"), "refusal_convention")
    assert detail.startswith(
        "2 of 9 probes: desktop/light/try 'Successes A'=5000: no field message"
    )
    vc.reset_clients()
    monkeypatch.setattr(vc, "run_refusal_audit", lambda base_url: vc.RefusalAudit())
    assert "no refusal was provoked" in _detail(
        _run(ctx, "refusal_convention"), "refusal_convention"
    )


def test_refusal_problems_read_the_page_geometry() -> None:
    control = {"top": 700, "bottom": 740, "left": 200, "right": 400}
    run = {"top": 1175, "bottom": 1224, "left": 200, "right": 460}
    under = {
        "text": "successes_a cannot be negative.",
        "inStatus": False,
        "top": 748,
        "bottom": 764,
        "left": 200,
        "right": 1200,
    }
    echo = {
        "text": "successes_a cannot be negative.",
        "top": 1232,
        "bottom": 1264,
        "left": 200,
        "right": 600,
    }
    ok = {
        "control": control,
        "run": run,
        "messages": [under],
        "status": [echo],
        "redCards": 0,
        "toasts": 0,
    }
    lead = "desktop/light/play 'successes_a'=-5"
    assert vc.refusal_problems("desktop/light/play", "successes_a", "-5", "negative", ok) == []
    # the Playground today: the field message alone, an empty status row
    play = {**ok, "status": [{"text": "", "top": 1224, "bottom": 1224, "left": 200, "right": 600}]}
    assert vc.refusal_problems("desktop/light/play", "successes_a", "-5", "negative", play) == [
        f"{lead}: no echo in the status row beside the action"
    ]
    # Try today: the status row alone
    status_only = {
        "text": "Successes A cannot exceed Trials A.",
        "inStatus": True,
        "top": 860,
        "bottom": 876,
        "left": 176,
        "right": 385,
    }
    try_state = {
        "control": {"top": 740, "bottom": 780, "left": 176, "right": 380},
        "run": {"top": 788, "bottom": 836, "left": 900, "right": 1100},
        "messages": [status_only],
        "status": [
            {"text": status_only["text"], "top": 852, "bottom": 884, "left": 176, "right": 600}
        ],
        "redCards": 0,
        "toasts": 0,
    }
    problems = vc.refusal_problems("desktop/light/try", "Successes A", "5000", "exceed", try_state)
    assert problems == [
        "desktop/light/try 'Successes A'=5000: no field message under the control"
        " ('Successes A cannot exceed Trials A.' elsewhere)"
    ]
    # a message far below the control is not "under" it; the wrong words; a red card; a toast
    far = {**under, "top": control["bottom"] + vc.FIELD_MESSAGE_REACH_PX + 1}
    problems = vc.refusal_problems(
        "d/l/play",
        "successes_a",
        "-5",
        "whole",
        {**ok, "messages": [far], "redCards": 1, "toasts": 1},
    )
    assert problems[0].endswith(
        "no field message under the control ('successes_a cannot be negative.' elsewhere)"
    )
    assert any("no message carries 'whole'" in p for p in problems)
    assert any("1 red card(s) for a refusal" in p for p in problems)
    assert any("1 toast(s)" in p for p in problems)
    silent = {**ok, "messages": [], "status": []}
    assert vc.refusal_problems("d/l/play", "successes_a", "-5", "negative", silent) == [
        "d/l/play 'successes_a'=-5: no message anywhere — the run was not refused, or silently"
    ]
    assert vc.refusal_problems("d/l/gov", "x", "1", "", {**ok, "control": None}) == [
        "d/l/gov 'x'=1: no visible control named 'x'"
    ]
    assert vc.refusal_problems("d/l/gov", "x", "1", "", None) == [
        "d/l/gov 'x'=1: the tab panel was not found"
    ]
    # a tab whose kernel is not here answers the run with its coded card: nothing to read
    coded = {**silent, "codes": ["unavailable · kernel_not_loaded"]}
    assert vc.refusal_not_exercisable(coded) == "unavailable · kernel_not_loaded"
    assert vc.refusal_not_exercisable(silent) is None
    assert vc.refusal_not_exercisable({**ok, "codes": ["unavailable · x"]}) is None
    assert vc.refusal_not_exercisable(None) is None


def test_refusal_shift_problems_name_everything_a_refusal_moved() -> None:
    """Round 11: the refusal probe snapshots the form before and after the refused press (with
    the Reproduce disclosure open) — a sibling box, a Run button, the element below the form,
    the editor's lines or height, an open disclosure's height, or Gradio's empty-editor
    placeholder each fail; a still page passes at every width."""
    assert vc.REFUSAL_CONTEXTS == (
        ("desktop", 1440, 900, "light"),
        ("tablet", 1024, 768, "light"),
        ("phone", 375, 812, "dark"),
    )
    assert vc.REFUSAL_OPEN_DISCLOSURE == "Reproduce" and vc.EMPTY_EDITOR_SELECTOR == "div.empty"
    before = {
        "boxes": [
            {"name": "Successes A", "top": 856, "bottom": 900, "left": 176, "right": 340},
            {"name": "Trials A", "top": 856, "bottom": 900, "left": 402, "right": 565},
            {"name": "Successes B", "top": 972, "bottom": 1016, "left": 176, "right": 340},
        ],
        "runs": [{"name": "Run", "top": 856, "bottom": 900, "left": 900, "right": 1100}],
        "below": {"top": 936, "bottom": 980, "left": 176, "right": 1264},
        "editors": [{"lines": 29, "top": 1400, "bottom": 2426, "left": 192, "right": 1248}],
        "accordions": [{"height": 1104}],
        "emptyEditors": 0,
    }
    lead = "phone/dark/try 'Trials A'=2.5"
    assert vc.refusal_shift_problems("phone/dark/try", "Trials A", "2.5", before, before) == []
    assert vc.refusal_shift_problems("phone/dark/try", "Trials A", "2.5", None, before) == []
    moved = {
        **before,
        "boxes": [before["boxes"][0], before["boxes"][1], {**before["boxes"][2], "top": 988}],
        "runs": [{**before["runs"][0], "top": 872}],
        "below": {**before["below"], "top": 984},
    }
    problems = vc.refusal_shift_problems("phone/dark/try", "Trials A", "2.5", before, moved)
    assert problems == [
        f"{lead}: 'Successes B' moved +16 px",
        f"{lead}: 'Run' moved +16 px",
        f"{lead}: the element below the form moved +48 px",
    ]
    # the LLM refusal that emptied the snippet: the editor vanished into a placeholder and
    # the accordion shrank; the RoPE panel's boxes below moved with it
    emptied = {
        **before,
        "editors": [],
        "accordions": [{"height": 339.8}],
        "emptyEditors": 1,
    }
    problems = vc.refusal_shift_problems("desktop/light/llm", "Rows", "50", before, emptied)
    assert problems == [
        "desktop/light/llm 'Rows'=50: 1 editor(s) before the refusal, 0 after",
        "desktop/light/llm 'Rows'=50: disclosure 0 height 1104 -> 340 px",
        "desktop/light/llm 'Rows'=50: 1 empty-editor placeholder(s)",
    ]
    fewer_lines = {**before, "editors": [{**before["editors"][0], "lines": 1, "bottom": 1436}]}
    problems = vc.refusal_shift_problems("d/l/llm", "Rows", "50", before, fewer_lines)
    assert problems == [
        "d/l/llm 'Rows'=50: editor 0 went from 29 to 1 lines",
        "d/l/llm 'Rows'=50: editor 0 height 1026 -> 36 px",
    ]
    vanished = {**before, "below": None, "boxes": before["boxes"][:2]}
    problems = vc.refusal_shift_problems("d/l/play", "n_a", "2.5", before, vanished)
    assert problems == [
        "d/l/play 'n_a'=2.5: 3 box(es) before the refusal, 2 after",
        "d/l/play 'n_a'=2.5: the element below the form appeared or vanished",
    ]
    # sub-pixel rounding is not movement
    jitter = {**before, "runs": [{**before["runs"][0], "top": 856.4}]}
    assert vc.refusal_shift_problems("d/l/try", "Trials A", "2.5", before, jitter) == []
    for key in ("boxes", "runs", "below", "editors", "accordions", "emptyEditors"):
        assert key in vc._JS_REFUSAL, key
    assert "div.empty" in vc._JS_REFUSAL and ".cm-line" in vc._JS_REFUSAL


def test_ecosystem_counts_or_unavailable(ctx, client) -> None:
    client.outputs["/eco_refresh"] = cards.render_unavailable_card(
        title="Ecosystem", error_code="hub_unreachable", hint="The Hub API did not answer."
    )
    report = _run(ctx, "ecosystem_counts")
    assert report.ok and "hub_unreachable" in _detail(report, "ecosystem_counts")
    client.outputs["/eco_refresh"] = f'<div class="alg-card-foot">huggingface.co · {TS}</div>'
    assert "no computed counts" in _detail(_run(ctx, "ecosystem_counts"), "ecosystem_counts")
    client.outputs["/eco_refresh"] = ("", None)
    assert "returned no output" in _detail(_run(ctx, "ecosystem_counts"), "ecosystem_counts")


def _hub_table(rows: int = 20, *, listed: bool = True, chips: str = "") -> str:
    body = "".join(
        f'<tr><td data-label="kernel"><a class="alg-eco-link">thyn-ai/algenta-f{i}</a></td>'
        f'<td data-label="functions">{300 + i} functions · 3 modules</td>'
        + (
            f'<td data-label="Hub">{"published 2026-09-21" if i % 2 else "12 downloads · cpu"}</td>'
            if listed
            else ""
        )
        + "</tr>"
        for i in range(rows)
    )
    return (
        f'<div class="alg-eco-head"><h2 class="alg-card-title">Hub kernels</h2>{chips}</div>'
        f'<table class="alg-stack-table alg-eco-table"><thead><tr><th>kernel</th></tr></thead>'
        f"<tbody>{body}</tbody></table>"
        '<div class="alg-card-foot">huggingface.co/api/kernels</div>'
    )


HUB_CHIPS = (
    '<div class="alg-chips"><span class="alg-chip alg-chip-neutral">20 kernels</span>'
    '<span class="alg-chip alg-chip-neutral">6,040 functions</span>'
    '<span class="alg-chip alg-chip-neutral">120 downloads</span>'
    '<span class="alg-chip alg-chip-neutral">4 likes</span>'
    f'<span class="alg-chip alg-chip-neutral">fetched {TS}</span></div>'
)
OSS_CARD = (
    '<article class="alg-card alg-eco-card"><h2 class="alg-card-title">Open-source kernels</h2>'
    '<div class="alg-hero-num">44</div><div class="alg-hero-label">packages</div></article>'
)
SDK_CARD_NO_MCP = (
    '<article class="alg-card alg-eco-card"><h2 class="alg-card-title">SDK and MCP</h2>'
    + cards.status_chip("unavailable", "unavailable · mcp_registry_not_installed")
    + "</article>"
)


def test_ecosystem_counts_checks_the_hub_table_when_the_hub_answered(ctx, client) -> None:
    """Round 1 called the whole tab a documented state as soon as the SDK card printed
    `mcp_registry_not_installed`; the Hub counts on the same page were never read."""
    client.outputs["/eco_refresh"] = (_hub_table(chips=HUB_CHIPS), OSS_CARD, SDK_CARD_NO_MCP)
    report = _run(ctx, "ecosystem_counts")
    assert report.ok, report.lines()
    assert _detail(report, "ecosystem_counts") == (
        "/eco_refresh Hub: 20 repositories · 20 listed by the Hub · 6,040 functions"
        " · 120 downloads · 4 likes; also unavailable: mcp_registry_not_installed"
    )
    # the Hub did not answer: its card's code is the documented state, the other cards named
    client.outputs["/eco_refresh"] = (
        cards.render_unavailable_card(
            title="Hub counts unavailable", error_code="hub_counts_unreachable", hint="x"
        )
        + _hub_table(listed=False),
        cards.render_unavailable_card(
            title="Open source", error_code="github_unreachable", hint="y"
        ),
        SDK_CARD_NO_MCP,
    )
    detail = _detail(_run(ctx, "ecosystem_counts"), "ecosystem_counts")
    assert detail == (
        "/eco_refresh Hub counts unavailable · hub_counts_unreachable (documented state);"
        " also unavailable: github_unreachable, mcp_registry_not_installed"
    )
    # a table with rows but an empty Hub column and no code is a broken fetch, not a state
    client.outputs["/eco_refresh"] = (_hub_table(listed=False), OSS_CARD, SDK_CARD_NO_MCP)
    detail = _detail(_run(ctx, "ecosystem_counts"), "ecosystem_counts")
    assert "no row carries a download count or a publish date" in detail
    client.outputs["/eco_refresh"] = (_hub_table(rows=0), OSS_CARD, SDK_CARD_NO_MCP)
    assert "no repository rows" in _detail(_run(ctx, "ecosystem_counts"), "ecosystem_counts")
    counts = vc.hub_counts(_hub_table(chips=HUB_CHIPS))
    assert counts == {"rows": 20, "listed": 20, "functions": 6040, "downloads": 120, "likes": 4}
    assert vc.hub_counts(_hub_table(rows=3))["functions"] is None


def test_exact_integers_accepts_the_contracts_refusal_and_never_a_rounded_echo(ctx, client) -> None:
    """The API path sends 2^53 + 1 as a JSON number; `playground.coerce` refuses it with
    `REASON_ABOVE_BROWSER_RANGE` and nothing runs — accepted beside the exact echo. A refusal
    printed next to a request that still carries a value fails, as does a rounded echo."""
    message = vc.playground.REASON_ABOVE_BROWSER_RANGE

    def refusing(**kwargs):
        if kwargs.get("function") == vc.EXACT_INT_FUNCTION:
            return (
                "",
                '<article class="alg-card alg-card-empty"></article>',
                f'<p class="alg-field-msg" role="alert">n_a {message}.</p>',
                {"__type__": "update", "visible": False},
                "# pip install kernels torch\n",
            )
        return LEVENSHTEIN_OUTPUTS

    client.outputs["/play_run"] = refusing
    report = _run(ctx, "exact_integers")
    assert report.ok, report.lines()
    assert _detail(report, "exact_integers") == (
        f"API path refuses {vc.EXACT_INT} as a JSON number ({vc.REFUSAL_WORDS!r}), nothing ran;"
        f" browser: typed {vc.EXACT_INT}, request {vc.EXACT_INT}"
    )
    assert vc.REFUSAL_WORDS == "is above the range the browser can enter exactly"

    def refusing_but_echoing(**kwargs):
        return (
            f'<p class="alg-field-msg" role="alert">n_a {message}.</p>',
            json.dumps(
                {"module": "ab_testing", "function": "z_test_proportions", "args": {"n_a": 2**53}}
            ),
        )

    client.outputs["/play_run"] = refusing_but_echoing
    detail = _detail(_run(ctx, "exact_integers"), "exact_integers")
    assert detail == f"/play_run: refused n_a={vc.EXACT_INT} yet the request carries {2**53}"
    client.outputs["/play_run"] = lambda **kwargs: (
        json.dumps(
            {"module": "ab_testing", "function": "z_test_proportions", "args": {"n_a": 2**53}}
        ),
    )
    detail = _detail(_run(ctx, "exact_integers"), "exact_integers")
    assert detail == f"/play_run: sent n_a={vc.EXACT_INT}, the request carries {2**53}"
    client.outputs["/play_run"] = lambda **kwargs: ("<article></article>",)
    detail = _detail(_run(ctx, "exact_integers"), "exact_integers")
    assert "neither a Request-and-response JSON" in detail


def test_every_remaining_endpoint_is_called_once(ctx, client) -> None:
    ctx._info = {
        "named_endpoints": {
            **INFO["named_endpoints"],
            "/try_snippet_mcp": _endpoint(_param("successes_a", 200, "Number")),
            "/try_gpu_status": _endpoint(),
            "/llm_rope": _endpoint(_param("tokens", 64, "Number")),
        }
    }
    client.outputs["/try_snippet_mcp"] = '{"jsonrpc": "2.0"}'
    client.outputs["/try_gpu_status"] = UNAVAILABLE_CARD.replace("lane_timeout", "gpu_offline")
    client.outputs["/llm_rope"] = LLM_CARD
    report = _run(ctx, "every_endpoint_answers")
    assert report.ok, report.lines()
    detail = _detail(report, "every_endpoint_answers")
    assert detail == "3 further endpoints answered; unavailable: /try_gpu_status gpu_offline"
    names = [n for n, _ in client.calls]
    assert names == [
        "/llm_rope",
        "/try_gpu_status",
        "/try_snippet_mcp",
    ]  # the six tab calls are not repeated
    assert dict(client.calls)["/try_snippet_mcp"] == {"successes_a": 200}
    client.outputs["/llm_rope"] = LLM_CARD
    # a selector cascade answers the default selection with value-less updates (the value
    # guard's no-op); the gate asks it once more for a changed selection and names the no-op
    ctx._info["named_endpoints"]["/play_form"] = _endpoint(
        _param("fam", "stats", "Dropdown"),
        _param("mod", "ab_testing", "Dropdown"),
        _param("fn", "z_test_proportions", "Dropdown"),
    )
    noop = ({"__type__": "update"}, {"props": {"__type__": "update"}, "__type__": "update"})

    def play_form(**kwargs):
        if kwargs == {"fam": "stats", "mod": "ab_testing", "fn": "z_test_proportions"}:
            return noop
        return ({"__type__": "update", "value": "levenshtein_distance"}, "# pip install kernels\n")

    client.outputs["/play_form"] = play_form
    report = _run(ctx, "every_endpoint_answers")
    assert report.ok, report.lines()
    assert _detail(report, "every_endpoint_answers") == (
        "4 further endpoints answered; unavailable: /try_gpu_status gpu_offline;"
        " no-op on the default selection, answered on a changed one: /play_form"
    )
    form_calls = [kw for n, kw in client.calls if n == "/play_form"]
    assert form_calls == [
        {"fam": "stats", "mod": "ab_testing", "fn": "z_test_proportions"},
        {"fam": "text", "mod": "text.fuzzy", "fn": "levenshtein_distance"},
    ]
    assert vc.is_noop(noop) and not vc.is_noop(("", {"__type__": "update"})) and not vc.is_noop(())
    # the Races candidate cascade (`race_sizes`) has the same guard: the default candidate is a
    # no-op, another candidate answers (a foreign id snaps back to the first offered, with values)
    ctx._info["named_endpoints"]["/race_sizes"] = _endpoint(
        _param("race_id", "levenshtein", "Dropdown")
    )

    def race_sizes(**kwargs):
        if kwargs == {"race_id": "levenshtein"}:
            return noop
        return (
            {"__type__": "update", "value": "levenshtein"},
            {"__type__": "update", "value": "M"},
            '<article class="alg-card alg-card-empty">Levenshtein</article>',
        )

    client.outputs["/race_sizes"] = race_sizes
    report = _run(ctx, "every_endpoint_answers")
    assert report.ok, report.lines()
    assert "/race_sizes" in _detail(report, "every_endpoint_answers")
    assert [kw for n, kw in client.calls if n == "/race_sizes"] == [
        {"race_id": "levenshtein"},
        {"race_id": vc.RACE_ALTERNATE},
    ]
    del ctx._info["named_endpoints"]["/race_sizes"]
    del client.outputs["/race_sizes"]
    client.outputs["/play_form"] = lambda **kwargs: noop  # a no-op on the changed selection too
    assert "/play_form returned no output" in _detail(
        _run(ctx, "every_endpoint_answers"), "every_endpoint_answers"
    )
    del ctx._info["named_endpoints"]["/play_form"]
    client.outputs["/llm_rope"] = ""
    assert "returned no output" in _detail(
        _run(ctx, "every_endpoint_answers"), "every_endpoint_answers"
    )
    del client.outputs["/llm_rope"]
    assert "raised RuntimeError" in _detail(
        _run(ctx, "every_endpoint_answers"), "every_endpoint_answers"
    )


def test_dropdown_choice_refusal_carries_the_hint(ctx, client) -> None:
    class Refusing(FakeClient):
        def predict(self, *, api_name, **kwargs):
            raise RuntimeError("Value: text.fuzzy is not in the list of choices: ['agent_runtime']")

    vc.reset_clients()
    vc.CLIENT_FACTORY = lambda base_url: Refusing({})
    detail = _detail(_run(ctx, "playground_levenshtein"), "playground_levenshtein")
    assert "not in the list of choices" in detail and "allow_custom_value=True" in detail


def test_client_errors_become_failures_not_crashes(ctx, client) -> None:
    del client.outputs["/race_run"]
    report = _run(ctx, "race_cell")
    assert report.failures == ["race_cell"]
    assert "raised RuntimeError" in _detail(report, "race_cell")


def test_client_connection_failure_is_one_failed_check(ctx, monkeypatch) -> None:
    def boom(base_url: str):
        raise OSError("connection refused")

    monkeypatch.setattr(vc, "CLIENT_FACTORY", boom)
    report = _run(ctx, "hero_result")
    assert report.failures == ["hero_result"]
    assert "could not connect" in _detail(report, "hero_result")


# ---------------------------------------------------------------------------
# Page checks
# ---------------------------------------------------------------------------


def test_health_must_be_ready(ctx, http, client) -> None:
    http.routes["/health"] = (200, HEALTH_BOOTING)
    assert _detail(_run(ctx, "health_ready"), "health_ready") == "/health not ready"
    http.routes["/health"] = (200, json.dumps({"ready": False, "error": "kernels: cache_missing"}))
    assert "cache_missing" in _detail(_run(ctx, "health_ready"), "health_ready")
    http.routes["/health"] = (503, "")
    assert "answered 503" in _detail(_run(ctx, "health_ready"), "health_ready")
    http.routes["/health"] = (200, "<html>")
    assert "not JSON" in _detail(_run(ctx, "health_ready"), "health_ready")
    http.routes["/health"] = (200, json.dumps({"stage": "ready"}))
    assert _run(ctx, "health_ready").ok


def test_health_ready_prints_the_boot_duration_not_the_uptime(ctx, http, client) -> None:
    http.routes["/health"] = (200, HEALTH_UPTIME)
    detail = _detail(_run(ctx, "health_ready"), "health_ready")
    assert detail == "ready, 3 stages, booted in 41.0 s"
    assert "1296" not in detail, "the uptime is not the boot"
    snapshot = json.loads(HEALTH_UPTIME)
    assert vc.boot_duration(snapshot) == 41.0
    # the two-clock snapshot `algenta_spaces.boot` writes now: elapsed_s is the boot itself
    two_clocks = {**snapshot, "elapsed_s": 4.1, "uptime_s": 3612.0, "boot_finished_utc": TS}
    assert vc.boot_duration(two_clocks) == 4.1, "the registry's own figure wins"
    http.routes["/health"] = (200, json.dumps(two_clocks))
    assert _detail(_run(ctx, "health_ready"), "health_ready") == "ready, 3 stages, booted in 4.1 s"
    assert vc.boot_duration({"stages": [{"id": "x"}], "elapsed_s": 5.0}) is None
    assert vc.boot_duration({"stages": "nope"}) is None
    assert _detail(_run(ctx, "health_ready"), "health_ready").startswith("ready, 3 stages")
    http.routes["/health"] = (200, HEALTH_READY)
    assert _detail(_run(ctx, "health_ready"), "health_ready") == "ready, 1 stages"


def test_shared_stamp_matches_staged_sha(ctx, http, client) -> None:
    assert _run(ctx, "shared_stamp").ok
    ctx.expected_shared_sha = "d" * 64
    assert "!= staged" in _detail(_run(ctx, "shared_stamp"), "shared_stamp")
    ctx.expected_shared_sha = None
    report = _run(ctx, "shared_stamp")
    assert report.skipped == ["shared_stamp"] and "local run" in _detail(report, "shared_stamp")
    ctx.expected_shared_sha = "dev"
    http.routes["/"] = (200, PAGE.replace(SHARED, "dev"))
    assert _detail(_run(ctx, "shared_stamp"), "shared_stamp") == "shared dev"
    ctx.expected_shared_sha = SHARED
    http.routes["/"] = (200, "<html>no footer</html>")
    assert "no build stamp" in _detail(_run(ctx, "shared_stamp"), "shared_stamp")


def test_stamp_regex_reads_both_config_encodings() -> None:
    """Gradio 6.28 inlines the config with \\u003e for `>`; the tool and the flagship read both."""
    literal = f'"alg-shell-stamp\\">build {SHARED}</span>"'
    escaped = f'alg-shell-stamp\\"\\u003ebuild {SHARED}\\u003c/span\\u003e'
    assert vr.SHA_STAMP_RE.search(literal) and vc.STAMP_RE.search(literal)
    assert vc.STAMP_RE.search(escaped).group(1) == SHARED
    assert vr.SHA_STAMP_RE.search(escaped).group(1) == SHARED
    assert vc.STAMP_RE.search(FOOTER_PLAIN).group(1) == SHARED
    assert vr.footer_stamp_of(PAGE_ESCAPED) == SHARED
    # the shared shell's stamp: twelve hex with the full sha in a `title` before or after the class
    short = SHARED[:12]
    before = f'<span title="build {SHARED}" class="alg-shell-stamp">build {short}</span>'
    after = f'<span class="alg-shell-stamp" title="build {SHARED}">build {short}</span>'
    escaped = (
        f'\\u003cspan title=\\"build {SHARED}\\" class=\\"alg-shell-stamp\\"\\u003ebuild {short}'
        "\\u003c/span\\u003e"
    )
    for page in (before, after, escaped):
        assert vc.STAMP_RE.search(page).group(1) == short, page
        assert vr.footer_stamp_of(page) == short, page
    assert vc.STAMP_RE.search('<span class="alg-shell-stamp">build dev</span>').group(1) == "dev"
    assert vr.footer_stamp_of('<span class="alg-shell-stamp">build dev</span>') is None


def test_shared_stamp_reads_a_gradio_6_page(ctx, http, client) -> None:
    http.routes["/"] = (200, PAGE_ESCAPED)
    assert _detail(_run(ctx, "shared_stamp"), "shared_stamp") == f"shared {SHARED[:12]}"
    http.routes["/"] = (
        200,
        PAGE_ESCAPED.replace(f"build {SHARED}", f"build {SHARED[:12]}").replace(
            'span class=\\"alg-shell-stamp\\"',
            f'span title=\\"build {SHARED}\\" class=\\"alg-shell-stamp\\"',
        ),
    )
    report = _run(ctx, "shared_stamp")
    assert report.ok and _detail(report, "shared_stamp") == f"shared {SHARED[:12]}"


# ---------------------------------------------------------------------------
# Browser checks on a prepared audit
# ---------------------------------------------------------------------------


def test_probe_reopen_files_a_click_once():
    """Codna review on #1150: `_probe_reopen` files a click as a reopen or as a failure, never
    both — a list that showed over a changed form is one failure, and `reopens +
    len(reopen_failures)` is the click count the gate reports."""

    class Keyboard:
        def press(self, key: str) -> None:
            pass

    class Locator:
        def filter(self, **kw: Any) -> Locator:
            return self

        def count(self) -> int:
            return 0

    class Page:
        def __init__(self, states: list[dict[str, Any]]) -> None:
            self.states = iter(states)
            self.keyboard = Keyboard()

        def evaluate(self, script: str) -> dict[str, Any]:
            return next(self.states)

        def locator(self, selector: str) -> Locator:
            return Locator()

        def wait_for_selector(self, selector: str, **kw: Any) -> None:
            pass

        def wait_for_timeout(self, ms: int) -> None:
            pass

    class Box:
        def get_attribute(self, name: str) -> str:
            return "false"

        def click(self) -> None:
            pass

    same = {"combos": [["Family", "text"]], "fields": 3}
    changed = {"combos": [["Family", "graph"]], "fields": 3}
    audit = vc.Audit()
    vc._probe_reopen(Page([same, same]), Box(), "Family", "desktop/light/play", audit, "click")
    assert audit.reopens == 1 and audit.reopen_failures == []
    vc._probe_reopen(Page([same, changed]), Box(), "Family", "desktop/light/play", audit, "click")
    assert audit.reopens == 1, "a changed form is not a reopen"
    assert audit.reopen_failures == ["desktop/light/play 'Family' click: Family 'text' -> 'graph'"]
    assert audit.reopens + len(audit.reopen_failures) == 2, "two clicks, each filed once"


def _with_audit(monkeypatch: pytest.MonkeyPatch, **fields) -> None:
    vc.reset_clients()  # the audit is cached per base URL
    audit = vc.Audit(
        **{k: (list(v) if isinstance(v, list) else v) for k, v in vars(CLEAN_AUDIT).items()}
    )
    for k, v in fields.items():
        setattr(audit, k, v)
    monkeypatch.setattr(vc, "run_audit", lambda base_url, slugs=None: audit)


def _with_cls(monkeypatch: pytest.MonkeyPatch, **fields) -> None:
    vc.reset_clients()
    result = vc.ClsAudit(loads=list(CLEAN_CLS.loads), worst=CLEAN_CLS.worst)
    for k, v in fields.items():
        setattr(result, k, v)
    monkeypatch.setattr(vc, "run_cls_audit", lambda base_url, slugs=None: result)


def test_browser_checks_pass_and_report_counts(ctx, client) -> None:
    report = _run(ctx, *(fn.__name__ for fn in vc.BROWSER_CHECKS))
    assert report.ok, report.lines()
    assert _detail(report, "console_clean") == "0 console errors over 7 tab views"
    assert _detail(report, "targets_44px") == "48 targets, all >= 44 px (20 listboxes opened)"
    assert _detail(report, "contrast_hero") == "30 samples >= 4.5:1"
    assert _detail(report, "no_identifiers_in_copy") == (
        "210 text nodes, no identifiers in primary copy"
    )
    assert _detail(report, "axe_serious_critical") == (
        "axe: 0 serious or critical over 28 tab views (nokey phase)"
    )
    assert _detail(report, "contrast_buttons") == "120 button samples >= 4.5:1"
    assert _detail(report, "contrast_code") == "64 token samples >= 4.5:1"
    assert _detail(report, "value_boxes_unclipped") == (
        "18 value boxes inside their boxes, values visible"
    )
    assert _detail(report, "no_stock_chrome") == (
        "6 samples over 2 runs, no stock chrome or stock colour"
    )
    assert _detail(report, "nav_separators") == "6 nav rows, separators only between links"
    assert _detail(report, "checkboxes_dark_unfilled") == "4 unchecked boxes empty in dark mode"
    assert _detail(report, "cls_budget") == "36 loads, worst 0.0012 <= 0.05"


def test_new_gates_fail_on_each_defect(ctx, client, monkeypatch) -> None:
    _with_audit(
        monkeypatch,
        button_contrast_failures=[
            "desktop/light/try button.alg-run 'Run' hover 1.19:1",
            "desktop/light/landing button[role=tab] 'Try it' selected 4.23:1",
        ],
    )
    detail = _detail(_run(ctx, "contrast_buttons"), "contrast_buttons")
    assert detail.startswith("2 of 120 button samples under 4.5:1: ")
    assert detail.index("1.19:1") < detail.index("4.23:1"), "worst ratio first"
    _with_audit(
        monkeypatch, code_contrast_failures=["desktop/dark/gov .cm-editor span.ͼb 'key' 2.9:1"]
    )
    assert "2.9:1" in _detail(_run(ctx, "contrast_code"), "contrast_code")
    _with_audit(monkeypatch, code_contrast_samples=0)
    assert "no code tokens" in _detail(_run(ctx, "contrast_code"), "contrast_code")
    _with_audit(
        monkeypatch,
        clipped_values=[
            "desktop/light/llm input[type=number] 'Rows' 56x44 overflows its parent 85x24"
        ],
    )
    assert "overflows its parent 85x24" in _detail(
        _run(ctx, "value_boxes_unclipped"), "value_boxes_unclipped"
    )
    _with_audit(
        monkeypatch,
        stock_chrome=["desktop/light/try Run +400 ms div.progress-text 'processing | 0.4s'"],
    )
    assert "processing | 0.4s" in _detail(_run(ctx, "no_stock_chrome"), "no_stock_chrome")
    _with_audit(monkeypatch, chrome_runs=[])
    assert "no run button" in _detail(_run(ctx, "no_stock_chrome"), "no_stock_chrome")
    _with_audit(
        monkeypatch,
        nav_separator_failures=["phone/light/landing .alg-shell-nav-links row 2 starts with '·'"],
    )
    assert "row 2 starts with" in _detail(_run(ctx, "nav_separators"), "nav_separators")
    _with_audit(monkeypatch, nav_rows_checked=0)
    assert "no nav rows" in _detail(_run(ctx, "nav_separators"), "nav_separators")
    _with_audit(
        monkeypatch,
        button_sample_errors=["desktop/light/try button hover: ElementHandle.hover: Timeout"],
    )
    detail = _detail(_run(ctx, "contrast_buttons"), "contrast_buttons")
    assert detail.startswith("1 state(s) not readable: ")
    _with_audit(
        monkeypatch,
        filled_checkboxes=[
            "desktop/dark/llm input[type=checkbox] 'Interleaved pairs' fill rgb(59, 130, 246)"
        ],
    )
    assert "Interleaved pairs" in _detail(
        _run(ctx, "checkboxes_dark_unfilled"), "checkboxes_dark_unfilled"
    )
    _with_cls(
        monkeypatch,
        failures=["desktop/gov #2 0.1313 at 314 ms (div.block, div.block.alg-disclosure)"],
        worst=0.1313,
    )
    detail = _detail(_run(ctx, "cls_budget"), "cls_budget")
    assert detail.startswith("1 of 36 loads over 0.05 (worst 0.1313): desktop/gov #2 0.1313")
    _with_cls(monkeypatch, loads=[])
    assert "no page load" in _detail(_run(ctx, "cls_budget"), "cls_budget")


def test_small_targets_are_summarised_by_selector() -> None:
    items = [
        "desktop/light/landing a.alg-shell-nav-link 'Docs' 31x44",
        "desktop/light/landing a.alg-shell-nav-link 'GitHub' 42x44",
        "phone/dark/llm button.reset-button '↺' 27x22",
        "desktop/dark/play input.border-none[role=combobox] 'Family' 338x39",
    ]
    summary = vc.small_target_summary(items)
    assert summary.startswith("a.alg-shell-nav-link ×2 (e.g. desktop/light/landing 'Docs' 31x44); ")
    assert "button.reset-button ×1 (e.g. phone/dark/llm '↺' 27x22)" in summary
    assert "input.border-none[role=combobox] ×1" in summary
    assert vc.small_target_summary([]) == ""


def test_browser_checks_fail_on_each_defect(ctx, client, monkeypatch) -> None:
    _with_audit(monkeypatch, console_errors=["error: Failed to load resource: 404 /favicon.ico"])
    assert "1 console error(s)" in _detail(_run(ctx, "console_clean"), "console_clean")
    _with_audit(monkeypatch, page_errors=["TypeError: x is undefined"])
    assert "TypeError" in _detail(_run(ctx, "console_clean"), "console_clean")
    _with_audit(monkeypatch, overflow=["phone/Races 412>375"])
    assert "412>375" in _detail(_run(ctx, "no_horizontal_scroll"), "no_horizontal_scroll")
    _with_audit(monkeypatch, overflow=["desktop/Races 1500>1440"])
    assert _run(ctx, "no_horizontal_scroll").ok  # only the 375 px gate is a rule
    _with_audit(monkeypatch, small_targets=["phone/dark/try button.alg-run 'Run' 88x36"])
    detail = _detail(_run(ctx, "targets_44px"), "targets_44px")
    assert detail.startswith(
        "1 of 48 target(s) under 44 px (20 listboxes opened): button.alg-run ×1"
    )
    assert "88x36" in detail
    _with_audit(monkeypatch, axe_violations=["desktop/landing color-contrast (serious, 2)"])
    assert "color-contrast" in _detail(_run(ctx, "axe_serious_critical"), "axe_serious_critical")
    _with_audit(
        monkeypatch,
        contrast_failures=[
            "desktop/landing .alg-chip 3.90:1",
            "desktop/light/try .alg-hero-num 4.12:1",
            "desktop/dark/try .alg-hero-num 4.23:1",
        ],
    )
    detail = _detail(_run(ctx, "contrast_hero"), "contrast_hero")
    assert detail.startswith("3 of 30 samples under 4.5:1: desktop/landing .alg-chip 3.90:1")
    assert detail.index("4.12:1") < detail.index("4.23:1"), "worst ratio first"
    # the open listbox: options under 44 px and a dropdown that would not open
    _with_audit(
        monkeypatch,
        small_targets=["desktop/light/play li.item[role=option] 'mde' 338x35.6"],
        listboxes_opened=3,
    )
    detail = _detail(_run(ctx, "targets_44px"), "targets_44px")
    assert detail.startswith(
        "1 of 48 target(s) under 44 px (3 listboxes opened): li.item[role=option] ×1"
    )
    _with_audit(monkeypatch, listbox_errors=["phone/dark/eco 'Family': Timeout 3000ms"])
    detail = _detail(_run(ctx, "targets_44px"), "targets_44px")
    assert detail.startswith("1 dropdown(s) not measured: phone/dark/eco 'Family'")
    # identifiers in primary copy, grouped by selector, the Playground's labels excepted
    _with_audit(
        monkeypatch,
        identifier_hits=[
            "desktop/light/try .alg-card-sub 'successes_a, n_a' in 'ab_testing.z_test_proportions · successes_a 50'",
            "desktop/light/landing span.alg-shell-badge 'torch25-cpu-aarch64-darwin' in 'Hub kernels · torch25-cpu-aarch64-darwin'",
            "desktop/light/gov p.alg-card-reason 'ALGENTA_API_KEY' in 'the Space secret ALGENTA_API_KEY turns it on.'",
        ],
    )
    detail = _detail(_run(ctx, "no_identifiers_in_copy"), "no_identifiers_in_copy")
    assert detail.startswith("3 identifier(s) in primary copy over 210 text nodes: ")
    assert ".alg-card-sub ×1 (e.g. desktop/light/try 'successes_a, n_a'" in detail
    assert "ALGENTA_API_KEY" in detail and "torch25-" in detail
    _with_audit(monkeypatch, copy_nodes=0)
    assert "no primary copy" in _detail(
        _run(ctx, "no_identifiers_in_copy"), "no_identifiers_in_copy"
    )


def test_round_3_gates_fail_on_each_defect(ctx, client, monkeypatch) -> None:
    # toasts: one seen after a governed run, and an audit that never looked
    _with_audit(
        monkeypatch,
        toasts=["desktop/light/gov Run governed execution +400 ms 'Error × No module named …'"],
    )
    detail = _detail(_run(ctx, "no_toasts"), "no_toasts")
    assert detail.startswith("1 toast(s) in 34 samples over 7 run presses: desktop/light/gov")
    _with_audit(monkeypatch, toast_samples=0)
    assert "no toast sample" in _detail(_run(ctx, "no_toasts"), "no_toasts")
    # dismissals that changed the form, and a listbox that would not open
    _with_audit(
        monkeypatch,
        dismissal_failures=[
            "desktop/light/play 'Family' click-away: Function 'z_test_proportions' ->"
            " 'confidence_interval_proportion'; 4 fields -> 3",
            "desktop/light/play 'Function' Tab: successes_a '123' -> '200'",
        ],
    )
    detail = _detail(_run(ctx, "dropdown_dismissal"), "dropdown_dismissal")
    assert detail.startswith("2 of 15 dismissals changed the form: desktop/light/play 'Family'")
    assert "'123' -> '200'" in detail
    _with_audit(monkeypatch, dismissal_errors=["desktop/light/eco 'Family' Tab: Timeout 3000ms"])
    assert "1 dismissal(s) not measured" in _detail(
        _run(ctx, "dropdown_dismissal"), "dropdown_dismissal"
    )
    _with_audit(monkeypatch, dismissals=0)
    assert "no dropdown" in _detail(_run(ctx, "dropdown_dismissal"), "dropdown_dismissal")
    # round 5: a click on the focused, closed box that opened nothing, and a probe not read
    _with_audit(
        monkeypatch,
        reopens=8,
        reopen_failures=[
            "desktop/light/play 'Family' click after Escape: no listbox within 3000 ms",
            "desktop/light/race 'Race' click after Tab-arrival: no listbox within 3000 ms",
        ],
    )
    detail = _detail(_run(ctx, "dropdown_reopens"), "dropdown_reopens")
    assert detail.startswith(
        "2 of 10 clicks opened nothing or changed the form: desktop/light/play"
    )
    # Codna review on #1150: a click whose list showed over a changed form is a failure, not a
    # reopen as well — 3 clean reopens and 2 changed forms are 5 clicks, never 7
    _with_audit(
        monkeypatch,
        reopens=3,
        reopen_failures=[
            "desktop/light/play 'Family' click after Escape: Family 'text' -> 'graph'",
            "desktop/light/race 'Race' click after Tab-arrival: rows '123' -> '200'",
        ],
    )
    detail = _detail(_run(ctx, "dropdown_reopens"), "dropdown_reopens")
    assert detail.startswith("2 of 5 clicks opened nothing or changed the form: desktop/light/play")
    _with_audit(monkeypatch, reopens=9, reopen_errors=["desktop/light/eco 'Family' Tab-arrival: x"])
    assert "1 probe(s) not measured" in _detail(_run(ctx, "dropdown_reopens"), "dropdown_reopens")
    _with_audit(monkeypatch, reopens=0)
    assert "no focused dropdown" in _detail(_run(ctx, "dropdown_reopens"), "dropdown_reopens")
    # the native proof: a family whose library is not loaded, or a Python substitute, fails
    broken_native = json.loads(HEALTH_READY)
    broken_native["facts"]["kernels"]["text"]["native"] = {
        **NATIVE_PROOF,
        "library": "text_fallback.py",
        "loaded": False,
        "error": "NativeUnavailable: refused",
    }
    ctx.fetch.routes["/health"] = (200, json.dumps(broken_native))
    detail = _detail(_run(ctx, "native_only"), "native_only")
    assert detail.startswith(
        "1 of 2 families: text: library 'text_fallback.py' is not a shared library"
    )
    assert "library not loaded (NativeUnavailable: refused)" in detail
    no_facts = {k: v for k, v in json.loads(HEALTH_READY).items() if k != "facts"}
    ctx.fetch.routes["/health"] = (200, json.dumps(no_facts))
    assert "carries no facts" in _detail(_run(ctx, "native_only"), "native_only")
    ctx.fetch.routes["/health"] = (200, HEALTH_READY)
    # the Hub table outgrowing its block at one width, and a run that measured nothing
    vc.reset_clients()
    clipped = vc.EcoTableAudit(
        samples=list(CLEAN_ECO_TABLE.samples),
        failures=[
            "1024 px: table right 1103 > block right 976",
            "1024 px: block scrolls 1055 in 928 px",
        ],
    )
    monkeypatch.setattr(vc, "run_eco_table_audit", lambda base_url: clipped)
    detail = _detail(_run(ctx, "eco_table_fits"), "eco_table_fits")
    assert detail.startswith("2 width(s) do not fit: 1024 px: table right 1103 > block right 976")
    vc.reset_clients()
    monkeypatch.setattr(vc, "run_eco_table_audit", lambda base_url: vc.EcoTableAudit())
    assert "not measured" in _detail(_run(ctx, "eco_table_fits"), "eco_table_fits")
    vc.reset_clients()
    monkeypatch.setattr(vc, "run_eco_table_audit", lambda base_url: CLEAN_ECO_TABLE)
    # the pure judge behind the table audit
    fits = {
        "tableRight": 976.0,
        "wrapRight": 976.0,
        "scrollWidth": 928,
        "clientWidth": 928,
        "docScroll": 1024,
        "inner": 1024,
        "backends": True,
    }
    assert vc.eco_table_problems(1024, fits) == []
    assert vc.eco_table_problems(1440, {**fits, "backends": False}) == [
        "backends column missing at the desktop width"
    ]
    wide = {**fits, "tableRight": 1103.2, "scrollWidth": 1055, "docScroll": 1103}
    assert vc.eco_table_problems(1024, wide) == [
        "table right 1103 > block right 976",
        "block scrolls 1055 in 928 px",
        "page scrolls sideways (1103 > 1024)",
    ]
    # the boot card: a stage that ran prints 0.0 s, the rows do not sum to the foot
    _with_audit(
        monkeypatch,
        boot_rows=[
            {"stage": "host", "elapsed": "0.0 s", "detail": "macOS arm64"},
            {"stage": "kernels", "elapsed": "0.0 s", "detail": "19 families warm in 1.7 s"},
            {"stage": "hero", "elapsed": "1.4 s", "detail": "0.11 ms per kernel call"},
        ],
        boot_foot=f"booted in 3.7 s · finished {TS}",
    )
    detail = _detail(_run(ctx, "boot_card_timings"), "boot_card_timings")
    assert detail.startswith("3 stages: 0.0 + 0.0 + 1.4 = 1.4 s, foot 3.7 s, /health — s; ")
    assert "the rows sum to 1.4 s, the foot says 3.7 s" in detail
    # with the stages' own clocks in /health the 0.0 s row is named against what it ran
    ctx.fetch.routes["/health"] = (
        200,
        json.dumps(
            {
                "ready": True,
                "error": None,
                "elapsed_s": 3.7,
                "uptime_s": 90.0,
                "stages": [
                    {"id": "host", "started_at": 0.0, "finished_at": 0.02},
                    {"id": "kernels", "started_at": 0.02, "finished_at": 1.72},
                    {"id": "hero", "started_at": 1.72, "finished_at": 3.12},
                ],
            }
        ),
    )
    detail = _detail(_run(ctx, "boot_card_timings"), "boot_card_timings")
    assert "kernels prints 0.0 s but ran 1.70 s" in detail
    assert "the foot says 3.7 s, /health booted in 3.70 s" not in detail
    _with_audit(monkeypatch, boot_rows=[])
    assert "no stage rows" in _detail(_run(ctx, "boot_card_timings"), "boot_card_timings")
    # the footer stamp: three lines of a 64-hex sha at 375 px, and a stamp that is not one
    _with_audit(
        monkeypatch,
        stamp_samples=[
            {
                "where": "phone/light/landing",
                "text": f"build {SHARED}",
                "w": 279,
                "h": 60,
                "lines": 3,
            }
        ],
    )
    detail = _detail(_run(ctx, "footer_stamp_one_line"), "footer_stamp_one_line")
    assert detail == f"phone/light/landing 'build {SHARED}' 279x60 px, 3 lines"
    _with_audit(
        monkeypatch,
        stamp_samples=[
            {"where": "phone/light/landing", "text": "built today", "w": 1, "h": 1, "lines": 1}
        ],
    )
    assert "not 'build <sha>'" in _detail(
        _run(ctx, "footer_stamp_one_line"), "footer_stamp_one_line"
    )
    _with_audit(monkeypatch, stamp_samples=[])
    assert "not measured" in _detail(_run(ctx, "footer_stamp_one_line"), "footer_stamp_one_line")
    # the permalink gate: promises the form did not keep, and a load that never happened
    vc.reset_clients()
    broken = vc.PermalinkAudit(
        loads=list(CLEAN_PERMALINKS.loads),
        failures=[
            "desktop/light play_args_only: box promises x=1, the form shows 'no control'",
            "phone/dark unknown_tab: box '?fn=text.fuzzy.levenshtein_distance' names no tab",
        ],
    )
    monkeypatch.setattr(vc, "run_permalink_audit", lambda base_url: broken)
    detail = _detail(_run(ctx, "permalink_truth"), "permalink_truth")
    assert detail.startswith("2 promise(s) the form did not keep over 20 loads: desktop/light")
    vc.reset_clients()
    monkeypatch.setattr(vc, "run_permalink_audit", lambda base_url: vc.PermalinkAudit())
    assert "no link was loaded" in _detail(_run(ctx, "permalink_truth"), "permalink_truth")
    # the exact-integer probe: the browser rounded 2^53 + 1 away without a word
    vc.reset_clients()
    monkeypatch.setattr(vc, "run_permalink_audit", lambda base_url: CLEAN_PERMALINKS)
    rounded = vc.ExactIntAudit(typed=str(vc.EXACT_INT), request=str(vc.EXACT_INT - 1))
    monkeypatch.setattr(vc, "run_exact_int_audit", lambda base_url: rounded)
    detail = _detail(_run(ctx, "exact_integers"), "exact_integers")
    assert detail == (
        f"API path echoes {vc.EXACT_INT} exactly; browser: typed {vc.EXACT_INT}, the request"
        f" carries {vc.EXACT_INT - 1} and no message under the field"
    )
    vc.reset_clients()
    refused = vc.ExactIntAudit(
        typed=str(vc.EXACT_INT), message="n_a must be a whole number below 2^53; use the API."
    )
    monkeypatch.setattr(vc, "run_exact_int_audit", lambda base_url: refused)
    report = _run(ctx, "exact_integers")
    assert report.ok and "refused with a message" in _detail(report, "exact_integers")
    # the API path itself must echo the integer exactly
    vc.reset_clients()
    monkeypatch.setattr(vc, "run_exact_int_audit", lambda base_url: CLEAN_EXACT_INT)

    def rounding_play_run(**kwargs: object) -> object:
        outputs = list(play_run(**kwargs))
        outputs[2] = outputs[2].replace(str(vc.EXACT_INT), str(float(vc.EXACT_INT)))
        return tuple(outputs)

    client.outputs["/play_run"] = rounding_play_run
    detail = _detail(_run(ctx, "exact_integers"), "exact_integers")
    assert detail.startswith(f"/play_run: sent n_a={vc.EXACT_INT}, the request carries")
    assert vc._int_in_request('{"args": {"n_a": 9007199254740993}}') == "9007199254740993"
    assert vc._int_in_request('{"args": [200, 9007199254740992]}') == "9007199254740992"
    assert vc._int_in_request('"n_a": 9007199254740993,') == "9007199254740993"
    assert vc._int_in_request("") == ""


def _form(
    selected: str,
    box: str,
    *,
    combos: list[tuple[str, str]] | None = None,
    nums: list[tuple[str, str]] | None = None,
    texts: list[tuple[str, str]] | None = None,
    radios: list[str] | None = None,
) -> dict:
    return {
        "selected": selected,
        "box": box,
        "combos": combos or [],
        "nums": nums or [],
        "texts": texts or [],
        "radios": radios or [],
        "checks": [],
        "jsons": [],
        "fields": len(nums or []) + len(texts or []),
    }


HELPERS = {
    "try_hero": "ab_testing.z_test_proportions",
    "try_labels": {
        "successes_a": "Successes A",
        "n_a": "Trials A",
        "successes_b": "Successes B",
        "n_b": "Trials B",
    },
    "race_titles": {"text.fuzzy.levenshtein_distance": "Levenshtein distance"},
}
PLAY_DEFAULT = {
    "combos": [("Family", "stats"), ("Module", "ab_testing"), ("Function", "z_test_proportions")],
    "nums": [("successes_a", "200"), ("n_a", "1000"), ("successes_b", "260"), ("n_b", "1000")],
}
TRY_DEFAULT = {
    "nums": [
        ("Successes A", "50"),
        ("Trials A", "1000"),
        ("Successes B", "65"),
        ("Trials B", "1000"),
    ]
}
RACE_M = {"combos": [("Race", "Levenshtein distance")], "radios": ["M · 600 × 600 characters"]}


def test_permalink_problems_name_every_promise_the_form_did_not_keep() -> None:
    """The seven shapes as the round-2 audit measured them (the box echoing the link) each name
    their broken promise; the same forms with a truthful box pass; a full shape whose box lost
    what the tab restored, or whose tab restored nothing, fails."""
    shapes = {name: (query, full) for name, query, full in vc.PERMALINK_SHAPES}
    lev = "text.fuzzy.levenshtein_distance"
    # 1 play args-only: the form is the default, the box kept args
    q, full = shapes["play_args_only"]
    state = _form("play", "?tab=play&args=%7B%22x%22%3A1%7D", **PLAY_DEFAULT)
    assert vc.permalink_problems(q, full, state, HELPERS) == [
        "box promises x=1, the form shows 'no control'"
    ]
    assert vc.permalink_problems(q, full, _form("play", "?tab=play", **PLAY_DEFAULT), HELPERS) == []
    # 2 play bad arg: lat1 blank, the box kept "north"
    q, full = shapes["play_bad_arg"]
    hav = {
        "combos": [
            ("Family", "geometry"),
            ("Module", "geodesy"),
            ("Function", "haversine_distance"),
        ],
        "nums": [("lat1", ""), ("lon1", "-0.1278"), ("lat2", "48.8566"), ("lon2", "2.3522")],
    }
    box = "?tab=play&fn=geodesy.haversine_distance&args=%7B%22lat1%22%3A%22north%22%7D"
    assert vc.permalink_problems(q, full, _form("play", box, **hav), HELPERS) == [
        "box promises lat1='north', the form shows ''"
    ]
    truthful = "?tab=play&fn=geodesy.haversine_distance"
    assert vc.permalink_problems(q, full, _form("play", truthful, **hav), HELPERS) == []
    # 3 try decimal: the field kept 50, the box said 12.5
    q, full = shapes["try_decimal_arg"]
    nums = [("Successes A", "50"), ("Trials A", "345"), ("Successes B", "67"), ("Trials B", "890")]
    box = "?tab=try&args=%7B%22successes_a%22%3A12.5%2C%22n_a%22%3A345%2C%22successes_b%22%3A67%2C%22n_b%22%3A890%7D"
    assert vc.permalink_problems(q, full, _form("try", box, nums=nums), HELPERS) == [
        "box promises successes_a=12.5, the form shows '50'"
    ]
    kept = "?tab=try&fn=ab_testing.z_test_proportions&args=%7B%22n_a%22%3A345%2C%22successes_b%22%3A67%2C%22n_b%22%3A890%7D"
    assert vc.permalink_problems(q, full, _form("try", kept, nums=nums), HELPERS) == []
    # 4 try foreign fn: defaults, the box kept fn and args
    q, full = shapes["try_foreign_fn"]
    box = f"?tab=try&fn={lev}&args=%7B%22successes_a%22%3A12%7D"
    problems = vc.permalink_problems(q, full, _form("try", box, **TRY_DEFAULT), HELPERS)
    assert problems == [
        f"box promises fn {lev}, the form shows no function control",
        "box promises successes_a=12, the form shows '50'",
    ]
    assert vc.permalink_problems(q, full, _form("try", "?tab=try", **TRY_DEFAULT), HELPERS) == []
    # 5 unknown tab: the box lost the tab and kept a foreign call
    q, full = shapes["unknown_tab"]
    box = f"?fn={lev}&args=%7B%22a%22%3A%22x%22%7D"
    problems = vc.permalink_problems(q, full, _form("try", box, **TRY_DEFAULT), HELPERS)
    assert problems[0] == f"box {box!r} names no tab"
    assert len(problems) == 3
    assert vc.permalink_problems(q, full, _form("try", "?tab=try", **TRY_DEFAULT), HELPERS) == []
    # 6 race bad size: M selected, the box said XL
    q, full = shapes["race_bad_size"]
    box = f"?tab=race&fn={lev}&args=%7B%22size%22%3A%22XL%22%7D"
    assert vc.permalink_problems(q, full, _form("race", box, **RACE_M), HELPERS) == [
        "box promises size='XL', the form shows 'M · 600 × 600 characters'"
    ]
    fixed = f"?tab=race&fn={lev}&args=%7B%22size%22%3A%22M%22%7D"
    assert vc.permalink_problems(q, full, _form("race", fixed, **RACE_M), HELPERS) == []
    # 7 race non-candidate: the default candidate, the box kept the link
    q, full = shapes["race_non_candidate"]
    box = "?tab=race&fn=ab_testing.z_test_proportions&args=%7B%22size%22%3A%22M%22%7D"
    problems = vc.permalink_problems(q, full, _form("race", box, **RACE_M), HELPERS)
    assert problems == [
        "box promises fn ab_testing.z_test_proportions, the form shows Levenshtein distance"
    ]
    assert vc.permalink_problems(q, full, _form("race", "?tab=race", **RACE_M), HELPERS) == []
    # the box names another tab than the strip shows, or nothing at all
    assert vc.permalink_problems(q, full, _form("race", "?tab=try", **RACE_M), HELPERS) == [
        "box names tab 'try', the strip shows 'race'"
    ]
    assert vc.permalink_problems(q, full, _form("race", "", **RACE_M), HELPERS) == [
        "the link box is empty"
    ]
    # a full shape: restored and kept passes; a box that lost it, or a tab that dropped it, fails
    q, full = shapes["race_levenshtein_L"]
    race_l = {
        "combos": [("Race", "Levenshtein distance")],
        "radios": ["L · 1,000 × 1,000 characters"],
    }
    kept = f"?tab=race&fn={lev}&args=%7B%22size%22%3A%22L%22%7D"
    assert full and vc.permalink_problems(q, full, _form("race", kept, **race_l), HELPERS) == []
    assert vc.permalink_problems(q, full, _form("race", "?tab=race", **race_l), HELPERS) == [
        f"box lost fn {lev} the tab restored (box '?tab=race')",
        "box lost size='L' the tab restored (box '?tab=race')",
    ]
    assert vc.permalink_problems(q, full, _form("race", "?tab=race", **RACE_M), HELPERS) == [
        f"box lost fn {lev} the tab restored (box '?tab=race')",
        "the tab did not restore size='L' (form shows 'M · 600 × 600 characters')",
    ]
    other = {"combos": [("Race", "Haversine distance")], "radios": ["M · New York to London"]}
    assert vc.permalink_problems(q, full, _form("race", "?tab=race", **other), HELPERS) == [
        f"the tab did not restore fn {lev}",
        "the tab did not restore size='L' (form shows 'M · New York to London')",
    ]
    q, full = shapes["play_levenshtein"]
    play_lev = {
        "combos": [
            ("Family", "text"),
            ("Module", "text.fuzzy"),
            ("Function", "levenshtein_distance"),
        ],
        "texts": [("a", "kitten"), ("b", "sitting")],
    }
    kept = f"?tab=play&fn={lev}&args=%7B%22a%22%3A%22kitten%22%2C%22b%22%3A%22sitting%22%7D"
    assert vc.permalink_problems(q, full, _form("play", kept, **play_lev), HELPERS) == []
    assert vc.permalink_problems(q, full, _form("play", "?tab=play", **play_lev), HELPERS) == [
        f"box lost fn {lev} the tab restored (box '?tab=play')",
        "box lost a='kitten' the tab restored (box '?tab=play')",
        "box lost b='sitting' the tab restored (box '?tab=play')",
    ]
    # the form diff the dismissal gate prints
    before = _form("play", "", **PLAY_DEFAULT)
    after = _form(
        "play",
        "",
        combos=[("Family", "stats"), ("Module", "ab_testing"), ("Function", "confidence_interval")],
        nums=[("successes", ""), ("n", ""), ("confidence", "")],
    )
    changes = vc._form_diff(before, after)
    assert changes[0] == "Function 'z_test_proportions' -> 'confidence_interval'"
    assert "4 fields -> 3" in changes
    assert vc._form_diff(before, before) == []
    assert vc._parse_link("?tab=play&fn=a.b&args=%7B%22x%22%3A1%7D") == ("play", "a.b", {"x": 1})
    assert vc._parse_link("?tab=play&args=not-json") == ("play", None, None)
    assert vc._parse_link("") == (None, None, None)
    assert len(vc.PERMALINK_SHAPES) == 10 and sum(full for _, _, full in vc.PERMALINK_SHAPES) == 3
    assert len({name for name, _, _ in vc.PERMALINK_SHAPES}) == 10


def test_identifier_patterns_catch_the_round_1_findings_and_spare_prose() -> None:
    """The gate's regexes (shared with the browser as source strings) on the strings round 1
    found in primary copy, and on the prose that must pass."""
    patterns = {name: re.compile(source) for name, source in vc.IDENTIFIER_PATTERNS}
    caught = {
        "Hub kernels · torch-universal, torch25-cpu-aarch64-darwin": "variant",
        "ab_testing.z_test_proportions · successes_a 50 · n_a 1,000": "snake_case",
        "the Space secret ALGENTA_API_KEY turns it on.": "env_name",
        "https://api.algenta.ai · 2026-09-22 20:09 UTC": "url",
        "algenta-geometry@54b91d9 · torch25-cpu-aarch64-darwin": "variant",
        "huggingface_hub": "snake_case",
    }
    for text, name in caught.items():
        assert patterns[name].search(text), (name, text)
    prose = (
        "6,040 compiled Mojo kernels",
        "19 Mojo kernel families · this container",
        "Mojo kernels running on this machine. Race them against Python.",
        "Space code Apache-2.0 · kernels under the Algenta Community License 1.1 — commercial"
        " plans at algenta.ai/pricing",
        f"local run · Apple M4 Max · 16 vCPU · Darwin arm64 · Python 3.12.5 · rulebook v{bench.RULEBOOK_VERSION}",
        "parity vs statsmodels: z Δ ≤ 1e-09 · p Δ ≤ 1e-06",
        "140 MCP tools",
        "GPU stage offline · 2026-09-22 20:08 UTC",
        "Two-proportion z-test",
        "L · 1,000 × 1,000 characters",
    )
    for text in prose:
        for name, pattern in patterns.items():
            assert not pattern.search(text), (name, text)
    assert vc.CODE_CHIP_RE.match("unavailable · gpu_status_unreachable")
    assert not vc.CODE_CHIP_RE.match("unavailable · Gpu Status")
    assert vc.COPY_ALLOW_PLAY_TAB == "play" and ".alg-form label" in vc.COPY_ALLOW_PLAY_SELECTOR
    for needle in (".cm-editor", "[role=listbox]", "[data-kind=unavailable]", "input"):
        assert needle in vc.COPY_EXCLUDE_SELECTOR, needle


def test_browser_checks_skip_loudly_without_playwright_or_axe(ctx, client, monkeypatch) -> None:
    def no_browser(base_url: str, slugs=None):
        vc.skip("playwright not installed")

    monkeypatch.setattr(vc, "run_audit", no_browser)
    monkeypatch.setattr(vc, "run_cls_audit", no_browser)
    monkeypatch.setattr(
        vc, "run_permalink_audit", lambda base_url: vc.skip("playwright not installed")
    )
    monkeypatch.setattr(
        vc, "run_exact_int_audit", lambda base_url: vc.skip("playwright not installed")
    )
    monkeypatch.setattr(
        vc, "run_eco_table_audit", lambda base_url: vc.skip("playwright not installed")
    )
    report = _run(
        ctx,
        "console_clean",
        "targets_44px",
        "cls_budget",
        "permalink_truth",
        "exact_integers",
        "eco_table_fits",
    )
    assert report.ok and report.skipped == [
        "console_clean",
        "targets_44px",
        "cls_budget",
        "permalink_truth",
        "exact_integers",
        "eco_table_fits",
    ]
    assert report.results[0].tag == "SKIP"
    assert "playwright not installed" in report.results[0].detail
    _with_audit(monkeypatch, axe_ran=False, axe_reason="axe-playwright-python not installed")
    report = _run(ctx, "axe_serious_critical")
    assert report.skipped == ["axe_serious_critical"]
    assert "axe-playwright-python" in report.results[0].detail
    assert "skipped: axe_serious_critical" in report.lines()[-1]


def test_audit_is_cached_per_base_url(ctx, client, monkeypatch) -> None:
    calls: list[str] = []

    def counting(base_url: str, slugs=None):
        calls.append(base_url)
        return CLEAN_AUDIT

    monkeypatch.setattr(vc, "run_audit", counting)
    cls_calls: list[str] = []

    def counting_cls(base_url: str, slugs=None):
        cls_calls.append(base_url)
        return CLEAN_CLS

    monkeypatch.setattr(vc, "run_cls_audit", counting_cls)
    link_calls: list[str] = []

    def counting_links(base_url: str):
        link_calls.append(base_url)
        return CLEAN_PERMALINKS

    monkeypatch.setattr(vc, "run_permalink_audit", counting_links)
    _run(
        ctx, "console_clean", "no_horizontal_scroll", "targets_44px", "contrast_hero", "cls_budget"
    )
    _run(ctx, "contrast_buttons", "cls_budget", "no_toasts", "permalink_truth")
    _run(ctx, "permalink_truth", "dropdown_dismissal")
    assert calls == ["http://127.0.0.1:7860"]
    assert cls_calls == ["http://127.0.0.1:7860"], "the CLS pass is its own cached audit"
    assert link_calls == ["http://127.0.0.1:7860"], "the permalink pass is its own cached audit"


def test_tab_labels_can_be_learned_from_the_strip() -> None:
    class Page:
        def evaluate(self, js: str):
            assert "data-tab-id" in js
            return [["try", "Try it"], ["play", "Playground"], ["", "x"], ["race", ""]]

    assert vc.read_tab_labels(Page()) == {"try": "Try it", "play": "Playground"}
    assert vc.learn_tab_labels(Page()) == {"try": "Try it", "play": "Playground"}
    assert vc._LABEL_CACHE["play"] == "Playground"
    vc.reset_clients()
    assert vc._LABEL_CACHE == {}


def test_audit_javascript_is_well_formed() -> None:
    scripts = (
        vc._JS_TARGETS,
        vc._JS_CONTRAST,
        vc._JS_OVERFLOW,
        vc._JS_BUTTON_STYLE,
        vc._JS_CODE_CONTRAST,
        vc._JS_VALUE_BOXES,
        vc._JS_CHECKBOX_FILL,
        vc._JS_NAV_SEPARATORS,
        vc._JS_STOCK_CHROME,
        vc._JS_CLS_INIT,
        vc._JS_LISTBOX,
        vc._JS_IDENTIFIERS,
        vc._JS_FORM_STATE,
        vc._JS_TOASTS,
        vc._JS_BOOT_ROWS,
        vc._JS_STAMP,
        vc._JS_TAB_SELECTED_WITH_PANEL,
        vc._JS_PANEL_SIGNATURE,
        vc._JS_REVEALED,
        vc._JS_IDLE,
        vc._JS_RUN_DISABLED,
        vc._JS_CODE_CHROME,
        vc._JS_VOIDS,
        vc._JS_REFUSAL,
    )
    for js in scripts:  # regex literals such as /[^)]+/ keep parentheses out of this count
        assert js.count("{") == js.count("}"), "unbalanced braces"
        assert js.count("[") == js.count("]"), "unbalanced brackets"
        assert "!important" not in js
        # the copy lint's one convention: never `!x`, always `x === false` / `=== null`
        assert re.search(r"!(?![=])", js) is None, js[:60]
    assert "toast-body" in vc.TOAST_SELECTOR and vc.TOAST_SELECTOR in vc.STOCK_CHROME_SELECTOR
    assert vc.DISMISSALS == ("click-away", "Tab", "Escape")
    assert vc.EXACT_INT == 2**53 + 1 and vc.LATE_SAMPLE_MS == 3000
    assert vc.VOID_MAX_PX == 240 and "'*'" in vc._JS_VOIDS
    assert (
        'data-testid="block-label"' in vc._JS_CODE_CHROME
        and ".cm-lineNumbers" in vc._JS_CODE_CHROME
    )
    assert ".alg-field-msg" in vc._JS_REFUSAL and ".alg-status" in vc._JS_REFUSAL
    assert [slug for slug, *_ in vc.REFUSAL_PROBES] == ["try", "play", "llm", "gov"]
    # round 10: the LLM tab's Rows box is refused above 32 with a sentence naming the range
    assert ("llm", "Rows", "50", "rows") in vc.REFUSAL_PROBES
    assert vc.HOOK_NONCE_RE.search("/hook/CTd0spedChhS89CmhN6tCgDyosxUDUX1")
    assert vc.HOOK_NONCE_RE.search("/hook/n0nce") is None, "a short test nonce is not the pattern"
    assert vc.HOOK_URL_RE.search("Webhook https://x.hf.space/hook/CTd0spedChhS89CmhN6tCgDyosxUDUX1")
    assert vc.PHASES == ("nokey", "keyed") and "axe_serious_critical" in vc.KEYED_REQUIRED
    assert "43.5" in vc._JS_TARGETS and "43.5" in vc._JS_LISTBOX  # 44 px with half-pixel slack
    assert "4.5" in vc._JS_CONTRAST and "4.5" in vc._JS_LISTBOX
    assert "aria-selected" in vc._JS_LISTBOX, "the highlighted option is measured too"
    assert "matchAll" in vc._JS_IDENTIFIERS and "closest(accordion)" in vc._JS_IDENTIFIERS
    assert vc.OPTION_SELECTOR == "[role=listbox] [role=option]"
    for selector in (".alg-hero-num", ".alg-chip", ".alg-shell-badge", ".alg-tile-link"):
        assert selector in vc.CONTRAST_SELECTORS, selector
    for selector in (".alg-stat-label", ".alg-stat-value", ".alg-stat-meta", ".alg-card-sub"):
        assert selector in vc.CONTRAST_SELECTORS, selector
    # The tiles are `alg-stat` (cards.tile) now; a selector for a class nothing renders would
    # read as coverage without measuring anything.
    for gone in (".alg-tile-title", ".alg-tile-value", ".alg-tile-caption"):
        assert gone not in vc.CONTRAST_SELECTORS, gone
    assert "radio" in vc._JS_TARGETS and "combobox" in vc._JS_TARGETS
    assert "::before" in vc._JS_NAV_SEPARATORS and "::after" in vc._JS_NAV_SEPARATORS
    assert ".alg-shell-nav-list" in vc.NAV_LINK_ROWS and ".alg-shell-nav-links" in vc.NAV_LINK_ROWS
    assert vc.same_code("hosted_not_configured", hosted_api.NOT_CONFIGURED_CODE)
    assert vc.same_code("HOSTED-NOT-CONFIGURED", "hosted_not_configured")
    assert not vc.same_code(None, "x") and not vc.same_code("hosted_unavailable", "x")
    assert "layout-shift" in vc._JS_CLS_INIT and "hadRecentInput" in vc._JS_CLS_INIT
    assert vc.CLS_MAX == 0.05 and vc.CLS_LOADS == 3
    assert vc.CHROME_SAMPLE_MS == (100, 400, 800)
    assert vc.AUDIT_THEMES == ("light", "dark")
    assert vc.BOOTING_CLASS == "alg-booting"
    assert vc._JS_REVEALED.count(vc.BOOTING_CLASS) == 1
    for state in ("hover", "focus", "disabled"):
        assert state in vc.BUTTON_STATES


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def test_text_helpers_read_the_real_cards() -> None:
    assert vc.foot_of(HERO_CARD) == (HW, TS)
    assert vc.foot_of(UNAVAILABLE_CARD) is None  # the unavailable foot has no stamp
    assert vc.unavailable_code(UNAVAILABLE_CARD) == "lane_timeout"
    # the cards print every code in lowercase snake_case, whatever the constant's spelling
    assert vc.unavailable_code(NOT_CONFIGURED_CARD) == _snake(hosted_api.NOT_CONFIGURED_CODE)
    assert vc.same_code(vc.unavailable_code(NOT_CONFIGURED_CARD), hosted_api.NOT_CONFIGURED_CODE)
    assert vc.unavailable_code(RACE_CARD) is None
    assert vc.unavailable_code(NOT_RECORDED_CARD) is None
    assert vc.NOT_RECORDED_RE.search(NOT_RECORDED_CARD)
    assert vc.PARITY_RE.search(HERO_CARD) and vc.PARITY_RE.search(RACE_CARD)
    assert not vc.PARITY_RE.search(NO_PARITY_CARD)
    assert len(vc.LANE_VAL_RE.findall(RACE_CARD)) == 2
    assert vc.plain_text("<b>a&amp;b</b> c") == " a&b  c"
    assert vc.texts_of(["x", None, {"k": 1}, 3]) == ["x", '{"k": 1}', "3"]
    assert vc._contains_int(["<td>0.3 ms</td><td>3</td>"], 3)
    assert not vc._contains_int(["<td>0.3 ms</td><td>13</td>"], 3)
    assert not vc._contains_int([True], 1)


# ---------------------------------------------------------------------------
# The run script QA and the golden capture use
# ---------------------------------------------------------------------------


def test_run_script_is_executable_and_sets_the_environment() -> None:
    assert RUN_SCRIPT.is_file()
    assert RUN_SCRIPT.stat().st_mode & 0o111, "not executable"
    text = RUN_SCRIPT.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    for needle in (
        "HF_HOME",
        "venv-flagship",
        "uv venv --python 3.12",
        "gradio==6.28.0",
        "playwright install chromium",
        "GRADIO_SERVER_PORT",
        "_shared",
        "app.py",
        "/health",
        "--wait",
    ):
        assert needle in text, needle
    assert FAKE_WORDS.search(text) is None


# ---------------------------------------------------------------------------
# Goldens: manifest, shots, diff
# ---------------------------------------------------------------------------

goldens = _import("_goldens", VISUAL_DIR)


def test_shot_grid_is_six_tabs_by_three_viewports_by_two_themes() -> None:
    grid = goldens._shots()
    assert len(grid) == 6 * 3 * 2 == 36
    assert {s.viewport for s in grid} == {"desktop", "tablet", "phone"}
    assert goldens.VIEWPORTS == {"desktop": (1440, 900), "tablet": (1024, 768), "phone": (375, 812)}
    assert {s.theme for s in grid} == {"light", "dark"}
    assert grid[0].stem == "try-desktop-light"
    assert grid[0].url("http://127.0.0.1:7860/") == "http://127.0.0.1:7860/?tab=try"
    assert len({s.stem for s in grid}) == 36
    assert goldens.MAX_BYTES == 500 * 1024
    assert goldens.PIXEL_THRESHOLD == 0, "strict: no unmasked pixel may differ"
    assert goldens.AA_TOLERANCE_PX == 1


def test_mask_colour_is_a_design_token() -> None:
    from algenta_spaces import design

    assert goldens._mask_color("light") == design.COLOR_TOKENS["surface-2"][0]
    assert goldens._mask_color("dark") == design.COLOR_TOKENS["surface-2"][1]


def _png(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    pil_image = pytest.importorskip("PIL.Image")
    pil_image.new("RGB", size, color).save(path)


def test_diff_is_strict_beyond_a_one_pixel_anti_aliasing_tolerance(tmp_path: Path) -> None:
    pil_image = pytest.importorskip("PIL.Image")
    pil_draw = pytest.importorskip("PIL.ImageDraw")
    golden = tmp_path / "g.png"
    _png(golden, (400, 300), (100, 100, 100))
    same = tmp_path / "same.png"
    _png(same, (400, 300), (100, 100, 100))
    d = goldens._compare(golden, same)
    assert d.ok and d.changed == 0 and d.describe().startswith("identical beyond the 1-px")
    # a uniform shift under the channel tolerance is anti-aliasing, not drift
    dim = tmp_path / "dim.png"
    _png(dim, (400, 300), (100 + goldens.CHANNEL_TOLERANCE - 4, 100, 100))
    assert goldens._compare(golden, dim).ok
    # a one-pixel line that moved by one pixel is anti-aliasing (every pixel finds its match
    # next door in either direction) ...
    line = pil_image.new("RGB", (400, 300), (100, 100, 100))
    pil_draw.Draw(line).line((0, 200, 399, 200), fill=(250, 250, 250), width=1)
    line.save(tmp_path / "line.png")
    moved = pil_image.new("RGB", (400, 300), (100, 100, 100))
    pil_draw.Draw(moved).line((0, 201, 399, 201), fill=(250, 250, 250), width=1)
    moved.save(tmp_path / "moved.png")
    assert goldens._compare(tmp_path / "line.png", tmp_path / "moved.png").changed == 0
    # ... a line that moved by two pixels is not, and one changed pixel fails
    moved2 = pil_image.new("RGB", (400, 300), (100, 100, 100))
    pil_draw.Draw(moved2).line((0, 202, 399, 202), fill=(250, 250, 250), width=1)
    moved2.save(tmp_path / "moved2.png")
    d = goldens._compare(tmp_path / "line.png", tmp_path / "moved2.png")
    assert not d.ok and d.changed >= 2 * 400
    speck = pil_image.new("RGB", (400, 300), (100, 100, 100))
    pil_draw.Draw(speck).point((200, 150), fill=(250, 250, 250))
    speck.save(tmp_path / "speck.png")
    d = goldens._compare(golden, tmp_path / "speck.png", tmp_path / "diff.png")
    assert not d.ok and d.changed == 1
    assert (
        d.describe() == "1 pixel differ beyond the 1-px anti-aliasing tolerance (0.0008% of 120000)"
    )
    assert (tmp_path / "diff.png").is_file()
    # a size change is drift by definition
    other = tmp_path / "other.png"
    _png(other, (400, 320), (100, 100, 100))
    d = goldens._compare(golden, other)
    assert not d.ok and not d.size_match and "400x320 vs golden 400x300" in d.describe()


def test_diff_fails_on_a_one_digit_change_in_an_unmasked_caption(tmp_path: Path) -> None:
    """The round-2 finding: `P95 0.20 ms` -> `P95 0.14 ms` (151 raw pixels) was filtered to 2
    and passed the old 0.1 % threshold. Planted here with Pillow's font: the digit change
    fails, the same caption drawn one pixel to the right passes, two pixels fails."""
    pil_image = pytest.importorskip("PIL.Image")
    pil_draw = pytest.importorskip("PIL.ImageDraw")
    pil_font = pytest.importorskip("PIL.ImageFont")
    font = pil_font.load_default()

    def caption(name: str, text: str, dx: int = 0) -> Path:
        image = pil_image.new("RGB", (200, 40), (255, 255, 255))
        pil_draw.Draw(image).text((10 + dx, 12), text, fill=(20, 20, 20), font=font)
        path = tmp_path / f"{name}.png"
        image.save(path)
        return path

    golden = caption("golden", "P95 0.20 ms")
    digit = goldens._compare(golden, caption("digit", "P95 0.14 ms"), tmp_path / "digit.png")
    assert not digit.ok and digit.changed >= 10, digit.describe()
    shifted = goldens._compare(golden, caption("shifted", "P95 0.20 ms", dx=1))
    assert shifted.ok and shifted.changed == 0
    far = goldens._compare(golden, caption("far", "P95 0.20 ms", dx=2))
    assert not far.ok
    # the masks cover every measured number the diff must not see
    for selector in (
        ".alg-card-result .alg-chips",
        ".alg-lane-table tbody",
        ".alg-lane-val",
        "time[data-stamp-kind]",
        ".alg-chip[data-kind='measured']",
        ".alg-hero-num",
        ".alg-status",
        ".alg-boot-detail",
        ".alg-eco-table .alg-chips",
        ".alg-board-table tbody",
    ):
        assert selector in goldens.MASK_SELECTORS, selector


def test_manifest_roundtrip_and_consistency_checks(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    slugs = ("try", "play")
    entries = []
    for shot in goldens._shots(slugs):
        path = tmp_path / f"{shot.stem}.png"
        _png(path, (shot.width // 10, shot.height // 10), (10, 20, 30))
        entries.append(
            goldens.Entry(
                file=path.name,
                tab=shot.tab,
                viewport=shot.viewport,
                theme=shot.theme,
                width=shot.width,
                height=shot.height,
                format="png",
                full_page=True,
                sha256=goldens._sha256_of(path),
                bytes=path.stat().st_size,
            )
        )
    manifest = goldens._write_manifest(entries, tmp_path)
    data = json.loads(manifest.read_text())
    assert data["pixel_threshold"] == 0 and data["max_bytes"] == 500 * 1024
    assert data["aa_tolerance_px"] == 1 and data["channel_tolerance"] == goldens.CHANNEL_TOLERANCE
    assert [e.file for e in goldens._read_manifest(tmp_path)] == sorted(e.file for e in entries)
    assert goldens._check_manifest(tmp_path, slugs) == []
    # every kind of inconsistency is named
    (tmp_path / "try-phone-dark.png").write_bytes(b"\x89PNG tampered")
    (tmp_path / "play-desktop-light.png").unlink()
    problems = goldens._check_manifest(tmp_path, slugs)
    assert any(p.startswith("try-phone-dark.png: sha256") for p in problems)
    assert any(p.startswith("try-phone-dark.png:") and "bytes" in p for p in problems)
    assert "play-desktop-light.png: missing" in problems
    assert any(
        p.endswith("no golden") for p in goldens._check_manifest(tmp_path, ("try", "play", "race"))
    )
    assert any(p.endswith("golden for no tab") for p in goldens._check_manifest(tmp_path, ("try",)))
    assert goldens._check_manifest(tmp_path / "nowhere") == [
        f"manifest unreadable: [Errno 2] No such file or directory: '{tmp_path / 'nowhere' / 'manifest.json'}'"
    ]


def test_golden_capture_refuses_fallback_fonts_and_reads_the_hero_state(tmp_path: Path) -> None:
    """The regeneration is reproducible or it refuses: fonts must have loaded, the hero state is
    a recorded precondition, every UTC stamp is masked by text."""

    class Page:
        def __init__(self, loaded: set[str]) -> None:
            self.loaded = loaded
            self.masked: list[object] = []
            self.waits: list[tuple[str, object]] = []
            self.forced: list[str] = []

        def evaluate(self, js: str, arg=None):
            if "document.fonts.load" in js:  # the design's faces, force-loaded
                self.forced = list(arg)
                return True
            assert "document.fonts.check" in js
            return arg in self.loaded

        def wait_for_function(self, js: str, arg=None, timeout: int = 0) -> None:
            assert "document.fonts" in js
            self.waits.append((js, arg))

        def locator(self, sel: str) -> str:
            return f"locator:{sel}"

        def get_by_text(self, pattern) -> str:
            return f"text:{pattern.pattern}"

    assert vc.fonts_missing(Page({"Inter", "JetBrains Mono"})) == []
    assert vc.fonts_missing(Page({"Inter"})) == ["JetBrains Mono"]
    page = Page({"Inter", "JetBrains Mono"})
    goldens._wait_for_fonts(page)
    # round 4: `document.fonts` is empty until Gradio injects the faces (~370 ms), and an empty
    # set reads `loaded` — so the wait is: the families' faces exist, the design's four faces
    # are force-loaded, every one reports loaded; the status alone is never the gate
    assert [js for js, _ in page.waits] == [goldens.FONT_FACES_JS, goldens.FONTS_LOADED_JS]
    assert page.waits[0][1] == ["Inter", "JetBrains Mono"]
    assert page.forced == list(goldens.FONT_SPECS) == page.waits[1][1]
    assert {'400 16px "Inter"', '600 16px "Inter"'} <= set(goldens.FONT_SPECS)
    assert {'400 13px "JetBrains Mono"', '600 13px "JetBrains Mono"'} <= set(goldens.FONT_SPECS)
    assert "families.every(f => have.has(f))" in goldens.FONT_FACES_JS
    assert "specs.every(s => document.fonts.check(s))" in goldens.FONTS_LOADED_JS
    assert goldens.FONTS_READY_JS not in [js for js, _ in page.waits]
    with pytest.raises(RuntimeError, match="web fonts not loaded: Inter"):
        goldens._wait_for_fonts(Page({"JetBrains Mono"}))

    # every page is loaded in independent contexts until two consecutive loads encode
    # byte-identically (round 4: a renderer now and then rasterises a whole load's text in
    # another anti-aliasing); a page that never reproduces itself is refused
    class Load:
        def __init__(self, renders: list[bytes]) -> None:
            self.renders = list(renders)
            self.loads = 0

        def __call__(self, browser, base_url, shot, out_dir, expect_hub_state):
            self.loads += 1
            (out_dir / f"{shot.stem}.png").write_bytes(self.renders.pop(0))
            return goldens.Entry(
                file=f"{shot.stem}.png",
                tab=shot.tab,
                viewport=shot.viewport,
                theme=shot.theme,
                width=shot.width,
                height=shot.height,
                format="png",
                full_page=True,
                sha256="",
                bytes=0,
                image_width=1,
                image_height=1,
            )

    shot = goldens.Shot("try", "desktop", "light", 1440, 900)
    odd_first = Load([b"odd", b"normal", b"normal"])
    entry = goldens._capture_agreed(None, "http://x", shot, tmp_path, None, capture=odd_first)
    assert odd_first.loads == 3 and (tmp_path / entry.file).read_bytes() == b"normal"
    agreed = Load([b"same", b"same"])
    goldens._capture_agreed(None, "http://x", shot, tmp_path, None, capture=agreed)
    assert agreed.loads == goldens.LOADS_TO_AGREE == 2
    never = Load([bytes([i]) for i in range(goldens.LOADS_MAX + 1)])
    with pytest.raises(RuntimeError, match="no two in a row rendered the page identically"):
        goldens._capture_agreed(None, "http://x", shot, tmp_path, None, capture=never)
    assert never.loads == goldens.LOADS_MAX == 5
    assert (
        "_capture_agreed(browser, base_url, shot, out_dir, expect_hub_state)"
        in inspect.getsource(goldens._capture_all)
    )
    masks = goldens._masks(Page(set()))
    assert masks[-1].startswith("text:") and "UTC" in masks[-1]
    assert "locator:.alg-shell-badges" in masks and "locator:.alg-eco-table tbody" in masks
    assert goldens.UTC_STAMP_RE.search("measured 2026-09-22 19:05 UTC")
    assert not goldens.UTC_STAMP_RE.search("counted at boot")
    # the opening card's state, from /health and from the manifest
    assert goldens._hero_status_of({"hero": {"status": "measured"}}) == "measured"
    assert goldens._hero_status_of({"hero": {"status": "noisy"}}) == "noisy"
    assert goldens._hero_status_of({"hero": None}) == "unknown"
    assert goldens._hero_status_of("not json") == "unknown"
    assert goldens._manifest_hero_status(tmp_path) is None
    manifest = goldens._write_manifest([], tmp_path, hero_status="measured")
    assert json.loads(manifest.read_text())["hero_status"] == "measured"
    assert goldens._manifest_hero_status(tmp_path) == "measured"
    goldens._write_manifest([], tmp_path)
    assert "hero_status" not in json.loads(manifest.read_text()), "absent when not recorded"
    assert goldens.HERO_MEASURED == "measured"


ECO_FETCHED = (
    '<div class="alg-eco-head"><h2 class="alg-card-title">On the Hub</h2></div>'
    '<table class="alg-stack-table alg-eco-table"><thead><tr><th>kernel</th><th>on the Hub</th>'
    '</tr></thead><tbody><tr><td data-label="kernel">algenta-stats</td>'
    '<td data-label="on the Hub">12 downloads · 1 like</td></tr></tbody></table>'
)
ECO_NOT_FETCHED = (
    '<article class="alg-card alg-card-quiet"><span class="alg-chip alg-chip-neutral"'
    ' data-kind="unavailable">unavailable · hub_counts_not_fetched</span></article>'
    '<table class="alg-stack-table alg-eco-table"><thead><tr><th>kernel</th></tr></thead>'
    '<tbody><tr><td data-label="kernel">algenta-stats</td></tr></tbody></table>'
)


def _config_with(table_html: str) -> dict:
    return {
        "components": [
            {"id": 1, "props": {"value": "<span class='alg-shell-stamp'>build dev</span>"}},
            {"id": 2, "props": {"value": table_html}},
            {"id": 3, "props": {}},
        ]
    }


def test_goldens_record_and_compare_the_deploy_state(tmp_path: Path) -> None:
    """The manifest carries the state the goldens picture — the opening card, the Ecosystem
    table's Hub state and the Space — read from `/health` and `/config`; a comparison against
    another state, or a manifest recording none, is refused with the reason."""
    assert goldens._hub_state_of_html(ECO_FETCHED) == "fetched"
    assert goldens._hub_state_of_html(ECO_NOT_FETCHED) == "hub_counts_not_fetched"
    assert goldens._hub_state_of_html(ECO_NOT_FETCHED.replace("not_fetched", "unreachable")) == (
        "hub_counts_unreachable"
    )
    assert goldens._hub_state_of_html("<p>no table</p>") == "unknown"
    assert goldens._hub_state_of_config(_config_with(ECO_FETCHED)) == "fetched"
    assert goldens._hub_state_of_config(_config_with(ECO_NOT_FETCHED)) == "hub_counts_not_fetched"
    assert goldens._hub_state_of_config({"components": []}) == "unknown"
    assert goldens._hub_state_of_config(None) == "unknown"
    assert goldens._space_id_of({"space_id": " thyn-ai/algenta "}) == "thyn-ai/algenta"
    assert goldens._space_id_of({"space_id": ""}) == "" and goldens._space_id_of(None) == ""
    deployed = {"hero_status": "measured", "hub_state": "fetched", "space_id": "thyn-ai/algenta"}
    local = {"hero_status": "measured", "hub_state": "hub_counts_not_fetched", "space_id": ""}
    # the manifest: state written and read back, hero_status kept for older readers
    assert goldens._manifest_state(tmp_path) is None
    manifest = goldens._write_manifest([], tmp_path, state=deployed)
    data = json.loads(manifest.read_text())
    assert data["state"] == deployed and data["hero_status"] == "measured"
    assert goldens._manifest_state(tmp_path) == deployed
    assert goldens._manifest_hero_status(tmp_path) == "measured"
    # refused: no state recorded, or a fact that differs — with the one command to regenerate
    assert goldens._state_mismatch(deployed, deployed) is None
    none = goldens._state_mismatch(None, deployed)
    assert none.startswith("the manifest records no state") and "SPACE_ID=thyn-ai/algenta" in none
    assert goldens.REGENERATE_COMMAND in none
    mismatch = goldens._state_mismatch(deployed, local)
    assert mismatch.startswith("the goldens picture another state than the app serves: ")
    assert "Ecosystem Hub state 'fetched' in the goldens, 'hub_counts_not_fetched' live" in mismatch
    assert "Space 'thyn-ai/algenta' in the goldens, 'none' live" in mismatch
    assert "opening card" not in mismatch and mismatch.endswith("regenerate in the deployed one)")
    noisy = goldens._state_mismatch(deployed, {**deployed, "hero_status": "noisy"})
    assert "opening card 'measured' in the goldens, 'noisy' live" in noisy
    assert goldens.EXIT_STATE_MISMATCH == 3 and goldens.HUB_FETCHED == "fetched"
    assert goldens.DEPLOYED_SPACE_ID == "thyn-ai/algenta"
    assert goldens.DEPLOYED_SPACE_HOST == "thyn-ai-algenta.hf.space"
    assert "--regenerate" in goldens.REGENERATE_COMMAND
    # the manifest predating the state: the pytest gate and the CLI refuse, never compare
    goldens._write_manifest([], tmp_path, hero_status="measured")
    assert goldens._manifest_state(tmp_path) is None
    # the manifest's image dimensions are the picture's own, checked against the file
    pytest.importorskip("PIL")
    _png(tmp_path / "try-phone-dark.png", (375, 1732), (10, 20, 30))
    entry = goldens.Entry(
        file="try-phone-dark.png",
        tab="try",
        viewport="phone",
        theme="dark",
        width=375,
        height=812,
        format="png",
        full_page=True,
        sha256=goldens._sha256_of(tmp_path / "try-phone-dark.png"),
        bytes=(tmp_path / "try-phone-dark.png").stat().st_size,
        image_width=375,
        image_height=1732,
    )
    goldens._write_manifest([entry], tmp_path, state=deployed)
    assert goldens._check_manifest(tmp_path, ("try",)) == [
        "try-desktop-dark: no golden",
        "try-desktop-light: no golden",
        "try-phone-light: no golden",
        "try-tablet-dark: no golden",
        "try-tablet-light: no golden",
    ]
    wrong = goldens.Entry(**{**vars(entry), "image_height": 812})
    goldens._write_manifest([wrong], tmp_path, state=deployed)
    problems = goldens._check_manifest(tmp_path, ("try",))
    assert "try-phone-dark.png: 375x1732 px, manifest says 375x812" in problems
    assert goldens._image_size(tmp_path / "try-phone-dark.png") == (375, 1732)
    old = goldens.Entry(**{**vars(entry), "image_width": 0, "image_height": 0})
    goldens._write_manifest([old], tmp_path, state=deployed)
    assert not any("px, manifest says" in p for p in goldens._check_manifest(tmp_path, ("try",)))


def test_regeneration_names_the_first_differing_row(tmp_path: Path, capsys) -> None:
    """A red golden run prints every row and then the first differing one on its own line, so
    the Integrate stage's log leads with the drift; a missing fresh shot is a difference."""
    same = goldens.Diff((10, 10), (10, 10), changed=0, total=100)
    drift = goldens.Diff((10, 10), (10, 10), changed=42, total=100)
    resized = goldens.Diff((10, 10), (10, 12), changed=100, total=100)
    assert goldens._first_difference({"b.png": same, "a.png": same}) is None
    assert goldens._first_difference(
        {"try-phone-dark.png": drift, "eco-desktop-light.png": same}
    ) == (
        "try-phone-dark.png 42 pixels differ beyond the 1-px anti-aliasing tolerance (42.0000% of 100)"
    )
    assert goldens._first_difference({"z.png": drift, "a.png": resized}) == (
        "a.png size 10x12 vs golden 10x10"
    )
    failed = goldens._report({"z.png": drift, "a.png": same}, tmp_path / "diff")
    out = capsys.readouterr().out
    assert failed == 1
    assert out.splitlines()[-1].startswith("  [FAIL] first difference: z.png 42 pixels differ")
    assert "  [OK] a.png" in out and "  [FAIL] z.png" in out
    # a manifest entry with no fresh shot counts as drift, never as a pass
    pytest.importorskip("PIL")
    _png(tmp_path / "one.png", (20, 20), (1, 2, 3))
    entry = goldens.Entry(
        file="one.png",
        tab="try",
        viewport="phone",
        theme="dark",
        width=375,
        height=812,
        format="png",
        full_page=True,
        sha256=goldens._sha256_of(tmp_path / "one.png"),
        bytes=(tmp_path / "one.png").stat().st_size,
    )
    goldens._write_manifest([entry], tmp_path)
    results = goldens._compare_all(tmp_path / "nowhere", tmp_path)
    assert not results["one.png"].ok
    manifest = json.loads((tmp_path / goldens.MANIFEST_NAME).read_text())
    assert manifest["fonts"] == ["Inter", "JetBrains Mono"] and manifest["motion"] == "off"
    assert ".alg-shell-badges" in manifest["masks"] and any(
        m.startswith("text:") and "UTC" in m for m in manifest["masks"]
    )


def test_committed_goldens_are_consistent_when_present() -> None:
    if not (goldens.GOLDEN_DIR / goldens.MANIFEST_NAME).is_file():
        pytest.skip(
            "no goldens committed yet: <venv>/bin/python tests/spaces/visual/_goldens.py"
            " --url <running app> --regenerate"
        )
    pytest.importorskip("PIL")
    problems = goldens._check_manifest()
    assert problems == [], "\n".join(problems)
    entries = goldens._read_manifest()
    assert len(entries) == 36
    assert all(e.bytes <= goldens.MAX_BYTES for e in entries)
    state = goldens._manifest_state()
    if state is None or not all(e.image_width for e in entries):
        pytest.skip(
            "the committed goldens predate the state record and the image dimensions: the"
            " Integrate stage regenerates them in the deployed state with"
            f" {goldens.REGENERATE_COMMAND!r}"
        )
    assert state["hub_state"] == goldens.HUB_FETCHED, "the committed set pictures the Space"
    assert state["space_id"] == goldens.DEPLOYED_SPACE_ID
    for e in entries:
        assert (e.image_width, e.image_height) == goldens._image_size(goldens.GOLDEN_DIR / e.file)


def test_a_golden_difference_must_reproduce_on_a_second_agreed_capture(tmp_path: Path) -> None:
    """Round 4: a renderer now and then rasterises a whole load's text in another anti-aliasing.
    `_compare_all` with a base URL captures a differing page once more (two agreeing loads) and
    the second reading decides; a difference that reproduces still fails; a size change is drift
    without a retry."""
    pil_image = pytest.importorskip("PIL.Image")
    pil_draw = pytest.importorskip("PIL.ImageDraw")
    golden_dir, fresh_dir, retry_dir = tmp_path / "golden", tmp_path / "fresh", tmp_path / "retry"
    for d in (golden_dir, fresh_dir):
        d.mkdir()
    shot = goldens._shot_of("try-desktop-light.png")
    assert shot is not None and shot.stem == "try-desktop-light"

    def png(path: Path, speck: bool = False, size: tuple[int, int] = (200, 40)) -> Path:
        image = pil_image.new("RGB", size, (255, 255, 255))
        pil_draw.Draw(image).text((10, 12), "P95 0.20 ms", fill=(20, 20, 20))
        if speck:
            pil_draw.Draw(image).point((150, 30), fill=(0, 0, 0))
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        return path

    golden = png(golden_dir / "try-desktop-light.png")
    entry = goldens.Entry(
        file="try-desktop-light.png",
        tab="try",
        viewport="desktop",
        theme="light",
        width=1440,
        height=900,
        format="png",
        full_page=True,
        sha256=goldens._sha256_of(golden),
        bytes=golden.stat().st_size,
        image_width=200,
        image_height=40,
    )
    goldens._write_manifest(
        [entry],
        golden_dir,
        state={"hero_status": "measured", "hub_state": "fetched", "space_id": "x"},
    )
    png(fresh_dir / "try-desktop-light.png", speck=True)  # the first capture differs by one pixel
    calls: list[tuple[str, str]] = []

    def recapture_normal(base_url, shot_, out_dir, hub_state):
        calls.append((base_url, shot_.stem))
        png(out_dir / "try-desktop-light.png")  # the second agreed capture equals the golden
        return entry

    results = goldens._compare_all(
        fresh_dir,
        golden_dir,
        tmp_path / "diff",
        base_url="http://x",
        expect_hub_state="fetched",
        retry_dir=retry_dir,
        recapture=recapture_normal,
    )
    assert results["try-desktop-light.png"].ok and calls == [("http://x", "try-desktop-light")]

    def recapture_same(base_url, shot_, out_dir, hub_state):
        png(out_dir / "try-desktop-light.png", speck=True)  # the difference reproduces
        return entry

    results = goldens._compare_all(
        fresh_dir,
        golden_dir,
        tmp_path / "diff",
        base_url="http://x",
        retry_dir=retry_dir,
        recapture=recapture_same,
    )
    assert not results["try-desktop-light.png"].ok and results["try-desktop-light.png"].changed == 1
    # without a base URL the first reading stands (the offline unit path), and a size change
    # is drift without a second capture
    results = goldens._compare_all(fresh_dir, golden_dir, tmp_path / "diff")
    assert not results["try-desktop-light.png"].ok
    png(fresh_dir / "try-desktop-light.png", size=(200, 48))

    def never(*args):  # pragma: no cover - the assertion below is the point
        raise AssertionError("a size change must not be recaptured")

    results = goldens._compare_all(
        fresh_dir, golden_dir, None, base_url="http://x", recapture=never
    )
    assert (
        not results["try-desktop-light.png"].ok and not results["try-desktop-light.png"].size_match
    )


class _EdgePage:
    """A page whose first `statuses` loads come back from the Hub's edge before the app does; a
    status of 200 with `mounted` False is the holding page served with a 200."""

    def __init__(self, statuses: list[int], mounted: list[bool] | None = None) -> None:
        self.statuses = list(statuses)
        self.mounted = list(mounted or [])
        self.waits: list[int] = []
        self.loads = 0
        self._status = 200

    def goto(self, url: str, wait_until: str = "load") -> object:
        self.loads += 1
        self._status = self.statuses.pop(0) if self.statuses else 200
        return type("Resp", (), {"status": self._status})()

    def wait_for_function(self, expression: str, timeout: int = 0) -> None:
        mounted = self.mounted.pop(0) if self.mounted else True
        if not mounted:
            raise TimeoutError("gradio-app never mounted")

    def wait_for_timeout(self, ms: int) -> None:
        self.waits.append(ms)


def test_cls_audit_waits_out_edge_429s_and_reports_them():
    """Two 429 answers, then the app: two backoffs (5 s, 10 s) and `edge_retries` 2; five 429s
    in a row (more than the backoff ladder) fail the load loudly instead of timing out."""
    page = _EdgePage([429, 429, 200])
    assert vc.goto_past_edge_limits(page, "https://x.hf.space/?tab=try") == 2
    assert page.loads == 3 and page.waits == [5000, 10000]
    clean = _EdgePage([200])
    assert vc.goto_past_edge_limits(clean, "https://x.hf.space/") == 0 and clean.waits == []
    stuck = _EdgePage([429] * 6)
    with pytest.raises(vc.CheckFailedError, match="holding page"):
        vc.goto_past_edge_limits(stuck, "https://x.hf.space/")
    assert stuck.loads == len(vc.EDGE_LIMIT_BACKOFF_S) + 1
    # The holding page served with a 200 (no gradio-app mounts) is waited out the same way.
    quiet = _EdgePage([200, 200], mounted=[False, True])
    assert vc.goto_past_edge_limits(quiet, "https://x.hf.space/") == 1 and quiet.waits == [5000]
    audit = vc.ClsAudit(loads=["desktop/try #1 0.0000"], worst=0.0, edge_retries=2)
    assert audit.edge_retries == 2 and audit.failures == []


class _ShellPage(_EdgePage):
    """An edge page whose shell (the footer stamp) shows only from the `shows_from`-th load."""

    def __init__(self, shows_from: int) -> None:
        super().__init__([])
        self.shows_from = shows_from
        self.stamp_waits = 0

    def wait_for_selector(self, selector: str, state: str = "attached", timeout: int = 0) -> None:
        self.stamp_waits += 1
        if self.loads < self.shows_from:
            raise TimeoutError("no stamp")


def test_cls_audit_reloads_when_the_edge_lets_the_document_through_but_not_the_shell():
    """A document without the footer stamp within SHELL_WAIT_MS is one more backoff wait; the
    third load shows the shell → 2 waits reported; a shell that never shows fails loudly."""
    page = _ShellPage(shows_from=3)
    assert vc.load_until_the_shell_shows(page, "https://x.hf.space/?tab=try") == 2
    assert page.loads == 3 and page.waits == [5000, 10000]
    never = _ShellPage(shows_from=99)
    with pytest.raises(vc.CheckFailedError, match="never showed"):
        vc.load_until_the_shell_shows(never, "https://x.hf.space/?tab=try")
    assert never.loads == len(vc.EDGE_LIMIT_BACKOFF_S) + 1


def test_boot_row_live_reads_the_batched_n_chip(ctx, client, monkeypatch) -> None:
    """Rulebook v0.4: `/health` carries `k` beside `n`, and the boot row must print the Try
    card's own n chip (`n = 21 × 103 calls`) — a row still saying `n = 21` is a wording the page
    contradicts two cards down, and the gate names the words it wanted."""
    ms = cards.fmt_ms(0.0979)
    _with_audit(
        monkeypatch,
        boot_rows=[
            {
                "stage": "hero",
                "elapsed": "1.8 s",
                "detail": f"{ms} per kernel call, n = 21 × 103 calls · statsmodels agrees",
            }
        ],
        boot_hero={"status": "measured", "kernel_ms": 0.0979, "n": 21, "k": 103, "attempts": 1},
    )
    report = _run(ctx, "boot_row_live")
    assert report.ok, report.lines()
    assert _detail(report, "boot_row_live").endswith(
        f"/health hero measured {ms} per kernel call, n = 21 × 103 calls, attempt 1"
    )
    _with_audit(
        monkeypatch,
        boot_rows=[
            {
                "stage": "hero",
                "elapsed": "1.8 s",
                "detail": f"{ms} per kernel call, n = 21 · statsmodels agrees",
            }
        ],
        boot_hero={"status": "measured", "kernel_ms": 0.0979, "n": 21, "k": 103, "attempts": 1},
    )
    report = _run(ctx, "boot_row_live")
    assert not report.ok
    assert (
        f"while /health says measured {ms} per kernel call, n = 21 × 103 calls, attempt 1"
        in _detail(report, "boot_row_live")
    )
    # an older snapshot without k: `n = 21` is the truth, as before
    _with_audit(
        monkeypatch,
        boot_rows=[
            {"stage": "hero", "elapsed": "1.8 s", "detail": f"{ms} per kernel call, n = 21"}
        ],
        boot_hero={"status": "measured", "kernel_ms": 0.0979, "n": 21, "attempts": 1},
    )
    assert _run(ctx, "boot_row_live").ok
