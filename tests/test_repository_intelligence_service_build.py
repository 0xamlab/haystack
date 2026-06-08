"""Tests for repository_intelligence_service: build.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_build_module_index_uses_registered_root_scoped_sql_alias_builders(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sql-module-index-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "customers.sql").write_text(
        "create table sales.customers as\n"
        "select 1 as id;\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["models/customers.sql"],
        root_path=repo_path,
    )

    assert module_index["sales.customers"] == "models/customers.sql"


