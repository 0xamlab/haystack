from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_SOURCE_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "examples/langgraph/decision_tool.py": (
        "Cloud Managed example",
        "<YOUR_ALGENTA_API_KEY>",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "Private profiles fail closed",
        "silently fall back to Algenta cloud.",
    ),
    "examples/langgraph/capability_router.py": (
        "Cloud Managed example",
        "<YOUR_ALGENTA_API_KEY>",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "Private profiles fail closed",
        "silently fall back to Algenta cloud.",
    ),
    "examples/multi-hop/python_public_client_flow.py": (
        "Cloud Managed public-client path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail",
        "do not silently fall back",
        "ALGENTA_API_URL",
    ),
    "examples/multi-hop/typescript_public_client_flow.ts": (
        "Cloud Managed public-client path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail",
        "do not silently fall back",
        "ALGENTA_API_URL",
    ),
    "examples/shared/privacy_profile.py": (
        "Cloud Managed base URL",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail",
        "do not silently fall back",
        "ALGENTA_API_URL",
    ),
    "examples/shared/privacyProfile.ts": (
        "Cloud Managed base URL",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail",
        "do not silently fall back",
        "ALGENTA_BASE_URL / DE_BASE_URL",
        "ALGENTA_API_URL",
    ),
    "examples/multi-hop/python_runtime_library_flow.py": (
        "local runtime-library path",
        "local daemon",
        "self-hosted operator deployment",
        "`self_hosted` and `air_gapped`",
        "does not silently fall back",
        "ALGENTA_API_URL",
    ),
    "examples/multi-hop/typescript_runtime_library_flow.ts": (
        "local runtime-library path",
        "local daemon",
        "self-hosted operator deployment",
        "`self_hosted` and `air_gapped`",
        "does not silently fall back",
        "ALGENTA_BASE_URL` / `DE_BASE_URL` / `ALGENTA_API_URL`",
        "`ALGENTA_API_KEY` / `DE_API_KEY`",
    ),
}


@pytest.mark.parametrize(
    ("relative_path", "required_snippets"),
    list(_SOURCE_EXPECTATIONS.items()),
)
def test_example_source_surfaces_call_out_private_profile_boundaries(
    relative_path: str,
    required_snippets: tuple[str, ...],
) -> None:
    text = (ROOT / relative_path).read_text()
    for snippet in required_snippets:
        assert snippet in text
    assert "de_live_..." not in text
