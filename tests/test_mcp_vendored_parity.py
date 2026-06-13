"""Drift guard for code vendored into the standalone `algenta-mcp` package.

`algenta-mcp` (packages/mcp) is decoupled from the monorepo so it can `pipx install`. One pure
stdlib-only formatter is copied verbatim from the engine; this test fails if the copy drifts from
its source, so the two can't silently diverge. (Everything else the MCP package needs comes from
the published `algenta-sdk` or 3rd-party libs — not vendored.)
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

_VENDORED = {
    # vendored copy -> engine source (the copy is a short header + the verbatim source)
    "packages/mcp/algenta_mcp/_channel_envelope.py": (
        "apps/api_server/services/repository_intelligence_channel_envelope.py"
    ),
}


def test_vendored_files_match_their_source() -> None:
    for vendored_rel, source_rel in _VENDORED.items():
        source = (_ROOT / source_rel).read_text(encoding="utf-8")
        vendored = (_ROOT / vendored_rel).read_text(encoding="utf-8")
        assert source in vendored, (
            f"{vendored_rel} drifted from {source_rel} — re-vendor it "
            f"(cp the source in, keep the VENDORED header)."
        )


def test_mcp_package_has_no_monorepo_imports() -> None:
    # The whole point of the package: it must not import apps.* (the monorepo).
    pkg = _ROOT / "packages" / "mcp" / "algenta_mcp"
    offenders = [
        str(p.relative_to(pkg))
        for p in pkg.rglob("*.py")
        if "from apps." in p.read_text(encoding="utf-8")
        or "import apps." in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"algenta-mcp must not import the monorepo (apps.*): {offenders}"
