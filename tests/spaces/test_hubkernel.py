"""algenta_spaces.hubkernel — TRUST, loader, warm-up, describe, preload, host floor (offline).

Every kernel here is a fake module object; `kernels`, `torch` and
`huggingface_hub` are never imported. The live counterpart is
`tests/spaces/integration/test_hubkernel_live.py`.
"""

from __future__ import annotations

import json
import sys
import threading
import types
from pathlib import Path

import pytest
from _rules import _assert_clean_copy
from algenta_spaces import hubkernel as hk

STATS_SHA = "ac35ffe20385f0eb7d2a1d2f1f935dc3a287c886"
TEXT_SHA = "fb2cab4558c5ace333d832d0a0c4b807ba0357f1"
VARIANT = "torch29-cxx11-cpu-x86_64-linux"


def _path(repo: str, sha: str, variant: str = VARIANT) -> str:
    return f"/data/hub/kernels--thyn-ai--{repo}/snapshots/{sha}/build/{variant}/__init__.py"


class FakeKernelError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details or {}


def _param(name: str, type_: str, has_default: bool = False) -> dict:
    return {"name": name, "type": type_, "has_default": has_default, "is_mut": False, "doc": ""}


STATS_CONTRACT = {
    "modules": {
        "ab_testing": {
            "name": "ab_testing",
            "description": "A/B testing",
            "structs": {},
            "functions": {
                "z_test_proportions": {
                    "name": "z_test_proportions",
                    "params": [
                        _param("successes_a", "Int"),
                        _param("n_a", "Int"),
                        _param("successes_b", "Int"),
                        _param("n_b", "Int"),
                    ],
                    "return_type": "List[Float64]",
                    "returns_doc": "[z_statistic, p_value].",
                    "doc": "Two-proportion z-test.",
                    "count_relations": [],
                },
            },
        },
        "matrix_decomp": {
            "name": "matrix_decomp",
            "description": "matrix decompositions",
            "status_decoder": "decode_status",
            "structs": {},
            "functions": {
                "trace": {"name": "trace", "params": [_param("m", "List[Float64]")]},
                "det": {
                    "name": "det",
                    "params": [_param("m", "List[Float64]"), _param("n", "Int", True)],
                    "return_type": "Float64",
                    "count_relations": [{"bounds": ["m"], "factors": ["n", "n"]}],
                },
            },
        },
        "env": {"name": "env", "functions": {"home": {"name": "home", "params": []}}},
    },
    "status_names": {},
}

TEXT_CONTRACT = {
    "modules": {
        "text.fuzzy": {
            "name": "text.fuzzy",
            "description": "fuzzy matching",
            "functions": {
                "levenshtein_distance": {
                    "name": "levenshtein_distance",
                    "params": [_param("a", "String"), _param("b", "String")],
                    "return_type": "Int",
                    "count_relations": [],
                },
                "secret_fn": {"name": "secret_fn", "params": []},
            },
        }
    }
}


def fake_kernel(repo: str, sha: str, contract: dict, *, excluded=(), variant: str = VARIANT):
    mod = types.ModuleType(f"_fake_{repo.replace('-', '_')}")
    mod.__file__ = _path(repo, sha, variant)
    mod.CONTRACT = contract
    mod.excluded_functions = list(excluded)
    mod.calls = []
    mod.KernelError = FakeKernelError

    def execute(module: str, function: str, args):
        mod.calls.append((module, function, args))
        if function == "z_test_proportions":
            if len(args) != 4:
                raise FakeKernelError(
                    "invalid_arguments",
                    f"z_test_proportions takes 4 to 4 arguments, {len(args)} given",
                )
            return [-1.440793230951582, 0.1496431923825119]
        if function == "levenshtein_distance":
            return abs(len(args[0]) - len(args[1]))
        if function == "det":
            raise ZeroDivisionError("singular")
        return {"module": module, "function": function}

    mod.execute = execute
    return mod


