"""Tests for repository_intelligence_service: repository_snapshot_e.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_graph_contains_php_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "php-dependency-repo"
    (repo_path / "app" / "Models").mkdir(parents=True)
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "app" / "Models" / "User.php").write_text("<?php\n", encoding="utf-8")
    (repo_path / "public" / "index.php").write_text(
        "<?php\nuse App\\\\Models\\\\User;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["app", "public"],
            include_patterns=["app/**/*.php", "public/*.php", "public/**/*.php"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:public/index.php"
        and str(row["target_node"]) == "file:app/Models/User.php"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_php_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "php-symbol-repo"
    (repo_path / "app" / "Models").mkdir(parents=True)
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "app" / "Models" / "User.php").write_text(
        "<?php\n"
        "namespace App\\Models;\n"
        "class User {\n"
        "    public static function make(): User {\n"
        "        return new User();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "public" / "index.php").write_text(
        "<?php\n"
        "namespace App;\n"
        "use App\\Models\\User;\n"
        "class Entry {\n"
        "    public function run(): User {\n"
        "        return User::make();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["app", "public"],
            include_patterns=["app/**/*.php", "public/*.php", "public/**/*.php"],
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

    run_symbol_id = symbol_ids[("public/index.php", "run")]
    make_symbol_id = symbol_ids[("app/Models/User.php", "make")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{make_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_deduplicates_resolved_php_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "php-dedup-symbol-repo"
    (repo_path / "app" / "Models").mkdir(parents=True)
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "app" / "Models" / "User.php").write_text(
        "<?php\n"
        "namespace App\\Models;\n"
        "class User {}\n",
        encoding="utf-8",
    )
    (repo_path / "public" / "index.php").write_text(
        "<?php\n"
        "namespace App;\n"
        "use App\\Models\\User;\n"
        "class Entry {\n"
        "    public function run(): array {\n"
        "        return [User::ADMIN, User::MEMBER];\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["app", "public"],
            include_patterns=["app/**/*.php", "public/*.php", "public/**/*.php"],
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

    run_symbol_id = symbol_ids[("public/index.php", "run")]
    user_symbol_id = symbol_ids[("app/Models/User.php", "User")]
    matching_edges = [
        row
        for row in graph_rows
        if str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{user_symbol_id}"
    ]
    assert len(matching_edges) == 1


def test_repository_snapshot_graph_contains_php_trait_docblock_and_type_hint_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "php-rich-symbol-repo"
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["app", "database"],
            include_patterns=["app/**/*.php", "database/**/*.php"],
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

    audited_user_symbol_id = symbol_ids[("app/Models/AuditedUser.php", "AuditedUser")]
    user_symbol_id = symbol_ids[("app/Models/User.php", "User")]
    has_audit_symbol_id = symbol_ids[("app/Traits/HasAudit.php", "HasAudit")]
    user_factory_symbol_id = symbol_ids[
        ("database/Factories/UserFactory.php", "UserFactory")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{audited_user_symbol_id}"
        and str(row["target_node"]) == f"symbol:{user_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{audited_user_symbol_id}"
        and str(row["target_node"]) == f"symbol:{has_audit_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{audited_user_symbol_id}"
        and str(row["target_node"]) == f"symbol:{user_factory_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_elixir_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "elixir-dependency-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "lib" / "acme" / "repo.ex").write_text("defmodule Acme.Repo do\nend\n", encoding="utf-8")
    (repo_path / "lib" / "acme.ex").write_text(
        "defmodule Acme do\n  alias Acme.Repo\nend\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=["lib/*.ex", "lib/**/*.ex"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:lib/acme.ex"
        and str(row["target_node"]) == "file:lib/acme/repo.ex"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_elixir_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "elixir-symbol-graph-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "lib" / "acme" / "repo.ex").write_text(
        "defmodule Acme.Repo do\n"
        "  def format_value do\n"
        "    :ok\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme.ex").write_text(
        "defmodule Acme do\n"
        "  alias Acme.Repo\n"
        "\n"
        "  def run do\n"
        "    Repo.format_value()\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=["lib/*.ex", "lib/**/*.ex"],
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

    run_symbol_id = symbol_ids[("lib/acme.ex", "run")]
    format_value_symbol_id = symbol_ids[("lib/acme/repo.ex", "format_value")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{format_value_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_grouped_elixir_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "elixir-grouped-dependency-repo"
    (repo_path / "lib" / "phx_new").mkdir(parents=True)
    (repo_path / "lib" / "mix" / "tasks").mkdir(parents=True)
    (repo_path / "lib" / "phx_new" / "generator.ex").write_text(
        "defmodule Phx.New.Generator do\nend\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "mix" / "tasks" / "phx.new.ex").write_text(
        "defmodule Mix.Tasks.Phx.New do\n"
        "  alias Phx.New.{Generator}\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=["lib/**/*.ex"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:lib/mix/tasks/phx.new.ex"
        and str(row["target_node"]) == "file:lib/phx_new/generator.ex"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_csharp_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "csharp-dependency-repo"
    (repo_path / "src" / "MediatR").mkdir(parents=True)
    (repo_path / "src" / "MediatR" / "Mediator.cs").write_text(
        "namespace MediatR; public sealed class Mediator {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "MediatR" / "Handler.cs").write_text(
        "using MediatR;\nnamespace MediatR; public sealed class Handler { private readonly Mediator _m = new(); }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.cs"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/MediatR/Handler.cs"
        and str(row["target_node"]).startswith("file:src/MediatR/")
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_csharp_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "csharp-symbol-repo"
    (repo_path / "src" / "MediatR").mkdir(parents=True)
    (repo_path / "src" / "MediatR" / "Mediator.cs").write_text(
        "namespace MediatR; public sealed class Mediator {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "MediatR" / "Handler.cs").write_text(
        "using MediatR;\n"
        "namespace MediatR; public sealed class Handler { private readonly Mediator _m = new(); }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.cs"],
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

    handler_symbol_id = symbol_ids[("src/MediatR/Handler.cs", "Handler")]
    mediator_symbol_id = symbol_ids[("src/MediatR/Mediator.cs", "Mediator")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{handler_symbol_id}"
        and str(row["target_node"]) == f"symbol:{mediator_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_visual_basic_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "visual-basic-repo"
    (repo_path / "src" / "Acme").mkdir(parents=True)
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.vb"],
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
        and str(row["source_node"]) == "file:src/Acme/Handler.vb"
        and str(row["target_node"]) == "file:src/Acme/Mediator.vb"
        for row in graph_rows
    )
    handler_symbol_id = symbol_ids[("src/Acme/Handler.vb", "Handler")]
    mediator_symbol_id = symbol_ids[("src/Acme/Mediator.vb", "Mediator")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{handler_symbol_id}"
        and str(row["target_node"]) == f"symbol:{mediator_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_ada_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ada-dependency-repo"
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "alire.toml"],
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
        and str(row["source_node"]) == "file:src/main.adb"
        and str(row["target_node"]) == "file:src/acme-util.adb"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/main.adb", "Main")]
    helper_symbol_id = symbol_ids[("src/acme-util.adb", "Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_cobol_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cobol-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "copybooks").mkdir(parents=True)
    (repo_path / "copybooks" / "PERSON-REC.cpy").write_text(
        "       01 PERSON-REC.\n"
        "          05 PERSON-ID PIC 9(4).\n",
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "copybooks"],
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
        and str(row["source_node"]) == "file:src/MAINAPP.cbl"
        and str(row["target_node"]) == "file:copybooks/PERSON-REC.cpy"
        for row in graph_rows
    )
    main_para_symbol_id = symbol_ids[("src/MAINAPP.cbl", "main-para")]
    utils_symbol_id = symbol_ids[("src/UTILS.cbl", "utils")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_para_symbol_id}"
        and str(row["target_node"]) == f"symbol:{utils_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_plsql_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "plsql-dependency-repo"
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["db"],
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
        and str(row["source_node"]) == "file:db/order_api.pkb"
        and str(row["target_node"]) == "file:db/order_api.pks"
        for row in graph_rows
    )
    submit_order_symbol_id = symbol_ids[("db/order_api.pkb", "submit_order")]
    record_order_symbol_id = symbol_ids[("db/app_util.pks", "record_order")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{submit_order_symbol_id}"
        and str(row["target_node"]) == f"symbol:{record_order_symbol_id}"
        for row in graph_rows
    )


