from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import benchmarks.repository_intelligence_real_repo_probe as probe_module
from apps.api_server.schemas.repositories import (
    RepositoryDiagnostic,
    RepositorySnapshotCreateRequest,
)
from apps.api_server.schemas.response import (
    DecisionEnvelope,
    MetricsSummary,
    PercentileSummary,
    RunMetadata,
)
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_language_priority import (
    REPOSITORY_LANGUAGE_POPULARITY_ORDER,
    sort_repository_languages,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _build_connected_dependency_map,
    _candidate_config_focus_paths,
    _candidate_existing_leaf_roots,
    _candidate_repository_file_paths,
    _candidate_solutions,
    _connected_map_candidate_file_limit,
    _derive_operational_seed_paths_without_diagnostics,
    _derive_operational_seed_plan_without_diagnostics,
    _effective_focus_paths_for_snapshot,
    _focus_paths_from_diagnostics,
    _load_snapshot_graph_summary,
    _repo_profile_candidate_paths,
    _repo_profile_config_paths,
    _resolve_diagnostic_base_path,
    _resolve_diagnostic_project_path,
    _should_group_focus_path_scan,
    _should_use_seeded_profile_candidate_scan,
    _store_probe_prepass_cache,
    _support_roots_need_expansion,
    _support_roots_requiring_expansion,
    parse_repository_diagnostics,
    run_probe,
)


def _probe_envelope() -> DecisionEnvelope:
    return DecisionEnvelope(
        run_id="00000000-0000-0000-0000-000000000001",
        engine_version="2026.05.0",
        recommended_action="apply_patch",
        confidence=0.93,
        rationale="Patch simulation satisfies the current execution policy.",
        metrics=MetricsSummary(
            expected_value=91.0,
            median=88.0,
            std_deviation=7.0,
            variance=49.0,
            probability_of_loss=0.05,
            var_95=6.0,
            cvar_95=9.0,
        ),
        percentiles=PercentileSummary(
            p5=-6.0,
            p25=72.0,
            p50=88.0,
            p75=97.0,
            p95=111.0,
        ),
        scenarios_run=5000,
        execution_ms=9,
        metadata=RunMetadata(
            mode="expert",
            seed=42,
            billing_units=1,
            engine_version="2026.05.0",
        ),
    )


def _init_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Repo Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-m", "Initial commit"], check=True)


def _typescript_rootdir_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "probe-rootdir-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        '{"name":"@acme/common"}\n',
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "index.ts").write_text(
        "import { shared } from '@acme/common/shared';\n"
        "export const run = (): string => shared();\n",
        encoding="utf-8",
    )
    (repo_path / "packages" / "common" / "src" / "shared.ts").write_text(
        "export function shared(): string {\n"
        "  return 'shared';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "tsconfig.json").write_text(
        '{\n'
        '  "compilerOptions": { "outDir": "dist", "rootDir": "../.." },\n'
        '  "include": ["src"]\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "tsconfig.test.json").write_text(
        '{\n'
        '  "extends": "./tsconfig.json",\n'
        '  "compilerOptions": {\n'
        '    "noEmit": true,\n'
        '    "rootDir": ".",\n'
        '    "baseUrl": ".",\n'
        '    "paths": {\n'
        '      "@acme/common": ["../../packages/common/src/index.ts"],\n'
        '      "@acme/common/*": ["../../packages/common/src/*"]\n'
        "    }\n"
        "  },\n"
        '  "include": ["src"]\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "diagnostics.txt").write_text(
        "../../packages/common/src/shared.ts(1,1): error TS6059: File is not under 'rootDir'.\n",
        encoding="utf-8",
    )
    return repo_path


def test_parse_repository_diagnostics_reads_typescript_tsc_output(tmp_path: Path) -> None:
    repo_path = tmp_path / "routing-engine"
    (repo_path / "services" / "execution-service" / "src").mkdir(parents=True)
    target = repo_path / "services" / "execution-service" / "src" / "index.ts"
    target.write_text("export const value = 1;\n", encoding="utf-8")

    output = (
        f"{target}(12,5): error TS6059: File is not under 'rootDir' "
        "'/tmp/service'. 'rootDir' is expected to contain all source files.\n"
    )
    diagnostics = parse_repository_diagnostics(repo_path=repo_path, output=output)

    assert len(diagnostics) == 1
    assert diagnostics[0].path == "services/execution-service/src/index.ts"
    assert diagnostics[0].line == 12
    assert diagnostics[0].code == "TS6059"
    assert "rootDir" in diagnostics[0].message


def test_parse_repository_diagnostics_uses_nested_base_path(tmp_path: Path) -> None:
    repo_path = tmp_path / "routing-engine"
    (repo_path / "services" / "execution-service" / "src").mkdir(parents=True)
    target = repo_path / "services" / "execution-service" / "src" / "index.ts"
    target.write_text("export const value = 1;\n", encoding="utf-8")

    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output="src/index.ts(12,5): error TS6059: File is not under 'rootDir'.\n",
        base_path=repo_path / "services" / "execution-service",
    )

    assert diagnostics[0].path == "services/execution-service/src/index.ts"


def test_parse_repository_diagnostics_reads_python_traceback_frames(tmp_path: Path) -> None:
    repo_path = tmp_path / "python-repo"
    (repo_path / "app").mkdir(parents=True)
    target = repo_path / "app" / "worker.py"
    target.write_text("def run() -> None:\n    raise RuntimeError('boom')\n", encoding="utf-8")

    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output=f'  File "{target}", line 2, in run\n',
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].path == "app/worker.py"
    assert diagnostics[0].line == 2
    assert diagnostics[0].message == "Python traceback frame in run"


def test_parse_repository_diagnostics_reads_node_stack_frames(tmp_path: Path) -> None:
    repo_path = tmp_path / "node-repo"
    (repo_path / "src").mkdir(parents=True)
    target = repo_path / "src" / "server.ts"
    target.write_text("throw new Error('boom');\n", encoding="utf-8")

    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output=f"    at startServer ({target}:17:9)\n",
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].path == "src/server.ts"
    assert diagnostics[0].line == 17
    assert diagnostics[0].message == "JavaScript stack frame in startServer"


def test_parse_repository_diagnostics_reads_rust_spans(tmp_path: Path) -> None:
    repo_path = tmp_path / "rust-repo"
    (repo_path / "src").mkdir(parents=True)
    target = repo_path / "src" / "main.rs"
    target.write_text("fn main() {}\n", encoding="utf-8")

    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output=" --> src/main.rs:12:5\n",
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].path == "src/main.rs"
    assert diagnostics[0].line == 12
    assert diagnostics[0].message == "Rust compiler span"


def test_focus_paths_from_diagnostics_prefers_explicit_and_diagnostic_paths(tmp_path: Path) -> None:
    repo_path = tmp_path / "routing-engine"
    repo_path.mkdir()
    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output=(
            "services/execution-service/src/index.ts(12,5): error TS6059: "
            "File is not under 'rootDir'.\n"
        ),
    )

    focus_paths = _focus_paths_from_diagnostics(
        repo_path=repo_path,
        diagnostics=diagnostics,
        explicit_focus_paths=["services/execution-service"],
    )

    assert focus_paths == [
        "services/execution-service",
        "services/execution-service/src/index.ts",
        "services/execution-service/src",
    ]


def test_effective_focus_paths_for_snapshot_prefers_connected_files_over_broad_dirs() -> None:
    diagnostics = [
        RepositoryDiagnostic(
            path="services/execution-service/src/index.ts",
            line=12,
            severity="error",
            code="TS6059",
            message="File is not under rootDir.",
        )
    ]

    effective_focus_paths = _effective_focus_paths_for_snapshot(
        diagnostics=diagnostics,
        connected_files=[
            "services/execution-service/src/index.ts",
            "packages/common/src/execution.ts",
        ],
        fallback_focus_paths=[
            "services/execution-service",
            "services/execution-service/src/index.ts",
            "services/execution-service/src",
        ],
        config_focus_paths=[
            "services/execution-service/tsconfig.test.json",
            "package.json",
        ],
    )

    assert effective_focus_paths == [
        "services/execution-service/src/index.ts",
        "packages/common/src/execution.ts",
        "services/execution-service/tsconfig.test.json",
        "package.json",
    ]


def test_effective_focus_paths_for_snapshot_without_diagnostics_prefers_connected_files() -> None:
    effective_focus_paths = _effective_focus_paths_for_snapshot(
        diagnostics=[],
        connected_files=[
            "src/main.tsx",
            "src/App.tsx",
            "src/lib/utils.ts",
        ],
        fallback_focus_paths=["src"],
        config_focus_paths=["tsconfig.json", "package.json"],
    )

    assert effective_focus_paths == [
        "src/main.tsx",
        "src/App.tsx",
        "src/lib/utils.ts",
        "tsconfig.json",
        "package.json",
    ]


def test_resolve_diagnostic_base_path_infers_cd_command(tmp_path: Path) -> None:
    repo_path = tmp_path / "routing-engine"
    (repo_path / "services" / "execution-service").mkdir(parents=True)

    resolved = _resolve_diagnostic_base_path(
        repo_path,
        diagnostic_command="cd services/execution-service && pnpm exec tsc --noEmit",
        diagnostic_base_path=None,
    )

    assert resolved == (repo_path / "services" / "execution-service").resolve()


def test_resolve_diagnostic_project_path_infers_project_argument(tmp_path: Path) -> None:
    repo_path = tmp_path / "routing-engine"
    (repo_path / "services" / "execution-service").mkdir(parents=True)
    (repo_path / "services" / "execution-service" / "tsconfig.test.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    resolved = _resolve_diagnostic_project_path(
        repo_path,
        diagnostic_command="pnpm exec tsc -p tsconfig.test.json --noEmit",
        diagnostic_base_path=repo_path / "services" / "execution-service",
    )

    assert resolved == "services/execution-service/tsconfig.test.json"


def test_candidate_config_focus_paths_includes_nearby_tsconfig_files(tmp_path: Path) -> None:
    repo_path = _typescript_rootdir_repo(tmp_path)

    config_paths = _candidate_config_focus_paths(
        repo_path=repo_path,
        focus_paths=["services/app"],
        diagnostic_base_path=repo_path / "services" / "app",
        diagnostic_project_path="services/app/tsconfig.test.json",
    )

    assert "services/app/tsconfig.test.json" in config_paths
    assert "services/app/tsconfig.json" in config_paths
    assert "packages/common/package.json" not in config_paths


def test_connected_dependency_map_follows_relative_and_workspace_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        '{"name":"@acme/common"}\n',
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts", "packages/**/*.ts", "packages/**/*.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "packages/common/src/shared.ts",
        "services/app/src/main.ts",
        "services/app/src/util.ts",
    ]


def test_connected_dependency_map_bridges_reverse_dependents_from_scope(tmp_path: Path) -> None:
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        '{"name":"@acme/common"}\n',
        encoding="utf-8",
    )
    (repo_path / "packages" / "common" / "src" / "shared.ts").write_text(
        "export const shared = (): string => 'shared';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { shared } from '@acme/common/shared';\n"
        "export const run = (): string => shared();\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["packages/common/src/shared.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts", "packages/**/*.ts", "packages/**/*.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["bridged_importer_count"] == 1
    assert connected_map["bridged_importers"] == ["services/app/src/main.ts"]
    assert "services/app/src/main.ts" in connected_map["connected_files"]


def test_connected_dependency_map_prefers_operational_reverse_dependents_over_tests(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        '{"name":"@acme/common"}\n',
        encoding="utf-8",
    )
    (repo_path / "packages" / "common" / "src" / "shared.ts").write_text(
        "export const shared = (): string => 'shared';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { shared } from '@acme/common/shared';\n"
        "export const run = (): string => shared();\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.test.ts").write_text(
        "import { shared } from '@acme/common/shared';\n"
        "export const testRun = (): string => shared();\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["packages/common/src/shared.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts", "packages/**/*.ts", "packages/**/*.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["bridged_importers"] == ["services/app/src/main.ts"]
    assert "services/app/src/main.ts" in connected_map["connected_files"]
    assert "services/app/src/main.test.ts" not in connected_map["connected_files"]


def test_connected_dependency_map_uses_dependency_only_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "services" / "app" / "src" / "util.ts").write_text(
        "export const helper = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { helper } from './util';\n"
        "export const run = (): string => helper();\n",
        encoding="utf-8",
    )

    def _unexpected_analyze_file(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("connected-map cold path should not require full file analysis")

    monkeypatch.setattr(repository_service, "_analyze_file", _unexpected_analyze_file)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1


def test_candidate_repository_file_paths_uses_git_listing_without_iter_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = tmp_path / "git-listing-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "export const run = (): string => 'ok';\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    def _unexpected_iter_repository_files(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("git listing should avoid repository tree walk in the probe")

    monkeypatch.setattr(repository_service, "_iter_repository_files", _unexpected_iter_repository_files)

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts"],
        max_files=32,
    )

    assert candidate_paths == ["services/app/src/main.ts"]


def test_candidate_repository_file_paths_prioritizes_operational_files_over_tests(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-priority-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "export const run = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.test.ts").write_text(
        "export const testRun = (): string => 'ok';\n",
        encoding="utf-8",
    )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=[],
        include_patterns=["services/**/*.ts"],
        max_files=1,
    )

    assert candidate_paths == ["services/app/src/main.ts"]


def test_candidate_repository_file_paths_caps_bridge_directory_expansion(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-bridge-budget-repo"
    source_dir = repo_path / "services" / "app" / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "main.ts").write_text(
        "export const run = (): string => 'ok';\n",
        encoding="utf-8",
    )
    for index in range(600):
        (source_dir / f"worker_{index}.ts").write_text(
            f"export const worker{index} = (): number => {index};\n",
            encoding="utf-8",
        )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts"],
        max_files=1024,
    )

    assert "services/app/src/main.ts" in candidate_paths
    assert len(candidate_paths) == 256


def test_candidate_repository_file_paths_distributes_budget_across_bridge_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-bridge-roots-repo"
    alpha_dir = repo_path / "pkgs" / "alpha" / "lib"
    omega_dir = repo_path / "pkgs" / "omega" / "lib"
    alpha_dir.mkdir(parents=True)
    omega_dir.mkdir(parents=True)
    for index in range(20):
        (alpha_dir / f"worker_{index}.dart").write_text(
            f"int worker{index}() => {index};\n",
            encoding="utf-8",
        )
    (omega_dir / "omega.dart").write_text(
        "int omega() => 1;\n",
        encoding="utf-8",
    )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=["pkgs/alpha", "pkgs/omega"],
        include_patterns=["pkgs/**/*.dart"],
        max_files=4,
    )

    assert "pkgs/omega/lib/omega.dart" in candidate_paths


def test_candidate_repository_file_paths_tightens_spread_for_many_bridge_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-many-bridge-roots-repo"
    bridge_paths: list[str] = []
    for index in range(32):
        module_dir = repo_path / f"pkg_{index}" / "src"
        module_dir.mkdir(parents=True)
        bridge_paths.append(f"pkg_{index}")
        for file_index in range(12):
            (module_dir / f"worker_{file_index}.ts").write_text(
                f"export const worker{file_index} = (): number => {index + file_index};\n",
                encoding="utf-8",
            )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=bridge_paths,
        include_patterns=["pkg_*/**/*.ts"],
        max_files=512,
    )

    counts_by_root: dict[str, int] = {}
    for candidate_path in candidate_paths:
        root_path = candidate_path.split("/src/", 1)[0]
        counts_by_root[root_path] = counts_by_root.get(root_path, 0) + 1

    assert 160 <= len(candidate_paths) < 224
    assert len(counts_by_root) == 32
    assert max(counts_by_root.values()) == 6
    assert min(counts_by_root.values()) >= 3
    assert "pkg_0/src/worker_0.ts" in candidate_paths
    assert "pkg_31/src/worker_0.ts" in candidate_paths


def test_candidate_repository_file_paths_shared_parent_roots_keep_broad_collect(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-shared-parent-roots-repo"
    bridge_paths: list[str] = []
    for index in range(32):
        module_dir = repo_path / "pkgs" / f"pkg_{index}" / "lib"
        module_dir.mkdir(parents=True)
        bridge_paths.append(f"pkgs/pkg_{index}")
        for file_index in range(12):
            (module_dir / f"worker_{file_index}.dart").write_text(
                f"int worker{file_index}() => {index + file_index};\n",
                encoding="utf-8",
            )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=bridge_paths,
        include_patterns=["pkgs/**/*.dart"],
        max_files=512,
    )

    counts_by_root: dict[str, int] = {}
    for candidate_path in candidate_paths:
        root_path = candidate_path.split("/lib/", 1)[0]
        counts_by_root[root_path] = counts_by_root.get(root_path, 0) + 1

    assert len(candidate_paths) > 160
    assert len(counts_by_root) == 32
    assert max(counts_by_root.values()) > 6
    assert min(counts_by_root.values()) >= 2


def test_should_group_focus_path_scan_prefers_large_diverse_root_sets() -> None:
    roots = [f"pkg_{index}/src" for index in range(24)]

    assert _should_group_focus_path_scan(roots) is True


def test_should_group_focus_path_scan_prefers_large_shared_parent_sets() -> None:
    roots = [f"pkgs/pkg_{index}/lib" for index in range(20)]

    assert _should_group_focus_path_scan(roots) is True


def test_should_group_focus_path_scan_skips_medium_multi_group_sets() -> None:
    roots = [
        "buildSrc/src/main/groovy",
        "doc/manual/src",
        "doc/site/src",
        "integration/geb-gradle/src/main/groovy",
        "integration/geb-testcontainers/src/main/groovy",
        "internal/test-support/src/main/groovy",
        "module/a/src/main/groovy",
        "module/b/src/main/groovy",
        "module/c/src/main/groovy",
        "module/d/src/main/groovy",
        "module/e/src/main/groovy",
        "module/f/src/main/groovy",
        "module/g/src/main/groovy",
        "module/h/src/main/groovy",
        "module/i/src/main/groovy",
        "module/j/src/main/groovy",
        "module/k/src/main/groovy",
        "module/l/src/main/groovy",
        "module/m/src/main/groovy",
        "module/n/src/main/groovy",
        "module/o/src/main/groovy",
        "module/p/src/main/groovy",
    ]

    assert _should_group_focus_path_scan(roots) is False


def test_should_group_focus_path_scan_prefers_medium_source_root_sets() -> None:
    roots = [
        "play-functional/src/main/scala",
        "play-json-joda/src/main/scala",
        "play-json/js-native/src",
        "play-json/js/src",
        "play-json/jvm-native/src",
        "play-json/jvm/src/main/scala",
        "play-json/native/src/main/scala",
        "play-json/shared/src/main/scala",
        "project",
    ]

    assert _should_group_focus_path_scan(roots) is False
    assert _should_group_focus_path_scan(roots[:-1]) is True


def test_should_use_seeded_profile_candidate_scan_skips_scattered_small_root_sets() -> None:
    assert (
        _should_use_seeded_profile_candidate_scan(
            seed_paths=[],
            bridge_paths=[
                "play-functional/src/main/scala",
                "play-json-joda/src/main/scala",
                "play-json/js-native/src",
                "play-json/js/src",
                "play-json/jvm-native/src",
                "play-json/jvm/src/main/scala",
                "play-json/native/src/main/scala",
                "play-json/shared/src/main/scala",
            ],
        )
        is False
    )


def test_should_use_seeded_profile_candidate_scan_keeps_seeded_single_group_root_sets() -> None:
    assert (
        _should_use_seeded_profile_candidate_scan(
            seed_paths=[],
            bridge_paths=[
                "os/src",
                "os/src-2",
                "os/src-3",
                "os/src-jvm",
                "os/src-native",
                "os/watch/src",
                "os/zip/src",
            ],
        )
        is True
    )
    assert (
        _should_use_seeded_profile_candidate_scan(
            seed_paths=["pkgs/app/lib/app.dart"],
            bridge_paths=[
                "pkgs/app/lib",
                "pkgs/http/lib",
                "pkgs/http_profile/lib",
            ],
        )
        is True
    )


def _write_scratch_project(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(payload, indent=2, sort_keys=True))


def _scratch_project_payload(name: str = "Maze") -> dict[str, object]:
    return {
        "extensions": [],
        "meta": {"agent": "pytest", "semver": "3.0.0", "vm": "0.2.0"},
        "monitors": [],
        "targets": [
            {
                "blocks": {
                    "stage_event": {
                        "fields": {},
                        "inputs": {},
                        "next": "stage_broadcast",
                        "opcode": "event_whenflagclicked",
                        "parent": None,
                        "topLevel": True,
                    },
                    "stage_broadcast": {
                        "fields": {},
                        "inputs": {"BROADCAST_INPUT": [1, [11, "start", "broadcast-id"]]},
                        "next": None,
                        "opcode": "event_broadcast",
                        "parent": "stage_event",
                        "topLevel": False,
                    },
                },
                "broadcasts": {"broadcast-id": "start"},
                "comments": {},
                "costumes": [],
                "currentCostume": 0,
                "isStage": True,
                "lists": {},
                "name": "Stage",
                "sounds": [],
                "tempo": 60,
                "variables": {},
                "videoState": "on",
                "videoTransparency": 50,
                "volume": 100,
            },
            {
                "blocks": {
                    "receive": {
                        "fields": {"BROADCAST_OPTION": ["start", "broadcast-id"]},
                        "inputs": {},
                        "next": "call",
                        "opcode": "event_whenbroadcastreceived",
                        "parent": None,
                        "topLevel": True,
                    },
                    "call": {
                        "fields": {},
                        "inputs": {},
                        "mutation": {
                            "argumentids": "[]",
                            "proccode": "init",
                            "warp": "false",
                        },
                        "next": None,
                        "opcode": "procedures_call",
                        "parent": "receive",
                        "topLevel": False,
                    },
                    "define": {
                        "fields": {},
                        "inputs": {"custom_block": [1, "prototype"]},
                        "next": None,
                        "opcode": "procedures_definition",
                        "parent": None,
                        "topLevel": True,
                    },
                    "prototype": {
                        "fields": {},
                        "inputs": {},
                        "mutation": {
                            "argumentids": "[]",
                            "proccode": "init",
                            "warp": "false",
                        },
                        "next": None,
                        "opcode": "procedures_prototype",
                        "parent": "define",
                        "topLevel": False,
                    },
                },
                "broadcasts": {},
                "comments": {},
                "costumes": [],
                "currentCostume": 0,
                "isStage": False,
                "lists": {},
                "name": name,
                "size": 100,
                "sounds": [],
                "variables": {},
                "visible": True,
                "volume": 100,
                "x": 0,
                "y": 0,
            },
        ],
    }


def test_repository_language_popularity_order_covers_broad_supported_surface() -> None:
    assert len(REPOSITORY_LANGUAGE_POPULARITY_ORDER) >= 50
    assert REPOSITORY_LANGUAGE_POPULARITY_ORDER[:14] == (
        "typescript",
        "python",
        "javascript",
        "vue",
        "svelte",
        "astro",
        "node",
        "java",
        "cs",
        "dotnet",
        "php",
        "hack",
        "shell",
        "fish",
    )
    assert "c" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "ada" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "assembly" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "cobol" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "scratch" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "pug" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "delphi" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "plsql" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "tsql" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "sas" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "ml" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vb6" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vba" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "abap" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "matlab" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "objectivec" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "prolog" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "lisp" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "scheme" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "racket" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "gdscript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "gml" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "foxpro" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "solidity" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vbscript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "applescript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "ladder" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "apex" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "labview" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "wolfram" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "rpg" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "actionscript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "awk" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "coffeescript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "autohotkey" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "cfml" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "elm" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "agda" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "idris" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "haxe" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "fish" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "emacslisp" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vimscript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "xpp" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "verilog" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "systemverilog" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vhdl" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "tcl" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vala" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "smalltalk" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "mql5" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "gams" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "openscad" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "purescript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "rescript" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "roc" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "smarty" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "graphviz" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "mermaid" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "plantuml" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "openqasm" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "gleam" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "janet" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "raku" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "starlark" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "chapel" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "eiffel" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "dhall" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "rego" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "yara" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "nix" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "nushell" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "bitbake" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "jinja" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "liquid" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "handlebars" in REPOSITORY_LANGUAGE_POPULARITY_ORDER
    assert "vue" in REPOSITORY_LANGUAGE_POPULARITY_ORDER


def test_candidate_ecosystems_for_path_treats_custom_suffixes_and_ambiguous_m_files_carefully(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-ecosystems-repo"
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "script").mkdir(parents=True)
    (repo_path / "ios").mkdir(parents=True)
    (repo_path / "lisp").mkdir(parents=True)
    (repo_path / "foxpro").mkdir(parents=True)
    (repo_path / "Kernel").mkdir(parents=True)
    (repo_path / "vb6").mkdir(parents=True)
    (repo_path / "vba").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "cfml-app" / "models").mkdir(parents=True)
    (repo_path / "cfml-app" / "public").mkdir(parents=True)
    (repo_path / "database" / "dbo" / "Stored Procedures").mkdir(parents=True)
    (repo_path / "coffee-app" / "src").mkdir(parents=True)
    (repo_path / "delphi-app" / "source").mkdir(parents=True)
    (repo_path / "elm-app" / "src" / "Page").mkdir(parents=True)
    (repo_path / "elisp-app" / "lisp").mkdir(parents=True)
    (repo_path / "smalltalk-app" / "src" / "Demo-Core").mkdir(parents=True)
    (repo_path / "vala-app" / "src").mkdir(parents=True)
    (repo_path / "vala-app" / "vapi").mkdir(parents=True)
    (repo_path / "mql5-app" / "Experts").mkdir(parents=True)
    (repo_path / "mql5-app" / "Include").mkdir(parents=True)
    (repo_path / "gams-app" / "include").mkdir(parents=True)
    (repo_path / "openscad-app" / "lib").mkdir(parents=True)
    (repo_path / "purescript-app" / "src" / "Data").mkdir(parents=True)
    (repo_path / "purescript-app" / "test").mkdir(parents=True)
    (repo_path / "gleam-app" / "src" / "demo").mkdir(parents=True)
    (repo_path / "gleam-app" / "test").mkdir(parents=True)
    (repo_path / "janet-app" / "src" / "demo").mkdir(parents=True)
    (repo_path / "janet-app" / "test").mkdir(parents=True)
    (repo_path / "dhall-app" / "schemas").mkdir(parents=True)
    (repo_path / "dhall-app" / "tests").mkdir(parents=True)
    (repo_path / "rego-app" / "policy" / "lib").mkdir(parents=True)
    (repo_path / "agda-app" / "src" / "Data").mkdir(parents=True)
    (repo_path / "idris-app" / "src" / "Demo").mkdir(parents=True)
    (repo_path / "idris-app" / "tests").mkdir(parents=True)
    (repo_path / "raku-app" / "lib" / "Demo").mkdir(parents=True)
    (repo_path / "raku-app" / "bin").mkdir(parents=True)
    (repo_path / "nushell-app" / "modules").mkdir(parents=True)
    (repo_path / "fish-app" / "functions").mkdir(parents=True)
    (repo_path / "fish-app" / "conf.d").mkdir(parents=True)
    (repo_path / "haxe-app" / "src" / "demo").mkdir(parents=True)
    (repo_path / "lean-app" / "Batteries").mkdir(parents=True)
    (repo_path / "starlark-app" / "rules").mkdir(parents=True)
    (repo_path / "starlark-app" / "lib").mkdir(parents=True)
    (repo_path / "nix-app" / "nix" / "lib").mkdir(parents=True)
    (repo_path / "scheme-app" / "lib" / "acme").mkdir(parents=True)
    (repo_path / "racket-app" / "private").mkdir(parents=True)
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "tcllib").mkdir(parents=True)
    (repo_path / "contracts").mkdir(parents=True)
    (repo_path / "logic").mkdir(parents=True)
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "vhdl").mkdir(parents=True)
    (repo_path / "godot" / "scripts").mkdir(parents=True)
    (repo_path / "labview" / "Source").mkdir(parents=True)
    (repo_path / "labview" / "Controls").mkdir(parents=True)
    (repo_path / "force-app" / "main" / "default" / "classes").mkdir(parents=True)
    (repo_path / "force-app" / "main" / "default" / "triggers").mkdir(parents=True)
    (repo_path / "src" / "boot.asm").write_text(
        "global start\nstart:\n    ret\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "translate").write_text(
        "#!/usr/bin/env gawk -f\n"
        '@include "../lib/math.awk"\n'
        "BEGIN { print add(1, 2) }\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "math.awk").write_text(
        "function add(a, b) {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "cfml-app" / "box.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "cfml-app" / "Application.cfc").write_text(
        "component {\n"
        "    function onApplicationStart() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "cfml-app" / "models" / "UserService.cfc").write_text(
        "component {\n"
        "    function run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "cfml-app" / "public" / "index.cfm").write_text(
        '<cfinclude template="../Application.cfc">\n',
        encoding="utf-8",
    )
    (repo_path / "database" / "Acme.sqlproj").write_text(
        "<Project>\n"
        "  <ItemGroup>\n"
        '    <Build Include="dbo\\Stored Procedures\\LoadCustomers.sql" />\n'
        "  </ItemGroup>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "_CoqProject").write_text(
        "-Q theories Demo\n"
        "theories/Main.v\n",
        encoding="utf-8",
    )
    (repo_path / "lean-app" / "lean-toolchain").write_text(
        "leanprover/lean4:stable\n",
        encoding="utf-8",
    )
    (repo_path / "lean-app" / "lakefile.lean").write_text(
        "package batteries where\n\n"
        "lean_lib Batteries\n",
        encoding="utf-8",
    )
    (repo_path / "lean-app" / "Batteries" / "Main.lean").write_text(
        "import Batteries.Helper\n\n"
        "def main : Nat := Batteries.Helper.helper\n",
        encoding="utf-8",
    )
    (repo_path / "lean-app" / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 1\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Main.v").write_text(
        "From Demo Require Import Helper.\n"
        "Definition main := Helper.helper.\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper := 1.\n",
        encoding="utf-8",
    )
    (
        repo_path / "database" / "dbo" / "Stored Procedures" / "LoadCustomers.sql"
    ).write_text(
        "create or alter procedure dbo.LoadCustomers\n"
        "as\n"
        "begin\n"
        "    set nocount on;\n"
        "    select 1 as id;\n"
        "end\n"
        "go\n",
        encoding="utf-8",
    )
    (repo_path / "delphi-app" / "AcmeApp.dproj").write_text(
        "<Project>\n"
        "  <MainSource>AcmeApp.dpr</MainSource>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "delphi-app" / "AcmeApp.dpr").write_text(
        "program AcmeApp;\n"
        "uses MainForm in 'source/MainForm.pas';\n"
        "begin\n"
        "  MainForm.Run;\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "delphi-app" / "source" / "MainForm.pas").write_text(
        "unit MainForm;\n"
        "interface\n"
        "uses System.SysUtils, Vcl.Forms;\n"
        "{$R *.dfm}\n"
        "implementation\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "elm-app" / "elm.json").write_text(
        json.dumps(
            {
                "type": "application",
                "source-directories": ["src"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "elm-app" / "src" / "Main.elm").write_text(
        "module Main exposing (main)\n\n"
        "import Page.Home exposing (homeView)\n\n"
        "main : String\n"
        "main =\n"
        "    homeView\n",
        encoding="utf-8",
    )
    (repo_path / "elm-app" / "src" / "Page" / "Home.elm").write_text(
        "module Page.Home exposing (homeView)\n\n"
        "homeView : String\n"
        "homeView =\n"
        "    \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "coffee-app" / "Cakefile").write_text(
        "task 'build', ->\n"
        "  require './src/main'\n",
        encoding="utf-8",
    )
    (repo_path / "coffee-app" / "src" / "main.coffee").write_text(
        "run = ->\n"
        "  console.log 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "vala-app" / "src" / "main.vala").write_text(
        "namespace Demo {\n"
        "    public class App : Object {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "vala-app" / "vapi" / "demo.vapi").write_text(
        "namespace Demo {\n"
        "    public class Helper : Object;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "mql5-app" / "demo.mqproj").write_text(
        '<Project><Files><File>Experts/Main.mq5</File><File>Include/Helper.mqh</File></Files></Project>\n',
        encoding="utf-8",
    )
    (repo_path / "mql5-app" / "Experts" / "Main.mq5").write_text(
        '#include "../Include/Helper.mqh"\n'
        "void OnStart()\n"
        "{\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "mql5-app" / "Include" / "Helper.mqh").write_text(
        "class Helper\n"
        "{\n"
        "public:\n"
        "   string RenderJson()\n"
        "     {\n"
        '      return "{}";\n'
        "     }\n"
        "};\n",
        encoding="utf-8",
    )
    (repo_path / "gams-app" / "main.gms").write_text(
        "$include include/common.inc\n"
        "set i /a,b/;\n"
        "parameter demand(i);\n",
        encoding="utf-8",
    )
    (repo_path / "gams-app" / "include" / "common.inc").write_text(
        "parameter supply(i);\n",
        encoding="utf-8",
    )
    (repo_path / "openscad-app" / "main.scad").write_text(
        "include <lib/helper.scad>;\n"
        "module build() {\n"
        "  gusset(10);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "openscad-app" / "lib" / "helper.scad").write_text(
        "module gusset(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "purescript-app" / "spago.yaml").write_text(
        "package:\n"
        "  name: demo\n"
        "workspace:\n"
        "  package_set:\n"
        "    registry: 64.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "purescript-app" / "src" / "Main.purs").write_text(
        "module Main where\n\nimport Data.Helper (helperValue)\n\nmain = helperValue\n",
        encoding="utf-8",
    )
    (repo_path / "purescript-app" / "src" / "Data" / "Helper.purs").write_text(
        "module Data.Helper where\n\nhelperValue :: Int\nhelperValue = 1\n",
        encoding="utf-8",
    )
    (repo_path / "purescript-app" / "test" / "Main.purs").write_text(
        "module Test.Main where\n\nmain = 1\n",
        encoding="utf-8",
    )
    (repo_path / "gleam-app" / "gleam.toml").write_text(
        'name = "demo"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (repo_path / "gleam-app" / "src" / "main.gleam").write_text(
        "import demo/helper.{render_json}\n\npub fn main() {\n  render_json()\n}\n",
        encoding="utf-8",
    )
    (repo_path / "gleam-app" / "src" / "demo" / "helper.gleam").write_text(
        "pub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )
    (repo_path / "gleam-app" / "test" / "main.gleam").write_text(
        "pub fn test_main() {\n  Nil\n}\n",
        encoding="utf-8",
    )
    (repo_path / "janet-app" / "project.janet").write_text(
        '(declare-project :name "demo" :source @["src"] :main "src/main.janet")\n',
        encoding="utf-8",
    )
    (repo_path / "janet-app" / "src" / "main.janet").write_text(
        '(import ./demo/helper :as helper)\n\n(defn main []\n  (helper/render-json))\n',
        encoding="utf-8",
    )
    (repo_path / "janet-app" / "src" / "demo" / "helper.janet").write_text(
        "(defn render-json [] @{})\n",
        encoding="utf-8",
    )
    (repo_path / "janet-app" / "test" / "main.janet").write_text(
        "(defn test-main [] @{})\n",
        encoding="utf-8",
    )
    (repo_path / "dhall-app" / "package.dhall").write_text(
        "{ Type = ./schemas/Step.dhall }\n",
        encoding="utf-8",
    )
    (repo_path / "dhall-app" / "schemas" / "Step.dhall").write_text(
        "{ Type = \"step\", default = \"run\" }\n",
        encoding="utf-8",
    )
    (repo_path / "dhall-app" / "workflow.dhall").write_text(
        "let Package = ./package.dhall\nin Package.Type\n",
        encoding="utf-8",
    )
    (repo_path / "dhall-app" / "tests" / "workflow_test.dhall").write_text(
        "let Package = ../package.dhall\nin Package.Type\n",
        encoding="utf-8",
    )
    (repo_path / "rego-app" / "policy" / "main.rego").write_text(
        "package policy.main\n\n"
        "import data.policy.lib.helpers as helper\n\n"
        "allow if {\n"
        "    helper.render_json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "rego-app" / "policy" / "lib" / "helpers.rego").write_text(
        "package policy.lib.helpers\n\n"
        "render_json if {\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "yara-app" / "rules" / "lib").mkdir(parents=True)
    (repo_path / "yara-app" / "tests").mkdir(parents=True)
    (repo_path / "yara-app" / "rules" / "index.yar").write_text(
        'include "./main.yar"\n'
        'include "./lib/helper.yar"\n',
        encoding="utf-8",
    )
    (repo_path / "yara-app" / "rules" / "main.yar").write_text(
        "rule main_rule {\n"
        "  condition:\n"
        "    helper_rule\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "yara-app" / "rules" / "lib" / "helper.yar").write_text(
        "private rule helper_rule {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "yara-app" / "tests" / "rules_test.yar").write_text(
        "rule rules_test {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "bitbake-app" / "conf").mkdir(parents=True)
    (repo_path / "bitbake-app" / "classes").mkdir(parents=True)
    (repo_path / "bitbake-app" / "recipes-core" / "base").mkdir(parents=True)
    (repo_path / "bitbake-app" / "recipes-core" / "images").mkdir(parents=True)
    (repo_path / "bitbake-app" / "conf" / "layer.conf").write_text(
        'BBPATH .= ":${LAYERDIR}"\n'
        'BBFILES += "${LAYERDIR}/recipes-*/*/*.bb"\n',
        encoding="utf-8",
    )
    (repo_path / "bitbake-app" / "classes" / "image.bbclass").write_text(
        "python do_rootfs() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "bitbake-app" / "recipes-core" / "base" / "base.inc").write_text(
        'BASE_NAME = "base"\n',
        encoding="utf-8",
    )
    (repo_path / "bitbake-app" / "recipes-core" / "images" / "core-image-minimal.bb").write_text(
        "require ../base/base.inc\n"
        "inherit image\n"
        'IMAGE_FEATURES += "ssh-server-dropbear"\n',
        encoding="utf-8",
    )
    (repo_path / "hcl-app" / "modules" / "child").mkdir(parents=True)
    (repo_path / "hcl-app" / "main.tf").write_text(
        'module "child" {\n'
        '  source = "./modules/child"\n'
        '}\n\n'
        'variable "name" {\n'
        '  default = "demo"\n'
        '}\n\n'
        "locals {\n"
        '  prefix = "vpc-${var.name}"\n'
        "}\n\n"
        'output "full_name" {\n'
        "  value = local.prefix\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "hcl-app" / "modules" / "child" / "main.tf").write_text(
        'output "child_id" {\n'
        '  value = "child"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "agda-app" / "standard-library.agda-lib").write_text(
        "name: demo\ninclude: src\n",
        encoding="utf-8",
    )
    (repo_path / "agda-app" / "src" / "Main.agda").write_text(
        "module Main where\n\n"
        "open import Data.Helper using (helper)\n\n"
        "main : Set\n"
        "main = helper\n",
        encoding="utf-8",
    )
    (repo_path / "agda-app" / "src" / "Data" / "Helper.agda").write_text(
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n",
        encoding="utf-8",
    )
    (repo_path / "idris-app" / "demo.ipkg").write_text(
        "package demo\n"
        "sourcedir = src\n"
        "modules = Demo.Helper\n"
        "main = Main\n",
        encoding="utf-8",
    )
    (repo_path / "idris-app" / "src" / "Main.idr").write_text(
        "module Main\n\n"
        "import Demo.Helper\n\n"
        "main : IO ()\n"
        "main = renderJson\n",
        encoding="utf-8",
    )
    (repo_path / "idris-app" / "src" / "Demo" / "Helper.idr").write_text(
        "module Demo.Helper\n\n"
        "renderJson : IO ()\n"
        "renderJson = pure ()\n",
        encoding="utf-8",
    )
    (repo_path / "idris-app" / "tests" / "Main.idr").write_text(
        "module Tests.Main\n\n"
        "testMain : IO ()\n"
        "testMain = pure ()\n",
        encoding="utf-8",
    )
    (repo_path / "raku-app" / "META6.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "provides": {"Demo::Helper": "lib/Demo/Helper.rakumod"},
                "bin": ["demo.raku"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "raku-app" / "lib" / "Demo" / "Helper.rakumod").write_text(
        "unit module Demo::Helper;\n\nsub render-json() is export { \"{}\" }\n",
        encoding="utf-8",
    )
    (repo_path / "raku-app" / "bin" / "demo.raku").write_text(
        "use Demo::Helper;\n\nsub main() {\n    Demo::Helper::render-json();\n}\n",
        encoding="utf-8",
    )
    (repo_path / "nushell-app" / "main.nu").write_text(
        "source modules/helper.nu\n\n"
        "def main [] {\n"
        "  render-json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "nushell-app" / "modules" / "helper.nu").write_text(
        "export def render-json [] {\n"
        "  '{}'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "fish-app" / "main.fish").write_text(
        "source functions/helper.fish\n\n"
        "function main\n"
        "    helper\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "fish-app" / "functions" / "helper.fish").write_text(
        "function helper\n"
        "    echo '{}'\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "fish-app" / "conf.d" / "init.fish").write_text(
        "helper\n",
        encoding="utf-8",
    )
    (repo_path / "haxe-app" / "build.hxml").write_text(
        "-cp src\n-main demo.Main\n",
        encoding="utf-8",
    )
    (repo_path / "haxe-app" / "src" / "demo" / "Main.hx").write_text(
        "package demo;\n"
        "\n"
        "import demo.Helper;\n"
        "\n"
        "class Main {\n"
        "    static function main() {\n"
        "        Helper.renderJson();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "haxe-app" / "src" / "demo" / "Helper.hx").write_text(
        "package demo;\n"
        "\n"
        "class Helper {\n"
        "    public static function renderJson():String {\n"
        '        return "{}";\n'
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "automation").mkdir(parents=True, exist_ok=True)
    (repo_path / "automation" / "Main.ahk").write_text(
        '#Include "../Lib/Helper.ahk"\n'
        "Main() {\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Lib").mkdir(parents=True, exist_ok=True)
    (repo_path / "Lib" / "Helper.ahk").write_text(
        "RenderJson(value) {\n"
        "    return value\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "starlark-app" / "MODULE.bazel").write_text(
        'module(name = "acme")\n',
        encoding="utf-8",
    )
    (repo_path / "starlark-app" / "BUILD.bazel").write_text(
        'load("//rules:demo.bzl", "demo_macro")\n'
        '\n'
        'demo_macro(name = "app")\n',
        encoding="utf-8",
    )
    (repo_path / "starlark-app" / "rules" / "demo.bzl").write_text(
        'load("//lib:common.bzl", "render_json")\n'
        "\n"
        "def demo_macro(name):\n"
        "    return render_json(name)\n",
        encoding="utf-8",
    )
    (repo_path / "starlark-app" / "lib" / "common.bzl").write_text(
        "def render_json(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "nix-app" / "flake.nix").write_text(
        "{\n"
        "  inputs.nixpkgs.url = \"github:NixOS/nixpkgs\";\n"
        "  outputs = { self, nixpkgs }:\n"
        "    let formatter = import ./nix/lib/formatter.nix { pkgs = nixpkgs.legacyPackages.x86_64-linux; }; in {\n"
        "      formatter = formatter.mkFormatter nixpkgs.legacyPackages.x86_64-linux.alejandra;\n"
        "    };\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "nix-app" / "nix" / "lib" / "formatter.nix").write_text(
        "{ pkgs }:\n"
        "{\n"
        "  mkFormatter = package: package;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "smalltalk-app" / ".smalltalk.ston").write_text(
        "{ }\n",
        encoding="utf-8",
    )
    (repo_path / "smalltalk-app" / "src" / "Demo-Core" / "package.st").write_text(
        "Package { #name : 'Demo-Core' }\n",
        encoding="utf-8",
    )
    (repo_path / "smalltalk-app" / "src" / "Demo-Core" / "Helper.class.st").write_text(
        "Class {\n"
        "\t#name : 'Helper',\n"
        "\t#superclass : 'Object',\n"
        "\t#category : 'Demo-Core',\n"
        "\t#package : 'Demo-Core'\n"
        "}\n"
        "\n"
        "{ #category : 'rendering' }\n"
        "Helper class >> renderJson [\n"
        "\t^ '{}'\n"
        "]\n",
        encoding="utf-8",
    )
    (repo_path / "elisp-app" / "Cask").write_text(
        "(source gnu)\n"
        '(package-file "main.el")\n',
        encoding="utf-8",
    )
    (repo_path / "elisp-app" / "main.el").write_text(
        "(require 'helper)\n"
        "(provide 'main)\n"
        "(defun run () (helper-fn))\n",
        encoding="utf-8",
    )
    (repo_path / "elisp-app" / "lisp" / "helper.el").write_text(
        "(provide 'helper)\n"
        "(defun helper-fn () 1)\n",
        encoding="utf-8",
    )
    (repo_path / "scheme-app" / "package.scm").write_text(
        "(define-library (acme app)\n"
        "  (export run)\n"
        "  (import (acme helper))\n"
        "  (begin\n"
        "    (define (run) (helper))))\n",
        encoding="utf-8",
    )
    (repo_path / "scheme-app" / "main.scm").write_text(
        "#!r6rs\n"
        "(import (acme helper))\n"
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "scheme-app" / "lib" / "acme" / "helper.sld").write_text(
        "(define-library (acme helper)\n"
        "  (export helper)\n"
        "  (begin\n"
        "    (define (helper) 1)))\n",
        encoding="utf-8",
    )
    (repo_path / "racket-app" / "info.rkt").write_text(
        "#lang info\n"
        '(define collection "racket-app")\n',
        encoding="utf-8",
    )
    (repo_path / "racket-app" / "main.rkt").write_text(
        "#lang racket\n"
        '(require "private/helper.rkt")\n'
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "racket-app" / "private" / "helper.rkt").write_text(
        "#lang racket\n"
        "(define (helper) 1)\n",
        encoding="utf-8",
    )
    (repo_path / "include" / "io.inc").write_text(
        "extern print_string\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.c").write_text(
        '#include "io.h"\n'
        "int main(void) { return 0; }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.as").write_text(
        "package demo.app {\n"
        "    public class Main {\n"
        "        public function boot():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "family.pl").write_text(
        ":- module(family, [ancestor/2]).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )
    (repo_path / "script" / "app.pl").write_text(
        "use strict;\n"
        "use warnings;\n"
        "sub run { return 1; }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.m").write_text(
        "function value = main()\nvalue = helper();\nend\n",
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "Helpers.wl").write_text(
        'BeginPackage["Acme`"];\n'
        'helper::usage = "helper";\n'
        "helper[] := 1;\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "init.m").write_text(
        'Get["Acme`Helpers`"];\n',
        encoding="utf-8",
    )
    (repo_path / "ios" / "AppDelegate.m").write_text(
        "#import <Foundation/Foundation.h>\n@implementation AppDelegate\n@end\n",
        encoding="utf-8",
    )
    (repo_path / "ios" / "AppDelegate.h").write_text(
        "#import <Foundation/Foundation.h>\n@interface AppDelegate : NSObject\n@end\n",
        encoding="utf-8",
    )
    (repo_path / "vb6" / "Project1.vbp").write_text(
        'Type=Exe\nForm=Form1.frm\nStartup="Form1"\nName="Project1"\n',
        encoding="utf-8",
    )
    (repo_path / "vb6" / "Form1.frm").write_text(
        "VERSION 5.00\n"
        "Begin VB.Form Form1\n"
        "End\n"
        'Attribute VB_Name = "Form1"\n',
        encoding="utf-8",
    )
    (repo_path / "vb6" / "modMain.bas").write_text(
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "vba" / "JsonConverter.bas").write_text(
        'Attribute VB_Name = "JsonConverter"\n'
        "Option Explicit\n"
        "Public Function ToJson() As String\n"
        '    ToJson = "{}"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "build.vbs").write_text(
        "Option Explicit\n"
        "Sub Main()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.wsf").write_text(
        "<job>\n"
        '  <script language="VBScript" src="build.vbs"></script>\n'
        '  <script language="VBScript">\n'
        "    Option Explicit\n"
        "    Sub Main()\n"
        "    End Sub\n"
        "  </script>\n"
        "</job>\n",
        encoding="utf-8",
    )
    (repo_path / "automation").mkdir(parents=True, exist_ok=True)
    (repo_path / "automation" / "Helper.applescript").write_text(
        "script HelperScript\n"
        "    on RenderJson(value)\n"
        "        return value\n"
        "    end RenderJson\n"
        "end script\n",
        encoding="utf-8",
    )
    (repo_path / "automation" / "Main.applescript").write_text(
        'property helperScript : load script POSIX file "Helper.applescript"\n'
        "on run\n"
        "    helperScript's RenderJson(\"{}\")\n"
        "end run\n",
        encoding="utf-8",
    )
    (repo_path / "automation" / "Compiled.scpt").write_text(
        "on run\n"
        "    return 1\n"
        "end run\n",
        encoding="utf-8",
    )
    (repo_path / "tcllib" / "pkgIndex.tcl").write_text(
        "package ifneeded sha1 2.0.5 [list source [file join $dir sha1.tcl]]\n",
        encoding="utf-8",
    )
    (repo_path / "tcllib" / "sha1.tcl").write_text(
        "package provide sha1 2.0.5\n"
        "proc ::sha1::run {} {\n"
        "    return ok\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lisp" / "acme.asd").write_text(
        '(asdf:defsystem "acme"\n'
        '  :components ((:file "package") (:file "helper") (:file "app")))\n',
        encoding="utf-8",
    )
    (repo_path / "lisp" / "app.lisp").write_text(
        "(defpackage #:acme.app (:use #:cl))\n"
        "(in-package #:acme.app)\n"
        "(defun run () (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "foxpro" / "main.prg").write_text(
        "LPARAMETERS value\n"
        "FUNCTION main()\n"
        "    RETURN value\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    (repo_path / "contracts" / "Counter.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "contract Counter {\n"
        "    function increment() public {}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.sv").write_text(
        "module top;\nendmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.v").write_text(
        "module child;\nendmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "defs.vh").write_text(
        "`ifndef DEFS_VH\n`define DEFS_VH\n`endif\n",
        encoding="utf-8",
    )
    (repo_path / "vhdl" / "top.vhd").write_text(
        "entity top is\n"
        "end entity;\n"
        "architecture rtl of top is\n"
        "begin\n"
        "end architecture;\n",
        encoding="utf-8",
    )
    (repo_path / "godot" / "scripts" / "player.gd").write_text(
        "class_name Player\n"
        "extends Node\n"
        "func ready_up() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (repo_path / "logic" / "Main.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="MainProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="MainRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[JSR(ChildRoutine,0);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "logic" / "Types.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        '<RSLogix5000Content TargetType="DataType">\n'
        '  <Controller Name="PlantController">\n'
        "    <DataTypes>\n"
        '      <DataType Name="MotorStatus">\n'
        "        <Members>\n"
        '          <Member Name="Running" DataType="BOOL"/>\n'
        "        </Members>\n"
        "      </DataType>\n"
        "    </DataTypes>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "labview" / "App.lvproj").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Project Type=\"Project\">\n"
        '  <Item Name="Main" Type="VI" URL="Source/Main.vi" />\n'
        '  <Item Name="Config" Type="Control" URL="Controls/Config.ctl" />\n'
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "labview" / "Source" / "Main.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")
    (repo_path / "labview" / "Controls" / "Config.ctl").write_bytes(b"RSRC\r\n\x00\x03LVCCLBVW")
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
    ).mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Descriptor"
    ).mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
        / "AcmeMain.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>AcmeMain</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class AcmeMain\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "  </SourceCode>\n"
        "</AxClass>\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Descriptor"
        / "Acme.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxModelInfo>\n"
        "  <Name>Acme</Name>\n"
        "</AxModelInfo>\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "force-app"
        / "main"
        / "default"
        / "classes"
        / "AccountTriggerHandler.cls"
    ).write_text(
        "public with sharing class AccountTriggerHandler {\n"
        "    public static void run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "force-app"
        / "main"
        / "default"
        / "triggers"
        / "AccountTrigger.trigger"
    ).write_text(
        "trigger AccountTrigger on Account (before insert) {\n"
        "    AccountTriggerHandler.run();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "puppet-app" / "manifests").mkdir(parents=True)
    (repo_path / "puppet-app" / "metadata.json").write_text(
        '{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        encoding="utf-8",
    )
    (repo_path / "puppet-app" / "Puppetfile").write_text(
        "mod 'puppetlabs-stdlib'\n",
        encoding="utf-8",
    )
    (repo_path / "puppet-app" / "manifests" / "init.pp").write_text(
        "class apache {\n"
        "  include apache::params\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "hack-app" / "src").mkdir(parents=True)
    (repo_path / "hack-app" / "tests").mkdir(parents=True)
    (repo_path / "hack-app" / ".hhconfig").write_text(
        "assume_php = false\n",
        encoding="utf-8",
    )
    (repo_path / "hack-app" / "src" / "Ref.php").write_text(
        "<?hh\nnamespace Demo;\nfinal class Ref<T> {}\n",
        encoding="utf-8",
    )
    (repo_path / "hack-app" / "src" / "Vec.hack").write_text(
        "namespace Demo;\nnewtype Vec<T> = vec<T>;\n",
        encoding="utf-8",
    )
    (repo_path / "hack-app" / "tests" / "RefTest.php").write_text(
        "<?hh\nnamespace Demo;\nfinal class RefTest {}\n",
        encoding="utf-8",
    )
    (repo_path / "pascal-app" / "src").mkdir(parents=True)
    (repo_path / "pascal-app" / "src" / "main.pp").write_text(
        "program Main;\n"
        "begin\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "batch-app" / "scripts").mkdir(parents=True)
    (repo_path / "batch-app" / "build.bat").write_text(
        "@echo off\n"
        "call scripts\\helper.cmd\n",
        encoding="utf-8",
    )
    (repo_path / "batch-app" / "scripts" / "helper.cmd").write_text(
        "@echo off\n"
        "echo helper\n",
        encoding="utf-8",
    )
    (repo_path / "make-app" / "mk").mkdir(parents=True)
    (repo_path / "make-app" / "Makefile").write_text(
        "include mk/common.mk\n"
        "build:\n"
        "\t$(MAKE) helper\n",
        encoding="utf-8",
    )
    (repo_path / "make-app" / "mk" / "common.mk").write_text(
        "helper:\n"
        "\t@echo helper\n",
        encoding="utf-8",
    )

    assert probe_module._candidate_ecosystems_for_path("fixtures/main.adb_body") == {"unknown"}
    assert probe_module._candidate_ecosystems_for_path("fixtures/main.unknown_ext") == {
        "unknown"
    }
    assert probe_module._candidate_ecosystems_for_path("src/main.adb") == {"ada"}
    assert probe_module._candidate_ecosystems_for_path("src/main.c") == {"c"}
    assert probe_module._candidate_ecosystems_for_path("src/Main.as") == {"actionscript"}
    assert probe_module._candidate_ecosystems_for_path(
        "bin/translate",
        repo_path=repo_path,
    ) == {"awk"}
    assert probe_module._candidate_ecosystems_for_path("lib/math.awk") == {"awk"}
    assert probe_module._candidate_ecosystems_for_path("coffee-app/src/main.coffee") == {
        "coffeescript"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "coffee-app/Cakefile",
        repo_path=repo_path,
    ) == {"coffeescript"}
    assert probe_module._candidate_ecosystems_for_path(
        "cfml-app/Application.cfc"
    ) == {"cfml"}
    assert probe_module._candidate_ecosystems_for_path(
        "cfml-app/public/index.cfm"
    ) == {"cfml"}
    assert probe_module._candidate_ecosystems_for_path(
        "cfml-app/box.json",
        repo_path=repo_path,
    ) == {"cfml"}
    assert probe_module._candidate_ecosystems_for_path(
        "database/Acme.sqlproj",
        repo_path=repo_path,
    ) == {"tsql"}
    assert probe_module._candidate_ecosystems_for_path(
        "database/dbo/Stored Procedures/LoadCustomers.sql",
        repo_path=repo_path,
    ) == {"tsql"}
    assert probe_module._candidate_ecosystems_for_path(
        "delphi-app/AcmeApp.dproj",
        repo_path=repo_path,
    ) == {"delphi"}
    assert probe_module._candidate_ecosystems_for_path(
        "delphi-app/AcmeApp.dpr",
        repo_path=repo_path,
    ) == {"delphi"}
    assert probe_module._candidate_ecosystems_for_path(
        "delphi-app/source/MainForm.pas",
        repo_path=repo_path,
    ) == {"delphi"}
    assert probe_module._candidate_ecosystems_for_path("elm-app/src/Main.elm") == {"elm"}
    assert probe_module._candidate_ecosystems_for_path("vala-app/src/main.vala") == {"vala"}
    assert probe_module._candidate_ecosystems_for_path("vala-app/vapi/demo.vapi") == {"vala"}
    assert probe_module._candidate_ecosystems_for_path("mql5-app/Experts/Main.mq5") == {"mql5"}
    assert probe_module._candidate_ecosystems_for_path("mql5-app/Include/Helper.mqh") == {"mql5"}
    assert probe_module._candidate_ecosystems_for_path("mql5-app/demo.mqproj") == {"mql5"}
    assert probe_module._candidate_ecosystems_for_path(
        "gams-app/main.gms",
        repo_path=repo_path,
    ) == {"gams"}
    assert probe_module._candidate_ecosystems_for_path(
        "gams-app/include/common.inc",
        repo_path=repo_path,
    ) == {"gams"}
    assert probe_module._candidate_ecosystems_for_path(
        "openscad-app/main.scad",
        repo_path=repo_path,
    ) == {"openscad"}
    assert probe_module._candidate_ecosystems_for_path(
        "haxe-app/build.hxml",
        repo_path=repo_path,
    ) == {"haxe"}
    assert probe_module._candidate_ecosystems_for_path(
        "haxe-app/src/demo/Main.hx",
        repo_path=repo_path,
    ) == {"haxe"}
    assert probe_module._candidate_ecosystems_for_path(
        "automation/Main.ahk",
        repo_path=repo_path,
    ) == {"autohotkey"}
    assert probe_module._candidate_ecosystems_for_path(
        "batch-app/build.bat",
        repo_path=repo_path,
    ) == {"batchfile"}
    assert probe_module._candidate_ecosystems_for_path(
        "make-app/Makefile",
        repo_path=repo_path,
    ) == {"makefile"}
    assert probe_module._candidate_ecosystems_for_path(
        "make-app/mk/common.mk",
        repo_path=repo_path,
    ) == {"makefile"}
    assert probe_module._candidate_ecosystems_for_path(
        "purescript-app/spago.yaml",
        repo_path=repo_path,
    ) == {"purescript"}
    assert probe_module._candidate_ecosystems_for_path(
        "purescript-app/src/Main.purs",
        repo_path=repo_path,
    ) == {"purescript"}
    assert probe_module._candidate_ecosystems_for_path(
        "gleam-app/gleam.toml",
        repo_path=repo_path,
    ) == {"gleam"}
    assert probe_module._candidate_ecosystems_for_path(
        "gleam-app/src/main.gleam",
        repo_path=repo_path,
    ) == {"gleam"}
    assert probe_module._candidate_ecosystems_for_path(
        "janet-app/project.janet",
        repo_path=repo_path,
    ) == {"janet"}
    assert probe_module._candidate_ecosystems_for_path(
        "janet-app/src/main.janet",
        repo_path=repo_path,
    ) == {"janet"}
    assert probe_module._candidate_ecosystems_for_path(
        "dhall-app/package.dhall",
        repo_path=repo_path,
    ) == {"dhall"}
    assert probe_module._candidate_ecosystems_for_path(
        "dhall-app/workflow.dhall",
        repo_path=repo_path,
    ) == {"dhall"}
    assert probe_module._candidate_ecosystems_for_path(
        "puppet-app/metadata.json",
        repo_path=repo_path,
    ) == {"puppet"}
    assert probe_module._candidate_ecosystems_for_path(
        "puppet-app/Puppetfile",
        repo_path=repo_path,
    ) == {"puppet"}
    assert probe_module._candidate_ecosystems_for_path(
        "puppet-app/manifests/init.pp",
        repo_path=repo_path,
    ) == {"puppet"}
    assert probe_module._candidate_ecosystems_for_path(
        "hack-app/.hhconfig",
        repo_path=repo_path,
    ) == {"hack"}
    assert probe_module._candidate_ecosystems_for_path(
        "hack-app/src/Ref.php",
        repo_path=repo_path,
    ) == {"hack"}
    assert probe_module._candidate_ecosystems_for_path(
        "hack-app/src/Vec.hack",
        repo_path=repo_path,
    ) == {"hack"}
    assert probe_module._candidate_ecosystems_for_path(
        "pascal-app/src/main.pp",
        repo_path=repo_path,
    ) == {"pascal"}
    assert probe_module._candidate_ecosystems_for_path(
        "rego-app/policy/main.rego",
        repo_path=repo_path,
    ) == {"rego"}
    assert probe_module._candidate_ecosystems_for_path(
        "rego-app/policy/lib/helpers.rego",
        repo_path=repo_path,
    ) == {"rego"}
    assert probe_module._candidate_ecosystems_for_path(
        "yara-app/rules/index.yar",
        repo_path=repo_path,
    ) == {"yara"}
    assert probe_module._candidate_ecosystems_for_path(
        "yara-app/rules/lib/helper.yar",
        repo_path=repo_path,
    ) == {"yara"}
    assert probe_module._candidate_ecosystems_for_path(
        "bitbake-app/conf/layer.conf",
        repo_path=repo_path,
    ) == {"bitbake"}
    assert probe_module._candidate_ecosystems_for_path(
        "bitbake-app/recipes-core/images/core-image-minimal.bb",
        repo_path=repo_path,
    ) == {"bitbake"}
    assert probe_module._candidate_ecosystems_for_path(
        "hcl-app/main.tf",
        repo_path=repo_path,
    ) == {"hcl"}
    assert probe_module._candidate_ecosystems_for_path(
        "hcl-app/modules/child/main.tf",
        repo_path=repo_path,
    ) == {"hcl"}
    assert probe_module._candidate_ecosystems_for_path(
        "bicep-app/bicepconfig.json",
        repo_path=repo_path,
    ) == {"bicep"}
    assert probe_module._candidate_ecosystems_for_path(
        "bicep-app/main.bicep",
        repo_path=repo_path,
    ) == {"bicep"}
    assert probe_module._candidate_ecosystems_for_path(
        "tlaplus-app/Spec.tla",
        repo_path=repo_path,
    ) == {"tlaplus"}
    assert probe_module._candidate_ecosystems_for_path(
        "agda-app/standard-library.agda-lib",
        repo_path=repo_path,
    ) == {"agda"}
    assert probe_module._candidate_ecosystems_for_path(
        "agda-app/src/Main.agda",
        repo_path=repo_path,
    ) == {"agda"}
    assert probe_module._candidate_ecosystems_for_path(
        "idris-app/demo.ipkg",
        repo_path=repo_path,
    ) == {"idris"}
    assert probe_module._candidate_ecosystems_for_path(
        "idris-app/src/Main.idr",
        repo_path=repo_path,
    ) == {"idris"}
    assert probe_module._candidate_ecosystems_for_path(
        "raku-app/META6.json",
        repo_path=repo_path,
    ) == {"raku"}
    assert probe_module._candidate_ecosystems_for_path(
        "raku-app/lib/Demo/Helper.rakumod",
        repo_path=repo_path,
    ) == {"raku"}
    assert probe_module._candidate_ecosystems_for_path(
        "nushell-app/main.nu",
        repo_path=repo_path,
    ) == {"nushell"}
    assert probe_module._candidate_ecosystems_for_path(
        "fish-app/main.fish",
        repo_path=repo_path,
    ) == {"fish"}
    assert probe_module._candidate_ecosystems_for_path(
        "fish-app/functions/helper.fish",
        repo_path=repo_path,
    ) == {"fish"}
    assert probe_module._candidate_ecosystems_for_path(
        "starlark-app/MODULE.bazel",
        repo_path=repo_path,
    ) == {"starlark"}
    assert probe_module._candidate_ecosystems_for_path(
        "starlark-app/BUILD.bazel",
        repo_path=repo_path,
    ) == {"starlark"}
    assert probe_module._candidate_ecosystems_for_path(
        "starlark-app/rules/demo.bzl",
        repo_path=repo_path,
    ) == {"starlark"}
    assert probe_module._candidate_ecosystems_for_path(
        "nix-app/flake.nix",
        repo_path=repo_path,
    ) == {"nix"}
    assert probe_module._candidate_ecosystems_for_path(
        "nix-app/nix/lib/formatter.nix",
        repo_path=repo_path,
    ) == {"nix"}
    assert probe_module._candidate_ecosystems_for_path(
        "smalltalk-app/.smalltalk.ston",
        repo_path=repo_path,
    ) == {"smalltalk"}
    assert probe_module._candidate_ecosystems_for_path(
        "smalltalk-app/src/Demo-Core/Helper.class.st",
        repo_path=repo_path,
    ) == {"smalltalk"}
    assert probe_module._candidate_ecosystems_for_path(
        "elisp-app/Cask",
        repo_path=repo_path,
    ) == {"emacslisp"}
    assert probe_module._candidate_ecosystems_for_path(
        "elisp-app/main.el",
        repo_path=repo_path,
    ) == {"emacslisp"}
    assert probe_module._candidate_ecosystems_for_path(
        "elisp-app/lisp/helper.el",
        repo_path=repo_path,
    ) == {"emacslisp"}
    assert probe_module._candidate_ecosystems_for_path("scheme-app/package.scm") == {"scheme"}
    assert probe_module._candidate_ecosystems_for_path("scheme-app/main.scm") == {"scheme"}
    assert probe_module._candidate_ecosystems_for_path("scheme-app/lib/acme/helper.sld") == {
        "scheme"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "racket-app/info.rkt",
        repo_path=repo_path,
    ) == {"racket"}
    assert probe_module._candidate_ecosystems_for_path(
        "racket-app/main.rkt",
        repo_path=repo_path,
    ) == {"racket"}
    assert probe_module._candidate_ecosystems_for_path("games/Maze.sb3") == {"scratch"}
    assert probe_module._candidate_ecosystems_for_path("imports/Legacy.xpo") == {"xpp"}
    assert probe_module._candidate_ecosystems_for_path("src/boot.asm") == {"assembly"}
    assert probe_module._candidate_ecosystems_for_path("src/zcl_math.clas.abap") == {"abap"}
    assert probe_module._candidate_ecosystems_for_path("src/main.cbl") == {"cobol"}
    assert probe_module._candidate_ecosystems_for_path("db/order_api.pkb") == {"plsql"}
    assert probe_module._candidate_ecosystems_for_path("programs/report.sas") == {"sas"}
    assert probe_module._candidate_ecosystems_for_path("src/main.sml") == {"ml"}
    assert probe_module._candidate_ecosystems_for_path("src/main.prolog") == {"prolog"}
    assert probe_module._candidate_ecosystems_for_path("logic/Main.L5X") == {"ladder"}
    assert probe_module._candidate_ecosystems_for_path("src/main.m") == {"unknown"}
    assert probe_module._candidate_ecosystems_for_path("Kernel/Helpers.wl") == {"wolfram"}
    assert probe_module._candidate_ecosystems_for_path("scripts/tree_api/tree_api.gml") == {
        "gml"
    }
    assert probe_module._candidate_ecosystems_for_path("src/family.pl", repo_path=repo_path) == {
        "prolog"
    }
    assert probe_module._candidate_ecosystems_for_path("script/app.pl", repo_path=repo_path) == {
        "perl"
    }
    assert probe_module._candidate_ecosystems_for_path("src/main.m", repo_path=repo_path) == {
        "matlab"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "Kernel/init.m",
        repo_path=repo_path,
    ) == {"wolfram"}
    assert probe_module._candidate_ecosystems_for_path(
        "ios/AppDelegate.m",
        repo_path=repo_path,
    ) == {"objectivec"}
    assert probe_module._candidate_ecosystems_for_path(
        "ios/AppDelegate.h",
        repo_path=repo_path,
    ) == {"objectivec"}
    assert probe_module._candidate_ecosystems_for_path(
        "include/io.inc",
        repo_path=repo_path,
    ) == {"assembly"}
    assert probe_module._candidate_ecosystems_for_path(
        "vb6/modMain.bas",
        repo_path=repo_path,
    ) == {"vba"}
    assert probe_module._candidate_ecosystems_for_path(
        "vb6/Form1.frm",
        repo_path=repo_path,
    ) == {"vb6"}
    assert probe_module._candidate_ecosystems_for_path(
        "vba/JsonConverter.bas",
        repo_path=repo_path,
    ) == {"vba"}
    assert probe_module._candidate_ecosystems_for_path(
        "vb6/Project1.vbp",
        repo_path=repo_path,
    ) == {"vb6"}
    assert probe_module._candidate_ecosystems_for_path("scripts/build.vbs") == {"vbscript"}
    assert probe_module._candidate_ecosystems_for_path(
        "scripts/main.wsf",
        repo_path=repo_path,
    ) == {"vbscript"}
    assert probe_module._candidate_ecosystems_for_path("automation/Helper.applescript") == {
        "applescript"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "automation/Compiled.scpt",
        repo_path=repo_path,
    ) == {"applescript"}
    assert probe_module._candidate_ecosystems_for_path("tcllib/pkgIndex.tcl") == {"tcl"}
    assert probe_module._candidate_ecosystems_for_path("tcllib/sha1.tcl") == {"tcl"}
    assert probe_module._candidate_ecosystems_for_path("qrpglesrc/ORD101.PGM.RPGLE") == {"rpg"}
    assert probe_module._candidate_ecosystems_for_path("qprotosrc/CUSTOMER.RPGLEINC") == {
        "rpg"
    }
    assert probe_module._candidate_ecosystems_for_path("lisp/acme.asd") == {"lisp"}
    assert probe_module._candidate_ecosystems_for_path(
        "lisp/app.lisp",
        repo_path=repo_path,
    ) == {"lisp"}
    assert probe_module._candidate_ecosystems_for_path(
        "foxpro/main.prg",
        repo_path=repo_path,
    ) == {"foxpro"}
    assert probe_module._candidate_ecosystems_for_path(
        "contracts/Counter.sol",
        repo_path=repo_path,
    ) == {"solidity"}
    assert probe_module._candidate_ecosystems_for_path(
        "shaders/noise.glsl",
        repo_path=repo_path,
    ) == {"glsl"}
    assert probe_module._candidate_ecosystems_for_path(
        "shaders/main.frag",
        repo_path=repo_path,
    ) == {"glsl"}
    assert probe_module._candidate_ecosystems_for_path(
        "shaders/passthrough.vert",
        repo_path=repo_path,
    ) == {"glsl"}
    assert probe_module._candidate_ecosystems_for_path(
        "_CoqProject",
        repo_path=repo_path,
    ) == {"coq"}
    assert probe_module._candidate_ecosystems_for_path(
        "theories/Main.v",
        repo_path=repo_path,
    ) == {"coq"}
    assert probe_module._candidate_ecosystems_for_path(
        "lean-app/lean-toolchain",
        repo_path=repo_path,
    ) == {"lean"}
    assert probe_module._candidate_ecosystems_for_path(
        "lean-app/Batteries/Main.lean",
        repo_path=repo_path,
    ) == {"lean"}
    assert probe_module._candidate_ecosystems_for_path("rtl/top.sv") == {"systemverilog"}
    assert probe_module._candidate_ecosystems_for_path(
        "rtl/child.v",
        repo_path=repo_path,
    ) == {"verilog"}
    assert probe_module._candidate_ecosystems_for_path(
        "rtl/defs.vh",
        repo_path=repo_path,
    ) == {"verilog"}
    assert probe_module._candidate_ecosystems_for_path(
        "vhdl/top.vhd",
        repo_path=repo_path,
    ) == {"vhdl"}
    assert probe_module._candidate_ecosystems_for_path(
        "godot/scripts/player.gd",
        repo_path=repo_path,
    ) == {"gdscript"}
    assert probe_module._candidate_ecosystems_for_path(
        "logic/Main.L5X",
        repo_path=repo_path,
    ) == {"ladder"}
    assert probe_module._candidate_ecosystems_for_path(
        "logic/Types.L5X",
        repo_path=repo_path,
    ) == {"ladder"}
    assert probe_module._candidate_ecosystems_for_path("labview/App.lvproj") == {"labview"}
    assert probe_module._candidate_ecosystems_for_path("labview/Source/Main.vi") == {"labview"}
    assert probe_module._candidate_ecosystems_for_path(
        "PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml",
        repo_path=repo_path,
    ) == {"xpp"}
    assert probe_module._candidate_ecosystems_for_path(
        "PackagesLocalDirectory/Acme/Descriptor/Acme.xml",
        repo_path=repo_path,
    ) == {"xpp"}
    assert probe_module._candidate_ecosystems_for_path(
        "labview/Controls/Config.ctl",
        repo_path=repo_path,
    ) == {"labview"}
    assert probe_module._candidate_ecosystems_for_path(
        "force-app/main/default/classes/AccountTriggerHandler.cls",
        repo_path=repo_path,
    ) == {"apex"}
    assert probe_module._candidate_ecosystems_for_path(
        "force-app/main/default/triggers/AccountTrigger.trigger",
        repo_path=repo_path,
    ) == {"apex"}


def test_sort_repository_languages_prefers_popularity_rank_before_name() -> None:
    assert sort_repository_languages(
        {"nim", "typescript", "python", "swift", "node", "dotnet", "groovy"}
    ) == [
        "typescript",
        "python",
        "node",
        "dotnet",
        "swift",
        "groovy",
        "nim",
    ]


def test_diversify_paths_by_support_root_preserves_ranked_root_order() -> None:
    assert probe_module._diversify_paths_by_support_root(
        paths=[
            "web/src/main.ts",
            "rust/src/main.rs",
            "py/src/acme/cli.py",
        ],
        support_roots={"web/src", "rust/src", "py/src"},
    ) == [
        "web/src/main.ts",
        "rust/src/main.rs",
        "py/src/acme/cli.py",
    ]


def test_support_roots_need_expansion_returns_false_when_all_roots_are_covered() -> None:
    assert (
        _support_roots_need_expansion(
            candidate_file_paths=[
                "ujson/src/ujson/AstTransformer.scala",
                "ujson/circe/src/ujson/circe/CirceJson.scala",
                "ujson/play/src/ujson/play/PlayJson.scala",
                "upack/src/upack/Msg.scala",
            ],
            support_roots=[
                "ujson/src/ujson",
                "ujson/circe/src/ujson",
                "ujson/play/src/ujson",
                "upack/src/upack",
            ],
        )
        is False
    )


def test_candidate_existing_leaf_roots_prunes_auxiliary_bin_roots(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "pkg" / "lib").mkdir(parents=True)
    (repo_path / "pkg" / "bin").mkdir(parents=True)

    assert _candidate_existing_leaf_roots(
        repo_path,
        roots={"pkg/lib", "pkg/bin"},
    ) == ["pkg/lib"]


def test_candidate_existing_leaf_roots_keeps_bin_without_sibling_code_root(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "pkg" / "bin").mkdir(parents=True)

    assert _candidate_existing_leaf_roots(
        repo_path,
        roots={"pkg/bin"},
    ) == ["pkg/bin"]


def test_candidate_existing_leaf_roots_prunes_top_level_bin_without_entrypoints(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "pkg" / "lib").mkdir(parents=True)

    assert _candidate_existing_leaf_roots(
        repo_path,
        roots={"bin", "pkg/lib"},
        entrypoint_paths={"pkg/lib/main.rb"},
    ) == ["pkg/lib"]


def test_candidate_existing_leaf_roots_keeps_top_level_bin_with_entrypoints(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "pkg" / "lib").mkdir(parents=True)

    assert _candidate_existing_leaf_roots(
        repo_path,
        roots={"bin", "pkg/lib"},
        entrypoint_paths={"bin/tool.rb", "pkg/lib/main.rb"},
    ) == ["bin", "pkg/lib"]


def test_support_roots_need_expansion_returns_true_when_any_root_is_uncovered() -> None:
    assert (
        _support_roots_need_expansion(
            candidate_file_paths=[
                "pkgs/http/lib/http.dart",
                "pkgs/http/lib/src/client.dart",
            ],
            support_roots=[
                "pkgs/http/lib",
                "pkgs/http_parser/lib",
            ],
        )
        is True
    )


def test_support_roots_requiring_expansion_ignores_auxiliary_bin_roots() -> None:
    assert (
        _support_roots_requiring_expansion(
            candidate_file_paths=[
                "pkg/lib/main.rb",
                "pkg/lib/core.rb",
            ],
            support_roots=[
                "pkg/lib",
                "pkg/bin",
            ],
        )
        == []
    )


def test_support_roots_requiring_expansion_returns_only_uncovered_roots() -> None:
    assert _support_roots_requiring_expansion(
        candidate_file_paths=[
            "pkgs/http/lib/http.dart",
            "pkgs/http/lib/src/client.dart",
        ],
        support_roots=[
            "pkgs/http/lib",
            "pkgs/http_parser/lib",
            "pkgs/http_profile/lib",
        ],
    ) == [
        "pkgs/http_parser/lib",
        "pkgs/http_profile/lib",
    ]


def test_candidate_existing_leaf_roots_drops_parent_roots_when_children_exist(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "leaf-support-roots-repo"
    (repo_path / "app" / "src" / "main" / "groovy").mkdir(parents=True)
    (repo_path / "app" / "src" / "main" / "java").mkdir(parents=True)

    leaf_roots = _candidate_existing_leaf_roots(
        repo_path,
        roots={"app", "app/src", "app/src/main/groovy", "app/src/main/java"},
    )

    assert leaf_roots == ["app/src/main/groovy", "app/src/main/java"]


def test_default_probe_include_patterns_cover_generic_src_repos(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "generic-src-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "node_modules" / "pkg").mkdir(parents=True)
    (repo_path / "src" / "main.tsx").write_text(
        "export const App = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text('{"name":"generic-src"}\n', encoding="utf-8")
    (repo_path / "node_modules" / "pkg" / "index.ts").write_text(
        "export const ignored = 1;\n",
        encoding="utf-8",
    )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=[],
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        max_files=32,
    )

    assert "src/main.tsx" in candidate_paths
    assert "package.json" in candidate_paths
    assert all(not path.startswith("node_modules/") for path in candidate_paths)


def test_default_probe_include_patterns_cover_generic_ruby_and_java_repos(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "polyglot-probe-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "src" / "main" / "java" / "com" / "acme").mkdir(parents=True)
    (repo_path / "app" / "worker.rb").write_text("puts 'ok'\n", encoding="utf-8")
    (repo_path / "src" / "main" / "java" / "com" / "acme" / "Main.java").write_text(
        "class Main {}\n",
        encoding="utf-8",
    )
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "pom.xml").write_text("<project />\n", encoding="utf-8")
    (repo_path / "build.gradle").write_text("plugins {}\n", encoding="utf-8")

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=[],
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        max_files=32,
    )

    assert "app/worker.rb" in candidate_paths
    assert "src/main/java/com/acme/Main.java" in candidate_paths
    assert "Gemfile" in candidate_paths
    assert "pom.xml" in candidate_paths
    assert "build.gradle" in candidate_paths


def test_default_probe_include_patterns_cover_generic_cpp_repos(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cpp-probe-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include" / "acme").mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text("add_library(acme src/main.cpp)\n", encoding="utf-8")
    (repo_path / "src" / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
    (repo_path / "include" / "acme" / "core.hpp").write_text("#pragma once\n", encoding="utf-8")

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=[],
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        max_files=32,
    )

    assert "CMakeLists.txt" in candidate_paths
    assert "src/main.cpp" in candidate_paths
    assert "include/acme/core.hpp" in candidate_paths


def test_operational_seed_paths_without_diagnostics_prefers_entrypoints(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "frontend-repo"
    (repo_path / "src" / "pages").mkdir(parents=True)
    (repo_path / "src" / "components" / "ui").mkdir(parents=True)
    (repo_path / "src" / "main.tsx").write_text("export const bootstrap = 1;\n", encoding="utf-8")
    (repo_path / "src" / "App.tsx").write_text("export const App = () => null;\n", encoding="utf-8")
    (repo_path / "src" / "pages" / "Index.tsx").write_text(
        "export const Index = () => null;\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "components" / "ui" / "button.tsx").write_text(
        "export const Button = () => null;\n",
        encoding="utf-8",
    )

    seed_paths = _derive_operational_seed_paths_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert "src/main.tsx" in seed_paths
    assert "src/App.tsx" in seed_paths
    assert "src/pages/Index.tsx" in seed_paths


def test_operational_seed_plan_without_diagnostics_uses_generic_frontend_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "frontend-profile-repo"
    (repo_path / "src" / "pages").mkdir(parents=True)
    (repo_path / "src" / "components" / "ui").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        '{\n'
        '  "name": "frontend-profile",\n'
        '  "scripts": { "dev": "vite", "build": "vite build" }\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "vite.config.js").write_text(
        "export default {};\n",
        encoding="utf-8",
    )
    (repo_path / "tsconfig.app.json").write_text(
        '{\n'
        '  "compilerOptions": {\n'
        '    "baseUrl": ".",\n'
        '    "paths": { "@/*": ["./src/*"] }\n'
        "  },\n"
        '  "include": ["src"]\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.tsx").write_text("export const bootstrap = 1;\n", encoding="utf-8")
    (repo_path / "src" / "App.tsx").write_text("export const App = () => null;\n", encoding="utf-8")
    (repo_path / "src" / "pages" / "Index.tsx").write_text(
        "export const Index = () => null;\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "components" / "ui" / "button.tsx").write_text(
        "export const Button = () => null;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert "src/main.tsx" in seed_plan["entrypoint_files"]
    assert "src/App.tsx" in seed_plan["entrypoint_files"]
    assert "src/pages/Index.tsx" in seed_plan["entrypoint_files"]
    assert "vite.config.js" not in seed_plan["entrypoint_files"]
    assert "src" in seed_plan["support_roots"]
    assert "package.json" in seed_plan["config_paths"]
    assert "tsconfig.app.json" in seed_plan["config_paths"]
    assert "node" in seed_plan["detected_ecosystems"]
    assert "typescript" in seed_plan["detected_ecosystems"]


def test_operational_seed_plan_without_diagnostics_does_not_expand_passive_package_json_app_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "clojure-passive-package-json-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "app" / "acme").mkdir(parents=True)
    (repo_path / "deps.edn").write_text(
        '{:paths ["src"]}\n',
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        json.dumps(
            {
                "name": "acme",
                "devDependencies": {
                    "shadow-cljs": "^3.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.cljc").write_text(
        "(ns acme.core)\n(def value 1)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "helper.cljc").write_text(
        "(ns acme.helper)\n(def helper 1)\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "acme" / "demo.cljc").write_text(
        "(ns acme.demo)\n(def demo 1)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "clojure" in seed_plan["detected_ecosystems"]
    assert "node" in seed_plan["detected_ecosystems"]
    assert "src" in seed_plan["support_roots"]
    assert "app" not in seed_plan["support_roots"]
    assert "src/acme/core.cljc" in seed_plan["entrypoint_files"]
    assert "app/acme/demo.cljc" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_leaf_support_root_code(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nested-polyglot-profile-repo"
    (repo_path / "website" / "pages").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "website" / "package.json").write_text(
        '{\n'
        '  "name": "nested-polyglot-profile",\n'
        '  "scripts": { "dev": "next dev" }\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "website" / "next.config.js").write_text(
        "module.exports = {};\n",
        encoding="utf-8",
    )
    (repo_path / "website" / "theme.config.jsx").write_text(
        "export default {};\n",
        encoding="utf-8",
    )
    (repo_path / "website" / "pages" / "_app.tsx").write_text(
        "export default function App() { return null; }\n",
        encoding="utf-8",
    )
    (repo_path / "build.zig").write_text(
        "const std = @import(\"std\");\n"
        "pub fn build(b: *std.Build) void {\n"
        "  _ = b;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.zig").write_text(
        "pub fn main() void {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "node" in seed_plan["detected_ecosystems"]
    assert "zig" in seed_plan["detected_ecosystems"]
    assert "website/pages/_app.tsx" in seed_plan["entrypoint_files"]
    assert "src/main.zig" in seed_plan["entrypoint_files"]
    assert "website/next.config.js" not in seed_plan["entrypoint_files"]
    assert "website/theme.config.jsx" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_pyproject_scripts(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "python-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "acme"\n'
        "[project.scripts]\n"
        'acme = "acme.cli:main"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "cli.py").write_text(
        "def main() -> int:\n    return 0\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert "src/acme/cli.py" in seed_plan["entrypoint_files"]
    assert "src" in seed_plan["support_roots"]
    assert "pyproject.toml" in seed_plan["config_paths"]
    assert "python" in seed_plan["detected_ecosystems"]


def test_operational_seed_plan_without_diagnostics_orders_detected_ecosystems_by_rank(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mixed-ranked-profile-repo"
    (repo_path / "web" / "src").mkdir(parents=True)
    (repo_path / "py" / "src" / "acme").mkdir(parents=True)
    (repo_path / "rust" / "src").mkdir(parents=True)
    (repo_path / "web" / "package.json").write_text(
        '{\n'
        '  "name": "mixed-ranked-profile",\n'
        '  "scripts": { "dev": "vite" }\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "web" / "tsconfig.json").write_text(
        '{\n'
        '  "compilerOptions": {\n'
        '    "baseUrl": ".",\n'
        '    "paths": { "@/*": ["./src/*"] }\n'
        "  },\n"
        '  "include": ["src"]\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "web" / "src" / "main.ts").write_text(
        "export const bootstrap = 1;\n",
        encoding="utf-8",
    )
    (repo_path / "py" / "pyproject.toml").write_text(
        "[project]\n"
        'name = "acme"\n'
        "[project.scripts]\n"
        'acme = "acme.cli:main"\n',
        encoding="utf-8",
    )
    (repo_path / "py" / "src" / "acme" / "cli.py").write_text(
        "def main() -> int:\n    return 0\n",
        encoding="utf-8",
    )
    (repo_path / "rust" / "Cargo.toml").write_text(
        "[package]\n"
        'name = "ranked-rust"\n'
        'version = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "rust" / "src" / "main.rs").write_text(
        "fn main() {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=256,
    )

    assert seed_plan["detected_ecosystems"] == ["typescript", "python", "node", "rust"]
    assert seed_plan["entrypoint_files"][:3] == [
        "web/src/main.ts",
        "py/src/acme/cli.py",
        "rust/src/main.rs",
    ]


def test_operational_seed_plan_without_diagnostics_uses_pubspec_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dart-profile-repo"
    (repo_path / "lib" / "src").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "pubspec.yaml").write_text(
        "name: acme_client\n"
        "environment:\n"
        '  sdk: ">=3.0.0 <4.0.0"\n',
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme_client.dart").write_text(
        "export 'src/client.dart' show Client;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "src" / "client.dart").write_text(
        "class Client {}\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "acme_client.dart").write_text(
        "import 'package:acme_client/acme_client.dart' show Client;\n"
        "Client run() => Client();\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "acme_client_test.dart").write_text(
        "void main() {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "dart" in seed_plan["detected_ecosystems"]
    assert "pubspec.yaml" in seed_plan["config_paths"]
    assert any(root in seed_plan["support_roots"] for root in {"lib", "lib/Demo"})
    assert "bin" in seed_plan["support_roots"]
    assert "lib/acme_client.dart" in seed_plan["entrypoint_files"]
    assert "bin/acme_client.dart" in seed_plan["entrypoint_files"]
    assert "test/acme_client_test.dart" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_primary_dart_workspace_ecosystem(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dart-workspace-profile-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "pkgs" / "core" / "lib").mkdir(parents=True)
    (repo_path / "pkgs" / "example" / "android").mkdir(parents=True)
    (repo_path / "pkgs" / "example" / "windows" / "runner").mkdir(parents=True)
    (repo_path / "pkgs" / "example" / "linux").mkdir(parents=True)
    (repo_path / "pubspec.yaml").write_text(
        "name: acme_workspace\n"
        "workspace:\n"
        "  - pkgs/core\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme_workspace.dart").write_text(
        "export 'package:core/core.dart';\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "core" / "pubspec.yaml").write_text(
        "name: core\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "core" / "lib" / "core.dart").write_text(
        "class Core {}\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "example" / "android" / "build.gradle").write_text(
        "plugins { id 'com.android.application' }\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "example" / "windows" / "runner" / "main.cpp").write_text(
        "int main() { return 0; }\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "example" / "linux" / "main.cc").write_text(
        "int main() { return 0; }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=256,
    )

    assert seed_plan["detected_ecosystems"][:4] == ["java", "cpp", "dart", "groovy"]
    assert seed_plan["operational_ecosystems"][0] == "dart"
    assert seed_plan["entrypoint_files"][0] == "lib/acme_workspace.dart"
    assert "pkgs/core/lib/core.dart" in seed_plan["entrypoint_files"][:3]
    assert "pkgs/example/windows/runner/main.cpp" not in seed_plan["entrypoint_files"][:2]


def test_operational_seed_plan_without_diagnostics_uses_clojure_deps_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "clojure-deps-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "deps.edn").write_text(
        '{:paths ["src"] :main acme.core}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.clj").write_text(
        "(ns acme.core)\n(defn run [] :ok)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "util.clj").write_text(
        "(ns acme.util)\n(defn helper [] :ok)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["clojure"]
    assert "deps.edn" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme/core.clj" in seed_plan["entrypoint_files"]
    assert "src/acme/util.clj" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_clojure_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "clojure-project-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "project.clj").write_text(
        '(defproject acme/core "0.1.0" :main acme.core :source-paths ["src"])\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.clj").write_text(
        "(ns acme.core)\n(defn run [] :ok)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["clojure"]
    assert "project.clj" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme/core.clj" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_lua_rockspec_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lua-rockspec-profile-repo"
    (repo_path / "lua" / "acme").mkdir(parents=True)
    (repo_path / "acme-scm-1.rockspec").write_text(
        'package = "acme"\n'
        'build = { modules = { ["acme.init"] = "lua/acme/init.lua", ["acme.util"] = "lua/acme/util.lua" } }\n',
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "init.lua").write_text(
        "local M = {}\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "util.lua").write_text(
        "local M = {}\nfunction M.helper() return 'ok' end\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "spec").mkdir(parents=True)
    (repo_path / "spec" / "acme_spec.lua").write_text(
        "return true\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["lua"]
    assert "acme-scm-1.rockspec" in seed_plan["config_paths"]
    assert "lua" in seed_plan["support_roots"]
    assert "lua/acme/init.lua" in seed_plan["entrypoint_files"]
    assert "lua/acme/util.lua" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_luau_profiles(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "luau-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "package.json").write_text('{"name":"luau-profile-repo","private":true}', encoding="utf-8")
    (repo_path / "default.project.json").write_text(
        '{\n  "name": "jecs",\n  "tree": {\n    "$path": "src/jecs.luau"\n  }\n}\n',
        encoding="utf-8",
    )
    (repo_path / "wally.toml").write_text(
        "[package]\nname = 'ukendio/jecs'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "jecs.luau").write_text(
        "--!strict\nlocal M = {}\nfunction M.helper()\n  return 'ok'\nend\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "spec.luau").write_text(
        "--!strict\nreturn {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["node", "luau"]
    assert seed_plan["operational_ecosystems"][0] == "luau"
    assert "default.project.json" in seed_plan["config_paths"]
    assert "wally.toml" in seed_plan["config_paths"]
    assert "package.json" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/jecs.luau" in seed_plan["entrypoint_files"]
    assert "test/spec.luau" not in seed_plan["entrypoint_files"]
    assert "src/jecs.luau" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_prefers_manifest_ecosystem_code(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lua-mixed-profile-repo"
    (repo_path / "doc").mkdir(parents=True)
    (repo_path / "fun-scm-1.rockspec").write_text(
        'package = "fun"\n'
        'build = { modules = { ["fun"] = "fun.lua" } }\n',
        encoding="utf-8",
    )
    (repo_path / "fun.lua").write_text(
        "local M = {}\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "doc" / "conf.py").write_text("project = 'fun'\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["lua"]
    assert "fun.lua" in seed_plan["entrypoint_files"]
    assert "doc/conf.py" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_shell_repo_conventions(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shell-profile-repo"
    (repo_path / "plugins" / "git").mkdir(parents=True)
    (repo_path / "themes").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "plugins" / "git" / "git.plugin.zsh").write_text(
        "git_main() { echo git; }\n",
        encoding="utf-8",
    )
    (repo_path / "themes" / "acme.zsh-theme").write_text(
        "prompt_acme_setup() { echo theme; }\n",
        encoding="utf-8",
    )
    (repo_path / "install.sh").write_text(
        "install_main() { echo install; }\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "install_test.sh").write_text(
        "test_install() { :; }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["shell"]
    assert "install.sh" in seed_plan["entrypoint_files"]
    assert "plugins/git/git.plugin.zsh" in seed_plan["candidate_file_paths"]
    assert "themes/acme.zsh-theme" in seed_plan["candidate_file_paths"]
    assert "test/install_test.sh" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_root_shell_entrypoints(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shell-root-entrypoint-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "toolkit.sh").write_text(
        "main() {\n"
        "  . ./lib/core.zsh\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "core.zsh").write_text("helper() { echo core; }\n", encoding="utf-8")
    (repo_path / "lib" / "helper.zsh").write_text("util() { echo util; }\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["shell"]
    assert seed_plan["entrypoint_files"][0] == "toolkit.sh"


def test_operational_seed_plan_without_diagnostics_uses_powershell_manifest_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "powershell-profile-repo"
    (repo_path / "Public").mkdir(parents=True)
    (repo_path / "Private").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Acme.psd1").write_text(
        "@{\n"
        "  RootModule = 'Acme.psm1'\n"
        "  NestedModules = @('Public/Invoke-Acme.ps1')\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Acme.psm1").write_text(
        '. "$PSScriptRoot/Private/Helpers.ps1"\n',
        encoding="utf-8",
    )
    (repo_path / "Public" / "Invoke-Acme.ps1").write_text(
        "function Invoke-Acme { Get-Helper }\n",
        encoding="utf-8",
    )
    (repo_path / "Private" / "Helpers.ps1").write_text(
        "function Get-Helper { return 'ok' }\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "Acme.Tests.ps1").write_text(
        "Describe 'Acme' {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["powershell"]
    assert "Acme.psm1" in seed_plan["entrypoint_files"]
    assert "Public" in seed_plan["support_roots"]
    assert "Private" in seed_plan["support_roots"]
    assert "tests/Acme.Tests.ps1" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_rebar_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "erlang-rebar-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "rebar.config").write_text("{erl_opts, [debug_info]}.\n", encoding="utf-8")
    (repo_path / "src" / "acme.erl").write_text(
        "-module(acme).\n-export([run/0]).\nrun() -> ok.\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "acme_SUITE.erl").write_text(
        "-module(acme_SUITE).\n-export([all/0]).\nall() -> [].\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["erlang"]
    assert "rebar.config" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.erl" in seed_plan["entrypoint_files"]
    assert "test/acme_SUITE.erl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_erlang_mk_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "erlang-mk-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "erlang.mk").write_text("PROJECT = acme\n", encoding="utf-8")
    (repo_path / "src" / "acme.erl").write_text(
        "-module(acme).\n-export([run/0]).\nrun() -> ok.\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "acme_SUITE.erl").write_text(
        "-module(acme_SUITE).\n-export([all/0]).\nall() -> [].\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["erlang"]
    assert "erlang.mk" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.erl" in seed_plan["entrypoint_files"]
    assert "test/acme_SUITE.erl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_erlang_app_src_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "erlang-app-src-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "src" / "acme.app.src").write_text(
        "{application, acme, [{modules, [acme]}]}.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.erl").write_text(
        "-module(acme).\n-export([run/0]).\nrun() -> ok.\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "acme_SUITE.erl").write_text(
        "-module(acme_SUITE).\n-export([all/0]).\nall() -> [].\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["erlang"]
    assert "src/acme.app.src" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.erl" in seed_plan["entrypoint_files"]
    assert "test/acme_SUITE.erl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_nimble_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nimble-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "acme.nimble").write_text("version = \"0.1.0\"\n", encoding="utf-8")
    (repo_path / "src" / "acme.nim").write_text("proc run*() = discard\n", encoding="utf-8")
    (repo_path / "src" / "acme" / "util.nim").write_text(
        "proc helper*() = discard\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "acme_test.nim").write_text(
        "discard\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["nim"]
    assert "acme.nimble" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.nim" in seed_plan["entrypoint_files"]
    assert "src/acme/util.nim" in seed_plan["candidate_file_paths"]
    assert "tests/acme_test.nim" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_root_package_dir_for_nimble_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nimble-root-package-repo"
    (repo_path / "acme" / "private").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "acme.nimble").write_text("version = \"0.1.0\"\n", encoding="utf-8")
    (repo_path / "acme.nim").write_text("proc run*() = discard\n", encoding="utf-8")
    (repo_path / "acme" / "routing.nim").write_text(
        "proc route*() = discard\n",
        encoding="utf-8",
    )
    (repo_path / "acme" / "private" / "util.nim").write_text(
        "proc helper*() = discard\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "suite.nim").write_text("discard\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["nim"]
    assert "acme.nimble" in seed_plan["config_paths"]
    assert "acme" in seed_plan["support_roots"]
    assert "acme.nim" in seed_plan["entrypoint_files"]
    assert "acme/routing.nim" in seed_plan["entrypoint_files"]
    assert "acme/private/util.nim" in seed_plan["entrypoint_files"]
    assert "tests/suite.nim" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_config_nims_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nim-config-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "config.nims").write_text("switch(\"opt\", \"speed\")\n", encoding="utf-8")
    (repo_path / "src" / "acme.nim").write_text("proc run*() = discard\n", encoding="utf-8")
    (repo_path / "tests" / "suite.nim").write_text("discard\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["nim"]
    assert "config.nims" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.nim" in seed_plan["entrypoint_files"]
    assert "tests/suite.nim" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_ignores_nested_non_operational_nim_configs(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nim-nested-config-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "acme.nimble").write_text("version = \"0.1.0\"\n", encoding="utf-8")
    (repo_path / "tests" / "config.nims").write_text(
        "switch(\"warning\", \"off\")\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.nim").write_text("proc run*() = discard\n", encoding="utf-8")
    (repo_path / "src" / "acme" / "util.nim").write_text(
        "proc helper*() = discard\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "example.nim").write_text("discard\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "nim" in seed_plan["detected_ecosystems"]
    assert "acme.nimble" in seed_plan["config_paths"]
    assert "tests/config.nims" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "tests" not in seed_plan["support_roots"]
    assert "src/acme.nim" in seed_plan["entrypoint_files"]
    assert "tests/example.nim" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_dune_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ocaml-dune-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "dune-project").write_text("(lang dune 3.0)\n", encoding="utf-8")
    (repo_path / "src" / "dune").write_text("(library (name acme))\n", encoding="utf-8")
    (repo_path / "src" / "main.ml").write_text("let run () = Util.helper ()\n", encoding="utf-8")
    (repo_path / "src" / "util.ml").write_text("let helper () = 1\n", encoding="utf-8")
    (repo_path / "test" / "dune").write_text("(test (name main))\n", encoding="utf-8")
    (repo_path / "test" / "main.ml").write_text("let () = ()\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["ocaml"]
    assert "dune-project" in seed_plan["config_paths"]
    assert "src/dune" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "test" not in seed_plan["support_roots"]
    assert "src/main.ml" in seed_plan["entrypoint_files"]
    assert "src/util.ml" in seed_plan["entrypoint_files"]
    assert "test/main.ml" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_opam_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ocaml-opam-profile-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "acme.opam").write_text("opam-version: \"2.0\"\n", encoding="utf-8")
    (repo_path / "lib" / "acme.ml").write_text("let run () = Util.helper ()\n", encoding="utf-8")
    (repo_path / "lib" / "util.ml").write_text("let helper () = 1\n", encoding="utf-8")
    (repo_path / "test" / "acme_test.ml").write_text("let () = ()\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["ocaml"]
    assert "acme.opam" in seed_plan["config_paths"]
    assert any(root in seed_plan["support_roots"] for root in {"lib", "lib/Demo"})
    assert "lib/acme.ml" in seed_plan["entrypoint_files"]
    assert "lib/util.ml" in seed_plan["candidate_file_paths"]
    assert "test/acme_test.ml" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_inferrs_manifestless_ocaml_ecosystem(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "manifestless-ocaml-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "src" / "main.ml").write_text("let run () = Util.helper ()\n", encoding="utf-8")
    (repo_path / "src" / "util.ml").write_text("let helper () = 1\n", encoding="utf-8")
    (repo_path / "test" / "main.ml").write_text("let () = ()\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["ocaml"]
    assert "src/main.ml" in seed_plan["entrypoint_files"]
    assert "test/main.ml" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_cpanfile_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "perl-cpanfile-profile-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "t").mkdir(parents=True)
    (repo_path / "cpanfile").write_text("requires 'strict';\n", encoding="utf-8")
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\nsub run { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Util.pm").write_text(
        "package My::Util;\nsub helper { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "t" / "main.t").write_text("use Test::More;\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["perl"]
    assert "cpanfile" in seed_plan["config_paths"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/My/Main.pm" in seed_plan["entrypoint_files"]
    assert "lib/My/Util.pm" in seed_plan["candidate_file_paths"]
    assert "t/main.t" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_makefile_pl_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "perl-makefile-pl-profile-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "script").mkdir(parents=True)
    (repo_path / "Makefile.PL").write_text("use ExtUtils::MakeMaker;\n", encoding="utf-8")
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\nsub run { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "script" / "app.pl").write_text(
        "use My::Main;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["perl"]
    assert "Makefile.PL" in seed_plan["config_paths"]
    assert "lib" in seed_plan["support_roots"]
    assert "script" in seed_plan["support_roots"]
    assert "lib/My/Main.pm" in seed_plan["entrypoint_files"]
    assert "script/app.pl" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_prolog_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "prolog-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "family.pl").write_text(
        ":- module(family, [ancestor/2, parent/2]).\n"
        "parent(alice, bob).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.pl").write_text(
        ":- module(main, [run/0]).\n"
        ":- use_module('family.pl', [ancestor/2]).\n"
        "run :- ancestor(alice, bob).\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main_test.pl").write_text(
        ":- module(main_test, [run_test/0]).\n"
        "run_test :- true.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["prolog"]
    assert "src/main.pl" in seed_plan["entrypoint_files"]
    assert "src/family.pl" in seed_plan["candidate_file_paths"]
    assert "tests/main_test.pl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_mlb_profile(tmp_path: Path) -> None:
    repo_path = tmp_path / "ml-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "project.mlb").write_text(
        "src/Util.sml\n"
        "src/Main.sml\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Util.sml").write_text(
        "structure Util = struct\n"
        "fun helper () = 1\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.sml").write_text(
        "structure Main = struct\n"
        "open Util\n"
        "val run = helper ()\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "MainTest.sml").write_text(
        "structure MainTest = struct\n"
        "val run = 0\n"
        "end\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["ml"]
    assert "project.mlb" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Main.sml" in seed_plan["entrypoint_files"]
    assert "src/Util.sml" in seed_plan["candidate_file_paths"]
    assert "tests/MainTest.sml" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_r_description_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "r-description-profile-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "tests" / "testthat").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    (repo_path / "R" / "main.R").write_text(
        "run <- function() {\n  helper()\n}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "helper.R").write_text(
        "helper <- function() {\n  1\n}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "testthat" / "test-main.R").write_text(
        "test_that('run works', { expect_true(TRUE) })\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["r"]
    assert "DESCRIPTION" in seed_plan["config_paths"]
    assert "NAMESPACE" in seed_plan["config_paths"]
    assert "R" in seed_plan["support_roots"]
    assert "R/main.R" in seed_plan["entrypoint_files"]
    assert "R/helper.R" in seed_plan["candidate_file_paths"]
    assert "tests/testthat/test-main.R" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_primary_r_code_over_auxiliary_tooling(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "r-primary-with-tooling-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "inst" / "www" / "shared" / "bootstrap" / "js").mkdir(parents=True)
    (repo_path / "srcts" / "types" / "extras").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    for index in range(10):
        (repo_path / "R" / f"module_{index}.R").write_text(
            f"module_{index} <- function() {{\n  {index}\n}}\n",
            encoding="utf-8",
        )
    (repo_path / "package.json").write_text(
        json.dumps(
            {
                "name": "@acme/pkg",
                "types": "srcts/types/extras/global.d.ts",
                "scripts": {
                    "build": "tsx srcts/build/index.ts",
                },
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "tsconfig.json").write_text(
        json.dumps(
            {
                "include": [
                    "srcts/src/**/*.ts",
                    "srcts/build/*.ts",
                ]
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "inst" / "www" / "shared" / "bootstrap" / "js" / "bootstrap.js").write_text(
        "window.bootstrap = true;\n",
        encoding="utf-8",
    )
    (repo_path / "srcts" / "types" / "extras" / "global.d.ts").write_text(
        "declare global {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "r" in seed_plan["detected_ecosystems"]
    assert "node" in seed_plan["detected_ecosystems"]
    assert "typescript" in seed_plan["detected_ecosystems"]
    assert seed_plan["entrypoint_files"]
    assert all(path.startswith("R/") for path in seed_plan["entrypoint_files"])
    assert "srcts/types/extras/global.d.ts" not in seed_plan["entrypoint_files"]
    assert "inst/www/shared/bootstrap/js/bootstrap.js" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_julia_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "julia-project-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "Project.toml").write_text(
        'name = "Acme"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "Manifest.toml").write_text("# generated\n", encoding="utf-8")
    (repo_path / "src" / "Acme.jl").write_text(
        'module Acme\ninclude("Helper.jl")\nend\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.jl").write_text("helper() = 1\n", encoding="utf-8")
    (repo_path / "test" / "runtests.jl").write_text("using Test\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["julia"]
    assert "Project.toml" in seed_plan["config_paths"]
    assert "Manifest.toml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Acme.jl" in seed_plan["entrypoint_files"]
    assert "src/Helper.jl" in seed_plan["candidate_file_paths"]
    assert "test/runtests.jl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_shard_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "crystal-shard-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "spec").mkdir(parents=True)
    (repo_path / "shard.yml").write_text(
        "name: acme\n"
        "version: 0.1.0\n"
        "targets:\n"
        "  acme:\n"
        "    main: src/acme.cr\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.cr").write_text(
        'require "./acme/*"\nmodule Acme\nend\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "helper.cr").write_text(
        "module Acme::Helper\nend\n",
        encoding="utf-8",
    )
    (repo_path / "spec" / "acme_spec.cr").write_text(
        "describe Acme do\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src", "shard.yml"],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["crystal"]
    assert "shard.yml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.cr" in seed_plan["entrypoint_files"]
    assert "src/acme/helper.cr" in seed_plan["candidate_file_paths"]
    assert "spec/acme_spec.cr" not in seed_plan["entrypoint_files"]


def test_repo_profile_candidate_paths_include_uppercase_r_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "r-candidate-paths-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "main.R").write_text(
        "run <- function() {\n  1\n}\n",
        encoding="utf-8",
    )

    candidate_paths = _repo_profile_candidate_paths(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "R/main.R" in candidate_paths


def test_repo_profile_config_paths_discovers_nested_pubspec_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "dart-workspace-config-repo"
    (repo_path / "pkgs" / "app").mkdir(parents=True)
    (repo_path / "pkgs" / "http").mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "pubspec.yaml").write_text(
        "name: http\n",
        encoding="utf-8",
    )

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=[],
    )

    assert config_paths == [
        "pkgs/app/pubspec.yaml",
        "pkgs/http/pubspec.yaml",
    ]


def test_repo_profile_config_paths_discovers_tsconfig_variants(tmp_path: Path) -> None:
    repo_path = tmp_path / "tsconfig-variant-config-repo"
    (repo_path / "packages" / "web").mkdir(parents=True)
    (repo_path / "tsconfig.base.json").write_text("{}", encoding="utf-8")
    (repo_path / "packages" / "web" / "tsconfig.app.json").write_text(
        "{}",
        encoding="utf-8",
    )

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=[],
    )

    assert config_paths == [
        "packages/web/tsconfig.app.json",
        "tsconfig.base.json",
    ]


def test_operational_seed_plan_without_diagnostics_discovers_nested_pubspec_workspace_profiles(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dart-workspace-profile-repo"
    (repo_path / "pkgs" / "app" / "lib").mkdir(parents=True)
    (repo_path / "pkgs" / "http" / "lib" / "src").mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "pubspec.yaml").write_text(
        "name: http\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "app" / "lib" / "app.dart").write_text(
        "import 'package:http/http.dart' show Client;\n\n"
        "String run() => Client().ping();\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "http.dart").write_text(
        "export 'src/client.dart' show Client;\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "src" / "client.dart").write_text(
        "class Client {\n"
        "  String ping() => 'ok';\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=256,
    )

    assert seed_plan["detected_ecosystems"] == ["dart"]
    assert "pkgs/app/pubspec.yaml" in seed_plan["config_paths"]
    assert "pkgs/http/pubspec.yaml" in seed_plan["config_paths"]
    assert "pkgs/http/lib/http.dart" in seed_plan["candidate_file_paths"]
    assert "pkgs/http/lib/src/client.dart" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_profile_roots_for_initial_candidate_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "dart-profile-seeded-candidate-repo"
    (repo_path / "pkgs" / "app" / "lib").mkdir(parents=True)
    (repo_path / "pkgs" / "http" / "lib" / "src").mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "pubspec.yaml").write_text(
        "name: http\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "app" / "lib" / "app.dart").write_text(
        "import 'package:http/http.dart' show Client;\n"
        "String run() => Client().ping();\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "http.dart").write_text(
        "export 'src/client.dart' show Client;\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "src" / "client.dart").write_text(
        "class Client {\n"
        "  String ping() => 'ok';\n"
        "}\n",
        encoding="utf-8",
    )

    candidate_calls: list[dict[str, list[str]]] = []
    original_candidate_repository_file_paths = probe_module._candidate_repository_file_paths

    def _recording_candidate_repository_file_paths(
        *,
        repo_path: Path,
        seed_paths: list[str],
        bridge_paths: list[str],
        include_patterns: list[str],
        max_files: int,
    ) -> list[str]:
        candidate_calls.append(
            {
                "seed_paths": list(seed_paths),
                "bridge_paths": list(bridge_paths),
            }
        )
        return original_candidate_repository_file_paths(
            repo_path=repo_path,
            seed_paths=seed_paths,
            bridge_paths=bridge_paths,
            include_patterns=include_patterns,
            max_files=max_files,
        )

    monkeypatch.setattr(
        probe_module,
        "_candidate_repository_file_paths",
        _recording_candidate_repository_file_paths,
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert candidate_calls
    assert "pkgs/app/lib/app.dart" in candidate_calls[0]["seed_paths"]
    assert "pkgs/app/lib" in candidate_calls[0]["bridge_paths"]
    assert "pkgs/http/lib" in candidate_calls[0]["bridge_paths"]
    assert candidate_calls[0]["bridge_paths"] != ["."]
    assert "pkgs/http/lib/src/client.dart" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_keeps_later_workspace_entrypoints_in_candidates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dart-workspace-candidates-repo"
    app_lib_dir = repo_path / "pkgs" / "app" / "lib"
    parser_lib_dir = repo_path / "pkgs" / "http_parser" / "lib"
    parser_src_dir = parser_lib_dir / "src"
    app_lib_dir.mkdir(parents=True)
    parser_src_dir.mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http_parser" / "pubspec.yaml").write_text(
        "name: http_parser\n",
        encoding="utf-8",
    )
    (app_lib_dir / "app.dart").write_text(
        "import 'package:http_parser/http_parser.dart';\n"
        "String run() => MediaType.text;\n",
        encoding="utf-8",
    )
    for index in range(40):
        (app_lib_dir / f"worker_{index}.dart").write_text(
            f"int worker{index}() => {index};\n",
            encoding="utf-8",
        )
    (parser_lib_dir / "http_parser.dart").write_text(
        "export 'src/media_type.dart';\n",
        encoding="utf-8",
    )
    (parser_src_dir / "media_type.dart").write_text(
        "class MediaType {\n"
        "  static const String text = 'text/plain';\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=32,
    )

    assert "pkgs/http_parser/lib/http_parser.dart" in seed_plan["candidate_file_paths"]
    assert "pkgs/http_parser/lib/src/media_type.dart" in seed_plan["candidate_file_paths"]
    assert "pkgs/http_parser/lib/http_parser.dart" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_seeds_support_scan_from_entrypoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "dart-support-scan-seeds-repo"
    app_lib_dir = repo_path / "pkgs" / "app" / "lib"
    parser_lib_dir = repo_path / "pkgs" / "http_parser" / "lib"
    parser_src_dir = parser_lib_dir / "src"
    app_lib_dir.mkdir(parents=True)
    parser_src_dir.mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http_parser" / "pubspec.yaml").write_text(
        "name: http_parser\n",
        encoding="utf-8",
    )
    (app_lib_dir / "app.dart").write_text(
        "import 'package:http_parser/http_parser.dart';\n"
        "String run() => MediaType.text;\n",
        encoding="utf-8",
    )
    for index in range(96):
        (app_lib_dir / f"worker_{index}.dart").write_text(
            f"int worker{index}() => {index};\n",
            encoding="utf-8",
        )
    (parser_lib_dir / "http_parser.dart").write_text(
        "export 'src/media_type.dart';\n",
        encoding="utf-8",
    )
    (parser_src_dir / "media_type.dart").write_text(
        "class MediaType {\n"
        "  static const String text = 'text/plain';\n"
        "}\n",
        encoding="utf-8",
    )

    candidate_calls: list[dict[str, list[str]]] = []
    original_candidate_repository_file_paths = probe_module._candidate_repository_file_paths

    def _recording_candidate_repository_file_paths(
        *,
        repo_path: Path,
        seed_paths: list[str],
        bridge_paths: list[str],
        include_patterns: list[str],
        max_files: int,
    ) -> list[str]:
        candidate_calls.append(
            {
                "seed_paths": list(seed_paths),
                "bridge_paths": list(bridge_paths),
            }
        )
        return original_candidate_repository_file_paths(
            repo_path=repo_path,
            seed_paths=seed_paths,
            bridge_paths=bridge_paths,
            include_patterns=include_patterns,
            max_files=max_files,
        )

    monkeypatch.setattr(
        probe_module,
        "_candidate_repository_file_paths",
        _recording_candidate_repository_file_paths,
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=64,
    )

    support_scan_calls = [
        call
        for call in candidate_calls
        if "pkgs/http_parser/lib" in call["bridge_paths"]
        and "pkgs/app/lib" not in call["bridge_paths"]
    ]

    if support_scan_calls:
        assert any(
            "pkgs/app/lib/app.dart" in call["seed_paths"]
            and "pkgs/http_parser/lib/http_parser.dart" in call["seed_paths"]
            for call in support_scan_calls
        )
    else:
        assert candidate_calls
        assert "pkgs/app/lib/app.dart" in candidate_calls[0]["seed_paths"]
        assert "pkgs/http_parser/lib/http_parser.dart" in candidate_calls[0]["seed_paths"]
        assert "pkgs/http_parser/lib" in candidate_calls[0]["bridge_paths"]
    assert "pkgs/http_parser/lib/src/media_type.dart" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_skips_support_rescan_when_roots_are_covered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "dart-covered-support-roots-repo"
    app_lib_dir = repo_path / "pkgs" / "app" / "lib"
    parser_lib_dir = repo_path / "pkgs" / "http_parser" / "lib"
    parser_src_dir = parser_lib_dir / "src"
    app_lib_dir.mkdir(parents=True)
    parser_src_dir.mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http_parser" / "pubspec.yaml").write_text(
        "name: http_parser\n",
        encoding="utf-8",
    )
    (app_lib_dir / "app.dart").write_text(
        "import 'package:http_parser/http_parser.dart';\n"
        "String run() => MediaType.text;\n",
        encoding="utf-8",
    )
    (parser_lib_dir / "http_parser.dart").write_text(
        "export 'src/media_type.dart';\n",
        encoding="utf-8",
    )
    (parser_src_dir / "media_type.dart").write_text(
        "class MediaType {\n"
        "  static const String text = 'text/plain';\n"
        "}\n",
        encoding="utf-8",
    )

    candidate_calls: list[dict[str, list[str]]] = []
    original_candidate_repository_file_paths = probe_module._candidate_repository_file_paths

    def _recording_candidate_repository_file_paths(
        *,
        repo_path: Path,
        seed_paths: list[str],
        bridge_paths: list[str],
        include_patterns: list[str],
        max_files: int,
    ) -> list[str]:
        candidate_calls.append(
            {
                "seed_paths": list(seed_paths),
                "bridge_paths": list(bridge_paths),
            }
        )
        return original_candidate_repository_file_paths(
            repo_path=repo_path,
            seed_paths=seed_paths,
            bridge_paths=bridge_paths,
            include_patterns=include_patterns,
            max_files=max_files,
        )

    monkeypatch.setattr(
        probe_module,
        "_candidate_repository_file_paths",
        _recording_candidate_repository_file_paths,
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=256,
    )

    assert len(candidate_calls) == 1
    assert "pkgs/http_parser/lib/src/media_type.dart" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_excludes_github_yaml_fallbacks(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "python-gh-noise-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / ".github" / "workflows").mkdir(parents=True)
    (repo_path / ".github" / "DISCUSSION_TEMPLATE").mkdir(parents=True)
    (repo_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "acme"\n'
        "[project.scripts]\n"
        'acme = "acme.cli:main"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "cli.py").write_text(
        "def main() -> int:\n    return 0\n",
        encoding="utf-8",
    )
    (repo_path / ".github" / "workflows" / "test.yml").write_text(
        "name: test\n",
        encoding="utf-8",
    )
    (repo_path / ".github" / "DISCUSSION_TEMPLATE" / "questions.yml").write_text(
        "body: []\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "src/acme/cli.py" in seed_plan["entrypoint_files"]
    assert all(not path.startswith(".github/") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_uses_maven_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "java-maven-repo"
    (repo_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (repo_path / ".github" / "workflows").mkdir(parents=True)
    (repo_path / "pom.xml").write_text(
        "<project><modelVersion>4.0.0</modelVersion></project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "java" / "com" / "example" / "PetClinicApplication.java").write_text(
        "package com.example;\npublic class PetClinicApplication {}\n",
        encoding="utf-8",
    )
    (repo_path / ".github" / "workflows" / "build.yml").write_text(
        "name: build\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "pom.xml" in seed_plan["config_paths"]
    assert "java" in seed_plan["detected_ecosystems"]
    assert "src/main/java" in seed_plan["support_roots"]
    assert any(path.endswith(".java") for path in seed_plan["entrypoint_files"])
    assert all(not path.startswith(".github/") for path in seed_plan["entrypoint_files"])


def test_non_operational_profile_path_ignores_common_package_namespace_segments() -> None:
    assert (
        probe_module._is_non_operational_profile_path("src/main/kotlin/com/example/blog/App.kt")
        is False
    )


def test_non_operational_profile_path_ignores_jvm_samples_namespace_segments() -> None:
    assert (
        probe_module._is_non_operational_profile_path(
            "src/main/java/org/springframework/samples/petclinic/PetClinicApplication.java"
        )
        is False
    )


def test_non_operational_profile_path_matches_dotted_benchmark_segments() -> None:
    assert (
        probe_module._is_non_operational_profile_path(
            "src/FluentValidation.Tests.Benchmarks/Program.cs"
        )
        is True
    )


def test_non_operational_profile_path_matches_docsrc_segments() -> None:
    assert (
        probe_module._is_non_operational_profile_path("docsrc/content/tutorial.fsx") is True
    )


def test_non_operational_profile_path_matches_docs_segments() -> None:
    assert probe_module._is_non_operational_profile_path("docs/make.jl") is True


def test_non_operational_project_path_matches_docs_project_segments() -> None:
    assert probe_module._is_non_operational_project_path("src/FSharpPlus.Docs") is True


def test_operational_seed_plan_without_diagnostics_deprioritizes_jvm_resource_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "java-resource-repo"
    (repo_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (repo_path / "src" / "main" / "resources" / "db").mkdir(parents=True)
    (repo_path / "pom.xml").write_text(
        "<project><modelVersion>4.0.0</modelVersion></project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "java" / "com" / "example" / "PetClinicApplication.java").write_text(
        "package com.example;\npublic class PetClinicApplication {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "resources" / "db" / "schema.sql").write_text(
        "create table demo(id int);\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert any(path.endswith(".java") for path in seed_plan["entrypoint_files"])
    assert all(not path.endswith(".sql") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_excludes_text_control_fallbacks(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "go-library-repo"
    (repo_path / ".github" / "workflows").mkdir(parents=True)
    (repo_path / "doc").mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/acme\n", encoding="utf-8")
    (repo_path / "cobra.go").write_text("package cobra\nfunc New() {}\n", encoding="utf-8")
    (repo_path / "args.go").write_text("package cobra\nfunc Args() {}\n", encoding="utf-8")
    (repo_path / "Makefile").write_text("test:\n\tgo test ./...\n", encoding="utf-8")
    (repo_path / "LICENSE.txt").write_text("license\n", encoding="utf-8")
    (repo_path / ".github" / "workflows" / "test.yml").write_text("name: test\n", encoding="utf-8")
    (repo_path / "doc" / "usage.md").write_text("# usage\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "go" in seed_plan["detected_ecosystems"]
    assert any(path.endswith(".go") for path in seed_plan["entrypoint_files"])
    assert all(not path.endswith("_test.go") for path in seed_plan["entrypoint_files"])
    assert "Makefile" not in seed_plan["entrypoint_files"]
    assert "LICENSE.txt" not in seed_plan["entrypoint_files"]
    assert all(not path.startswith(".github/") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_deprioritizes_docs_examples(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "python-docs-heavy-repo"
    (repo_path / "fastapi").mkdir(parents=True)
    (repo_path / "docs_src" / "tutorial").mkdir(parents=True)
    (repo_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "fastapi-like"\n'
        "[project.scripts]\n"
        'fastapi = "fastapi.cli:main"\n',
        encoding="utf-8",
    )
    (repo_path / "fastapi" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (repo_path / "fastapi" / "cli.py").write_text("def main() -> int:\n    return 0\n", encoding="utf-8")
    (repo_path / "fastapi" / "routing.py").write_text("class Router: ...\n", encoding="utf-8")
    (repo_path / "docs_src" / "tutorial" / "main.py").write_text(
        "def tutorial() -> int:\n    return 0\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "fastapi/cli.py" in seed_plan["entrypoint_files"]
    assert any(path.startswith("fastapi/") for path in seed_plan["entrypoint_files"])
    assert "docs_src/tutorial/main.py" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_composer_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "php-composer-repo"
    (repo_path / "app" / "Models").mkdir(parents=True)
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "composer.json").write_text(
        '{\n'
        '  "autoload": { "psr-4": { "App\\\\\\\\": "app/" } },\n'
        '  "bin": ["artisan"]\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "app" / "ConsoleKernel.php").write_text("<?php\n", encoding="utf-8")
    (repo_path / "app" / "Models" / "User.php").write_text("<?php\n", encoding="utf-8")
    (repo_path / "public" / "index.php").write_text("<?php\n", encoding="utf-8")
    (repo_path / "artisan").write_text("#!/usr/bin/env php\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "php" in seed_plan["detected_ecosystems"]
    assert "composer.json" in seed_plan["config_paths"]
    assert "app" in seed_plan["support_roots"]
    assert "public/index.php" in seed_plan["entrypoint_files"] or "artisan" in seed_plan["entrypoint_files"]
    assert "app/Models/User.php" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_hack_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hack-hhconfig-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / ".hhconfig").write_text("assume_php = false\n", encoding="utf-8")
    (repo_path / "src" / "Ref.php").write_text(
        "<?hh\nnamespace Demo;\nfinal class Ref<T> {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "User.hack").write_text(
        "namespace Demo;\nuse type Demo\\Ref;\nfinal class User { public function make(): Ref<int> { return new Ref(); } }\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "UserTest.php").write_text(
        "<?hh\nnamespace Demo;\nfinal class UserTest {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"][0] == "hack"
    assert seed_plan["operational_ecosystems"][0] == "hack"
    assert ".hhconfig" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Ref.php" in seed_plan["entrypoint_files"] or "src/User.hack" in seed_plan["entrypoint_files"]
    assert "tests/UserTest.php" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_mix_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "elixir-mix-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "mix.exs").write_text(
        "defmodule Acme.MixProject do\n"
        "  use Mix.Project\n"
        "  def project do\n"
        "    [app: :acme]\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme.ex").write_text("defmodule Acme do\nend\n", encoding="utf-8")
    (repo_path / "lib" / "acme" / "repo.ex").write_text("defmodule Acme.Repo do\nend\n", encoding="utf-8")
    (repo_path / "lib" / "acme" / "application.ex").write_text(
        "defmodule Acme.Application do\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "elixir" in seed_plan["detected_ecosystems"]
    assert "mix.exs" in seed_plan["config_paths"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/acme.ex" in seed_plan["entrypoint_files"] or "lib/acme/application.ex" in seed_plan["entrypoint_files"]
    assert "lib/acme/repo.ex" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_deprioritizes_static_assets(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "elixir-node-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "priv" / "static").mkdir(parents=True)
    (repo_path / "mix.exs").write_text(
        "defmodule Acme.MixProject do\n"
        "  use Mix.Project\n"
        "  def project do\n"
        "    [app: :acme]\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        json.dumps({"name": "acme", "main": "priv/static/app.js"}),
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme.ex").write_text("defmodule Acme do\nend\n", encoding="utf-8")
    (repo_path / "priv" / "static" / "app.js").write_text("export const app = true;\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "lib/acme.ex" in seed_plan["entrypoint_files"]
    assert "priv/static/app.js" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_swift_package_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "swift-package-repo"
    (repo_path / "Sources" / "AcmeCLI").mkdir(parents=True)
    (repo_path / "Package.swift").write_text(
        'let package = Package(name: "AcmeCLI")\n',
        encoding="utf-8",
    )
    (repo_path / "Sources" / "AcmeCLI" / "main.swift").write_text(
        'print("ok")\n',
        encoding="utf-8",
    )
    (repo_path / "Sources" / "AcmeCLI" / "Command.swift").write_text(
        "struct Command {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "swift" in seed_plan["detected_ecosystems"]
    assert "Package.swift" in seed_plan["config_paths"]
    assert "Sources" in seed_plan["support_roots"]
    assert "Sources/AcmeCLI/main.swift" in seed_plan["entrypoint_files"]
    assert "Sources/AcmeCLI/Command.swift" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_swift_library_sources(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "swift-library-repo"
    (repo_path / "Sources" / "ArgumentParser").mkdir(parents=True)
    (repo_path / "Package.swift").write_text(
        'let package = Package(name: "ArgumentParser")\n',
        encoding="utf-8",
    )
    (repo_path / "Sources" / "ArgumentParser" / "Argument.swift").write_text(
        "public struct Argument {}\n",
        encoding="utf-8",
    )
    (repo_path / "Sources" / "ArgumentParser" / "Parser.swift").write_text(
        "public struct Parser {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "swift" in seed_plan["detected_ecosystems"]
    assert "Sources/ArgumentParser/Argument.swift" in seed_plan["entrypoint_files"]
    assert "Sources/ArgumentParser/Parser.swift" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_scala_build_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scala-build-repo"
    (repo_path / "src" / "main" / "scala" / "acme").mkdir(parents=True)
    (repo_path / "src" / "test" / "scala" / "acme").mkdir(parents=True)
    (repo_path / "build.sbt").write_text(
        'name := "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "scala" / "acme" / "Main.scala").write_text(
        "package acme\nobject Main\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "scala" / "acme" / "Routes.scala").write_text(
        "package acme\nobject Routes\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "test" / "scala" / "acme" / "RoutesSpec.scala").write_text(
        "package acme\nobject RoutesSpec\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "scala" in seed_plan["detected_ecosystems"]
    assert "build.sbt" in seed_plan["config_paths"]
    assert "src/main/scala" in seed_plan["support_roots"]
    assert "src/main/scala/acme/Main.scala" in seed_plan["entrypoint_files"]
    assert "src/main/scala/acme/Routes.scala" in seed_plan["entrypoint_files"]
    assert "src/test/scala/acme/RoutesSpec.scala" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_mill_scala_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mill-scala-repo"
    (repo_path / "upack" / "src" / "upack").mkdir(parents=True)
    (repo_path / "upickle" / "src" / "upickle").mkdir(parents=True)
    (repo_path / "bench" / "src").mkdir(parents=True)
    (repo_path / "build.mill").write_text(
        "import mill._\n",
        encoding="utf-8",
    )
    (repo_path / "upack" / "src" / "upack" / "Msg.scala").write_text(
        "package upack\nobject Msg\n",
        encoding="utf-8",
    )
    (repo_path / "upickle" / "src" / "upickle" / "Api.scala").write_text(
        "package upickle\nobject Api\n",
        encoding="utf-8",
    )
    (repo_path / "bench" / "src" / "Common.scala").write_text(
        "package bench\nobject Common\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "scala" in seed_plan["detected_ecosystems"]
    assert "build.mill" in seed_plan["config_paths"]
    assert "upack/src/upack" in seed_plan["support_roots"]
    assert "upickle/src/upickle" in seed_plan["support_roots"]
    assert "upack/src/upack/Msg.scala" in seed_plan["entrypoint_files"]
    assert "upickle/src/upickle/Api.scala" in seed_plan["entrypoint_files"]
    assert "bench/src/Common.scala" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_scala_profile_roots_for_initial_candidate_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "scala-profile-seeded-candidate-repo"
    (repo_path / "play-json" / "shared" / "src" / "main" / "scala" / "play" / "api" / "libs" / "json").mkdir(parents=True)
    (repo_path / "play-json" / "jvm" / "src" / "main" / "scala" / "play" / "api" / "libs" / "json").mkdir(parents=True)
    (repo_path / "benchmarks" / "src" / "main" / "scala").mkdir(parents=True)
    (repo_path / "build.sbt").write_text(
        'name := "play-json"\n',
        encoding="utf-8",
    )
    (
        repo_path
        / "play-json"
        / "shared"
        / "src"
        / "main"
        / "scala"
        / "play"
        / "api"
        / "libs"
        / "json"
        / "Json.scala"
    ).write_text(
        "package play.api.libs.json\nobject Json\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "play-json"
        / "jvm"
        / "src"
        / "main"
        / "scala"
        / "play"
        / "api"
        / "libs"
        / "json"
        / "JvmJson.scala"
    ).write_text(
        "package play.api.libs.json\nobject JvmJson\n",
        encoding="utf-8",
    )
    (repo_path / "benchmarks" / "src" / "main" / "scala" / "Bench.scala").write_text(
        "package benchmarks\nobject Bench\n",
        encoding="utf-8",
    )

    candidate_calls: list[dict[str, list[str]]] = []
    original_candidate_repository_file_paths = probe_module._candidate_repository_file_paths

    def _recording_candidate_repository_file_paths(
        *,
        repo_path: Path,
        seed_paths: list[str],
        bridge_paths: list[str],
        include_patterns: list[str],
        max_files: int,
    ) -> list[str]:
        candidate_calls.append(
            {
                "seed_paths": list(seed_paths),
                "bridge_paths": list(bridge_paths),
            }
        )
        return original_candidate_repository_file_paths(
            repo_path=repo_path,
            seed_paths=seed_paths,
            bridge_paths=bridge_paths,
            include_patterns=include_patterns,
            max_files=max_files,
        )

    monkeypatch.setattr(
        probe_module,
        "_candidate_repository_file_paths",
        _recording_candidate_repository_file_paths,
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert candidate_calls
    assert candidate_calls[0]["bridge_paths"] != ["."]
    assert "play-json/shared/src/main/scala" in candidate_calls[0]["bridge_paths"]
    assert "play-json/jvm/src/main/scala" in candidate_calls[0]["bridge_paths"]
    assert "benchmarks/src" not in candidate_calls[0]["bridge_paths"]
    assert "play-json/shared/src/main/scala/play/api/libs/json/Json.scala" in seed_plan["candidate_file_paths"]
    assert "play-json/jvm/src/main/scala/play/api/libs/json/JvmJson.scala" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_gradle_groovy_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gradle-groovy-repo"
    (repo_path / "src" / "main" / "groovy" / "org" / "example").mkdir(parents=True)
    (repo_path / "src" / "test" / "groovy" / "org" / "example").mkdir(parents=True)
    (repo_path / "build.gradle").write_text(
        "plugins { id 'groovy' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "groovy" / "org" / "example" / "Main.groovy").write_text(
        "package org.example\nclass Main {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "groovy" / "org" / "example" / "Helper.groovy").write_text(
        "package org.example\nclass Helper {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "test" / "groovy" / "org" / "example" / "MainSpec.groovy").write_text(
        "package org.example\nclass MainSpec {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "groovy" in seed_plan["detected_ecosystems"]
    assert "java" in seed_plan["detected_ecosystems"]
    assert "build.gradle" in seed_plan["config_paths"]
    assert "src/main/groovy" in seed_plan["support_roots"]
    assert "src/main/groovy/org/example/Main.groovy" in seed_plan["entrypoint_files"]
    assert "src/main/groovy/org/example/Helper.groovy" in seed_plan["candidate_file_paths"]
    assert "src/test/groovy/org/example/MainSpec.groovy" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_gradle_kotlin_main_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gradle-kotlin-repo"
    (repo_path / "src" / "main" / "kotlin" / "org" / "example").mkdir(parents=True)
    (repo_path / "src" / "jvmTest" / "java" / "org" / "example").mkdir(parents=True)
    (repo_path / "buildSrc" / "src" / "main" / "kotlin" / "buildlogic").mkdir(parents=True)
    (repo_path / "build.gradle.kts").write_text(
        "plugins { kotlin(\"jvm\") version \"2.0.0\" }\n",
        encoding="utf-8",
    )
    (repo_path / "settings.gradle.kts").write_text(
        'rootProject.name = "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "kotlin" / "org" / "example" / "Main.kt").write_text(
        "package org.example\nclass Main\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "kotlin" / "org" / "example" / "Helper.kt").write_text(
        "package org.example\nclass Helper\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "jvmTest" / "java" / "org" / "example" / "JavaNoise.java").write_text(
        "package org.example; public class JavaNoise {}\n",
        encoding="utf-8",
    )
    (repo_path / "buildSrc" / "build.gradle.kts").write_text(
        "plugins { kotlin(\"jvm\") version \"2.0.0\" }\n",
        encoding="utf-8",
    )
    (repo_path / "buildSrc" / "src" / "main" / "kotlin" / "buildlogic" / "BuildLogic.kt").write_text(
        "package buildlogic\nclass BuildLogic\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "kotlin" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "kotlin"
    assert "build.gradle.kts" in seed_plan["config_paths"]
    assert "src/main/kotlin" in seed_plan["support_roots"]
    assert "buildSrc/src/main/kotlin" not in seed_plan["support_roots"]
    assert "src/main/kotlin/org/example/Main.kt" in seed_plan["entrypoint_files"]
    assert "src/main/kotlin/org/example/Helper.kt" in seed_plan["candidate_file_paths"]
    assert "src/jvmTest/java/org/example/JavaNoise.java" not in seed_plan["entrypoint_files"]
    assert "buildSrc/src/main/kotlin/buildlogic/BuildLogic.kt" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_gradle_settings_included_projects(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gradle-settings-repo"
    (repo_path / "app" / "src" / "main" / "groovy").mkdir(parents=True)
    (repo_path / "feature" / "core" / "src" / "main" / "groovy").mkdir(parents=True)
    (repo_path / "settings.gradle").write_text(
        'include "app", ":feature:core"\n',
        encoding="utf-8",
    )
    (repo_path / "app" / "src" / "main" / "groovy" / "Main.groovy").write_text(
        "class Main {}\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "feature"
        / "core"
        / "src"
        / "main"
        / "groovy"
        / "Application.groovy"
    ).write_text(
        "class Application {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "groovy" in seed_plan["detected_ecosystems"]
    assert "java" in seed_plan["detected_ecosystems"]
    assert "settings.gradle" in seed_plan["config_paths"]
    assert "app/src/main/groovy" in seed_plan["support_roots"]
    assert "feature/core/src/main/groovy" in seed_plan["support_roots"]
    assert "app" not in seed_plan["support_roots"]
    assert "feature/core" not in seed_plan["support_roots"]
    assert "app/src/main/groovy/Main.groovy" in seed_plan["entrypoint_files"]
    assert "feature/core/src/main/groovy/Application.groovy" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_robotframework_suites(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "robotframework-repo"
    (repo_path / "login_tests").mkdir(parents=True)
    (repo_path / "resources").mkdir(parents=True)
    (repo_path / "demoapp").mkdir(parents=True)
    (repo_path / "resources" / "resource.robot").write_text(
        "*** Keywords ***\nOpen Login Page\n    Log    hello\n",
        encoding="utf-8",
    )
    (repo_path / "login_tests" / "valid_login.robot").write_text(
        "*** Settings ***\nResource    ../resources/resource.robot\n\n*** Test Cases ***\nValid Login\n    Open Login Page\n",
        encoding="utf-8",
    )
    (repo_path / "demoapp" / "server.py").write_text(
        "def main():\n    return None\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "robotframework" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "robotframework"
    assert "login_tests" in seed_plan["support_roots"]
    assert "login_tests/valid_login.robot" in seed_plan["entrypoint_files"]
    assert "resources/resource.robot" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_promotes_typst_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "typst-profile-repo"
    (repo_path / "content").mkdir(parents=True)
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "content" / "math.typ").write_text(
        "#let add(x, y) = x + y\n"
        "#let scale(x) = x * 2\n",
        encoding="utf-8",
    )
    (repo_path / "partials" / "common.typ").write_text(
        "#let title() = [Demo]\n",
        encoding="utf-8",
    )
    (repo_path / "main.typ").write_text(
        '#import "content/math.typ": add\n'
        '#import "content/math.typ" as math\n'
        '#include "partials/common.typ"\n'
        "#let render() = {\n"
        "  add(1, 2)\n"
        "  math.scale(3)\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "typst.toml").write_text(
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "helper.py").write_text(
        "def main():\n    return None\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "typst" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "typst"
    assert "main.typ" in seed_plan["entrypoint_files"]
    assert "content" in seed_plan["support_roots"]
    assert "typst.toml" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_promotes_scss_when_scss_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scss-profile-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "_mixins.scss").write_text(
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "_functions.scss").write_text(
        "@function helper-fn() {\n"
        "  @return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "app.scss").write_text(
        '@use "styles/mixins" as mixins;\n'
        '@import "styles/functions";\n'
        ".button {\n"
        "  @include mixins.button-base;\n"
        "  color: helper-fn();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "theme.scss").write_text(
        '@import "styles/functions";\n'
        ".theme {\n"
        "  color: helper-fn();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "app.rb").write_text("class App; end\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "scss" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "scss"
    assert "app.scss" in seed_plan["entrypoint_files"]
    assert "styles/_mixins.scss" in seed_plan["candidate_file_paths"]
    assert "styles" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_promotes_dockerfile_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dockerfile-profile-repo"
    (repo_path / "docker").mkdir(parents=True)
    (repo_path / "conf" / "alpha").mkdir(parents=True)
    (repo_path / "conf" / "beta").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(8):
        image_dir = repo_path / "docker" / f"image_{index}"
        image_dir.mkdir(parents=True)
        (repo_path / "scripts" / f"boot_{index}.sh").write_text(
            "#!/usr/bin/env sh\n"
            f"echo boot {index}\n",
            encoding="utf-8",
        )
        (image_dir / "Dockerfile").write_text(
            "FROM alpine:3.20\n"
            f"COPY ../../scripts/boot_{index}.sh /usr/local/bin/boot.sh\n"
            "RUN sh ../../scripts/boot_0.sh\n",
            encoding="utf-8",
        )
    (repo_path / "conf" / "alpha" / "local.conf").write_text(
        'IMAGE_INSTALL:append = " docker"\n',
        encoding="utf-8",
    )
    (repo_path / "conf" / "beta" / "local.conf").write_text(
        'MACHINE ??= "qemuarm64"\n',
        encoding="utf-8",
    )
    (repo_path / "cmd").mkdir(parents=True)
    (repo_path / "cmd" / "main.go").write_text(
        "package main\n\nfunc main() {}\n",
        encoding="utf-8",
    )
    (repo_path / "internal").mkdir(parents=True)
    (repo_path / "internal" / "helper.go").write_text(
        "package internal\n\nfunc Run() {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "dockerfile" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "dockerfile"
    assert "docker/image_0/Dockerfile" in seed_plan["entrypoint_files"]
    assert "docker/image_0/Dockerfile" in seed_plan["candidate_file_paths"]
    assert "docker/image_0" in seed_plan["support_roots"]
    assert "bitbake" in seed_plan["detected_ecosystems"]


def test_operational_seed_plan_without_diagnostics_does_not_force_dockerfile_first_in_go_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mixed-go-docker-repo"
    (repo_path / "docker").mkdir(parents=True)
    (repo_path / "cmd").mkdir(parents=True)
    (repo_path / "internal").mkdir(parents=True)
    for index in range(2):
        (repo_path / "docker" / f"build_{index}.Dockerfile").write_text(
            "FROM golang:1.24\n"
            "COPY . /src\n",
            encoding="utf-8",
        )
    for index in range(10):
        target_dir = repo_path / ("cmd" if index < 5 else "internal")
        (target_dir / f"file_{index}.go").write_text(
            f"package main\n\nfunc run{index}() {{}}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "dockerfile" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "dockerfile"


def test_operational_seed_plan_without_diagnostics_does_not_force_typst_first_in_rust_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mixed-rust-typst-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "docs" / "guide.typ").write_text(
        "#let render() = [Guide]\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "appendix.typ").write_text(
        "#include \"guide.typ\"\n",
        encoding="utf-8",
    )
    (repo_path / "typst.toml").write_text(
        "[package]\nname = \"mixed\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )
    for index in range(8):
        (repo_path / "src" / f"module_{index}.rs").write_text(
            f"pub fn run_{index}() {{}}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "typst" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "typst"
    assert "rust" in seed_plan["operational_ecosystems"]


def test_operational_seed_plan_without_diagnostics_uses_build_zig_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "zig-build-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "examples").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "build.zig").write_text(
        'const std = @import("std");\n'
        "pub fn build(b: *std.Build) void {\n"
        "  _ = b.addExecutable(.{\n"
        '    .name = "acme",\n'
        '    .root_source_file = b.path("src/main.zig"),\n'
        "  });\n"
        '  _ = b.addModule("acme", .{\n'
        '    .root_source_file = b.path("src/root.zig"),\n'
        "  });\n"
        "  _ = b.addExecutable(.{\n"
        '    .name = "demo",\n'
        '    .root_source_file = b.path("examples/demo.zig"),\n'
        "  });\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.zig").write_text("pub fn main() void {}\n", encoding="utf-8")
    (repo_path / "src" / "root.zig").write_text("pub const Answer = 42;\n", encoding="utf-8")
    (repo_path / "examples" / "demo.zig").write_text(
        "pub fn main() void {}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "root_test.zig").write_text(
        "test \"answer\" {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "zig" in seed_plan["detected_ecosystems"]
    assert "build.zig" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.zig" in seed_plan["entrypoint_files"]
    assert "src/root.zig" in seed_plan["entrypoint_files"]
    assert "examples/demo.zig" not in seed_plan["entrypoint_files"]
    assert "tests/root_test.zig" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_cabal_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haskell-cabal-repo"
    (repo_path / "src" / "Text" / "ParserCombinators").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "parsec.cabal").write_text(
        "name: parsec\n"
        "version: 1.0.0.0\n"
        "library\n"
        "  hs-source-dirs: src\n"
        "  exposed-modules: Text.Parsec, Text.ParserCombinators.Parsec\n"
        "test-suite parsec-tests\n"
        "  hs-source-dirs: test\n"
        "  main-is: Main.hs\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Text" / "Parsec.hs").write_text(
        "module Text.Parsec where\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Text" / "ParserCombinators" / "Parsec.hs").write_text(
        "module Text.ParserCombinators.Parsec where\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "Main.hs").write_text(
        "module Main where\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "haskell" in seed_plan["detected_ecosystems"]
    assert "parsec.cabal" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Text/Parsec.hs" in seed_plan["entrypoint_files"]
    assert "src/Text/ParserCombinators/Parsec.hs" in seed_plan["entrypoint_files"]
    assert "test/Main.hs" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_package_yaml_haskell_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haskell-package-yaml-repo"
    (repo_path / "src" / "Acme").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "package.yaml").write_text(
        "name: acme\n"
        "library:\n"
        "  source-dirs: src\n"
        "  exposed-modules:\n"
        "    - Acme.Lib\n"
        "executables:\n"
        "  acme-cli:\n"
        "    main: Main.hs\n"
        "    source-dirs:\n"
        "      - app\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme" / "Lib.hs").write_text(
        "module Acme.Lib where\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "Main.hs").write_text(
        "module Main where\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "haskell" in seed_plan["detected_ecosystems"]
    assert "package.yaml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "app" in seed_plan["support_roots"]
    assert "src/Acme/Lib.hs" in seed_plan["entrypoint_files"]
    assert "app/Main.hs" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_csproj_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dotnet-repo"
    (repo_path / "src" / "AcmeApp").mkdir(parents=True)
    (repo_path / "src" / "AcmeApp" / "AcmeApp.csproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Program.cs").write_text(
        "class Program { static void Main() {} }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Mediator.cs").write_text(
        "public sealed class Mediator {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert "dotnet" in seed_plan["detected_ecosystems"]
    assert "src/AcmeApp/AcmeApp.csproj" in seed_plan["config_paths"]
    assert "src/AcmeApp" in seed_plan["support_roots"]
    assert "src/AcmeApp/Program.cs" in seed_plan["entrypoint_files"]
    assert "src/AcmeApp/Mediator.cs" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_fsproj_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fsharp-repo"
    (repo_path / "src" / "AcmeApp").mkdir(parents=True)
    (repo_path / "test" / "AcmeApp.Benchmarks").mkdir(parents=True)
    (repo_path / "src" / "AcmeApp" / "AcmeApp.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Program.fs").write_text(
        "namespace AcmeApp\n\nmodule Program =\n    let main _ = 0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Routes.fs").write_text(
        "namespace AcmeApp\n\nmodule Routes =\n    let ping () = \"pong\"\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "AcmeApp.Benchmarks" / "AcmeApp.Benchmarks.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "AcmeApp.Benchmarks" / "Program.fs").write_text(
        "module Benchmarks.Program\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "dotnet" in seed_plan["detected_ecosystems"]
    assert "fsharp" in seed_plan["detected_ecosystems"]
    assert "src/AcmeApp/AcmeApp.fsproj" in seed_plan["config_paths"]
    assert "src/AcmeApp" in seed_plan["support_roots"]
    assert "src/AcmeApp/Program.fs" in seed_plan["entrypoint_files"]
    assert "src/AcmeApp/Routes.fs" in seed_plan["entrypoint_files"]
    assert "test/AcmeApp.Benchmarks/Program.fs" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_vbproj_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "visual-basic-repo"
    (repo_path / "src" / "AcmeApp" / "tests").mkdir(parents=True)
    (repo_path / "src" / "AcmeApp" / "AcmeApp.vbproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Program.vb").write_text(
        "Namespace AcmeApp\n"
        "Module Program\n"
        "    Sub Main()\n"
        "    End Sub\n"
        "End Module\n"
        "End Namespace\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Mediator.vb").write_text(
        "Namespace AcmeApp\n"
        "Public Class Mediator\n"
        "End Class\n"
        "End Namespace\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "tests" / "ProgramTests.vb").write_text(
        "Public Class ProgramTests\nEnd Class\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "dotnet" in seed_plan["detected_ecosystems"]
    assert "visualbasic" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "visualbasic"
    assert "src/AcmeApp/AcmeApp.vbproj" in seed_plan["config_paths"]
    assert "src/AcmeApp" in seed_plan["support_roots"]
    assert "src/AcmeApp/Program.vb" in seed_plan["entrypoint_files"]
    assert "src/AcmeApp/Mediator.vb" in seed_plan["entrypoint_files"]
    assert "src/AcmeApp/tests/ProgramTests.vb" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_vbp_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vb6-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Project1.vbp").write_text(
        'Type=Exe\n'
        'Class=cHelper; src/cHelper.cls\n'
        'Module=modMain; src/modMain.bas\n'
        'Form=src/Form1.frm\n'
        'Startup="Form1"\n'
        'Name="Project1"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Form1.frm").write_text(
        "VERSION 5.00\n"
        "Begin VB.Form Form1\n"
        "End\n"
        'Attribute VB_Name = "Form1"\n'
        "Option Explicit\n"
        "Private Sub Form_Load()\n"
        "    modMain.RunApp\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "modMain.bas").write_text(
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "cHelper.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "cHelper"\n'
        "Option Explicit\n"
        "Public Function Helper() As String\n"
        '    Helper = "ok"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "Project1.vbp").write_text(
        'Type=Exe\nForm=Form1.frm\nStartup="Form1"\nName="Project1Tests"\n',
        encoding="utf-8",
    )
    (repo_path / "tests" / "Form1.frm").write_text(
        'VERSION 5.00\nBegin VB.Form Form1\nEnd\nAttribute VB_Name = "Form1"\n',
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["vb6"]
    assert "Project1.vbp" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Form1.frm" in seed_plan["entrypoint_files"]
    assert "src/cHelper.cls" in seed_plan["candidate_file_paths"]
    assert "tests/Form1.frm" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_vba_surface(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vba-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "JsonConverter.bas").write_text(
        'Attribute VB_Name = "JsonConverter"\n'
        "Option Explicit\n"
        "Public Sub Main()\n"
        "    Dim data As JsonData\n"
        "    Set data = New JsonData\n"
        "    Debug.Print data.ToJson()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "JsonData.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "JsonData"\n'
        "Option Explicit\n"
        "Public Function ToJson() As String\n"
        '    ToJson = "{}"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "TestJson.bas").write_text(
        'Attribute VB_Name = "TestJson"\n'
        "Option Explicit\n"
        "Public Sub TestMain()\n"
        "End Sub\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["vba"]
    assert seed_plan["operational_ecosystems"] == ["vba"]
    assert "src" in seed_plan["support_roots"]
    assert "src/JsonConverter.bas" in seed_plan["entrypoint_files"]
    assert "src/JsonData.cls" in seed_plan["candidate_file_paths"]
    assert "tests/TestJson.bas" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_vbscript_wsf_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vbscript-profile-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "helper.vbs").write_text(
        "Class Helper\nEnd Class\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.wsf").write_text(
        "<job>\n"
        '  <script language="VBScript" src="lib/helper.vbs"></script>\n'
        '  <script language="VBScript">\n'
        "    Option Explicit\n"
        "    Sub Main()\n"
        "    End Sub\n"
        "  </script>\n"
        "</job>\n",
        encoding="utf-8",
    )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "test_helper.vbs").write_text(
        "Sub TestMain()\nEnd Sub\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["vbscript"]
    assert seed_plan["operational_ecosystems"] == ["vbscript"]
    assert "scripts/main.wsf" in seed_plan["config_paths"]
    assert "scripts/main.wsf" in seed_plan["entrypoint_files"]
    assert "scripts/lib" in seed_plan["support_roots"]
    assert "tests/test_helper.vbs" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_applescript_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "applescript-profile-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "Helper.applescript").write_text(
        "script HelperScript\n"
        "    on RenderJson(value)\n"
        "        return value\n"
        "    end RenderJson\n"
        "end script\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "Main.applescript").write_text(
        'property helperScript : load script POSIX file "lib/Helper.applescript"\n'
        "on run\n"
        "    helperScript's RenderJson(\"{}\")\n"
        "end run\n",
        encoding="utf-8",
    )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "MainTests.applescript").write_text(
        "on run\n"
        "    return true\n"
        "end run\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["applescript"]
    assert seed_plan["operational_ecosystems"] == ["applescript"]
    assert seed_plan["config_paths"] == []
    assert any(root in seed_plan["support_roots"] for root in {"scripts", "scripts/lib"})
    assert "scripts/Main.applescript" in seed_plan["entrypoint_files"]
    assert "tests/MainTests.applescript" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_cfml_box_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cfml-profile-repo"
    (repo_path / "config").mkdir(parents=True)
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "box.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "config" / "app.cfm").write_text(
        "<cfset request.ready = true />\n",
        encoding="utf-8",
    )
    (repo_path / "Application.cfc").write_text(
        "component {\n"
        '    include "config/app.cfm";\n'
        "    function onApplicationStart() {\n"
        "        local.userService = new models.UserService();\n"
        "        local.userService.run();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "UserService.cfc").write_text(
        "component {\n"
        "    function run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "public" / "index.cfm").write_text(
        '<cfinclude template="../config/app.cfm">\n',
        encoding="utf-8",
    )
    (repo_path / "tests" / "ApplicationTest.cfc").write_text(
        "component {\n"
        "    function testRun() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["cfml"]
    assert seed_plan["operational_ecosystems"] == ["cfml"]
    assert seed_plan["config_paths"] == ["box.json"]
    assert "config" in seed_plan["support_roots"]
    assert "models" in seed_plan["support_roots"]
    assert "public" in seed_plan["support_roots"]
    assert "Application.cfc" in seed_plan["entrypoint_files"]
    assert "public/index.cfm" in seed_plan["entrypoint_files"]
    assert "tests/ApplicationTest.cfc" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_ladder_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ladder-profile-repo"
    (repo_path / "logic").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "logic" / "Child.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="SupportProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="ChildRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[XIC(StartPB)OTE(RunMotor);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "logic" / "Main.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="MainProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="MainRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[JSR(ChildRoutine,0);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "logic" / "Types.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        '<RSLogix5000Content TargetType="DataType">\n'
        '  <Controller Name="PlantController">\n'
        "    <DataTypes>\n"
        '      <DataType Name="MotorStatus">\n'
        "        <Members>\n"
        '          <Member Name="Running" DataType="BOOL"/>\n'
        "        </Members>\n"
        "      </DataType>\n"
        "    </DataTypes>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "MainTest.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="TestController">\n'
        "    <Programs>\n"
        '      <Program Name="TestProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="TestRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[XIC(TestPB)OTE(TestCoil);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["ladder"]
    assert seed_plan["operational_ecosystems"] == ["ladder"]
    assert "logic" in seed_plan["support_roots"]
    assert "logic/Main.L5X" in seed_plan["entrypoint_files"]
    assert "logic/Child.L5X" in seed_plan["entrypoint_files"]
    assert "logic/Types.L5X" not in seed_plan["entrypoint_files"]
    assert "tests/MainTest.L5X" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_asconfig_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "actionscript-profile-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "base").mkdir(parents=True)
    (repo_path / "src" / "demo" / "utils").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "asconfig.json").write_text(
        "{\n"
        '  "compilerOptions": {\n'
        '    "source-path": ["src"],\n'
        '    "mainClass": "demo.app.Main"\n'
        "  },\n"
        '  "files": ["src/demo/utils/Utils.as"]\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "base" / "BaseActor.as").write_text(
        "package demo.base {\n"
        "    public class BaseActor {\n"
        "        public function baseReady():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "utils" / "Utils.as").write_text(
        "package demo.utils {\n"
        "    public class Utils {\n"
        "        public static function helper():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "app" / "Main.as").write_text(
        "package demo.app {\n"
        "    import demo.base.BaseActor;\n"
        "    import demo.utils.Utils;\n"
        "    public class Main extends BaseActor {\n"
        "        public function boot():void {\n"
        "            Utils.helper();\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "MainTest.as").write_text(
        "package demo.tests {\n"
        "    public class MainTest {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["actionscript"]
    assert seed_plan["operational_ecosystems"] == ["actionscript"]
    assert "asconfig.json" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/demo/app/Main.as" in seed_plan["entrypoint_files"]
    assert "src/demo/utils/Utils.as" in seed_plan["entrypoint_files"]
    assert "tests/MainTest.as" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_awk_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "awk-profile-repo"
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "bin" / "translate").write_text(
        "#!/usr/bin/env gawk -f\n"
        '@include "../lib/math.awk"\n'
        "BEGIN {\n"
        "    print add(1, 2)\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "math.awk").write_text(
        "function add(a, b) {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "translate_test.awk").write_text(
        "BEGIN { print add(0, 0) }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["awk"]
    assert seed_plan["operational_ecosystems"] == ["awk"]
    assert seed_plan["config_paths"] == []
    assert any(root in seed_plan["support_roots"] for root in {"bin", "lib"})
    assert "bin/translate" in seed_plan["entrypoint_files"]
    assert "tests/translate_test.awk" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_cakefile_coffeescript_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coffeescript-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "Cakefile").write_text(
        "task 'build', ->\n"
        "  require './src/main'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper.coffee").write_text(
        "renderJson = (value) ->\n"
        "  value\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.coffee").write_text(
        "helper = require './helper'\n"
        "run = ->\n"
        "  helper.renderJson '{}'\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "main_test.coffee").write_text(
        "run = ->\n"
        "  true\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["coffeescript"]
    assert seed_plan["operational_ecosystems"] == ["coffeescript"]
    assert "Cakefile" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.coffee" in seed_plan["entrypoint_files"]
    assert "src/helper.coffee" in seed_plan["candidate_file_paths"]
    assert "test/main_test.coffee" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_elm_profile(tmp_path: Path) -> None:
    repo_path = tmp_path / "elm-profile-repo"
    (repo_path / "src" / "Page").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "elm.json").write_text(
        json.dumps(
            {
                "type": "application",
                "source-directories": ["src"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.elm").write_text(
        "module Main exposing (main)\n\n"
        "import Page.Home exposing (homeView)\n\n"
        "main : String\n"
        "main =\n"
        "    homeView\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Page" / "Home.elm").write_text(
        "module Page.Home exposing (homeView)\n\n"
        "homeView : String\n"
        "homeView =\n"
        "    \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "MainTest.elm").write_text(
        "module MainTest exposing (suite)\n\nsuite = []\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["elm"]
    assert seed_plan["operational_ecosystems"] == ["elm"]
    assert seed_plan["config_paths"] == ["elm.json"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Main.elm" in seed_plan["entrypoint_files"]
    assert "src/Page/Home.elm" in seed_plan["entrypoint_files"]
    assert "tests/MainTest.elm" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_vala_meson_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vala-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('demo', 'vala')\n"
        "executable('demo', ['src/main.vala', 'src/helper.vala'])\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper.vala").write_text(
        "namespace Demo.Util {\n"
        "    public class Helper : Object {\n"
        "        public string render_json () {\n"
        '            return "{}";\n'
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.vala").write_text(
        "using Demo.Util;\n"
        "\n"
        "namespace Demo.App {\n"
        "    public class App : Object {\n"
        "        public void run () {\n"
        "            Helper helper = new Helper ();\n"
        "            helper.render_json ();\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main_test.vala").write_text(
        "void main () {\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["meson", "vala"]
    assert seed_plan["operational_ecosystems"] == ["vala", "meson"]
    assert "meson.build" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.vala" in seed_plan["entrypoint_files"]
    assert "src/helper.vala" in seed_plan["candidate_file_paths"]
    assert "tests/main_test.vala" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_mql5_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mql5-profile-repo"
    (repo_path / "Experts").mkdir(parents=True)
    (repo_path / "Include").mkdir(parents=True)
    (repo_path / "Tests").mkdir(parents=True)
    (repo_path / "demo.mqproj").write_text(
        '<Project><Files><File>Experts/Main.mq5</File><File>Include/Helper.mqh</File></Files></Project>\n',
        encoding="utf-8",
    )
    (repo_path / "Include" / "Helper.mqh").write_text(
        "class Helper\n"
        "{\n"
        "public:\n"
        "   string RenderJson()\n"
        "     {\n"
        '      return "{}";\n'
        "     }\n"
        "};\n",
        encoding="utf-8",
    )
    (repo_path / "Experts" / "Main.mq5").write_text(
        '#include "../Include/Helper.mqh"\n'
        "void OnStart()\n"
        "{\n"
        "   Helper helper;\n"
        "   helper.RenderJson();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Tests" / "MainTest.mq5").write_text(
        "void OnStart()\n"
        "{\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["mql5"]
    assert seed_plan["operational_ecosystems"] == ["mql5"]
    assert "demo.mqproj" in seed_plan["config_paths"]
    assert "Experts" in seed_plan["support_roots"]
    assert "Include" in seed_plan["support_roots"]
    assert "Experts/Main.mq5" in seed_plan["entrypoint_files"]
    assert "Include/Helper.mqh" in seed_plan["candidate_file_paths"]
    assert "Tests/MainTest.mq5" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_gams_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gams-profile-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "models" / "main.gms").write_text(
        "$include ../include/common.inc\n"
        "set i /a,b/;\n"
        "parameter demand(i);\n",
        encoding="utf-8",
    )
    (repo_path / "include" / "common.inc").write_text(
        "parameter supply(i);\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["gams"]
    assert seed_plan["operational_ecosystems"] == ["gams"]
    assert "models/main.gms" in seed_plan["config_paths"]
    assert "models" in seed_plan["support_roots"]
    assert "include" in seed_plan["support_roots"]
    assert "models/main.gms" in seed_plan["entrypoint_files"]
    assert "include/common.inc" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_openscad_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "openscad-profile-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "examples").mkdir(parents=True)
    (repo_path / "main.scad").write_text(
        "include <lib/helper.scad>;\n"
        "module build() {\n"
        "  gusset(10);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "helper.scad").write_text(
        "module gusset(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "examples" / "demo.scad").write_text(
        "use <../lib/helper.scad>;\n"
        "gusset(5);\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["openscad"]
    assert seed_plan["operational_ecosystems"] == ["openscad"]
    assert "main.scad" in seed_plan["config_paths"]
    assert "main.scad" in seed_plan["entrypoint_files"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/helper.scad" in seed_plan["candidate_file_paths"]
    assert "examples/demo.scad" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_nix_flake_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nix-profile-repo"
    (repo_path / "nix" / "lib").mkdir(parents=True)
    (repo_path / "flake.nix").write_text(
        "{\n"
        "  inputs.nixpkgs.url = \"github:NixOS/nixpkgs\";\n"
        "  outputs = { self, nixpkgs }:\n"
        "    let formatter = import ./nix/lib/formatter.nix { pkgs = nixpkgs.legacyPackages.x86_64-linux; }; in {\n"
        "      formatter = formatter.mkFormatter nixpkgs.legacyPackages.x86_64-linux.alejandra;\n"
        "    };\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "nix" / "lib" / "formatter.nix").write_text(
        "{ pkgs }:\n"
        "{\n"
        "  mkFormatter = package: package;\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["nix"]
    assert seed_plan["operational_ecosystems"] == ["nix"]
    assert "flake.nix" in seed_plan["config_paths"]
    assert "flake.nix" in seed_plan["entrypoint_files"]
    assert "nix/lib" in seed_plan["support_roots"]
    assert "nix/lib/formatter.nix" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_purescript_spago_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "purescript-profile-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "spago.yaml").write_text(
        "package:\n"
        "  name: demo\n"
        "workspace:\n"
        "  package_set:\n"
        "    registry: 64.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.purs").write_text(
        "module Main where\n\nimport Data.Helper (helperValue)\n\nmain = helperValue\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Data" / "Helper.purs").write_text(
        "module Data.Helper where\n\nhelperValue :: Int\nhelperValue = 1\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "Main.purs").write_text(
        "module Test.Main where\n\nmain = 1\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["purescript"]
    assert seed_plan["operational_ecosystems"] == ["purescript"]
    assert "spago.yaml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Main.purs" in seed_plan["entrypoint_files"]
    assert "test/Main.purs" not in seed_plan["entrypoint_files"]
    assert "src/Data/Helper.purs" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_gleam_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gleam-profile-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "gleam.toml").write_text(
        'name = "demo"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.gleam").write_text(
        "import demo/helper.{render_json}\n\npub fn main() {\n  render_json()\n}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "helper.gleam").write_text(
        "pub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "main.gleam").write_text(
        "pub fn test_main() {\n  Nil\n}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["gleam"]
    assert seed_plan["operational_ecosystems"] == ["gleam"]
    assert "gleam.toml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.gleam" in seed_plan["entrypoint_files"]
    assert "test/main.gleam" not in seed_plan["entrypoint_files"]
    assert "src/demo/helper.gleam" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_janet_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "janet-profile-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "project.janet").write_text(
        '(declare-project :name "demo" :source @["src"] :main "src/main.janet")\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.janet").write_text(
        '(import ./demo/helper :as helper)\n\n(defn main []\n  (helper/render-json))\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "helper.janet").write_text(
        "(defn render-json [] @{})\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "main.janet").write_text(
        "(defn test-main [] @{})\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["janet"]
    assert seed_plan["operational_ecosystems"] == ["janet"]
    assert "project.janet" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.janet" in seed_plan["entrypoint_files"]
    assert "test/main.janet" not in seed_plan["entrypoint_files"]
    assert "src/demo/helper.janet" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_dhall_package_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dhall-profile-repo"
    (repo_path / "schemas").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "package.dhall").write_text(
        "{ Type = ./schemas/Step.dhall }\n",
        encoding="utf-8",
    )
    (repo_path / "schemas" / "Step.dhall").write_text(
        "{ Type = \"step\", default = \"run\" }\n",
        encoding="utf-8",
    )
    (repo_path / "workflow.dhall").write_text(
        "let Package = ./package.dhall\nin Package.Type\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "workflow_test.dhall").write_text(
        "let Package = ../package.dhall\nin Package.Type\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["dhall"]
    assert seed_plan["operational_ecosystems"] == ["dhall"]
    assert "package.dhall" in seed_plan["config_paths"]
    assert "package.dhall" in seed_plan["entrypoint_files"]
    assert "schemas" in seed_plan["support_roots"]
    assert "workflow.dhall" in seed_plan["candidate_file_paths"]
    assert "tests/workflow_test.dhall" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_batchfile_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "batchfile-profile-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "build.bat").write_text(
        "@echo off\n"
        "call scripts\\helper.cmd\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "helper.cmd").write_text(
        "@echo off\n"
        "echo helper\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "ignored.bat").write_text(
        "@echo off\n"
        "echo ignored\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["batchfile"]
    assert seed_plan["operational_ecosystems"] == ["batchfile"]
    assert "build.bat" in seed_plan["entrypoint_files"]
    assert "scripts" in seed_plan["support_roots"]
    assert "tests/ignored.bat" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_makefile_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "makefile-profile-repo"
    (repo_path / "mk").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Makefile").write_text(
        "include mk/common.mk\n"
        "build: clean\n"
        "\t$(MAKE) helper\n"
        "clean:\n"
        "\t@echo clean\n",
        encoding="utf-8",
    )
    (repo_path / "mk" / "common.mk").write_text(
        "helper:\n"
        "\t@echo helper\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "ignored.mk").write_text(
        "ignored:\n"
        "\t@echo ignored\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["makefile"]
    assert seed_plan["operational_ecosystems"] == ["makefile"]
    assert "Makefile" in seed_plan["entrypoint_files"]
    assert "mk" in seed_plan["support_roots"]
    assert "tests/ignored.mk" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_eiffel_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "eiffel-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "system.ecf").write_text(
        '<?xml version="1.0"?>\n'
        '<system name="demo">\n'
        '  <target name="demo">\n'
        '    <root class="APPLICATION" feature="make"/>\n'
        '    <cluster name="src" location="src"/>\n'
        "  </target>\n"
        "</system>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\n"
        "inherit\n"
        "    HELPER\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        local\n"
        "            helper: HELPER\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper.e").write_text(
        "class HELPER\n"
        "feature\n"
        "    assist\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "application_test.e").write_text(
        "class APPLICATION_TEST\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["eiffel"]
    assert seed_plan["operational_ecosystems"] == ["eiffel"]
    assert "system.ecf" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/application.e" in seed_plan["entrypoint_files"]
    assert "src/helper.e" in seed_plan["candidate_file_paths"]
    assert "tests/application_test.e" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_puppet_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "puppet-profile-repo"
    (repo_path / "manifests").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "metadata.json").write_text(
        '{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        encoding="utf-8",
    )
    (repo_path / "manifests" / "init.pp").write_text(
        "class apache {\n"
        "  include apache::params\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "manifests" / "params.pp").write_text(
        "class apache::params { }\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "init.pp").write_text(
        "class apache::tests { }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["puppet"]
    assert seed_plan["operational_ecosystems"] == ["puppet"]
    assert "metadata.json" in seed_plan["config_paths"]
    assert "manifests" in seed_plan["support_roots"]
    assert "manifests/init.pp" in seed_plan["entrypoint_files"]
    assert "manifests/params.pp" in seed_plan["candidate_file_paths"]
    assert "tests/init.pp" not in seed_plan["entrypoint_files"]


def test_candidate_ecosystems_for_path_identifies_eiffel_configs_and_sources(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "eiffel-candidate-ecosystems-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "system.ecf").write_text(
        '<?xml version="1.0"?>\n'
        '<system name="demo">\n'
        '  <target name="demo">\n'
        '    <root class="APPLICATION" feature="make"/>\n'
        '    <cluster name="src" location="src"/>\n'
        "  </target>\n"
        "</system>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )

    assert probe_module._candidate_ecosystems_for_path("system.ecf", repo_path=repo_path) == {
        "eiffel"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "src/application.e",
        repo_path=repo_path,
    ) == {"eiffel"}


def test_candidate_ecosystems_for_path_identifies_odin_configs_and_sources(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-candidate-ecosystems-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "ols.json").write_text(
        '{"profile":"default","profiles":[{"name":"default","checker_path":["src"]}]}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.odin").write_text(
        'package main\n\nimport "core:fmt"\n\nmain :: proc() {\n    fmt.println("ok")\n}\n',
        encoding="utf-8",
    )

    assert probe_module._candidate_ecosystems_for_path("ols.json", repo_path=repo_path) == {
        "odin"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "src/main.odin",
        repo_path=repo_path,
    ) == {"odin"}


def test_operational_seed_plan_without_diagnostics_uses_agda_library_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "agda-profile-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "standard-library.agda-lib").write_text(
        "name: demo\ninclude: src\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.agda").write_text(
        "module Main where\n\n"
        "open import Data.Helper using (helper)\n\n"
        "main : Set\n"
        "main = helper\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Data" / "Helper.agda").write_text(
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "Main.agda").write_text(
        "module Tests.Main where\n\nmain : Set\nmain = Set\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["agda"]
    assert seed_plan["operational_ecosystems"] == ["agda"]
    assert "standard-library.agda-lib" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Main.agda" in seed_plan["entrypoint_files"]
    assert "src/Data/Helper.agda" in seed_plan["candidate_file_paths"]
    assert "tests/Main.agda" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_idris_ipkg_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "idris-profile-repo"
    (repo_path / "src" / "Demo").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "demo.ipkg").write_text(
        "package demo\n"
        "sourcedir = src\n"
        "modules = Demo.Helper\n"
        "main = Main\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.idr").write_text(
        "module Main\n\n"
        "import Demo.Helper\n\n"
        "main : IO ()\n"
        "main = renderJson\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo" / "Helper.idr").write_text(
        "module Demo.Helper\n\n"
        "renderJson : IO ()\n"
        "renderJson = pure ()\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "Main.idr").write_text(
        "module Tests.Main\n\n"
        "testMain : IO ()\n"
        "testMain = pure ()\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["idris"]
    assert seed_plan["operational_ecosystems"] == ["idris"]
    assert seed_plan["config_paths"] == ["demo.ipkg"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Main.idr" in seed_plan["entrypoint_files"]
    assert "src/Demo/Helper.idr" in seed_plan["candidate_file_paths"]
    assert "tests/Main.idr" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_raku_meta6_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "raku-profile-repo"
    (repo_path / "lib" / "Demo").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "META6.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "provides": {"Demo::Helper": "lib/Demo/Helper.rakumod"},
                "bin": ["demo.raku"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "lib" / "Demo" / "Helper.rakumod").write_text(
        "unit module Demo::Helper;\n\nsub render-json() is export { \"{}\" }\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "demo.raku").write_text(
        "use Demo::Helper;\n\nsub main() {\n    Demo::Helper::render-json();\n}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "demo.raku").write_text(
        "sub test-main() { }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["raku"]
    assert seed_plan["operational_ecosystems"] == ["raku"]
    assert seed_plan["config_paths"] == ["META6.json"]
    assert any(root in seed_plan["support_roots"] for root in {"lib", "lib/Demo"})
    assert "bin" in seed_plan["support_roots"]
    assert "bin/demo.raku" in seed_plan["entrypoint_files"]
    assert "tests/demo.raku" not in seed_plan["entrypoint_files"]
    assert "lib/Demo/Helper.rakumod" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_nushell_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nushell-profile-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "main.nu").write_text(
        "source modules/helper.nu\n\n"
        "def main [] {\n"
        "  render-json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "helper.nu").write_text(
        "export def render-json [] {\n"
        "  '{}'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main.nu").write_text(
        "def test-main [] {\n"
        "  render-json\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["nushell"]
    assert seed_plan["operational_ecosystems"] == ["nushell"]
    assert "modules" in seed_plan["support_roots"]
    assert "main.nu" in seed_plan["entrypoint_files"]
    assert "tests/main.nu" not in seed_plan["entrypoint_files"]
    assert "modules/helper.nu" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_fish_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fish-profile-repo"
    (repo_path / "functions").mkdir(parents=True)
    (repo_path / "conf.d").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "main.fish").write_text(
        "source functions/helper.fish\n\n"
        "function main\n"
        "    helper\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "functions" / "helper.fish").write_text(
        "function helper\n"
        "    echo '{}'\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "conf.d" / "init.fish").write_text("helper\n", encoding="utf-8")
    (repo_path / "tests" / "main.fish").write_text(
        "function test_main\n"
        "    helper\n"
        "end\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["fish"]
    assert seed_plan["operational_ecosystems"] == ["fish"]
    assert "functions" in seed_plan["support_roots"]
    assert "main.fish" in seed_plan["entrypoint_files"]
    assert "conf.d/init.fish" in seed_plan["entrypoint_files"]
    assert "tests/main.fish" not in seed_plan["entrypoint_files"]
    assert "functions/helper.fish" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_rego_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rego-profile-repo"
    (repo_path / "policy" / "lib").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "policy" / "main.rego").write_text(
        "package policy.main\n\n"
        "import data.policy.lib.helpers as helper\n\n"
        "allow if {\n"
        "    helper.render_json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "policy" / "lib" / "helpers.rego").write_text(
        "package policy.lib.helpers\n\n"
        "render_json if {\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "policy_test.rego").write_text(
        "package policy.test\n\n"
        "test_allow if {\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["rego"]
    assert seed_plan["operational_ecosystems"] == ["rego"]
    assert "policy/main.rego" in seed_plan["entrypoint_files"]
    assert "policy/lib" in seed_plan["support_roots"]
    assert "policy/lib/helpers.rego" in seed_plan["candidate_file_paths"]
    assert "tests/policy_test.rego" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_yara_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "yara-profile-repo"
    (repo_path / "rules" / "lib").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "rules" / "index.yar").write_text(
        'include "./main.yar"\n'
        'include "./lib/helper.yar"\n',
        encoding="utf-8",
    )
    (repo_path / "rules" / "main.yar").write_text(
        "rule main_rule {\n"
        "  condition:\n"
        "    helper_rule\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "lib" / "helper.yar").write_text(
        "private rule helper_rule {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "rules_test.yar").write_text(
        "rule rules_test {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["yara"]
    assert seed_plan["operational_ecosystems"] == ["yara"]
    assert "rules/index.yar" in seed_plan["entrypoint_files"]
    assert "rules/lib" in seed_plan["support_roots"]
    assert "rules/lib/helper.yar" in seed_plan["candidate_file_paths"]
    assert "tests/rules_test.yar" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_glsl_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "glsl-profile-repo"
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "shaders" / "main.frag").write_text(
        '#version 300 es\n'
        '#include "../lib/noise.glsl"\n'
        "out vec4 fragColor;\n"
        "void main() {\n"
        "  fragColor = vec4(noise());\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "noise.glsl").write_text(
        "float noise() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "noise_test.frag").write_text(
        '#version 300 es\nvoid main() {}\n',
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["glsl"]
    assert seed_plan["operational_ecosystems"] == ["glsl"]
    assert "shaders/main.frag" in seed_plan["entrypoint_files"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/noise.glsl" in seed_plan["candidate_file_paths"]
    assert "tests/noise_test.frag" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_hlsl_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hlsl-profile-repo"
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "shaders" / "main.hlsl").write_text(
        '#include "../include/noise.hlsli"\n'
        "float4 RenderMain() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "include" / "noise.hlsli").write_text(
        "float NoiseValue() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "noise_test.hlsl").write_text(
        "float4 TestMain() : SV_Target {\n"
        "  return float4(0.0, 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["hlsl"]
    assert seed_plan["operational_ecosystems"] == ["hlsl"]
    assert "shaders/main.hlsl" in seed_plan["entrypoint_files"]
    assert "include" in seed_plan["support_roots"]
    assert "include/noise.hlsli" in seed_plan["candidate_file_paths"]
    assert "tests/noise_test.hlsl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_shaderlab_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shaderlab-profile-repo"
    (repo_path / "Shaders" / "Includes").mkdir(parents=True)
    (repo_path / "Tests").mkdir(parents=True)
    (repo_path / "Shaders" / "Main.shader").write_text(
        'Shader "Demo/Main" {\n'
        "SubShader {\n"
        "Pass {\n"
        "CGPROGRAM\n"
        '#include "Includes/Common.cginc"\n'
        "float4 frag() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDCG\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Shaders" / "Includes" / "Common.cginc").write_text(
        "float NoiseValue() {\n"
        "  return 0.25;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Tests" / "Preview.shader").write_text(
        'Shader "Demo/Preview" {\n'
        "SubShader { Pass { } }\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "shaderlab" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "shaderlab"
    assert "Shaders/Main.shader" in seed_plan["entrypoint_files"]
    assert "Shaders/Includes/Common.cginc" in seed_plan["candidate_file_paths"]
    assert "Tests/Preview.shader" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_coq_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coq-profile-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "_CoqProject").write_text(
        "-Q theories Demo\n"
        "theories/Main.v\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper : nat := 0.\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Main.v").write_text(
        "Require Import Helper.\n"
        "Lemma run : nat.\n"
        "Proof.\n"
        "  exact helper.\n"
        "Qed.\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "MainTest.v").write_text(
        "Lemma ignored : True.\nProof.\n exact I.\nQed.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["coq"]
    assert seed_plan["operational_ecosystems"] == ["coq"]
    assert "_CoqProject" in seed_plan["config_paths"]
    assert "theories/Main.v" in seed_plan["entrypoint_files"]
    assert "theories" in seed_plan["support_roots"]
    assert "tests/MainTest.v" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_lean_lake_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lean-profile-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "lean-toolchain").write_text(
        "leanprover/lean4:stable\n",
        encoding="utf-8",
    )
    (repo_path / "lakefile.lean").write_text(
        "package batteries where\n\n"
        "lean_lib Batteries\n",
        encoding="utf-8",
    )
    (repo_path / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 0\n",
        encoding="utf-8",
    )
    (repo_path / "Batteries" / "Main.lean").write_text(
        "import Batteries.Helper\n\n"
        "def main : Nat := Batteries.Helper.helper\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "Main.lean").write_text(
        "def ignored : Nat := 1\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["lean"]
    assert seed_plan["operational_ecosystems"] == ["lean"]
    assert "lean-toolchain" in seed_plan["config_paths"]
    assert "lakefile.lean" in seed_plan["config_paths"]
    assert "Batteries/Main.lean" in seed_plan["entrypoint_files"]
    assert "Batteries" in seed_plan["support_roots"]
    assert "test/Main.lean" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_hcl_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hcl-profile-repo"
    (repo_path / "modules" / "child").mkdir(parents=True)
    (repo_path / "main.tf").write_text(
        'module "child" {\n'
        '  source = "./modules/child"\n'
        '}\n\n'
        'variable "name" {\n'
        '  default = "demo"\n'
        '}\n\n'
        "locals {\n"
        '  prefix = "vpc-${var.name}"\n'
        "}\n\n"
        'output "full_name" {\n'
        "  value = local.prefix\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "child" / "main.tf").write_text(
        'output "child_id" {\n'
        '  value = "child"\n'
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["hcl"]
    assert seed_plan["operational_ecosystems"] == ["hcl"]
    assert "main.tf" in seed_plan["entrypoint_files"]
    assert "modules/child" in seed_plan["support_roots"]
    assert "modules/child/main.tf" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_bitbake_layer_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bitbake-profile-repo"
    (repo_path / "conf").mkdir(parents=True)
    (repo_path / "classes").mkdir(parents=True)
    (repo_path / "recipes-core" / "base").mkdir(parents=True)
    (repo_path / "recipes-core" / "images").mkdir(parents=True)
    (repo_path / "recipes-devtools" / "python" / "python3-cmake").mkdir(parents=True)
    (repo_path / "conf" / "layer.conf").write_text(
        'BBPATH .= ":${LAYERDIR}"\n'
        'BBFILES += "${LAYERDIR}/recipes-*/*/*.bb"\n',
        encoding="utf-8",
    )
    (repo_path / "classes" / "image.bbclass").write_text(
        "python do_rootfs() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "recipes-core" / "base" / "base.inc").write_text(
        'BASE_NAME = "base"\n',
        encoding="utf-8",
    )
    (repo_path / "recipes-core" / "images" / "core-image-minimal.bb").write_text(
        "require ../base/base.inc\n"
        "inherit image\n"
        'IMAGE_FEATURES += "ssh-server-dropbear"\n',
        encoding="utf-8",
    )
    (repo_path / "recipes-devtools" / "python" / "python3-cmake" / "CMakeLists.txt").write_text(
        "project(python3-cmake)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "bitbake" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "bitbake"
    assert "conf/layer.conf" in seed_plan["config_paths"]
    assert "recipes-devtools/python/python3-cmake/CMakeLists.txt" not in seed_plan["config_paths"]
    assert "classes/image.bbclass" in seed_plan["candidate_file_paths"]
    assert "recipes-core/images/core-image-minimal.bb" in seed_plan["entrypoint_files"]
    assert "classes" in seed_plan["support_roots"]
    assert "recipes-devtools/python/python3-cmake" not in seed_plan["support_roots"]
    assert "recipes-core/base/base.inc" in seed_plan["candidate_file_paths"]
    assert "recipes-devtools/python/python3-cmake/CMakeLists.txt" not in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_bicep_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bicep-profile-repo"
    (repo_path / "modules" / "child").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "bicepconfig.json").write_text("{}", encoding="utf-8")
    (repo_path / "main.bicep").write_text(
        "param name string = 'demo'\n\n"
        "module child './modules/child/main.bicep' = {\n"
        "  name: 'child'\n"
        "  params: {\n"
        "    name: name\n"
        "  }\n"
        "}\n\n"
        "output childName string = child.name\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "child" / "main.bicep").write_text(
        "param name string\n\n"
        "output childId string = name\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main.test.bicep").write_text(
        "module testDeployment '../main.bicep' = {\n"
        "  name: 'test'\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["bicep"]
    assert seed_plan["operational_ecosystems"] == ["bicep"]
    assert "bicepconfig.json" in seed_plan["config_paths"]
    assert "main.bicep" in seed_plan["entrypoint_files"]
    assert "modules/child" in seed_plan["support_roots"]
    assert "modules/child/main.bicep" in seed_plan["candidate_file_paths"]
    assert "tests/main.test.bicep" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_prefers_bicep_over_root_node_tooling(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bicep-node-mixed-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        json.dumps(
            {
                "name": "bicep-node-mixed-repo",
                "private": True,
                "scripts": {
                    "lint": "eslint .",
                },
                "devDependencies": {
                    "eslint": "^9.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    (repo_path / ".eslintrc.js").write_text(
        "module.exports = { root: true };\n",
        encoding="utf-8",
    )
    (repo_path / "bicepconfig.json").write_text("{}", encoding="utf-8")
    (repo_path / "main.bicep").write_text(
        "module child './modules/child.bicep' = {\n"
        "  name: 'child'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "child.bicep").write_text(
        "output childId string = 'demo'\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["operational_ecosystems"][0] == "bicep"
    assert "bicepconfig.json" in seed_plan["config_paths"]
    assert "package.json" in seed_plan["config_paths"]
    assert "main.bicep" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_tlaplus_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tlaplus-profile-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "MCSpec.cfg").write_text("SPECIFICATION Spec\n", encoding="utf-8")
    (repo_path / "Spec.tla").write_text(
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals, Util\n\n"
        "VARIABLES x\n\n"
        "Init == x = 0\n"
        "Next == x' = x + 1\n"
        "Spec == Init /\\ [][Next]_x\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "Util.tla").write_text(
        "---- MODULE Util ----\n"
        "Answer == 42\n",
        encoding="utf-8",
    )
    (repo_path / "MCSpec.tla").write_text(
        "---- MODULE MCSpec ----\n"
        "EXTENDS Spec\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["tlaplus"]
    assert seed_plan["operational_ecosystems"] == ["tlaplus"]
    assert "MCSpec.cfg" in seed_plan["config_paths"]
    assert "MCSpec.tla" in seed_plan["entrypoint_files"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/Util.tla" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_logtalk_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "logtalk-profile-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "loader.lgt").write_text(
        ":- initialization((\n"
        "    logtalk_load(main),\n"
        "    logtalk_load(lib/support)\n"
        ")).\n",
        encoding="utf-8",
    )
    (repo_path / "main.lgt").write_text(
        ":- object(main).\n"
        "    :- uses(support, [answer/1]).\n"
        "    run :- support::answer(_).\n"
        ":- end_object.\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "support.lgt").write_text(
        ":- object(support).\n"
        "    :- public(answer/1).\n"
        "    answer(42).\n"
        ":- end_object.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["logtalk"]
    assert seed_plan["operational_ecosystems"] == ["logtalk"]
    assert "main.lgt" in seed_plan["entrypoint_files"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/support.lgt" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_chapel_mason_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "chapel-mason-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Mason.toml").write_text(
        "[brick]\nname = \"Crypto\"\ntype = \"library\"\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Crypto.chpl").write_text(
        "module Crypto {\n"
        "use Utils;\n"
        "proc run() {\n"
        "  return helper();\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Utils.chpl").write_text(
        "module Utils {\nproc helper() { return 1; }\n}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["chapel"]
    assert seed_plan["operational_ecosystems"] == ["chapel"]
    assert "Mason.toml" in seed_plan["config_paths"]
    assert "src/Crypto.chpl" in seed_plan["entrypoint_files"]
    assert "src" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_chapel_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "chapel-manifestless-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "main.chpl").write_text(
        "module Main {\n"
        "use Utils;\n"
        "proc run() {\n"
        "  return helper();\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Utils.chpl").write_text(
        "module Utils {\nproc helper() { return 1; }\n}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["chapel"]
    assert seed_plan["operational_ecosystems"] == ["chapel"]
    assert "main.chpl" in seed_plan["entrypoint_files"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Utils.chpl" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_odin_ols_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-ols-profile-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "ols.json").write_text(
        '{"profile":"default","profiles":[{"name":"default","checker_path":["src"]}]}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.odin").write_text(
        'package main\n\nimport "src:common"\n\nmain :: proc() -> int {\n    return common.helper()\n}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "common" / "helper.odin").write_text(
        "package common\n\nhelper :: proc() -> int {\n    return 1\n}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "helper_test.odin").write_text(
        "package tests\n\nhelper_test :: proc() {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["odin"]
    assert seed_plan["operational_ecosystems"] == ["odin"]
    assert "ols.json" in seed_plan["config_paths"]
    assert "src/main.odin" in seed_plan["entrypoint_files"]
    assert "tests/helper_test.odin" not in seed_plan["entrypoint_files"]
    assert "src/common" in seed_plan["support_roots"] or "src" in seed_plan["support_roots"]
    assert "src/common/helper.odin" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_odin_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-manifestless-profile-repo"
    (repo_path / "lib" / "helper").mkdir(parents=True)
    (repo_path / "main.odin").write_text(
        'package main\n\nimport "lib:helper"\n\nmain :: proc() -> int {\n    return helper.render_json()\n}\n',
        encoding="utf-8",
    )
    (repo_path / "lib" / "helper" / "helper.odin").write_text(
        "package helper\n\nrender_json :: proc() -> int {\n    return 1\n}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["odin"]
    assert seed_plan["operational_ecosystems"] == ["odin"]
    assert "main.odin" in seed_plan["entrypoint_files"]
    assert "lib/helper" in seed_plan["support_roots"]
    assert "lib/helper/helper.odin" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_factor_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "factor-manifestless-profile-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "math" / "math.factor").write_text(
        "IN: math\n\n: square ( n -- n ) dup * ;\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "main.factor").write_text(
        "USING: math ;\nIN: app.main\n\n: run ( n -- n ) square ;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["factor"]
    assert seed_plan["operational_ecosystems"] == ["factor"]
    assert "app/main.factor" in seed_plan["entrypoint_files"]
    assert "math" in seed_plan["support_roots"] or "app" in seed_plan["support_roots"]
    assert "math/math.factor" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_cue_module_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cue-profile-repo"
    (repo_path / "cue.mod").mkdir(parents=True)
    (repo_path / "pkg" / "schema").mkdir(parents=True)
    (repo_path / "cue.mod" / "module.cue").write_text(
        'module: "example.com/demo"\n',
        encoding="utf-8",
    )
    (repo_path / "pkg" / "schema" / "schema.cue").write_text(
        "package schema\n\n#Answer: 42\n",
        encoding="utf-8",
    )
    (repo_path / "main.cue").write_text(
        'package main\n\nimport schema "example.com/demo/pkg/schema"\n\nvalue: schema.#Answer\n',
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["cue"]
    assert seed_plan["operational_ecosystems"] == ["cue"]
    assert "cue.mod/module.cue" in seed_plan["config_paths"]
    assert "main.cue" in seed_plan["entrypoint_files"]
    assert "pkg/schema" in seed_plan["support_roots"]
    assert "pkg/schema/schema.cue" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_haxe_hxml_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haxe-profile-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "build.hxml").write_text(
        "-cp src\n-main demo.Main\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "Main.hx").write_text(
        "package demo;\n"
        "\n"
        "import demo.Helper;\n"
        "\n"
        "class Main {\n"
        "    static function main() {\n"
        "        Helper.renderJson();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "Helper.hx").write_text(
        "package demo;\n"
        "\n"
        "class Helper {\n"
        "    public static function renderJson():String {\n"
        '        return "{}";\n'
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["haxe"]
    assert seed_plan["operational_ecosystems"] == ["haxe"]
    assert "build.hxml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/demo/Main.hx" in seed_plan["entrypoint_files"]
    assert "src/demo/Helper.hx" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_autohotkey_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autohotkey-profile-repo"
    (repo_path / "Lib").mkdir(parents=True)
    (repo_path / "Lib" / "Helper.ahk").write_text(
        "RenderJson(value) {\n"
        "    return value\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "Main.ahk").write_text(
        '#Include "../Lib/Helper.ahk"\n'
        "\n"
        "Main() {\n"
        '    return RenderJson("{}")\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "MainTests.ahk").write_text(
        "MainTests() {\n"
        "    return true\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["autohotkey"]
    assert seed_plan["operational_ecosystems"] == ["autohotkey"]
    assert seed_plan["config_paths"] == []
    assert "scripts/Main.ahk" in seed_plan["entrypoint_files"]
    assert "tests/MainTests.ahk" not in seed_plan["entrypoint_files"]
    assert "Lib" in seed_plan["support_roots"]
    assert "Lib/Helper.ahk" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_autoit_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autoit-profile-repo"
    (repo_path / "Includes").mkdir(parents=True)
    (repo_path / "Includes" / "Helper.au3").write_text(
        "Func RenderJson($value)\n"
        "    Return $value\n"
        "EndFunc\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "Main.au3").write_text(
        '#include "../Includes/Helper.au3"\n'
        "\n"
        "Func Main()\n"
        '    Return RenderJson("{}")\n'
        "EndFunc\n",
        encoding="utf-8",
    )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "MainTests.au3").write_text(
        "Func MainTests()\n"
        "    Return True\n"
        "EndFunc\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["autoit"]
    assert seed_plan["operational_ecosystems"] == ["autoit"]
    assert seed_plan["config_paths"] == []
    assert "scripts/Main.au3" in seed_plan["entrypoint_files"]
    assert "tests/MainTests.au3" not in seed_plan["entrypoint_files"]
    assert "Includes" in seed_plan["support_roots"]
    assert "Includes/Helper.au3" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_squirrel_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "squirrel-profile-repo"
    (repo_path / "scripts" / "vscripts").mkdir(parents=True)
    (repo_path / "scripts" / "vscripts" / "main.nut").write_text(
        'IncludeScript("ppmod");\n'
        '::main <- function () {\n'
        "  ppmod.run();\n"
        "};\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "vscripts" / "ppmod.nut").write_text(
        "::ppmod <- {\n"
        "  run = function () {\n"
        '    return "ok";\n'
        "  }\n"
        "};\n",
        encoding="utf-8",
    )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "MainTests.nut").write_text(
        "::MainTests <- function () {\n"
        "  return true;\n"
        "};\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["squirrel"]
    assert seed_plan["operational_ecosystems"] == ["squirrel"]
    assert seed_plan["config_paths"] == []
    assert "scripts/vscripts/main.nut" in seed_plan["entrypoint_files"]
    assert "tests/MainTests.nut" not in seed_plan["entrypoint_files"]
    assert "scripts/vscripts" in seed_plan["support_roots"]
    assert "scripts/vscripts/ppmod.nut" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_promotes_cython_when_cython_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cython-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "core.pyx").write_text(
        "from acme.helpers cimport render_json\n"
        "\n"
        "cpdef int run():\n"
        "    return render_json()\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "helpers.pxd").write_text(
        "cdef int render_json()\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "defs.pxi").write_text(
        "DEF ANSWER = 42\n",
        encoding="utf-8",
    )
    (repo_path / "setup.py").write_text(
        "from setuptools import setup\nsetup(name='acme')\n",
        encoding="utf-8",
    )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "test_core.pyx").write_text(
        "cpdef int test_run():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "cython" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "cython"
    assert "src/acme/core.pyx" in seed_plan["entrypoint_files"]
    assert "src/acme/helpers.pxd" in seed_plan["candidate_file_paths"]
    assert "tests/test_core.pyx" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_promotes_cuda_when_cuda_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cuda-profile-repo"
    (repo_path / "src" / "kernels").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "src" / "main.cu").write_text(
        '#include "kernels/math.cuh"\n'
        "__global__ void kernel_run(int* out) {\n"
        "  *out = add_one(*out);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "kernels" / "math.cuh").write_text(
        "__device__ inline int add_one(int x) {\n"
        "  return x + 1;\n"
        "}\n",
        encoding="utf-8",
    )
    for index in range(22):
        (repo_path / "src" / f"extra_{index}.cu").write_text(
            "__global__ void kernel_extra(int* out) {\n"
            "  *out += 1;\n"
            "}\n",
            encoding="utf-8",
        )
    for index in range(6):
        (repo_path / "include" / f"helper_{index}.cuh").write_text(
            "__device__ inline int helper(int x) {\n"
            "  return x;\n"
            "}\n",
            encoding="utf-8",
        )
    for index in range(8):
        (repo_path / "src" / f"host_{index}.cpp").write_text(
            "int run_host() {\n"
            "  return 1;\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "test_kernel.cu").write_text(
        "__global__ void test_only(int* out) {\n"
        "  *out = 0;\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "cuda" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "cuda"
    assert "src/main.cu" in seed_plan["entrypoint_files"]
    assert "src/kernels/math.cuh" in seed_plan["candidate_file_paths"]
    assert "tests/test_kernel.cu" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_promotes_cuda_in_manifest_rich_cmake_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cuda-cmake-profile-repo"
    sample_count = 12
    root_cmakelists = ["cmake_minimum_required(VERSION 3.26)", "project(cuda_samples LANGUAGES CXX CUDA)"]
    for index in range(sample_count):
        sample_dir = repo_path / "samples" / f"sample_{index}"
        sample_dir.mkdir(parents=True)
        root_cmakelists.append(f"add_subdirectory(samples/sample_{index})")
        (sample_dir / "CMakeLists.txt").write_text(
            f"add_executable(sample_{index} main.cpp kernel_{index}.cu)\n",
            encoding="utf-8",
        )
        (sample_dir / "main.cpp").write_text(
            "int main() {\n"
            "  return 0;\n"
            "}\n",
            encoding="utf-8",
        )
        (sample_dir / f"kernel_{index}.cu").write_text(
            f"__global__ void run_kernel_{index}(int* out) {{\n"
            f"  *out += {index};\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "CMakeLists.txt").write_text("\n".join(root_cmakelists) + "\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "cuda" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "cuda"
    assert any(path.endswith(".cu") for path in seed_plan["candidate_file_paths"])
    assert "samples/sample_0/CMakeLists.txt" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_promotes_stan_when_stan_surface_is_substantial(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "stan-profile-repo"
    (repo_path / "models" / "lib").mkdir(parents=True)
    (repo_path / "models" / "main.stan").write_text(
        '#include "lib/math.stan"\n'
        "\n"
        "functions {\n"
        "  real run(real x) {\n"
        "    return add_one(x);\n"
        "  }\n"
        "}\n"
        "data {\n"
        "  real x;\n"
        "}\n"
        "model {\n"
        "  target += run(x);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "lib" / "math.stan").write_text(
        "functions {\n"
        "  real add_one(real x) {\n"
        "    return x + 1;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    for index in range(6):
        (repo_path / "models" / f"extra_{index}.stan").write_text(
            "data {\n"
            f"  real x_{index};\n"
            "}\n"
            "model {\n"
            f"  target += normal_lpdf(x_{index} | 0, 1);\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "analysis").mkdir(parents=True)
    for index in range(4):
        (repo_path / "analysis" / f"plot_{index}.R").write_text(
            "print('stan profile')\n",
            encoding="utf-8",
        )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "test_model.stan").write_text(
        "data {\n  real x;\n}\nmodel {\n  target += normal_lpdf(x | 0, 1);\n}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "stan" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "stan"
    assert "models/main.stan" in seed_plan["entrypoint_files"]
    assert "models/lib/math.stan" in seed_plan["candidate_file_paths"]
    assert "tests/test_model.stan" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_starlark_bazel_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "starlark-profile-repo"
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "MODULE.bazel").write_text(
        'module(name = "acme")\n',
        encoding="utf-8",
    )
    (repo_path / "BUILD.bazel").write_text(
        'load("rules:demo.bzl", "demo_macro")\n'
        '\n'
        'demo_macro(name = "app")\n',
        encoding="utf-8",
    )
    (repo_path / "rules" / "demo.bzl").write_text(
        'load("//lib:common.bzl", "render_json")\n'
        'load(":helper.bzl", "emit_name")\n'
        "\n"
        "def demo_macro(name):\n"
        "    return emit_name(render_json(name))\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "helper.bzl").write_text(
        "def emit_name(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "common.bzl").write_text(
        "def render_json(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "demo_test.bzl").write_text(
        "def test_macro(name):\n"
        "    return name\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["starlark"]
    assert seed_plan["operational_ecosystems"] == ["starlark"]
    assert "MODULE.bazel" in seed_plan["config_paths"]
    assert "BUILD.bazel" in seed_plan["config_paths"]
    assert "BUILD.bazel" in seed_plan["entrypoint_files"]
    assert "rules/demo.bzl" in seed_plan["entrypoint_files"]
    assert "rules" in seed_plan["support_roots"]
    assert "rules/demo.bzl" in seed_plan["candidate_file_paths"]
    assert "rules/helper.bzl" in seed_plan["candidate_file_paths"]
    assert "tests/demo_test.bzl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_v_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "v-profile-repo"
    (repo_path / "src" / "helper").mkdir(parents=True)
    (repo_path / "v.mod").write_text(
        "Module {\n"
        "    name: 'demo'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.v").write_text(
        "module main\n"
        "\n"
        "import helper\n"
        "\n"
        "fn main() {\n"
        "    helper.render_json()\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper" / "helper.v").write_text(
        "module helper\n"
        "\n"
        "pub fn render_json() string {\n"
        "    return '{}'\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["v"]
    assert seed_plan["operational_ecosystems"] == ["v"]
    assert "v.mod" in seed_plan["config_paths"]
    assert "main.v" in seed_plan["entrypoint_files"]
    assert "src/helper" in seed_plan["support_roots"]
    assert "src/helper/helper.v" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_verilog_manifestless_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "verilog-profile-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "defs.vh").write_text(
        "`ifndef DEFS_VH\n"
        "`define DEFS_VH\n"
        "`endif\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.v").write_text(
        "module child;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.v").write_text(
        '`include "defs.vh"\n'
        "module top;\n"
        "  child u_child();\n"
        "endmodule\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["verilog"]
    assert seed_plan["operational_ecosystems"] == ["verilog"]
    assert "rtl/top.v" in seed_plan["entrypoint_files"]
    assert "rtl" in seed_plan["support_roots"]
    assert "rtl/child.v" in seed_plan["candidate_file_paths"]
    assert "rtl/defs.vh" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_smalltalk_ston_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "smalltalk-profile-repo"
    (repo_path / "src" / "Demo-Baseline").mkdir(parents=True)
    (repo_path / "src" / "Demo-Core").mkdir(parents=True)
    (repo_path / "tests" / "Demo-Core-Tests").mkdir(parents=True)
    (repo_path / ".smalltalk.ston").write_text("{ }\n", encoding="utf-8")
    (repo_path / "src" / "Demo-Baseline" / "package.st").write_text(
        "Package { #name : 'Demo-Baseline' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-Baseline" / "BaselineOfDemo.class.st").write_text(
        "Class {\n"
        "\t#name : 'BaselineOfDemo',\n"
        "\t#superclass : 'BaselineOf',\n"
        "\t#category : 'Demo-Baseline',\n"
        "\t#package : 'Demo-Baseline'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-Core" / "package.st").write_text(
        "Package { #name : 'Demo-Core' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-Core" / "Helper.class.st").write_text(
        "Class {\n"
        "\t#name : 'Helper',\n"
        "\t#superclass : 'Object',\n"
        "\t#category : 'Demo-Core',\n"
        "\t#package : 'Demo-Core'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "Demo-Core-Tests" / "HelperTest.class.st").write_text(
        "Class {\n"
        "\t#name : 'HelperTest',\n"
        "\t#superclass : 'TestCase',\n"
        "\t#category : 'Demo-Core-Tests',\n"
        "\t#package : 'Demo-Core-Tests'\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["smalltalk"]
    assert seed_plan["operational_ecosystems"] == ["smalltalk"]
    assert ".smalltalk.ston" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Demo-Baseline/BaselineOfDemo.class.st" in seed_plan["entrypoint_files"]
    assert "src/Demo-Core/Helper.class.st" in seed_plan["candidate_file_paths"]
    assert "tests/Demo-Core-Tests/HelperTest.class.st" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_emacslisp_cask_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "emacslisp-profile-repo"
    (repo_path / "lisp").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Cask").write_text(
        "(source gnu)\n"
        '(package-file "main.el")\n',
        encoding="utf-8",
    )
    (repo_path / "main.el").write_text(
        "(require 'helper)\n"
        "(provide 'main)\n"
        "(defun run () (helper-fn))\n",
        encoding="utf-8",
    )
    (repo_path / "lisp" / "helper.el").write_text(
        "(provide 'helper)\n"
        "(defun helper-fn () 1)\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main-test.el").write_text(
        "(provide 'main-test)\n"
        "(defun run-test () t)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["emacslisp"]
    assert seed_plan["operational_ecosystems"] == ["emacslisp"]
    assert seed_plan["config_paths"] == ["Cask"]
    assert "lisp" in seed_plan["support_roots"]
    assert "main.el" in seed_plan["entrypoint_files"]
    assert "lisp/helper.el" in seed_plan["entrypoint_files"]
    assert "tests/main-test.el" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_vimscript_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vimscript-profile-repo"
    (repo_path / "plugin").mkdir(parents=True)
    (repo_path / "autoload").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "vimrc").write_text("set runtimepath^=.\n", encoding="utf-8")
    (repo_path / "autoload" / "fugitive.vim").write_text(
        "function! fugitive#run()\n"
        "  return '{}'\n"
        "endfunction\n",
        encoding="utf-8",
    )
    (repo_path / "plugin" / "fugitive.vim").write_text(
        "source ../autoload/fugitive.vim\n"
        "call fugitive#run()\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "fugitive_spec.vim").write_text(
        "call assert_equal('{}', fugitive#run())\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["vimscript"]
    assert seed_plan["operational_ecosystems"] == ["vimscript"]
    assert "vimrc" in seed_plan["config_paths"]
    assert "plugin/fugitive.vim" in seed_plan["entrypoint_files"]
    assert "tests/fugitive_spec.vim" not in seed_plan["entrypoint_files"]
    assert "autoload" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_uses_racket_info_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "racket-profile-repo"
    (repo_path / "private").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "info.rkt").write_text(
        "#lang info\n"
        '(define collection "racket-profile-repo")\n',
        encoding="utf-8",
    )
    (repo_path / "main.rkt").write_text(
        "#lang racket\n"
        '(require "private/helper.rkt")\n'
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "private" / "helper.rkt").write_text(
        "#lang racket\n"
        "(define (helper) 1)\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main-test.rkt").write_text(
        "#lang racket\n"
        "(define (test-run) 1)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["racket"]
    assert seed_plan["operational_ecosystems"] == ["racket"]
    assert seed_plan["config_paths"] == ["info.rkt"]
    assert "private" in seed_plan["support_roots"]
    assert "main.rkt" in seed_plan["entrypoint_files"]
    assert "private/helper.rkt" in seed_plan["entrypoint_files"]
    assert "tests/main-test.rkt" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_scheme_package_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scheme-profile-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "package.scm").write_text(
        "(define-library (acme app)\n"
        "  (export run)\n"
        "  (import (acme helper))\n"
        "  (begin\n"
        "    (define (run) (helper))))\n",
        encoding="utf-8",
    )
    (repo_path / "main.scm").write_text(
        "#!r6rs\n"
        "(import (acme helper))\n"
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "helper.sld").write_text(
        "(define-library (acme helper)\n"
        "  (export helper)\n"
        "  (begin\n"
        "    (define (helper) 1)))\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "helper-test.scm").write_text(
        "#!r6rs\n"
        "(define (test-helper) 1)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["scheme"]
    assert seed_plan["operational_ecosystems"] == ["scheme"]
    assert seed_plan["config_paths"] == ["package.scm"]
    assert any(root == "lib" or root.startswith("lib/") for root in seed_plan["support_roots"])
    assert "main.scm" in seed_plan["entrypoint_files"]
    assert "lib/acme/helper.sld" in seed_plan["entrypoint_files"]
    assert "tests/helper-test.scm" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_xpp_descriptor_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "xpp-profile-repo"
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
    ).mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Descriptor"
    ).mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Descriptor"
        / "Acme.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxModelInfo>\n"
        "  <Name>Acme</Name>\n"
        "</AxModelInfo>\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
        / "BaseWorker.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>BaseWorker</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class BaseWorker\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "  </SourceCode>\n"
        "</AxClass>\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
        / "MainWorker.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>MainWorker</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class MainWorker extends BaseWorker\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "    <Methods>\n"
        "      <Method>\n"
        "        <Name>boot</Name>\n"
        "        <Source><![CDATA[\n"
        "public static void boot()\n"
        "{\n"
        "    BaseWorker::doWork();\n"
        "}\n"
        "]]></Source>\n"
        "      </Method>\n"
        "    </Methods>\n"
        "  </SourceCode>\n"
        "</AxClass>\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Tests"
        / "AxClass"
    ).mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Tests"
        / "AxClass"
        / "MainWorkerTest.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>MainWorkerTest</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class MainWorkerTest\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "  </SourceCode>\n"
        "</AxClass>\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["xpp"]
    assert seed_plan["operational_ecosystems"] == ["xpp"]
    assert seed_plan["config_paths"] == ["PackagesLocalDirectory/Acme/Descriptor/Acme.xml"]
    assert "PackagesLocalDirectory/Acme/Acme/AxClass" in seed_plan["support_roots"]
    assert "PackagesLocalDirectory/Acme/Acme/AxClass/MainWorker.xml" in seed_plan["entrypoint_files"]
    assert "PackagesLocalDirectory/Acme/Acme/AxClass/BaseWorker.xml" in seed_plan["entrypoint_files"]
    assert "PackagesLocalDirectory/Acme/Tests/AxClass/MainWorkerTest.xml" not in seed_plan[
        "entrypoint_files"
    ]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_scratch_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scratch-profile-repo"
    _write_scratch_project(
        repo_path / "games" / "Maze.sb3",
        _scratch_project_payload(),
    )
    _write_scratch_project(
        repo_path / "tests" / "MazeTest.sb3",
        _scratch_project_payload(name="TestSprite"),
    )
    (repo_path / "README.md").write_text("# Scratch Repo\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["scratch"]
    assert seed_plan["operational_ecosystems"] == ["scratch"]
    assert seed_plan["config_paths"] == []
    assert "games" in seed_plan["support_roots"]
    assert "games/Maze.sb3" in seed_plan["entrypoint_files"]
    assert "tests/MazeTest.sb3" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_labview_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "labview-profile-repo"
    (repo_path / "Source" / "Libraries").mkdir(parents=True)
    (repo_path / "Source" / "Controls").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "App.lvproj").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Project Type=\"Project\">\n"
        '  <Item Name="Main" Type="VI" URL="Source/Main.vi" />\n'
        '  <Item Name="Helpers" Type="Library" URL="Source/Libraries/Helpers.lvlib" />\n'
        '  <Item Name="Config" Type="Control" URL="Source/Controls/Config.ctl" />\n'
        '  <Item Name="MainTest" Type="VI" URL="tests/MainTest.vi" />\n'
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "Source" / "Libraries" / "Helpers.lvlib").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Library Name=\"Helpers\">\n"
        '  <Item Name="Helper" Type="VI" URL="Helper.vi" />\n'
        "</Library>\n",
        encoding="utf-8",
    )
    (repo_path / "Source" / "Main.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")
    (repo_path / "Source" / "Libraries" / "Helper.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")
    (repo_path / "Source" / "Controls" / "Config.ctl").write_bytes(b"RSRC\r\n\x00\x03LVCCLBVW")
    (repo_path / "tests" / "MainTest.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["labview"]
    assert seed_plan["operational_ecosystems"] == ["labview"]
    assert "App.lvproj" in seed_plan["config_paths"]
    assert "Source" in seed_plan["support_roots"]
    assert "Source/Libraries" in seed_plan["support_roots"]
    assert "Source/Controls" in seed_plan["support_roots"]
    assert "Source/Main.vi" in seed_plan["entrypoint_files"]
    assert "Source/Libraries/Helpers.lvlib" in seed_plan["entrypoint_files"]
    assert "Source/Controls/Config.ctl" not in seed_plan["entrypoint_files"]
    assert "tests/MainTest.vi" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_tcl_pkgindex_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tcl-profile-repo"
    (repo_path / "modules" / "demo").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "modules" / "demo" / "pkgIndex.tcl").write_text(
        "package ifneeded demo 1.0 [list source [file join $dir demo.tcl]]\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "demo" / "helpers.tcl").write_text(
        "package provide helpers 1.0\n"
        "proc ::helpers::run {} {\n"
        "    return ok\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "demo" / "demo.tcl").write_text(
        "package provide demo 1.0\n"
        "source helpers.tcl\n"
        "proc ::demo::main {} {\n"
        "    ::helpers::run\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "demo_test.tcl").write_text(
        "source ../modules/demo/demo.tcl\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["tcl"]
    assert seed_plan["operational_ecosystems"] == ["tcl"]
    assert "modules/demo/pkgIndex.tcl" in seed_plan["config_paths"]
    assert "modules/demo" in seed_plan["support_roots"]
    assert "modules/demo/demo.tcl" in seed_plan["entrypoint_files"]
    assert "modules/demo/pkgIndex.tcl" not in seed_plan["entrypoint_files"]
    assert "tests/demo_test.tcl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_systemverilog_bender_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "systemverilog-profile-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Bender.yml").write_text(
        "sources:\n"
        "  - rtl/defs.svh\n"
        "  - rtl/child.sv\n"
        "  - rtl/top.sv\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "defs.svh").write_text(
        "package util_pkg;\n"
        "  function int helper();\n"
        "    return 1;\n"
        "  endfunction\n"
        "endpackage\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.sv").write_text(
        "module child;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.sv").write_text(
        '`include "defs.svh"\n'
        "import util_pkg::*;\n"
        "module top;\n"
        "  child u_child();\n"
        "  int value = util_pkg::helper();\n"
        "endmodule\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "top_test.sv").write_text(
        "module top_test;\n"
        "  top dut();\n"
        "endmodule\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["systemverilog"]
    assert seed_plan["operational_ecosystems"] == ["systemverilog"]
    assert "Bender.yml" in seed_plan["config_paths"]
    assert "rtl" in seed_plan["support_roots"]
    assert "rtl/top.sv" in seed_plan["entrypoint_files"]
    assert "rtl/defs.svh" not in seed_plan["entrypoint_files"]
    assert "tests/top_test.sv" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_project_godot_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gdscript-profile-repo"
    (repo_path / "src" / "Autoload").mkdir(parents=True)
    (repo_path / "scenes").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "project.godot").write_text(
        "[application]\n"
        'run/main_scene="res://scenes/main.tscn"\n'
        "\n"
        "[autoload]\n"
        'Global="*res://src/Autoload/Global.gd"\n',
        encoding="utf-8",
    )
    (repo_path / "scenes" / "main.tscn").write_text(
        '[gd_scene format=3]\n'
        '[ext_resource type="Script" path="res://src/main.gd" id="1"]\n'
        '[node name="Root" type="Node"]\n'
        'script = ExtResource("1")\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.gd").write_text(
        "class_name MainScene\n"
        "extends Node\n"
        "func _ready() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Autoload" / "Global.gd").write_text(
        "class_name Global\n"
        "extends Node\n"
        "func ping() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "player_test.gd").write_text(
        "extends Node\n"
        "func _ready() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["gdscript"]
    assert seed_plan["operational_ecosystems"] == ["gdscript"]
    assert "project.godot" in seed_plan["config_paths"]
    assert any(root in seed_plan["support_roots"] for root in {"src", "src/Autoload"})
    assert "src/main.gd" in seed_plan["entrypoint_files"]
    assert "src/Autoload/Global.gd" in seed_plan["entrypoint_files"]
    assert "tests/player_test.gd" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_gml_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gml-profile-repo"
    (repo_path / "scripts" / "tree_runtime").mkdir(parents=True)
    (repo_path / "scripts" / "tree_api").mkdir(parents=True)
    (repo_path / "objects" / "Entity").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "BehaviorTree.yyp").write_text(
        "{\n"
        '  "resources": [\n'
        '    {\n'
        '      "id": {\n'
        '        "path": "scripts/tree_runtime/tree_runtime.yy",\n'
        "      },\n"
        "    },\n"
        '    {\n'
        '      "id": {\n'
        '        "path": "scripts/tree_api/tree_api.yy",\n'
        "      },\n"
        "    },\n"
        '    {\n'
        '      "id": {\n'
        '        "path": "objects/Entity/Entity.yy",\n'
        "      },\n"
        "    },\n"
        "  ],\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "tree_runtime" / "tree_runtime.yy").write_text(
        "{\n}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "tree_runtime" / "tree_runtime.gml").write_text(
        "function __BHTree() constructor {\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "tree_api" / "tree_api.yy").write_text(
        "{\n}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "tree_api" / "tree_api.gml").write_text(
        "function bh_tree() {\n"
        "    return new __BHTree();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "objects" / "Entity" / "Entity.yy").write_text(
        "{\n}\n",
        encoding="utf-8",
    )
    (repo_path / "objects" / "Entity" / "Create_0.gml").write_text(
        "function setup() {\n"
        "    return bh_tree();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "tree_test.gml").write_text(
        "function tree_test() {\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["gml"]
    assert seed_plan["operational_ecosystems"] == ["gml"]
    assert "BehaviorTree.yyp" in seed_plan["config_paths"]
    assert any(root in seed_plan["support_roots"] for root in {"scripts", "scripts/tree_api"})
    assert any(root in seed_plan["support_roots"] for root in {"objects", "objects/Entity"})
    assert "scripts/tree_runtime/tree_runtime.gml" in seed_plan["entrypoint_files"]
    assert "scripts/tree_api/tree_api.gml" in seed_plan["entrypoint_files"]
    assert "objects/Entity/Create_0.gml" in seed_plan["entrypoint_files"]
    assert "tests/tree_test.gml" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_vhdl_ls_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vhdl-profile-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "tb").mkdir(parents=True)
    (repo_path / "vhdl_ls.toml").write_text(
        "[libraries.work]\n"
        "files = [\n"
        '  "rtl/defs.vhd",\n'
        '  "rtl/child.vhd",\n'
        '  "rtl/top.vhd",\n'
        '  "tb/top_tb.vhd",\n'
        "]\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "defs.vhd").write_text(
        "package util_pkg is\n"
        "  function helper return integer;\n"
        "end package;\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.vhd").write_text(
        "entity child is\n"
        "end entity;\n"
        "architecture rtl of child is\n"
        "begin\n"
        "end architecture;\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.vhd").write_text(
        "library work;\n"
        "use work.util_pkg.all;\n"
        "entity top is\n"
        "end entity;\n"
        "architecture rtl of top is\n"
        "begin\n"
        "  u_child: entity work.child port map();\n"
        "end architecture;\n",
        encoding="utf-8",
    )
    (repo_path / "tb" / "top_tb.vhd").write_text(
        "entity top_tb is\n"
        "end entity;\n"
        "architecture tb of top_tb is\n"
        "begin\n"
        "  dut: entity work.top port map();\n"
        "end architecture;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["vhdl"]
    assert seed_plan["operational_ecosystems"] == ["vhdl"]
    assert "vhdl_ls.toml" in seed_plan["config_paths"]
    assert "rtl" in seed_plan["support_roots"]
    assert "rtl/top.vhd" in seed_plan["entrypoint_files"]
    assert "rtl/defs.vhd" not in seed_plan["entrypoint_files"]
    assert "tb/top_tb.vhd" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_rpg_iproj_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rpg-profile-repo"
    (repo_path / "QRPGLESRC").mkdir(parents=True)
    (repo_path / "QPROTOSRC").mkdir(parents=True)
    (repo_path / "iproj.json").write_text(
        '{\n'
        '  "includePath": ["QPROTOSRC"],\n'
        '  "compileCommand": "/QOpenSys/pkgs/bin/makei c -f {filename}"\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "QPROTOSRC" / "CUSTOMER.RPGLEINC").write_text(
        "dcl-ds Customer qualified;\n"
        "   id packed(5);\n"
        "end-ds;\n",
        encoding="utf-8",
    )
    (repo_path / "QRPGLESRC" / "ORD101.PGM.RPGLE").write_text(
        "**free\n"
        "dcl-proc Updord export;\n"
        "   dcl-pi *n ind;\n"
        "      id packed(5);\n"
        "   end-pi;\n"
        "   return *on;\n"
        "end-proc;\n",
        encoding="utf-8",
    )
    (repo_path / "QRPGLESRC" / "ORD100.PGM.RPGLE").write_text(
        "**free\n"
        "/copy CUSTOMER.RPGLEINC\n"
        "dcl-pr Updord extpgm('ORD101');\n"
        "   id packed(5);\n"
        "end-pr;\n"
        "dcl-proc Run export;\n"
        "   dcl-pi *n;\n"
        "   end-pi;\n"
        "   return Updord(1);\n"
        "end-proc;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["rpg"]
    assert seed_plan["operational_ecosystems"] == ["rpg"]
    assert "iproj.json" in seed_plan["config_paths"]
    assert "QRPGLESRC" in seed_plan["support_roots"]
    assert "QPROTOSRC" in seed_plan["support_roots"]
    assert "QRPGLESRC/ORD100.PGM.RPGLE" in seed_plan["entrypoint_files"]
    assert "QRPGLESRC/ORD101.PGM.RPGLE" in seed_plan["entrypoint_files"]
    assert "QPROTOSRC/CUSTOMER.RPGLEINC" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_apex_sfdx_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "apex-profile-repo"
    (repo_path / "force-app" / "main" / "default" / "classes").mkdir(parents=True)
    (repo_path / "force-app" / "main" / "default" / "triggers").mkdir(parents=True)
    (repo_path / "sfdx-project.json").write_text(
        '{\n'
        '  "packageDirectories": [\n'
        '    { "path": "force-app", "default": true }\n'
        "  ],\n"
        '  "sourceApiVersion": "60.0"\n'
        '}\n',
        encoding="utf-8",
    )
    (
        repo_path
        / "force-app"
        / "main"
        / "default"
        / "classes"
        / "AccountTriggerHandler.cls"
    ).write_text(
        "public with sharing class AccountTriggerHandler {\n"
        "    public static void run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "force-app"
        / "main"
        / "default"
        / "classes"
        / "AccountTriggerHandlerTest.cls"
    ).write_text(
        "@IsTest\n"
        "private class AccountTriggerHandlerTest {\n"
        "    @IsTest static void testRun() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "force-app"
        / "main"
        / "default"
        / "triggers"
        / "AccountTrigger.trigger"
    ).write_text(
        "trigger AccountTrigger on Account (before insert) {\n"
        "    AccountTriggerHandler.run();\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["apex"]
    assert seed_plan["operational_ecosystems"] == ["apex"]
    assert "sfdx-project.json" in seed_plan["config_paths"]
    assert "force-app/main/default/classes" in seed_plan["support_roots"]
    assert "force-app/main/default/triggers" in seed_plan["support_roots"]
    assert "force-app/main/default/classes/AccountTriggerHandler.cls" in seed_plan["entrypoint_files"]
    assert "force-app/main/default/triggers/AccountTrigger.trigger" in seed_plan["entrypoint_files"]
    assert (
        "force-app/main/default/classes/AccountTriggerHandlerTest.cls"
        not in seed_plan["entrypoint_files"]
    )


def test_operational_seed_plan_without_diagnostics_uses_wolfram_paclet_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "wolfram-profile-repo"
    (repo_path / "Kernel").mkdir(parents=True)
    (repo_path / "Resources").mkdir(parents=True)
    (repo_path / "PacletInfo.wl").write_text(
        'PacletObject[<|"Name" -> "Acme/Test", "Extensions" -> {{"Kernel", "Root" -> "Kernel", "Context" -> {"Acme`"}}}|>]\n',
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "init.m").write_text(
        'Get["Acme`Main`"];\n',
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "Main.wl").write_text(
        'BeginPackage["Acme`", {"Acme`Helpers`"}];\n'
        'run::usage = "run";\n'
        'Begin["`Private`"];\n'
        "run[] := helper[];\n"
        "End[];\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "Helpers.wl").write_text(
        'BeginPackage["Acme`"];\n'
        'helper::usage = "helper";\n'
        'Begin["`Private`"];\n'
        "helper[] := 1;\n"
        "End[];\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )
    (repo_path / "Resources" / "Tooling.wl").write_text(
        "tooling[] := 1;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["wolfram"]
    assert seed_plan["operational_ecosystems"] == ["wolfram"]
    assert "PacletInfo.wl" in seed_plan["config_paths"]
    assert "Kernel" in seed_plan["support_roots"]
    assert "Resources" in seed_plan["support_roots"]
    assert "Kernel/init.m" in seed_plan["entrypoint_files"]
    assert "Kernel/Main.wl" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_ada_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ada-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "alire.toml").write_text(
        'name = "acme"\n'
        'executables = ["main"]\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.adb").write_text(
        "with Acme.Util;\n"
        "procedure Main is\n"
        "begin\n"
        "   Acme.Util.Helper;\n"
        "end Main;\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme-util.adb").write_text(
        "package body Acme.Util is\n"
        "   procedure Helper is\n"
        "   begin\n"
        "      null;\n"
        "   end Helper;\n"
        "end Acme.Util;\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main_tests.adb").write_text(
        "procedure Main_Tests is\nbegin\n   null;\nend Main_Tests;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "ada" in seed_plan["detected_ecosystems"]
    assert "alire.toml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.adb" in seed_plan["entrypoint_files"]
    assert "src/acme-util.adb" in seed_plan["entrypoint_files"]
    assert "tests/main_tests.adb" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_fpm_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fortran-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "fpm.toml").write_text(
        'name = "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.f90").write_text(
        "module acme\nimplicit none\nend module acme\n",
        encoding="utf-8",
    )
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "app" / "main.f90").write_text(
        "program main\nuse acme\nend program main\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "main.f90").write_text(
        "program test_main\nend program test_main\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "fortran" in seed_plan["detected_ecosystems"]
    assert "fpm.toml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "app" in seed_plan["support_roots"]
    assert "src/acme.f90" in seed_plan["entrypoint_files"]
    assert "app/main.f90" in seed_plan["entrypoint_files"]
    assert "test/main.f90" not in seed_plan["entrypoint_files"]


def test_connected_dependency_map_follows_fortran_use_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "fortran-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "fpm.toml").write_text(
        'name = "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "math_utils.f90").write_text(
        "module math_utils\n"
        "implicit none\n"
        "contains\n"
        "subroutine helper()\n"
        "end subroutine helper\n"
        "end module math_utils\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.f90").write_text(
        "program main\n"
        "use math_utils, only: helper\n"
        "implicit none\n"
        "call helper()\n"
        "end program main\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.f90"],
        bridge_paths=["src"],
        include_patterns=[
            "src/**/*.f90",
            "src/*.f90",
            "src/**/*.f95",
            "src/*.f95",
            "src/**/*.f03",
            "src/*.f03",
            "src/**/*.f08",
            "src/*.f08",
            "src/**/*.f",
            "src/*.f",
            "src/**/*.for",
            "src/*.for",
            "fpm.toml",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/main.f90",
        "src/math_utils.f90",
    ]


def test_connected_dependency_map_follows_ada_with_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "ada-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "alire.toml").write_text(
        'name = "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme-util.adb").write_text(
        "package body Acme.Util is\n"
        "   procedure Helper is\n"
        "   begin\n"
        "      null;\n"
        "   end Helper;\n"
        "end Acme.Util;\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.adb").write_text(
        "with Acme.Util;\n"
        "procedure Main is\n"
        "begin\n"
        "   Acme.Util.Helper;\n"
        "end Main;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.adb"],
        bridge_paths=["src"],
        include_patterns=[
            "src/**/*.adb",
            "src/*.adb",
            "src/**/*.ads",
            "src/*.ads",
            "*.adb",
            "*.ads",
            "*.ada",
            "alire.toml",
            "*.gpr",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme-util.adb",
        "src/main.adb",
    ]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_cobol_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cobol-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "copybooks").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "MAINAPP.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. MAINAPP.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       COPY PERSON-REC.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           CALL \"UTILS\".\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "UTILS.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. UTILS.\n"
        "       PROCEDURE DIVISION.\n"
        "       UTILS-MAIN.\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )
    (repo_path / "copybooks" / "PERSON-REC.cpy").write_text(
        "       01 PERSON-REC.\n"
        "          05 PERSON-ID PIC 9(4).\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "MAINAPP_TEST.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. MAINAPP-TEST.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["cobol"]
    assert "src/MAINAPP.cbl" in seed_plan["entrypoint_files"]
    assert "copybooks/PERSON-REC.cpy" not in seed_plan["entrypoint_files"]
    assert "tests/MAINAPP_TEST.cbl" not in seed_plan["entrypoint_files"]
    assert "copybooks/PERSON-REC.cpy" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_pascal_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "pascal-project-repo"
    (repo_path / "app" / "source").mkdir(parents=True)
    (repo_path / "app" / "tests").mkdir(parents=True)
    (repo_path / "app" / "Acme.lpi").write_text("<CONFIG></CONFIG>\n", encoding="utf-8")
    (repo_path / "app" / "main.lpr").write_text(
        "program AcmeApp;\n"
        "uses AcmeUtil;\n"
        "begin\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "source" / "AcmeUtil.pas").write_text(
        "unit AcmeUtil;\n"
        "interface\n"
        "procedure Helper;\n"
        "implementation\n"
        "procedure Helper;\n"
        "begin\n"
        "end;\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "tests" / "MainTests.pas").write_text(
        "unit MainTests;\ninterface\nimplementation\nend.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "pascal" in seed_plan["detected_ecosystems"]
    assert "app/Acme.lpi" in seed_plan["config_paths"]
    assert "app" in seed_plan["support_roots"]
    assert "app/source" in seed_plan["support_roots"]
    assert "app/main.lpr" in seed_plan["entrypoint_files"]
    assert "app/tests/MainTests.pas" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_delphi_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "delphi-project-repo"
    (repo_path / "App" / "source").mkdir(parents=True)
    (repo_path / "App" / "tests").mkdir(parents=True)
    (repo_path / "App" / "AcmeApp.dproj").write_text(
        "<Project>\n"
        "  <MainSource>AcmeApp.dpr</MainSource>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "AcmeApp.dpr").write_text(
        "program AcmeApp;\n"
        "uses MainForm in 'source/MainForm.pas';\n"
        "begin\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "source" / "MainForm.pas").write_text(
        "unit MainForm;\n"
        "interface\n"
        "uses System.SysUtils, Vcl.Forms;\n"
        "{$R *.dfm}\n"
        "implementation\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "tests" / "MainTests.pas").write_text(
        "unit MainTests;\ninterface\nimplementation\nend.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["delphi"]
    assert seed_plan["operational_ecosystems"] == ["delphi"]
    assert "App/AcmeApp.dproj" in seed_plan["config_paths"]
    assert "App" in seed_plan["support_roots"]
    assert "App/source" in seed_plan["support_roots"]
    assert "App/AcmeApp.dpr" in seed_plan["entrypoint_files"]
    assert "App/source/MainForm.pas" in seed_plan["candidate_file_paths"]
    assert "App/tests/MainTests.pas" not in seed_plan["entrypoint_files"]


def test_connected_dependency_map_follows_pascal_uses_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "pascal-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Acme.lpi").write_text("<CONFIG></CONFIG>\n", encoding="utf-8")
    (repo_path / "src" / "AcmeUtil.pas").write_text(
        "unit AcmeUtil;\n"
        "interface\n"
        "procedure Helper;\n"
        "implementation\n"
        "procedure Helper;\n"
        "begin\n"
        "end;\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "main.lpr").write_text(
        "program AcmeApp;\n"
        "uses AcmeUtil;\n"
        "begin\n"
        "  AcmeUtil.Helper;\n"
        "end.\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.lpr"],
        bridge_paths=["src"],
        include_patterns=[
            "src/**/*.pas",
            "src/*.pas",
            "*.pas",
            "*.pp",
            "*.lpr",
            "*.dpr",
            "*.dpk",
            "*.lpi",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "main.lpr",
        "src/AcmeUtil.pas",
    ]


def test_connected_dependency_map_follows_delphi_uses_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "delphi-connected-map-repo"
    (repo_path / "App" / "source").mkdir(parents=True)
    (repo_path / "App" / "AcmeApp.dproj").write_text(
        "<Project>\n"
        "  <MainSource>AcmeApp.dpr</MainSource>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "source" / "MainForm.pas").write_text(
        "unit MainForm;\n"
        "interface\n"
        "uses System.SysUtils, Vcl.Forms;\n"
        "type\n"
        "  TMainForm = class\n"
        "  public\n"
        "    class procedure Run;\n"
        "  end;\n"
        "{$R *.dfm}\n"
        "implementation\n"
        "class procedure TMainForm.Run;\n"
        "begin\n"
        "end;\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "AcmeApp.dpr").write_text(
        "program AcmeApp;\n"
        "uses MainForm in 'source/MainForm.pas';\n"
        "begin\n"
        "  MainForm.Run;\n"
        "end.\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["App/AcmeApp.dpr"],
        bridge_paths=["App/source"],
        include_patterns=[
            "App/**/*.pas",
            "App/*.pas",
            "App/*.dpr",
            "App/*.dpk",
            "App/*.dproj",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "App/AcmeApp.dpr",
        "App/source/MainForm.pas",
    ]


def test_connected_dependency_map_follows_cobol_copy_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "cobol-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "copybooks").mkdir(parents=True)
    (repo_path / "src" / "MAINAPP.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. MAINAPP.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       COPY PERSON-REC.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           CALL \"UTILS\".\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "UTILS.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. UTILS.\n"
        "       PROCEDURE DIVISION.\n"
        "       UTILS-MAIN.\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )
    (repo_path / "copybooks" / "PERSON-REC.cpy").write_text(
        "       01 PERSON-REC.\n"
        "          05 PERSON-ID PIC 9(4).\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/MAINAPP.cbl"],
        bridge_paths=["src", "copybooks"],
        include_patterns=[
            "src/**/*.cbl",
            "src/*.cbl",
            "src/**/*.cob",
            "src/*.cob",
            "copybooks/**/*.cpy",
            "copybooks/*.cpy",
            "*.cbl",
            "*.cob",
            "*.cobol",
            "*.cpy",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "copybooks/PERSON-REC.cpy",
        "src/MAINAPP.cbl",
        "src/UTILS.cbl",
    ]


def test_connected_dependency_map_follows_rpg_copy_and_extpgm_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "rpg-connected-map-repo"
    (repo_path / "QRPGLESRC").mkdir(parents=True)
    (repo_path / "QPROTOSRC").mkdir(parents=True)
    (repo_path / "QPROTOSRC" / "CUSTOMER.RPGLEINC").write_text(
        "dcl-ds Customer qualified;\n"
        "   id packed(5);\n"
        "end-ds;\n",
        encoding="utf-8",
    )
    (repo_path / "QRPGLESRC" / "ORD101.PGM.RPGLE").write_text(
        "**free\n"
        "dcl-proc Updord export;\n"
        "   dcl-pi *n ind;\n"
        "      id packed(5);\n"
        "   end-pi;\n"
        "   return *on;\n"
        "end-proc;\n",
        encoding="utf-8",
    )
    (repo_path / "QRPGLESRC" / "ORD100.PGM.RPGLE").write_text(
        "**free\n"
        "/copy CUSTOMER.RPGLEINC\n"
        "dcl-pr Updord extpgm('ORD101');\n"
        "   id packed(5);\n"
        "end-pr;\n"
        "dcl-proc Run export;\n"
        "   dcl-pi *n;\n"
        "   end-pi;\n"
        "   return Updord(1);\n"
        "end-proc;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["QRPGLESRC/ORD100.PGM.RPGLE"],
        bridge_paths=["QRPGLESRC", "QPROTOSRC"],
        include_patterns=[
            "QRPGLESRC/**/*.RPGLE",
            "QRPGLESRC/*.RPGLE",
            "QRPGLESRC/**/*.SQLRPGLE",
            "QRPGLESRC/*.SQLRPGLE",
            "QPROTOSRC/**/*.RPGLEINC",
            "QPROTOSRC/*.RPGLEINC",
            "*.RPGLE",
            "*.SQLRPGLE",
            "*.RPGLEINC",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "QPROTOSRC/CUSTOMER.RPGLEINC",
        "QRPGLESRC/ORD100.PGM.RPGLE",
        "QRPGLESRC/ORD101.PGM.RPGLE",
    ]


def test_connected_dependency_map_follows_ladder_jsr_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "ladder-connected-map-repo"
    (repo_path / "logic").mkdir(parents=True)
    (repo_path / "logic" / "Child.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="SupportProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="ChildRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[XIC(StartPB)OTE(RunMotor);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "logic" / "Main.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="MainProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="MainRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[JSR(ChildRoutine,0);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["logic/Main.L5X"],
        bridge_paths=["logic"],
        include_patterns=[
            "logic/**/*.L5X",
            "logic/*.L5X",
            "*.L5X",
            "logic/**/*.l5x",
            "logic/*.l5x",
            "*.l5x",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "logic/Child.L5X",
        "logic/Main.L5X",
    ]


def test_connected_dependency_map_follows_actionscript_import_and_extends_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "actionscript-connected-map-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "base").mkdir(parents=True)
    (repo_path / "src" / "demo" / "utils").mkdir(parents=True)
    (repo_path / "src" / "demo" / "base" / "BaseActor.as").write_text(
        "package demo.base {\n"
        "    public class BaseActor {\n"
        "        public function baseReady():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "utils" / "Utils.as").write_text(
        "package demo.utils {\n"
        "    public class Utils {\n"
        "        public static function helper():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "app" / "Main.as").write_text(
        "package demo.app {\n"
        "    import demo.base.BaseActor;\n"
        "    import demo.utils.Utils;\n"
        "    public class Main extends BaseActor {\n"
        "        public function boot():void {\n"
        "            var utils:Utils = new Utils();\n"
        "            Utils.helper();\n"
        "            utils.helper();\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/demo/app/Main.as"],
        bridge_paths=["src"],
        include_patterns=["**/*.as", "*.as", "asconfig.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "src/demo/app/Main.as",
        "src/demo/base/BaseActor.as",
        "src/demo/utils/Utils.as",
    ]


def test_connected_dependency_map_keeps_scratch_projects_indexable(tmp_path: Path) -> None:
    repo_path = tmp_path / "scratch-connected-map-repo"
    _write_scratch_project(
        repo_path / "games" / "Maze.sb3",
        _scratch_project_payload(),
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["games/Maze.sb3"],
        bridge_paths=["games"],
        include_patterns=["**/*.sb3", "*.sb3"],
        max_files=128,
        max_file_size_bytes=150_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 1
    assert connected_map["connected_files"] == ["games/Maze.sb3"]


def test_connected_dependency_map_follows_labview_project_and_library_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "labview-connected-map-repo"
    (repo_path / "Source" / "Libraries").mkdir(parents=True)
    (repo_path / "Source" / "Controls").mkdir(parents=True)
    (repo_path / "App.lvproj").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Project Type=\"Project\">\n"
        '  <Item Name="Main" Type="VI" URL="Source/Main.vi" />\n'
        '  <Item Name="Helpers" Type="Library" URL="Source/Libraries/Helpers.lvlib" />\n'
        '  <Item Name="Config" Type="Control" URL="Source/Controls/Config.ctl" />\n'
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "Source" / "Libraries" / "Helpers.lvlib").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Library Name=\"Helpers\">\n"
        '  <Item Name="Helper" Type="VI" URL="Helper.vi" />\n'
        "</Library>\n",
        encoding="utf-8",
    )
    (repo_path / "Source" / "Main.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")
    (repo_path / "Source" / "Libraries" / "Helper.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")
    (repo_path / "Source" / "Controls" / "Config.ctl").write_bytes(b"RSRC\r\n\x00\x03LVCCLBVW")

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["App.lvproj"],
        bridge_paths=["Source"],
        include_patterns=[
            "**/*.lvproj",
            "*.lvproj",
            "**/*.lvlib",
            "*.lvlib",
            "**/*.lvclass",
            "*.lvclass",
            "**/*.vi",
            "*.vi",
            "**/*.vim",
            "*.vim",
            "**/*.vit",
            "*.vit",
            "**/*.ctl",
            "*.ctl",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 5
    assert connected_map["resolved_dependency_edges"] >= 4
    assert connected_map["connected_files"] == [
        "App.lvproj",
        "Source/Controls/Config.ctl",
        "Source/Libraries/Helper.vi",
        "Source/Libraries/Helpers.lvlib",
        "Source/Main.vi",
    ]


def test_connected_dependency_map_follows_tcl_pkgindex_and_source_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tcl-connected-map-repo"
    (repo_path / "modules" / "demo").mkdir(parents=True)
    (repo_path / "modules" / "demo" / "pkgIndex.tcl").write_text(
        "package ifneeded demo 1.0 [list source [file join $dir demo.tcl]]\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "demo" / "helpers.tcl").write_text(
        "package provide helpers 1.0\n"
        "proc ::helpers::run {} {\n"
        "    return ok\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "demo" / "demo.tcl").write_text(
        "package provide demo 1.0\n"
        "source helpers.tcl\n"
        "proc ::demo::main {} {\n"
        "    ::helpers::run\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["modules/demo/pkgIndex.tcl"],
        bridge_paths=["modules/demo"],
        include_patterns=["**/*.tcl", "*.tcl", "**/*.tm", "*.tm"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "modules/demo/demo.tcl",
        "modules/demo/helpers.tcl",
        "modules/demo/pkgIndex.tcl",
    ]


def test_connected_dependency_map_follows_systemverilog_include_and_instantiation_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "systemverilog-connected-map-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "defs.svh").write_text(
        "package util_pkg;\n"
        "  function int helper();\n"
        "    return 1;\n"
        "  endfunction\n"
        "endpackage\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.sv").write_text(
        "module child;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.sv").write_text(
        '`include "defs.svh"\n'
        "import util_pkg::*;\n"
        "module top;\n"
        "  child u_child();\n"
        "  int value = util_pkg::helper();\n"
        "endmodule\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["rtl/top.sv"],
        bridge_paths=["rtl"],
        include_patterns=["**/*.sv", "*.sv", "**/*.svh", "*.svh", "**/*.v", "*.v", "**/*.vh", "*.vh"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "rtl/child.sv",
        "rtl/defs.svh",
        "rtl/top.sv",
    ]


def test_connected_dependency_map_follows_verilog_include_and_instantiation_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "verilog-connected-map-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "defs.vh").write_text(
        "function helper;\n"
        "endfunction\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.v").write_text(
        "module child;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.v").write_text(
        '`include "defs.vh"\n'
        "module top;\n"
        "  child u_child();\n"
        "  assign ready = helper;\n"
        "endmodule\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["rtl/top.v"],
        bridge_paths=["rtl"],
        include_patterns=["**/*.v", "*.v", "**/*.vh", "*.vh"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "rtl/child.v",
        "rtl/defs.vh",
        "rtl/top.v",
    ]


def test_connected_dependency_map_follows_gdscript_preload_and_extends_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gdscript-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "base_actor.gd").write_text(
        "class_name BaseActor\n"
        "extends Node\n"
        "func base_ready() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "utils.gd").write_text(
        "class_name Utils\n"
        "extends RefCounted\n"
        "func helper() -> int:\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "player.gd").write_text(
        "class_name Player\n"
        'extends "res://src/base_actor.gd"\n'
        'const UtilsRef = preload("res://src/utils.gd")\n'
        "func _ready() -> void:\n"
        "    UtilsRef.helper()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/player.gd"],
        bridge_paths=["src"],
        include_patterns=["**/*.gd", "*.gd", "project.godot"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "src/base_actor.gd",
        "src/player.gd",
        "src/utils.gd",
    ]


def test_connected_dependency_map_follows_gml_script_and_object_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gml-connected-map-repo"
    (repo_path / "scripts" / "tree_runtime").mkdir(parents=True)
    (repo_path / "scripts" / "tree_api").mkdir(parents=True)
    (repo_path / "objects" / "Entity").mkdir(parents=True)
    (repo_path / "scripts" / "tree_runtime" / "tree_runtime.gml").write_text(
        "function __BHTree() constructor {\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "tree_api" / "tree_api.gml").write_text(
        "function bh_tree() {\n"
        "    return new __BHTree();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "objects" / "Entity" / "Create_0.gml").write_text(
        "function setup() {\n"
        "    return bh_tree();\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["objects/Entity/Create_0.gml"],
        bridge_paths=["scripts", "objects"],
        include_patterns=["**/*.gml", "*.gml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "objects/Entity/Create_0.gml",
        "scripts/tree_api/tree_api.gml",
        "scripts/tree_runtime/tree_runtime.gml",
    ]


def test_connected_dependency_map_follows_vhdl_use_and_instantiation_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vhdl-connected-map-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "defs.vhd").write_text(
        "package util_pkg is\n"
        "  function helper return integer;\n"
        "end package;\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.vhd").write_text(
        "entity child is\n"
        "end entity;\n"
        "architecture rtl of child is\n"
        "begin\n"
        "end architecture;\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.vhd").write_text(
        "library work;\n"
        "use work.util_pkg.all;\n"
        "entity top is\n"
        "end entity;\n"
        "architecture rtl of top is\n"
        "begin\n"
        "  u_child: entity work.child port map();\n"
        "end architecture;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["rtl/top.vhd"],
        bridge_paths=["rtl"],
        include_patterns=["**/*.vhd", "*.vhd", "**/*.vhdl", "*.vhdl"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "rtl/child.vhd",
        "rtl/defs.vhd",
        "rtl/top.vhd",
    ]


def test_connected_dependency_map_follows_prolog_use_module_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "prolog-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "family.pl").write_text(
        ":- module(family, [ancestor/2, parent/2]).\n"
        "parent(alice, bob).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "related.pl").write_text(
        ":- module(related, [related/2]).\n"
        ":- use_module('family.pl', [ancestor/2]).\n"
        "related(X, Y) :- ancestor(X, Y).\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/related.pl"],
        bridge_paths=["src"],
        include_patterns=[
            "src/**/*.pl",
            "src/*.pl",
            "src/**/*.prolog",
            "src/*.prolog",
            "*.pl",
            "*.prolog",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/family.pl",
        "src/related.pl",
    ]


def test_connected_dependency_map_follows_ml_open_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "ml-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "project.mlb").write_text(
        "src/Util.sml\n"
        "src/Main.sml\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Util.sml").write_text(
        "structure Util = struct\n"
        "fun helper () = 1\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.sml").write_text(
        "structure Main = struct\n"
        "open Util\n"
        "val run = helper ()\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.sml"],
        bridge_paths=["src", "project.mlb"],
        include_patterns=[
            "src/**/*.sml",
            "src/*.sml",
            "src/**/*.sig",
            "src/*.sig",
            "src/**/*.fun",
            "src/*.fun",
            "*.mlb",
            "*.cm",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/Main.sml",
        "src/Util.sml",
    ]


def test_connected_dependency_map_follows_classic_visual_basic_project_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vb6-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project1.vbp").write_text(
        'Type=Exe\n'
        'Class=cHelper; src/cHelper.cls\n'
        'Module=modMain; src/modMain.bas\n'
        'Form=src/Form1.frm\n'
        'Startup="Form1"\n'
        'Name="Project1"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Form1.frm").write_text(
        "VERSION 5.00\n"
        "Begin VB.Form Form1\n"
        "End\n"
        'Attribute VB_Name = "Form1"\n'
        "Option Explicit\n"
        "Private mHelper As cHelper\n"
        "Private Sub Form_Load()\n"
        "    Set mHelper = New cHelper\n"
        "    Debug.Print mHelper.Helper()\n"
        "    modMain.RunApp\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "cHelper.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "cHelper"\n'
        "Option Explicit\n"
        "Public Function Helper() As String\n"
        '    Helper = "ok"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "modMain.bas").write_text(
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Form1.frm"],
        bridge_paths=["src", "Project1.vbp"],
        include_patterns=[
            "src/**/*.bas",
            "src/*.bas",
            "src/**/*.cls",
            "src/*.cls",
            "src/**/*.frm",
            "src/*.frm",
            "*.vbp",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 3
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "src/Form1.frm" in connected_map["connected_files"]
    assert "src/cHelper.cls" in connected_map["connected_files"]
    assert "src/modMain.bas" in connected_map["connected_files"]


def test_connected_dependency_map_follows_vba_module_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "vba-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "JsonData.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "JsonData"\n'
        "Option Explicit\n"
        "Public Function ToJson() As String\n"
        '    ToJson = "{}"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "JsonConverter.bas").write_text(
        'Attribute VB_Name = "JsonConverter"\n'
        "Option Explicit\n"
        "Public Sub Main()\n"
        "    Dim data As JsonData\n"
        "    Set data = New JsonData\n"
        "    Debug.Print data.ToJson()\n"
        "End Sub\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/JsonConverter.bas"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.bas", "src/*.bas", "src/**/*.cls", "src/*.cls"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/JsonConverter.bas",
        "src/JsonData.cls",
    ]


def test_connected_dependency_map_skips_missing_classic_visual_basic_project_targets(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vb6-missing-target-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project1.vbp").write_text(
        'Type=Exe\n'
        'Class=cMissing; [CLASS]/cMissing.cls\n'
        'Module=modMain; src/modMain.bas\n'
        'Form=src/Form1.frm\n'
        'Startup="Form1"\n'
        'Name="Project1"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Form1.frm").write_text(
        "VERSION 5.00\n"
        "Begin VB.Form Form1\n"
        "End\n"
        'Attribute VB_Name = "Form1"\n'
        "Option Explicit\n"
        "Private Sub Form_Load()\n"
        "    modMain.RunApp\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "modMain.bas").write_text(
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Form1.frm"],
        bridge_paths=["src", "Project1.vbp"],
        include_patterns=[
            "src/**/*.bas",
            "src/*.bas",
            "src/**/*.cls",
            "src/*.cls",
            "src/**/*.frm",
            "src/*.frm",
            "*.vbp",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert "src/Form1.frm" in connected_map["connected_files"]
    assert "src/modMain.bas" in connected_map["connected_files"]
    assert "[CLASS]/cMissing.cls" not in connected_map["connected_files"]
    assert connected_map["unresolved_dependency_count"] >= 1


def test_operational_seed_plan_without_diagnostics_uses_lisp_asd_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lisp-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "acme.asd").write_text(
        '(asdf:defsystem "acme"\n'
        '  :pathname "src"\n'
        '  :components ((:file "package") (:file "helper") (:file "app")))\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "package.lisp").write_text(
        "(defpackage #:acme.helper (:use #:cl) (:export #:helper))\n"
        "(defpackage #:acme.app (:use #:cl) (:import-from #:acme.helper #:helper))\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper.lisp").write_text(
        "(in-package #:acme.helper)\n"
        "(defun helper () 1)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "app.lisp").write_text(
        "(in-package #:acme.app)\n"
        "(defun run () (helper))\n",
        encoding="utf-8",
    )

    seed_plan = probe_module._derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["lisp"]
    assert seed_plan["operational_ecosystems"] == ["lisp"]
    assert "acme.asd" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/package.lisp" in seed_plan["entrypoint_files"]
    assert "src/app.lisp" in seed_plan["entrypoint_files"]


def test_connected_dependency_map_follows_lisp_asd_and_package_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lisp-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "acme.asd").write_text(
        '(asdf:defsystem "acme"\n'
        '  :pathname "src"\n'
        '  :components ((:file "package") (:file "helper") (:file "app")))\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "package.lisp").write_text(
        "(defpackage #:acme.helper (:use #:cl) (:export #:helper))\n"
        "(defpackage #:acme.app (:use #:cl) (:import-from #:acme.helper #:helper))\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper.lisp").write_text(
        "(in-package #:acme.helper)\n"
        "(defun helper () 1)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "app.lisp").write_text(
        "(in-package #:acme.app)\n"
        "(defun run () (helper))\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/app.lisp"],
        bridge_paths=["src", "acme.asd"],
        include_patterns=["*.asd", "src/**/*.lisp", "src/*.lisp"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "src/app.lisp" in connected_map["connected_files"]
    assert "src/helper.lisp" in connected_map["connected_files"]


def test_connected_dependency_map_follows_emacslisp_require_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "emacslisp-connected-map-repo"
    (repo_path / "lisp").mkdir(parents=True)
    (repo_path / "Cask").write_text(
        "(source gnu)\n"
        '(package-file "main.el")\n',
        encoding="utf-8",
    )
    (repo_path / "main.el").write_text(
        "(require 'helper)\n"
        "(provide 'main)\n"
        "(defun run () (helper-fn))\n",
        encoding="utf-8",
    )
    (repo_path / "lisp" / "helper.el").write_text(
        "(provide 'helper)\n"
        "(defun helper-fn () 1)\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.el"],
        bridge_paths=["lisp", "Cask"],
        include_patterns=["*.el", "lisp/**/*.el", "lisp/*.el", "Cask"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "main.el" in connected_map["connected_files"]
    assert "lisp/helper.el" in connected_map["connected_files"]


def test_connected_dependency_map_follows_vimscript_source_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vimscript-connected-map-repo"
    (repo_path / "plugin").mkdir(parents=True)
    (repo_path / "autoload").mkdir(parents=True)
    (repo_path / "autoload" / "fugitive.vim").write_text(
        "function! fugitive#run()\n"
        "  return '{}'\n"
        "endfunction\n",
        encoding="utf-8",
    )
    (repo_path / "plugin" / "fugitive.vim").write_text(
        "source ../autoload/fugitive.vim\n"
        "call fugitive#run()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["plugin/fugitive.vim"],
        bridge_paths=["plugin", "autoload"],
        include_patterns=[
            "plugin/**/*.vim",
            "plugin/*.vim",
            "autoload/**/*.vim",
            "autoload/*.vim",
            "*.vim",
            ".vimrc",
            "vimrc",
            "gvimrc",
            "_vimrc",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "plugin/fugitive.vim" in connected_map["connected_files"]
    assert "autoload/fugitive.vim" in connected_map["connected_files"]


def test_connected_dependency_map_follows_racket_require_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "racket-connected-map-repo"
    (repo_path / "private").mkdir(parents=True)
    (repo_path / "info.rkt").write_text(
        "#lang info\n"
        '(define collection "acme")\n',
        encoding="utf-8",
    )
    (repo_path / "main.rkt").write_text(
        "#lang racket\n"
        '(require "private/helper.rkt")\n'
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "private" / "helper.rkt").write_text(
        "#lang racket\n"
        "(define (helper) 1)\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.rkt"],
        bridge_paths=["private", "info.rkt"],
        include_patterns=["*.rkt", "private/**/*.rkt", "private/*.rkt"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "main.rkt" in connected_map["connected_files"]
    assert "private/helper.rkt" in connected_map["connected_files"]


def test_connected_dependency_map_follows_scheme_import_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scheme-connected-map-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "package.scm").write_text(
        "(define-library (acme app)\n"
        "  (export run)\n"
        "  (import (acme helper))\n"
        "  (begin\n"
        "    (define (run) (helper))))\n",
        encoding="utf-8",
    )
    (repo_path / "main.scm").write_text(
        "#!r6rs\n"
        "(import (acme helper))\n"
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "helper.sld").write_text(
        "(define-library (acme helper)\n"
        "  (export helper)\n"
        "  (begin\n"
        "    (define (helper) 1)))\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.scm"],
        bridge_paths=["lib", "package.scm"],
        include_patterns=["*.scm", "lib/**/*.sld", "lib/*.sld", "*.sld"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "main.scm" in connected_map["connected_files"]
    assert "lib/acme/helper.sld" in connected_map["connected_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_foxpro_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "foxpro-profile-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "programs" / "util.prg").write_text(
        "FUNCTION helper()\n"
        "    RETURN 1\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    (repo_path / "programs" / "main.prg").write_text(
        "SET PROCEDURE TO programs/util ADDITIVE\n"
        "FUNCTION run()\n"
        "    RETURN helper()\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main_test.prg").write_text(
        "FUNCTION run_test()\n"
        "    RETURN .T.\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )

    seed_plan = probe_module._derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["foxpro"]
    assert seed_plan["operational_ecosystems"] == ["foxpro"]
    assert "programs/main.prg" in seed_plan["entrypoint_files"]
    assert "tests/main_test.prg" not in seed_plan["entrypoint_files"]
    assert "programs/util.prg" in seed_plan["candidate_file_paths"]
    assert "programs" in seed_plan["support_roots"]


def test_connected_dependency_map_follows_foxpro_set_procedure_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "foxpro-connected-map-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "include" / "common.h").write_text(
        '#define APP_NAME "Acme"\n',
        encoding="utf-8",
    )
    (repo_path / "programs" / "util.prg").write_text(
        "FUNCTION helper()\n"
        "    RETURN 1\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    (repo_path / "programs" / "main.prg").write_text(
        '#INCLUDE "../include/common.h"\n'
        "SET PROCEDURE TO programs/util ADDITIVE\n"
        "FUNCTION run()\n"
        "    RETURN helper()\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["programs/main.prg"],
        bridge_paths=["programs", "include"],
        include_patterns=[
            "programs/**/*.prg",
            "programs/*.prg",
            "include/**/*.h",
            "include/*.h",
            "*.prg",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "include/common.h",
        "programs/main.prg",
        "programs/util.prg",
    ]


def test_operational_seed_plan_without_diagnostics_detects_solidity_foundry_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "solidity-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "foundry.toml").write_text(
        '[profile.default]\nsrc = "src"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Ownable.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "abstract contract Ownable {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Counter.sol").write_text(
        'pragma solidity ^0.8.20;\n'
        'import {Ownable} from "./Ownable.sol";\n'
        "contract Counter is Ownable {}\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "Counter.t.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "contract CounterTest {}\n",
        encoding="utf-8",
    )

    seed_plan = probe_module._derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["solidity"]
    assert seed_plan["operational_ecosystems"] == ["solidity"]
    assert "src/Counter.sol" in seed_plan["entrypoint_files"]
    assert "test/Counter.t.sol" not in seed_plan["entrypoint_files"]
    assert "src" in seed_plan["support_roots"]
    assert "foundry.toml" in seed_plan["config_paths"]


def test_connected_dependency_map_follows_solidity_import_and_inheritance_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "solidity-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Ownable.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "abstract contract Ownable {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Counter.sol").write_text(
        'pragma solidity ^0.8.20;\n'
        'import {Ownable} from "./Ownable.sol";\n'
        "contract Counter is Ownable {}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Counter.sol"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.sol", "src/*.sol", "*.sol"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "src/Counter.sol",
        "src/Ownable.sol",
    ]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_plsql_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "plsql-profile-repo"
    (repo_path / "db").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "db" / "app_util.pks").write_text(
        "create or replace package app_util as\n"
        "  procedure record_order(p_order_id in number);\n"
        "end app_util;\n"
        "/\n",
        encoding="utf-8",
    )
    (repo_path / "db" / "order_api.pks").write_text(
        "create or replace package order_api as\n"
        "  procedure submit_order;\n"
        "end order_api;\n"
        "/\n",
        encoding="utf-8",
    )
    (repo_path / "db" / "order_api.pkb").write_text(
        "create or replace package body order_api as\n"
        "  procedure submit_order is\n"
        "  begin\n"
        "    app_util.record_order(42);\n"
        "  end submit_order;\n"
        "end order_api;\n"
        "/\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "order_api_test.prc").write_text(
        "create or replace procedure order_api_test is\nbegin\n  null;\nend;\n/\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["plsql"]
    assert "db/order_api.pkb" in seed_plan["entrypoint_files"]
    assert "db/order_api.pks" not in seed_plan["entrypoint_files"]
    assert "tests/order_api_test.prc" not in seed_plan["entrypoint_files"]
    assert "db/order_api.pks" in seed_plan["candidate_file_paths"]


def test_connected_dependency_map_follows_plsql_package_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "plsql-connected-map-repo"
    (repo_path / "db").mkdir(parents=True)
    (repo_path / "db" / "app_util.pks").write_text(
        "create or replace package app_util as\n"
        "  procedure record_order(p_order_id in number);\n"
        "end app_util;\n"
        "/\n",
        encoding="utf-8",
    )
    (repo_path / "db" / "order_api.pks").write_text(
        "create or replace package order_api as\n"
        "  procedure submit_order;\n"
        "end order_api;\n"
        "/\n",
        encoding="utf-8",
    )
    (repo_path / "db" / "order_api.pkb").write_text(
        "create or replace package body order_api as\n"
        "  procedure submit_order is\n"
        "  begin\n"
        "    app_util.record_order(42);\n"
        "  end submit_order;\n"
        "end order_api;\n"
        "/\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["db/order_api.pkb"],
        bridge_paths=["db"],
        include_patterns=[
            "db/**/*.pkb",
            "db/*.pkb",
            "db/**/*.pks",
            "db/*.pks",
            "db/**/*.pls",
            "db/*.pls",
            "db/**/*.prc",
            "db/*.prc",
            "db/**/*.fnc",
            "db/*.fnc",
            "db/**/*.trg",
            "db/*.trg",
            "*.pkb",
            "*.pks",
            "*.pls",
            "*.prc",
            "*.fnc",
            "*.trg",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "db/app_util.pks",
        "db/order_api.pkb",
        "db/order_api.pks",
    ]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_sas_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sas-profile-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "macros").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "macros" / "render_table.sas").write_text(
        "%macro render_table();\n"
        "  %put rendering table;\n"
        "%mend render_table;\n",
        encoding="utf-8",
    )
    (repo_path / "programs" / "report.sas").write_text(
        "%include \"../macros/render_table.sas\";\n"
        "%macro build_report();\n"
        "  %render_table();\n"
        "%mend build_report;\n"
        "%build_report();\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "report_test.sas").write_text(
        "%macro report_test();\n"
        "  %put test;\n"
        "%mend report_test;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["sas"]
    assert "programs/report.sas" in seed_plan["entrypoint_files"]
    assert "tests/report_test.sas" not in seed_plan["entrypoint_files"]
    assert "macros/render_table.sas" in seed_plan["candidate_file_paths"]


def test_connected_dependency_map_follows_sas_include_and_macro_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "sas-connected-map-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "macros").mkdir(parents=True)
    (repo_path / "macros" / "render_table.sas").write_text(
        "%macro render_table();\n"
        "  %put rendering table;\n"
        "%mend render_table;\n",
        encoding="utf-8",
    )
    (repo_path / "programs" / "report.sas").write_text(
        "%include \"../macros/render_table.sas\";\n"
        "%macro build_report();\n"
        "  %render_table();\n"
        "%mend build_report;\n"
        "%build_report();\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["programs/report.sas"],
        bridge_paths=["programs", "macros"],
        include_patterns=[
            "programs/**/*.sas",
            "programs/*.sas",
            "macros/**/*.sas",
            "macros/*.sas",
            "*.sas",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "macros/render_table.sas",
        "programs/report.sas",
    ]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_matlab_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "matlab-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "helper.m").write_text(
        "function value = helper()\n"
        "value = 1;\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.m").write_text(
        "function value = main()\n"
        "value = helper();\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main_test.m").write_text(
        "function value = main_test()\n"
        "value = 0;\n"
        "end\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["matlab"]
    assert "src/main.m" in seed_plan["entrypoint_files"]
    assert "src/helper.m" in seed_plan["candidate_file_paths"]
    assert "tests/main_test.m" not in seed_plan["entrypoint_files"]


def test_connected_dependency_map_follows_matlab_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "matlab-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.m").write_text(
        "function value = helper()\n"
        "value = 1;\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.m").write_text(
        "function value = main()\n"
        "value = helper();\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.m"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.m", "src/*.m", "*.m"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/helper.m",
        "src/main.m",
    ]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_objective_c_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "objective-c-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "ACMHelper.h").write_text(
        "#import <Foundation/Foundation.h>\n"
        "@interface ACMHelper : NSObject\n"
        "+ (void)work;\n"
        "@end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "ACMClient.m").write_text(
        "#import \"ACMHelper.h\"\n"
        "@interface ACMClient : NSObject\n"
        "- (void)run;\n"
        "@end\n"
        "@implementation ACMClient\n"
        "- (void)run {\n"
        "    [ACMHelper work];\n"
        "}\n"
        "@end\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "ACMClientTests.m").write_text(
        "#import <Foundation/Foundation.h>\n"
        "@interface ACMClientTests : NSObject\n"
        "@end\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["objectivec"]
    assert "src/ACMClient.m" in seed_plan["entrypoint_files"]
    assert "src/ACMHelper.h" in seed_plan["candidate_file_paths"]
    assert "tests/ACMClientTests.m" not in seed_plan["entrypoint_files"]


def test_connected_dependency_map_follows_objective_c_import_and_message_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "objective-c-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "ACMHelper.h").write_text(
        "#import <Foundation/Foundation.h>\n"
        "@interface ACMHelper : NSObject\n"
        "+ (void)work;\n"
        "@end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "ACMClient.m").write_text(
        "#import \"ACMHelper.h\"\n"
        "@interface ACMClient : NSObject\n"
        "- (void)run;\n"
        "@end\n"
        "@implementation ACMClient\n"
        "- (void)run {\n"
        "    [ACMHelper work];\n"
        "}\n"
        "@end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/ACMClient.m"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.h", "src/*.h", "src/**/*.m", "src/*.m"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {"src/ACMClient.m", "src/ACMHelper.h"}


def test_operational_seed_plan_without_diagnostics_detects_manifestless_assembly_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "assembly-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "include" / "io.inc").write_text(
        "extern print_string\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "io.asm").write_text(
        "global print_string\n"
        "print_string:\n"
        "    ret\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.asm").write_text(
        "%include \"../include/io.inc\"\n"
        "global main\n"
        "main:\n"
        "    call print_string\n"
        "    ret\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main_test.asm").write_text(
        "global test_main\n"
        "test_main:\n"
        "    ret\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["assembly"]
    assert "src/main.asm" in seed_plan["entrypoint_files"]
    assert "include/io.inc" in seed_plan["candidate_file_paths"]
    assert "tests/main_test.asm" not in seed_plan["entrypoint_files"]


def test_connected_dependency_map_follows_assembly_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "assembly-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "include" / "io.inc").write_text(
        "extern print_string\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "io.asm").write_text(
        "global print_string\n"
        "print_string:\n"
        "    ret\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.asm").write_text(
        "%include \"../include/io.inc\"\n"
        "global main\n"
        "main:\n"
        "    call print_string\n"
        "    ret\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.asm"],
        bridge_paths=["src", "include"],
        include_patterns=[
            "src/**/*.asm",
            "src/*.asm",
            "include/**/*.inc",
            "include/*.inc",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert set(connected_map["connected_files"]) == {
        "include/io.inc",
        "src/io.asm",
        "src/main.asm",
    }


def test_operational_seed_plan_without_diagnostics_detects_manifestless_abap_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "abap-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "zcl_math.clas.abap").write_text(
        "CLASS zcl_math DEFINITION PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    CLASS-METHODS add_one IMPORTING iv_value TYPE i RETURNING VALUE(rv_value) TYPE i.\n"
        "ENDCLASS.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "zcl_report.clas.abap").write_text(
        "CLASS zcl_report DEFINITION PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    METHODS run.\n"
        "ENDCLASS.\n"
        "\n"
        "CLASS zcl_report IMPLEMENTATION.\n"
        "  INCLUDE zcl_report.clas.locals_imp.\n"
        "ENDCLASS.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "zcl_report.clas.locals_imp.abap").write_text(
        "METHOD run.\n"
        "  DATA(result) = zcl_math=>add_one( 1 ).\n"
        "ENDMETHOD.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "zif_report.intf.abap").write_text(
        "INTERFACE zif_report PUBLIC.\n"
        "  METHODS run.\n"
        "ENDINTERFACE.\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "zcl_report.clas.testclasses.abap").write_text(
        "CLASS ltc_report DEFINITION FOR TESTING.\n"
        "  PRIVATE SECTION.\n"
        "    METHODS test_run.\n"
        "ENDCLASS.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["abap"]
    assert "src/zcl_report.clas.abap" in seed_plan["entrypoint_files"]
    assert "src/zcl_report.clas.locals_imp.abap" not in seed_plan["entrypoint_files"]
    assert "src/zif_report.intf.abap" not in seed_plan["entrypoint_files"]
    assert "tests/zcl_report.clas.testclasses.abap" not in seed_plan["entrypoint_files"]
    assert "src/zcl_math.clas.abap" in seed_plan["candidate_file_paths"]


def test_connected_dependency_map_follows_abap_include_and_static_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "abap-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "zcl_math.clas.abap").write_text(
        "CLASS zcl_math DEFINITION PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    CLASS-METHODS add_one IMPORTING iv_value TYPE i RETURNING VALUE(rv_value) TYPE i.\n"
        "ENDCLASS.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "zcl_report.clas.abap").write_text(
        "CLASS zcl_report DEFINITION PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    METHODS run.\n"
        "ENDCLASS.\n"
        "\n"
        "CLASS zcl_report IMPLEMENTATION.\n"
        "  INCLUDE zcl_report.clas.locals_imp.\n"
        "ENDCLASS.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "zcl_report.clas.locals_imp.abap").write_text(
        "METHOD run.\n"
        "  DATA(result) = zcl_math=>add_one( 1 ).\n"
        "ENDMETHOD.\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/zcl_report.clas.abap"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.abap", "src/*.abap", "*.abap"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "src/zcl_math.clas.abap",
        "src/zcl_report.clas.abap",
        "src/zcl_report.clas.locals_imp.abap",
    ]


def test_operational_seed_plan_without_diagnostics_uses_dub_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "d-dub-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "dub.json").write_text(
        '{\n  "name": "acme"\n}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "main.d").write_text(
        "module acme.main;\nint main() { return 0; }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "utils.d").write_text(
        "module acme.utils;\nint helper() { return 1; }\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main_test.d").write_text(
        "module tests.main_test;\nint main() { return 0; }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "d" in seed_plan["detected_ecosystems"]
    assert "dub.json" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme/main.d" in seed_plan["entrypoint_files"]
    assert "src/acme/utils.d" in seed_plan["candidate_file_paths"]
    assert "tests/main_test.d" not in seed_plan["entrypoint_files"]


def test_connected_dependency_map_follows_d_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "d-connected-map-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "dub.json").write_text(
        '{\n  "name": "acme"\n}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "utils.d").write_text(
        "module acme.utils;\nint helper() { return 1; }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "main.d").write_text(
        "module acme.main;\nimport acme.utils : helper;\nint main() { return helper(); }\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme/main.d"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.d", "src/*.d", "dub.json", "dub.sdl"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme/main.d",
        "src/acme/utils.d",
    ]


def test_connected_dependency_map_follows_vala_import_and_method_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vala-connected-map-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "util").mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('demo', 'vala')\n"
        "executable('demo', ['src/demo/app/Main.vala', 'src/demo/util/Helper.vala'])\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "util" / "Helper.vala").write_text(
        "namespace Demo.Util {\n"
        "    public class Helper : Object {\n"
        "        public string render_json () {\n"
        '            return "{}";\n'
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "app" / "Main.vala").write_text(
        "using Demo.Util;\n"
        "\n"
        "namespace Demo.App {\n"
        "    public class App : Object {\n"
        "        public void run () {\n"
        "            Helper helper = new Helper ();\n"
        "            helper.render_json ();\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/demo/app/Main.vala"],
        bridge_paths=["src"],
        include_patterns=[
            "src/**/*.vala",
            "src/*.vala",
            "*.vala",
            "**/*.vapi",
            "*.vapi",
            "meson.build",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/demo/app/Main.vala",
        "src/demo/util/Helper.vala",
    }


def test_connected_dependency_map_follows_mql5_include_and_method_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "mql5-connected-map-repo"
    (repo_path / "Experts").mkdir(parents=True)
    (repo_path / "Include").mkdir(parents=True)
    (repo_path / "demo.mqproj").write_text(
        '<Project><Files><File>Experts/Main.mq5</File><File>Include/Helper.mqh</File></Files></Project>\n',
        encoding="utf-8",
    )
    (repo_path / "Include" / "Helper.mqh").write_text(
        "class Helper\n"
        "{\n"
        "public:\n"
        "   string RenderJson()\n"
        "     {\n"
        '      return "{}";\n'
        "     }\n"
        "};\n",
        encoding="utf-8",
    )
    (repo_path / "Experts" / "Main.mq5").write_text(
        '#include "../Include/Helper.mqh"\n'
        "void OnStart()\n"
        "{\n"
        "   Helper helper;\n"
        "   helper.RenderJson();\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["Experts/Main.mq5"],
        bridge_paths=["Experts", "Include"],
        include_patterns=[
            "Experts/**/*.mq5",
            "Experts/*.mq5",
            "Include/**/*.mqh",
            "Include/*.mqh",
            "*.mqproj",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "Experts/Main.mq5",
        "Include/Helper.mqh",
    }


def test_connected_dependency_map_follows_gams_include_and_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "gams-connected-map-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "include" / "common.inc").write_text(
        "parameter demand(i);\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "main.gms").write_text(
        "$include ../include/common.inc\n"
        "set i /a,b/;\n"
        "parameter cost(i);\n"
        "equation balance;\n"
        "balance.. demand('a') =e= cost('a');\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["models/main.gms"],
        bridge_paths=["models", "include"],
        include_patterns=[
            "models/**/*.gms",
            "models/*.gms",
            "include/**/*.inc",
            "include/*.inc",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "models/main.gms",
        "include/common.inc",
    }


def test_connected_dependency_map_follows_openscad_include_and_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "openscad-connected-map-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "helper.scad").write_text(
        "module gusset(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.scad").write_text(
        "include <lib/helper.scad>;\n"
        "module build() {\n"
        "  gusset(10);\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.scad"],
        bridge_paths=["lib"],
        include_patterns=["**/*.scad", "*.scad"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "main.scad",
        "lib/helper.scad",
    }


def test_connected_dependency_map_follows_factor_using_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "factor-connected-map-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "math" / "math.factor").write_text(
        "IN: math\n\n: square ( n -- n ) dup * ;\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "main.factor").write_text(
        "USING: math ;\nIN: app.main\n\n: run ( n -- n ) square ;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["app/main.factor"],
        bridge_paths=["math"],
        include_patterns=["**/*.factor", "*.factor"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "app/main.factor",
        "math/math.factor",
    }


def test_connected_dependency_map_follows_cue_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cue-connected-map-repo"
    (repo_path / "cue.mod").mkdir(parents=True)
    (repo_path / "pkg" / "schema").mkdir(parents=True)
    (repo_path / "cue.mod" / "module.cue").write_text(
        'module: "example.com/demo"\n',
        encoding="utf-8",
    )
    (repo_path / "pkg" / "schema" / "schema.cue").write_text(
        "package schema\n\n#Answer: 42\n",
        encoding="utf-8",
    )
    (repo_path / "main.cue").write_text(
        'package main\n\nimport schema "example.com/demo/pkg/schema"\n\nvalue: schema.#Answer\n',
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.cue"],
        bridge_paths=["pkg/schema"],
        include_patterns=["**/*.cue", "*.cue"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert {"main.cue", "pkg/schema/schema.cue"} <= set(connected_map["connected_files"])


def test_connected_dependency_map_follows_starlark_load_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "starlark-connected-map-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "lib" / "common.bzl").write_text(
        "def render_json(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "helper.bzl").write_text(
        "def emit_name(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "demo.bzl").write_text(
        'load("//lib:common.bzl", "render_json")\n'
        'load(":helper.bzl", "emit_name")\n'
        "\n"
        "def demo_macro(name):\n"
        "    return emit_name(render_json(name))\n",
        encoding="utf-8",
    )
    (repo_path / "BUILD.bazel").write_text(
        'load("rules:demo.bzl", "demo_macro")\n'
        '\n'
        'demo_macro(name = "app")\n',
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["BUILD.bazel"],
        bridge_paths=["rules", "lib"],
        include_patterns=[
            "**/*.bzl",
            "*.bzl",
            "**/*.star",
            "*.star",
            "**/BUILD.bazel",
            "BUILD.bazel",
            "**/BUILD",
            "BUILD",
            "MODULE.bazel",
            "WORKSPACE",
            "WORKSPACE.bazel",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 4
    assert connected_map["resolved_dependency_edges"] >= 3
    assert set(connected_map["connected_files"]) == {
        "BUILD.bazel",
        "rules/demo.bzl",
        "rules/helper.bzl",
        "lib/common.bzl",
    }


def test_connected_dependency_map_follows_nix_import_and_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "nix-connected-map-repo"
    (repo_path / "nix" / "lib").mkdir(parents=True)
    (repo_path / "nix" / "lib" / "formatter.nix").write_text(
        "{ pkgs }:\n"
        "{\n"
        "  mkFormatter = package: package;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "flake.nix").write_text(
        "{\n"
        "  inputs.nixpkgs.url = \"github:NixOS/nixpkgs\";\n"
        "  outputs = { self, nixpkgs }:\n"
        "    let formatter = import ./nix/lib/formatter.nix { pkgs = nixpkgs.legacyPackages.x86_64-linux; }; in {\n"
        "      formatter = formatter.mkFormatter nixpkgs.legacyPackages.x86_64-linux.alejandra;\n"
        "    };\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["flake.nix"],
        bridge_paths=["nix"],
        include_patterns=["**/*.nix", "*.nix"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "flake.nix",
        "nix/lib/formatter.nix",
    }


def test_connected_dependency_map_follows_purescript_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "purescript-connected-map-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "src" / "Main.purs").write_text(
        "module Main where\n\nimport Data.Helper (helperValue)\n\nmain = helperValue\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Data" / "Helper.purs").write_text(
        "module Data.Helper where\n\nhelperValue :: Int\nhelperValue = 1\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.purs"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.purs", "src/*.purs", "*.purs", "spago.yaml", "bower.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/Main.purs",
        "src/Data/Helper.purs",
    }


def test_connected_dependency_map_follows_gleam_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gleam-connected-map-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "gleam.toml").write_text(
        'name = "demo"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.gleam").write_text(
        "import demo/helper.{render_json}\n\npub fn main() {\n  render_json()\n}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "helper.gleam").write_text(
        "pub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.gleam"],
        bridge_paths=["src", "gleam.toml"],
        include_patterns=["src/**/*.gleam", "src/*.gleam", "*.gleam", "gleam.toml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/demo/helper.gleam",
        "src/main.gleam",
    }


def test_connected_dependency_map_follows_janet_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "janet-connected-map-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "project.janet").write_text(
        '(declare-project :name "demo" :source @["src"] :main "src/main.janet")\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.janet").write_text(
        '(import ./demo/helper :as helper)\n\n(defn main []\n  (helper/render-json))\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "helper.janet").write_text(
        "(defn render-json [] @{})\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.janet"],
        bridge_paths=["src", "project.janet"],
        include_patterns=["src/**/*.janet", "src/*.janet", "*.janet", "project.janet"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/demo/helper.janet",
        "src/main.janet",
    }


def test_connected_dependency_map_follows_rego_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rego-connected-map-repo"
    (repo_path / "policy" / "lib").mkdir(parents=True)
    (repo_path / "policy" / "main.rego").write_text(
        "package policy.main\n\n"
        "import data.policy.lib.helpers as helper\n\n"
        "allow if {\n"
        "    helper.render_json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "policy" / "lib" / "helpers.rego").write_text(
        "package policy.lib.helpers\n\n"
        "render_json if {\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["policy/main.rego"],
        bridge_paths=["policy", "policy/lib"],
        include_patterns=["**/*.rego", "*.rego"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "policy/lib/helpers.rego",
        "policy/main.rego",
    }


def test_connected_dependency_map_follows_yara_include_and_rule_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "yara-connected-map-repo"
    (repo_path / "rules" / "lib").mkdir(parents=True)
    (repo_path / "rules" / "index.yar").write_text(
        'include "./main.yar"\n'
        'include "./lib/helper.yar"\n',
        encoding="utf-8",
    )
    (repo_path / "rules" / "main.yar").write_text(
        "rule main_rule {\n"
        "  condition:\n"
        "    helper_rule\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "lib" / "helper.yar").write_text(
        "private rule helper_rule {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["rules/index.yar"],
        bridge_paths=["rules", "rules/lib"],
        include_patterns=["**/*.yar", "*.yar", "**/*.yara", "*.yara"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert set(connected_map["connected_files"]) == {
        "rules/index.yar",
        "rules/lib/helper.yar",
        "rules/main.yar",
    }


def test_connected_dependency_map_follows_hcl_module_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hcl-connected-map-repo"
    (repo_path / "modules" / "child").mkdir(parents=True)
    (repo_path / "main.tf").write_text(
        'module "child" {\n'
        '  source = "./modules/child"\n'
        '}\n\n'
        'variable "name" {\n'
        '  default = "demo"\n'
        '}\n\n'
        "locals {\n"
        '  prefix = "vpc-${var.name}"\n'
        "}\n\n"
        'output "full_name" {\n'
        "  value = local.prefix\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "child" / "main.tf").write_text(
        'output "child_id" {\n'
        '  value = "child"\n'
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.tf"],
        bridge_paths=[".", "modules/child"],
        include_patterns=["**/*.tf", "*.tf", "**/*.hcl", "*.hcl"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "main.tf",
        "modules/child/main.tf",
    }


def test_connected_dependency_map_follows_agda_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "agda-connected-map-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "standard-library.agda-lib").write_text(
        "name: demo\ninclude: src\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.agda").write_text(
        "module Main where\n\n"
        "open import Data.Helper using (helper)\n\n"
        "main : Set\n"
        "main = helper\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Data" / "Helper.agda").write_text(
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.agda"],
        bridge_paths=["src", "standard-library.agda-lib"],
        include_patterns=["src/**/*.agda", "src/*.agda", "*.agda", "*.agda-lib"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/Data/Helper.agda",
        "src/Main.agda",
    }


def test_connected_dependency_map_follows_idris_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "idris-connected-map-repo"
    (repo_path / "src" / "Demo").mkdir(parents=True)
    (repo_path / "demo.ipkg").write_text(
        "package demo\n"
        "sourcedir = src\n"
        "modules = Demo.Helper\n"
        "main = Main\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.idr").write_text(
        "module Main\n\n"
        "import Demo.Helper\n\n"
        "main : IO ()\n"
        "main = renderJson\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo" / "Helper.idr").write_text(
        "module Demo.Helper\n\n"
        "renderJson : IO ()\n"
        "renderJson = pure ()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.idr"],
        bridge_paths=["src", "demo.ipkg"],
        include_patterns=["src/**/*.idr", "src/*.idr", "*.idr", "*.lidr", "*.ipkg"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/Demo/Helper.idr",
        "src/Main.idr",
    }


def test_connected_dependency_map_follows_raku_use_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "raku-connected-map-repo"
    (repo_path / "lib" / "Demo").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "META6.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "provides": {"Demo::Helper": "lib/Demo/Helper.rakumod"},
                "bin": ["demo.raku"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "lib" / "Demo" / "Helper.rakumod").write_text(
        "unit module Demo::Helper;\n\nsub render-json() is export { \"{}\" }\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "demo.raku").write_text(
        "use Demo::Helper;\n\nsub main() {\n    Demo::Helper::render-json();\n}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["bin/demo.raku"],
        bridge_paths=["bin", "lib", "META6.json"],
        include_patterns=[
            "bin/**/*.raku",
            "bin/*.raku",
            "lib/**/*.rakumod",
            "lib/*.rakumod",
            "META6.json",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "bin/demo.raku",
        "lib/Demo/Helper.rakumod",
    }


def test_connected_dependency_map_follows_nushell_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nushell-connected-map-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "main.nu").write_text(
        "source modules/helper.nu\n\n"
        "def main [] {\n"
        "  render-json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "helper.nu").write_text(
        "export def render-json [] {\n"
        "  '{}'\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.nu"],
        bridge_paths=["modules"],
        include_patterns=["modules/**/*.nu", "*.nu"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "main.nu",
        "modules/helper.nu",
    }


def test_connected_dependency_map_follows_fish_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fish-connected-map-repo"
    (repo_path / "functions").mkdir(parents=True)
    (repo_path / "main.fish").write_text(
        "source functions/helper.fish\n\n"
        "function main\n"
        "    helper\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "functions" / "helper.fish").write_text(
        "function helper\n"
        "    echo '{}'\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.fish"],
        bridge_paths=["functions"],
        include_patterns=["functions/**/*.fish", "*.fish"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "functions/helper.fish",
        "main.fish",
    }


def test_connected_dependency_map_follows_haxe_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haxe-connected-map-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "Main.hx").write_text(
        "package demo;\n"
        "\n"
        "import demo.Helper;\n"
        "\n"
        "class Main {\n"
        "    static function main() {\n"
        "        Helper.renderJson();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "Helper.hx").write_text(
        "package demo;\n"
        "\n"
        "class Helper {\n"
        "    public static function renderJson():String {\n"
        '        return "{}";\n'
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/demo/Main.hx"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.hx", "src/*.hx", "*.hx", "*.hxml", "project.xml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1


def test_connected_dependency_map_follows_autohotkey_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autohotkey-connected-map-repo"
    (repo_path / "Lib").mkdir(parents=True)
    (repo_path / "Lib" / "Helper.ahk").write_text(
        "RenderJson(value) {\n"
        "    return value\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "Main.ahk").write_text(
        '#Include "../Lib/Helper.ahk"\n'
        "\n"
        "Main() {\n"
        '    return RenderJson("{}")\n'
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/Main.ahk"],
        bridge_paths=["scripts", "Lib"],
        include_patterns=["scripts/**/*.ahk", "scripts/*.ahk", "Lib/**/*.ahk", "Lib/*.ahk"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "scripts/Main.ahk" in connected_map["connected_files"]
    assert "Lib/Helper.ahk" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {"scripts/Main.ahk", "Lib/Helper.ahk"}


def test_connected_dependency_map_follows_autoit_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autoit-connected-map-repo"
    (repo_path / "Includes").mkdir(parents=True)
    (repo_path / "Includes" / "Helper.au3").write_text(
        "Func RenderJson($value)\n"
        "    Return $value\n"
        "EndFunc\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "Main.au3").write_text(
        '#include "../Includes/Helper.au3"\n'
        "\n"
        "Func Main()\n"
        '    Return RenderJson("{}")\n'
        "EndFunc\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/Main.au3"],
        bridge_paths=["scripts", "Includes"],
        include_patterns=[
            "scripts/**/*.au3",
            "scripts/*.au3",
            "Includes/**/*.au3",
            "Includes/*.au3",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "scripts/Main.au3" in connected_map["connected_files"]
    assert "Includes/Helper.au3" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "scripts/Main.au3",
        "Includes/Helper.au3",
    }


def test_connected_dependency_map_follows_squirrel_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "squirrel-connected-map-repo"
    (repo_path / "scripts" / "vscripts").mkdir(parents=True)
    (repo_path / "scripts" / "vscripts" / "main.nut").write_text(
        'IncludeScript("ppmod");\n'
        '::main <- function () {\n'
        "  ppmod.run();\n"
        "};\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "vscripts" / "ppmod.nut").write_text(
        "::ppmod <- {\n"
        "  run = function () {\n"
        '    return "ok";\n'
        "  }\n"
        "};\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/vscripts/main.nut"],
        bridge_paths=["scripts/vscripts"],
        include_patterns=[
            "scripts/vscripts/**/*.nut",
            "scripts/vscripts/*.nut",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "scripts/vscripts/main.nut" in connected_map["connected_files"]
    assert "scripts/vscripts/ppmod.nut" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "scripts/vscripts/main.nut",
        "scripts/vscripts/ppmod.nut",
    }


def test_connected_dependency_map_follows_cython_import_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cython-connected-map-repo"
    (repo_path / "pkg").mkdir(parents=True)
    (repo_path / "pkg" / "defs.pxi").write_text(
        "DEF ANSWER = 42\n",
        encoding="utf-8",
    )
    (repo_path / "pkg" / "helpermod.pxd").write_text(
        "cdef int helper()\n",
        encoding="utf-8",
    )
    (repo_path / "pkg" / "main.pyx").write_text(
        'include "defs.pxi"\n'
        "from helpermod cimport helper\n"
        "\n"
        "cpdef int run():\n"
        "    return helper()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["pkg/main.pyx"],
        bridge_paths=["pkg"],
        include_patterns=[
            "pkg/**/*.pyx",
            "pkg/**/*.pxd",
            "pkg/**/*.pxi",
            "pkg/*.pyx",
            "pkg/*.pxd",
            "pkg/*.pxi",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "pkg/main.pyx" in connected_map["connected_files"]
    assert "pkg/helpermod.pxd" in connected_map["connected_files"]
    assert "pkg/defs.pxi" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 2


def test_connected_dependency_map_follows_cuda_include_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "cuda-connected-map-repo"
    (repo_path / "src" / "kernels").mkdir(parents=True)
    (repo_path / "src" / "kernels" / "math.cuh").write_text(
        "__device__ inline int add_one(int x) {\n"
        "  return x + 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cu").write_text(
        '#include "kernels/math.cuh"\n'
        "__global__ void kernel_run(int* out) {\n"
        "  *out = add_one(*out);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.cu"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.cu", "src/**/*.cuh", "src/*.cu", "src/*.cuh"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "src/main.cu" in connected_map["connected_files"]
    assert "src/kernels/math.cuh" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1


def test_connected_dependency_map_follows_hlsl_include_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "hlsl-connected-map-repo"
    (repo_path / "shaders" / "include").mkdir(parents=True)
    (repo_path / "shaders" / "include" / "noise.hlsli").write_text(
        "float NoiseValue() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "shaders" / "main.hlsl").write_text(
        '#include "include/noise.hlsli"\n'
        "float4 RenderMain() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["shaders/main.hlsl"],
        bridge_paths=["shaders"],
        include_patterns=["shaders/**/*.hlsl", "shaders/**/*.hlsli", "shaders/*.hlsl"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "shaders/main.hlsl" in connected_map["connected_files"]
    assert "shaders/include/noise.hlsli" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1


def test_connected_dependency_map_follows_shaderlab_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shaderlab-connected-map-repo"
    (repo_path / "Shaders" / "Includes").mkdir(parents=True)
    (repo_path / "Shaders" / "Includes" / "Common.cginc").write_text(
        "float NoiseValue() {\n"
        "  return 0.25;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Shaders" / "Main.shader").write_text(
        'Shader "Demo/Main" {\n'
        "SubShader {\n"
        "Pass {\n"
        "HLSLPROGRAM\n"
        '#include "Includes/Common.cginc"\n'
        "float4 frag() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDHLSL\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["Shaders/Main.shader"],
        bridge_paths=["Shaders"],
        include_patterns=["Shaders/**/*.shader", "Shaders/**/*.cginc", "Shaders/*.shader"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "Shaders/Main.shader" in connected_map["connected_files"]
    assert "Shaders/Includes/Common.cginc" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1


def test_connected_dependency_map_follows_stan_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "stan-connected-map-repo"
    (repo_path / "models" / "lib").mkdir(parents=True)
    (repo_path / "models" / "lib" / "math.stan").write_text(
        "functions {\n"
        "  real add_one(real x) {\n"
        "    return x + 1;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "main.stan").write_text(
        '#include "lib/math.stan"\n'
        "\n"
        "functions {\n"
        "  real run(real x) {\n"
        "    return add_one(x);\n"
        "  }\n"
        "}\n"
        "data {\n"
        "  real x;\n"
        "}\n"
        "model {\n"
        "  target += run(x);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["models/main.stan"],
        bridge_paths=["models"],
        include_patterns=["models/**/*.stan", "models/*.stan"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "models/main.stan" in connected_map["connected_files"]
    assert "models/lib/math.stan" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1

def test_connected_dependency_map_follows_v_import_and_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "v-connected-map-repo"
    (repo_path / "src" / "helper").mkdir(parents=True)
    (repo_path / "main.v").write_text(
        "module main\n"
        "\n"
        "import helper\n"
        "\n"
        "fn run() {\n"
        "    helper.render_json()\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper" / "helper.v").write_text(
        "module helper\n"
        "\n"
        "pub fn render_json() string {\n"
        "    return '{}'\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.v"],
        bridge_paths=["src/helper"],
        include_patterns=["**/*.v", "*.v", "v.mod"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "main.v",
        "src/helper/helper.v",
    }


def test_connected_dependency_map_follows_smalltalk_class_message_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "smalltalk-connected-map-repo"
    (repo_path / "src" / "Demo-App").mkdir(parents=True)
    (repo_path / "src" / "Demo-Core").mkdir(parents=True)
    (repo_path / ".smalltalk.ston").write_text("{ }\n", encoding="utf-8")
    (repo_path / "src" / "Demo-Core" / "package.st").write_text(
        "Package { #name : 'Demo-Core' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-Core" / "Helper.class.st").write_text(
        "Class {\n"
        "\t#name : 'Helper',\n"
        "\t#superclass : 'Object',\n"
        "\t#category : 'Demo-Core',\n"
        "\t#package : 'Demo-Core'\n"
        "}\n"
        "\n"
        "{ #category : 'rendering' }\n"
        "Helper class >> renderJson [\n"
        "\t^ '{}'\n"
        "]\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-App" / "package.st").write_text(
        "Package { #name : 'Demo-App' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-App" / "Main.class.st").write_text(
        "Class {\n"
        "\t#name : 'Main',\n"
        "\t#superclass : 'Object',\n"
        "\t#category : 'Demo-App',\n"
        "\t#package : 'Demo-App'\n"
        "}\n"
        "\n"
        "{ #category : 'running' }\n"
        "Main >> run [\n"
        "\t^ Helper renderJson\n"
        "]\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Demo-App/Main.class.st"],
        bridge_paths=["src"],
        include_patterns=["**/*.st", "*.st", "**/*.ston", "*.ston"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/Demo-App/Main.class.st",
        "src/Demo-Core/Helper.class.st",
    }


def test_connected_dependency_map_follows_visual_basic_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "visual-basic-connected-map-repo"
    (repo_path / "src" / "Acme").mkdir(parents=True)
    (repo_path / "Acme.vbproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme" / "Mediator.vb").write_text(
        "Namespace Acme\n"
        "Public Class Mediator\n"
        "End Class\n"
        "End Namespace\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme" / "Handler.vb").write_text(
        "Imports Acme.Mediator\n"
        "Namespace Acme\n"
        "Public Class Handler\n"
        "    Private ReadOnly _mediator As Mediator = New Mediator()\n"
        "End Class\n"
        "End Namespace\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Acme/Handler.vb"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.vb", "src/*.vb", "*.vbproj"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/Acme/Handler.vb",
        "src/Acme/Mediator.vb",
    ]


def test_connected_dependency_map_follows_vbscript_wsf_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "vbscript-connected-map-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "helper.vbs").write_text(
        "Class Helper\n"
        "    Public Sub Run()\n"
        "    End Sub\n"
        "End Class\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.wsf").write_text(
        "<job>\n"
        '  <script language="VBScript" src="lib/helper.vbs"></script>\n'
        '  <script language="VBScript">\n'
        "    Option Explicit\n"
        "    Sub Main()\n"
        "        Dim helper\n"
        "        Set helper = New Helper\n"
        "        helper.Run()\n"
        "    End Sub\n"
        "  </script>\n"
        "</job>\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/main.wsf"],
        bridge_paths=["scripts"],
        include_patterns=["scripts/**/*.vbs", "scripts/**/*.wsf", "scripts/*.vbs", "scripts/*.wsf"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "scripts/lib/helper.vbs",
        "scripts/main.wsf",
    ]


def test_connected_dependency_map_follows_applescript_load_script_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "applescript-connected-map-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "Helper.applescript").write_text(
        "script HelperScript\n"
        "    on RenderJson(value)\n"
        "        return value\n"
        "    end RenderJson\n"
        "end script\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "Main.applescript").write_text(
        'property helperScript : load script POSIX file "lib/Helper.applescript"\n'
        "on run\n"
        "    helperScript's RenderJson(\"{}\")\n"
        "end run\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/Main.applescript"],
        bridge_paths=["scripts"],
        include_patterns=[
            "scripts/**/*.applescript",
            "scripts/*.applescript",
            "scripts/**/*.scpt",
            "scripts/*.scpt",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "scripts/Main.applescript",
        "scripts/lib/Helper.applescript",
    ] or connected_map["connected_files"] == [
        "scripts/lib/Helper.applescript",
        "scripts/Main.applescript",
    ]


def test_connected_dependency_map_follows_cfml_include_and_component_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cfml-connected-map-repo"
    (repo_path / "config").mkdir(parents=True)
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "config" / "app.cfm").write_text(
        "<cfset request.ready = true />\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "UserService.cfc").write_text(
        "component {\n"
        "    function run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Application.cfc").write_text(
        "component {\n"
        '    include "config/app.cfm";\n'
        "    function onApplicationStart() {\n"
        "        local.userService = new models.UserService();\n"
        "        local.userService.run();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["Application.cfc"],
        bridge_paths=["config", "models"],
        include_patterns=["**/*.cfc", "*.cfc", "**/*.cfm", "*.cfm"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert "Application.cfc" in connected_map["connected_files"]
    assert "config/app.cfm" in connected_map["connected_files"]
    assert "models/UserService.cfc" in connected_map["connected_files"]


def test_connected_dependency_map_follows_apex_trigger_and_handler_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "apex-connected-map-repo"
    (repo_path / "force-app" / "main" / "default" / "classes").mkdir(parents=True)
    (repo_path / "force-app" / "main" / "default" / "triggers").mkdir(parents=True)
    (repo_path / "sfdx-project.json").write_text(
        '{\n'
        '  "packageDirectories": [\n'
        '    { "path": "force-app", "default": true }\n'
        "  ],\n"
        '  "sourceApiVersion": "60.0"\n'
        '}\n',
        encoding="utf-8",
    )
    (
        repo_path
        / "force-app"
        / "main"
        / "default"
        / "classes"
        / "AccountTriggerHandler.cls"
    ).write_text(
        "public with sharing class AccountTriggerHandler {\n"
        "    public static void run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "force-app"
        / "main"
        / "default"
        / "triggers"
        / "AccountTrigger.trigger"
    ).write_text(
        "trigger AccountTrigger on Account (before insert) {\n"
        "    AccountTriggerHandler.run();\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["force-app/main/default/triggers/AccountTrigger.trigger"],
        bridge_paths=["force-app/main/default"],
        include_patterns=["force-app/**/*.cls", "force-app/**/*.trigger", "sfdx-project.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "force-app/main/default/classes/AccountTriggerHandler.cls",
        "force-app/main/default/triggers/AccountTrigger.trigger",
    ]


def test_connected_dependency_map_follows_wolfram_get_and_needs_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "wolfram-connected-map-repo"
    (repo_path / "Kernel").mkdir(parents=True)
    (repo_path / "PacletInfo.wl").write_text(
        'PacletObject[<|"Name" -> "Acme/Test", "Extensions" -> {{"Kernel", "Root" -> "Kernel", "Context" -> {"Acme`"}}}|>]\n',
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "init.m").write_text(
        'Get["Acme`Main`"];\n',
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "Main.wl").write_text(
        'BeginPackage["Acme`", {"Acme`Helpers`"}];\n'
        'run::usage = "run";\n'
        'Begin["`Private`"];\n'
        "run[] := helper[];\n"
        "End[];\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "Helpers.wl").write_text(
        'BeginPackage["Acme`"];\n'
        'helper::usage = "helper";\n'
        'Begin["`Private`"];\n'
        "helper[] := 1;\n"
        "End[];\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["Kernel/init.m"],
        bridge_paths=["Kernel"],
        include_patterns=["Kernel/**/*.wl", "Kernel/**/*.m", "PacletInfo.wl"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "Kernel/Helpers.wl",
        "Kernel/Main.wl",
        "Kernel/init.m",
    ]


def test_operational_seed_plan_without_diagnostics_uses_dbt_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dbt-sql-repo"
    (repo_path / "warehouse" / "models" / "staging").mkdir(parents=True)
    (repo_path / "warehouse" / "analyses").mkdir(parents=True)
    (repo_path / "warehouse" / "snapshots").mkdir(parents=True)
    (repo_path / "warehouse" / "macros").mkdir(parents=True)
    (repo_path / "dbt_project.yml").write_text(
        "name: acme\n"
        "model-paths:\n"
        "  - warehouse/models\n"
        "analysis-paths:\n"
        "  - warehouse/analyses\n"
        "snapshot-paths:\n"
        "  - warehouse/snapshots\n"
        "macro-paths:\n"
        "  - warehouse/macros\n",
        encoding="utf-8",
    )
    (repo_path / "warehouse" / "models" / "staging" / "stg_customers.sql").write_text(
        "select 1 as id\n",
        encoding="utf-8",
    )
    (repo_path / "warehouse" / "analyses" / "orders_report.sql").write_text(
        "select * from {{ ref('stg_customers') }}\n",
        encoding="utf-8",
    )
    (repo_path / "warehouse" / "snapshots" / "orders_snapshot.sql").write_text(
        "select * from {{ ref('stg_customers') }}\n",
        encoding="utf-8",
    )
    (repo_path / "warehouse" / "macros" / "helper.sql").write_text(
        "{% macro helper() %}select 1{% endmacro %}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "sql" in seed_plan["detected_ecosystems"]
    assert "dbt_project.yml" in seed_plan["config_paths"]
    assert "warehouse/models" in seed_plan["support_roots"]
    assert "warehouse/analyses" in seed_plan["support_roots"]
    assert "warehouse/snapshots" in seed_plan["support_roots"]
    assert "warehouse/macros" not in seed_plan["support_roots"]
    assert "warehouse/models/staging/stg_customers.sql" in seed_plan["entrypoint_files"]
    assert "warehouse/analyses/orders_report.sql" in seed_plan["entrypoint_files"]
    assert "warehouse/snapshots/orders_snapshot.sql" in seed_plan["entrypoint_files"]
    assert "warehouse/macros/helper.sql" not in seed_plan["entrypoint_files"]


def test_connected_dependency_map_follows_sql_relation_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "sql-connected-map-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "dbt_project.yml").write_text(
        "name: acme\n"
        "model-paths:\n"
        "  - models\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "customers.sql").write_text(
        "create table customers as\n"
        "select 1 as id;\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "orders.sql").write_text(
        "create view orders as\n"
        "select * from customers;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["models/orders.sql"],
        bridge_paths=["models"],
        include_patterns=["models/**/*.sql", "models/*.sql", "dbt_project.yml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "models/orders.sql",
        "models/customers.sql",
    }


def test_operational_seed_plan_without_diagnostics_uses_tsql_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tsql-profile-repo"
    (repo_path / "database" / "dbo" / "Stored Procedures").mkdir(parents=True)
    (repo_path / "database" / "dbo" / "Views").mkdir(parents=True)
    (repo_path / "database" / "tests").mkdir(parents=True)
    (repo_path / "database" / "Acme.sqlproj").write_text(
        "<Project>\n"
        "  <ItemGroup>\n"
        '    <Build Include="dbo\\Stored Procedures\\LoadCustomers.sql" />\n'
        '    <Build Include="dbo\\Views\\CustomersView.sql" />\n'
        "  </ItemGroup>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (
        repo_path / "database" / "dbo" / "Stored Procedures" / "LoadCustomers.sql"
    ).write_text(
        "create or alter procedure dbo.LoadCustomers\n"
        "as\n"
        "begin\n"
        "    set nocount on;\n"
        "    select 1 as id;\n"
        "end\n"
        "go\n",
        encoding="utf-8",
    )
    (repo_path / "database" / "dbo" / "Views" / "CustomersView.sql").write_text(
        "create or alter view dbo.CustomersView\n"
        "as\n"
        "select 1 as id;\n"
        "go\n",
        encoding="utf-8",
    )
    (repo_path / "database" / "tests" / "LoadCustomersTests.sql").write_text(
        "exec dbo.LoadCustomers;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["database"],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["tsql"]
    assert seed_plan["operational_ecosystems"] == ["tsql"]
    assert "database/Acme.sqlproj" in seed_plan["config_paths"]
    assert "database/dbo/Stored Procedures" in seed_plan["support_roots"]
    assert "database/dbo/Views" in seed_plan["support_roots"]
    assert "database/dbo/Stored Procedures/LoadCustomers.sql" in seed_plan["entrypoint_files"]
    assert "database/dbo/Views/CustomersView.sql" in seed_plan["entrypoint_files"]
    assert "database/tests/LoadCustomersTests.sql" not in seed_plan["entrypoint_files"]


def test_connected_dependency_map_follows_tsql_execute_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "tsql-connected-map-repo"
    (repo_path / "database" / "dbo" / "Stored Procedures").mkdir(parents=True)
    (repo_path / "database" / "Acme.sqlproj").write_text(
        "<Project>\n"
        "  <ItemGroup>\n"
        '    <Build Include="dbo\\Stored Procedures\\LoadCustomers.sql" />\n'
        '    <Build Include="dbo\\Stored Procedures\\LoadOrders.sql" />\n'
        "  </ItemGroup>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (
        repo_path / "database" / "dbo" / "Stored Procedures" / "LoadCustomers.sql"
    ).write_text(
        "create or alter procedure dbo.LoadCustomers\n"
        "as\n"
        "begin\n"
        "    set nocount on;\n"
        "    select 1 as id;\n"
        "end\n"
        "go\n",
        encoding="utf-8",
    )
    (repo_path / "database" / "dbo" / "Stored Procedures" / "LoadOrders.sql").write_text(
        "create or alter procedure dbo.LoadOrders\n"
        "as\n"
        "begin\n"
        "    set nocount on;\n"
        "    exec dbo.LoadCustomers;\n"
        "end\n"
        "go\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["database/dbo/Stored Procedures/LoadOrders.sql"],
        bridge_paths=["database/dbo/Stored Procedures"],
        include_patterns=["database/**/*.sql", "database/*.sql", "database/*.sqlproj"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "database/dbo/Stored Procedures/LoadOrders.sql",
        "database/dbo/Stored Procedures/LoadCustomers.sql",
    }


def test_operational_seed_plan_without_diagnostics_uses_solution_project_paths(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "solution-backed-fsharp-repo"
    (repo_path / "src" / "AcmeApp").mkdir(parents=True)
    (repo_path / "tests" / "AcmeApp.Benchmarks").mkdir(parents=True)
    (repo_path / "Acme.sln").write_text(
        'Microsoft Visual Studio Solution File, Format Version 12.00\n'
        'Project("{6EC3EE1D-3C4E-46DD-8F32-0CC8E7565705}") = "AcmeApp", "src\\\\AcmeApp\\\\AcmeApp.fsproj", "{11111111-1111-1111-1111-111111111111}"\n'
        "EndProject\n"
        'Project("{6EC3EE1D-3C4E-46DD-8F32-0CC8E7565705}") = "AcmeApp.Benchmarks", "tests\\\\AcmeApp.Benchmarks\\\\AcmeApp.Benchmarks.fsproj", "{22222222-2222-2222-2222-222222222222}"\n'
        "EndProject\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "AcmeApp.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Program.fs").write_text(
        "namespace AcmeApp\n\nmodule Program =\n    let main _ = 0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Routes.fs").write_text(
        "namespace AcmeApp\n\nmodule Routes =\n    let ping () = \"pong\"\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "AcmeApp.Benchmarks" / "AcmeApp.Benchmarks.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "AcmeApp.Benchmarks" / "Program.fs").write_text(
        "module Benchmarks.Program\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "dotnet" in seed_plan["detected_ecosystems"]
    assert "fsharp" in seed_plan["detected_ecosystems"]
    assert "Acme.sln" in seed_plan["config_paths"]
    assert "src/AcmeApp/AcmeApp.fsproj" in seed_plan["config_paths"]
    assert "src/AcmeApp" in seed_plan["support_roots"]
    assert "src/AcmeApp/Program.fs" in seed_plan["entrypoint_files"]
    assert "src/AcmeApp/Routes.fs" in seed_plan["entrypoint_files"]
    assert "tests/AcmeApp.Benchmarks/Program.fs" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_solution_profile_prefers_support_root_code(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "solution-library-repo"
    (repo_path / "src" / "AcmeLib").mkdir(parents=True)
    (repo_path / "docsrc" / "tools").mkdir(parents=True)
    (repo_path / "docsrc" / "content").mkdir(parents=True)
    (repo_path / "Acme.sln").write_text(
        'Microsoft Visual Studio Solution File, Format Version 12.00\n'
        'Project("{6EC3EE1D-3C4E-46DD-8F32-0CC8E7565705}") = "AcmeLib", "src\\\\AcmeLib\\\\AcmeLib.fsproj", "{11111111-1111-1111-1111-111111111111}"\n'
        "EndProject\n"
        'Project("{6EC3EE1D-3C4E-46DD-8F32-0CC8E7565705}") = "docsTool", "docsrc\\\\tools\\\\docsTool.fsproj", "{22222222-2222-2222-2222-222222222222}"\n'
        "EndProject\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeLib" / "AcmeLib.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeLib" / "Core.fs").write_text(
        "namespace AcmeLib\n\nmodule Core =\n    let answer = 42\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeLib" / "Pipeline.fs").write_text(
        "namespace AcmeLib\n\nmodule Pipeline =\n    let run value = value\n",
        encoding="utf-8",
    )
    (repo_path / "docsrc" / "tools" / "docsTool.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "docsrc" / "tools" / "Program.fs").write_text(
        "module DocsTool.Program\n",
        encoding="utf-8",
    )
    (repo_path / "docsrc" / "content" / "tutorial.fsx").write_text(
        "printfn \"docs\"\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "src/AcmeLib/Core.fs" in seed_plan["entrypoint_files"]
    assert "src/AcmeLib/Pipeline.fs" in seed_plan["entrypoint_files"]
    assert "docsrc/content/tutorial.fsx" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_solution_profile_excludes_docs_projects(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "solution-docs-project-repo"
    (repo_path / "src" / "AcmeLib").mkdir(parents=True)
    (repo_path / "src" / "Acme.Docs").mkdir(parents=True)
    (repo_path / "Acme.sln").write_text(
        'Microsoft Visual Studio Solution File, Format Version 12.00\n'
        'Project("{6EC3EE1D-3C4E-46DD-8F32-0CC8E7565705}") = "AcmeLib", "src\\\\AcmeLib\\\\AcmeLib.fsproj", "{11111111-1111-1111-1111-111111111111}"\n'
        "EndProject\n"
        'Project("{6EC3EE1D-3C4E-46DD-8F32-0CC8E7565705}") = "Acme.Docs", "src\\\\Acme.Docs\\\\Acme.Docs.fsproj", "{22222222-2222-2222-2222-222222222222}"\n'
        "EndProject\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeLib" / "AcmeLib.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeLib" / "Core.fs").write_text(
        "namespace AcmeLib\n\nmodule Core =\n    let answer = 42\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeLib" / "Pipeline.fs").write_text(
        "namespace AcmeLib\n\nmodule Pipeline =\n    let run value = value\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme.Docs" / "Acme.Docs.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme.Docs" / "Program.fs").write_text(
        "module Acme.Docs.Program\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "src/AcmeLib/Core.fs" in seed_plan["entrypoint_files"]
    assert "src/AcmeLib/Pipeline.fs" in seed_plan["entrypoint_files"]
    assert "src/Acme.Docs/Program.fs" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_cmake_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cmake-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include" / "acme").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text(
        "add_library(acme src/core.cpp include/acme/core.hpp)\n"
        "add_executable(acme_cli src/main.cpp)\n"
        "add_executable(acme_tests tests/core_test.cpp)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "core.cpp").write_text(
        '#include "acme/core.hpp"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cpp").write_text(
        '#include "acme/core.hpp"\n',
        encoding="utf-8",
    )
    (repo_path / "include" / "acme" / "core.hpp").write_text("#pragma once\n", encoding="utf-8")
    (repo_path / "tests" / "core_test.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "cpp" in seed_plan["detected_ecosystems"]
    assert "cmake" in seed_plan["detected_ecosystems"]
    assert "CMakeLists.txt" in seed_plan["config_paths"]
    assert "include/acme" in seed_plan["support_roots"]
    assert "include" not in seed_plan["support_roots"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.cpp" in seed_plan["entrypoint_files"]
    assert "src/core.cpp" in seed_plan["entrypoint_files"]
    assert "tests/core_test.cpp" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_meson_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "meson-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include" / "acme").mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('acme', 'c')\n"
        "library('acme', ['src/core.c', 'include/acme/core.h'])\n"
        "executable('acme_cli', 'src/main.c')\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "core.c").write_text(
        '#include "acme/core.h"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.c").write_text(
        '#include "acme/core.h"\n',
        encoding="utf-8",
    )
    (repo_path / "include" / "acme" / "core.h").write_text("#pragma once\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "c" in seed_plan["detected_ecosystems"]
    assert "meson" in seed_plan["detected_ecosystems"]
    assert "meson.build" in seed_plan["config_paths"]
    assert "include/acme" in seed_plan["support_roots"]
    assert "include" not in seed_plan["support_roots"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.c" in seed_plan["entrypoint_files"]
    assert "src/core.c" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_qmake_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qmake-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "libs").mkdir(parents=True)
    (repo_path / "project.pro").write_text(
        "TEMPLATE = subdirs\n"
        "SUBDIRS += libs app\n"
        "libs.file = libs/libs.pro\n"
        "app.file = app/app.pro\n"
        "app.depends = libs\n"
        "include(common.pri)\n",
        encoding="utf-8",
    )
    (repo_path / "common.pri").write_text("CONFIG += c++17\n", encoding="utf-8")
    (repo_path / "libs" / "libs.pro").write_text(
        "TEMPLATE = lib\n"
        "TARGET = helper\n"
        "SOURCES += helper.cpp\n",
        encoding="utf-8",
    )
    (repo_path / "libs" / "helper.cpp").write_text("int helper() { return 1; }\n", encoding="utf-8")
    (repo_path / "app" / "app.pro").write_text(
        "TEMPLATE = app\n"
        "TARGET = demo\n"
        "SOURCES += main.cpp\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "qmake" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "qmake"
    assert "project.pro" in seed_plan["config_paths"]
    assert "common.pri" in seed_plan["config_paths"]
    assert "libs/libs.pro" in seed_plan["config_paths"]
    assert "app/app.pro" in seed_plan["config_paths"]
    assert "app" in seed_plan["support_roots"]
    assert "libs" in seed_plan["support_roots"]
    assert "app/main.cpp" in seed_plan["entrypoint_files"]
    assert "libs/helper.cpp" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_qml_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qml-repo"
    (repo_path / "components").mkdir(parents=True)
    (repo_path / "qmldir").write_text(
        "module Demo.Components\n"
        "Button 1.0 components/Button.qml\n",
        encoding="utf-8",
    )
    (repo_path / "main.qml").write_text(
        'import "." as Demo\n'
        "Rectangle {\n"
        "    Demo.Button {\n"
        "        id: helper\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "components" / "Button.qml").write_text(
        "Rectangle {\n"
        "    id: helperButton\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "qml" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "qml"
    assert "qmldir" in seed_plan["config_paths"]
    assert "components" in seed_plan["support_roots"]
    assert "main.qml" in seed_plan["entrypoint_files"]
    assert "components/Button.qml" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_promotes_qml_in_qmake_repo_when_qml_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qml-qmake-repo"
    (repo_path / "components").mkdir(parents=True)
    (repo_path / "project.pro").write_text(
        "TEMPLATE = app\n"
        "TARGET = demo\n"
        "SOURCES += main.cpp\n"
        "RESOURCES += qml.qrc\n",
        encoding="utf-8",
    )
    (repo_path / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
    (repo_path / "qml.qrc").write_text(
        "<RCC><qresource prefix=\"/\">"
        "<file>main.qml</file>"
        "<file>components/Button.qml</file>"
        "<file>components/Card.qml</file>"
        "</qresource></RCC>\n",
        encoding="utf-8",
    )
    (repo_path / "main.qml").write_text(
        'import "." as Demo\n'
        "Rectangle {\n"
        "    Demo.Button {}\n"
        "    Demo.Card {}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "components" / "Button.qml").write_text(
        "Rectangle {\n"
        "    id: helperButton\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "components" / "Card.qml").write_text(
        "Rectangle {\n"
        "    id: helperCard\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "qml" in seed_plan["detected_ecosystems"]
    assert "qmake" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "qml"
    assert "project.pro" in seed_plan["config_paths"]
    assert "main.qml" in seed_plan["entrypoint_files"]
    assert "components" in seed_plan["support_roots"]
    assert "components/Button.qml" in seed_plan["candidate_file_paths"]
    assert "components/Card.qml" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_just_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "just-repo"
    (repo_path / "tasks").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "Justfile").write_text(
        "mod release 'tasks/release.just'\n"
        "build: release::publish\n"
        "  just lint\n"
        "lint:\n"
        "  ./scripts/lint.sh\n",
        encoding="utf-8",
    )
    (repo_path / "tasks" / "release.just").write_text(
        "publish:\n"
        "  echo publish\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "lint.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "just" in seed_plan["detected_ecosystems"]
    assert "Justfile" in seed_plan["entrypoint_files"]
    assert "tasks" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_cmake_profile_ignores_absolute_like_tokens(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cmake-absolute-token-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text(
        "add_library(acme /tmp/generated.c src/main.cpp)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "/" not in seed_plan["support_roots"]
    assert "//" not in seed_plan["support_roots"]
    assert "src/main.cpp" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_deprioritizes_dotnet_benchmark_projects(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dotnet-library-repo"
    (repo_path / "src" / "AcmeLib").mkdir(parents=True)
    (repo_path / "test" / "AcmeLib.Benchmarks").mkdir(parents=True)
    (repo_path / "src" / "AcmeLib" / "AcmeLib.csproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeLib" / "Mediator.cs").write_text(
        "public sealed class Mediator {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeLib" / "Pipeline.cs").write_text(
        "public sealed class Pipeline {}\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "AcmeLib.Benchmarks" / "AcmeLib.Benchmarks.csproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "AcmeLib.Benchmarks" / "Program.cs").write_text(
        "class Program { static void Main() {} }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "dotnet" in seed_plan["detected_ecosystems"]
    assert "src/AcmeLib/Mediator.cs" in seed_plan["entrypoint_files"]
    assert "src/AcmeLib/Pipeline.cs" in seed_plan["entrypoint_files"]
    assert "test/AcmeLib.Benchmarks/Program.cs" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_gemfile_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ruby-gem-repo"
    (repo_path / "lib" / "ruby_gem_repo").mkdir(parents=True)
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "lib" / "ruby_gem_repo.rb").write_text("module RubyGemRepo\nend\n", encoding="utf-8")
    (repo_path / "lib" / "ruby_gem_repo" / "version.rb").write_text(
        "module RubyGemRepo\n  VERSION = '0.1.0'\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "ruby" in seed_plan["detected_ecosystems"]
    assert "Gemfile" in seed_plan["config_paths"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/ruby_gem_repo.rb" in seed_plan["entrypoint_files"]
    assert "lib/ruby_gem_repo/version.rb" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_gemspec_name_hints(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rails-like-ruby-repo"
    (repo_path / "actionmailer" / "lib").mkdir(parents=True)
    (repo_path / "actionmailer" / "actionmailer.gemspec").write_text(
        'Gem::Specification.new do |spec|\n'
        '  spec.name = "actionmailer"\n'
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "actionmailer" / "lib" / "action_mailer.rb").write_text(
        "module ActionMailer\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "ruby" in seed_plan["detected_ecosystems"]
    assert "actionmailer/actionmailer.gemspec" in seed_plan["config_paths"]
    assert "actionmailer/lib" in seed_plan["support_roots"]
    assert "actionmailer/lib/action_mailer.rb" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_balances_polyglot_manifest_entrypoints(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "polyglot-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        '{\n'
        '  "name": "polyglot-profile",\n'
        '  "scripts": { "dev": "vite" }\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "src" / "main.tsx").write_text("export const bootstrap = 1;\n", encoding="utf-8")
    (repo_path / "src" / "App.tsx").write_text("export const App = () => null;\n", encoding="utf-8")
    (repo_path / "lib" / "polyglot_profile_repo.rb").write_text(
        "module PolyglotProfileRepo\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "node" in seed_plan["detected_ecosystems"]
    assert "ruby" in seed_plan["detected_ecosystems"]
    assert "src/main.tsx" in seed_plan["entrypoint_files"]
    assert "lib/polyglot_profile_repo.rb" in seed_plan["entrypoint_files"]


def test_connected_dependency_map_follows_ruby_require_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "ruby-connected-map-repo"
    (repo_path / "lib" / "jekyll").mkdir(parents=True)
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "lib" / "jekyll.rb").write_text(
        'require "jekyll/cache"\n'
        "module Jekyll\n"
        "  def self.run\n"
        "    Jekyll::Cache.helper\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "jekyll" / "cache.rb").write_text(
        "module Jekyll\n"
        "  class Cache\n"
        "    def self.helper\n"
        "      1\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lib/jekyll.rb"],
        bridge_paths=["lib"],
        include_patterns=["lib/*.rb", "lib/**/*.rb", "Gemfile"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "lib/jekyll.rb",
        "lib/jekyll/cache.rb",
    ]


def test_connected_dependency_map_follows_ruby_new_inheritance_and_mixin_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ruby-structure-connected-map-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "lib" / "acme" / "base_runner.rb").write_text(
        "module Acme\n"
        "  class BaseRunner\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "serializable.rb").write_text(
        "module Acme\n"
        "  module Serializable\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "runner.rb").write_text(
        'require "acme/base_runner"\n'
        'require "acme/serializable"\n'
        "module Acme\n"
        "  class Runner < BaseRunner\n"
        "    include Serializable\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme.rb").write_text(
        'require "acme/runner"\n'
        "module Acme\n"
        "  def self.build\n"
        "    Runner.new\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lib/acme.rb"],
        bridge_paths=["lib"],
        include_patterns=["lib/*.rb", "lib/**/*.rb", "Gemfile"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 4
    assert connected_map["resolved_dependency_edges"] >= 3
    assert connected_map["connected_files"] == [
        "lib/acme.rb",
        "lib/acme/base_runner.rb",
        "lib/acme/runner.rb",
        "lib/acme/serializable.rb",
    ]


def test_connected_dependency_map_follows_php_trait_docblock_and_type_hint_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "php-connected-map-repo"
    (repo_path / "app" / "Models").mkdir(parents=True)
    (repo_path / "app" / "Traits").mkdir(parents=True)
    (repo_path / "database" / "Factories").mkdir(parents=True)
    (repo_path / "app" / "Models" / "User.php").write_text(
        "<?php\n"
        "namespace App\\Models;\n"
        "class User {}\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "Traits" / "HasAudit.php").write_text(
        "<?php\n"
        "namespace App\\Traits;\n"
        "trait HasAudit {}\n",
        encoding="utf-8",
    )
    (repo_path / "database" / "Factories" / "UserFactory.php").write_text(
        "<?php\n"
        "namespace Database\\Factories;\n"
        "class UserFactory {}\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "Models" / "AuditedUser.php").write_text(
        "<?php\n"
        "namespace App\\Models;\n"
        "use App\\Traits\\HasAudit;\n"
        "use Database\\Factories\\UserFactory;\n"
        "/** @use HasAudit<UserFactory> */\n"
        "class AuditedUser extends User {\n"
        "    use HasAudit;\n"
        "    public function __construct(private UserFactory $factory) {}\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["app/Models/AuditedUser.php"],
        bridge_paths=["app", "database"],
        include_patterns=["app/**/*.php", "database/**/*.php"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 4
    assert connected_map["resolved_dependency_edges"] >= 3
    assert connected_map["connected_files"] == [
        "app/Models/AuditedUser.php",
        "app/Models/User.php",
        "app/Traits/HasAudit.php",
        "database/Factories/UserFactory.php",
    ]


def test_connected_dependency_map_uses_profile_support_roots_without_reverse_bridging(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "frontend-support-roots-repo"
    (repo_path / "src" / "pages").mkdir(parents=True)
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "types").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        '{\n'
        '  "name": "frontend-profile",\n'
        '  "scripts": { "dev": "vite", "build": "vite build" }\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "tsconfig.app.json").write_text(
        '{\n'
        '  "compilerOptions": {\n'
        '    "baseUrl": ".",\n'
        '    "paths": { "@/*": ["./src/*"] }\n'
        "  },\n"
        '  "include": ["src"]\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "lib" / "utils.ts").write_text(
        "export const cn = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "types" / "quote.ts").write_text(
        "export interface Quote { id: string }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "pages" / "Index.tsx").write_text(
        "import type { Quote } from '@/types/quote';\n"
        "import { cn } from '@/lib/utils';\n"
        "export const Index = (): Quote => ({ id: cn() });\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "App.tsx").write_text(
        "import { Index } from './pages/Index';\n"
        "export const App = () => Index();\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.tsx").write_text(
        "import { App } from './App';\n"
        "export const bootstrap = () => App();\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )
    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=list(seed_plan["entrypoint_files"]),
        bridge_paths=[],
        candidate_scope_paths=list(seed_plan["support_roots"]),
        enable_reverse_bridging=False,
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["bridged_importer_count"] == 0
    assert "src/lib/utils.ts" in connected_map["connected_files"]
    assert "src/types/quote.ts" in connected_map["connected_files"]


def test_connected_dependency_map_reuses_shared_dependency_cache_across_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "services" / "app" / "src" / "util.ts").write_text(
        "export const helper = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { helper } from './util';\n"
        "export const run = (): string => helper();\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    first = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    def _unexpected_analyze_file_dependencies(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("shared dependency-analysis cache should avoid reparsing unchanged files")

    monkeypatch.setattr(
        repository_service,
        "_analyze_file_dependencies",
        _unexpected_analyze_file_dependencies,
    )

    second = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert first["connected_files"] == second["connected_files"]
    assert second["resolved_dependency_edges"] == first["resolved_dependency_edges"]


def test_connected_dependency_map_follows_python_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "python-workspace-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "helper.py").write_text(
        "def helper() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "util.py").write_text(
        "from lib.helper import helper\n\n"
        "def normalize() -> str:\n"
        "    return helper()\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "main.py").write_text(
        "from app.util import normalize\n\n"
        "def run() -> str:\n"
        "    return normalize()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["app/main.py"],
        bridge_paths=["app"],
        include_patterns=["app/*.py", "app/**/*.py", "lib/*.py", "lib/**/*.py"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "app/main.py",
        "app/util.py",
        "lib/helper.py",
    ]


def test_connected_dependency_map_follows_rust_module_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "rust-workspace-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.rs").write_text(
        "pub fn value() -> String {\n"
        '    "ok".to_string()\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.rs").write_text(
        "use crate::helper::value;\n"
        "mod helper;\n\n"
        "pub fn run() -> String {\n"
        "    value()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.rs"],
        bridge_paths=["src"],
        include_patterns=["src/*.rs", "src/**/*.rs"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/helper.rs",
        "src/main.rs",
    ]


def test_connected_dependency_map_follows_go_module_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "go-workspace-repo"
    (repo_path / "helper").mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper" / "helper.go").write_text(
        "package helper\n\n"
        "func Value() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package main\n\n"
        'import "example.com/repo/helper"\n\n'
        "func run() string {\n"
        "    return helper.Value()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.go"],
        bridge_paths=["."],
        include_patterns=["*.go", "**/*.go"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "helper/helper.go",
        "main.go",
    ]


def test_connected_dependency_map_follows_go_same_package_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "go-same-package-connected-map-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run() string {\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.go"],
        bridge_paths=["."],
        include_patterns=["*.go", "**/*.go"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "helper.go",
        "main.go",
    ]


def test_connected_dependency_map_ignores_go_builtin_collisions_for_same_package_refs(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "go-builtin-connected-map-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "builtin.go").write_text(
        "package cobra\n\n"
        "func len(items []string) int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run(items []string) int {\n"
        "    _ = len(items)\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.go"],
        bridge_paths=["."],
        include_patterns=["*.go", "**/*.go"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "helper.go",
        "main.go",
    ]


def test_connected_dependency_map_prefers_non_test_go_same_package_targets(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "go-test-leak-connected-map-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "helper_test.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "test"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run() string {\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.go"],
        bridge_paths=["."],
        include_patterns=["*.go", "**/*.go"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "helper.go",
        "main.go",
    ]


def test_connected_dependency_map_ignores_go_stdlib_import_file_name_collisions(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "go-stdlib-import-collision-connected-map-repo"
    (repo_path / "middleware").mkdir(parents=True)
    (repo_path / "_examples" / "versions" / "data").mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "middleware" / "recoverer.go").write_text(
        "package middleware\n\n"
        'import "errors"\n\n'
        "func Recoverer() error {\n"
        '    return errors.New("boom")\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "_examples" / "versions" / "data" / "errors.go").write_text(
        "package data\n\n"
        "func PresentError() string {\n"
        '    return "boom"\n'
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["middleware/recoverer.go"],
        bridge_paths=[".", "_examples"],
        include_patterns=["*.go", "**/*.go"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_files"] == [
        "middleware/recoverer.go",
    ]


def test_connected_dependency_map_follows_kotlin_multi_type_file_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "kotlin-connected-map-repo"
    package_dir = repo_path / "src" / "main" / "kotlin" / "com" / "example"
    package_dir.mkdir(parents=True)
    (package_dir / "Repositories.kt").write_text(
        "package com.example\n"
        "interface ArticleRepository\n"
        "interface UserRepository\n",
        encoding="utf-8",
    )
    (package_dir / "Controllers.kt").write_text(
        "package com.example\n"
        "class HtmlController(\n"
        "    private val articleRepository: ArticleRepository,\n"
        "    private val userRepository: UserRepository,\n"
        ")\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main/kotlin/com/example/Controllers.kt"],
        bridge_paths=["src/main/kotlin"],
        include_patterns=["src/main/kotlin/**/*.kt"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/main/kotlin/com/example/Controllers.kt",
        "src/main/kotlin/com/example/Repositories.kt",
    ]


def test_connected_dependency_map_follows_groovy_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "groovy-connected-map-repo"
    package_dir = repo_path / "src" / "main" / "groovy" / "org" / "example"
    package_dir.mkdir(parents=True)
    (repo_path / "build.gradle").write_text(
        "plugins { id 'groovy' }\n",
        encoding="utf-8",
    )
    (package_dir / "Owner.groovy").write_text(
        "package org.example\nclass Owner {}\n",
        encoding="utf-8",
    )
    (package_dir / "OwnerController.groovy").write_text(
        "package org.example\n"
        "import org.example.Owner as PetOwner\n"
        "class OwnerController {\n"
        "  PetOwner owner\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main/groovy/org/example/OwnerController.groovy"],
        bridge_paths=["src/main/groovy"],
        include_patterns=["build.gradle", "src/main/groovy/**/*.groovy"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert sorted(connected_map["connected_files"]) == [
        "src/main/groovy/org/example/Owner.groovy",
        "src/main/groovy/org/example/OwnerController.groovy",
    ]


def test_connected_dependency_map_follows_robotframework_resource_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "robotframework-connected-map-repo"
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "resources").mkdir(parents=True)
    (repo_path / "resources" / "common.resource").write_text(
        "*** Keywords ***\nOpen Login Page\n    Log    ready\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "login.robot").write_text(
        "*** Settings ***\nResource    ../resources/common.resource\n\n*** Test Cases ***\nValid Login\n    Open Login Page\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["tests/login.robot"],
        bridge_paths=["tests", "resources"],
        include_patterns=["tests/**/*.robot", "resources/**/*.resource"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert sorted(connected_map["connected_files"]) == [
        "resources/common.resource",
        "tests/login.robot",
    ]


def test_connected_dependency_map_follows_typst_import_include_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "typst-connected-map-repo"
    (repo_path / "content").mkdir(parents=True)
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "content" / "math.typ").write_text(
        "#let add(x, y) = x + y\n"
        "#let scale(x) = x * 2\n",
        encoding="utf-8",
    )
    (repo_path / "partials" / "common.typ").write_text(
        "#let title() = [Demo]\n",
        encoding="utf-8",
    )
    (repo_path / "main.typ").write_text(
        '#import "content/math.typ": add\n'
        '#import "content/math.typ" as math\n'
        '#include "partials/common.typ"\n'
        "#let render() = {\n"
        "  add(1, 2)\n"
        "  math.scale(3)\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.typ"],
        bridge_paths=["content", "partials"],
        include_patterns=["*.typ", "content/*.typ", "content/**/*.typ", "partials/*.typ"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert sorted(connected_map["connected_files"]) == [
        "content/math.typ",
        "main.typ",
        "partials/common.typ",
    ]


def test_connected_dependency_map_follows_scss_import_and_reference_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scss-connected-map-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "_mixins.scss").write_text(
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "_functions.scss").write_text(
        "@function helper-fn() {\n"
        "  @return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "app.scss").write_text(
        '@use "styles/mixins" as mixins;\n'
        '@import "styles/functions";\n'
        ".button {\n"
        "  @include mixins.button-base;\n"
        "  color: helper-fn();\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["app.scss"],
        bridge_paths=["styles"],
        include_patterns=["*.scss", "styles/*.scss", "styles/**/*.scss"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert sorted(connected_map["connected_files"]) == [
        "app.scss",
        "styles/_functions.scss",
        "styles/_mixins.scss",
    ]


def test_connected_dependency_map_follows_dockerfile_copy_run_and_stage_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dockerfile-connected-map-repo"
    (repo_path / "docker").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "bootstrap.sh").write_text(
        "#!/usr/bin/env sh\n"
        "echo bootstrap\n",
        encoding="utf-8",
    )
    (repo_path / "docker" / "Dockerfile").write_text(
        "FROM alpine:3.20 AS base\n"
        "COPY ../scripts/bootstrap.sh /usr/local/bin/bootstrap.sh\n"
        "RUN ./../scripts/bootstrap.sh\n"
        "FROM base AS runtime\n"
        "COPY --from=base /usr/local/bin/bootstrap.sh /usr/local/bin/bootstrap.sh\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["docker/Dockerfile"],
        bridge_paths=["scripts"],
        include_patterns=["docker/Dockerfile", "scripts/*.sh", "scripts/**/*.sh"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 2
    assert sorted(connected_map["connected_files"]) == [
        "docker/Dockerfile",
        "scripts/bootstrap.sh",
    ]


def test_connected_dependency_map_follows_dart_package_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "dart-workspace-repo"
    (repo_path / "lib" / "src").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "pubspec.yaml").write_text(
        "name: acme_client\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "src" / "helper.dart").write_text(
        "class Helper {\n"
        "  static String value() => 'ok';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme_client.dart").write_text(
        "export 'src/helper.dart' show Helper;\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "acme_client.dart").write_text(
        "import 'package:acme_client/acme_client.dart' show Helper;\n\n"
        "String run() => Helper.value();\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["bin/acme_client.dart"],
        bridge_paths=["lib", "bin"],
        include_patterns=["lib/*.dart", "lib/**/*.dart", "bin/*.dart", "bin/**/*.dart"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "bin/acme_client.dart",
        "lib/acme_client.dart",
        "lib/src/helper.dart",
    ]


def test_connected_dependency_map_follows_clojure_namespace_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "clojure-connected-map-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "util.clj").write_text(
        "(ns acme.util)\n(defn helper [] :ok)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.clj").write_text(
        "(ns acme.core\n"
        "  (:require [acme.util :as util]))\n"
        "(defn run []\n"
        "  (util/helper))\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme/core.clj"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.clj", "src/**/*.cljc", "src/**/*.cljs"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme/core.clj",
        "src/acme/util.clj",
    ]


def test_connected_dependency_map_follows_lua_require_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "lua-connected-map-repo"
    (repo_path / "lua" / "acme").mkdir(parents=True)
    (repo_path / "lua" / "acme" / "util.lua").write_text(
        "local M = {}\nfunction M.helper() return 'ok' end\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "core.lua").write_text(
        "local util = require('acme.util')\n"
        "local function run()\n"
        "  return util.helper()\n"
        "end\n"
        "return { run = run }\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lua/acme/core.lua"],
        bridge_paths=["lua"],
        include_patterns=["lua/**/*.lua", "*.rockspec"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "lua/acme/core.lua",
        "lua/acme/util.lua",
    ]


def test_connected_dependency_map_follows_lua_require_member_and_method_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lua-member-connected-map-repo"
    (repo_path / "lua" / "acme").mkdir(parents=True)
    (repo_path / "lua" / "acme" / "util.lua").write_text(
        "local M = {}\n"
        "function M.helper() return 'ok' end\n"
        "function M:push() return self:helper() end\n"
        "return M\n",
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "core.lua").write_text(
        "local util = require('acme.util')\n"
        "local helper = require('acme.util').helper\n"
        "local function run()\n"
        "  util:push()\n"
        "  return helper()\n"
        "end\n"
        "return { run = run }\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lua/acme/core.lua"],
        bridge_paths=["lua"],
        include_patterns=["lua/**/*.lua", "*.rockspec"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 3
    assert connected_map["connected_files"] == [
        "lua/acme/core.lua",
        "lua/acme/util.lua",
    ]


def test_connected_dependency_map_follows_shell_source_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "shell-connected-map-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "lib" / "util.zsh").write_text(
        "helper() {\n"
        "  echo ok\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.sh").write_text(
        ". ../lib/util.zsh\n"
        "run() {\n"
        "  helper\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/main.sh"],
        bridge_paths=["scripts", "lib"],
        include_patterns=["scripts/*.sh", "lib/*.zsh"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "lib/util.zsh",
        "scripts/main.sh",
    ]


def test_connected_dependency_map_follows_awk_include_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "awk-connected-map-repo"
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "math.awk").write_text(
        "function add(a, b) {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "translate").write_text(
        "#!/usr/bin/env gawk -f\n"
        '@include "../lib/math.awk"\n'
        "BEGIN {\n"
        "    print add(1, 2)\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["bin/translate"],
        bridge_paths=["bin", "lib"],
        include_patterns=["bin/translate", "lib/*.awk", "**/*.awk", "*.awk"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "bin/translate",
        "lib/math.awk",
    ]


def test_connected_dependency_map_follows_coffeescript_require_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "coffeescript-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.coffee").write_text(
        "renderJson = (value) ->\n"
        "  value\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.coffee").write_text(
        "helper = require './helper'\n"
        "run = ->\n"
        "  helper.renderJson '{}'\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.coffee"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.coffee", "src/*.coffee", "*.coffee", "Cakefile"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/helper.coffee",
        "src/main.coffee",
    ]


def test_connected_dependency_map_follows_elm_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "elm-connected-map-repo"
    (repo_path / "src" / "Page").mkdir(parents=True)
    (repo_path / "src" / "Page" / "Home.elm").write_text(
        "module Page.Home exposing (homeView)\n\n"
        "homeView : String\n"
        "homeView =\n"
        "    \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.elm").write_text(
        "module Main exposing (main)\n\n"
        "import Page.Home exposing (homeView)\n\n"
        "main : String\n"
        "main =\n"
        "    homeView\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.elm"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.elm", "src/*.elm", "elm.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/Main.elm",
        "src/Page/Home.elm",
    ]


def test_connected_dependency_map_follows_powershell_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "powershell-connected-map-repo"
    (repo_path / "Private").mkdir(parents=True)
    (repo_path / "Private" / "Helpers.ps1").write_text(
        "function Get-Helper {\n"
        "  return 'ok'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Module.psm1").write_text(
        '. "$PSScriptRoot/Private/Helpers.ps1"\n'
        "function Invoke-Main {\n"
        "  Get-Helper\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["Module.psm1"],
        bridge_paths=["Private", "Module.psm1"],
        include_patterns=["*.psm1", "Private/*.ps1", "*.psd1"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "Module.psm1",
        "Private/Helpers.ps1",
    ]


def test_connected_dependency_map_follows_erlang_module_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "erlang-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "acme_util.erl").write_text(
        "-module(acme_util).\n-export([helper/0]).\nhelper() -> ok.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.erl").write_text(
        "-module(acme).\n-export([run/0]).\nrun() -> acme_util:helper().\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme.erl"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.erl", "src/**/*.hrl", "rebar.config"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme.erl",
        "src/acme_util.erl",
    ]


def test_connected_dependency_map_follows_nim_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "nim-connected-map-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "util.nim").write_text(
        "proc helper*(): string =\n"
        "  \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.nim").write_text(
        "import acme/util\n"
        "proc run*(): string =\n"
        "  util.helper()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme.nim"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.nim", "*.nimble", "config.nims"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme.nim",
        "src/acme/util.nim",
    ]


def test_connected_dependency_map_follows_ocaml_module_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "ocaml-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "util.ml").write_text(
        "let helper () = 1\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.ml").write_text(
        "let run () = Util.helper ()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.ml"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.ml", "src/*.ml", "dune-project", "**/dune", "*.opam"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/main.ml",
        "src/util.ml",
    ]


def test_connected_dependency_map_follows_perl_module_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "perl-connected-map-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "lib" / "My" / "Util.pm").write_text(
        "package My::Util;\nsub helper { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\nuse My::Util;\nsub run { My::Util->helper() }\n1;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lib/My/Main.pm"],
        bridge_paths=["lib"],
        include_patterns=["lib/**/*.pm", "lib/*.pm", "cpanfile", "Makefile.PL", "Build.PL"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "lib/My/Main.pm",
        "lib/My/Util.pm",
    ]


def test_connected_dependency_map_follows_perl_imported_call_and_parent_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "perl-imported-call-connected-map-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "lib" / "My" / "Base.pm").write_text(
        "package My::Base;\nsub parent_method { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Util.pm").write_text(
        "package My::Util;\nsub helper { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\nuse parent 'My::Base';\nuse My::Util qw(helper);\nsub run { helper() }\n1;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lib/My/Main.pm"],
        bridge_paths=["lib"],
        include_patterns=["lib/**/*.pm", "lib/*.pm", "cpanfile", "Makefile.PL", "Build.PL"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "lib/My/Base.pm",
        "lib/My/Main.pm",
        "lib/My/Util.pm",
    ]


def test_connected_dependency_map_follows_r_source_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "r-connected-map-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    (repo_path / "R" / "helper.R").write_text(
        "helper <- function() {\n  1\n}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "main.R").write_text(
        'source("helper.R")\n'
        "run <- function() {\n"
        "  helper()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["R/main.R"],
        bridge_paths=["R"],
        include_patterns=["R/**/*.R", "R/*.R", "DESCRIPTION", "NAMESPACE"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "R/helper.R",
        "R/main.R",
    ]


def test_connected_dependency_map_follows_r_package_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "r-package-symbol-connected-map-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    (repo_path / "R" / "helper.R").write_text(
        "helper <- function() {\n  1\n}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "main.R").write_text(
        "run <- function() {\n"
        "  helper()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["R/main.R"],
        bridge_paths=["R"],
        include_patterns=["R/**/*.R", "R/*.R", "DESCRIPTION", "NAMESPACE"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "R/helper.R",
        "R/main.R",
    ]


def test_connected_dependency_map_ignores_r_builtin_collisions_for_package_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "r-package-builtin-connected-map-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    (repo_path / "R" / "builtin-shadow.R").write_text(
        "names <- function(x) {\n"
        "  x\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "helper.R").write_text(
        "helper <- function(x) {\n"
        "  x\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "main.R").write_text(
        "run <- function(x) {\n"
        "  names(x)\n"
        "  helper(x)\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["R/main.R"],
        bridge_paths=["R"],
        include_patterns=["R/**/*.R", "R/*.R", "DESCRIPTION", "NAMESPACE"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "R/helper.R",
        "R/main.R",
    ]


def test_connected_dependency_map_follows_julia_include_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "julia-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project.toml").write_text(
        'name = "Acme"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.jl").write_text(
        "module Helper\nhelper() = 1\nend\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme.jl").write_text(
        'module Acme\ninclude("Helper.jl")\nusing .Helper: helper\n'
        "run() = helper()\nend\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Acme.jl"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.jl", "src/*.jl", "Project.toml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/Acme.jl",
        "src/Helper.jl",
    ]


def test_connected_dependency_map_follows_crystal_wildcard_requires(tmp_path: Path) -> None:
    repo_path = tmp_path / "crystal-connected-map-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shard.yml").write_text(
        "name: acme\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.cr").write_text(
        'require "./acme/*"\nmodule Acme\nend\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "helper.cr").write_text(
        "module Acme::Helper\n"
        "  def self.helper : Int32\n"
        "    1\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme.cr"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.cr", "src/*.cr", "shard.yml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme.cr",
        "src/acme/helper.cr",
    ]


def test_connected_dependency_map_follows_crystal_type_annotation_and_mixin_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "crystal-type-annotation-connected-map-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shard.yml").write_text(
        "name: acme\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "base_runner.cr").write_text(
        "module Acme\n"
        "  class BaseRunner\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "serializable.cr").write_text(
        "module Acme\n"
        "  module Serializable\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "options.cr").write_text(
        "module Acme\n"
        "  class Options\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "runner.cr").write_text(
        "module Acme\n"
        "  class Runner < BaseRunner\n"
        "    include Serializable\n"
        "    def initialize(options : Options)\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme/runner.cr"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.cr", "src/*.cr", "shard.yml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 4
    assert connected_map["resolved_dependency_edges"] >= 3
    assert connected_map["connected_files"] == [
        "src/acme/base_runner.cr",
        "src/acme/options.cr",
        "src/acme/runner.cr",
        "src/acme/serializable.cr",
    ]


def test_connected_dependency_map_uses_precomputed_candidate_files_for_dart_workspace_packages(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dart-workspace-packages-repo"
    (repo_path / "pkgs" / "app" / "lib").mkdir(parents=True)
    (repo_path / "pkgs" / "http" / "lib" / "src").mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "pubspec.yaml").write_text(
        "name: http\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "src" / "base.dart").write_text(
        "class Client {\n"
        "  String ping() => 'ok';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "http.dart").write_text(
        "export 'src/base.dart' show Client;\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "app" / "lib" / "app.dart").write_text(
        "import 'package:http/http.dart' show Client;\n\n"
        "String run() => Client().ping();\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["pkgs/app/lib/app.dart"],
        bridge_paths=["pkgs/app/lib"],
        candidate_file_paths=[
            "pkgs/app/lib/app.dart",
            "pkgs/http/lib/http.dart",
            "pkgs/http/lib/src/base.dart",
        ],
        include_patterns=["pkgs/**/*.dart"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "pkgs/app/lib/app.dart",
        "pkgs/http/lib/http.dart",
        "pkgs/http/lib/src/base.dart",
    ]


def test_connected_dependency_map_follows_cpp_include_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "cpp-workspace-repo"
    (repo_path / "include" / "acme").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include" / "acme" / "core.hpp").write_text("#pragma once\n", encoding="utf-8")
    (repo_path / "src" / "format.hpp").write_text(
        '#include "acme/core.hpp"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cpp").write_text(
        '#include "format.hpp"\n',
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.cpp"],
        bridge_paths=["src", "include"],
        include_patterns=["src/**/*.cpp", "src/**/*.hpp", "include/**/*.hpp"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "include/acme/core.hpp",
        "src/format.hpp",
        "src/main.cpp",
    ]


def test_connected_dependency_map_follows_mojo_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "mojo-workspace-repo"
    (repo_path / "helper").mkdir(parents=True)
    (repo_path / "helper" / "util.mojo").write_text(
        "fn value():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (repo_path / "main.mojo").write_text(
        "import helper.util\n\n"
        "fn run():\n"
        "    return util.value()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.mojo"],
        bridge_paths=["."],
        include_patterns=["*.mojo", "**/*.mojo"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "helper/util.mojo",
        "main.mojo",
    ]


def test_candidate_solutions_specialize_typescript_rootdir_drift() -> None:
    repo_path = Path("/tmp/repo")
    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output=(
            "services/execution-service/src/index.ts(12,5): error TS6059: "
            "File is not under 'rootDir'.\n"
            "packages/common/src/execution.ts(4,1): error TS6059: "
            "File is not under 'rootDir'.\n"
        ),
    )

    solutions = _candidate_solutions(diagnostics)

    assert len(solutions) == 1
    assert solutions[0]["problem_class"] == "typescript_rootdir_drift"
    assert solutions[0]["diagnostic_count"] == 2
    assert "project references" in " ".join(solutions[0]["candidate_actions"]).lower()


def test_connected_map_candidate_file_limit_scales_with_graph_budget() -> None:
    assert (
        _connected_map_candidate_file_limit(
            max_files=4_000,
            max_connected_files=192,
            concrete_seed_count=0,
        )
        == 800
    )
    assert (
        _connected_map_candidate_file_limit(
            max_files=1_200,
            max_connected_files=400,
            concrete_seed_count=0,
        )
        == 1200
    )
    assert (
        _connected_map_candidate_file_limit(
            max_files=256,
            max_connected_files=32,
            concrete_seed_count=0,
        )
        == 256
    )
    assert (
        _connected_map_candidate_file_limit(
            max_files=6_000,
            max_connected_files=256,
            concrete_seed_count=4,
        )
        == 384
    )
    assert (
        _connected_map_candidate_file_limit(
            max_files=6_000,
            max_connected_files=256,
            concrete_seed_count=12,
        )
        == 256
    )


def test_store_probe_prepass_cache_retries_after_missing_tmp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "runtime" / "probe_prepass" / "cache.json"
    attempts = 0
    original_replace = Path.replace

    def _flaky_replace(self: Path, target: Path) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            self.unlink(missing_ok=True)
            raise FileNotFoundError(self)
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", _flaky_replace)

    _store_probe_prepass_cache(cache_path, {"schema_version": "repository-probe-prepass-v1"})

    assert attempts == 2
    assert cache_path.exists()


def test_load_snapshot_graph_summary_includes_symbol_risk_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "summary-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    helper_path = repo_path / "services" / "app" / "src" / "util.ts"
    target_path = repo_path / "services" / "app" / "src" / "main.ts"
    helper_path.write_text(
        "export function helper(): string {\n"
        "  return 'ready';\n"
        "}\n",
        encoding="utf-8",
    )
    target_path.write_text(
        "import { helper } from './util';\n"
        "\n"
        "export class Planner {\n"
        "  build(): string {\n"
        "    function finalize(value: string): string {\n"
        "      return `${helper()}-${value.toUpperCase()}`;\n"
        "    }\n"
        "    return finalize('ok');\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    connector = repository_service._InlineConnector(  # type: ignore[attr-defined]
        id=repository_service._coerce_scope_uuid("summary-repo"),  # type: ignore[attr-defined]
        org_id=repository_service._coerce_scope_uuid("summary-org"),  # type: ignore[attr-defined]
        connector_type=repository_service._InlineConnectorType("local_repo"),  # type: ignore[attr-defined]
    )
    connector = type(
        "Connector",
        (),
        {
            "id": connector.id,
            "org_id": connector.org_id,
            "owner_key_id": None,
            "connector_type": type("ConnectorType", (), {"value": "local_repo"})(),
            "config_json": '{"path": "' + str(repo_path) + '"}',
        },
    )()
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["services/app/src"],
            include_patterns=["services/**/*.ts"],
        ),
    )

    summary = _load_snapshot_graph_summary(
        repository_graph_path=snapshot.repository_graph_artifact.storage_path,
        dependency_graph_path=snapshot.dependency_graph_artifact.storage_path,
        symbol_graph_path=snapshot.symbol_graph_artifact.storage_path,
        seed_files=["services/app/src/main.ts"],
    )

    assert summary["parent_child_symbol_count"] >= 2
    assert summary["symbol_reference_edge_count"] >= 2
    assert summary["highest_change_risk_symbols"]
    assert summary["highest_change_risk_operational_symbols"]
    assert summary["highest_change_risk_operational_edges"]
    top_symbol = summary["highest_change_risk_operational_symbols"][0]
    assert top_symbol["symbol_name"] in {"Planner", "build", "finalize", "helper"}
    assert any(
        edge["target_symbol"] == "helper" for edge in summary["top_symbol_reference_edges"]
    )


def test_run_probe_persists_runtime_and_measures_warm_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = _typescript_rootdir_repo(tmp_path)
    _init_git_repo(repo_path)
    runtime_dir = tmp_path / "runtime"

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _probe_envelope(), {"execution_ms": 9}

    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
        ),
    )

    result = run_probe(
        repo_path=repo_path,
        focus_paths=["services/app"],
        diagnostic_command="cat diagnostics.txt # pnpm exec tsc -p tsconfig.test.json --noEmit",
        diagnostic_base_path="services/app",
        planner_model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        runtime_dir=runtime_dir,
        reuse_existing_state=False,
        max_files=256,
        max_file_size_bytes=100_000,
        max_total_bytes=2_000_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert result["runtime"]["persisted"] is True
    assert Path(result["runtime"]["repository_runtime_root"]).exists()
    assert result["prepass"]["cache_status"] == "miss_stored"
    assert result["prepass"]["cache_enabled"] is True
    assert result["snapshot"]["status"] == "created"
    assert result["snapshot"]["warm_status"] == "existing"
    assert result["graph_query"]["seed_file_paths"]
    assert result["graph_query"]["top_change_risk_files"]
    assert result["decision_plan"]["decision_plan"]["repository_analysis"]["planner_execution_mode"] == (
        "deterministic_local"
    )
    assert result["simulation"]["recommended_action"] == "apply_patch"
    assert result["apply_patch_only"]["mode"] == "patch_only"
    assert result["apply_patch_only"]["applied"] is False
    assert result["planner_status"] == "patch_only_completed"


def test_run_probe_reuses_git_prepass_cache_for_hot_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = _typescript_rootdir_repo(tmp_path)
    _init_git_repo(repo_path)
    runtime_dir = tmp_path / "runtime"
    command_calls = 0
    graph_calls = 0
    original_run_command = probe_module._run_command
    original_build_connected_dependency_map = probe_module._build_connected_dependency_map

    async def _fake_run_simulation_fast(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _probe_envelope(), {"execution_ms": 9}

    def _counting_run_command(repo_path: Path, command: str) -> dict[str, object]:
        nonlocal command_calls
        command_calls += 1
        return original_run_command(repo_path, command)

    def _counting_build_connected_dependency_map(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal graph_calls
        graph_calls += 1
        return original_build_connected_dependency_map(*args, **kwargs)

    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service,
        "get_policy",
        lambda _org_id: SimpleNamespace(
            snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0
        ),
    )
    monkeypatch.setattr(probe_module, "_run_command", _counting_run_command)
    monkeypatch.setattr(
        probe_module,
        "_build_connected_dependency_map",
        _counting_build_connected_dependency_map,
    )

    first = run_probe(
        repo_path=repo_path,
        focus_paths=["services/app"],
        diagnostic_command="cat diagnostics.txt # pnpm exec tsc -p tsconfig.test.json --noEmit",
        diagnostic_base_path="services/app",
        planner_model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        runtime_dir=runtime_dir,
        reuse_existing_state=False,
        max_files=256,
        max_file_size_bytes=100_000,
        max_total_bytes=2_000_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )
    second = run_probe(
        repo_path=repo_path,
        focus_paths=["services/app"],
        diagnostic_command="cat diagnostics.txt # pnpm exec tsc -p tsconfig.test.json --noEmit",
        diagnostic_base_path="services/app",
        planner_model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        runtime_dir=runtime_dir,
        reuse_existing_state=True,
        max_files=256,
        max_file_size_bytes=100_000,
        max_total_bytes=2_000_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert first["prepass"]["cache_status"] == "miss_stored"
    assert second["prepass"]["cache_status"] == "hit"
    assert second["snapshot"]["status"] == "existing"
    assert second["graph_query"]["top_change_risk_files"]
    assert second["diagnostic_command"]["elapsed_ms"] == 0.0
    assert second["diagnostic_command"]["cached_elapsed_ms"] is not None
    assert command_calls == 1
    assert graph_calls == 1