class FakeGetKernel:
    """Stands in for `kernels.get_kernel`: records kwargs, returns the fake per repo id."""

    def __init__(self, **kernels: types.ModuleType):
        self.kernels = {f"thyn-ai/{name.replace('_', '-')}": mod for name, mod in kernels.items()}
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, repo_id: str, **kwargs):
        self.calls.append((repo_id, kwargs))
        return self.kernels[repo_id]


class Clock:
    def __init__(self) -> None:
        self.now = 10.0

    def __call__(self) -> float:
        self.now += 0.25
        return self.now


@pytest.fixture
def stats():
    return fake_kernel("algenta-stats", STATS_SHA, STATS_CONTRACT)


@pytest.fixture
def text():
    return fake_kernel("algenta-text", TEXT_SHA, TEXT_CONTRACT, excluded=["text.fuzzy.secret_fn"])


@pytest.fixture
def loaded_stats(stats):
    return hk.load("stats", get_kernel=FakeGetKernel(algenta_stats=stats), clock=Clock())


# --- TRUST and the two repository files ---------------------------------------------------


def test_trust_is_the_twenty_capped_repos_and_matches_the_manifest(repo_root: Path):
    assert len(hk.TRUST) == 20
    assert hk.TRUST == tuple(sorted(hk.TRUST))
    assert all(repo.startswith("thyn-ai/algenta") for repo in hk.TRUST)
    assert "thyn-ai/algenta" in hk.TRUST and "thyn-ai/algenta-stats" in hk.TRUST
    manifest = json.loads((repo_root / hk.CAPABILITIES_REL).read_text())
    assert dict(manifest["publication_state"]["capped_v1_shas"]) == hk.FROZEN_CAPPED_V1_SHAS
    assert manifest["excluded_functions"] == hk.FROZEN_EXCLUDED_FUNCTIONS
    assert hk.CAPABILITIES.source.endswith("capabilities.json")
    assert hk.CAPABILITIES.capped_v1_shas == hk.FROZEN_CAPPED_V1_SHAS


def test_load_capabilities_from_a_file_and_the_frozen_fallback(tmp_path: Path):
    good = tmp_path / "capabilities.json"
    good.write_text(
        json.dumps(
            {
                "publication_state": {"capped_v1_shas": {"thyn-ai/algenta-x": "a" * 40}},
                "excluded_functions": {"m.f": "why"},
            }
        )
    )
    caps = hk.load_capabilities(good)
    assert caps.trust == ("thyn-ai/algenta-x",)
    assert caps.excluded_functions == {"m.f": "why"} and caps.source == str(good)

    frozen = hk.load_capabilities(tmp_path / "missing.json")
    assert frozen.source == hk.FROZEN_SOURCE
    assert frozen.capped_v1_shas == hk.FROZEN_CAPPED_V1_SHAS
    assert frozen.excluded_functions == hk.FROZEN_EXCLUDED_FUNCTIONS

    for bad in ("not json", "[]", '{"publication_state": {}}'):
        good.write_text(bad)
        with pytest.raises(hk.HubKernelError) as info:
            hk.load_capabilities(good)
        assert info.value.code == "capabilities_invalid"
    good.write_text(
        json.dumps({"publication_state": {"capped_v1_shas": {"other-org/x": "a" * 40}}})
    )
    with pytest.raises(hk.HubKernelError, match="not a thyn-ai repo id"):
        hk.load_capabilities(good)
    good.write_text(
        json.dumps({"publication_state": {"capped_v1_shas": {"thyn-ai/x": "not-a-sha"}}})
    )
    with pytest.raises(hk.HubKernelError, match="not a sha"):
        hk.load_capabilities(good)


