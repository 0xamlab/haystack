from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_wgsl_parser_dispatch as repository_wgsl_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    wgsl_analysis_support as repository_wgsl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    wgsl_primitives as repository_wgsl_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def _connector_for_repo(repo_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )


def _init_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Repo Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-qm", "Initial commit"], check=True)


def test_repository_intelligence_wgsl_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["wgsl"] is (
        repository_wgsl_parser_dispatch._parse_wgsl_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["wgsl"] is (
        repository_wgsl_parser_dispatch._parse_wgsl_dependencies_only
    )


def test_repository_intelligence_wgsl_helpers_are_modularized() -> None:
    assert repository_service.wgsl_adapter.strip_comments is (
        repository_wgsl_primitives.strip_comments
    )
    assert repository_service.wgsl_adapter.has_wgsl_path_hints is (
        repository_wgsl_primitives.has_wgsl_path_hints
    )
    assert repository_service.wgsl_adapter.iter_symbol_entries is (
        repository_wgsl_primitives.iter_symbol_entries
    )
    assert repository_service.wgsl_adapter.iter_function_call_names is (
        repository_wgsl_primitives.iter_function_call_names
    )
    assert repository_service.wgsl_adapter.parse_include_statements is (
        repository_wgsl_primitives.parse_include_statements
    )
    assert repository_service.wgsl_adapter.parse_import_statements is (
        repository_wgsl_primitives.parse_import_statements
    )
    assert repository_service.wgsl_adapter.is_probable_wgsl_source is (
        repository_wgsl_analysis_support.is_probable_wgsl_source
    )
    assert repository_service.wgsl_adapter.module_aliases_for_path is (
        repository_wgsl_analysis_support.module_aliases_for_path
    )
    assert repository_service.wgsl_adapter.parse_dependencies_only is (
        repository_wgsl_analysis_support.parse_dependencies_only
    )
    assert repository_service.wgsl_adapter.parse_file is (
        repository_wgsl_analysis_support.parse_file
    )


def test_wgsl_adapter_module_aliases_include_file_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "wgsl-alias-repo"
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "shaders" / "noise.wgsl").write_text(
        "struct NoiseConfig {\n"
        "  scale: f32,\n"
        "}\n"
        "fn NoiseValue() -> f32 {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.wgsl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="shaders/noise.wgsl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "shaders/noise.wgsl" in aliases
    assert "shaders/noise" in aliases
    assert "noise" in aliases
    assert "NoiseConfig" in aliases
    assert "NoiseValue" in aliases


def test_wgsl_adapter_parse_file_resolves_includes_and_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "wgsl-parse-repo"
    (repo_path / "shaders" / "lib").mkdir(parents=True)
    (repo_path / "shaders" / "lib" / "noise.wgsl").write_text(
        "fn NoiseValue() -> f32 {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "shaders" / "main.wgsl").write_text(
        '#include "lib/noise.wgsl"\n'
        "@fragment\n"
        "fn fs_main() -> vec4f {\n"
        "  return vec4f(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["shaders/main.wgsl", "shaders/lib/noise.wgsl"],
        root_path=repo_path,
    )
    text = (repo_path / "shaders" / "main.wgsl").read_text(encoding="utf-8")

    dependencies = repository_service.wgsl_adapter.parse_dependencies_only(
        "shaders/main.wgsl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.wgsl_adapter.parse_file(
        "shaders/main.wgsl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "shaders/lib/noise.wgsl" for dependency in dependencies)
    assert any(symbol.symbol_name == "fs_main" for symbol in symbols)
    assert any(
        reference.target_file == "shaders/lib/noise.wgsl"
        and "NoiseValue" in reference.target_names
        for reference in references
    )


def test_wgsl_language_detection_supports_wgsl_files() -> None:
    assert repository_service._language_for_path(
        Path("shaders/main.wgsl"),
        text="@fragment\nfn fs_main() -> vec4f { return vec4f(); }\n",
    ) == "wgsl"


def test_operational_seed_plan_without_diagnostics_promotes_wgsl_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "wgsl-profile-repo"
    (repo_path / "shaders" / "lib").mkdir(parents=True)
    (repo_path / "shaders" / "lib" / "noise.wgsl").write_text(
        "fn NoiseValue() -> f32 {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "shaders" / "main.wgsl").write_text(
        '#include "lib/noise.wgsl"\n'
        "@fragment\n"
        "fn fs_main() -> vec4f {\n"
        "  return vec4f(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "app.ts").write_text(
        "export const ready = true;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "wgsl" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "wgsl"
    assert "shaders/main.wgsl" in seed_plan["entrypoint_files"]
    assert "shaders/lib" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_does_not_force_wgsl_first_in_rust_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "wgsl-mixed-rust-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "Cargo.toml").write_text(
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    (repo_path / "shaders" / "main.wgsl").write_text(
        "@compute @workgroup_size(1)\n"
        "fn cs_main() {\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.rs").write_text(
        "mod module_0;\nfn main() { module_0::run_0(); }\n",
        encoding="utf-8",
    )
    for index in range(10):
        (repo_path / "src" / f"module_{index}.rs").write_text(
            f"pub fn run_{index}() {{}}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "wgsl" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "wgsl"
    assert "rust" in seed_plan["operational_ecosystems"]
