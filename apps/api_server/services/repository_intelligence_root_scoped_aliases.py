# ruff: noqa: I001
from __future__ import annotations
from collections.abc import Callable, Iterable
from functools import lru_cache
import re
from pathlib import Path
from typing import Any
from apps.api_server.services import repository_intelligence_adapters as repository_adapters
from apps.api_server.services.repository_intelligence_indexing import (
    _normalize_repository_relative_path,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier


class _LazyAdapterModule:
    # ``_overrides`` holds per-instance attribute overrides so callers (notably
    # ``pytest``'s ``monkeypatch.setattr``) can patch an adapter attribute on the
    # lazy wrapper without mutating the shared, real adapter module. Without it the
    # ``__slots__`` layout rejects ``setattr`` outright, which surfaced as setup/
    # teardown ``AttributeError``s across the suite.
    __slots__ = ("_adapter_name", "_overrides")

    def __init__(self, adapter_name: str) -> None:
        object.__setattr__(self, "_adapter_name", adapter_name)
        object.__setattr__(self, "_overrides", {})

    def _load(self):
        return getattr(repository_adapters, self._adapter_name)

    def __getattr__(self, name: str) -> object:
        # ``__getattr__`` only runs when normal lookup (slots/overrides) misses.
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        return getattr(self._load(), name)

    def __setattr__(self, name: str, value: object) -> None:
        if name in _LazyAdapterModule.__slots__:
            object.__setattr__(self, name, value)
            return
        object.__getattribute__(self, "_overrides")[name] = value

    def __delattr__(self, name: str) -> None:
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            del overrides[name]
            return
        # Deleting an attribute that was never overridden is a no-op restore
        # (the real adapter module still owns it); mirror monkeypatch's intent.
        raise AttributeError(name)

    def __dir__(self) -> list[str]:
        overrides = object.__getattribute__(self, "_overrides")
        return sorted(
            set(dir(type(self))) | set(overrides) | set(dir(self._load()))
        )


def _lazy_adapter_module(adapter_name: str) -> _LazyAdapterModule:
    return _LazyAdapterModule(adapter_name)


@lru_cache(maxsize=1)
def _pascal_solidity_dispatch_module():
    from apps.api_server.services import (
        repository_intelligence_pascal_solidity_dispatch as repository_pascal_solidity_dispatch,
    )

    return repository_pascal_solidity_dispatch


def _lazy_pascal_dispatch_attr(name: str) -> Callable[..., Any]:
    def _call(*args: Any, **kwargs: Any) -> Any:
        return getattr(_pascal_solidity_dispatch_module(), name)(*args, **kwargs)

    return _call


def _lazy_adapter_attr(adapter: _LazyAdapterModule, name: str) -> Callable[..., Any]:
    def _call(*args: Any, **kwargs: Any) -> Any:
        return getattr(adapter, name)(*args, **kwargs)

    return _call




abapcds_adapter = _lazy_adapter_module("abapcds")
aiken_adapter = _lazy_adapter_module("aiken")
alloy_adapter = _lazy_adapter_module("alloy")
angelscript_adapter = _lazy_adapter_module("angelscript")
answer_set_programming_adapter = _lazy_adapter_module("answer_set_programming")
apacheconf_adapter = _lazy_adapter_module("apacheconf")
asl_adapter = _lazy_adapter_module("asl")
aspectj_adapter = _lazy_adapter_module("aspectj")
aspnet_adapter = _lazy_adapter_module("aspnet")
ats_adapter = _lazy_adapter_module("ats")
freemarker_adapter = _lazy_adapter_module("freemarker")
onec_enterprise_adapter = _lazy_adapter_module("onec_enterprise")
abap_adapter = _lazy_adapter_module("abap")
actionscript_adapter = _lazy_adapter_module("actionscript")
ada_adapter = _lazy_adapter_module("ada")
agda_adapter = _lazy_adapter_module("agda")
apex_adapter = _lazy_adapter_module("apex")
applescript_adapter = _lazy_adapter_module("applescript")
assembly_adapter = _lazy_adapter_module("assembly")
autohotkey_adapter = _lazy_adapter_module("autohotkey")
autoit_adapter = _lazy_adapter_module("autoit")
awk_adapter = _lazy_adapter_module("awk")
batchfile_adapter = _lazy_adapter_module("batchfile")
antlr_adapter = _lazy_adapter_module("antlr")
asciidoc_adapter = _lazy_adapter_module("asciidoc")
astro_adapter = _lazy_adapter_module("astro")
blade_adapter = _lazy_adapter_module("blade")
cairo_adapter = _lazy_adapter_module("cairo")
cuda_adapter = _lazy_adapter_module("cuda")
cython_adapter = _lazy_adapter_module("cython")
dm_adapter = _lazy_adapter_module("dm")
dockerfile_adapter = _lazy_adapter_module("dockerfile")
ejs_adapter = _lazy_adapter_module("ejs")
erb_adapter = _lazy_adapter_module("erb")
fennel_adapter = _lazy_adapter_module("fennel")
gherkin_adapter = _lazy_adapter_module("gherkin")
graphviz_adapter = _lazy_adapter_module("graphviz")
haml_adapter = _lazy_adapter_module("haml")
handlebars_adapter = _lazy_adapter_module("handlebars")
hlsl_adapter = _lazy_adapter_module("hlsl")
hy_adapter = _lazy_adapter_module("hy")
jinja_adapter = _lazy_adapter_module("jinja")
just_adapter = _lazy_adapter_module("just")
less_adapter = _lazy_adapter_module("less")
liquid_adapter = _lazy_adapter_module("liquid")
mermaid_adapter = _lazy_adapter_module("mermaid")
modelica_adapter = _lazy_adapter_module("modelica")
moonbit_adapter = _lazy_adapter_module("moonbit")
move_adapter = _lazy_adapter_module("move")
mustache_adapter = _lazy_adapter_module("mustache")
nextflow_adapter = _lazy_adapter_module("nextflow")
nunjucks_adapter = _lazy_adapter_module("nunjucks")
openqasm_adapter = _lazy_adapter_module("openqasm")
org_adapter = _lazy_adapter_module("org")
plantuml_adapter = _lazy_adapter_module("plantuml")
protobuf_adapter = _lazy_adapter_module("protobuf")
pug_adapter = _lazy_adapter_module("pug")
reasonml_adapter = _lazy_adapter_module("reasonml")
rescript_adapter = _lazy_adapter_module("rescript")
roc_adapter = _lazy_adapter_module("roc")
rst_adapter = _lazy_adapter_module("rst")
scss_adapter = _lazy_adapter_module("scss")
shaderlab_adapter = _lazy_adapter_module("shaderlab")
slim_adapter = _lazy_adapter_module("slim")
smarty_adapter = _lazy_adapter_module("smarty")
squirrel_adapter = _lazy_adapter_module("squirrel")
stan_adapter = _lazy_adapter_module("stan")
stylus_adapter = _lazy_adapter_module("stylus")
svelte_adapter = _lazy_adapter_module("svelte")
sway_adapter = _lazy_adapter_module("sway")
tex_adapter = _lazy_adapter_module("tex")
twig_adapter = _lazy_adapter_module("twig")
typst_adapter = _lazy_adapter_module("typst")
vue_adapter = _lazy_adapter_module("vue")
wgsl_adapter = _lazy_adapter_module("wgsl")
wren_adapter = _lazy_adapter_module("wren")
vyper_adapter = _lazy_adapter_module("vyper")
al_adapter = _lazy_adapter_module("al")
ballerina_adapter = _lazy_adapter_module("ballerina")
clojurescript_adapter = _lazy_adapter_module("clojurescript")
four_d_adapter = _lazy_adapter_module("four_d")
graphql_adapter = _lazy_adapter_module("graphql")
groovy_adapter = _lazy_adapter_module("groovy")
opencl_adapter = _lazy_adapter_module("opencl")
pkl_adapter = _lazy_adapter_module("pkl")
plpgsql_adapter = _lazy_adapter_module("plpgsql")
qsharp_adapter = _lazy_adapter_module("qsharp")
sass_adapter = _lazy_adapter_module("sass")
sml_adapter = _lazy_adapter_module("sml")
webassembly_adapter = _lazy_adapter_module("webassembly")
xtend_adapter = _lazy_adapter_module("xtend")
cfml_adapter = _lazy_adapter_module("cfml")
classic_visual_basic_adapter = _lazy_adapter_module("classic_visual_basic")
clojure_adapter = _lazy_adapter_module("clojure")
cmake_adapter = _lazy_adapter_module("cmake")
cobol_adapter = _lazy_adapter_module("cobol")
coffeescript_adapter = _lazy_adapter_module("coffeescript")
meson_adapter = _lazy_adapter_module("meson")
qmake_adapter = _lazy_adapter_module("qmake")
qml_adapter = _lazy_adapter_module("qml")
chapel_adapter = _lazy_adapter_module("chapel")
coq_adapter = _lazy_adapter_module("coq")
eiffel_adapter = _lazy_adapter_module("eiffel")
lean_adapter = _lazy_adapter_module("lean")
crystal_adapter = _lazy_adapter_module("crystal")
d_language_adapter = _lazy_adapter_module("d_language")
delphi_adapter = _lazy_adapter_module("delphi")
dhall_adapter = _lazy_adapter_module("dhall")
elixir_adapter = _lazy_adapter_module("elixir")
elm_adapter = _lazy_adapter_module("elm")
emacslisp_adapter = _lazy_adapter_module("emacslisp")
erlang_adapter = _lazy_adapter_module("erlang")
cue_adapter = _lazy_adapter_module("cue")
factor_adapter = _lazy_adapter_module("factor")
fish_adapter = _lazy_adapter_module("fish")
makefile_adapter = _lazy_adapter_module("makefile")
odin_adapter = _lazy_adapter_module("odin")
fortran_adapter = _lazy_adapter_module("fortran")
foxpro_adapter = _lazy_adapter_module("foxpro")
fsharp_adapter = _lazy_adapter_module("fsharp")
gams_adapter = _lazy_adapter_module("gams")
gdscript_adapter = _lazy_adapter_module("gdscript")
gleam_adapter = _lazy_adapter_module("gleam")
gml_adapter = _lazy_adapter_module("gml")
haskell_adapter = _lazy_adapter_module("haskell")
haxe_adapter = _lazy_adapter_module("haxe")
hcl_adapter = _lazy_adapter_module("hcl")
bicep_adapter = _lazy_adapter_module("bicep")
idris_adapter = _lazy_adapter_module("idris")
janet_adapter = _lazy_adapter_module("janet")
tlaplus_adapter = _lazy_adapter_module("tlaplus")
rego_adapter = _lazy_adapter_module("rego")
yara_adapter = _lazy_adapter_module("yara")
julia_adapter = _lazy_adapter_module("julia")
jvm_adapter = _lazy_adapter_module("jvm")
labview_adapter = _lazy_adapter_module("labview")
ladder_adapter = _lazy_adapter_module("ladder")
lisp_adapter = _lazy_adapter_module("lisp")
lua_adapter = _lazy_adapter_module("lua")
luau_adapter = _lazy_adapter_module("luau")
matlab_adapter = _lazy_adapter_module("matlab")
ml_adapter = _lazy_adapter_module("ml")
mql5_adapter = _lazy_adapter_module("mql5")
nim_adapter = _lazy_adapter_module("nim")
nix_adapter = _lazy_adapter_module("nix")
nushell_adapter = _lazy_adapter_module("nushell")
objective_c_adapter = _lazy_adapter_module("objective_c")
ocaml_adapter = _lazy_adapter_module("ocaml")
openscad_adapter = _lazy_adapter_module("openscad")
pascal_adapter = _lazy_adapter_module("pascal")
perl_adapter = _lazy_adapter_module("perl")
php_adapter = _lazy_adapter_module("php")
puppet_adapter = _lazy_adapter_module("puppet")
plsql_adapter = _lazy_adapter_module("plsql")
prolog_adapter = _lazy_adapter_module("prolog")
purescript_adapter = _lazy_adapter_module("purescript")
r_language_adapter = _lazy_adapter_module("r_language")
racket_adapter = _lazy_adapter_module("racket")
raku_adapter = _lazy_adapter_module("raku")
rpg_adapter = _lazy_adapter_module("rpg")
ruby_adapter = _lazy_adapter_module("ruby")
robotframework_adapter = _lazy_adapter_module("robotframework")
sas_adapter = _lazy_adapter_module("sas")
scheme_adapter = _lazy_adapter_module("scheme")
scratch_adapter = _lazy_adapter_module("scratch")
smalltalk_adapter = _lazy_adapter_module("smalltalk")
solidity_adapter = _lazy_adapter_module("solidity")
sql_adapter = _lazy_adapter_module("sql")
starlark_adapter = _lazy_adapter_module("starlark")
systemverilog_adapter = _lazy_adapter_module("systemverilog")
tcl_adapter = _lazy_adapter_module("tcl")
tsql_adapter = _lazy_adapter_module("tsql")
vala_adapter = _lazy_adapter_module("vala")
vba_adapter = _lazy_adapter_module("vba")
vbscript_adapter = _lazy_adapter_module("vbscript")
verilog_adapter = _lazy_adapter_module("verilog")
vhdl_adapter = _lazy_adapter_module("vhdl")
vimscript_adapter = _lazy_adapter_module("vimscript")
visual_basic_adapter = _lazy_adapter_module("visual_basic")
v_adapter = _lazy_adapter_module("vlang")
wolfram_adapter = _lazy_adapter_module("wolfram")
xpp_adapter = _lazy_adapter_module("xpp")




















_normalize_pascal_target = _lazy_pascal_dispatch_attr("_normalize_pascal_target")
_normalize_pascal_symbol_name = _lazy_pascal_dispatch_attr(
    "_normalize_pascal_symbol_name"
)
_strip_pascal_comments = _lazy_pascal_dispatch_attr("_strip_pascal_comments")
_pascal_unit_name = _lazy_pascal_dispatch_attr("_pascal_unit_name")
_pascal_uses_targets = _lazy_pascal_dispatch_attr("_pascal_uses_targets")
_collect_pascal_symbol_entries = _lazy_pascal_dispatch_attr(
    "_collect_pascal_symbol_entries"
)

# --- builder functions/helpers were split into sibling modules for size;
# re-import them here (after the adapter globals above) so the registry below
# can reference them and the public import surface stays unchanged ---
from apps.api_server.services.repository_intelligence_root_scoped_aliases_builders_a import (
    _nim_declared_symbol_aliases_for_path,
    _camelize_identifier,
    _r_package_context_for_path,
    _julia_package_context_for_path,
    _r_module_aliases_for_path,
    _julia_module_aliases_for_path,
    _lisp_module_aliases_for_path,
    _puppet_module_aliases_for_path,
    _emacslisp_module_aliases_for_path,
    _fish_module_aliases_for_path,
    _racket_module_aliases_for_path,
    _scheme_module_aliases_for_path,
    _lua_module_aliases_for_path,
    _luau_module_aliases_for_path,
    _normalize_fortran_name,
    _normalize_ada_unit_name,
    _strip_ada_comments,
    _collect_ada_symbol_entries,
    _normalize_d_module_name,
    _strip_d_comments,
    _d_statement_entries,
    _collect_d_symbol_entries,
    _is_fortran_declared_symbol_alias,
    _fortran_statement_entries,
    _collect_fortran_symbol_entries,
    _collect_fsharp_symbol_entries,
    _fsharp_module_aliases_for_path,
    _abap_module_aliases_for_path,
    _abapcds_module_aliases_for_path,
    _onec_enterprise_module_aliases_for_path,
    _alloy_module_aliases_for_path,
    _aiken_module_aliases_for_path,
    _answer_set_programming_module_aliases_for_path,
    _asl_module_aliases_for_path,
    _ats_module_aliases_for_path,
    _aspnet_module_aliases_for_path,
    _ada_module_aliases_for_path,
    _four_d_module_aliases_for_path,
    _apex_module_aliases_for_path,
    _awk_module_aliases_for_path,
    _batchfile_module_aliases_for_path,
    _makefile_module_aliases_for_path,
    _just_module_aliases_for_path,
    _dockerfile_module_aliases_for_path,
    _cython_module_aliases_for_path,
    _cuda_module_aliases_for_path,
    _hlsl_module_aliases_for_path,
    _wgsl_module_aliases_for_path,
    _shaderlab_module_aliases_for_path,
    _stan_module_aliases_for_path,
    _protobuf_module_aliases_for_path,
    _tex_module_aliases_for_path,
    _rst_module_aliases_for_path,
    _asciidoc_module_aliases_for_path,
    _org_module_aliases_for_path,
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
    _cfml_module_aliases_for_path,
    _coffeescript_module_aliases_for_path,
    _vala_module_aliases_for_path,
    _mql5_module_aliases_for_path,
    _gams_module_aliases_for_path,
    _nix_module_aliases_for_path,
    _nushell_module_aliases_for_path,
    _openscad_module_aliases_for_path,
    _purescript_module_aliases_for_path,
    _cairo_module_aliases_for_path,
    _reasonml_module_aliases_for_path,
    _rescript_module_aliases_for_path,
    _sway_module_aliases_for_path,
    _modelica_module_aliases_for_path,
    _roc_module_aliases_for_path,
    _agda_module_aliases_for_path,
    _idris_module_aliases_for_path,
    _raku_module_aliases_for_path,
    _gleam_module_aliases_for_path,
    _hy_module_aliases_for_path,
    _wren_module_aliases_for_path,
    _fennel_module_aliases_for_path,
    _vyper_module_aliases_for_path,
    _sass_module_aliases_for_path,
    _qsharp_module_aliases_for_path,
    _opencl_module_aliases_for_path,
    _graphql_module_aliases_for_path,
    _pkl_module_aliases_for_path,
)
from apps.api_server.services.repository_intelligence_root_scoped_aliases_builders_b import (
    _plpgsql_module_aliases_for_path,
    _webassembly_module_aliases_for_path,
    _ballerina_module_aliases_for_path,
    _clojurescript_module_aliases_for_path,
    _al_module_aliases_for_path,
    _sml_module_aliases_for_path,
    _groovy_module_aliases_for_path,
    _xtend_module_aliases_for_path,
    _freemarker_module_aliases_for_path,
    _nextflow_module_aliases_for_path,
    _moonbit_module_aliases_for_path,
    _chapel_module_aliases_for_path,
    _coq_module_aliases_for_path,
    _lean_module_aliases_for_path,
    _eiffel_module_aliases_for_path,
    _janet_module_aliases_for_path,
    _dhall_module_aliases_for_path,
    _rego_module_aliases_for_path,
    _yara_module_aliases_for_path,
    _hcl_module_aliases_for_path,
    _bicep_module_aliases_for_path,
    _tlaplus_module_aliases_for_path,
    _haxe_module_aliases_for_path,
    _v_module_aliases_for_path,
    _elm_module_aliases_for_path,
    _actionscript_module_aliases_for_path,
    _angelscript_module_aliases_for_path,
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
    _objective_c_module_aliases_for_path,
    _wolfram_module_aliases_for_path,
    _d_module_aliases_for_path,
    _solidity_module_aliases_for_path,
    _gdscript_module_aliases_for_path,
    _gml_module_aliases_for_path,
    _systemverilog_module_aliases_for_path,
    _verilog_module_aliases_for_path,
    _vhdl_module_aliases_for_path,
    _tcl_module_aliases_for_path,
    _xpp_module_aliases_for_path,
    _robotframework_module_aliases_for_path,
    _gherkin_module_aliases_for_path,
    _antlr_module_aliases_for_path,
    _apacheconf_module_aliases_for_path,
    _aspectj_module_aliases_for_path,
    _graphviz_module_aliases_for_path,
    _mermaid_module_aliases_for_path,
    _plantuml_module_aliases_for_path,
    _openqasm_module_aliases_for_path,
    _move_module_aliases_for_path,
    _dm_module_aliases_for_path,
    _scss_module_aliases_for_path,
    _less_module_aliases_for_path,
    _stylus_module_aliases_for_path,
    _jinja_module_aliases_for_path,
    _liquid_module_aliases_for_path,
    _handlebars_module_aliases_for_path,
    _mustache_module_aliases_for_path,
    _nunjucks_module_aliases_for_path,
    _twig_module_aliases_for_path,
    _haml_module_aliases_for_path,
    _slim_module_aliases_for_path,
    _smarty_module_aliases_for_path,
    _erb_module_aliases_for_path,
    _pug_module_aliases_for_path,
    _ejs_module_aliases_for_path,
    _blade_module_aliases_for_path,
)
_RootScopedModuleAliasBuilder = Callable[..., Iterable[str]]
# These helpers re-export an adapter attribute (e.g. ruby.module_aliases_for_path).
# They are served through ``__getattr__`` rather than bound eagerly so that importing
# this module does not load any adapter (the root-scoped lazy-load test guards that),
# while attribute access still returns the *real* adapter attribute so identity holds
# (the modularization tests guard that). The builder registry below uses
# ``_lazy_adapter_attr`` wrappers inline, which stay lazy and are only ever called.
_LAZY_ADAPTER_ATTR_EXPORTS: dict[str, tuple[_LazyAdapterModule, str]] = {
    "_scala_package_aliases_for_path": (jvm_adapter, "scala_package_aliases_for_path"),
    "_jvm_declared_type_aliases_for_path": (jvm_adapter, "declared_type_aliases_for_path"),
    "_crystal_declared_type_aliases_for_path": (crystal_adapter, "declared_type_aliases_for_path"),
    "_haskell_module_aliases_for_path": (haskell_adapter, "module_aliases_for_path"),
    "_ocaml_module_aliases_for_path": (ocaml_adapter, "module_aliases_for_path"),
    "_perl_module_aliases_for_path": (perl_adapter, "module_aliases_for_path"),
    "_php_module_aliases_for_path": (php_adapter, "module_aliases_for_path"),
    "_ruby_module_aliases_for_path": (ruby_adapter, "module_aliases_for_path"),
    "_nim_module_aliases_for_path": (nim_adapter, "module_aliases_for_path"),
    "_extract_clojure_ns_form": (clojure_adapter, "extract_ns_form"),
    "_clojure_namespace_path": (clojure_adapter, "namespace_path"),
    "_clojure_module_aliases_for_path": (clojure_adapter, "module_aliases_for_path"),
    "_is_nim_declared_symbol_alias": (nim_adapter, "is_declared_symbol_alias"),
    "_fsharp_path_aliases": (fsharp_adapter, "path_aliases"),
    "_fsharp_namespaces_from_text": (fsharp_adapter, "namespaces_from_text"),
    "_fsharp_open_targets": (fsharp_adapter, "open_targets"),
    "_crystal_constant_aliases_for_file": (crystal_adapter, "constant_aliases_for_file"),
    "_is_crystal_constant_alias": (crystal_adapter, "is_constant_alias"),
    "_elixir_module_aliases_for_path": (elixir_adapter, "module_aliases_for_path"),
    "_erlang_module_aliases_for_path": (erlang_adapter, "module_aliases_for_path"),
}


def __getattr__(name: str):
    target = _LAZY_ADAPTER_ATTR_EXPORTS.get(name)
    if target is not None:
        adapter, attr = target
        return getattr(adapter, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_ROOT_SCOPED_MODULE_ALIAS_BUILDER_REGISTRY: tuple[
    tuple[tuple[str, ...], _RootScopedModuleAliasBuilder],
    ...,
] = (
    (("clojure",), _lazy_adapter_attr(clojure_adapter, "module_aliases_for_path")),
    (("crystal",), _lazy_adapter_attr(crystal_adapter, "declared_type_aliases_for_path")),
    (("erlang",), _lazy_adapter_attr(erlang_adapter, "module_aliases_for_path")),
    (("lua",), _lua_module_aliases_for_path),
    (("luau",), _luau_module_aliases_for_path),
    (("ex", "elixir"), _lazy_adapter_attr(elixir_adapter, "module_aliases_for_path")),
    (("scala",), _lazy_adapter_attr(jvm_adapter, "scala_package_aliases_for_path")),
    (("java", "kotlin", "scala", "groovy", "processing", "xtend"), _lazy_adapter_attr(jvm_adapter, "declared_type_aliases_for_path")),
    (("robotframework",), _robotframework_module_aliases_for_path),
    (("gherkin",), _gherkin_module_aliases_for_path),
    (("antlr",), _antlr_module_aliases_for_path),
    (("graphviz",), _graphviz_module_aliases_for_path),
    (("mermaid",), _mermaid_module_aliases_for_path),
    (("plantuml",), _plantuml_module_aliases_for_path),
    (("openqasm",), _openqasm_module_aliases_for_path),
    (("move",), _move_module_aliases_for_path),
    (("cairo",), _cairo_module_aliases_for_path),
    (("sway",), _sway_module_aliases_for_path),
    (("dm",), _dm_module_aliases_for_path),
    (("scss",), _scss_module_aliases_for_path),
    (("less",), _less_module_aliases_for_path),
    (("stylus",), _stylus_module_aliases_for_path),
    (("jinja",), _jinja_module_aliases_for_path),
    (("liquid",), _liquid_module_aliases_for_path),
    (("handlebars",), _handlebars_module_aliases_for_path),
    (("mustache",), _mustache_module_aliases_for_path),
    (("nunjucks",), _nunjucks_module_aliases_for_path),
    (("twig",), _twig_module_aliases_for_path),
    (("haml",), _haml_module_aliases_for_path),
    (("slim",), _slim_module_aliases_for_path),
    (("smarty",), _smarty_module_aliases_for_path),
    (("erb",), _erb_module_aliases_for_path),
    (("pug",), _pug_module_aliases_for_path),
    (("ejs",), _ejs_module_aliases_for_path),
    (("blade",), _blade_module_aliases_for_path),
    (("fsharp",), _fsharp_module_aliases_for_path),
    (("abap",), _abap_module_aliases_for_path),
    (("ada",), _ada_module_aliases_for_path),
    (("apex",), _apex_module_aliases_for_path),
    (("batchfile",), _batchfile_module_aliases_for_path),
    (("makefile",), _makefile_module_aliases_for_path),
    (("just",), _just_module_aliases_for_path),
    (("dockerfile",), _dockerfile_module_aliases_for_path),
    (("cuda",), _cuda_module_aliases_for_path),
    (("hlsl",), _hlsl_module_aliases_for_path),
    (("wgsl",), _wgsl_module_aliases_for_path),
    (("shaderlab",), _shaderlab_module_aliases_for_path),
    (("cython",), _cython_module_aliases_for_path),
    (("stan",), _stan_module_aliases_for_path),
    (("protobuf",), _protobuf_module_aliases_for_path),
    (("tex",), _tex_module_aliases_for_path),
    (("rst",), _rst_module_aliases_for_path),
    (("asciidoc",), _asciidoc_module_aliases_for_path),
    (("org",), _org_module_aliases_for_path),
    (("typst",), _typst_module_aliases_for_path),
    (("cmake",), _cmake_module_aliases_for_path),
    (("meson",), _meson_module_aliases_for_path),
    (("qmake",), _qmake_module_aliases_for_path),
    (("qml",), _qml_module_aliases_for_path),
    (("vue",), _vue_module_aliases_for_path),
    (("astro",), _astro_module_aliases_for_path),
    (("svelte",), _svelte_module_aliases_for_path),
    (("odin",), _odin_module_aliases_for_path),
    (("autohotkey",), _autohotkey_module_aliases_for_path),
    (("autoit",), _autoit_module_aliases_for_path),
    (("squirrel",), _squirrel_module_aliases_for_path),
    (("awk",), _awk_module_aliases_for_path),
    (("cfml",), _cfml_module_aliases_for_path),
    (("coffeescript",), _coffeescript_module_aliases_for_path),
    (("vala",), _vala_module_aliases_for_path),
    (("mql5",), _mql5_module_aliases_for_path),
    (("gams",), _gams_module_aliases_for_path),
    (("nix",), _nix_module_aliases_for_path),
    (("nushell",), _nushell_module_aliases_for_path),
    (("fish",), _fish_module_aliases_for_path),
    (("openscad",), _openscad_module_aliases_for_path),
    (("purescript",), _purescript_module_aliases_for_path),
    (("reasonml",), _reasonml_module_aliases_for_path),
    (("rescript",), _rescript_module_aliases_for_path),
    (("modelica",), _modelica_module_aliases_for_path),
    (("roc",), _roc_module_aliases_for_path),
    (("agda",), _agda_module_aliases_for_path),
    (("idris",), _idris_module_aliases_for_path),
    (("raku",), _raku_module_aliases_for_path),
    (("gleam",), _gleam_module_aliases_for_path),
    (("hy",), _hy_module_aliases_for_path),
    (("wren",), _wren_module_aliases_for_path),
    (("fennel",), _fennel_module_aliases_for_path),
    (("vyper",), _vyper_module_aliases_for_path),
    (("sass",), _sass_module_aliases_for_path),
    (("qsharp",), _qsharp_module_aliases_for_path),
    (("opencl",), _opencl_module_aliases_for_path),
    (("graphql",), _graphql_module_aliases_for_path),
    (("pkl",), _pkl_module_aliases_for_path),
    (("plpgsql",), _plpgsql_module_aliases_for_path),
    (("webassembly",), _webassembly_module_aliases_for_path),
    (("ballerina",), _ballerina_module_aliases_for_path),
    (("clojurescript",), _clojurescript_module_aliases_for_path),
    (("al",), _al_module_aliases_for_path),
    (("sml",), _sml_module_aliases_for_path),
    (("groovy",), _groovy_module_aliases_for_path),
    (("xtend",), _xtend_module_aliases_for_path),
    (("freemarker",), _freemarker_module_aliases_for_path),
    (("nextflow",), _nextflow_module_aliases_for_path),
    (("moonbit",), _moonbit_module_aliases_for_path),
    (("chapel",), _chapel_module_aliases_for_path),
    (("coq",), _coq_module_aliases_for_path),
    (("lean",), _lean_module_aliases_for_path),
    (("eiffel",), _eiffel_module_aliases_for_path),
    (("janet",), _janet_module_aliases_for_path),
    (("dhall",), _dhall_module_aliases_for_path),
    (("4d",), _four_d_module_aliases_for_path),
    (("rego",), _rego_module_aliases_for_path),
    (("yara",), _yara_module_aliases_for_path),
    (("hcl",), _hcl_module_aliases_for_path),
    (("bicep",), _bicep_module_aliases_for_path),
    (("tlaplus",), _tlaplus_module_aliases_for_path),
    (("haxe",), _haxe_module_aliases_for_path),
    (("v",), _v_module_aliases_for_path),
    (("elm",), _elm_module_aliases_for_path),
    (("abapcds",), _abapcds_module_aliases_for_path),
    (("1centerprise",), _onec_enterprise_module_aliases_for_path),
    (("alloy",), _alloy_module_aliases_for_path),
    (("aiken",), _aiken_module_aliases_for_path),
    (("answer set programming",), _answer_set_programming_module_aliases_for_path),
    (("asl",), _asl_module_aliases_for_path),
    (("ats",), _ats_module_aliases_for_path),
    (("asp.net",), _aspnet_module_aliases_for_path),
    (("actionscript",), _actionscript_module_aliases_for_path),
    (("angelscript",), _angelscript_module_aliases_for_path),
    (("scratch",), _scratch_module_aliases_for_path),
    (("smalltalk",), _smalltalk_module_aliases_for_path),
    (("starlark",), _starlark_module_aliases_for_path),
    (("factor",), _factor_module_aliases_for_path),
    (("cue",), _cue_module_aliases_for_path),
    (("vimscript",), _vimscript_module_aliases_for_path),
    (("assembly",), _assembly_module_aliases_for_path),
    (("prolog",), _prolog_module_aliases_for_path),
    (("foxpro",), _foxpro_module_aliases_for_path),
    (("cobol",), _cobol_module_aliases_for_path),
    (("vbscript",), _vbscript_module_aliases_for_path),
    (("applescript",), _applescript_module_aliases_for_path),
    (("vba",), _vba_module_aliases_for_path),
    (("vb",), _visual_basic_module_aliases_for_path),
    (("vb6",), _classic_visual_basic_module_aliases_for_path),
    (("pascal",), _pascal_module_aliases_for_path),
    (("delphi",), _delphi_module_aliases_for_path),
    (("sql",), _sql_module_aliases_for_path),
    (("tsql",), _tsql_module_aliases_for_path),
    (("ladder",), _ladder_module_aliases_for_path),
    (("labview",), _labview_module_aliases_for_path),
    (("plsql",), _plsql_module_aliases_for_path),
    (("rpg",), _rpg_module_aliases_for_path),
    (("sas",), _sas_module_aliases_for_path),
    (("fortran",), _fortran_module_aliases_for_path),
    (("matlab",), _matlab_module_aliases_for_path),
    (("ml",), _ml_module_aliases_for_path),
    (("lisp",), _lisp_module_aliases_for_path),
    (("puppet",), _puppet_module_aliases_for_path),
    (("emacslisp",), _emacslisp_module_aliases_for_path),
    (("scheme",), _scheme_module_aliases_for_path),
    (("racket",), _racket_module_aliases_for_path),
    (("objectivec",), _objective_c_module_aliases_for_path),
    (("wolfram",), _wolfram_module_aliases_for_path),
    (("xpp",), _xpp_module_aliases_for_path),
    (("d",), _d_module_aliases_for_path),
    (("solidity",), _solidity_module_aliases_for_path),
    (("gdscript",), _gdscript_module_aliases_for_path),
    (("gml",), _gml_module_aliases_for_path),
    (("verilog",), _verilog_module_aliases_for_path),
    (("systemverilog",), _systemverilog_module_aliases_for_path),
    (("vhdl",), _vhdl_module_aliases_for_path),
    (("tcl",), _tcl_module_aliases_for_path),
    (("apacheconf",), _apacheconf_module_aliases_for_path),
    (("aspectj",), _aspectj_module_aliases_for_path),
    (("haskell",), _lazy_adapter_attr(haskell_adapter, "module_aliases_for_path")),
    (("ocaml",), _lazy_adapter_attr(ocaml_adapter, "module_aliases_for_path")),
    (("perl",), _lazy_adapter_attr(perl_adapter, "module_aliases_for_path")),
    (("php",), _lazy_adapter_attr(php_adapter, "module_aliases_for_path")),
    (("ruby",), _lazy_adapter_attr(ruby_adapter, "module_aliases_for_path")),
    (("r",), _r_module_aliases_for_path),
    (("nim",), _lazy_adapter_attr(nim_adapter, "module_aliases_for_path")),
    (("nim",), _nim_declared_symbol_aliases_for_path),
    (("julia",), _julia_module_aliases_for_path),
)
_ROOT_SCOPED_MODULE_ALIAS_BUILDERS = tuple(
    builder for _, builder in _ROOT_SCOPED_MODULE_ALIAS_BUILDER_REGISTRY
)
_ROOT_SCOPED_MODULE_ALIAS_BUILDERS_BY_LANGUAGE: dict[
    str, tuple[_RootScopedModuleAliasBuilder, ...]
] = {}
for _languages, _builder in _ROOT_SCOPED_MODULE_ALIAS_BUILDER_REGISTRY:
    for _language in _languages:
        _ROOT_SCOPED_MODULE_ALIAS_BUILDERS_BY_LANGUAGE[_language] = (
            _ROOT_SCOPED_MODULE_ALIAS_BUILDERS_BY_LANGUAGE.get(_language, ())
            + (_builder,)
        )


def root_scoped_module_alias_builders_for_language(
    language: str | None,
) -> tuple[_RootScopedModuleAliasBuilder, ...]:
    normalized_language = (language or "").strip().lower()
    if not normalized_language or normalized_language == "unknown":
        return _ROOT_SCOPED_MODULE_ALIAS_BUILDERS
    return _ROOT_SCOPED_MODULE_ALIAS_BUILDERS_BY_LANGUAGE.get(
        normalized_language,
        (),
    )
