from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_blade_parser_dispatch as repository_blade_parser_dispatch,
)
from apps.api_server.services import repository_intelligence_file_selection
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    blade_analysis_support as repository_blade_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    blade_primitives as repository_blade_primitives,
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


def test_repository_intelligence_blade_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["blade"] is (
        repository_blade_parser_dispatch._parse_blade_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["blade"] is (
        repository_blade_parser_dispatch._parse_blade_dependencies_only
    )


def test_repository_intelligence_blade_helpers_are_modularized() -> None:
    assert repository_service.blade_adapter.strip_comments is repository_blade_primitives.strip_comments
    assert repository_service.blade_adapter.has_blade_path_hints is (
        repository_blade_primitives.has_blade_path_hints
    )
    assert repository_service.blade_adapter.iter_dependency_entries is (
        repository_blade_primitives.iter_dependency_entries
    )
    assert repository_service.blade_adapter.iter_reference_entries is (
        repository_blade_primitives.iter_reference_entries
    )
    assert repository_service.blade_adapter.resolve_import is (
        repository_blade_primitives.resolve_import
    )
    assert repository_service.blade_adapter.is_probable_blade_source is (
        repository_blade_analysis_support.is_probable_blade_source
    )
    assert repository_service.blade_adapter.module_aliases_for_path is (
        repository_blade_analysis_support.module_aliases_for_path
    )
    assert repository_service.blade_adapter.parse_dependencies_only is (
        repository_blade_analysis_support.parse_dependencies_only
    )
    assert repository_service.blade_adapter.parse_file is (
        repository_blade_analysis_support.parse_file
    )


def test_blade_adapter_module_aliases_include_view_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "blade-alias-repo"
    (repo_path / "resources" / "views" / "layouts").mkdir(parents=True)
    (repo_path / "resources" / "views" / "layouts" / "app.blade.php").write_text(
        "<html><body>@yield('content')</body></html>\n",
        encoding="utf-8",
    )

    aliases = repository_service.blade_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="resources/views/layouts/app.blade.php",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "resources/views/layouts/app.blade.php" in aliases
    assert "resources/views/layouts/app" in aliases
    assert "layouts.app" in aliases


def test_blade_adapter_parse_file_resolves_template_dependencies_and_section_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "blade-parse-repo"
    (repo_path / "resources" / "views" / "layouts").mkdir(parents=True)
    (repo_path / "resources" / "views" / "partials").mkdir(parents=True)
    (repo_path / "resources" / "views" / "components").mkdir(parents=True)
    (repo_path / "resources" / "views" / "layouts" / "app.blade.php").write_text(
        "<html><body>@yield('content')</body></html>\n",
        encoding="utf-8",
    )
    (repo_path / "resources" / "views" / "partials" / "card.blade.php").write_text(
        "<article>{{ $title }}</article>\n",
        encoding="utf-8",
    )
    (repo_path / "resources" / "views" / "components" / "alert.blade.php").write_text(
        "<div>{{ $slot }}</div>\n",
        encoding="utf-8",
    )
    (repo_path / "resources" / "views" / "home.blade.php").write_text(
        "@extends('layouts.app')\n"
        "@section('content')\n"
        "  @include('partials.card')\n"
        "  @yield('content')\n"
        "  <x-alert />\n"
        "@endsection\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "resources/views/layouts/app.blade.php",
            "resources/views/partials/card.blade.php",
            "resources/views/components/alert.blade.php",
            "resources/views/home.blade.php",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "resources" / "views" / "home.blade.php").read_text(encoding="utf-8")

    dependencies = repository_service.blade_adapter.parse_dependencies_only(
        "resources/views/home.blade.php",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.blade_adapter.parse_file(
        "resources/views/home.blade.php",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "resources/views/layouts/app.blade.php"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "resources/views/partials/card.blade.php"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "resources/views/components/alert.blade.php"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "home" for symbol in symbols)
    assert any(symbol.symbol_name == "content" for symbol in symbols)
    assert any(
        reference.target_file == "resources/views/layouts/app.blade.php"
        and "layouts.app" in reference.target_names
        for reference in references
    )
    assert any(
        reference.target_file == "resources/views/home.blade.php"
        and reference.target_names == ("content",)
        for reference in references
    )


def test_blade_language_detection_supports_blade_php_suffix() -> None:
    assert ".php" in repository_intelligence_file_selection.TEXT_FILE_SUFFIXES

    assert repository_service._language_for_path(
        Path("resources/views/home.blade.php"),
        text="<h1>{{ $title }}</h1>\n",
    ) == "blade"


def test_operational_seed_plan_without_diagnostics_promotes_blade_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "blade-profile-repo"
    (repo_path / "resources" / "views" / "layouts").mkdir(parents=True)
    (repo_path / "resources" / "views" / "partials").mkdir(parents=True)
    (repo_path / "resources" / "views" / "layouts" / "app.blade.php").write_text(
        "<html><body>@yield('content')</body></html>\n",
        encoding="utf-8",
    )
    (repo_path / "resources" / "views" / "partials" / "card.blade.php").write_text(
        "<article>{{ $title }}</article>\n",
        encoding="utf-8",
    )
    (repo_path / "resources" / "views" / "welcome.blade.php").write_text(
        "@extends('layouts.app')\n@include('partials.card')\n@section('content')Hello@endsection\n",
        encoding="utf-8",
    )
    (repo_path / "routes").mkdir(parents=True)
    (repo_path / "routes" / "web.php").write_text(
        "<?php\nRoute::view('/', 'welcome');\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "blade" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "blade"
    assert any(path.endswith(".blade.php") for path in seed_plan["candidate_file_paths"])
    assert any(root.startswith("resources/views") for root in seed_plan["support_roots"])


def test_operational_seed_plan_without_diagnostics_does_not_force_blade_first_in_php_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "blade-mixed-php-repo"
    (repo_path / "resources" / "views").mkdir(parents=True)
    (repo_path / "resources" / "views" / "home.blade.php").write_text(
        "<h1>{{ $title }}</h1>\n",
        encoding="utf-8",
    )
    (repo_path / "app").mkdir(parents=True)
    for index in range(24):
        (repo_path / "app" / f"Controller{index}.php").write_text(
            f"<?php\nfunction demo_controller_{index}() {{ return 'ok'; }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "blade" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "blade"
    assert "php" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_blade_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "blade-graph-repo"
    (repo_path / "resources" / "views" / "layouts").mkdir(parents=True)
    (repo_path / "resources" / "views" / "partials").mkdir(parents=True)
    (repo_path / "resources" / "views" / "layouts" / "app.blade.php").write_text(
        "<html><body>@yield('content')</body></html>\n",
        encoding="utf-8",
    )
    (repo_path / "resources" / "views" / "partials" / "card.blade.php").write_text(
        "<article>{{ $title }}</article>\n",
        encoding="utf-8",
    )
    (repo_path / "resources" / "views" / "home.blade.php").write_text(
        "@extends('layouts.app')\n"
        "@section('content')\n"
        "  @include('partials.card')\n"
        "  @yield('content')\n"
        "@endsection\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=[
                "*.blade.php",
                "resources/views/**/*.blade.php",
                "resources/views/*.blade.php",
            ],
            max_files=16,
        ),
    )
    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "template"
        and str(row["source_node"]) == "file:resources/views/home.blade.php"
        and str(row["target_node"]) == "file:resources/views/layouts/app.blade.php"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "template"
        and str(row["target_node"]) == "file:resources/views/partials/card.blade.php"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"])
        == f"symbol:{symbol_ids[('resources/views/home.blade.php', 'home')]}"
        and str(row["target_node"])
        == f"symbol:{symbol_ids[('resources/views/layouts/app.blade.php', 'layouts.app')]}"
        for row in graph_rows
    )
