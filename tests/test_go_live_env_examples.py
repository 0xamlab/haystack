from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "tests" / "integration" / "connector_validation_catalog.py"
FIVETRAN_PATH = ROOT / "tests" / "go_live_fivetran_verify.py"
ROOT_ENV_EXAMPLE = ROOT / ".env.example"
GO_LIVE_ENV_EXAMPLE = ROOT / "tests" / "integration" / "go_live_validation.env.example"
GO_LIVE_VERIFY_SUMMARY = ROOT / "build" / "go_live_verify_summary.json"


def _extract_de_test_names(text: str) -> set[str]:
    return set(re.findall(r"\bDE_TEST_[A-Z0-9_]+\b", text))


def _extract_env_assignment_names(text: str) -> set[str]:
    return {match.group(1) for match in re.finditer(r"(?m)^([A-Z0-9_]+)=", text)}


def _extract_current_gap_env_names() -> set[str]:
    payload = json.loads(GO_LIVE_VERIFY_SUMMARY.read_text(encoding="utf-8"))
    gap_env_summary = payload.get("gap_env_summary") or {}
    return set((gap_env_summary.get("env_case_ids") or {}).keys())


def test_root_env_example_covers_all_catalog_de_test_env_names() -> None:
    catalog_env_names = _extract_de_test_names(
        CATALOG_PATH.read_text(encoding="utf-8")
    ) | _extract_de_test_names(FIVETRAN_PATH.read_text(encoding="utf-8"))
    template_env_names = _extract_env_assignment_names(ROOT_ENV_EXAMPLE.read_text(encoding="utf-8"))

    missing = sorted(catalog_env_names - template_env_names)
    assert missing == []


def test_go_live_env_example_covers_all_catalog_de_test_env_names() -> None:
    catalog_env_names = _extract_de_test_names(
        CATALOG_PATH.read_text(encoding="utf-8")
    ) | _extract_de_test_names(FIVETRAN_PATH.read_text(encoding="utf-8"))
    template_env_names = _extract_env_assignment_names(
        GO_LIVE_ENV_EXAMPLE.read_text(encoding="utf-8")
    )

    missing = sorted(catalog_env_names - template_env_names)
    assert missing == []


def test_root_env_example_covers_all_current_gap_env_names() -> None:
    gap_env_names = _extract_current_gap_env_names()
    template_env_names = _extract_env_assignment_names(ROOT_ENV_EXAMPLE.read_text(encoding="utf-8"))

    missing = sorted(gap_env_names - template_env_names)
    assert missing == []


def test_go_live_env_example_covers_all_current_gap_env_names() -> None:
    gap_env_names = _extract_current_gap_env_names()
    template_env_names = _extract_env_assignment_names(
        GO_LIVE_ENV_EXAMPLE.read_text(encoding="utf-8")
    )

    missing = sorted(gap_env_names - template_env_names)
    assert missing == []
