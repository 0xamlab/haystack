# ruff: noqa: I001
from __future__ import annotations
from pathlib import Path
from apps.api_server.services.repository_intelligence_shared import _stable_identifier
from apps.api_server.services.repository_intelligence_root_scoped_aliases import (
    actionscript_adapter,
    al_adapter,
    angelscript_adapter,
    antlr_adapter,
    apacheconf_adapter,
    applescript_adapter,
    aspectj_adapter,
    assembly_adapter,
    ballerina_adapter,
    bicep_adapter,
    blade_adapter,
    chapel_adapter,
    classic_visual_basic_adapter,
    clojurescript_adapter,
    cobol_adapter,
    coq_adapter,
    cue_adapter,
    d_language_adapter,
    delphi_adapter,
    dhall_adapter,
    dm_adapter,
    eiffel_adapter,
    ejs_adapter,
    elm_adapter,
    erb_adapter,
    factor_adapter,
    fortran_adapter,
    foxpro_adapter,
    freemarker_adapter,
    gdscript_adapter,
    gherkin_adapter,
    gml_adapter,
    graphviz_adapter,
    groovy_adapter,
    haml_adapter,
    handlebars_adapter,
    haxe_adapter,
    hcl_adapter,
    janet_adapter,
    jinja_adapter,
    labview_adapter,
    ladder_adapter,
    lean_adapter,
    less_adapter,
    liquid_adapter,
    matlab_adapter,
    mermaid_adapter,
    ml_adapter,
    moonbit_adapter,
    move_adapter,
    mustache_adapter,
    nextflow_adapter,
    nunjucks_adapter,
    objective_c_adapter,
    openqasm_adapter,
    pascal_adapter,
    plantuml_adapter,
    plpgsql_adapter,
    plsql_adapter,
    prolog_adapter,
    pug_adapter,
    rego_adapter,
    robotframework_adapter,
    rpg_adapter,
    sas_adapter,
    scratch_adapter,
    scss_adapter,
    slim_adapter,
    smalltalk_adapter,
    smarty_adapter,
    sml_adapter,
    solidity_adapter,
    sql_adapter,
    starlark_adapter,
    stylus_adapter,
    systemverilog_adapter,
    tcl_adapter,
    tlaplus_adapter,
    tsql_adapter,
    twig_adapter,
    v_adapter,
    vba_adapter,
    vbscript_adapter,
    verilog_adapter,
    vhdl_adapter,
    vimscript_adapter,
    visual_basic_adapter,
    webassembly_adapter,
    wolfram_adapter,
    xpp_adapter,
    xtend_adapter,
    yara_adapter,
)
def _plpgsql_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return plpgsql_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
_webassembly_module_aliases_for_path = lambda *, root_path, file_path: webassembly_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _ballerina_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return ballerina_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _clojurescript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return clojurescript_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
    )
_al_module_aliases_for_path = lambda *, root_path, file_path: al_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _sml_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return sml_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )


_groovy_module_aliases_for_path = lambda *, root_path, file_path: groovy_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_xtend_module_aliases_for_path = lambda *, root_path, file_path: xtend_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_freemarker_module_aliases_for_path = lambda *, root_path, file_path: freemarker_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_nextflow_module_aliases_for_path = lambda *, root_path, file_path: nextflow_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _moonbit_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return moonbit_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _chapel_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return chapel_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
def _coq_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return coq_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        # Coq resolves symbol references (references_symbol graph edges) through the
        # module index, which therefore must carry symbol-level aliases.
        include_symbol_aliases=True,
    )
def _lean_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return lean_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
def _eiffel_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return eiffel_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
def _janet_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return janet_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _dhall_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return dhall_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _rego_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return rego_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _yara_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return yara_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _hcl_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return hcl_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _bicep_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return bicep_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
def _tlaplus_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return tlaplus_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _haxe_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return haxe_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _v_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return v_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _elm_module_aliases_for_path(*, root_path: Path, file_path: str, text: str | None = None) -> set[str]:
    return elm_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