def test_locate_repo_file_env_then_vendored_then_walk_up(tmp_path: Path, monkeypatch):
    target = tmp_path / "docs" / "x" / "thing.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}")
    assert hk.locate_repo_file("docs/x/thing.json", start=tmp_path / "a" / "b") == target
    assert hk.locate_repo_file("docs/x/nothing.json", start=tmp_path) is None
    assert hk.locate_repo_file("docs/x/thing.json", env_key="K", env={"K": str(target)}) == target
    assert hk.locate_repo_file("docs/x/thing.json", env_key="K", env={"K": "/nope"}) is None
    monkeypatch.setattr(hk, "package_root", lambda: target.parent)
    assert hk.locate_repo_file("elsewhere/thing.json") == target


def test_card_examples_match_the_repo_json_and_cover_every_family(repo_root: Path):
    source = json.loads((repo_root / hk.DESCRIPTIONS_REL).read_text())["card_examples"]
    assert {k: tuple(v[:2]) + (v[2],) for k, v in source.items()} == hk.FROZEN_CARD_EXAMPLES
    for repo in hk.TRUST:
        example = hk.card_example(repo)
        assert isinstance(example, hk.CardExample) and example.module and example.function
    assert hk.card_example("stats").as_call() == "ab_testing.z_test_proportions(50, 1000, 65, 1000)"
    assert hk.card_example("thyn-ai/algenta-text").args == ["kitten", "sitting"]
    with pytest.raises(hk.HubKernelError) as info:
        hk.card_example("stats", examples={})
    assert info.value.code == "no_card_example"


def test_parse_example_accepts_literals_only():
    ex = hk.parse_example("ab_testing.z_test_proportions(50, 1000, 65, 1000)")
    assert ex == hk.CardExample("ab_testing", "z_test_proportions", [50, 1000, 65, 1000])
    nested = hk.parse_example(" text.fuzzy.levenshtein_distance('kitten', \"sitting\") ")
    assert nested.module == "text.fuzzy" and nested.args == ["kitten", "sitting"]
    kw = hk.parse_example("linalg.vec_cross(a=[1, 0, 0], b=[0, 1, 0])")
    assert kw.args == {"a": [1, 0, 0], "b": [0, 1, 0]}
    assert kw.as_call() == "linalg.vec_cross(a=[1, 0, 0], b=[0, 1, 0])"
    assert hk.parse_example("finance.cagr(-1.5, 2e3, True, None)").args == [
        -1.5,
        2000.0,
        True,
        None,
    ]
    for bad in (
        "__import__('os').system('id')",
        "ab_testing.z_test_proportions(__import__('os'))",
        "ab_testing.z_test_proportions(1 + 1)",
        "ab_testing.z_test_proportions(x)",
        "z_test_proportions(1)",
        "ab_testing.z_test_proportions",
        "ab_testing.z_test_proportions(1, b=2)",
        "ab_testing.z_test_proportions(**{'a': 1})",
        "def f(): pass",
        "",
    ):
        with pytest.raises(hk.HubKernelError) as info:
            hk.parse_example(bad)
        assert info.value.code == "bad_card_example", bad


def test_load_card_examples_from_a_file_with_both_entry_shapes(tmp_path: Path):
    path = tmp_path / "module_descriptions.json"
    path.write_text(
        json.dumps(
            {
                "card_examples": {
                    "algenta-stats": "stats.mean([1, 2, 3])",
                    "algenta-text": ["text.fuzzy", "hamming_distance", ["ab", "ac"]],
                }
            }
        )
    )
    table = hk.load_card_examples(path)
    assert table["algenta-stats"] == hk.CardExample("stats", "mean", [[1, 2, 3]])
    assert table["algenta-text"] == hk.CardExample("text.fuzzy", "hamming_distance", ["ab", "ac"])
    assert table["algenta-finance"].function == "cagr"  # frozen entries stay
    assert hk.load_card_examples(tmp_path / "missing.json")["algenta-stats"].function == (
        "z_test_proportions"
    )
    path.write_text(json.dumps({"card_examples": {"algenta-stats": ["only", "two"]}}))
    with pytest.raises(hk.HubKernelError) as info:
        hk.load_card_examples(path)
    assert info.value.code == "bad_card_example"
    path.write_text(json.dumps({"nope": 1}))
    with pytest.raises(hk.HubKernelError) as info:
        hk.load_card_examples(path)
    assert info.value.code == "descriptions_invalid"


