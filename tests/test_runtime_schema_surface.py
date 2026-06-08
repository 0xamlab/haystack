from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"

for path in (str(ROOT), str(PYTHON_SDK)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _is_name_or_attr(node: ast.AST, name: str) -> bool:
    return (isinstance(node, ast.Name) and node.id == name) or (
        isinstance(node, ast.Attribute) and node.attr == name
    )


def _subscript_elements(node: ast.Subscript) -> list[ast.AST]:
    if isinstance(node.slice, ast.Tuple):
        return list(node.slice.elts)
    return [node.slice]


def _is_list_annotation(node: ast.AST) -> bool:
    if not isinstance(node, ast.Subscript):
        return False
    if _is_name_or_attr(node.value, "Annotated"):
        elements = _subscript_elements(node)
        return bool(elements) and _is_list_annotation(elements[0])
    return _is_name_or_attr(node.value, "list") or _is_name_or_attr(node.value, "List")


def _annotation_uses_list_strict_metadata(node: ast.AST) -> bool:
    if not isinstance(node, ast.Subscript) or not _is_name_or_attr(node.value, "Annotated"):
        return False
    elements = _subscript_elements(node)
    if not elements or not _is_list_annotation(elements[0]):
        return False
    return any(
        isinstance(metadata, ast.Call) and _is_name_or_attr(metadata.func, "Strict")
        or _is_name_or_attr(metadata, "Strict")
        for metadata in elements[1:]
    )


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


def _strict_list_field_offenders(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        if _annotation_uses_list_strict_metadata(node.annotation):
            offenders.append(f"{_display_path(path)}:{node.lineno}:{node.target.id}")
            continue
        if not isinstance(node.value, ast.Call):
            continue
        if not _is_name_or_attr(node.value.func, "Field"):
            continue
        if not _is_list_annotation(node.annotation):
            continue
        if any(
            keyword.arg == "strict"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.value.keywords
        ):
            offenders.append(f"{_display_path(path)}:{node.lineno}:{node.target.id}")

    return offenders


def test_runtime_models_do_not_apply_strict_constraints_to_list_fields() -> None:
    offenders: list[str] = []
    # Both apps/runtime_manifest and decision_engine.models_runtime_manifest
    # are now packages (the files were modularized); scan every submodule.
    apps_runtime_files = sorted((ROOT / "apps" / "runtime_manifest").glob("*.py"))
    sdk_manifest_files = sorted(
        (ROOT / "packages" / "python-sdk" / "decision_engine" / "models_runtime_manifest").glob("*.py")
    )
    paths_to_scan = list(apps_runtime_files) + list(sdk_manifest_files)
    for path in paths_to_scan:
        offenders.extend(_strict_list_field_offenders(path))

    assert offenders == [], "invalid strict list field constraints found:\n" + "\n".join(
        offenders
    )


def test_runtime_schema_guard_detects_annotated_strict_list_metadata(tmp_path: Path) -> None:
    path = tmp_path / "runtime_strict_list_offender.py"
    path.write_text(
        "from typing import Annotated\n"
        "from pydantic import Strict\n\n"
        "modules: Annotated[list[str], Strict()]\n",
        encoding="utf-8",
    )

    offenders = _strict_list_field_offenders(path)

    assert offenders == [f"{path.name}:4:modules"]


def test_runtime_response_models_build_json_schema() -> None:
    producer_runtime_manifest_models = importlib.import_module("apps.runtime_manifest")
    decision_engine_manifest_models = importlib.import_module(
        "decision_engine.models_runtime_manifest"
    )

    producer_classes = (
        producer_runtime_manifest_models.RuntimeManifestResponse,
        producer_runtime_manifest_models.RuntimeAdminModulesResponse,
        producer_runtime_manifest_models.RuntimeAdminBenchmarksResponse,
        producer_runtime_manifest_models.RuntimeReleaseValidationResponse,
    )
    sdk_classes = (
        decision_engine_manifest_models.RuntimeManifestResult,
        decision_engine_manifest_models.RuntimeAdminModulesResult,
        decision_engine_manifest_models.RuntimeAdminBenchmarksResult,
        decision_engine_manifest_models.RuntimeReleaseValidationResult,
    )

    for model_cls in (*producer_classes, *sdk_classes):
        schema = model_cls.model_json_schema()
        assert schema["type"] == "object"
        assert schema["properties"]
