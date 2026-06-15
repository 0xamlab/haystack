"""Tests for repository_intelligence_real_repo_probe: operational_seed_j.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from benchmarks.repository_intelligence_real_repo_probe_profile_manifest_build_support import (
    _cmake_profile_hints,
    clear_c_family_manifest_ecosystem_cache,
)

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


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
    assert "CMakeLists.txt" in seed_plan["entrypoint_files"]
    assert "include/acme" in seed_plan["support_roots"]
    assert "include" not in seed_plan["support_roots"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.cpp" in seed_plan["entrypoint_files"]
    assert "src/core.cpp" in seed_plan["entrypoint_files"]
    assert "tests/core_test.cpp" not in seed_plan["entrypoint_files"]


def test_cmake_profile_hints_cache_reuses_manifest_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "cmake-profile-cache-repo"
    repo_path.mkdir(parents=True)
    manifest_path = repo_path / "CMakeLists.txt"
    manifest_path.write_text(
        "add_library(acme src/core.cpp include/acme/core.hpp)\n"
        "add_executable(acme_cli src/main.cpp)\n",
        encoding="utf-8",
    )

    clear_c_family_manifest_ecosystem_cache()
    original_read_text = Path.read_text
    read_counts: dict[Path, int] = {}

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self == manifest_path:
            read_counts[self] = read_counts.get(self, 0) + 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    first_entrypoints, first_roots, first_configs = _cmake_profile_hints(
        repo_path,
        "CMakeLists.txt",
    )
    second_entrypoints, second_roots, second_configs = _cmake_profile_hints(
        repo_path,
        "CMakeLists.txt",
    )

    assert first_entrypoints == second_entrypoints
    assert first_roots == second_roots
    assert first_configs == second_configs
    assert "src/main.cpp" in first_entrypoints
    assert "include/acme" in first_roots
    assert read_counts.get(manifest_path, 0) == 1


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


def test_operational_seed_plan_without_diagnostics_prefers_just_over_shell_and_containerfile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "just-container-repo"
    (repo_path / "build_files").mkdir(parents=True)
    (repo_path / "Justfile").write_text(
        "build:\n"
        "  ./build_files/build.sh\n",
        encoding="utf-8",
    )
    (repo_path / "Containerfile").write_text(
        "FROM alpine:3.20\n"
        "COPY . /workspace\n",
        encoding="utf-8",
    )
    (repo_path / "build_files" / "build.sh").write_text(
        "#!/usr/bin/env bash\n"
        "echo build\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "just" in seed_plan["detected_ecosystems"]
    assert "dockerfile" in seed_plan["detected_ecosystems"]
    assert "shell" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "just"
    assert "Justfile" in seed_plan["entrypoint_files"]


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