# --- names ------------------------------------------------------------------------------------


def test_family_names_and_repo_ids():
    assert hk.short_family("stats") == "algenta-stats"
    assert hk.short_family("algenta-stats") == "algenta-stats"
    assert hk.short_family("thyn-ai/algenta-stats") == "algenta-stats"
    assert hk.short_family("algenta") == "algenta"
    assert hk.repo_id_of("general-a") == "thyn-ai/algenta-general-a"
    assert hk.repo_id_of("algenta") == "thyn-ai/algenta"
    for bad in ("other/algenta-stats", "", "nope", "thyn-ai/algenta-unknown"):
        with pytest.raises(hk.HubKernelUnavailable) as info:
            hk.repo_id_of(bad)
        assert info.value.code == "unknown_family"
    assert hk.repo_id_of("x", trust=["thyn-ai/algenta-x"]) == "thyn-ai/algenta-x"


# --- load ---------------------------------------------------------------------------------------


def test_load_passes_trust_and_reads_variant_and_shas(stats):
    fetch = FakeGetKernel(algenta_stats=stats)
    clock = Clock()
    loaded = hk.load("stats", get_kernel=fetch, clock=clock)
    assert fetch.calls == [
        (
            "thyn-ai/algenta-stats",
            {"version": 1, "backend": "cpu", "trust_remote_code": list(hk.TRUST)},
        )
    ]
    assert loaded.family == "algenta-stats" and loaded.repo_id == "thyn-ai/algenta-stats"
    assert loaded.kernel is stats
    assert loaded.variant == VARIANT
    assert loaded.capped_v1_sha == STATS_SHA and loaded.snapshot_sha == STATS_SHA
    assert loaded.pinned is True and loaded.short_sha == "ac35ffe"
    assert loaded.label() == "algenta-stats@ac35ffe"
    assert loaded.load_s == pytest.approx(0.25)
    assert loaded.warm is False and loaded.warmup_ms is None and loaded.is_umbrella is False

    other = hk.load(
        "thyn-ai/algenta-text",
        backend="metal",
        version=2,
        trust=["thyn-ai/algenta-text"],
        get_kernel=FakeGetKernel(algenta_text=fake_kernel("algenta-text", "0" * 40, TEXT_CONTRACT)),
    )
    assert other.backend == "metal" and other.version == 2
    assert other.pinned is False  # the cache holds another revision than the capped one
    assert other.capped_v1_sha == TEXT_SHA and other.snapshot_sha == "0" * 40


def test_load_maps_every_failure_to_a_code(stats):
    def raising(exc):
        def fetch(repo_id, **kwargs):
            raise exc

        return fetch

    cases = [
        (FakeKernelError("platform_unsupported", "needs macOS 15"), "platform_unsupported"),
        (
            FakeKernelError("native_unavailable", "libx.so could not be loaded"),
            "native_unavailable",
        ),
        (ModuleNotFoundError("No module named 'torch'", name="torch"), "torch_not_installed"),
        (
            ImportError("No module named 'kernels._rust'", name="kernels._rust"),
            "kernels_not_installed",
        ),
        (
            FileNotFoundError("Cannot find a build variant for this system in x"),
            "variant_unavailable",
        ),
        (FileNotFoundError("Cannot find a local snapshot for x (offline)"), "cache_missing"),
        (ConnectionError("Hub timed out"), "hub_unreachable"),
        (ValueError("trust_remote_code must include thyn-ai/algenta-stats"), "trust_required"),
        (ValueError("Cyclic kernel dependency detected"), "load_failed"),
        (RuntimeError("boom"), "load_failed"),
    ]
    for exc, code in cases:
        with pytest.raises(hk.HubKernelUnavailable) as info:
            hk.load("stats", get_kernel=raising(exc))
        assert info.value.code == code, (exc, info.value)
        assert "thyn-ai/algenta-stats" in str(info.value)
        assert info.value.__cause__ is exc

    with pytest.raises(hk.HubKernelUnavailable) as info:
        hk.load("stats", get_kernel=lambda *a, **k: types.ModuleType("nofile"))
    assert info.value.code == "variant_unknown"


