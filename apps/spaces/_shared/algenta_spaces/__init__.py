"""Shared chrome, tokens, cards, rulebook harness and utilities for the Algenta Spaces.

Import order matters only for CSS: `fleet_css()` returns the stylesheets in the
order a Space should load them (tokens first, then the base type utilities,
then shell, cards and boot).
"""

from __future__ import annotations

from . import (
    bench,
    boot,
    cards,
    css,
    design,
    facts,
    hubkernel,
    lane,
    playground,
    ratelimit,
    runtime,
    shell,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "bench",
    "boot",
    "cards",
    "css",
    "design",
    "facts",
    "fleet_css",
    "hubkernel",
    "lane",
    "playground",
    "ratelimit",
    "runtime",
    "shell",
]


def fleet_css() -> str:
    """Every stylesheet the package ships, in load order."""
    return "\n".join(
        (
            design.TOKENS_CSS,
            design.BASE_CSS,
            shell.SHELL_CSS,
            cards.CARD_CSS,
            boot.BOOT_CSS,
        )
    )
