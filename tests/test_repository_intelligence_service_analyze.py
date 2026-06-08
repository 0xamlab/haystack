"""Tests for repository_intelligence_service: analyze.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_analyze_snapshot_files_preserves_input_order_when_parallel(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ordered-repo"
    (repo_path / "src").mkdir(parents=True)
    first = repo_path / "src" / "a.py"
    second = repo_path / "src" / "b.py"
    first.write_text("def a() -> int:\n    return 1\n", encoding="utf-8")
    second.write_text("def b() -> int:\n    return 2\n", encoding="utf-8")

    original_analyze_file_cached = repository_service._analyze_file_cached

    def _delayed_analyze_file_cached(*args, **kwargs):  # type: ignore[no-untyped-def]
        path = kwargs["path"]
        if Path(path).name == "a.py":
            time.sleep(0.05)
        return original_analyze_file_cached(*args, **kwargs)

    repository_service._analyze_file_cached = _delayed_analyze_file_cached
    try:
        analyses = repository_service._analyze_snapshot_files(
            root_path=repo_path,
            files=[first, second],
            module_index={"src/a": "src/a.py", "src/b": "src/b.py"},
            workspace_package_index={},
            workspace_go_module_index={},
            max_file_size_bytes=100_000,
            analysis_context_hash="order-test",
            git_content_hashes=None,
            max_workers=2,
        )
    finally:
        repository_service._analyze_file_cached = original_analyze_file_cached

    assert [analysis.file_path for analysis in analyses] == ["src/a.py", "src/b.py"]


def test_analyze_file_dependencies_uses_registered_sql_dependency_parser(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sql-dependency-registry-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "customers.sql").write_text(
        "create table customers as\n"
        "select 1 as id;\n",
        encoding="utf-8",
    )
    orders_path = repo_path / "models" / "orders.sql"
    orders_path.write_text(
        "select * from {{ ref('customers') }}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["models/customers.sql", "models/orders.sql"],
        root_path=repo_path,
    )
    dependencies = repository_service._analyze_file_dependencies(
        root_path=repo_path,
        path=orders_path,
        module_index=module_index,
        workspace_package_index={},
        workspace_go_module_index=None,
        max_file_size_bytes=100_000,
    )

    assert any(dependency.target_file == "models/customers.sql" for dependency in dependencies)


