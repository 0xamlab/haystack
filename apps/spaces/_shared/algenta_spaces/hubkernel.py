"""Hub kernels inside a Space — the `get_kernel` loader, warm-up, host floor and contract view.

A Space loads the compiled Algenta families straight from the Kernels Hub::

    from kernels import get_kernel
    k = get_kernel("thyn-ai/algenta-stats", version=1, backend="cpu", trust_remote_code=TRUST)

`TRUST` must name every repository in the dependency tree (HF-TRUST-002): the
umbrella `thyn-ai/algenta` pins nineteen families by revision, so the list is
the twenty capped v1 repositories from `docs/hf-kernels/release/capabilities.json`
(`publication_state.capped_v1_shas`). The file is read at import when it can be
found (an environment variable, a copy next to the package, or the repository
checkout); otherwise the frozen copy below is used — a test asserts the two agree.

What this module gives a Space, all stdlib at import (`kernels`, `torch` and
`huggingface_hub` are imported inside `load`):

* `load(family)` → `LoadedKernel`: the kernel module, its build variant read from
  `kernel.__file__` (`torch29-cxx11-cpu-x86_64-linux`, `torch25-cpu-aarch64-darwin`,
  `torch-universal` for the umbrella), the capped sha the footer prints, the
  snapshot sha the cache actually holds, and the load time.
* `warm_up(loaded)`: one contract-valid call per family — the family's card
  example from `scripts/hf_kernels/module_descriptions.json["card_examples"]`,
  parsed with `ast.literal_eval` (never `eval`) — timed, so the boot card can show
  "algenta-stats warm in 1.4 s" and the first visitor never pays the cold start.
* `preload(families)`: every family for boot, before `launch()`, or on a thread.
* `host_floor_ok()`: the published CPU floor — x86-64-v3 (`avx2` in
  `/proc/cpuinfo`) and glibc 2.35 on Linux; both bypassed with a reason on macOS,
  where the kernel loader checks the macOS 15 floor itself.
* `describe(loaded)`: `kernel.CONTRACT` as plain dicts for the playground form,
  with the excluded functions removed.
* `execute(loaded, module, function, args)`: one timed call through
  `kernel.execute`, errors mapped to `HubKernelCallError` with the kernel's code.

ABI §9 applies to everything here: the compiled library holds one device-wide
worker slot (blocking `flock` on `/dev/null`), so a second native call from any
thread or process waits for the first. Route native calls through `lane.Lane`
and never time a call from two threads at once.

Errors are one small hierarchy: `HubKernelError` carries a stable `.code` the
runbook indexes (`kernels_not_installed`, `variant_unavailable`, `cache_missing`,
`hub_unreachable`, `native_unavailable`, `unknown_family`, `no_card_example`,
`bad_card_example`, …); `HubKernelUnavailable` is a load or platform failure,
`HubKernelCallError` a refused or failed call. Nothing here catches without
re-raising a typed error, and nothing evaluates text from a file as code.
"""

from __future__ import annotations

import ast
import copy
import ctypes
import json
import logging
import os
import platform
import re
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from .runtime import is_sha, pinned_versions
from .shell import check_copy

log = logging.getLogger(__name__)

ORG = "thyn-ai"
UMBRELLA_FAMILY = "algenta"
DEFAULT_BACKEND = "cpu"
DEFAULT_VERSION = 1

CAPABILITIES_ENV = "ALGENTA_CAPABILITIES_JSON"
DESCRIPTIONS_ENV = "ALGENTA_MODULE_DESCRIPTIONS_JSON"
CAPABILITIES_REL = Path("docs/hf-kernels/release/capabilities.json")
DESCRIPTIONS_REL = Path("scripts/hf_kernels/module_descriptions.json")
FROZEN_SOURCE = "frozen"

TRANSPORT_NOTE = "includes JSON marshalling across the C ABI"
ONE_WORKER_NOTE = "one native call at a time"
GLIBC_FLOOR = (2, 35)
X86_64_V3_FLAG = "avx2"
PINNED_DISTS = ("kernels", "torch", "huggingface_hub")

_BUILD_MARKER = "/build/"
_SNAPSHOT_RE = re.compile(r"/snapshots/([0-9a-f]{7,64})/")
_VERSION_RE = re.compile(r"(\d+)\.(\d+)")

# --- frozen fallbacks: identical to the JSON sources at the time of writing (tested) ---------

