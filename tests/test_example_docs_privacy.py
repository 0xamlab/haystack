from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_README_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "examples/claude-desktop/README.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Codna cloud.",
        "Cloud Managed API keys come from",
        "self-hosted operator",
        "legacy `DE_API_KEY`, `DE_BASE_URL`, and `ALGENTA_API_URL` remain accepted for compatibility.",
        "<SET ALGENTA_API_KEY OR DE_API_KEY BEFORE LAUNCH>",
        "Authorization: Bearer <YOUR_ALGENTA_API_KEY>",
    ),
    "examples/chatgpt-actions/README.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Codna cloud.",
        "https://your-algenta-base-url.example",
        "/openapi.json",
        "Authorization: Bearer <YOUR_ALGENTA_API_KEY>",
    ),
    "examples/n8n/README.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Codna cloud.",
        "https://your-algenta-base-url.example",
        "Authorization: Bearer <YOUR_ALGENTA_API_KEY>",
        "Replace `https://your-algenta-base-url.example` with Cloud Managed",
        "provisioned by that deployment.",
    ),
    "examples/make/README.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Codna cloud.",
        "https://your-algenta-base-url.example",
        "Use `https://app.codna.ai/dashboard/api-keys` only in Cloud Managed.",
        "self-hosted operator",
        "Authorization: Bearer <YOUR_ALGENTA_API_KEY>",
    ),
    "examples/zapier/README.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Codna cloud.",
        "https://your-algenta-base-url.example",
        "Use `https://app.codna.ai/dashboard/api-keys` only in Cloud Managed.",
        "self-hosted operator",
        "Authorization: Bearer <YOUR_ALGENTA_API_KEY>",
    ),
    "examples/power-automate/README.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Codna cloud.",
        "https://your-algenta-base-url.example",
        "Use a Cloud Managed key only when the flow targets",
        "self-hosted operator deployment",
        "Authorization: Bearer <YOUR_ALGENTA_API_KEY>",
    ),
    "examples/multi-hop/README.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Codna cloud.",
        'ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"',
        'echo "Set ALGENTA_API_KEY or DE_API_KEY before running this example."',
        'ALGENTA_BASE_URL="${ALGENTA_BASE_URL:-${DE_BASE_URL:-${ALGENTA_API_URL:-https://api.codna.ai}}}"',
    ),
    "examples/capability-plane/README.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Codna cloud.",
        'ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"',
        'echo "Set ALGENTA_API_KEY or DE_API_KEY before running this example."',
        'ALGENTA_BASE_URL="${ALGENTA_BASE_URL:-${DE_BASE_URL:-${ALGENTA_API_URL:-https://api.codna.ai}}}"',
        "examples/langgraph/capability_router.py",
    ),
    "examples/azure-ai-studio/README.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Codna cloud.",
        "All snippets below resolve `ALGENTA_URL` from `ALGENTA_BASE_URL`,",
        "provisioned by your",
        "ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY>",
        'os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")',
        'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")',
        'os.environ.get("ALGENTA_BASE_URL")',
        'or os.environ.get("DE_BASE_URL")',
        'or os.environ.get("ALGENTA_API_URL")',
        'raise RuntimeError(',
        'Use https://api.codna.ai only in Cloud Managed.',
        "Canonical key env var is `ALGENTA_API_KEY`. Legacy `DE_API_KEY` remains",
        "accepted for compatibility in the snippets above.",
        "Canonical base URL env var is `ALGENTA_BASE_URL`. Legacy `DE_BASE_URL` and",
        "`ALGENTA_API_URL` remain accepted for compatibility in the snippets above.",
    ),
}


@pytest.mark.parametrize(
    ("relative_path", "required_snippets"),
    list(_README_EXPECTATIONS.items()),
)
def test_example_readmes_call_out_private_profile_base_url_rules(
    relative_path: str,
    required_snippets: tuple[str, ...],
) -> None:
    text = (ROOT / relative_path).read_text()
    for snippet in required_snippets:
        assert snippet in text


def test_claude_desktop_readme_avoids_live_looking_key_literals() -> None:
    text = (ROOT / "examples" / "claude-desktop" / "README.md").read_text()

    assert "de_live_YOUR_KEY_HERE" not in text
    assert "de_test_YOUR_TEST_KEY" not in text
    assert "Header: Authorization: Bearer de_live_..." not in text
