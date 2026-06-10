# ruff: noqa: I001
from __future__ import annotations
import re
from pathlib import Path
from typing import Any
from apps.api_server.services import repository_intelligence_pascal_solidity_dispatch as repository_pascal_solidity_dispatch
from apps.api_server.services.repository_intelligence_adapters import abap as abap_adapter, actionscript as actionscript_adapter, ada as ada_adapter, agda as agda_adapter, apex as apex_adapter, applescript as applescript_adapter, assembly as assembly_adapter, autohotkey as autohotkey_adapter, autoit as autoit_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import awk as awk_adapter, batchfile as batchfile_adapter
from apps.api_server.services.repository_intelligence_adapters import antlr as antlr_adapter, asciidoc as asciidoc_adapter, astro as astro_adapter, blade as blade_adapter, cuda as cuda_adapter, cython as cython_adapter, dm as dm_adapter, dockerfile as dockerfile_adapter, ejs as ejs_adapter, erb as erb_adapter, fennel as fennel_adapter, gherkin as gherkin_adapter, graphviz as graphviz_adapter, haml as haml_adapter, handlebars as handlebars_adapter, hlsl as hlsl_adapter, hy as hy_adapter, jinja as jinja_adapter, just as just_adapter, less as less_adapter, liquid as liquid_adapter, mermaid as mermaid_adapter, modelica as modelica_adapter, moonbit as moonbit_adapter, move as move_adapter, mustache as mustache_adapter, nextflow as nextflow_adapter, nunjucks as nunjucks_adapter, openqasm as openqasm_adapter, org as org_adapter, plantuml as plantuml_adapter, protobuf as protobuf_adapter, pug as pug_adapter, rescript as rescript_adapter, roc as roc_adapter, rst as rst_adapter, scss as scss_adapter, shaderlab as shaderlab_adapter, slim as slim_adapter, smarty as smarty_adapter, squirrel as squirrel_adapter, stan as stan_adapter, stylus as stylus_adapter, svelte as svelte_adapter, tex as tex_adapter, twig as twig_adapter, typst as typst_adapter, vue as vue_adapter, wgsl as wgsl_adapter, wren as wren_adapter, vyper as vyper_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import (
    al as al_adapter,
    clojurescript as clojurescript_adapter,
    groovy as groovy_adapter,
    opencl as opencl_adapter,
    qsharp as qsharp_adapter,
    sass as sass_adapter,
    sml as sml_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import cfml as cfml_adapter, classic_visual_basic as classic_visual_basic_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    clojure as clojure_adapter,
    cmake as cmake_adapter,
    cobol as cobol_adapter,
    coffeescript as coffeescript_adapter,
    meson as meson_adapter,
    qmake as qmake_adapter,
    qml as qml_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import chapel as chapel_adapter, coq as coq_adapter, eiffel as eiffel_adapter, lean as lean_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import crystal as crystal_adapter
from apps.api_server.services.repository_intelligence_adapters import d_language as d_language_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    delphi as delphi_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import dhall as dhall_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    elixir as elixir_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import elm as elm_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    emacslisp as emacslisp_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    erlang as erlang_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import cue as cue_adapter, factor as factor_adapter, fish as fish_adapter, makefile as makefile_adapter, odin as odin_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import (
    fortran as fortran_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    foxpro as foxpro_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    fsharp as fsharp_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gams as gams_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gdscript as gdscript_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import gleam as gleam_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    gml as gml_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    haskell as haskell_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import haxe as haxe_adapter, hcl as hcl_adapter, bicep as bicep_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import idris as idris_adapter
from apps.api_server.services.repository_intelligence_adapters import janet as janet_adapter
from apps.api_server.services.repository_intelligence_adapters import tlaplus as tlaplus_adapter, rego as rego_adapter
from apps.api_server.services.repository_intelligence_adapters import yara as yara_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    julia as julia_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import jvm as jvm_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    labview as labview_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ladder as ladder_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    lisp as lisp_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    lua as lua_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    luau as luau_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    matlab as matlab_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ml as ml_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import mql5 as mql5_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    nim as nim_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import nix as nix_adapter
from apps.api_server.services.repository_intelligence_adapters import nushell as nushell_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    objective_c as objective_c_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ocaml as ocaml_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    openscad as openscad_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    pascal as pascal_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    perl as perl_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    php as php_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    puppet as puppet_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    plsql as plsql_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    prolog as prolog_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    purescript as purescript_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    r_language as r_language_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    racket as racket_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import raku as raku_adapter
from apps.api_server.services.repository_intelligence_adapters import rpg as rpg_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    ruby as ruby_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    robotframework as robotframework_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    sas as sas_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    scheme as scheme_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    scratch as scratch_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    smalltalk as smalltalk_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    solidity as solidity_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    sql as sql_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    starlark as starlark_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    systemverilog as systemverilog_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    tcl as tcl_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    tsql as tsql_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import vala as vala_adapter
from apps.api_server.services.repository_intelligence_adapters import vba as vba_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    vbscript as vbscript_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    verilog as verilog_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import vhdl as vhdl_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    vimscript as vimscript_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    visual_basic as visual_basic_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import vlang as v_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    wolfram as wolfram_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import xpp as xpp_adapter
from apps.api_server.services.repository_intelligence_indexing import (
    _normalize_repository_relative_path,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier
_scala_package_aliases_for_path = jvm_adapter.scala_package_aliases_for_path
_jvm_declared_type_aliases_for_path = jvm_adapter.declared_type_aliases_for_path
_crystal_declared_type_aliases_for_path = crystal_adapter.declared_type_aliases_for_path
_haskell_module_aliases_for_path = haskell_adapter.module_aliases_for_path
_ocaml_module_aliases_for_path = ocaml_adapter.module_aliases_for_path
_perl_module_aliases_for_path = perl_adapter.module_aliases_for_path
_php_module_aliases_for_path = php_adapter.module_aliases_for_path
_ruby_module_aliases_for_path = ruby_adapter.module_aliases_for_path
_nim_module_aliases_for_path = nim_adapter.module_aliases_for_path
_extract_clojure_ns_form, _clojure_namespace_path, _clojure_module_aliases_for_path = (
    clojure_adapter.extract_ns_form,
    clojure_adapter.namespace_path,
    clojure_adapter.module_aliases_for_path,
)
_is_nim_declared_symbol_alias = nim_adapter.is_declared_symbol_alias
_fsharp_path_aliases = fsharp_adapter.path_aliases
_fsharp_namespaces_from_text = fsharp_adapter.namespaces_from_text
_fsharp_open_targets = fsharp_adapter.open_targets
_crystal_constant_aliases_for_file = crystal_adapter.constant_aliases_for_file
_is_crystal_constant_alias = crystal_adapter.is_constant_alias
_elixir_module_aliases_for_path = elixir_adapter.module_aliases_for_path
_erlang_module_aliases_for_path = erlang_adapter.module_aliases_for_path
(
    _normalize_pascal_target,
    _normalize_pascal_symbol_name,
    _strip_pascal_comments,
    _pascal_unit_name,
    _pascal_uses_targets,
    _collect_pascal_symbol_entries,
) = (
    repository_pascal_solidity_dispatch._normalize_pascal_target,
    repository_pascal_solidity_dispatch._normalize_pascal_symbol_name,
    repository_pascal_solidity_dispatch._strip_pascal_comments,
    repository_pascal_solidity_dispatch._pascal_unit_name,
    repository_pascal_solidity_dispatch._pascal_uses_targets,
    repository_pascal_solidity_dispatch._collect_pascal_symbol_entries,
)
def _nim_declared_symbol_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return nim_adapter.declared_symbol_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
    )
def _camelize_identifier(value: str) -> str:
    normalized_value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not normalized_value:
        return ""
    return "".join(piece.capitalize() for piece in normalized_value.split("_") if piece)
def _r_package_context_for_path(
    *,
    root_path: Path,
    file_path: str,
) -> tuple[str | None, str | None]:
    return r_language_adapter.package_context_for_path(
        root_path=root_path,
        file_path=file_path,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )
def _julia_package_context_for_path(
    *,
    root_path: Path,
    file_path: str,
) -> tuple[str | None, str | None]:
    return julia_adapter.package_context_for_path(
        root_path=root_path,
        file_path=file_path,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )
def _r_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return r_language_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )
def _julia_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return julia_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )

def _lisp_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return lisp_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _puppet_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return puppet_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _emacslisp_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return emacslisp_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _fish_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return fish_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _racket_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return racket_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _scheme_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return scheme_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _lua_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return lua_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path)


def _luau_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return luau_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path)


def _normalize_fortran_name(raw_name: str) -> str:
    return fortran_adapter.normalize_name(raw_name)


def _normalize_ada_unit_name(raw_name: str) -> str:
    return ada_adapter.normalize_unit_name(raw_name)


def _strip_ada_comments(text: str) -> str:
    return ada_adapter.strip_comments(text)


def _collect_ada_symbol_entries(
    text: str,
    *,
    file_path: str,
) -> list[dict[str, Any]]:
    return ada_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _normalize_d_module_name(raw_name: str) -> str:
    return d_language_adapter.normalize_module_name(raw_name)


def _strip_d_comments(text: str) -> str:
    return d_language_adapter.strip_comments(text)


def _d_statement_entries(text: str) -> tuple[tuple[int, str], ...]:
    return d_language_adapter.statement_entries(text)


def _collect_d_symbol_entries(
    text: str,
    *,
    file_path: str,
) -> list[dict[str, Any]]:
    return d_language_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _is_fortran_declared_symbol_alias(value: str) -> bool:
    return fortran_adapter.is_declared_symbol_alias(value)


