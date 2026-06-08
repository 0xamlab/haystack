from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
README = ROOT / "README.md"
CAPABILITY_PLANE_DOC = ROOT / "apps" / "docs" / "docs" / "api-reference" / "capability-plane.md"


def test_makefile_exposes_capability_plane_verify_target() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "capability-plane-verify:" in text
    assert "## capability-plane-verify:" in text
    assert "tests/test_capability_plane_contract_parity.py" in text
    assert "tests/test_capability_plane_typed_failure_parity.py" in text
    assert "tests/test_capability_plane_public_agnosticity.py" in text
    assert "tests/test_capability_plane_api.py" in text
    assert "tests/test_mcp_capability_plane_tools.py" in text
    assert "tests/test_gitbook_v1_docs.py" in text
    assert "pnpm --filter algenta-sdk test -- src/capability_plane.test.ts" in text


def test_capability_plane_verify_target_is_discoverable_from_root_and_api_docs() -> None:
    readme = README.read_text(encoding="utf-8")
    api_doc = CAPABILITY_PLANE_DOC.read_text(encoding="utf-8")

    assert "make capability-plane-verify" in readme
    assert "make capability-plane-verify" in api_doc


def test_make_help_lists_capability_plane_verify_target() -> None:
    proc = subprocess.run(  # noqa: S603
        ["make", "help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "capability-plane-verify" in proc.stdout
