from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_FILES = (
    "examples/capability-plane/README.md",
    "examples/langgraph/capability_router.py",
    "apps/docs/docs/api-reference/capability-plane.md",
    "apps/docs/docs/sdks/python.md",
    "apps/docs/docs/sdks/typescript.md",
    "apps/docs/docs/integrations/langgraph.md",
    "packages/algenta-core/README.md",
)

_SECTION_FILES = (
    "packages/python-sdk/README.md",
    "packages/ts-sdk/README.md",
)

_FORBIDDEN_SNIPPETS = (
    "Mission-owned",
    "Mission and other external clients",
    "x-active-mcps",
    "x-active-skills",
)


def test_capability_plane_public_surfaces_remain_customer_agnostic() -> None:
    for relative_path in _FILES:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in _FORBIDDEN_SNIPPETS:
            assert snippet not in text, f"{relative_path} leaked forbidden snippet: {snippet}"


def _extract_unified_capability_plane_section(text: str) -> str:
    marker = "## Unified Capability Plane"
    start = text.find(marker)
    assert start != -1, "Unified Capability Plane section is missing."
    next_section = text.find("\n## ", start + len(marker))
    if next_section == -1:
        return text[start:]
    return text[start:next_section]


def test_capability_plane_package_sections_remain_customer_agnostic() -> None:
    for relative_path in _SECTION_FILES:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        section = _extract_unified_capability_plane_section(text)
        for snippet in _FORBIDDEN_SNIPPETS:
            assert snippet not in section, f"{relative_path} leaked forbidden snippet: {snippet}"
