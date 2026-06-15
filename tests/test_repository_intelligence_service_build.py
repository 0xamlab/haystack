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


def test_root_scoped_module_alias_builder_registry_is_language_scoped() -> None:
    openqasm_builders = (
        repository_root_scoped_aliases.root_scoped_module_alias_builders_for_language(
            "openqasm"
        )
    )

    assert repository_root_scoped_aliases._openqasm_module_aliases_for_path in openqasm_builders
    assert repository_root_scoped_aliases._protobuf_module_aliases_for_path not in openqasm_builders
    assert (
        repository_root_scoped_aliases.root_scoped_module_alias_builders_for_language(
            "unknown"
        )
        is repository_root_scoped_aliases._ROOT_SCOPED_MODULE_ALIAS_BUILDERS
    )
    assert (
        repository_root_scoped_aliases.root_scoped_module_alias_builders_for_language(
            "dart"
        )
        == ()
    )
    assert (
        repository_root_scoped_aliases.root_scoped_module_alias_builders_for_language("c")
        == ()
    )


def test_build_module_index_uses_text_aware_root_scoped_language_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "puppet-module-index-repo"
    (repo_path / "manifests").mkdir(parents=True)
    (repo_path / "manifests" / "site.pp").write_text(
        "class profile::base { }\n",
        encoding="utf-8",
    )
    observed_languages: list[str | None] = []
    original = (
        repository_root_scoped_aliases.root_scoped_module_alias_builders_for_language
    )

    def _recording_selector(language: str | None) -> tuple[Any, ...]:
        observed_languages.append(language)
        return original(language)

    monkeypatch.setattr(
        repository_root_scoped_aliases,
        "root_scoped_module_alias_builders_for_language",
        _recording_selector,
    )

    repository_service._build_module_index(
        ["manifests/site.pp"],
        root_path=repo_path,
    )

    assert observed_languages == ["puppet"]


def test_build_module_index_uses_module_only_root_scoped_openscad_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "openscad-module-index-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "helpers.scad").write_text(
        "module shelf(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n"
        "function render_profile(value) = value + 1;\n",
        encoding="utf-8",
    )
    observed_include_symbol_aliases: list[bool] = []
    original = repository_root_scoped_aliases.openscad_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_include_symbol_aliases.append(bool(kwargs.get("include_symbol_aliases")))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.openscad_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["models/helpers.scad"],
        root_path=repo_path,
    )

    # OpenSCAD resolves symbol references (the references_symbol graph edges) through
    # the module index, so the index must carry the symbol-level aliases; skipping
    # them would drop those edges. The path/module aliases are still present.
    assert observed_include_symbol_aliases == [True]
    assert module_index["models.helpers"] == "models/helpers.scad"
    assert module_index["shelf"] == "models/helpers.scad"
    assert module_index["render_profile"] == "models/helpers.scad"


def test_build_module_index_uses_module_only_root_scoped_purescript_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "purescript-module-index-repo"
    (repo_path / "src" / "Control").mkdir(parents=True)
    (repo_path / "src" / "Control" / "Helper.purs").write_text(
        "module Control.Helper where\n\n"
        "renderJson :: String\n"
        "renderJson = \"{}\"\n",
        encoding="utf-8",
    )
    observed_include_symbol_aliases: list[bool | None] = []
    original = repository_root_scoped_aliases.purescript_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.purescript_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["src/Control/Helper.purs"],
        root_path=repo_path,
    )

    assert observed_include_symbol_aliases == [False]
    assert module_index["src.Control.Helper"] == "src/Control/Helper.purs"
    assert module_index["Control.Helper"] == "src/Control/Helper.purs"
    assert "renderJson" not in module_index
    assert "Control.Helper.renderJson" not in module_index


def test_build_module_index_uses_module_only_root_scoped_bicep_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bicep-module-index-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "modules" / "main.bicep").write_text(
        "param name string\n\n"
        "var prefix = name\n\n"
        "output fullName string = prefix\n",
        encoding="utf-8",
    )
    observed_include_symbol_aliases: list[bool | None] = []
    original = repository_root_scoped_aliases.bicep_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.bicep_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["modules/main.bicep"],
        root_path=repo_path,
    )

    assert observed_include_symbol_aliases == [False]
    assert module_index["modules"] == "modules/main.bicep"
    assert module_index["modules.main"] == "modules/main.bicep"
    assert "name" not in module_index
    assert "prefix" not in module_index
    assert "fullName" not in module_index


