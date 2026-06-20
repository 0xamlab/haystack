# ruff: noqa: T201
"""
Multi-hop local runtime-library flow example.

This module demonstrates the local runtime-library path. It defaults to a
local daemon and does not silently fall back to Algenta cloud. If you provide
`ALGENTA_BASE_URL` / `DE_BASE_URL` / `ALGENTA_API_URL` or `ALGENTA_API_KEY` /
`DE_API_KEY` for daemon bootstrap or self-hosted control surfaces, point them
at your self-hosted operator deployment instead of Algenta cloud in
`self_hosted` and `air_gapped`.
"""

from __future__ import annotations

import os

from algenta import MojoRuntime, libraries


def _optional_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _runtime_config() -> dict[str, str | bool]:
    return {
        "mode": "local",
        "auto_start_daemon": _optional_env("ALGENTA_AUTO_START_DAEMON") != "0",
        "api_key": _optional_env("ALGENTA_API_KEY", "DE_API_KEY"),
        "base_url": _optional_env("ALGENTA_BASE_URL", "DE_BASE_URL", "ALGENTA_API_URL"),
    }


def main() -> None:
    runtime_config = _runtime_config()
    runtime = MojoRuntime(**runtime_config)

    # Mission get_algenta_library_health -> public MojoRuntime.health()
    health = runtime.health()
    print("runtime health:", health)

    # Mission list_algenta_libraries -> public list_modules() / catalog.names()
    modules = runtime.list_modules()
    print("module count:", len(modules))
    print("first modules:", [module["name"] for module in modules[:5]])

    catalog = libraries(**runtime_config)
    print("catalog names:", catalog.names()[:5])

    # Mission inspect_algenta_library / get_algenta_library_module
    print("text.tokenizer functions:", runtime.list_functions("text.tokenizer"))
    text_tokenizer = catalog.module("text.tokenizer")
    print("text.tokenizer proxy name:", text_tokenizer.name)

    # Mission execute_algenta_library -> direct execute() or module proxy calls
    direct = runtime.execute(
        "rerank_eval",
        "precision_at_k",
        {"relevance": [1, 0, 1, 1], "k": 3},
    )
    print("direct execute result:", direct["result"])

    tokens = text_tokenizer.word_tokenize("delay correlation route")
    print("proxy execute result:", tokens)


if __name__ == "__main__":
    main()