def _actionscript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return actionscript_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _angelscript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return angelscript_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _scratch_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return scratch_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _smalltalk_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return smalltalk_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _starlark_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return starlark_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )
def _factor_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return factor_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _cue_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return cue_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _vimscript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return vimscript_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _assembly_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return assembly_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        # Assembly resolves call/extern references (references_symbol graph edges)
        # through the module index, so the index MUST carry symbol-level aliases
        # (e.g. `print_string` -> the defining file). Skipping them drops those edges.
        include_symbol_aliases=True,
    )


def _prolog_module_aliases_for_path(*, root_path: Path, file_path: str, text: str | None = None) -> set[str]:
    return prolog_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )


def _foxpro_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return foxpro_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _cobol_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return cobol_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _vbscript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return vbscript_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _applescript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return applescript_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _vba_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return vba_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )


def _visual_basic_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return visual_basic_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _classic_visual_basic_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return classic_visual_basic_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )


def _pascal_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return pascal_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _delphi_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return delphi_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _sql_module_aliases_for_path(*, root_path: Path, file_path: str, text: str | None = None) -> set[str]:
    return sql_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )


def _tsql_module_aliases_for_path(*, root_path: Path, file_path: str, text: str | None = None) -> set[str]:
    return tsql_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )


def _ladder_module_aliases_for_path(*, root_path: Path, file_path: str, text: str | None = None) -> set[str]:
    return ladder_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )


def _labview_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return labview_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _plsql_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return plsql_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )

def _rpg_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return rpg_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )

def _sas_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return sas_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )

def _fortran_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return fortran_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )

def _matlab_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return matlab_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )

def _ml_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return ml_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )


def _objective_c_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return objective_c_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _wolfram_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return wolfram_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )


def _d_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return d_language_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )


def _solidity_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return solidity_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _gdscript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return gdscript_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _gml_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return gml_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _systemverilog_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return systemverilog_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        # SystemVerilog resolves symbol references (references_symbol graph edges)
        # through the module index, which therefore must carry symbol-level aliases.
        include_symbol_aliases=True,
    )


def _verilog_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return verilog_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _vhdl_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return vhdl_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )

def _tcl_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return tcl_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _xpp_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return xpp_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )


def _robotframework_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return robotframework_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _gherkin_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return gherkin_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _antlr_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return antlr_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _apacheconf_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    if not apacheconf_adapter.has_apacheconf_path_hints(Path(file_path)):
        return set()
    return apacheconf_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )
def _aspectj_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    if not aspectj_adapter.has_aspectj_path_hints(path=Path(file_path)):
        return set()
    return aspectj_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )
_graphviz_module_aliases_for_path = lambda *, root_path, file_path: graphviz_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_mermaid_module_aliases_for_path = lambda *, root_path, file_path: mermaid_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_plantuml_module_aliases_for_path = lambda *, root_path, file_path: plantuml_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_openqasm_module_aliases_for_path = lambda *, root_path, file_path: openqasm_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_move_module_aliases_for_path = lambda *, root_path, file_path: move_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _dm_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return dm_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )


def _scss_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return scss_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )


def _less_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return less_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )


def _stylus_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return stylus_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
        include_symbol_aliases=False,
    )
def _jinja_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return jinja_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _liquid_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return liquid_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
def _handlebars_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return handlebars_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _mustache_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return mustache_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
_nunjucks_module_aliases_for_path = lambda *, root_path, file_path: nunjucks_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _twig_module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    text: str | None = None,
) -> set[str]:
    return twig_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
        text=text,
    )
_haml_module_aliases_for_path = lambda *, root_path, file_path: haml_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_slim_module_aliases_for_path = lambda *, root_path, file_path: slim_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_smarty_module_aliases_for_path = lambda *, root_path, file_path: smarty_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_erb_module_aliases_for_path = lambda *, root_path, file_path: erb_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _pug_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return pug_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _ejs_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return ejs_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _blade_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return blade_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