def test_build_module_index_uses_module_only_root_scoped_elm_aliases(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "elm-module-index-repo"
    (repo_path / "src" / "Page").mkdir(parents=True)
    (repo_path / "src" / "Page" / "Home.elm").write_text(
        "module Page.Home exposing (Model, init)\n\n"
        "type alias Model =\n"
        "    { count : Int }\n\n"
        "init : Model\n"
        "init =\n"
        "    { count = 0 }\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/Page/Home.elm"],
        root_path=repo_path,
    )

    assert module_index["src.Page.Home"] == "src/Page/Home.elm"
    assert module_index["Page.Home"] == "src/Page/Home.elm"
    assert "Model" not in module_index
    assert "init" not in module_index
    assert "Page.Home.init" not in module_index


def test_build_module_index_uses_module_only_root_scoped_opencl_aliases(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "opencl-module-index-repo"
    (repo_path / "kernels").mkdir(parents=True)
    (repo_path / "kernels" / "common.clh").write_text(
        "__constant int SCALE = 2;\n"
        "inline float scale_value(float value) {\n"
        "    return value * SCALE;\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["kernels/common.clh"],
        root_path=repo_path,
    )

    assert module_index["kernels/common.clh"] == "kernels/common.clh"
    assert module_index["kernels/common"] == "kernels/common.clh"
    assert "scale_value" not in module_index


def test_build_module_index_passes_preloaded_text_to_cuda_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cuda-module-index-text-repo"
    (repo_path / "src" / "kernels").mkdir(parents=True)
    source_text = (
        "__device__ inline int add_one(int x) {\n"
        "  return x + 1;\n"
        "}\n"
    )
    (repo_path / "src" / "kernels" / "vector_add.cuh").write_text(
        source_text,
        encoding="utf-8",
    )
    observed_texts: list[str | None] = []
    original = repository_root_scoped_aliases.cuda_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.cuda_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["src/kernels/vector_add.cuh"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]


def test_build_module_index_passes_preloaded_text_to_ladder_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ladder-module-index-text-repo"
    (repo_path / "logic").mkdir(parents=True)
    source_text = (
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
        "</RSLogix5000Content>\n"
    )
    (repo_path / "logic" / "Main.L5X").write_text(source_text, encoding="utf-8")
    observed_texts: list[str | None] = []
    original = repository_root_scoped_aliases.ladder_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.ladder_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["logic/Main.L5X"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]


def test_build_module_index_passes_preloaded_text_to_lean_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lean-module-index-text-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    source_text = "def helper : Nat := 0\n"
    (repo_path / "Batteries" / "Helper.lean").write_text(
        source_text,
        encoding="utf-8",
    )
    observed_texts: list[str | None] = []
    original = repository_root_scoped_aliases.lean_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.lean_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["Batteries/Helper.lean"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]


def test_build_module_index_uses_module_only_root_scoped_lean_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lean-module-index-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    (repo_path / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 0\n",
        encoding="utf-8",
    )
    observed_include_symbol_aliases: list[bool | None] = []
    original = repository_root_scoped_aliases.lean_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.lean_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["Batteries/Helper.lean"],
        root_path=repo_path,
    )

    assert observed_include_symbol_aliases == [False]
    assert module_index["Batteries.Helper"] == "Batteries/Helper.lean"
    assert module_index["Helper"] == "Batteries/Helper.lean"
    assert "helper" not in module_index


def test_build_module_index_passes_preloaded_text_to_wolfram_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "wolfram-module-index-text-repo"
    (repo_path / "Kernel").mkdir(parents=True)
    source_text = (
        'BeginPackage["Acme`"];\n'
        'helper::usage = "helper";\n'
        'Begin["`Private`"];\n'
        "helper[] := 1;\n"
        "End[];\n"
        "EndPackage[];\n"
    )
    (repo_path / "Kernel" / "Helpers.wl").write_text(
        source_text,
        encoding="utf-8",
    )
    observed_texts: list[str | None] = []
    original = repository_root_scoped_aliases.wolfram_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.wolfram_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["Kernel/Helpers.wl"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]


def test_build_module_index_passes_preloaded_text_to_vba_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vba-module-index-text-repo"
    (repo_path / "src").mkdir(parents=True)
    source_text = (
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "JsonData"\n'
        "Option Explicit\n"
        "Public Function ToJson() As String\n"
        '    ToJson = "{}"\n'
        "End Function\n"
    )
    (repo_path / "src" / "JsonData.cls").write_text(source_text, encoding="utf-8")
    observed_texts: list[str | None] = []
    original = repository_root_scoped_aliases.vba_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.vba_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["src/JsonData.cls"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]


