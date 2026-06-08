"""Tests for test_runtime_surface_compatibility: all_standalone.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-4/tests/test_runtime_surface_compatibility.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_surface_compatibility_helpers import *  # noqa: F401,F403


def test_all_standalone_integration_scripts_emit_summary_artifacts() -> None:
    integration_root = ROOT / "tests" / "integration"
    missing_suite_name: list[str] = []
    missing_write: list[str] = []
    missing_print: list[str] = []
    missing_progress: list[str] = []

    for path in sorted(integration_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "Standalone integration script; run via python" not in text:
            continue
        if "SUITE_NAME =" not in text:
            missing_suite_name.append(path.name)
        if "write_live_integration_summary(" not in text and "write_live_summary_artifact(" not in text:
            missing_write.append(path.name)
        if "Summary artifact:" not in text:
            missing_print.append(path.name)
        if '_emit(f"  ... {name}")' not in text and 'print(f"  ... {name}", flush=True)' not in text:
            missing_progress.append(path.name)

    assert not missing_suite_name, f"Standalone integration scripts missing suite names: {missing_suite_name}"
    assert not missing_write, f"Standalone integration scripts missing summary writers: {missing_write}"
    assert not missing_print, f"Standalone integration scripts missing summary artifact output: {missing_print}"
    assert not missing_progress, (
        f"Standalone integration scripts missing visible per-check progress output: {missing_progress}"
    )


def test_all_standalone_integration_scripts_register_suite_names_in_the_correct_artifact_registry() -> None:
    integration_root = ROOT / "tests" / "integration"
    integration_registry = (integration_root / "live_integration_artifacts.py").read_text(
        encoding="utf-8"
    )
    rollout_registry = (ROOT / "benchmarks" / "llm_rollout_live_artifacts.py").read_text(
        encoding="utf-8"
    )
    missing_registration: list[str] = []

    for path in sorted(integration_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "Standalone integration script; run via python" not in text:
            continue
        match = re.search(r'^SUITE_NAME\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if match is None:
            missing_registration.append(f"{path.name}: missing SUITE_NAME")
            continue

        suite_name = match.group(1)
        registry_text = (
            rollout_registry if "write_live_summary_artifact(" in text else integration_registry
        )
        registry_name = (
            "benchmarks/llm_rollout_live_artifacts.py"
            if "write_live_summary_artifact(" in text
            else "tests/integration/live_integration_artifacts.py"
        )
        if f'"{suite_name}"' not in registry_text:
            missing_registration.append(f"{path.name}: {suite_name} missing from {registry_name}")

    assert not missing_registration, (
        "Standalone integration scripts missing artifact registry entries: "
        f"{missing_registration}"
    )


def test_all_standalone_integration_scripts_bind_summary_writers_to_suite_name() -> None:
    integration_root = ROOT / "tests" / "integration"
    missing_suite_binding: list[str] = []

    for path in sorted(integration_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "Standalone integration script; run via python" not in text:
            continue

        uses_integration_writer = "write_live_integration_summary(" in text
        uses_rollout_writer = "write_live_summary_artifact(" in text

        if uses_integration_writer and (
            re.search(r"write_live_integration_summary\(\s*SUITE_NAME\s*,", text) is None
            and "name=SUITE_NAME" not in text
        ):
            missing_suite_binding.append(
                f"{path.name}: write_live_integration_summary not bound to SUITE_NAME"
            )

        if uses_rollout_writer and "suite_name=SUITE_NAME" not in text:
            missing_suite_binding.append(
                f"{path.name}: write_live_summary_artifact not bound to SUITE_NAME"
            )

    assert not missing_suite_binding, (
        "Standalone integration scripts missing SUITE_NAME summary-writer bindings: "
        f"{missing_suite_binding}"
    )


def test_all_standalone_integration_scripts_bind_summary_writers_to_own_script_path() -> None:
    integration_root = ROOT / "tests" / "integration"
    missing_script_binding: list[str] = []

    for path in sorted(integration_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "Standalone integration script; run via python" not in text:
            continue

        expected_script = f"tests/integration/{path.name}"

        if "write_live_integration_summary(" in text:
            match = re.search(
                r'write_live_integration_summary\(.*?script="([^"]+)"',
                text,
                re.DOTALL,
            )
            if match is None or match.group(1) != expected_script:
                missing_script_binding.append(
                    f"{path.name}: write_live_integration_summary script != {expected_script}"
                )

        if "write_live_summary_artifact(" in text:
            match = re.search(
                r'write_live_summary_artifact\(.*?script="([^"]+)"',
                text,
                re.DOTALL,
            )
            if match is None or match.group(1) != expected_script:
                missing_script_binding.append(
                    f"{path.name}: write_live_summary_artifact script != {expected_script}"
                )

    assert not missing_script_binding, (
        "Standalone integration scripts missing exact script-path summary bindings: "
        f"{missing_script_binding}"
    )


def test_all_standalone_integration_scripts_with_skip_lanes_write_skipped_counts_to_summary() -> None:
    integration_root = ROOT / "tests" / "integration"
    missing_skipped_binding: list[str] = []

    for path in sorted(integration_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "Standalone integration script; run via python" not in text:
            continue
        if "write_live_integration_summary(" not in text:
            continue
        if "SKIP" not in text:
            continue
        if re.search(r"write_live_integration_summary\(.*?skipped=", text, re.DOTALL) is None:
            missing_skipped_binding.append(
                f"{path.name}: write_live_integration_summary missing skipped= binding"
            )

    assert not missing_skipped_binding, (
        "Standalone integration scripts with skip lanes missing skipped summary bindings: "
        f"{missing_skipped_binding}"
    )