def test_load_without_kernels_installed_is_kernels_not_installed(monkeypatch, stats):
    monkeypatch.setitem(sys.modules, "kernels", None)  # import raises ImportError
    with pytest.raises(hk.HubKernelUnavailable) as info:
        hk.load("stats")
    assert info.value.code == "kernels_not_installed"
    assert "pip install kernels torch" in info.value.message


def test_variant_and_snapshot_helpers():
    mod = types.ModuleType("m")
    mod.__file__ = _path("algenta-llm", "b" * 40, "torch29-cxx11-cu128-x86_64-linux")
    assert hk.variant_of(mod) == "torch29-cxx11-cu128-x86_64-linux"
    assert hk.snapshot_sha_of(mod) == "b" * 40
    mod.__file__ = "/site-packages/local_build/__init__.py"
    with pytest.raises(hk.HubKernelUnavailable):
        hk.variant_of(mod)
    assert hk.snapshot_sha_of(mod) == ""
    mod.__file__ = "/x/build/"
    with pytest.raises(hk.HubKernelUnavailable):
        hk.variant_of(mod)


# --- calls, warm-up, describe ---------------------------------------------------------------------


def test_execute_times_the_call_and_maps_kernel_errors(loaded_stats, stats):
    clock = Clock()
    call = hk.execute(
        loaded_stats, "ab_testing", "z_test_proportions", [50, 1000, 65, 1000], clock=clock
    )
    assert call.result == [-1.440793230951582, 0.1496431923825119]
    assert call.elapsed_ms == pytest.approx(250.0)
    assert call.as_call() == "ab_testing.z_test_proportions(50, 1000, 65, 1000)"
    assert stats.calls[-1] == ("ab_testing", "z_test_proportions", [50, 1000, 65, 1000])

    with pytest.raises(hk.HubKernelCallError) as info:
        hk.execute(loaded_stats, "ab_testing", "z_test_proportions", [1])
    assert info.value.code == "invalid_arguments" and "4 to 4" in info.value.message
    with pytest.raises(hk.HubKernelCallError) as info:
        hk.execute(loaded_stats, "matrix_decomp", "det", [[1.0]])
    assert info.value.code == "call_failed" and "ZeroDivisionError" in info.value.message
    with pytest.raises(hk.HubKernelCallError) as info:
        hk.execute(loaded_stats, "nope", "f", [])
    assert info.value.code == "unknown_module"
    with pytest.raises(hk.HubKernelCallError) as info:
        hk.execute(loaded_stats, "ab_testing", "nope", [])
    assert info.value.code == "unknown_function"
    # excluded by the manifest (module.function and module.*) — refused before the kernel sees it
    for module, function in (("matrix_decomp", "trace"), ("env", "home")):
        with pytest.raises(hk.HubKernelCallError) as info:
            hk.execute(loaded_stats, module, function, [])
        assert info.value.code == "excluded_function"
    assert not any(c[0] in ("nope", "env") or c[1] == "trace" for c in stats.calls)


def test_function_spec_is_a_copy(loaded_stats):
    spec = hk.function_spec(loaded_stats, "ab_testing", "z_test_proportions")
    assert [p["name"] for p in spec["params"]] == ["successes_a", "n_a", "successes_b", "n_b"]
    spec["params"].clear()
    assert len(hk.function_spec(loaded_stats, "ab_testing", "z_test_proportions")["params"]) == 4