def test_build_module_index_passes_preloaded_text_to_classic_visual_basic_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vb6-module-index-text-repo"
    repo_path.mkdir(parents=True)
    source_text = (
        'Name="Project1"\n'
        'Startup="Main"\n'
        "Module=Main; src/Main.bas\n"
    )
    (repo_path / "Project1.vbp").write_text(source_text, encoding="utf-8")
    observed_texts: list[str | None] = []
    original = repository_root_scoped_aliases.classic_visual_basic_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.classic_visual_basic_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["Project1.vbp"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]


def test_build_module_index_passes_preloaded_text_to_scheme_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scheme-module-index-text-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    source_text = (
        "(define-library (acme helper)\n"
        "  (export helper)\n"
        "  (begin\n"
        "    (define (helper) 1)))\n"
    )
    (repo_path / "lib" / "acme" / "helper.sld").write_text(source_text, encoding="utf-8")
    observed_texts: list[str | None] = []
    observed_include_symbol_aliases: list[bool | None] = []
    loaded_adapter = repository_root_scoped_aliases.scheme_adapter._load()
    original = loaded_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original(**kwargs)

    monkeypatch.setattr(
        loaded_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["lib/acme/helper.sld"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]
    assert observed_include_symbol_aliases == [False]


def test_build_module_index_passes_preloaded_text_to_sml_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sml-module-index-text-repo"
    (repo_path / "src").mkdir(parents=True)
    source_text = (
        "structure Util = struct\n"
        "fun helper () = 1\n"
        "end\n"
    )
    (repo_path / "src" / "Util.sml").write_text(source_text, encoding="utf-8")
    observed_texts: list[str | None] = []
    observed_include_symbol_aliases: list[bool | None] = []
    loaded_adapter = repository_root_scoped_aliases.sml_adapter._load()
    original = loaded_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original(**kwargs)

    monkeypatch.setattr(
        loaded_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["src/Util.sml"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]
    assert observed_include_symbol_aliases == [False]


def test_build_module_index_passes_preloaded_text_to_systemverilog_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "systemverilog-module-index-text-repo"
    (repo_path / "rtl").mkdir(parents=True)
    source_text = (
        "package util_pkg;\n"
        "endpackage\n"
        "module top;\n"
        "endmodule\n"
    )
    (repo_path / "rtl" / "top.sv").write_text(source_text, encoding="utf-8")
    observed_texts: list[str | None] = []
    observed_include_symbol_aliases: list[bool | None] = []
    loaded_adapter = repository_root_scoped_aliases.systemverilog_adapter._load()
    original = loaded_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original(**kwargs)

    monkeypatch.setattr(
        loaded_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["rtl/top.sv"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]
    # Preloaded text is the optimization under test; symbol-level aliases must still be
    # built because SystemVerilog resolves symbol references (references_symbol graph
    # edges) through the module index.
    assert observed_include_symbol_aliases == [True]


def test_build_module_index_passes_preloaded_text_to_vyper_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vyper-module-index-text-repo"
    (repo_path / "contracts").mkdir(parents=True)
    source_text = (
        "def deposit(amount: uint256):\n"
        "    pass\n"
    )
    (repo_path / "contracts" / "Vault.vy").write_text(source_text, encoding="utf-8")
    observed_texts: list[str | None] = []
    observed_include_symbol_aliases: list[bool | None] = []
    loaded_adapter = repository_root_scoped_aliases.vyper_adapter._load()
    original = loaded_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original(**kwargs)

    monkeypatch.setattr(
        loaded_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["contracts/Vault.vy"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]
    assert observed_include_symbol_aliases == [False]


def test_build_module_index_passes_preloaded_text_to_xpp_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "xpp-module-index-text-repo"
    source_text = (
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
        "</AxClass>\n"
    )
    source_path = repo_path / "PackagesLocalDirectory" / "Acme" / "Acme" / "AxClass" / "AcmeMain.xml"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(source_text, encoding="utf-8")
    observed_texts: list[str | None] = []
    original = repository_root_scoped_aliases.xpp_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.xpp_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]


def test_build_module_index_passes_preloaded_text_to_qmake_root_scoped_alias_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qmake-module-index-text-repo"
    repo_path.mkdir(parents=True)
    source_text = (
        "TEMPLATE = subdirs\n"
        "TARGET = workspace\n"
        "SUBDIRS += app\n"
    )
    (repo_path / "project.pro").write_text(source_text, encoding="utf-8")
    observed_texts: list[str | None] = []
    original = repository_root_scoped_aliases.qmake_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.qmake_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    repository_service._build_module_index(
        ["project.pro"],
        root_path=repo_path,
    )

    assert observed_texts == [source_text]


def test_build_module_index_uses_path_only_root_scoped_shaderlab_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shaderlab-module-index-repo"
    (repo_path / "Shaders").mkdir(parents=True)
    (repo_path / "Shaders" / "Main.shader").write_text(
        'Shader "Demo/Main" {\n'
        "SubShader {\n"
        "Pass {\n"
        "HLSLPROGRAM\n"
        "float4 frag() : SV_Target {\n"
        "  return float4(0.0, 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDHLSL\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    observed_kwargs: list[tuple[bool | None, bool | None]] = []
    original = repository_root_scoped_aliases.shaderlab_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_kwargs.append(
            (
                kwargs.get("include_symbol_aliases"),
                kwargs.get("include_shader_name_aliases"),
            )
        )
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.shaderlab_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["Shaders/Main.shader"],
        root_path=repo_path,
    )

    assert observed_kwargs == [(False, False)]
    assert module_index["Shaders/Main.shader"] == "Shaders/Main.shader"
    assert module_index["Shaders/Main"] == "Shaders/Main.shader"
    assert module_index["Main"] == "Shaders/Main.shader"
    assert "Demo/Main" not in module_index
    assert "frag" not in module_index


def test_build_module_index_uses_path_only_root_scoped_less_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "less-module-index-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "theme.less").write_text(
        "@brand-color: #123456;\n.rounded(@radius) { border-radius: @radius; }\n",
        encoding="utf-8",
    )
    observed_include_symbol_aliases: list[bool | None] = []
    original = repository_root_scoped_aliases.less_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.less_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["styles/theme.less"],
        root_path=repo_path,
    )

    assert observed_include_symbol_aliases == [False]
    assert module_index["styles/theme.less"] == "styles/theme.less"
    assert module_index["styles.theme"] == "styles/theme.less"
    assert module_index["theme"] == "styles/theme.less"
    assert "brand-color" not in module_index
    assert "rounded" not in module_index


def test_build_module_index_uses_path_only_root_scoped_typst_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "typst-module-index-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "math.typ").write_text(
        "#let add(x, y) = x + y\n#let scale(x) = x * 2\n",
        encoding="utf-8",
    )
    observed_include_symbol_aliases: list[bool | None] = []
    original = repository_root_scoped_aliases.typst_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.typst_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["docs/math.typ"],
        root_path=repo_path,
    )

    assert observed_include_symbol_aliases == [False]
    assert module_index["docs/math.typ"] == "docs/math.typ"
    assert module_index["docs.math"] == "docs/math.typ"
    assert module_index["math"] == "docs/math.typ"
    assert "add" not in module_index
    assert "scale" not in module_index


