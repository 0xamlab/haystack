"""Tests for repository_intelligence_service: repository_analysis.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_analysis_resolves_typescript_relative_and_workspace_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        json.dumps({"name": "@acme/common"}),
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "util.ts").write_text(
        "export const helper = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "packages" / "common" / "src" / "shared.ts").write_text(
        "export const shared = (): string => 'shared';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { helper } from './util';\n"
        "import { shared } from '@acme/common/shared';\n"
        "export const run = (): string => `${helper()}-${shared()}`;\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "services/app/src/main.ts",
            "services/app/src/util.ts",
            "packages/common/src/shared.ts",
        ]
    )
    workspace_package_index = repository_service._build_workspace_package_index(repo_path)
    analysis = repository_service._analyze_file(
        root_path=repo_path,
        path=repo_path / "services" / "app" / "src" / "main.ts",
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        max_file_size_bytes=100_000,
    )

    resolved_targets = {dependency.target_file for dependency in analysis.dependencies}
    assert "services/app/src/util.ts" in resolved_targets
    assert "packages/common/src/shared.ts" in resolved_targets


def test_repository_analysis_resolves_typescript_tsconfig_path_aliases(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tsconfig-alias-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "tsconfig.json").write_text(
        '{\n'
        '  "compilerOptions": {\n'
        '    "baseUrl": ".",\n'
        '    "paths": {\n'
        '      "@/*": ["./src/*"]\n'
        "    }\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "lib" / "utils.ts").write_text(
        "export const helper = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.ts").write_text(
        "import { helper } from '@/lib/utils';\n"
        "export const run = (): string => helper();\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        [
            "src/main.ts",
            "src/lib/utils.ts",
        ],
        root_path=repo_path,
    )
    analysis = repository_service._analyze_file(
        root_path=repo_path,
        path=repo_path / "src" / "main.ts",
        module_index=module_index,
        workspace_package_index={},
        max_file_size_bytes=100_000,
    )

    resolved_targets = {dependency.target_file for dependency in analysis.dependencies}
    assert "src/lib/utils.ts" in resolved_targets


def test_repository_analysis_extracts_nested_typescript_symbol_hierarchy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "nested-symbol-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    target_path = repo_path / "services" / "app" / "src" / "main.ts"
    target_path.write_text(
        "export class Planner {\n"
        "  private readonly onEvent = async (): Promise<string> => {\n"
        "    function normalize(value: string): string {\n"
        "      return value.trim();\n"
        "    }\n"
        "    return normalize('ok');\n"
        "  };\n"
        "\n"
        "  build(): string {\n"
        "    function finalize(value: string): string {\n"
        "      return value.toUpperCase();\n"
        "    }\n"
        "    return finalize('ok');\n"
        "  }\n"
        "}\n"
        "\n"
        "export const run = (): string => {\n"
        "  class Inner {\n"
        "    execute(): string {\n"
        "      return 'done';\n"
        "    }\n"
        "  }\n"
        "  return new Inner().execute();\n"
        "};\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(["services/app/src/main.ts"])
    analysis = repository_service._analyze_file(
        root_path=repo_path,
        path=target_path,
        module_index=module_index,
        workspace_package_index={},
        max_file_size_bytes=100_000,
    )

    symbols_by_name = {symbol.symbol_name: symbol for symbol in analysis.symbols}
    assert symbols_by_name["Planner"].parent_symbol_id is None
    assert symbols_by_name["onEvent"].parent_symbol_id == symbols_by_name["Planner"].symbol_id
    assert symbols_by_name["normalize"].parent_symbol_id == symbols_by_name["onEvent"].symbol_id
    assert symbols_by_name["build"].parent_symbol_id == symbols_by_name["Planner"].symbol_id
    assert symbols_by_name["finalize"].parent_symbol_id == symbols_by_name["build"].symbol_id
    assert symbols_by_name["run"].parent_symbol_id is None
    assert symbols_by_name["Inner"].parent_symbol_id == symbols_by_name["run"].symbol_id
    assert symbols_by_name["execute"].parent_symbol_id == symbols_by_name["Inner"].symbol_id


