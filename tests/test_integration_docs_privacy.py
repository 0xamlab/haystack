from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_DOC_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "apps/docs/docs/integrations/overview.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "replace the hosted base URL with your self-hosted base URL",
        "Private profiles do not silently fall back to Algenta cloud.",
        "Authorization: Bearer <YOUR_ALGENTA_API_KEY>",
    ),
    "apps/docs/docs/integrations/chatgpt-actions.md": (
        "Cloud Managed",
        "replace the hosted base URL with your self-hosted base URL",
        "Private profiles do not silently fall back to Algenta cloud.",
        "https://your-algenta-base-url.example/openapi.json",
    ),
    "apps/docs/docs/integrations/claude-codex.md": (
        "Cloud Managed endpoint",
        "replace the hosted base URL with your self-hosted base URL",
        "Private profiles do not silently fall back to Algenta cloud.",
        "`DE_API_KEY`, `DE_BASE_URL`, and `ALGENTA_API_URL` remain accepted for compatibility.",
        "Authorization: Bearer <YOUR_ALGENTA_API_KEY>",
        "<SET ALGENTA_API_KEY OR DE_API_KEY BEFORE LAUNCH>",
    ),
    "apps/docs/docs/integrations/azure-ai-studio.md": (
        "Cloud Managed",
        "replace the hosted base URL with your self-hosted base URL",
        "Private profiles do not silently fall back to Algenta cloud.",
        "https://your-algenta-base-url.example/openapi.json",
        "legacy `DE_API_KEY`,",
        "`DE_BASE_URL`, and `ALGENTA_API_URL` remain accepted for compatibility.",
    ),
    "apps/docs/docs/integrations/n8n.md": (
        "Cloud Managed",
        "replace the hosted base URL with your self-hosted base URL",
        "Private profiles do not silently fall back to Algenta cloud.",
        "Bearer <YOUR_ALGENTA_API_KEY>",
        "https://your-algenta-base-url.example",
    ),
    "apps/docs/docs/integrations/zapier.md": (
        "Cloud Managed",
        "replace the hosted base URL with your self-hosted base URL",
        "Private profiles do not silently fall back to Algenta cloud.",
        "Authorization: Bearer <YOUR_ALGENTA_API_KEY>",
        "https://your-algenta-base-url.example",
    ),
    "apps/docs/docs/integrations/make.md": (
        "Cloud Managed",
        "replace the hosted base URL with your self-hosted base URL",
        "Private profiles do not silently fall back to Algenta cloud.",
        "Authorization: Bearer <YOUR_ALGENTA_API_KEY>",
        "https://your-algenta-base-url.example",
    ),
    "apps/mcp_server/README.md": (
        "Cloud Managed",
        "replace the hosted base URL with your self-hosted base URL",
        "Private profiles fail closed and will not silently fall back to Algenta cloud.",
        "Use `https://app.algenta.ai/dashboard/api-keys` only in Cloud Managed.",
        "self-hosted operator deployment",
        "`DE_API_KEY`, `DE_BASE_URL`, and `ALGENTA_API_URL` remain accepted for compatibility.",
    ),
}


@pytest.mark.parametrize(
    ("relative_path", "required_snippets"),
    list(_DOC_EXPECTATIONS.items()),
)
def test_integration_docs_call_out_private_profile_base_url_rules(
    relative_path: str,
    required_snippets: tuple[str, ...],
) -> None:
    text = (ROOT / relative_path).read_text()
    for snippet in required_snippets:
        assert snippet in text


def test_mcp_readme_uses_current_dashboard_hostname() -> None:
    text = (ROOT / "apps" / "mcp_server" / "README.md").read_text()

    assert "app.algenta.io" not in text
    assert "https://app.algenta.ai/dashboard/api-keys" in text


def test_mcp_readme_uses_fail_closed_key_resolution_in_runnable_examples() -> None:
    text = (ROOT / "apps" / "mcp_server" / "README.md").read_text()

    assert 'export ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"' in text
    assert 'echo "Set ALGENTA_API_KEY or DE_API_KEY before running this example."' in text
    assert 'api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in text
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in text
    assert 'base_url = (' in text
    assert 'raise RuntimeError(' in text
    assert 'Set ALGENTA_BASE_URL, DE_BASE_URL, or ALGENTA_API_URL before running this example.' in text
    assert 'Use https://api.algenta.ai only in Cloud Managed.' in text
    assert 'or "https://api.algenta.ai"' not in text
    assert "de_live_your_key_here" not in text


def test_claude_codex_doc_avoids_live_looking_key_literals() -> None:
    text = (ROOT / "apps" / "docs" / "docs" / "integrations" / "claude-codex.md").read_text()

    assert "Authorization: Bearer de_live_..." not in text
    assert "de_live_YOUR_KEY_HERE" not in text