FROZEN_CAPPED_V1_SHAS: dict[str, str] = {
    "thyn-ai/algenta": "b7baf6c620a6ec42d851d50d310e8bd10805f206",
    "thyn-ai/algenta-bits-time": "199dff6cf340d61d1d10da026e27288fc0b88dff",
    "thyn-ai/algenta-crypto": "944dadd434e2d92f357454e560000f541be7d86c",
    "thyn-ai/algenta-finance": "a646c590c67ff78a29f51b768dd58d32f475a139",
    "thyn-ai/algenta-general-a": "34fa002a1a2374c8cce73a70423b5d36fe4793ce",
    "thyn-ai/algenta-general-b": "a2ffcc4eb1c7b6db5f087f74e75c77e9d09dfc2b",
    "thyn-ai/algenta-general-c": "8c2dd0491f8b3faae59e7e8215144665a59d0fc0",
    "thyn-ai/algenta-general-d": "d2eb31c5032da4b3779fdac9439d78fcc376d42e",
    "thyn-ai/algenta-general-e": "022f029f19f7e213b0293da11751a2c471f3277d",
    "thyn-ai/algenta-geometry": "54b91d902d9a38a244c8a5f093aa7bfd2824d6dd",
    "thyn-ai/algenta-graph": "7247b466a11e49d2d2eeef2beb488732938e20e6",
    "thyn-ai/algenta-llm": "516a8ad9b3fc161dec270f942c2c8dc8f0f9e59d",
    "thyn-ai/algenta-ml": "c67aed624ae1e22398e79780d5bfc8bb66237c0c",
    "thyn-ai/algenta-networking": "11ada7623e74dbbeb3a4f004648d58fe40cd1d9b",
    "thyn-ai/algenta-serialization": "12109d34d242a4fb702d8b78419a9aff195dc91d",
    "thyn-ai/algenta-signal": "a770d6fe3be1bbf6f08accc70902490a85cbf00f",
    "thyn-ai/algenta-stats": "ac35ffe20385f0eb7d2a1d2f1f935dc3a287c886",
    "thyn-ai/algenta-tensors": "e1a96bbad9bedcd71afce08a4c648ffec55576e6",
    "thyn-ai/algenta-text": "fb2cab4558c5ace333d832d0a0c4b807ba0357f1",
    "thyn-ai/algenta-vision": "ebad076f3be6255d77fee9f279c2af5728ea973e",
}

_SQUARE = (
    "reads its matrix argument as square; a non-square nested list is not expressible as a "
    "length rule"
)
_INTEROP = "needs the host interpreter (Python interop) — SIGSEGV in-process"
_SIMPLEX = "requires a consistent distance/simplex structure; not expressible as a length rule"

FROZEN_EXCLUDED_FUNCTIONS: dict[str, str] = {
    "column_rank.run_column_rank": (
        "takes a full JSON request string; reached through the column-ranking session, "
        "not a plain in-process call"
    ),
    "combinatorial.tsp_greedy": (
        "reads its distance argument as a square matrix; a non-square nested list is not "
        "expressible as a length rule"
    ),
    "compression.huffman.generate_codes": (
        "allocates from a frequency table whose size it trusts; an ill-formed table is not "
        "expressible as a length rule"
    ),
    "constraint.magic_square_check": (
        "reads its grid argument as square; a non-square nested list is not expressible as a "
        "length rule"
    ),
    "contest_strategy.option_board": (
        "requires its per-entrant arrays to share one length; a mismatch is not expressible as "
        "a length rule"
    ),
    "datetime.now_epoch": _INTEROP,
    "dependency.dependency_depth": (
        "walks an adjacency list that must be acyclic and in range; not expressible as a "
        "length rule"
    ),
    "dimensionality.power_iteration": _SQUARE,
    "env.*": _INTEROP,
    "gbdt.gbdt_predict": (
        "walks a tree encoding that must be well-formed; a malformed tree is not expressible "
        "as a length rule"
    ),
    "matrix_decomp.lu_decompose": _SQUARE,
    "matrix_decomp.trace": (
        "reads the diagonal of a square matrix; a non-square nested list is not expressible as "
        "a length rule"
    ),
    "svm_kernel.is_positive_semidefinite": _SQUARE,
    "svm_kernel.kernel_center": _SQUARE,
    "topology.filtration_values": _SIMPLEX,
    "topology.persistence_diagram_0": _SIMPLEX,
    "topology.vietoris_rips_edges": (
        "requires a square distance matrix; a non-square nested list is not expressible as a "
        "length rule"
    ),
    "trie.*": (
        "the trie functions take a Trie structure that a plain in-process call cannot build; "
        "use the SDK for tries"
    ),
}

FROZEN_CARD_EXAMPLES: dict[str, tuple[str, str, list[Any]]] = {
    "algenta-bits-time": ("number_theory", "prime_factors", [360]),
    "algenta-crypto": ("crypto.crc32", "crc32_hex", ["hello"]),
    "algenta-finance": ("finance", "cagr", [100, 200, 10]),
    "algenta-general-a": ("allocation", "kelly_criterion", [0.6, 2]),
    "algenta-general-b": ("epidemiology", "herd_immunity_threshold", [4]),
    "algenta-general-c": ("operations_research", "eoq_quantity", [1000, 50, 2]),
    "algenta-general-d": ("set_ops", "jaccard_index", [[1, 2, 3, 4], [3, 4, 5, 6]]),
    "algenta-general-e": ("wood_science", "moisture_content", [120, 100]),
    "algenta-geometry": ("geodesy", "haversine_distance", [0, 0, 0, 1]),
    "algenta-graph": ("topology", "euler_characteristic", [4, 6, 4]),
    "algenta-ml": ("gradient_descent", "lr_cosine_schedule", [50, 100, 0.1, 0]),
    "algenta-networking": ("net.url", "url_encode", ["hello world"]),
    "algenta-serialization": ("compression.delta", "delta_encode", [[1, 4, 9, 16, 25]]),
    "algenta-signal": ("audio", "midi_to_frequency", [69]),
    "algenta-tensors": ("linalg", "vec_cross", [[1, 0, 0], [0, 1, 0]]),
    "algenta-text": ("text.fuzzy", "levenshtein_distance", ["kitten", "sitting"]),
    "algenta-vision": (
        "image_morphology",
        "foreground_area_ratio_flat",
        [[0, 255, 255, 0, 255, 0, 0, 255], 4, 2, 128],
    ),
}

