"""Tests for repository_intelligence_service: repository_snapshot_d.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_graph_contains_nim_plain_import_and_same_file_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "nim-symbol-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "acme.nimble").write_text("version = \"0.1.0\"\n", encoding="utf-8")
    (repo_path / "src" / "acme" / "util.nim").write_text(
        "proc helper*(): string =\n"
        "  \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.nim").write_text(
        "import acme/util\n"
        "proc localHelper*(): string =\n"
        "  \"local\"\n"
        "proc wrap*(): string =\n"
        "  helper()\n"
        "proc run*(): string =\n"
        "  localHelper()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.nim", "*.nimble", "config.nims"],
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

    wrap_symbol_id = symbol_ids[("src/acme.nim", "wrap")]
    run_symbol_id = symbol_ids[("src/acme.nim", "run")]
    helper_symbol_id = symbol_ids[("src/acme/util.nim", "helper")]
    local_helper_symbol_id = symbol_ids[("src/acme.nim", "localHelper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{wrap_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{local_helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_ocaml_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ocaml-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "dune-project").write_text("(lang dune 3.0)\n", encoding="utf-8")
    (repo_path / "src" / "util.ml").write_text(
        "let helper () = 1\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.ml").write_text(
        "let run () = Util.helper ()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.ml", "src/*.ml", "dune-project", "**/dune", "*.opam"],
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

    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:src/main.ml"
        and str(row["target_node"]) == "file:src/util.ml"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/main.ml", "run")]
    helper_symbol_id = symbol_ids[("src/util.ml", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_perl_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "perl-dependency-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "cpanfile").write_text("requires 'strict';\n", encoding="utf-8")
    (repo_path / "lib" / "My" / "Util.pm").write_text(
        "package My::Util;\n"
        "sub helper { 1 }\n"
        "1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\n"
        "use My::Util;\n"
        "sub run { My::Util->helper() }\n"
        "1;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=[
                "lib/**/*.pm",
                "lib/*.pm",
                "cpanfile",
                "Makefile.PL",
                "Build.PL",
                "dist.ini",
            ],
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

    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:lib/My/Main.pm"
        and str(row["target_node"]) == "file:lib/My/Util.pm"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("lib/My/Main.pm", "run")]
    helper_symbol_id = symbol_ids[("lib/My/Util.pm", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_perl_imported_call_and_parent_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "perl-imported-call-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "cpanfile").write_text("requires 'strict';\n", encoding="utf-8")
    (repo_path / "lib" / "My" / "Base.pm").write_text(
        "package My::Base;\n"
        "sub parent_method { 1 }\n"
        "1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Util.pm").write_text(
        "package My::Util;\n"
        "sub helper { 1 }\n"
        "1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\n"
        "use parent 'My::Base';\n"
        "use My::Util qw(helper);\n"
        "sub run { helper() }\n"
        "1;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=[
                "lib/**/*.pm",
                "lib/*.pm",
                "cpanfile",
                "Makefile.PL",
                "Build.PL",
                "dist.ini",
            ],
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

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:lib/My/Main.pm"
        and str(row["target_node"]) == "file:lib/My/Base.pm"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:lib/My/Main.pm"
        and str(row["target_node"]) == "file:lib/My/Util.pm"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("lib/My/Main.pm", "run")]
    helper_symbol_id = symbol_ids[("lib/My/Util.pm", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_r_package_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "r-package-graph-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    (repo_path / "R" / "helper.R").write_text(
        "helper <- function() {\n"
        "  1\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "main.R").write_text(
        "run <- function() {\n"
        "  helper()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["R", "DESCRIPTION", "NAMESPACE"],
            include_patterns=["R/**/*.R", "R/*.R", "DESCRIPTION", "NAMESPACE"],
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

    run_symbol_id = symbol_ids[("R/main.R", "run")]
    helper_symbol_id = symbol_ids[("R/helper.R", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_ignores_r_builtin_collisions_for_unqualified_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "r-package-builtins-graph-repo"
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["R", "DESCRIPTION", "NAMESPACE"],
            include_patterns=["R/**/*.R", "R/*.R", "DESCRIPTION", "NAMESPACE"],
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

    run_symbol_id = symbol_ids[("R/main.R", "run")]
    helper_symbol_id = symbol_ids[("R/helper.R", "helper")]
    builtin_shadow_symbol_id = symbol_ids[("R/builtin-shadow.R", "names")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert not any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{builtin_shadow_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_julia_include_and_import_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "julia-package-graph-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project.toml").write_text(
        'name = "Acme"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.jl").write_text(
        "module Helper\n"
        "helper() = 1\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme.jl").write_text(
        'module Acme\ninclude("Helper.jl")\nusing .Helper: helper\n\nfunction run()\n'
        "  helper()\n"
        "end\nend\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "Project.toml"],
            include_patterns=["src/**/*.jl", "src/*.jl", "Project.toml"],
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

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/Acme.jl"
        and str(row["target_node"]) == "file:src/Helper.jl"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/Acme.jl", "run")]
    helper_symbol_id = symbol_ids[("src/Helper.jl", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_julia_package_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "julia-package-symbol-graph-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project.toml").write_text(
        'name = "Acme"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.jl").write_text(
        "helper() = 1\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Runner.jl").write_text(
        "run() = helper()\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme.jl").write_text(
        'module Acme\ninclude("Helper.jl")\ninclude("Runner.jl")\nend\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "Project.toml"],
            include_patterns=["src/**/*.jl", "src/*.jl", "Project.toml"],
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

    run_symbol_id = symbol_ids[("src/Runner.jl", "run")]
    helper_symbol_id = symbol_ids[("src/Helper.jl", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_ignores_julia_constructor_calls_for_operational_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "julia-package-constructor-graph-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project.toml").write_text(
        'name = "Acme"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Types.jl").write_text(
        "struct HelperType\n  value::Int\nend\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Runner.jl").write_text(
        "make_type() = HelperType(1)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme.jl").write_text(
        'module Acme\ninclude("Types.jl")\ninclude("Runner.jl")\nend\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "Project.toml"],
            include_patterns=["src/**/*.jl", "src/*.jl", "Project.toml"],
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

    make_type_symbol_id = symbol_ids[("src/Runner.jl", "make_type")]
    helper_type_symbol_id = symbol_ids[("src/Types.jl", "HelperType")]
    assert not any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{make_type_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_type_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_crystal_wildcard_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "crystal-dependency-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shard.yml").write_text(
        "name: acme\nversion: 0.1.0\n",
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
    (repo_path / "src" / "acme.cr").write_text(
        'require "./acme/*"\n\n'
        "module Acme\n"
        "  def self.run : Int32\n"
        "    Acme::Helper.helper\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "shard.yml"],
            include_patterns=["src/**/*.cr", "src/*.cr", "shard.yml"],
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

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/acme.cr"
        and str(row["target_node"]) == "file:src/acme/helper.cr"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/acme.cr", "run")]
    helper_symbol_id = symbol_ids[("src/acme/helper.cr", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_crystal_constructor_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "crystal-constructor-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shard.yml").write_text(
        "name: acme\nversion: 0.1.0\n",
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
        "  class Runner\n"
        "    def initialize(options : Options)\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.cr").write_text(
        'require "./acme/*"\n\n'
        "module Acme\n"
        "  def self.build : Runner\n"
        "    Runner.new(Options.new)\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "shard.yml"],
            include_patterns=["src/**/*.cr", "src/*.cr", "shard.yml"],
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

    build_symbol_id = symbol_ids[("src/acme.cr", "build")]
    options_symbol_id = symbol_ids[("src/acme/options.cr", "Options")]
    runner_symbol_id = symbol_ids[("src/acme/runner.cr", "Runner")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{options_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{runner_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_crystal_type_annotation_and_mixin_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "crystal-type-annotation-repo"
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "shard.yml"],
            include_patterns=["src/**/*.cr", "src/*.cr", "shard.yml"],
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

    runner_symbol_id = symbol_ids[("src/acme/runner.cr", "Runner")]
    initialize_symbol_id = symbol_ids[("src/acme/runner.cr", "initialize")]
    base_runner_symbol_id = symbol_ids[("src/acme/base_runner.cr", "BaseRunner")]
    serializable_symbol_id = symbol_ids[("src/acme/serializable.cr", "Serializable")]
    options_symbol_id = symbol_ids[("src/acme/options.cr", "Options")]

    for target_symbol_id in (base_runner_symbol_id, serializable_symbol_id):
        assert any(
            str(row["edge_type"]) == "references_symbol"
            and str(row["source_node"]) == f"symbol:{runner_symbol_id}"
            and str(row["target_node"]) == f"symbol:{target_symbol_id}"
            for row in graph_rows
        )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{initialize_symbol_id}"
        and str(row["target_node"]) == f"symbol:{options_symbol_id}"
        for row in graph_rows
    )


