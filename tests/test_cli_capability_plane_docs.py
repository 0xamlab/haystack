from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_DOC = ROOT / "apps" / "docs" / "docs" / "sdks" / "cli.md"


def test_cli_docs_cover_capability_plane_commands() -> None:
    text = CLI_DOC.read_text()

    assert "de capabilities providers --format json" in text
    assert "de capabilities provider provider.skill_pack.algenta --format json" in text
    assert "de capabilities bindings --provider-id provider.skill_pack.algenta --format json" in text
    assert "de capabilities list --kind skill,mcp_tool --format json" in text
    assert "de capabilities route examples/capability-plane/capability_route_request.json --format json" in text
    assert "de capabilities execute examples/capability-plane/capability_execute_request.json --format json" in text
    assert "examples/capability-plane/" in text
    assert "`de capabilities providers`" in text
    assert "`de capabilities route <request.json>`" in text
    assert "`de capabilities execute <request.json>` to execute one selected `algenta_managed` capability" in text
    assert "`algenta_managed` routes can execute through `de capabilities execute`" in text
    assert "`client_managed` routes must execute through the customer app or local adapter path" in text