def test_warm_up_runs_the_card_example_and_records_it(loaded_stats, stats):
    clock = Clock()
    call = hk.warm_up(loaded_stats, clock=clock)
    assert call.module == "ab_testing" and call.function == "z_test_proportions"
    assert stats.calls == [("ab_testing", "z_test_proportions", [50, 1000, 65, 1000])]
    assert loaded_stats.warm is True
    assert loaded_stats.warmup_ms == pytest.approx(250.0)
    assert loaded_stats.warmup_call == hk.card_example("stats")
    assert loaded_stats.warmup_result == call.result
    custom = hk.CardExample("ab_testing", "z_test_proportions", [1, 2, 3, 4])
    hk.warm_up(loaded_stats, example=custom)
    assert stats.calls[-1][2] == [1, 2, 3, 4] and loaded_stats.warmup_call is custom


def test_describe_returns_plain_json_with_excluded_functions_removed(loaded_stats, text):
    view = hk.describe(loaded_stats)
    json.dumps(view)
    assert view["family"] == "algenta-stats" and view["variant"] == VARIANT
    assert view["capped_v1_sha"] == STATS_SHA and view["backend"] == "cpu"
    assert list(view["modules"]) == ["ab_testing", "env", "matrix_decomp"]
    ab = view["modules"]["ab_testing"]
    assert ab["family"] == "algenta-stats" and ab["description"] == "A/B testing"
    fn = ab["functions"]["z_test_proportions"]
    assert [(p["name"], p["type"], p["has_default"]) for p in fn["params"]] == [
        ("successes_a", "Int", False),
        ("n_a", "Int", False),
        ("successes_b", "Int", False),
        ("n_b", "Int", False),
    ]
    assert fn["return_type"] == "List[Float64]" and fn["returns_doc"] == "[z_statistic, p_value]."
    md = view["modules"]["matrix_decomp"]
    assert list(md["functions"]) == ["det"]  # trace is excluded by the manifest
    assert md["status_decoder"] == "decode_status"
    assert md["functions"]["det"]["count_relations"] == [{"bounds": ["m"], "factors": ["n", "n"]}]
    assert md["functions"]["det"]["params"][1]["has_default"] is True
    assert view["modules"]["env"]["functions"] == {}  # env.* excluded
    assert view["excluded"] == ["env.home", "matrix_decomp.trace"]
    assert view["function_count"] == 2
    # a kernel's own excluded_functions list is honoured too
    loaded_text = hk.load("text", get_kernel=FakeGetKernel(algenta_text=text))
    text_view = hk.describe(loaded_text)
    assert list(text_view["modules"]["text.fuzzy"]["functions"]) == ["levenshtein_distance"]
    assert text_view["excluded"] == ["text.fuzzy.secret_fn"]
    # describe never mutates the contract
    view["modules"]["ab_testing"]["functions"]["z_test_proportions"]["params"].clear()
    assert (
        len(STATS_CONTRACT["modules"]["ab_testing"]["functions"]["z_test_proportions"]["params"])
        == 4
    )


def test_umbrella_routes_to_its_member_families(stats, text):
    umbrella = types.ModuleType("_fake_algenta")
    umbrella.__file__ = _path(
        "algenta", hk.FROZEN_CAPPED_V1_SHAS["thyn-ai/algenta"], "torch-universal"
    )
    umbrella.families = {"stats": "thyn-ai/algenta-stats", "text": "thyn-ai/algenta-text"}
    umbrella.stats = stats
    umbrella.text = text
    loaded = hk.load("algenta", get_kernel=FakeGetKernel(algenta=umbrella))
    assert loaded.is_umbrella and loaded.variant == "torch-universal"
    assert list(hk.family_modules(loaded)) == ["algenta-stats", "algenta-text"]
    assert hk.owner_of(loaded, "text.fuzzy") == ("algenta-text", text)
    view = hk.describe(loaded)
    assert view["modules"]["text.fuzzy"]["family"] == "algenta-text"
    assert view["modules"]["ab_testing"]["family"] == "algenta-stats"
    assert view["excluded"] == ["env.home", "matrix_decomp.trace", "text.fuzzy.secret_fn"]
    call = hk.warm_up(loaded)  # the umbrella example is the stats hero call
    assert call.function == "z_test_proportions" and stats.calls[-1][1] == "z_test_proportions"
    assert hk.execute(loaded, "text.fuzzy", "levenshtein_distance", ["ab", "abcd"]).result == 2

    bare = types.ModuleType("bare")
    bare.__file__ = _path("algenta", "c" * 40, "torch-universal")
    with pytest.raises(hk.HubKernelUnavailable) as info:
        hk.family_modules(hk.load("algenta", get_kernel=FakeGetKernel(algenta=bare)))
    assert info.value.code == "no_contract"
    umbrella.text = types.ModuleType("nocontract")
    with pytest.raises(hk.HubKernelUnavailable) as info:
        hk.family_modules(loaded)
    assert info.value.code == "no_contract"