def test_build_module_index_uses_path_only_root_scoped_coq_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coq-module-index-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper : nat := 0.\n",
        encoding="utf-8",
    )
    observed_include_symbol_aliases: list[bool | None] = []
    original = repository_root_scoped_aliases.coq_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.coq_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["theories/Helper.v"],
        root_path=repo_path,
    )

    # Coq resolves symbol references (the references_symbol graph edges) through the
    # module index, so the index must carry the symbol-level aliases; skipping them
    # would drop those edges. The path/module aliases are still present.
    assert observed_include_symbol_aliases == [True]
    assert module_index["theories/Helper.v"] == "theories/Helper.v"
    assert module_index["theories.Helper"] == "theories/Helper.v"
    assert module_index["Helper"] == "theories/Helper.v"
    assert module_index["helper"] == "theories/Helper.v"


def test_build_module_index_uses_path_only_root_scoped_dm_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dm-module-index-repo"
    (repo_path / "code").mkdir(parents=True)
    (repo_path / "code" / "main.dm").write_text(
        "/obj/item\nspawn_item()\n    return new /obj/item\n",
        encoding="utf-8",
    )
    observed_include_symbol_aliases: list[bool | None] = []
    original = repository_root_scoped_aliases.dm_adapter.module_aliases_for_path

    def _recording_module_aliases_for_path(**kwargs: Any) -> set[str]:
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original(**kwargs)

    monkeypatch.setattr(
        repository_root_scoped_aliases.dm_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["code/main.dm"],
        root_path=repo_path,
    )

    assert observed_include_symbol_aliases == [False]
    assert module_index["code/main.dm"] == "code/main.dm"
    assert module_index["code.main"] == "code/main.dm"
    assert module_index["main"] == "code/main.dm"
    assert "/obj/item" not in module_index
    assert "spawn_item" not in module_index
