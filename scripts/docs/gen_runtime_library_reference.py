#!/usr/bin/env python3
"""Generate the Runtime library catalog page from the packaged public contract.

Source of truth: ``packages/algenta/algenta/runtime_library_contract.json``. We render every
public module name with its exact function count, matching the installed CLI, MCP tools, and
``GET /v1/libraries`` without exposing generated dispatch implementation details.

Writes ``gitbook/engine/runtime-library-catalog.md``. ``--check`` fails if it is
stale (CI no-drift gate).
Regression floor: modules must not silently collapse.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "packages" / "algenta" / "algenta" / "runtime_library_contract.json"
OUT = ROOT / "gitbook" / "engine" / "runtime-library-catalog.md"
MODULE_FLOOR = 200

# Ordered category rules: (category title, [substrings]). First match wins;
# the rest fall to "General".
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("Vision & imaging", ["image", "vision", "pixel", "morpholog", "palette", "ocr"]),
    (
        "LLM & attention",
        ["llm", "attention", "transformer", "token", "embedding", "rope", "kv_cache"],
    ),
    (
        "Machine learning",
        [
            "ml_",
            "_ml",
            "activation",
            "gradient",
            "optimizer",
            "loss",
            "layer",
            "neural",
            "state_space",
            "quantiz",
            "calibrat",
            "inference",
            "train",
        ],
    ),
    (
        "Tensors & linear algebra",
        ["tensor", "linalg", "matrix", "vector_kernel", "blas", "eigen", "decomp", "gpu_kernel"],
    ),
    (
        "Statistics & probability",
        [
            "distribution",
            "stat",
            "bayes",
            "probab",
            "hypothesis",
            "ab_testing",
            "regression",
            "sampling",
            "montecarlo",
            "monte_carlo",
            "interval",
        ],
    ),
    ("Signal & audio", ["signal", "fft", "audio", "acoustic", "wavelet", "filter_", "spectr"]),
    (
        "Cryptography & hashing",
        ["crypto", "hash", "cipher", "sha", "hmac", "aes", "rsa", "ecdsa", "ed25519"],
    ),
    ("Text & language", ["text", "string", "tokenize", "levenshtein", "ngram", "unicode", "lang"]),
    ("Graph & automata", ["graph", "automata", "tree", "heap", "trie", "dag", "topolog"]),
    (
        "Serialization & data",
        [
            "json",
            "serial",
            "encode",
            "decode",
            "compress",
            "data_",
            "_data",
            "csv",
            "parquet",
            "protobuf",
            "base64",
        ],
    ),
    (
        "Bits, numbers & time",
        [
            "bitops",
            "bit_",
            "datetime",
            "date",
            "time",
            "calendar",
            "number",
            "arithmetic",
            "interval",
            "rounding",
        ],
    ),
    (
        "Geometry & spatial",
        ["geo", "geometry", "spatial", "haversine", "coordinate", "mesh", "polygon"],
    ),
    (
        "Networking & systems",
        ["net", "http", "url", "ip_", "socket", "compiler", "register", "memory"],
    ),
    (
        "Finance & business",
        [
            "finance",
            "account",
            "npv",
            "irr",
            "amortiz",
            "pricing",
            "tax",
            "payroll",
            "depreciat",
            "bond",
            "option_",
        ],
    ),
]


def extract() -> dict[str, int]:
    """Return exact public module function counts from the packaged contract."""
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    modules = payload.get("modules")
    if not isinstance(modules, list):
        raise ValueError("runtime library contract has no module list")
    counts = {
        module["name"]: len(module["functions"])
        for module in modules
        if isinstance(module, dict)
        and isinstance(module.get("name"), str)
        and isinstance(module.get("functions"), list)
    }
    if len(counts) != payload.get("module_count") or sum(counts.values()) != payload.get(
        "function_count"
    ):
        raise ValueError("runtime library contract counts are inconsistent")
    return counts


def categorize(module: str) -> str:
    for title, subs in CATEGORY_RULES:
        if any(s in module for s in subs):
            return title
    return "General & domain modules"


def render(counts: dict[str, int]) -> str:
    modules = sorted(counts)
    total_fn = sum(counts.values())
    buckets: dict[str, list[str]] = defaultdict(list)
    for m in modules:
        buckets[categorize(m)].append(m)

    order = [t for t, _ in CATEGORY_RULES] + ["General & domain modules"]
    lines: list[str] = []
    lines.append("---")
    lines.append("icon: books")
    lines.append(
        "description: The full catalog of Algenta runtime-library modules — vision, LLM, ML, "
        "tensors, statistics, signal, crypto, and more — callable through /v1/libraries."
    )
    lines.append("---")
    lines.append("")
    lines.append("# Runtime library catalog")
    lines.append("")
    lines.append(
        f"The engine ships a compiled runtime library of **{len(modules)} modules** and "
        f"**{total_fn} functions** — the low-level building blocks the high-level "
        "engines are made of. "
        "You can call any one directly with a `module` + `function` name; see "
        "[Runtime libraries](runtime-libraries.md) for how to list, check, and execute them."
    )
    lines.append("")
    lines.append('{% hint style="info" %}')
    lines.append(
        "The catalog is **self-describing** — `GET /v1/libraries` returns every "
        "module and its exported functions live, and `GET /v1/libraries?q=<term>` "
        "filters by name (for example `?q=image` for the vision modules, `?q=llm` "
        "for sampling). This page groups the modules so you can see what is "
        "available; the endpoint is the authoritative, always-current list."
    )
    lines.append("{% endhint %}")
    lines.append("")
    lines.append("## Flagship domains")
    lines.append("")
    lines.append(
        "A few of the most-used domains, with example modules. **Computer vision** — `image_ops`, "
        "`image_features`, `image_similarity`, `image_morphology`, `image_resize`, "
        "`image_quality`, `image_regions`, `image_palette`, `document_vision`, "
        "`vision_gate`. **LLM** — `llm_sampling`, `vision_attention_scale`. Discover "
        "any of them with `GET /v1/libraries?q=image` or `?q=llm`."
    )
    lines.append("")
    for cat in order:
        mods = buckets.get(cat)
        if not mods:
            continue
        lines.append(f"## {cat}")
        lines.append("")
        lines.append(f"{len(mods)} modules.")
        lines.append("")
        lines.append("| Module | Functions |")
        lines.append("| --- | --- |")
        for m in sorted(mods):
            lines.append(f"| `{m}` | {counts[m]} |")
        lines.append("")

    lines.append("## Call a module")
    lines.append("")
    lines.append(
        "Every module here is callable through the same surface — the HTTP API, "
        "the `de` CLI, and the MCP "
        "tools. See [Runtime libraries](runtime-libraries.md) for the `GET /v1/libraries`, "
        "`GET /v1/libraries/health`, and `POST /v1/libraries/execute` details."
    )
    lines.append("")
    lines.append('<table data-view="cards">')
    lines.append(
        "<thead><tr><th></th><th></th><th data-hidden data-card-target "
        'data-type="content-ref"></th></tr></thead>'
    )
    lines.append("<tbody>")
    lines.append(
        "<tr><td><strong>Run a library function</strong></td><td>List, check, and "
        "execute modules over the API, CLI, or MCP.</td><td><a "
        'href="runtime-libraries.md">runtime-libraries.md</a></td></tr>'
    )
    lines.append(
        "<tr><td><strong>Engine catalog</strong></td><td>The high-level engines "
        "these functions compose into.</td><td><a "
        'href="catalog.md">catalog.md</a></td></tr>'
    )
    lines.append(
        "<tr><td><strong>How the engine works</strong></td><td>Where the runtime "
        "library sits in the architecture.</td><td><a "
        'href="../concepts/engine.md">../concepts/engine.md</a></td></tr>'
    )
    lines.append("</tbody>")
    lines.append("</table>")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if the page is stale")
    args = ap.parse_args()

    counts = extract()
    if len(counts) < MODULE_FLOOR:
        print(f"EXTRACTION BROKEN: {len(counts)} modules < floor {MODULE_FLOOR}")
        return 1
    content = render(counts)

    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != content:
            print(f"DRIFT: {OUT.relative_to(ROOT)} is stale vs the contract — run `make docs-gen`")
            return 1
        print(f"runtime-library-catalog.md OK ({len(counts)} modules)")
        return 0

    OUT.write_text(content, encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} ({len(counts)} modules, {sum(counts.values())} functions)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
