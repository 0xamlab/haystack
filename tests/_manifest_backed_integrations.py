from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

MANIFEST_BACKED_INTEGRATIONS = tuple(
    json.loads(
        Path(__file__)
        .resolve()
        .with_name("manifest_backed_integrations.fixture.json")
        .read_text(encoding="utf-8")
    )
)
MANIFEST_BACKED_INTEGRATIONS_DISPLAY = ", ".join(
    str(entry["name"]) for entry in MANIFEST_BACKED_INTEGRATIONS
)
MANIFEST_BACKED_READ_ONLY_DISPLAY = ", ".join(
    str(entry["name"])
    for entry in MANIFEST_BACKED_INTEGRATIONS
    if entry.get("write_actions") == []
)

def _normalize_integration_value(value: Any) -> Any:
    if isinstance(value, (tuple, list)):
        return [_normalize_integration_value(item) for item in value]
    if isinstance(value, Mapping):
        return {key: _normalize_integration_value(item) for key, item in value.items()}
    return value


def _normalize_or_reuse_manifest_backed_integrations(
    integrations: Sequence[Any],
) -> list[dict[str, object]]:
    if (
        integrations is MANIFEST_BACKED_INTEGRATIONS
        or integrations is NORMALIZED_MANIFEST_BACKED_INTEGRATIONS
    ):
        return NORMALIZED_MANIFEST_BACKED_INTEGRATIONS
    return normalize_manifest_backed_integrations(integrations)


def assert_manifest_backed_integrations(integrations: Sequence[Any]) -> None:
    assert_manifest_backed_integrations_equal(
        integrations,
        NORMALIZED_MANIFEST_BACKED_INTEGRATIONS,
    )


def assert_manifest_backed_integrations_equal(
    integrations: Sequence[Any],
    expected_integrations: Sequence[Any],
) -> None:
    normalized_integrations = _normalize_or_reuse_manifest_backed_integrations(integrations)
    if expected_integrations is integrations:
        normalized_expected_integrations = normalized_integrations
    else:
        normalized_expected_integrations = _normalize_or_reuse_manifest_backed_integrations(
            expected_integrations
        )
    assert normalized_integrations == normalized_expected_integrations


def contract_integrations_match_manifest(integrations: Sequence[Any]) -> bool:
    try:
        return (
            _normalize_or_reuse_manifest_backed_integrations(integrations)
            == NORMALIZED_MANIFEST_BACKED_INTEGRATIONS
        )
    except (AssertionError, AttributeError, IndexError, KeyError, TypeError):
        return False


def normalize_manifest_backed_integrations(integrations: Sequence[Any]) -> list[dict[str, object]]:
    if not integrations:
        raise AssertionError("expected manifest-backed integrations")
    fields = tuple(MANIFEST_BACKED_INTEGRATIONS[0].keys())
    return [
        {
            field: _normalize_integration_value(
                integration[field] if isinstance(integration, Mapping) else getattr(integration, field)
            )
            for field in fields
        }
        for integration in integrations
    ]


NORMALIZED_MANIFEST_BACKED_INTEGRATIONS = normalize_manifest_backed_integrations(
    MANIFEST_BACKED_INTEGRATIONS
)


def assert_manifest_backed_integration_texts_equal(
    left_text: str,
    right_text: str,
) -> None:
    left_match = re.search(
        r"(?:export const INTEGRATIONS =|exports\.INTEGRATIONS =)\s*(\[[\s\S]*?\]);",
        left_text,
    )
    if left_match is None:
        raise AssertionError("missing exported INTEGRATIONS array")
    left_integrations = json.loads(left_match.group(1))
    assert_manifest_backed_integrations(left_integrations)
    if right_text == left_text:
        return
    right_match = re.search(
        r"(?:export const INTEGRATIONS =|exports\.INTEGRATIONS =)\s*(\[[\s\S]*?\]);",
        right_text,
    )
    if right_match is None:
        raise AssertionError("missing exported INTEGRATIONS array")
    right_integrations = json.loads(right_match.group(1))
    assert_manifest_backed_integrations_equal(left_integrations, right_integrations)
