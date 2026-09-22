"""algenta_spaces.playground against the real Hub kernels (network, kernels + torch installed).

Runs only with `ALGENTA_SPACES_LIVE=1`:

    ALGENTA_SPACES_LIVE=1 python3 -m pytest tests/spaces/integration -q -p no:cacheprovider -m slow

Every family a hero names is loaded with `get_kernel(..., version=1, backend="cpu",
trust_remote_code=TRUST)`; a family that fails to load is reported with the reason and its heroes
skip. For each hero the table's default arguments go through `form_spec` -> `parse_inputs` ->
`kernel.execute`, and the wall time of the native call is printed per function. The committed
contract fixtures are checked against the live contracts (and written when absent), every callable
function of every loaded family gets a form, and two concurrent calls are shown to serialise (ABI §9)
by wall time against the serialised sum — the only metric a blocking lock cannot fool.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from algenta_spaces import playground as pg

pytestmark = pytest.mark.slow

LIVE = os.environ.get("ALGENTA_SPACES_LIVE") == "1"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
STATS_FIXTURE = FIXTURES / "contract_algenta_stats.json"
HERO_FIXTURE = FIXTURES / "hero_contracts.json"
HERO_FAMILIES = tuple(dict.fromkeys(hero.family for hero in pg.HEROES))
HEAVY_MIN_MS = 50.0
HEAVY_MAX_CHARS = 32_000
EFFECTIVE_WORKERS_MAX = 1.1

if not LIVE:
    pytest.skip("set ALGENTA_SPACES_LIVE=1 to run against the Hub", allow_module_level=True)

kernels_lib = pytest.importorskip("kernels")
pytest.importorskip("torch")


def _cache_writable() -> str | None:
    from huggingface_hub import constants

    cache = Path(constants.HF_HUB_CACHE)
    try:
        cache.mkdir(parents=True, exist_ok=True)
        probe = cache / ".algenta_spaces_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return f"HF cache {cache} is not writable ({exc}); set HF_HOME"
    return None


def _variant_of(kernel: Any) -> tuple[str, str]:
    """`(revision sha, variant dir)` from the loaded package's path inside the Hub cache.

    The cache is `snapshots/<sha>/... -> blobs/<hash>` symlinks, so the path is read as given,
    never resolved.
    """
    path = Path(kernel.__file__)
    match = re.search(r"/snapshots/([0-9a-f]{40})/build/([^/]+)/", str(path))
    if match is None:
        raise AssertionError(f"kernel path is not a Hub snapshot: {path}")
    return match.group(1), match.group(2)


class Fleet:
    """Every hero family, loaded once; `failures` explains the ones that did not load."""

    def __init__(self) -> None:
        self.kernels: dict[str, Any] = {}
        self.failures: dict[str, str] = {}
        self.load_s: dict[str, float] = {}

    def load(self, family: str) -> Any:
        if family in self.kernels or family in self.failures:
            return self.kernels.get(family)
        t0 = time.perf_counter()
        try:
            kernel = kernels_lib.get_kernel(
                pg.repo_id(family),
                version=pg.KERNEL_VERSION,
                backend=pg.BACKEND,
                trust_remote_code=list(pg.TRUST),
            )
        except Exception as exc:  # noqa: BLE001 - the reason is the report
            self.failures[family] = f"{type(exc).__name__}: {exc}"
            print(f"LOAD FAIL {pg.repo_id(family)}: {self.failures[family]}")
            return None
        self.load_s[family] = time.perf_counter() - t0
        self.kernels[family] = kernel
        sha, variant = _variant_of(kernel)
        print(
            f"LOAD OK   {pg.repo_id(family)} {variant} @{sha[:12]} in {self.load_s[family]:.2f} s"
        )
        return kernel

    def require(self, family: str) -> Any:
        kernel = self.load(family)
        if kernel is None:
            pytest.skip(f"{pg.repo_id(family)} did not load: {self.failures[family]}")
        return kernel


@pytest.fixture(scope="module")
def fleet() -> Fleet:
    reason = _cache_writable()
    if reason:
        pytest.skip(reason)
    return Fleet()


def _record(kernel: Any, family: str, modules: list[str] | None = None) -> dict[str, Any]:
    sha, variant = _variant_of(kernel)
    contract = kernel.CONTRACT
    if modules is not None:
        kept = {name: contract["modules"][name] for name in modules}
        decoders = {m.get("status_decoder") for m in kept.values()} - {None}
        contract = {
            "modules": kept,
            "status_names": {d: contract["status_names"][d] for d in sorted(decoders)},
        }
    return {
        "repo_id": pg.repo_id(family),
        "revision": sha,
        "variant": variant,
        "kernels_version": kernels_lib.__version__,
        "excluded_functions": list(kernel.excluded_functions),
        "contract": json.loads(json.dumps(contract)),
    }


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def test_stats_fixture_matches_the_live_darwin_contract(fleet: Fleet):
    kernel = fleet.require("stats")
    live = _record(kernel, "stats")
    if not STATS_FIXTURE.exists():
        _write(STATS_FIXTURE, live)
        print(f"WROTE {STATS_FIXTURE} ({STATS_FIXTURE.stat().st_size} bytes)")
    committed = json.loads(STATS_FIXTURE.read_text(encoding="utf-8"))
    assert committed["contract"] == live["contract"], "the committed stats contract drifted"
    assert committed["excluded_functions"] == live["excluded_functions"]
    assert committed["revision"] == live["revision"]
    assert STATS_FIXTURE.stat().st_size < 500 * 1024


def test_hero_contracts_fixture_matches_the_live_families(fleet: Fleet):
    wanted: dict[str, list[str]] = {}
    for hero in pg.HEROES:
        if hero.family != "stats":
            wanted.setdefault(hero.family, [])
            if hero.module not in wanted[hero.family]:
                wanted[hero.family].append(hero.module)
    live: dict[str, Any] = {}
    for family, modules in wanted.items():
        kernel = fleet.load(family)
        if kernel is not None:
            live[family] = _record(kernel, family, sorted(modules))
    if not HERO_FIXTURE.exists():
        _write(HERO_FIXTURE, live)
        print(f"WROTE {HERO_FIXTURE} ({HERO_FIXTURE.stat().st_size} bytes)")
    committed = json.loads(HERO_FIXTURE.read_text(encoding="utf-8"))
    for family, record in live.items():
        assert family in committed, f"{family} missing from {HERO_FIXTURE.name}"
        assert committed[family]["contract"] == record["contract"], f"{family} contract drifted"
        assert committed[family]["revision"] == record["revision"]
    if fleet.failures:
        pytest.skip(f"families not loaded: {fleet.failures}")


def test_the_table_validates_against_every_loaded_family(fleet: Fleet):
    loaded = {family: fleet.load(family) for family in HERO_FAMILIES}
    loaded = {family: kernel for family, kernel in loaded.items() if kernel is not None}
    assert loaded, f"no hero family loaded: {fleet.failures}"
    assert pg.hero_functions(loaded) is pg.HEROES


@pytest.mark.parametrize("hero", pg.HEROES, ids=lambda h: f"{h.family}:{h.qualname}")
def test_hero_executes_with_its_default_arguments(fleet: Fleet, hero: pg.Hero):
    kernel = fleet.require(hero.family)
    cold = pg.run(kernel, hero.module, hero.function, hero.args)  # may include lazy native init
    outcome = pg.run(kernel, hero.module, hero.function, hero.args)
    assert outcome.result is not None
    assert outcome.result == cold.result, "the same inputs must give the same answer"
    rendered = json.dumps(outcome.result, default=str)
    if isinstance(outcome.result, dict) and "status" in outcome.result:
        name = pg.status_name(kernel, hero.module, outcome.result["status"])
        assert pg.is_ok_status(name), (name, outcome.result)
    print(
        f"HERO {hero.family:9} {hero.qualname:55} {hero.mode:4} "
        f"warm {outcome.latency_ms:8.3f} ms  cold {cold.latency_ms:8.1f} ms  -> {rendered[:80]}"
    )
    # the snippet for what just ran renders in every dialect
    for mode in pg.MODES:
        pg.snippet(hero.family, hero.module, hero.function, hero.args, mode=mode)


def test_every_callable_function_gets_a_form(fleet: Fleet):
    total = 0
    kinds: dict[str, int] = {}
    for family in HERO_FAMILIES:
        kernel = fleet.load(family)
        if kernel is None:
            continue
        for module, function in pg.list_functions(kernel):
            spec = pg.form_spec(kernel, module, function)
            for field in spec:
                assert field.kind in pg.KINDS
                kinds[field.kind] = kinds.get(field.kind, 0) + 1
            total += 1
        for excluded in kernel.excluded_functions:
            module, function = excluded.rsplit(".", 1)
            if function != "*":
                # stripped from CONTRACT at generation time, or refused by the exclusion list
                with pytest.raises((pg.UnknownFunctionError, pg.ExcludedFunctionError)):
                    pg.form_spec(kernel, module, function)
    assert total > 0
    print(f"FORMS {total} functions across {len(fleet.kernels)} families; field kinds {kinds}")


def test_bad_input_is_refused_before_the_abi(fleet: Fleet):
    kernel = fleet.require("stats")
    with pytest.raises(pg.ValidationError, match="n_b: must be an int"):
        pg.run(kernel, "ab_testing", "z_test_proportions", {**pg.HEROES[0].args, "n_b": "ten"})
    with pytest.raises(pg.ValidationError, match="must be a finite number"):
        pg.run(kernel, "stat_tests", "pearson_r", {"x": [1.0, float("inf")], "y": [1.0, 2.0]})
    llm = fleet.load("llm")
    if llm is not None:
        rmsnorm = next(h for h in pg.heroes_for("llm") if h.function == "rmsnorm_fwd_flat")
        args = dict(rmsnorm.args)
        args["x"] = args["x"][:-1]
        with pytest.raises(pg.ValidationError, match="counts more elements than x holds"):
            pg.run(llm, "normk.rmsnorm", "rmsnorm_fwd_flat", args)


def _heavy_call(kernel: Any) -> tuple[dict[str, Any], float]:
    """A levenshtein call that takes at least HEAVY_MIN_MS warm, by growing the strings."""
    size = 2_000
    while True:
        args = {"a": "ab" * (size // 2), "b": "ba" * (size // 2)}
        pg.run(kernel, "text.fuzzy", "levenshtein_distance", args)  # warm
        warm = min(
            pg.run(kernel, "text.fuzzy", "levenshtein_distance", args).latency_ms for _ in range(2)
        )
        if warm >= HEAVY_MIN_MS or size >= HEAVY_MAX_CHARS:
            return args, warm
        size *= 2


def test_two_concurrent_calls_serialise_by_wall_time(fleet: Fleet):
    """ABI §9: total wall time of K calls from 2 threads ≈ K x one call, never ≈ K/2."""
    kernel = fleet.require("text")
    args, single_ms = _heavy_call(kernel)
    if single_ms < HEAVY_MIN_MS:
        pytest.skip(
            f"warm call is {single_ms:.1f} ms even at {HEAVY_MAX_CHARS} chars; not measurable"
        )
    calls_per_thread = 3
    spans: list[tuple[float, float]] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(calls_per_thread):
            t0 = time.perf_counter()
            pg.run(kernel, "text.fuzzy", "levenshtein_distance", args)
            t1 = time.perf_counter()
            with lock:
                spans.append((t0, t1))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = max(end for _, end in spans) - min(start for start, _ in spans)
    serial = 2 * calls_per_thread * single_ms / 1e3
    effective_workers = serial / wall
    print(
        f"CAP single={single_ms:.1f} ms calls={len(spans)} wall={wall:.2f} s "
        f"serial={serial:.2f} s effective_workers={effective_workers:.2f}"
    )
    assert len(spans) == 2 * calls_per_thread
    assert effective_workers <= EFFECTIVE_WORKERS_MAX


def test_report(fleet: Fleet):
    """Last: the load table and every family that did not load, with its reason."""
    for family, seconds in sorted(fleet.load_s.items()):
        print(f"REPORT loaded {pg.repo_id(family):28} {seconds:6.2f} s")
    for family, reason in sorted(fleet.failures.items()):
        print(f"REPORT failed {pg.repo_id(family):28} {reason}")
    assert fleet.kernels or fleet.failures