def _fortran_statement_entries(text: str) -> tuple[tuple[int, str], ...]:
    return fortran_adapter.statement_entries(text)


def _collect_fortran_symbol_entries(
    text: str,
    *,
    file_path: str,
) -> list[dict[str, Any]]:
    return fortran_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _collect_fsharp_symbol_entries(
    text: str,
    *,
    file_path: str,
) -> list[dict[str, Any]]:
    return fsharp_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _fsharp_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return fsharp_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _abap_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return abap_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _ada_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return ada_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )
def _apex_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return apex_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _awk_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return awk_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _batchfile_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return batchfile_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _makefile_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return makefile_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _just_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return just_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _dockerfile_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return dockerfile_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _cython_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return cython_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _cuda_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return cuda_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _hlsl_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return hlsl_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _wgsl_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return wgsl_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _shaderlab_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return shaderlab_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _stan_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return stan_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _protobuf_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return protobuf_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _tex_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return tex_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _rst_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return rst_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _asciidoc_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return asciidoc_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _org_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return org_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _typst_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return typst_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _cmake_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return cmake_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _meson_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return meson_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _qmake_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return qmake_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _qml_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return qml_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _vue_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return vue_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _astro_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return astro_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _svelte_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return svelte_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _odin_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return odin_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _autohotkey_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return autohotkey_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _autoit_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return autoit_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _squirrel_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return squirrel_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _cfml_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return cfml_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _coffeescript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return coffeescript_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _vala_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return vala_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _mql5_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return mql5_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _gams_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return gams_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _nix_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return nix_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _nushell_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return nushell_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )

def _openscad_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return openscad_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _purescript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return purescript_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _rescript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return rescript_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
_modelica_module_aliases_for_path = lambda *, root_path, file_path: modelica_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_roc_module_aliases_for_path = lambda *, root_path, file_path: roc_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _agda_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return agda_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _idris_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return idris_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _raku_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return raku_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _gleam_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return gleam_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
_hy_module_aliases_for_path = lambda *, root_path, file_path: hy_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_wren_module_aliases_for_path = lambda *, root_path, file_path: wren_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_fennel_module_aliases_for_path = lambda *, root_path, file_path: fennel_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_vyper_module_aliases_for_path = lambda *, root_path, file_path: vyper_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_sass_module_aliases_for_path = lambda *, root_path, file_path: sass_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_qsharp_module_aliases_for_path = lambda *, root_path, file_path: qsharp_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_opencl_module_aliases_for_path = lambda *, root_path, file_path: opencl_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _clojurescript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return clojurescript_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
    )
_al_module_aliases_for_path = lambda *, root_path, file_path: al_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_sml_module_aliases_for_path = lambda *, root_path, file_path: sml_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_groovy_module_aliases_for_path = lambda *, root_path, file_path: groovy_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_nextflow_module_aliases_for_path = lambda *, root_path, file_path: nextflow_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_moonbit_module_aliases_for_path = lambda *, root_path, file_path: moonbit_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _chapel_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return chapel_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _coq_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return coq_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _lean_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return lean_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
def _eiffel_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return eiffel_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E501
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
def _bicep_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return bicep_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _tlaplus_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return tlaplus_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _haxe_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return haxe_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _v_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return v_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _elm_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return elm_adapter.module_aliases_for_path(
        root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier
    )
def _actionscript_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return actionscript_adapter.module_aliases_for_path(
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


def _assembly_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return assembly_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _prolog_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return prolog_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
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


def _vba_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return vba_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _visual_basic_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return visual_basic_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _classic_visual_basic_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return classic_visual_basic_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
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


def _sql_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return sql_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _tsql_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return tsql_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _ladder_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return ladder_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
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

def _sas_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return sas_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )

def _fortran_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return fortran_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )

def _matlab_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return matlab_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )

def _ml_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return ml_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _objective_c_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return objective_c_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _wolfram_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return wolfram_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
    )


def _d_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return d_language_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
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


def _systemverilog_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    return systemverilog_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=_stable_identifier,
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
def _xpp_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return xpp_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _robotframework_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return robotframework_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _gherkin_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return gherkin_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _antlr_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return antlr_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
_graphviz_module_aliases_for_path = lambda *, root_path, file_path: graphviz_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_mermaid_module_aliases_for_path = lambda *, root_path, file_path: mermaid_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_plantuml_module_aliases_for_path = lambda *, root_path, file_path: plantuml_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_openqasm_module_aliases_for_path = lambda *, root_path, file_path: openqasm_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_move_module_aliases_for_path = lambda *, root_path, file_path: move_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier); _dm_module_aliases_for_path = lambda *, root_path, file_path: dm_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501,E702
def _scss_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return scss_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _less_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return less_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _stylus_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return stylus_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _jinja_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return jinja_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _liquid_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return liquid_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _handlebars_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return handlebars_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
_mustache_module_aliases_for_path = lambda *, root_path, file_path: mustache_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_nunjucks_module_aliases_for_path = lambda *, root_path, file_path: nunjucks_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_twig_module_aliases_for_path = lambda *, root_path, file_path: twig_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_haml_module_aliases_for_path = lambda *, root_path, file_path: haml_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_slim_module_aliases_for_path = lambda *, root_path, file_path: slim_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_smarty_module_aliases_for_path = lambda *, root_path, file_path: smarty_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
_erb_module_aliases_for_path = lambda *, root_path, file_path: erb_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)  # noqa: E731,E501
def _pug_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return pug_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _ejs_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return ejs_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
def _blade_module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]: return blade_adapter.module_aliases_for_path(root_path=root_path, file_path=file_path, stable_identifier=_stable_identifier)
_ROOT_SCOPED_MODULE_ALIAS_BUILDERS = (
    _clojure_module_aliases_for_path,
    _crystal_declared_type_aliases_for_path,
    _erlang_module_aliases_for_path,
    _lua_module_aliases_for_path,
    _luau_module_aliases_for_path,
    _elixir_module_aliases_for_path,
    _scala_package_aliases_for_path,
    _jvm_declared_type_aliases_for_path, _robotframework_module_aliases_for_path, _gherkin_module_aliases_for_path, _antlr_module_aliases_for_path, _graphviz_module_aliases_for_path, _mermaid_module_aliases_for_path, _plantuml_module_aliases_for_path, _openqasm_module_aliases_for_path, _move_module_aliases_for_path, _dm_module_aliases_for_path,
    _scss_module_aliases_for_path, _less_module_aliases_for_path, _stylus_module_aliases_for_path, _jinja_module_aliases_for_path, _liquid_module_aliases_for_path, _handlebars_module_aliases_for_path, _mustache_module_aliases_for_path, _nunjucks_module_aliases_for_path, _twig_module_aliases_for_path, _haml_module_aliases_for_path, _slim_module_aliases_for_path, _smarty_module_aliases_for_path, _erb_module_aliases_for_path, _pug_module_aliases_for_path, _ejs_module_aliases_for_path, _blade_module_aliases_for_path, _fsharp_module_aliases_for_path,
    _abap_module_aliases_for_path,
    _ada_module_aliases_for_path,
    _apex_module_aliases_for_path,
    _batchfile_module_aliases_for_path,
    _makefile_module_aliases_for_path,
    _just_module_aliases_for_path,
    _dockerfile_module_aliases_for_path,
    _cuda_module_aliases_for_path,
    _hlsl_module_aliases_for_path,
    _wgsl_module_aliases_for_path,
    _shaderlab_module_aliases_for_path,
    _cython_module_aliases_for_path,
    _stan_module_aliases_for_path,
    _protobuf_module_aliases_for_path,
    _tex_module_aliases_for_path,
    _rst_module_aliases_for_path, _asciidoc_module_aliases_for_path, _org_module_aliases_for_path,
    _typst_module_aliases_for_path,
    _cmake_module_aliases_for_path,
    _meson_module_aliases_for_path,
    _qmake_module_aliases_for_path,
    _qml_module_aliases_for_path,
    _vue_module_aliases_for_path,
    _astro_module_aliases_for_path,
    _svelte_module_aliases_for_path,
    _odin_module_aliases_for_path,
    _autohotkey_module_aliases_for_path,
    _autoit_module_aliases_for_path,
    _squirrel_module_aliases_for_path,
    _awk_module_aliases_for_path,
    _cfml_module_aliases_for_path,
    _coffeescript_module_aliases_for_path,
    _vala_module_aliases_for_path,
    _mql5_module_aliases_for_path,
    _gams_module_aliases_for_path,
    _nix_module_aliases_for_path,
    _nushell_module_aliases_for_path,
    _fish_module_aliases_for_path,
    _openscad_module_aliases_for_path,
    _purescript_module_aliases_for_path,
    _rescript_module_aliases_for_path, _modelica_module_aliases_for_path, _roc_module_aliases_for_path,
    _agda_module_aliases_for_path,
    _idris_module_aliases_for_path,
    _raku_module_aliases_for_path,
    _gleam_module_aliases_for_path,
    _hy_module_aliases_for_path, _wren_module_aliases_for_path, _fennel_module_aliases_for_path, _vyper_module_aliases_for_path, _sass_module_aliases_for_path, _qsharp_module_aliases_for_path, _opencl_module_aliases_for_path, _clojurescript_module_aliases_for_path, _al_module_aliases_for_path, _sml_module_aliases_for_path, _groovy_module_aliases_for_path, _nextflow_module_aliases_for_path, _moonbit_module_aliases_for_path,
    _chapel_module_aliases_for_path, _coq_module_aliases_for_path, _lean_module_aliases_for_path, _eiffel_module_aliases_for_path,  # noqa: E501
    _janet_module_aliases_for_path,
    _dhall_module_aliases_for_path,
    _rego_module_aliases_for_path,
    _yara_module_aliases_for_path,
    _hcl_module_aliases_for_path,
    _bicep_module_aliases_for_path, _tlaplus_module_aliases_for_path, _haxe_module_aliases_for_path,
    _v_module_aliases_for_path,
    _elm_module_aliases_for_path,
    _actionscript_module_aliases_for_path,
    _scratch_module_aliases_for_path,
    _smalltalk_module_aliases_for_path,
    _starlark_module_aliases_for_path,
    _factor_module_aliases_for_path,
    _cue_module_aliases_for_path,
    _vimscript_module_aliases_for_path,
    _assembly_module_aliases_for_path,
    _prolog_module_aliases_for_path,
    _foxpro_module_aliases_for_path,
    _cobol_module_aliases_for_path,
    _vbscript_module_aliases_for_path,
    _applescript_module_aliases_for_path,
    _vba_module_aliases_for_path,
    _visual_basic_module_aliases_for_path,
    _classic_visual_basic_module_aliases_for_path,
    _pascal_module_aliases_for_path,
    _delphi_module_aliases_for_path,
    _sql_module_aliases_for_path,
    _tsql_module_aliases_for_path,
    _ladder_module_aliases_for_path,
    _labview_module_aliases_for_path,
    _plsql_module_aliases_for_path,
    _rpg_module_aliases_for_path,
    _sas_module_aliases_for_path,
    _fortran_module_aliases_for_path,
    _matlab_module_aliases_for_path,
    _ml_module_aliases_for_path,
    _lisp_module_aliases_for_path,
    _puppet_module_aliases_for_path,
    _emacslisp_module_aliases_for_path,
    _scheme_module_aliases_for_path,
    _racket_module_aliases_for_path,
    _objective_c_module_aliases_for_path,
    _wolfram_module_aliases_for_path,
    _xpp_module_aliases_for_path,
    _d_module_aliases_for_path,
    _solidity_module_aliases_for_path,
    _gdscript_module_aliases_for_path,
    _gml_module_aliases_for_path,
    _verilog_module_aliases_for_path,
    _systemverilog_module_aliases_for_path,
    _vhdl_module_aliases_for_path,
    _tcl_module_aliases_for_path,
    _haskell_module_aliases_for_path,
    _ocaml_module_aliases_for_path,
    _perl_module_aliases_for_path,
    _php_module_aliases_for_path,
    _ruby_module_aliases_for_path,
    _r_module_aliases_for_path,
    _nim_module_aliases_for_path, _nim_declared_symbol_aliases_for_path,
    _julia_module_aliases_for_path,
)
