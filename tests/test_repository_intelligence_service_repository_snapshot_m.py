"""Tests for repository_intelligence_service: repository_snapshot_m.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_graph_contains_assembly_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "assembly-dependency-repo"
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "include"],
            include_patterns=[
                "src/**/*.asm",
                "src/*.asm",
                "include/**/*.inc",
                "include/*.inc",
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
        and str(row["source_node"]) == "file:src/main.asm"
        and str(row["target_node"]) == "file:include/io.inc"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/main.asm", "main")]
    print_string_symbol_id = symbol_ids[("src/io.asm", "print_string")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{print_string_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_sql_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "sql-dependency-repo"
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
        "select * from {{ ref('customers') }}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["models", "dbt_project.yml"],
            include_patterns=["models/**/*.sql", "models/*.sql", "dbt_project.yml"],
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
        and str(row["source_node"]) == "file:models/orders.sql"
        and str(row["target_node"]) == "file:models/customers.sql"
        for row in graph_rows
    )

    orders_symbol_id = symbol_ids[("models/orders.sql", "orders")]
    customers_symbol_id = symbol_ids[("models/customers.sql", "customers")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{orders_symbol_id}"
        and str(row["target_node"]) == f"symbol:{customers_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_tsql_execute_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "tsql-dependency-repo"
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["database"],
            include_patterns=["database/**/*.sql", "database/*.sql", "database/*.sqlproj"],
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
        and str(row["source_node"]) == "file:database/dbo/Stored Procedures/LoadOrders.sql"
        and str(row["target_node"])
        == "file:database/dbo/Stored Procedures/LoadCustomers.sql"
        for row in graph_rows
    )

    orders_symbol_id = symbol_ids[
        ("database/dbo/Stored Procedures/LoadOrders.sql", "loadorders")
    ]
    customers_symbol_id = symbol_ids[
        ("database/dbo/Stored Procedures/LoadCustomers.sql", "loadcustomers")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{orders_symbol_id}"
        and str(row["target_node"]) == f"symbol:{customers_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_csharp_same_namespace_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "csharp-same-namespace-repo"
    (repo_path / "src" / "MediatR").mkdir(parents=True)
    (repo_path / "src" / "MediatR" / "IMediator.cs").write_text(
        "namespace MediatR; public interface IMediator {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "MediatR" / "Mediator.cs").write_text(
        "namespace MediatR; public class Mediator : IMediator {}\n",
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
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:src/MediatR/Mediator.cs"
        and str(row["target_node"]) == "file:src/MediatR/IMediator.cs"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_java_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "java-dependency-repo"
    package_dir = repo_path / "src" / "main" / "java" / "org" / "example"
    package_dir.mkdir(parents=True)
    (package_dir / "Owner.java").write_text(
        "package org.example;\npublic class Owner {}\n",
        encoding="utf-8",
    )
    (package_dir / "OwnerController.java").write_text(
        "package org.example;\nimport org.example.Owner;\npublic class OwnerController { private Owner owner; }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/java"],
            include_patterns=["src/main/java/**/*.java"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main/java/org/example/OwnerController.java"
        and str(row["target_node"]) == "file:src/main/java/org/example/Owner.java"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_java_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "java-symbol-repo"
    package_dir = repo_path / "src" / "main" / "java" / "org" / "example"
    package_dir.mkdir(parents=True)
    (package_dir / "Owner.java").write_text(
        "package org.example;\npublic class Owner {}\n",
        encoding="utf-8",
    )
    (package_dir / "OwnerController.java").write_text(
        "package org.example;\n"
        "import org.example.Owner;\n"
        "public class OwnerController { private Owner owner; }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/java"],
            include_patterns=["src/main/java/**/*.java"],
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
        ("src/main/java/org/example/OwnerController.java", "OwnerController")
    ]
    owner_symbol_id = symbol_ids[("src/main/java/org/example/Owner.java", "Owner")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{controller_symbol_id}"
        and str(row["target_node"]) == f"symbol:{owner_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_kotlin_same_package_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "kotlin-dependency-repo"
    package_dir = repo_path / "src" / "main" / "kotlin" / "com" / "example"
    package_dir.mkdir(parents=True)
    (package_dir / "BlogProperties.kt").write_text(
        "package com.example\n"
        "data class BlogProperties(val title: String)\n",
        encoding="utf-8",
    )
    (package_dir / "BlogConfiguration.kt").write_text(
        "package com.example\n"
        "class BlogConfiguration(private val properties: BlogProperties)\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/kotlin"],
            include_patterns=["src/main/kotlin/**/*.kt"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:src/main/kotlin/com/example/BlogConfiguration.kt"
        and str(row["target_node"]) == "file:src/main/kotlin/com/example/BlogProperties.kt"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_kotlin_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "kotlin-symbol-repo"
    package_dir = repo_path / "src" / "main" / "kotlin" / "com" / "example"
    package_dir.mkdir(parents=True)
    (package_dir / "BlogProperties.kt").write_text(
        "package com.example\n"
        "data class BlogProperties(val title: String)\n",
        encoding="utf-8",
    )
    (package_dir / "BlogConfiguration.kt").write_text(
        "package com.example\n"
        "class BlogConfiguration(private val properties: BlogProperties)\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/kotlin"],
            include_patterns=["src/main/kotlin/**/*.kt"],
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

    config_symbol_id = symbol_ids[
        ("src/main/kotlin/com/example/BlogConfiguration.kt", "BlogConfiguration")
    ]
    properties_symbol_id = symbol_ids[
        ("src/main/kotlin/com/example/BlogProperties.kt", "BlogProperties")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{config_symbol_id}"
        and str(row["target_node"]) == f"symbol:{properties_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_kotlin_multi_type_file_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "kotlin-multi-type-symbol-repo"
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/kotlin"],
            include_patterns=["src/main/kotlin/**/*.kt"],
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
        ("src/main/kotlin/com/example/Controllers.kt", "HtmlController")
    ]
    article_repository_symbol_id = symbol_ids[
        ("src/main/kotlin/com/example/Repositories.kt", "ArticleRepository")
    ]
    user_repository_symbol_id = symbol_ids[
        ("src/main/kotlin/com/example/Repositories.kt", "UserRepository")
    ]
    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:src/main/kotlin/com/example/Controllers.kt"
        and str(row["target_node"]) == "file:src/main/kotlin/com/example/Repositories.kt"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{controller_symbol_id}"
        and str(row["target_node"]) == f"symbol:{article_repository_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{controller_symbol_id}"
        and str(row["target_node"]) == f"symbol:{user_repository_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scala_grouped_import_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scala-grouped-import-repo"
    core_dir = repo_path / "src" / "main" / "scala" / "upickle" / "core"
    upack_dir = repo_path / "src" / "main" / "scala" / "upack"
    core_dir.mkdir(parents=True)
    upack_dir.mkdir(parents=True)
    (core_dir / "Visitor.scala").write_text(
        "package upickle.core\ntrait Visitor\n",
        encoding="utf-8",
    )
    (core_dir / "BufferingInputStreamParser.scala").write_text(
        "package upickle.core\nobject BufferingInputStreamParser\n",
        encoding="utf-8",
    )
    (upack_dir / "MsgPackReader.scala").write_text(
        "package upack\n"
        "import upickle.core.{BufferingInputStreamParser, Visitor}\n"
        "object MsgPackReader {\n"
        "  val parser = BufferingInputStreamParser\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/scala"],
            include_patterns=["src/main/scala/**/*.scala"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main/scala/upack/MsgPackReader.scala"
        and str(row["target_node"]) == "file:src/main/scala/upickle/core/BufferingInputStreamParser.scala"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main/scala/upack/MsgPackReader.scala"
        and str(row["target_node"]) == "file:src/main/scala/upickle/core/Visitor.scala"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scala_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scala-symbol-repo"
    core_dir = repo_path / "src" / "main" / "scala" / "upickle" / "core"
    upack_dir = repo_path / "src" / "main" / "scala" / "upack"
    core_dir.mkdir(parents=True)
    upack_dir.mkdir(parents=True)
    (core_dir / "Visitor.scala").write_text(
        "package upickle.core\ntrait Visitor\n",
        encoding="utf-8",
    )
    (upack_dir / "MsgPackReader.scala").write_text(
        "package upack\n"
        "import upickle.core.Visitor\n"
        "object MsgPackReader {\n"
        "  def render(visitor: Visitor): Visitor = visitor\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/scala"],
            include_patterns=["src/main/scala/**/*.scala"],
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

    reader_symbol_id = symbol_ids[("src/main/scala/upack/MsgPackReader.scala", "MsgPackReader")]
    visitor_symbol_id = symbol_ids[("src/main/scala/upickle/core/Visitor.scala", "Visitor")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{reader_symbol_id}"
        and str(row["target_node"]) == f"symbol:{visitor_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scala_package_wildcard_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scala-package-wildcard-repo"
    syntax_dir = (
        repo_path
        / "src"
        / "main"
        / "scala"
        / "play"
        / "api"
        / "libs"
        / "functional"
        / "syntax"
    )
    functional_dir = syntax_dir.parent
    syntax_dir.mkdir(parents=True)
    functional_dir.mkdir(parents=True, exist_ok=True)
    (syntax_dir / "package.scala").write_text(
        "package play.api.libs.functional.syntax\n"
        "object SyntaxOps\n",
        encoding="utf-8",
    )
    (functional_dir / "UseSyntax.scala").write_text(
        "package play.api.libs.functional\n"
        "import play.api.libs.functional.syntax._\n"
        "object UseSyntax {\n"
        "  val syntax = SyntaxOps\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/main/scala"],
            include_patterns=["src/main/scala/**/*.scala"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main/scala/play/api/libs/functional/UseSyntax.scala"
        and str(row["target_node"]) == "file:src/main/scala/play/api/libs/functional/syntax/package.scala"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scala_package_alias_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scala-package-alias-repo"
    source_dir = repo_path / "os" / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "Path.scala").write_text(
        "package os\nobject Path\n",
        encoding="utf-8",
    )
    (source_dir / "ProcessOps.scala").write_text(
        "package os\n"
        "import os.Path\n"
        "object ProcessOps {\n"
        "  val path = Path\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["os/src"],
            include_patterns=["os/src/**/*.scala"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:os/src/ProcessOps.scala"
        and str(row["target_node"]) == "file:os/src/Path.scala"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_groovy_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "groovy-dependency-repo"
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
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main/groovy/org/example/OwnerController.groovy"
        and str(row["target_node"]) == "file:src/main/groovy/org/example/Owner.groovy"
        for row in graph_rows
    )


