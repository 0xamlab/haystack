from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "build" / "proofs" / "cline" / "cline_docs_snapshot.txt"
SNAPSHOT_HASH = ROOT / "build" / "proofs" / "cline" / "cline_docs_snapshot.sha256"


def test_cline_docs_snapshot_hash_matches_contents() -> None:
    payload = SNAPSHOT.read_bytes()
    expected_hash = SNAPSHOT_HASH.read_text(encoding="utf-8").strip()

    assert hashlib.sha256(payload).hexdigest() == expected_hash


def test_cline_docs_snapshot_covers_required_parity_surfaces() -> None:
    text = SNAPSHOT.read_text(encoding="utf-8")

    for needle in (
        "ClineCore",
        "Events",
        "Writing Plugins",
        "Permission Handling",
        "Multi-Agent Teams",
        "Scheduled Agents",
        "GitHub Actions Integration",
        "GitHub PR Review",
        "ACP: Editor Integrations",
        "MCP",
    ):
        assert needle in text, f"missing docs snapshot capability marker: {needle}"
