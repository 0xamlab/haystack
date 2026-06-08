from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _python_package_diffs(source_root: str, artifact_root: str) -> list[str]:
    source_base = ROOT / source_root
    artifact_base = ROOT / artifact_root
    diffs: list[str] = []

    source_files = {path.relative_to(source_base) for path in source_base.rglob("*.py")}
    artifact_files = {path.relative_to(artifact_base) for path in artifact_base.rglob("*.py")}

    missing_from_artifact = sorted(source_files - artifact_files)
    extra_in_artifact = sorted(artifact_files - source_files)
    for relative_path in missing_from_artifact:
        diffs.append(f"missing artifact file: {relative_path}")
    for relative_path in extra_in_artifact:
        diffs.append(f"extra artifact file: {relative_path}")

    for relative_path in sorted(source_files & artifact_files):
        source_text = (source_base / relative_path).read_text()
        artifact_text = (artifact_base / relative_path).read_text()
        if source_text != artifact_text:
            diffs.append(f"content drift: {relative_path}")

    return diffs


def test_python_sdk_build_artifacts_match_source_package_surfaces() -> None:
    assert _python_package_diffs(
        "packages/python-sdk/decision_engine",
        "packages/python-sdk/build/lib/decision_engine",
    ) == []


def test_algenta_core_build_artifacts_match_source_package_surfaces() -> None:
    assert _python_package_diffs(
        "packages/algenta-core/algenta",
        "packages/algenta-core/build/lib/algenta",
    ) == []
