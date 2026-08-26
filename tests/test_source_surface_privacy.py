from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Path fragments that mark a *build output* rather than a checked-in surface.
_GENERATED_MARKERS = ("/build/lib/", "/dist/")


def _read_surface(relative_path: str) -> str:
    """Read a surface under test, distinguishing build outputs from source.

    Several parametrized paths point at build outputs. ``packages/python-sdk/build``
    happens to be committed, but ``packages/algenta/build`` and
    ``packages/ts-sdk/dist`` are not, so those assertions are vacuous in a fresh
    clone and used to raise ``FileNotFoundError`` instead of asserting anything.
    An absent build output is skipped -- there is no distribution to make a claim
    about. An absent *source* path stays a hard failure: that means a real surface
    was moved or deleted and this test's path list went stale with it.
    """
    path = ROOT / relative_path
    if not path.exists():
        if any(marker in f"/{relative_path}" for marker in _GENERATED_MARKERS):
            pytest.skip(f"{relative_path} is a build output not present in this tree")
        raise AssertionError(
            f"{relative_path} is a source surface guarded by this test, but it does not exist"
        )
    return path.read_text()


_SOURCE_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "packages/python-sdk/decision_engine/__init__.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/python-sdk/decision_engine/client_facade/__init__.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/python-sdk/decision_engine/client.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/python-sdk/decision_engine/async_client_facade/__init__.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/python-sdk/decision_engine/async_client.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/algenta/algenta/client/__init__.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
        "explicit self-hosted `base_url`",
    ),
    "packages/algenta/algenta/__init__.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
        "explicit self-hosted `base_url`",
    ),
    "packages/algenta/algenta/runtime.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
        "explicit self-hosted `base_url`",
    ),
    "packages/algenta/algenta/decision.py": (
        "Cloud Managed path",
        "`self_hosted`",
        "`air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/algenta/algenta/forecast.py": (
        "Cloud Managed path",
        "`self_hosted`",
        "`air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/algenta/algenta/simple.py": (
        "Cloud Managed path",
        "`self_hosted`",
        "`air_gapped`",
        "self-hosted operator",
        "fail closed",
    ),
    "packages/algenta/algenta/simulate.py": (
        "Cloud Managed path",
        "`self_hosted`",
        "`air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/ts-sdk/src/_client_class.ts": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "apps/mcp_server/server.py": (
        "Cloud Managed",
        "self-hosted operator deployment",
        "fail closed",
        "do not silently fall back",
        "ALGENTA_API_KEY /",
        "DE_API_KEY",
        "ALGENTA_BASE_URL /",
        "DE_BASE_URL",
        "ALGENTA_API_URL",
    ),
    "apps/runtime/sdk.py": (
        "Cloud Managed example",
        "`self_hosted` and `air_gapped`",
        "ALGENTA_API_KEY / DE_API_KEY",
        "ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL",
        "fail closed",
        "<YOUR_ALGENTA_API_KEY>",
    ),
    "apps/cli/main/__init__.py": (
        "Cloud Managed example",
        "`self_hosted` and",
        "self-hosted operator",
        "fail closed",
        "<YOUR_ALGENTA_API_KEY>",
    ),
    "apps/cli/main/_cmd_auth_daemon_bench.py": (
        "<YOUR_LEGACY_DECISION_ENGINE_API_KEY>",
    ),
    "packages/algenta/algenta/cli.py": (
        "Cloud Managed path",
        "`self_hosted` and",
        "self-hosted operator",
    ),
    "packages/algenta/algenta/demo.py": (
        "Cloud Managed example",
        "self_hosted/air_gapped",
        "self-hosted origin",
    ),
    "examples/langgraph/decision_tool.py": (
        "Cloud Managed example",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/python-sdk/build/lib/decision_engine/__init__.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/python-sdk/build/lib/decision_engine/client_facade.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
        "explicit self-hosted `base_url`",
    ),
    "packages/python-sdk/build/lib/decision_engine/client.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/python-sdk/build/lib/decision_engine/async_client_facade.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/python-sdk/build/lib/decision_engine/async_client.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/algenta/build/lib/algenta/client.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
        "explicit self-hosted `base_url`",
    ),
    "packages/algenta/build/lib/algenta/__init__.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
        "explicit self-hosted `base_url`",
    ),
    "packages/algenta/build/lib/algenta/runtime.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
        "explicit self-hosted `base_url`",
    ),
    "packages/algenta/build/lib/algenta/decision.py": (
        "Cloud Managed path",
        "`self_hosted`",
        "`air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/algenta/build/lib/algenta/forecast.py": (
        "Cloud Managed path",
        "`self_hosted`",
        "`air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/algenta/build/lib/algenta/simple.py": (
        "Cloud Managed path",
        "`self_hosted`",
        "`air_gapped`",
        "self-hosted operator",
        "fail closed",
    ),
    "packages/algenta/build/lib/algenta/simulate.py": (
        "Cloud Managed path",
        "`self_hosted`",
        "`air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
    "packages/algenta/build/lib/algenta/cli.py": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator",
        "fail closed",
    ),
    "packages/algenta/build/lib/algenta/demo.py": (
        "Cloud Managed example",
        "self_hosted/air_gapped",
        "self-hosted origin",
    ),
    # NOTE: dist/_client_class.js is excluded because TSC strips JSDoc
    # comments from .js output by default; the .d.ts file preserves them.
    "packages/ts-sdk/dist/_client_class.d.ts": (
        "Cloud Managed path",
        "`self_hosted` and `air_gapped`",
        "self-hosted operator deployment",
        "fail closed",
    ),
}


@pytest.mark.parametrize(
    ("relative_path", "required_snippets"),
    list(_SOURCE_EXPECTATIONS.items()),
)
def test_user_visible_source_surfaces_call_out_private_profile_boundaries(
    relative_path: str,
    required_snippets: tuple[str, ...],
) -> None:
    text = _read_surface(relative_path)
    for snippet in required_snippets:
        assert snippet in text


@pytest.mark.parametrize(
    ("relative_path", "forbidden_snippet"),
    [
        (
            "packages/algenta/build/lib/algenta/client.py",
            "https://algenta.ai/dashboard/api-keys",
        ),
    ],
)
def test_distribution_surfaces_do_not_keep_stale_hosted_only_key_links(
    relative_path: str,
    forbidden_snippet: str,
) -> None:
    text = _read_surface(relative_path)
    assert forbidden_snippet not in text


@pytest.mark.parametrize(
    "relative_path",
    [
        "packages/python-sdk/decision_engine/__init__.py",
        "packages/python-sdk/decision_engine/client_facade/__init__.py",
        "packages/python-sdk/decision_engine/async_client_facade/__init__.py",
        "packages/algenta/algenta/client/__init__.py",
        "packages/algenta/algenta/decision.py",
        "packages/algenta/algenta/forecast.py",
        "packages/algenta/algenta/simulate.py",
        "packages/algenta/algenta/cli.py",
        "packages/algenta/algenta/demo.py",
        "packages/python-sdk/build/lib/decision_engine/__init__.py",
        "packages/python-sdk/build/lib/decision_engine/client_facade.py",
        "packages/python-sdk/build/lib/decision_engine/async_client_facade.py",
        "packages/algenta/build/lib/algenta/client.py",
        "packages/algenta/build/lib/algenta/decision.py",
        "packages/algenta/build/lib/algenta/forecast.py",
        "packages/algenta/build/lib/algenta/simulate.py",
        "packages/algenta/build/lib/algenta/cli.py",
        "packages/algenta/build/lib/algenta/demo.py",
        "packages/ts-sdk/src/_client_class.ts",
        "packages/ts-sdk/dist/_client_class.js",
        "packages/ts-sdk/dist/_client_class.d.ts",
        "apps/runtime/sdk.py",
        "apps/cli/main/__init__.py",
    ],
)
def test_user_visible_source_surfaces_avoid_live_looking_key_literals(
    relative_path: str,
) -> None:
    text = _read_surface(relative_path)
    assert "de_live_..." not in text
    assert "api_key='de_live_...'" not in text
    assert 'api_key="de_live_..."' not in text


@pytest.mark.parametrize(
    ("relative_path", "required_snippet"),
    [
        ("apps/runtime/license.py", '"api_key_prefix": "<API_KEY_PREFIX>"'),
        ("apps/runtime/metering.py", '"api_key_prefix": "<API_KEY_PREFIX>"'),
        ("apps/api-server/services/auth_service.py", "first 12 chars of the full raw key"),
    ],
)
def test_internal_auth_surfaces_use_neutral_key_prefix_examples(
    relative_path: str,
    required_snippet: str,
) -> None:
    text = _read_surface(relative_path)
    assert required_snippet in text
    assert "de_live_d36l" not in text
    assert 'de_live_ab12' not in text
