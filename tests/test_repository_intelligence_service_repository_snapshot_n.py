"""Tests for repository_intelligence_service: repository_snapshot_n.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_graph_contains_groovy_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "groovy-symbol-repo"
    source_dir = repo_path / "src" / "main" / "groovy" / "org" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "Owner.groovy").write_text(
        "package org.example\n"
        "class Owner {}\n",
        encoding="utf-8",
    )
    (source_dir / "OwnerController.groovy").write_text(
        "package org.example\n"
        "import org.example.Owner as PetOwner\n"
        "class OwnerController {\n"
        "  PetOwner owner\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/groovy"],
            include_patterns=["src/main/groovy/**/*.groovy"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    controller_symbol_id = symbol_ids[
        ("src/main/groovy/org/example/OwnerController.groovy", "OwnerController")
    ]
    owner_symbol_id = symbol_ids[("src/main/groovy/org/example/Owner.groovy", "Owner")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{controller_symbol_id}"
        and str(row["target_node"]) == f"symbol:{owner_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_haskell_module_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "haskell-module-repo"
    source_dir = repo_path / "src" / "Text"
    legacy_dir = source_dir / "ParserCombinators"
    legacy_dir.mkdir(parents=True)
    (repo_path / "parsec.cabal").write_text(
        "name: parsec\n"
        "version: 1.0.0.0\n"
        "library\n"
        "  hs-source-dirs: src\n"
        "  exposed-modules: Text.Parsec, Text.ParserCombinators.Parsec\n",
        encoding="utf-8",
    )
    (source_dir / "Parsec.hs").write_text(
        "module Text.Parsec where\n"
        "data Parser = Parser\n"
        'instance Show Parser where show _ = "Parser"\n',
        encoding="utf-8",
    )
    (legacy_dir / "Parsec.hs").write_text(
        "module Text.ParserCombinators.Parsec where\n"
        "import qualified Text.Parsec as P\n"
        "parser :: P.Parser\n"
        "parser = P.Parser\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.hs", "*.cabal"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    parser_symbol_id = symbol_ids[("src/Text/ParserCombinators/Parsec.hs", "parser")]
    data_symbol_id = symbol_ids[("src/Text/Parsec.hs", "Parser")]

    assert ("src/Text/Parsec.hs", "instance") not in symbol_ids
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/Text/ParserCombinators/Parsec.hs"
        and str(row["target_node"]) == "file:src/Text/Parsec.hs"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{parser_symbol_id}"
        and str(row["target_node"]) == f"symbol:{data_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_haskell_unqualified_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "haskell-unqualified-symbol-repo"
    source_dir = repo_path / "src" / "Text"
    source_dir.mkdir(parents=True)
    (repo_path / "sample.cabal").write_text(
        "name: sample\n"
        "version: 1.0.0.0\n"
        "library\n"
        "  hs-source-dirs: src\n"
        "  exposed-modules: Text.Foo, Text.Bar\n",
        encoding="utf-8",
    )
    (source_dir / "Foo.hs").write_text(
        "module Text.Foo where\n"
        "data Parser = Parser\n"
        "render :: Parser -> String\n"
        'render _ = "ok"\n',
        encoding="utf-8",
    )
    (source_dir / "Bar.hs").write_text(
        "module Text.Bar where\n"
        "import Text.Foo\n"
        "useParser :: Parser -> String\n"
        "useParser input = render input\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.hs", "*.cabal"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    use_parser_symbol_id = symbol_ids[("src/Text/Bar.hs", "useParser")]
    parser_symbol_id = symbol_ids[("src/Text/Foo.hs", "Parser")]
    render_symbol_id = symbol_ids[("src/Text/Foo.hs", "render")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{use_parser_symbol_id}"
        and str(row["target_node"]) == f"symbol:{parser_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{use_parser_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_ignores_haskell_local_bindings_as_top_level_symbols(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "haskell-local-binding-repo"
    source_dir = repo_path / "src" / "Text"
    source_dir.mkdir(parents=True)
    (repo_path / "sample.cabal").write_text(
        "name: sample\n"
        "version: 1.0.0.0\n"
        "library\n"
        "  hs-source-dirs: src\n"
        "  exposed-modules: Text.Local\n",
        encoding="utf-8",
    )
    (source_dir / "Local.hs").write_text(
        "module Text.Local where\n"
        "render :: Int -> Int\n"
        "render value =\n"
        "  let go inner = inner + 1\n"
        "  in go value\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.hs", "*.cabal"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_names = {
        (str(row["file_path"]), str(row["symbol_name"]))
        for row in symbol_rows
    }
    assert ("src/Text/Local.hs", "render") in symbol_names
    assert ("src/Text/Local.hs", "go") not in symbol_names


def test_repository_snapshot_graph_contains_zig_build_module_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "zig-build-module-repo"
    source_dir = repo_path / "src"
    source_dir.mkdir(parents=True)
    (repo_path / "build.zig").write_text(
        'const std = @import("std");\n'
        "pub fn build(b: *std.Build) void {\n"
        '  _ = b.addModule("acme", .{\n'
        '    .root_source_file = b.path("src/root.zig"),\n'
        "  });\n"
        "}\n",
        encoding="utf-8",
    )
    (source_dir / "root.zig").write_text(
        "pub const Answer = 42;\n",
        encoding="utf-8",
    )
    (source_dir / "main.zig").write_text(
        'const acme = @import("acme");\n'
        "pub fn main() void {\n"
        "  _ = acme.Answer;\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.zig"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    main_symbol_id = symbol_ids[("src/main.zig", "main")]
    answer_symbol_id = symbol_ids[("src/root.zig", "Answer")]

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.zig"
        and str(row["target_node"]) == "file:src/root.zig"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{answer_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_swift_same_target_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "swift-dependency-repo"
    target_dir = repo_path / "Sources" / "Acme"
    target_dir.mkdir(parents=True)
    (target_dir / "Documentation.docc").mkdir(parents=True)
    (target_dir / "CommandConfiguration.swift").write_text(
        "struct CommandConfiguration {}\n",
        encoding="utf-8",
    )
    (target_dir / "Documentation.docc" / "CommandConfiguration.md").write_text(
        "# docs\n",
        encoding="utf-8",
    )
    (target_dir / "ParsableCommand.swift").write_text(
        "protocol ParsableCommand {\n"
        "  static var configuration: CommandConfiguration { get }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Sources"],
            include_patterns=["Sources/**/*.swift"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:Sources/Acme/ParsableCommand.swift"
        and str(row["target_node"]) == "file:Sources/Acme/CommandConfiguration.swift"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_swift_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "swift-symbol-repo"
    target_dir = repo_path / "Sources" / "Acme"
    target_dir.mkdir(parents=True)
    (target_dir / "CommandConfiguration.swift").write_text(
        "struct CommandConfiguration {}\n",
        encoding="utf-8",
    )
    (target_dir / "ParsableCommand.swift").write_text(
        "protocol ParsableCommand {\n"
        "  static var configuration: CommandConfiguration { get }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Sources"],
            include_patterns=["Sources/**/*.swift"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    command_symbol_id = symbol_ids[("Sources/Acme/ParsableCommand.swift", "ParsableCommand")]
    configuration_symbol_id = symbol_ids[
        ("Sources/Acme/CommandConfiguration.swift", "CommandConfiguration")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{command_symbol_id}"
        and str(row["target_node"]) == f"symbol:{configuration_symbol_id}"
        for row in graph_rows
    )