# --- preload -----------------------------------------------------------------------------------


def test_preload_before_launch_collects_errors_and_reports_progress(stats, text):
    def fetch(repo_id, **kwargs):
        if repo_id.endswith("stats"):
            return stats
        if repo_id.endswith("text"):
            return text
        raise FileNotFoundError("Cannot find a build variant for this system")

    events: list[tuple[str, str, str]] = []
    outcome = hk.preload(
        ["stats", "thyn-ai/algenta-text", "vision"],
        get_kernel=fetch,
        progress=lambda *e: events.append(e),
        clock=Clock(),
    )
    assert outcome.done.is_set() and outcome.wait(0) is True
    assert list(outcome.loaded) == ["algenta-stats", "algenta-text"]
    assert outcome.loaded["algenta-stats"].warm and outcome.loaded["algenta-text"].warm
    assert text.calls == [("text.fuzzy", "levenshtein_distance", ["kitten", "sitting"])]
    assert list(outcome.errors) == ["algenta-vision"]
    assert outcome.errors["algenta-vision"].code == "variant_unavailable"
    assert outcome.ok is False
    assert outcome.summary().startswith("2 of 3 families loaded in ")
    assert outcome.summary().endswith("; algenta-vision: variant_unavailable")
    assert [(f, e) for f, e, _ in events] == [
        ("algenta-stats", "loading"),
        ("algenta-stats", "loaded"),
        ("algenta-stats", "warm"),
        ("algenta-text", "loading"),
        ("algenta-text", "loaded"),
        ("algenta-text", "warm"),
        ("algenta-vision", "loading"),
        ("algenta-vision", "error"),
    ]
    assert events[2][2].startswith("ab_testing.z_test_proportions(50, 1000, 65, 1000) in ")
    assert events[-1][2].startswith("variant_unavailable: ")
    with pytest.raises(ValueError):
        hk.preload(["stats", "algenta-stats"], get_kernel=fetch)


def test_preload_in_the_background_and_without_warm_up(stats):
    release = threading.Event()

    def fetch(repo_id, **kwargs):
        assert release.wait(5.0)
        return stats

    outcome = hk.preload(["stats"], before_launch=False, warm=False, get_kernel=fetch)
    assert outcome.done.is_set() is False and outcome.wait(0.05) is False
    release.set()
    assert outcome.wait(5.0) is True
    assert outcome.ok is True and stats.calls == []
    assert outcome.loaded["algenta-stats"].warm is False
    assert outcome.summary().startswith("1 family loaded in ")
    hk.warm_up(outcome.loaded["algenta-stats"])
    assert outcome.summary().startswith("1 family warm in ")


# --- host floor and footer -------------------------------------------------------------------