# Families whose Hub card carries no example line: the flagship hero call for `algenta-stats`
# (the plan's opening card), the CPU-valid RMSNorm call for `algenta-llm`, and the stats call
# again for the umbrella, which routes it to its `stats` member. All verified against the
# published contracts.
EXTRA_CARD_EXAMPLES: dict[str, tuple[str, str, list[Any]]] = {
    "algenta-stats": ("ab_testing", "z_test_proportions", [50, 1000, 65, 1000]),
    "algenta-llm": ("normk.rmsnorm", "rmsnorm_fwd_flat", [[1, 2, 3, 4], [1, 1], 2, 2, 1e-6]),
    UMBRELLA_FAMILY: ("ab_testing", "z_test_proportions", [50, 1000, 65, 1000]),
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class HubKernelError(Exception):
    """Anything this module refuses or cannot do; `code` is stable and indexed by the runbook."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        if not code.strip():
            raise ValueError("an error needs a code")
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details: dict[str, Any] = dict(details or {})


class HubKernelUnavailableError(HubKernelError):
    """A family could not be loaded here, or the host is below the published floor."""


class HubKernelCallError(HubKernelError):
    """A call the kernel refused (`invalid_arguments`, …) or that failed inside the runtime."""


HubKernelUnavailable = HubKernelUnavailableError


# ---------------------------------------------------------------------------
# Repository files: capabilities.json and module_descriptions.json
# ---------------------------------------------------------------------------


def package_root() -> Path:
    """The directory holding the `algenta_spaces` package (the Space root once vendored)."""
    return Path(__file__).resolve().parent.parent


def locate_repo_file(
    relative: Path | str,
    *,
    env_key: str | None = None,
    env: Mapping[str, str] | None = None,
    start: Path | None = None,
) -> Path | None:
    """Find a repository file: `env_key` path, then next to the package, then walking up.

    Returns None when nothing exists, so callers fall back to their frozen copy.
    """
    env = os.environ if env is None else env
    relative = Path(relative)
    if env_key:
        override = env.get(env_key, "").strip()
        if override:
            candidate = Path(override)
            return candidate if candidate.is_file() else None
    vendored = package_root() / relative.name
    if vendored.is_file():
        return vendored
    here = package_root() if start is None else Path(start)
    for parent in (here, *here.parents):
        candidate = parent / relative
        if candidate.is_file():
            return candidate
    return None


def _read_json(path: Path, code: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise HubKernelError(code, f"{path} cannot be read: {exc}") from exc
    except ValueError as exc:
        raise HubKernelError(code, f"{path} is not valid JSON: {exc}") from exc


@dataclass(frozen=True)
class Capabilities:
    """The slice of the release manifest a Space needs: pinned shas and hidden functions."""

    capped_v1_shas: dict[str, str]
    excluded_functions: dict[str, str]
    source: str

    @property
    def trust(self) -> tuple[str, ...]:
        return tuple(sorted(self.capped_v1_shas))


def load_capabilities(path: Path | str | None = None) -> Capabilities:
    """`capabilities.json` when present (given, env, vendored or checkout), else the frozen copy.

    A file that exists but does not hold the expected shape raises
    `HubKernelError("capabilities_invalid")` — a deploy bug is never papered over.
    """
    target = (
        Path(path)
        if path is not None
        else locate_repo_file(CAPABILITIES_REL, env_key=CAPABILITIES_ENV)
    )
    if target is None or not target.is_file():
        return Capabilities(
            dict(FROZEN_CAPPED_V1_SHAS), dict(FROZEN_EXCLUDED_FUNCTIONS), FROZEN_SOURCE
        )
    data = _read_json(target, "capabilities_invalid")
    state = data.get("publication_state") if isinstance(data, dict) else None
    shas = state.get("capped_v1_shas") if isinstance(state, dict) else None
    excluded = data.get("excluded_functions", {}) if isinstance(data, dict) else None
    if not isinstance(shas, dict) or not shas or not isinstance(excluded, dict):
        raise HubKernelError(
            "capabilities_invalid",
            f"{target} lacks publication_state.capped_v1_shas or excluded_functions",
        )
    for repo_id, sha in shas.items():
        if not isinstance(repo_id, str) or not repo_id.startswith(f"{ORG}/"):
            raise HubKernelError("capabilities_invalid", f"{repo_id!r} is not a {ORG} repo id")
        if not isinstance(sha, str) or not is_sha(sha):
            raise HubKernelError("capabilities_invalid", f"{repo_id}: {sha!r} is not a sha")
    return Capabilities(
        dict(sorted(shas.items())),
        {str(k): str(v) for k, v in sorted(excluded.items())},
        str(target),
    )


@dataclass(frozen=True)
class CardExample:
    """One contract-valid call: `module.function(*args)` or `module.function(**args)`."""

    module: str
    function: str
    args: list[Any] | dict[str, Any]

    def as_call(self) -> str:
        """`ab_testing.z_test_proportions(50, 1000, 65, 1000)` — the reproducible snippet line."""
        if isinstance(self.args, dict):
            inner = ", ".join(f"{k}={v!r}" for k, v in self.args.items())
        else:
            inner = ", ".join(repr(v) for v in self.args)
        return f"{self.module}.{self.function}({inner})"


def _dotted_name(node: ast.expr) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def parse_example(text: str) -> CardExample:
    """Parse `module.function(literal, ...)` without evaluating anything.

    The call target must be a dotted name with at least one dot; every argument
    must be a Python literal (`ast.literal_eval`); positional and keyword
    arguments are not mixed. Anything else is `bad_card_example`.
    """
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise HubKernelError("bad_card_example", f"not a call expression: {text!r}") from exc
    call = tree.body
    if not isinstance(call, ast.Call):
        raise HubKernelError("bad_card_example", f"not a call: {text!r}")
    target = _dotted_name(call.func)
    if target is None or "." not in target:
        raise HubKernelError("bad_card_example", f"call target is not module.function: {text!r}")
    module, function = target.rsplit(".", 1)
    if call.args and call.keywords:
        raise HubKernelError("bad_card_example", f"positional and keyword arguments mix: {text!r}")
    try:
        positional = [ast.literal_eval(node) for node in call.args]
        keywords: dict[str, Any] = {}
        for keyword in call.keywords:
            if keyword.arg is None:
                raise HubKernelError("bad_card_example", f"** unpacking is not a literal: {text!r}")
            keywords[keyword.arg] = ast.literal_eval(keyword.value)
    except ValueError as exc:
        raise HubKernelError("bad_card_example", f"argument is not a literal: {text!r}") from exc
    return CardExample(module, function, keywords if keywords else positional)


def _example_from_entry(family: str, entry: Any) -> CardExample:
    if isinstance(entry, str):
        return parse_example(entry)
    if (
        isinstance(entry, list | tuple)
        and len(entry) == 3
        and isinstance(entry[0], str)
        and isinstance(entry[1], str)
        and isinstance(entry[2], list | dict)
    ):
        return CardExample(entry[0], entry[1], copy.deepcopy(entry[2]))
    raise HubKernelError("bad_card_example", f"{family}: unexpected example shape {entry!r}")


def load_card_examples(path: Path | str | None = None) -> dict[str, CardExample]:
    """Every family's example call, from `module_descriptions.json` or the frozen copy.

    Families the JSON does not cover take `EXTRA_CARD_EXAMPLES`; a JSON entry
    always wins over the frozen one.
    """
    target = (
        Path(path)
        if path is not None
        else locate_repo_file(DESCRIPTIONS_REL, env_key=DESCRIPTIONS_ENV)
    )
    examples: dict[str, CardExample] = {
        family: CardExample(m, f, copy.deepcopy(a))
        for family, (m, f, a) in {**FROZEN_CARD_EXAMPLES, **EXTRA_CARD_EXAMPLES}.items()
    }
    if target is None or not target.is_file():
        return examples
    data = _read_json(target, "descriptions_invalid")
    entries = data.get("card_examples") if isinstance(data, dict) else None
    if not isinstance(entries, dict):
        raise HubKernelError("descriptions_invalid", f"{target} lacks card_examples")
    for family, entry in entries.items():
        examples[short_family(str(family))] = _example_from_entry(str(family), entry)
    return examples


# ---------------------------------------------------------------------------
# Family names
# ---------------------------------------------------------------------------


def short_family(family: str) -> str:
    """`thyn-ai/algenta-stats`, `algenta-stats` and `stats` all name `algenta-stats`."""
    name = family.strip()
    if "/" in name:
        org, _, name = name.partition("/")
        if org != ORG:
            raise HubKernelUnavailable("unknown_family", f"{family!r} is not a {ORG} repository")
    if not name:
        raise HubKernelUnavailable("unknown_family", "empty family name")
    if name == UMBRELLA_FAMILY or name.startswith("algenta-"):
        return name
    return f"algenta-{name}"


def repo_id_of(family: str, *, trust: Iterable[str] | None = None) -> str:
    """The Hub repository id for a family, refusing names outside `trust`."""
    repo_id = f"{ORG}/{short_family(family)}"
    allowed = TRUST if trust is None else tuple(trust)
    if repo_id not in allowed:
        raise HubKernelUnavailable(
            "unknown_family", f"{repo_id} is not one of the published families"
        )
    return repo_id


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


@dataclass
class LoadedKernel:
    """One family (or the umbrella) as loaded here, with everything a footer or card prints."""

    family: str
    repo_id: str
    kernel: ModuleType
    variant: str
    capped_v1_sha: str
    snapshot_sha: str
    backend: str
    version: int
    load_s: float
    warmup_ms: float | None = None
    warmup_call: CardExample | None = None
    warmup_result: Any = None

    @property
    def short_sha(self) -> str:
        return self.capped_v1_sha[:7]

    @property
    def is_umbrella(self) -> bool:
        return self.family == UMBRELLA_FAMILY

    @property
    def pinned(self) -> bool:
        """True when the cache holds exactly the capped revision (or the path shows no sha)."""
        return not self.snapshot_sha or self.snapshot_sha == self.capped_v1_sha

    @property
    def warm(self) -> bool:
        return self.warmup_ms is not None

    def label(self) -> str:
        """`algenta-stats@ac35ffe` — the family and its pinned revision, for chips and footers."""
        return f"{self.family}@{self.short_sha}"


def variant_of(kernel: ModuleType) -> str:
    """The build variant directory from `kernel.__file__` (`.../build/<variant>/__init__.py`)."""
    path = str(getattr(kernel, "__file__", "") or "")
    if _BUILD_MARKER not in path:
        raise HubKernelUnavailable(
            "variant_unknown", f"the kernel path holds no build variant: {path or 'no __file__'}"
        )
    variant = path.split(_BUILD_MARKER, 1)[1].split("/", 1)[0]
    if not variant:
        raise HubKernelUnavailable("variant_unknown", f"empty build variant in {path}")
    return variant


def snapshot_sha_of(kernel: ModuleType) -> str:
    """The Hub snapshot revision in `kernel.__file__`, or an empty string when not in a snapshot."""
    match = _SNAPSHOT_RE.search(str(getattr(kernel, "__file__", "") or ""))
    return match.group(1) if match else ""


def _import_get_kernel() -> Callable[..., ModuleType]:
    try:
        from kernels import get_kernel
    except ImportError as exc:
        missing = getattr(exc, "name", None) or "kernels"
        torch_missing = missing.split(".")[0] == "torch"
        code = "torch_not_installed" if torch_missing else "kernels_not_installed"
        raise HubKernelUnavailable(
            code, f"{missing} is not installed; `pip install kernels torch` provides both"
        ) from exc
    return get_kernel


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else type(exc).__name__


def map_load_error(repo_id: str, exc: BaseException) -> HubKernelUnavailable:
    """The typed error for whatever `get_kernel` or the kernel's own loader raised."""
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.strip():
        return HubKernelUnavailable(code, f"{repo_id}: {getattr(exc, 'message', _first_line(exc))}")
    if isinstance(exc, ImportError):
        missing = getattr(exc, "name", None) or ""
        if missing.split(".")[0] == "torch":
            return HubKernelUnavailable(
                "torch_not_installed", f"{repo_id}: torch is not installed ({_first_line(exc)})"
            )
        return HubKernelUnavailable(
            "kernels_not_installed", f"{repo_id}: import failed ({_first_line(exc)})"
        )
    text = _first_line(exc)
    lowered = text.lower()
    if isinstance(exc, FileNotFoundError):
        if "build variant" in lowered or "variant" in lowered:
            return HubKernelUnavailable(
                "variant_unavailable", f"{repo_id}: no build for this platform ({text})"
            )
        return HubKernelUnavailable(
            "cache_missing", f"{repo_id}: not in the local cache and offline ({text})"
        )
    if isinstance(exc, OSError):
        return HubKernelUnavailable("hub_unreachable", f"{repo_id}: {text}")
    if isinstance(exc, ValueError) and "trust" in lowered:
        return HubKernelUnavailable("trust_required", f"{repo_id}: {text}")
    return HubKernelUnavailable("load_failed", f"{repo_id}: {type(exc).__name__}: {text}")


def load(
    family: str,
    *,
    backend: str = DEFAULT_BACKEND,
    version: int = DEFAULT_VERSION,
    trust: Iterable[str] | None = None,
    get_kernel: Callable[..., ModuleType] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> LoadedKernel:
    """Load one family from the Hub (or the baked cache) and describe what arrived.

    `trust` defaults to `TRUST`; `get_kernel` defaults to `kernels.get_kernel`
    imported here, so the module imports without `kernels` installed.
    """
    repo_id = repo_id_of(family, trust=trust)
    trusted = list(TRUST if trust is None else trust)
    fetch = _import_get_kernel() if get_kernel is None else get_kernel
    t0 = clock()
    try:
        kernel = fetch(repo_id, version=version, backend=backend, trust_remote_code=trusted)
    except HubKernelError:
        raise
    except Exception as exc:
        raise map_load_error(repo_id, exc) from exc
    load_s = clock() - t0
    loaded = LoadedKernel(
        family=short_family(repo_id),
        repo_id=repo_id,
        kernel=kernel,
        variant=variant_of(kernel),
        capped_v1_sha=CAPABILITIES.capped_v1_shas.get(repo_id, ""),
        snapshot_sha=snapshot_sha_of(kernel),
        backend=backend,
        version=version,
        load_s=load_s,
    )
    if not loaded.pinned:
        log.warning(
            "%s: cache holds revision %s, the capped v1 revision is %s",
            repo_id,
            loaded.snapshot_sha,
            loaded.capped_v1_sha,
        )
    log.info("%s: loaded %s in %.2f s", repo_id, loaded.variant, load_s)
    return loaded


# ---------------------------------------------------------------------------
# Contract navigation and calls
# ---------------------------------------------------------------------------


def family_modules(loaded: LoadedKernel) -> dict[str, ModuleType]:
    """The kernel modules that carry a `CONTRACT`: the family itself, or the umbrella's members."""
    kernel = loaded.kernel
    if hasattr(kernel, "CONTRACT"):
        return {loaded.family: kernel}
    families = getattr(kernel, "families", None)
    if not isinstance(families, dict) or not families:
        raise HubKernelUnavailable(
            "no_contract", f"{loaded.repo_id} exposes neither CONTRACT nor families"
        )
    members: dict[str, ModuleType] = {}
    for attr, repo_id in families.items():
        member = getattr(kernel, str(attr), None)
        if member is None or not hasattr(member, "CONTRACT"):
            raise HubKernelUnavailable(
                "no_contract", f"{loaded.repo_id}: member {attr!r} ({repo_id}) has no CONTRACT"
            )
        members[short_family(str(repo_id))] = member
    return members


def _contract_modules(kernel: ModuleType) -> dict[str, Any]:
    contract = getattr(kernel, "CONTRACT", None)
    modules = contract.get("modules") if isinstance(contract, dict) else None
    if not isinstance(modules, dict):
        raise HubKernelUnavailable("no_contract", "CONTRACT.modules is missing")
    return modules


def owner_of(loaded: LoadedKernel, module: str) -> tuple[str, ModuleType]:
    """The (family, kernel module) that ships `module`, or `unknown_module`."""
    for family, kernel in family_modules(loaded).items():
        if module in _contract_modules(kernel):
            return family, kernel
    raise HubKernelCallError("unknown_module", f"{loaded.repo_id} ships no module {module!r}")


def excluded_keys(loaded: LoadedKernel | None = None) -> frozenset[str]:
    """`module.function` and `module.*` patterns hidden from forms and refused before a call."""
    keys = set(CAPABILITIES.excluded_functions)
    if loaded is not None:
        for kernel in family_modules(loaded).values():
            keys.update(str(k) for k in getattr(kernel, "excluded_functions", ()) or ())
    return frozenset(keys)


def is_excluded(module: str, function: str, keys: Iterable[str]) -> bool:
    keys = set(keys)
    return f"{module}.{function}" in keys or f"{module}.*" in keys


def function_spec(loaded: LoadedKernel, module: str, function: str) -> dict[str, Any]:
    """The contract entry for one function as a plain dict; excluded functions are refused."""
    _, kernel = owner_of(loaded, module)
    functions = _contract_modules(kernel)[module].get("functions")
    if not isinstance(functions, dict) or function not in functions:
        raise HubKernelCallError(
            "unknown_function", f"{module} has no function {function!r} in this kernel"
        )
    if is_excluded(module, function, excluded_keys(loaded)):
        raise HubKernelCallError(
            "excluded_function",
            f"{module}.{function} is not callable in-process: "
            f"{CAPABILITIES.excluded_functions.get(f'{module}.{function}', 'excluded')}",
        )
    return copy.deepcopy(functions[function])


@dataclass(frozen=True)
class Call:
    """One completed native call: what was asked, what came back, how long it took end to end."""

    module: str
    function: str
    args: list[Any] | dict[str, Any]
    result: Any
    elapsed_ms: float

    def as_call(self) -> str:
        return CardExample(self.module, self.function, self.args).as_call()


def execute(
    loaded: LoadedKernel,
    module: str,
    function: str,
    args: list[Any] | dict[str, Any],
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> Call:
    """`kernel.execute(module, function, args)` timed; the kernel's error code is preserved.

    The time includes JSON marshalling across the C ABI (`TRANSPORT_NOTE`).
    Under ABI §9 the call waits for the device's one worker slot if another
    native call is running, so route it through `lane.Lane`.
    """
    function_spec(loaded, module, function)
    _, kernel = owner_of(loaded, module)
    run = getattr(kernel, "execute", None)
    if not callable(run):
        raise HubKernelUnavailable("no_contract", f"{loaded.repo_id} has no execute()")
    t0 = clock()
    try:
        result = run(module, function, args)
    except HubKernelError:
        raise
    except Exception as exc:
        code = getattr(exc, "code", None)
        if isinstance(code, str) and code.strip():
            raise HubKernelCallError(
                code,
                str(getattr(exc, "message", _first_line(exc))),
                details=dict(getattr(exc, "details", None) or {}),
            ) from exc
        raise HubKernelCallError(
            "call_failed", f"{module}.{function}: {type(exc).__name__}: {_first_line(exc)}"
        ) from exc
    elapsed_ms = (clock() - t0) * 1e3
    return Call(module, function, copy.deepcopy(args), result, elapsed_ms)


def card_example(family: str, examples: Mapping[str, CardExample] | None = None) -> CardExample:
    """The family's one contract-valid example call, or `no_card_example`."""
    table = CARD_EXAMPLES if examples is None else examples
    name = short_family(family)
    example = table.get(name)
    if example is None:
        raise HubKernelError("no_card_example", f"{name} has no card example to warm up with")
    return example


def warm_up(
    loaded: LoadedKernel,
    *,
    example: CardExample | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Call:
    """Run the family's card example once, timed, and record it on `loaded`.

    The first native call pays the runtime initialisation (about a second on a
    cold container); doing it here, before `launch()`, keeps it off the first
    visitor's request.
    """
    call_spec = card_example(loaded.family) if example is None else example
    call = execute(loaded, call_spec.module, call_spec.function, call_spec.args, clock=clock)
    loaded.warmup_ms = call.elapsed_ms
    loaded.warmup_call = call_spec
    loaded.warmup_result = call.result
    log.info("%s: warm in %.1f ms (%s)", loaded.repo_id, call.elapsed_ms, call_spec.as_call())
    return call


def describe(loaded: LoadedKernel) -> dict[str, Any]:
    """`CONTRACT` as plain dicts for the UI: modules → functions → params, excluded removed.

    Each module carries the family that ships it (the umbrella merges nineteen),
    its description and `status_decoder` where the contract names one; each
    function its params (`name`, `type`, `has_default`, `default` when known,
    `doc`), `return_type`, `returns_doc`, `doc` and `count_relations`.
    """
    hidden = excluded_keys(loaded)
    modules: dict[str, Any] = {}
    removed: list[str] = []
    for family, kernel in family_modules(loaded).items():
        for module_name, spec in sorted(_contract_modules(kernel).items()):
            functions_in = spec.get("functions") if isinstance(spec, dict) else None
            functions_out: dict[str, Any] = {}
            for function_name, fn in sorted((functions_in or {}).items()):
                if is_excluded(module_name, function_name, hidden):
                    removed.append(f"{module_name}.{function_name}")
                    continue
                functions_out[function_name] = {
                    "name": function_name,
                    "params": copy.deepcopy(fn.get("params", [])),
                    "return_type": fn.get("return_type", ""),
                    "returns_doc": fn.get("returns_doc", ""),
                    "doc": fn.get("doc", ""),
                    "count_relations": copy.deepcopy(fn.get("count_relations", [])),
                }
            entry: dict[str, Any] = {
                "family": family,
                "description": spec.get("description", "") if isinstance(spec, dict) else "",
                "functions": functions_out,
            }
            if isinstance(spec, dict) and "status_decoder" in spec:
                entry["status_decoder"] = spec["status_decoder"]
            if isinstance(spec, dict) and spec.get("structs"):
                entry["structs"] = copy.deepcopy(spec["structs"])
            modules[module_name] = entry
    return {
        "family": loaded.family,
        "repo_id": loaded.repo_id,
        "variant": loaded.variant,
        "capped_v1_sha": loaded.capped_v1_sha,
        "backend": loaded.backend,
        "version": loaded.version,
        "modules": modules,
        "excluded": sorted(removed),
        "function_count": sum(len(m["functions"]) for m in modules.values()),
    }


# ---------------------------------------------------------------------------
# Boot: preload every family
# ---------------------------------------------------------------------------

Progress = Callable[[str, str, str], None]


@dataclass
class Preload:
    """The outcome of `preload`: what loaded, what did not and why, how long it took."""

    loaded: dict[str, LoadedKernel] = field(default_factory=dict)
    errors: dict[str, HubKernelError] = field(default_factory=dict)
    elapsed_s: float = 0.0
    done: threading.Event = field(default_factory=threading.Event)

    def wait(self, timeout: float | None = None) -> bool:
        return self.done.wait(timeout)

    @property
    def ok(self) -> bool:
        return self.done.is_set() and not self.errors

    def summary(self) -> str:
        """`3 families warm in 4.2 s`, or the failures by code."""
        total = len(self.loaded) + len(self.errors)
        warm = sum(1 for item in self.loaded.values() if item.warm)
        noun = "family" if total == 1 else "families"
        if not self.errors:
            state = "warm" if warm == len(self.loaded) else "loaded"
            return f"{total} {noun} {state} in {self.elapsed_s:.1f} s"
        failed = ", ".join(f"{name}: {err.code}" for name, err in sorted(self.errors.items()))
        return f"{len(self.loaded)} of {total} {noun} loaded in {self.elapsed_s:.1f} s; {failed}"


def preload(
    families: Iterable[str],
    *,
    backend: str = DEFAULT_BACKEND,
    version: int = DEFAULT_VERSION,
    before_launch: bool = True,
    warm: bool = True,
    progress: Progress | None = None,
    get_kernel: Callable[..., ModuleType] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Preload:
    """Load (and warm) every family for boot.

    `before_launch=True` runs synchronously and returns when every family has
    loaded or failed — call it before `blocks.launch()` so the first visitor sees
    warm kernels. `before_launch=False` runs the same work on a daemon thread and
    returns at once; `wait()` on the result. `progress(family, event, detail)`
    receives `loading`, `loaded`, `warm` and `error` events for the boot card.
    Per-family failures are collected in `errors`, never raised: a Space holds
    that family's tab with the reason and ships the rest.
    """
    names = [short_family(name) for name in families]
    if len(set(names)) != len(names):
        raise ValueError(f"families repeat: {names}")
    outcome = Preload()

    def say(family: str, event: str, detail: str) -> None:
        if progress is not None:
            progress(family, event, detail)

    def work() -> None:
        t0 = clock()
        try:
            for family in names:
                say(family, "loading", f"{ORG}/{family}")
                try:
                    item = load(
                        family, backend=backend, version=version, get_kernel=get_kernel, clock=clock
                    )
                    say(family, "loaded", f"{item.variant} in {item.load_s:.1f} s")
                    if warm:
                        call = warm_up(item, clock=clock)
                        say(family, "warm", f"{call.as_call()} in {call.elapsed_ms:.1f} ms")
                    outcome.loaded[family] = item
                except HubKernelError as exc:
                    outcome.errors[family] = exc
                    log.warning("%s: %s", family, exc)
                    say(family, "error", f"{exc.code}: {exc.message}")
        finally:
            outcome.elapsed_s = clock() - t0
            outcome.done.set()

    if before_launch:
        work()
        return outcome
    thread = threading.Thread(target=work, name="algenta-preload", daemon=True)
    thread.start()
    return outcome


# ---------------------------------------------------------------------------
# Host floor and footer note
# ---------------------------------------------------------------------------


def cpu_flags(cpuinfo: Path | str = "/proc/cpuinfo") -> frozenset[str]:
    """The `flags` set from /proc/cpuinfo; empty where the file has none or is unreadable."""
    try:
        with open(cpuinfo, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                key, sep, value = line.partition(":")
                if sep and key.strip().lower() in ("flags", "features"):
                    return frozenset(value.split())
    except OSError:
        return frozenset()
    return frozenset()


def parse_version(text: str) -> tuple[int, int] | None:
    """`2.35` from `2.35`, `glibc 2.35-0ubuntu3` or `2.39 (Ubuntu GLIBC 2.39-0ubuntu8)`."""
    match = _VERSION_RE.search(text or "")
    return (int(match.group(1)), int(match.group(2))) if match else None


def glibc_version() -> tuple[int, int] | None:
    """The running glibc from `gnu_get_libc_version`, else `platform.libc_ver`, else None."""
    try:
        libc = ctypes.CDLL(None)
        getter = libc.gnu_get_libc_version
        getter.restype = ctypes.c_char_p
        getter.argtypes = []
        return parse_version(getter().decode("ascii", "replace"))
    except (OSError, AttributeError, TypeError):
        pass
    name, version = platform.libc_ver()
    return parse_version(version) if name == "glibc" else None


def host_floor_ok(
    *,
    system: str | None = None,
    machine: str | None = None,
    cpuinfo: Path | str = "/proc/cpuinfo",
    libc_version: str | tuple[int, int] | None = None,
) -> tuple[bool, str]:
    """Is this host at the published CPU floor? `(ok, reason)` — the reason is always given.

    Linux x86_64 needs `avx2` (x86-64-v3) and glibc >= 2.35; Linux aarch64 needs
    glibc >= 2.35; macOS is bypassed because the kernel loader enforces the
    macOS 15 floor from each variant's manifest. Every input is injectable.
    """
    system = platform.system() if system is None else system
    machine = platform.machine() if machine is None else machine
    if system == "Darwin":
        return True, f"macOS {machine}: the loader checks the macOS 15 floor; no glibc or avx2 rule"
    if system != "Linux":
        return False, f"{system} {machine}: not a published platform (Linux and macOS arm64 are)"
    problems: list[str] = []
    facts: list[str] = []
    if machine in ("x86_64", "amd64"):
        flags = cpu_flags(cpuinfo)
        if not flags:
            problems.append("cpu flags unreadable")
        elif X86_64_V3_FLAG not in flags:
            problems.append(f"cpu lacks {X86_64_V3_FLAG} (x86-64-v3 floor)")
        else:
            facts.append(f"{X86_64_V3_FLAG} present")
    elif machine in ("aarch64", "arm64"):
        facts.append("aarch64: no instruction-set floor")
    else:
        return False, f"Linux {machine}: not a published architecture (x86_64 and aarch64 are)"
    if libc_version is None:
        version = glibc_version()
    elif isinstance(libc_version, tuple):
        version = libc_version
    else:
        version = parse_version(libc_version)
    if version is None:
        problems.append("glibc version unreadable")
    elif version < GLIBC_FLOOR:
        problems.append(
            f"glibc {version[0]}.{version[1]} is below {GLIBC_FLOOR[0]}.{GLIBC_FLOOR[1]}"
        )
    else:
        facts.append(f"glibc {version[0]}.{version[1]}")
    if problems:
        return False, f"Linux {machine}: " + "; ".join(problems)
    return True, f"Linux {machine}: " + ", ".join(facts)


def platform_note(
    loaded: LoadedKernel | Iterable[LoadedKernel] | None = None,
    *,
    dists: Iterable[str] = PINNED_DISTS,
) -> str:
    """The footer line: variant, pinned families, package pins, OS and the one-worker note.

    `Hub kernels · torch25-cpu-aarch64-darwin · algenta-stats@ac35ffe · kernels 0.17.1 ·
    torch 2.5.1 · Darwin arm64 · one native call at a time`
    """
    items = [] if loaded is None else [loaded] if isinstance(loaded, LoadedKernel) else list(loaded)
    parts = ["Hub kernels"]
    variants = sorted({item.variant for item in items})
    if variants:
        parts.append(", ".join(variants))
    if items:
        parts.append(", ".join(item.label() for item in items))
    for name, version in pinned_versions(dists).items():
        parts.append(f"{name} {version}" if version else f"{name} not installed")
    parts.append(f"{platform.system()} {platform.machine()}")
    parts.append(ONE_WORKER_NOTE)
    return check_copy(" · ".join(parts), what="platform note")


# ---------------------------------------------------------------------------
# Import-time state
# ---------------------------------------------------------------------------

CAPABILITIES: Capabilities = load_capabilities()
TRUST: tuple[str, ...] = CAPABILITIES.trust
CARD_EXAMPLES: dict[str, CardExample] = load_card_examples()
