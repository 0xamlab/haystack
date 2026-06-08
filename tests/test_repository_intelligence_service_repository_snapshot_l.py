"""Tests for repository_intelligence_service: repository_snapshot_l.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_graph_contains_fortran_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "fortran-dependency-repo"
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "fpm.toml"],
            include_patterns=["src/**/*.f90", "src/**/*.f95", "src/**/*.f03", "src/**/*.f08", "src/**/*.f", "src/**/*.for", "fpm.toml"],
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
        and str(row["source_node"]) == "file:src/main.f90"
        and str(row["target_node"]) == "file:src/math_utils.f90"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/main.f90", "main")]
    helper_symbol_id = symbol_ids[("src/math_utils.f90", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_d_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "d-dependency-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "dub.json").write_text(
        '{\n  "name": "acme"\n}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "utils.d").write_text(
        "module acme.utils;\n"
        "int helper() {\n"
        "    return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "main.d").write_text(
        "module acme.main;\n"
        "import acme.utils : helper;\n"
        "int main() {\n"
        "    return helper();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "dub.json"],
            include_patterns=["src/**/*.d", "src/*.d", "dub.json", "dub.sdl"],
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
        and str(row["source_node"]) == "file:src/acme/main.d"
        and str(row["target_node"]) == "file:src/acme/utils.d"
        for row in graph_rows
    )

    main_symbol_id = symbol_ids[("src/acme/main.d", "main")]
    helper_symbol_id = symbol_ids[("src/acme/utils.d", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_matlab_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "matlab-dependency-repo"
    (repo_path / "+acme").mkdir(parents=True)
    (repo_path / "+acme" / "helper.m").write_text(
        "function value = helper()\n"
        "value = 1;\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "main.m").write_text(
        "function value = main()\n"
        "import acme.helper\n"
        "value = helper();\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.m", "+acme"],
            include_patterns=["**/*.m", "*.m"],
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
        and str(row["source_node"]) == "file:main.m"
        and str(row["target_node"]) == "file:+acme/helper.m"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("main.m", "main")]
    helper_symbol_id = symbol_ids[("+acme/helper.m", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_objective_c_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "objective-c-dependency-repo"
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.h", "src/*.h", "src/**/*.m", "src/*.m"],
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
        and str(row["source_node"]) == "file:src/ACMClient.m"
        and str(row["target_node"]) == "file:src/ACMHelper.h"
        for row in graph_rows
    )
    client_run_symbol_id = symbol_ids[("src/ACMClient.m", "run")]
    helper_work_symbol_id = symbol_ids[("src/ACMHelper.h", "work")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{client_run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_work_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_prolog_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "prolog-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "family.pl").write_text(
        ":- module(family, [ancestor/2, parent/2]).\n"
        "parent(alice, bob).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "related.pl").write_text(
        ":- use_module('family.pl', [ancestor/2]).\n"
        "related(X, Y) :- ancestor(X, Y).\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=[
                "src/**/*.pl",
                "src/*.pl",
                "src/**/*.prolog",
                "src/*.prolog",
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
        and str(row["source_node"]) == "file:src/related.pl"
        and str(row["target_node"]) == "file:src/family.pl"
        for row in graph_rows
    )
    related_symbol_id = symbol_ids[("src/related.pl", "related")]
    ancestor_symbol_id = symbol_ids[("src/family.pl", "ancestor")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{related_symbol_id}"
        and str(row["target_node"]) == f"symbol:{ancestor_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_ml_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ml-dependency-repo"
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
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "project.mlb"],
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
        str(row["edge_type"]) == "open"
        and str(row["source_node"]) == "file:src/Main.sml"
        and str(row["target_node"]) == "file:src/Util.sml"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/Main.sml", "run")]
    helper_symbol_id = symbol_ids[("src/Util.sml", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_vba_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "vba-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "JsonData.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "JsonData"\n'
        "Option Explicit\n"
        "\n"
        "Public Function ToJson() As String\n"
        '    ToJson = "{}"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "JsonConverter.bas").write_text(
        'Attribute VB_Name = "JsonConverter"\n'
        "Option Explicit\n"
        "\n"
        "Public Sub Main()\n"
        "    Dim data As JsonData\n"
        "    Set data = New JsonData\n"
        "    Debug.Print data.ToJson()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.bas", "src/*.bas", "src/**/*.cls", "src/*.cls"],
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
        and str(row["source_node"]) == "file:src/JsonConverter.bas"
        and str(row["target_node"]) == "file:src/JsonData.cls"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/JsonConverter.bas", "Main")]
    to_json_symbol_id = symbol_ids[("src/JsonData.cls", "ToJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{to_json_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_classic_visual_basic_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "vb6-dependency-repo"
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
    (repo_path / "src" / "cHelper.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "cHelper"\n'
        "Option Explicit\n"
        "\n"
        "Public Function Helper() As String\n"
        '    Helper = "ok"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "modMain.bas").write_text(
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "\n"
        "Public Sub RunApp()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Form1.frm").write_text(
        "VERSION 5.00\n"
        "Begin VB.Form Form1\n"
        '   Caption = "Form1"\n'
        "End\n"
        'Attribute VB_Name = "Form1"\n'
        "Option Explicit\n"
        "\n"
        "Private mHelper As cHelper\n"
        "\n"
        "Private Sub Form_Load()\n"
        "    Set mHelper = New cHelper\n"
        "    Debug.Print mHelper.Helper()\n"
        "    modMain.RunApp\n"
        "End Sub\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "Project1.vbp"],
            include_patterns=[
                "src/**/*.bas",
                "src/*.bas",
                "src/**/*.cls",
                "src/*.cls",
                "src/**/*.frm",
                "src/*.frm",
                "*.vbp",
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
        and str(row["source_node"]) == "file:src/Form1.frm"
        and str(row["target_node"]) == "file:src/cHelper.cls"
        for row in graph_rows
    )
    form_load_symbol_id = symbol_ids[("src/Form1.frm", "Form_Load")]
    helper_symbol_id = symbol_ids[("src/cHelper.cls", "Helper")]
    run_app_symbol_id = symbol_ids[("src/modMain.bas", "RunApp")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{form_load_symbol_id}"
        and str(row["target_node"]) in {
            f"symbol:{helper_symbol_id}",
            f"symbol:{run_app_symbol_id}",
        }
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_lisp_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "lisp-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "acme.asd").write_text(
        '(asdf:defsystem "acme"\n'
        '  :pathname "src"\n'
        '  :components ((:file "helper") (:file "app")))\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "helper.lisp").write_text(
        "(defpackage #:acme.helper (:use #:cl) (:export #:helper))\n"
        "(in-package #:acme.helper)\n"
        "(defun helper () 1)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "app.lisp").write_text(
        "(defpackage #:acme.app (:use #:cl) (:import-from #:acme.helper #:helper))\n"
        "(in-package #:acme.app)\n"
        "(defun run () (helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "acme.asd"],
            include_patterns=["src/**/*.lisp", "src/*.lisp", "*.asd"],
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
        and str(row["source_node"]) == "file:src/app.lisp"
        and str(row["target_node"]) == "file:src/helper.lisp"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/app.lisp", "run")]
    helper_symbol_id = symbol_ids[("src/helper.lisp", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_emacslisp_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "emacslisp-dependency-repo"
    (repo_path / "lisp").mkdir(parents=True)
    (repo_path / "lisp" / "helper.el").write_text(
        "(provide 'helper)\n"
        "(defun helper-fn () 1)\n",
        encoding="utf-8",
    )
    (repo_path / "main.el").write_text(
        "(require 'helper)\n"
        "(provide 'main)\n"
        "(defun run () (helper-fn))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.el", "lisp"],
            include_patterns=["*.el", "lisp/**/*.el", "lisp/*.el"],
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
        and str(row["source_node"]) == "file:main.el"
        and str(row["target_node"]) == "file:lisp/helper.el"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("main.el", "run")]
    helper_symbol_id = symbol_ids[("lisp/helper.el", "helper-fn")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scheme_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scheme-dependency-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "package.scm").write_text(
        "(define-library (acme app)\n"
        "  (export run)\n"
        "  (import (acme helper))\n"
        "  (begin\n"
        "    (define (run) (helper))))\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "helper.sld").write_text(
        "(define-library (acme helper)\n"
        "  (export helper)\n"
        "  (begin\n"
        "    (define (helper) 1)))\n",
        encoding="utf-8",
    )
    (repo_path / "main.scm").write_text(
        "#!r6rs\n"
        "(import (acme helper))\n"
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.scm", "package.scm", "lib"],
            include_patterns=["*.scm", "lib/**/*.sld", "lib/*.sld", "*.sld"],
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
        and str(row["source_node"]) == "file:main.scm"
        and str(row["target_node"]) == "file:lib/acme/helper.sld"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("main.scm", "run")]
    helper_symbol_id = symbol_ids[("lib/acme/helper.sld", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


