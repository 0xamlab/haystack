from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cli_docs_require_explicit_target_for_private_profiles() -> None:
    text = (ROOT / "apps/docs/docs/sdks/cli.md").read_text(encoding="utf-8")

    assert "`self_hosted` and `air_gapped` profiles require an explicit CLI target" in text
    assert "default CLI target: `http://localhost:8000`" not in text