def test_host_floor_ok_rules(tmp_path: Path):
    ok, reason = hk.host_floor_ok(system="Darwin", machine="arm64")
    assert ok and reason.startswith("macOS arm64")
    ok, reason = hk.host_floor_ok(system="Windows", machine="AMD64")
    assert not ok and "not a published platform" in reason

    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("processor\t: 0\nflags\t\t: fpu vme sse4_2 avx avx2 bmi2 fma\n")
    assert hk.host_floor_ok(
        system="Linux", machine="x86_64", cpuinfo=cpuinfo, libc_version="2.39"
    ) == (True, "Linux x86_64: avx2 present, glibc 2.39")
    ok, reason = hk.host_floor_ok(
        system="Linux", machine="x86_64", cpuinfo=cpuinfo, libc_version="glibc 2.31-0ubuntu9"
    )
    assert not ok and reason == "Linux x86_64: glibc 2.31 is below 2.35"
    cpuinfo.write_text("flags\t\t: fpu sse4_2 avx\n")
    ok, reason = hk.host_floor_ok(
        system="Linux", machine="x86_64", cpuinfo=cpuinfo, libc_version=(2, 35)
    )
    assert not ok and reason == "Linux x86_64: cpu lacks avx2 (x86-64-v3 floor)"
    ok, reason = hk.host_floor_ok(
        system="Linux", machine="x86_64", cpuinfo=tmp_path / "none", libc_version="2.20"
    )
    assert not ok and reason == "Linux x86_64: cpu flags unreadable; glibc 2.20 is below 2.35"
    ok, reason = hk.host_floor_ok(
        system="Linux", machine="aarch64", cpuinfo=tmp_path / "none", libc_version="2.35"
    )
    assert ok and reason == "Linux aarch64: aarch64: no instruction-set floor, glibc 2.35"
    ok, reason = hk.host_floor_ok(system="Linux", machine="aarch64", libc_version="musl")
    assert not ok and reason == "Linux aarch64: glibc version unreadable"
    ok, reason = hk.host_floor_ok(system="Linux", machine="riscv64", libc_version="2.39")
    assert not ok and "not a published architecture" in reason
    # the real host answers something, with a reason, and never raises
    ok, reason = hk.host_floor_ok()
    assert isinstance(ok, bool) and reason


def test_cpu_flags_parse_and_version_helpers(tmp_path: Path):
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("processor: 0\nFeatures\t: fp asimd\nprocessor: 1\n")
    assert hk.cpu_flags(cpuinfo) == frozenset({"fp", "asimd"})
    cpuinfo.write_text("processor: 0\n")
    assert hk.cpu_flags(cpuinfo) == frozenset()
    assert hk.cpu_flags(tmp_path / "missing") == frozenset()
    assert hk.parse_version("2.39 (Ubuntu GLIBC 2.39-0ubuntu8)") == (2, 39)
    assert hk.parse_version("glibc 2.35") == (2, 35)
    assert hk.parse_version("") is None and hk.parse_version("musl") is None
    version = hk.glibc_version()
    assert version is None or (isinstance(version, tuple) and len(version) == 2)


def test_platform_note_lists_variants_pins_and_the_one_worker_rule(loaded_stats, text):
    note = hk.platform_note(loaded_stats, dists=["pytest", "no-such-dist-xyz"])
    assert note.startswith(f"Hub kernels · {VARIANT} · algenta-stats@ac35ffe · pytest ")
    assert "no-such-dist-xyz not installed" in note
    assert note.endswith(" · one native call at a time")
    _assert_clean_copy(note)
    loaded_text = hk.load("text", get_kernel=FakeGetKernel(algenta_text=text))
    both = hk.platform_note([loaded_stats, loaded_text], dists=[])
    assert "algenta-stats@ac35ffe, algenta-text@fb2cab4" in both
    bare = hk.platform_note(dists=[])
    assert bare.startswith("Hub kernels · ") and VARIANT not in bare
    assert "kernels" in hk.platform_note() and "torch" in hk.platform_note()
    _assert_clean_copy(hk.TRANSPORT_NOTE)


def test_error_hierarchy_carries_codes():
    err = hk.HubKernelCallError("invalid_arguments", "takes 4", details={"received": 1})
    assert isinstance(err, hk.HubKernelError) and str(err) == "invalid_arguments: takes 4"
    assert err.code == "invalid_arguments" and err.details == {"received": 1}
    assert issubclass(hk.HubKernelUnavailable, hk.HubKernelError)
    with pytest.raises(ValueError):
        hk.HubKernelError(" ", "no code")
