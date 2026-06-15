# ruff: noqa: I001, F401
from __future__ import annotations
import re
from apps.api_server.services import repository_intelligence_adapters as repository_adapters
from apps.api_server.services.repository_intelligence_contracts import _ModuleIndexLookup


class _LazyAdapterModule:
    __slots__ = ("_adapter_name", "_attribute_cache", "_loaded_module")

    def __init__(self, adapter_name: str) -> None:
        object.__setattr__(self, "_adapter_name", adapter_name)
        object.__setattr__(self, "_attribute_cache", {})
        object.__setattr__(self, "_loaded_module", None)

    def _load(self):
        loaded_module = object.__getattribute__(self, "_loaded_module")
        if loaded_module is None:
            loaded_module = getattr(repository_adapters, self._adapter_name)
            object.__setattr__(self, "_loaded_module", loaded_module)
        return loaded_module

    def __getattr__(self, name: str) -> object:
        cache = object.__getattribute__(self, "_attribute_cache")
        try:
            return cache[name]
        except KeyError:
            value = getattr(self._load(), name)
            cache[name] = value
            return value

    def __setattr__(self, name: str, value: object) -> None:
        # Slot-backed bookkeeping fields use the normal path; any other attribute is an
        # override (notably pytest's ``monkeypatch.setattr``) routed through the attribute
        # cache so callers can patch the wrapper without mutating the shared adapter
        # module. ``__getattr__`` reads the cache first, so the override takes effect.
        if name in _LazyAdapterModule.__slots__:
            object.__setattr__(self, name, value)
            return
        object.__getattribute__(self, "_attribute_cache")[name] = value

    def __delattr__(self, name: str) -> None:
        cache = object.__getattribute__(self, "_attribute_cache")
        if name in cache:
            del cache[name]
            return
        raise AttributeError(name)

    def __dir__(self) -> list[str]:
        cache = object.__getattribute__(self, "_attribute_cache")
        return sorted(set(dir(type(self))) | set(cache) | set(dir(self._load())))


def _lazy_adapter_module(adapter_name: str) -> _LazyAdapterModule:
    return _LazyAdapterModule(adapter_name)


as3_adapter = _lazy_adapter_module("actionscript")
agda_adapter = _lazy_adapter_module("agda")
ampl_adapter = _lazy_adapter_module("ampl")
apl_adapter = _lazy_adapter_module("apl")
apex_adapter = _lazy_adapter_module("apex")
osa_adapter = _lazy_adapter_module("applescript")
assembly_adapter = _lazy_adapter_module("assembly")
autoit_adapter = _lazy_adapter_module("autoit")
awk_adapter = _lazy_adapter_module("awk")
bicep_adapter = _lazy_adapter_module("bicep")
cmake_adapter = _lazy_adapter_module("cmake")
cfml_adapter = _lazy_adapter_module("cfml")
cvb = _lazy_adapter_module("classic_visual_basic")
common_workflow_language_adapter = _lazy_adapter_module("common_workflow_language")
meson_adapter = _lazy_adapter_module("meson")
qmake_adapter = _lazy_adapter_module("qmake")
qml_adapter = _lazy_adapter_module("qml")
antlr_adapter = _lazy_adapter_module("antlr")
asciidoc_adapter = _lazy_adapter_module("asciidoc")
astro_adapter = _lazy_adapter_module("astro")
blade_adapter = _lazy_adapter_module("blade")
cairo_adapter = _lazy_adapter_module("cairo")
coffee_adapter = _lazy_adapter_module("coffeescript")
coq_adapter = _lazy_adapter_module("coq")
cuda_adapter = _lazy_adapter_module("cuda")
cython_adapter = _lazy_adapter_module("cython")
dataweave_adapter = _lazy_adapter_module("dataweave")
dm_adapter = _lazy_adapter_module("dm")
earthly_adapter = _lazy_adapter_module("earthly")
ejs_adapter = _lazy_adapter_module("ejs")
erb_adapter = _lazy_adapter_module("erb")
fennel_adapter = _lazy_adapter_module("fennel")
gherkin_adapter = _lazy_adapter_module("gherkin")
graphql_adapter = _lazy_adapter_module("graphql")
graphviz_adapter = _lazy_adapter_module("graphviz")
haml_adapter = _lazy_adapter_module("haml")
handlebars_adapter = _lazy_adapter_module("handlebars")
hlsl_adapter = _lazy_adapter_module("hlsl")
hy_adapter = _lazy_adapter_module("hy")
jinja_adapter = _lazy_adapter_module("jinja")
lean_adapter = _lazy_adapter_module("lean")
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
pug_adapter = _lazy_adapter_module("pug")
reasonml_adapter = _lazy_adapter_module("reasonml")
rescript_adapter = _lazy_adapter_module("rescript")
roc_adapter = _lazy_adapter_module("roc")
slim_adapter = _lazy_adapter_module("slim")
smarty_adapter = _lazy_adapter_module("smarty")
svelte_adapter = _lazy_adapter_module("svelte")
sway_adapter = _lazy_adapter_module("sway")
twig_adapter = _lazy_adapter_module("twig")
vue_adapter = _lazy_adapter_module("vue")
wgsl_adapter = _lazy_adapter_module("wgsl")
wren_adapter = _lazy_adapter_module("wren")
xtend_adapter = _lazy_adapter_module("xtend")
vyper_adapter = _lazy_adapter_module("vyper")
delphi_adapter = _lazy_adapter_module("delphi")
emacslisp_adapter = _lazy_adapter_module("emacslisp")
eiffel_adapter = _lazy_adapter_module("eiffel")
brightscript_adapter = _lazy_adapter_module("brightscript")
codeql_adapter = _lazy_adapter_module("codeql")
gnuplot_adapter = _lazy_adapter_module("gnuplot")
mako_adapter = _lazy_adapter_module("mako")
maven_adapter = _lazy_adapter_module("maven")
bitbake_adapter = _lazy_adapter_module("bitbake")
cue_adapter = _lazy_adapter_module("cue")
dockerfile_adapter = _lazy_adapter_module("dockerfile")
factor_adapter = _lazy_adapter_module("factor")
fish_adapter = _lazy_adapter_module("fish")
just_adapter = _lazy_adapter_module("just")
makefile_adapter = _lazy_adapter_module("makefile")
shell_adapter = _lazy_adapter_module("shell")
foxpro_adapter = _lazy_adapter_module("foxpro")
gams_adapter = _lazy_adapter_module("gams")
gdscript_adapter = _lazy_adapter_module("gdscript")
gleam_adapter = _lazy_adapter_module("gleam")
gml_adapter = _lazy_adapter_module("gml")
hack_adapter = _lazy_adapter_module("hack")
haxe_adapter = _lazy_adapter_module("haxe")
idris_adapter = _lazy_adapter_module("idris")
labview_adapter = _lazy_adapter_module("labview")
ladder_adapter = _lazy_adapter_module("ladder")
lisp_adapter = _lazy_adapter_module("lisp")
luau_adapter = _lazy_adapter_module("luau")
matlab_adapter = _lazy_adapter_module("matlab")
nix_adapter = _lazy_adapter_module("nix")
nushell_adapter = _lazy_adapter_module("nushell")
objc_adapter = _lazy_adapter_module("objective_c")
openscad_adapter = _lazy_adapter_module("openscad")
protobuf_adapter = _lazy_adapter_module("protobuf")
prolog_adapter = _lazy_adapter_module("prolog")
puppet_adapter = _lazy_adapter_module("puppet")
rst_adapter = _lazy_adapter_module("rst")
tex_adapter = _lazy_adapter_module("tex")
purs_adapter = _lazy_adapter_module("purescript")
racket_adapter = _lazy_adapter_module("racket")
raku_adapter = _lazy_adapter_module("raku")
scheme_adapter = _lazy_adapter_module("scheme")
scratch_adapter = _lazy_adapter_module("scratch")
q_adapter = _lazy_adapter_module("q")
robotframework_adapter = _lazy_adapter_module("robotframework")
scss_adapter = _lazy_adapter_module("scss")
shaderlab_adapter = _lazy_adapter_module("shaderlab")
smalltalk_adapter = _lazy_adapter_module("smalltalk")
squirrel_adapter = _lazy_adapter_module("squirrel")
stan_adapter = _lazy_adapter_module("stan")
starlark_adapter = _lazy_adapter_module("starlark")
stylus_adapter = _lazy_adapter_module("stylus")
sv_adapter = _lazy_adapter_module("systemverilog")
tlaplus_adapter = _lazy_adapter_module("tlaplus")
tsql_adapter = _lazy_adapter_module("tsql")
typst_adapter = _lazy_adapter_module("typst")
vala_adapter = _lazy_adapter_module("vala")
less_adapter = _lazy_adapter_module("less")
tcl_adapter = _lazy_adapter_module("tcl")
vba_adapter = _lazy_adapter_module("vba")
vbscript_adapter = _lazy_adapter_module("vbscript")
verilog_adapter = _lazy_adapter_module("verilog")
vhdl_adapter = _lazy_adapter_module("vhdl")
vimscript_adapter = _lazy_adapter_module("vimscript")
v_adapter = _lazy_adapter_module("vlang")
wolfram_adapter = _lazy_adapter_module("wolfram")
xpp_adapter = _lazy_adapter_module("xpp")
xslt_adapter = _lazy_adapter_module("xslt")
abapcds_adapter = _lazy_adapter_module("abapcds")
aidl_adapter = _lazy_adapter_module("aidl")
al_adapter = _lazy_adapter_module("al")
aiken_adapter = _lazy_adapter_module("aiken")
alloy_adapter = _lazy_adapter_module("alloy")
angelscript_adapter = _lazy_adapter_module("angelscript")
answer_set_programming_adapter = _lazy_adapter_module("answer_set_programming")
apacheconf_adapter = _lazy_adapter_module("apacheconf")
aspnet_adapter = _lazy_adapter_module("aspnet")
asl_adapter = _lazy_adapter_module("asl")
aspectj_adapter = _lazy_adapter_module("aspectj")
ats_adapter = _lazy_adapter_module("ats")
ballerina_adapter = _lazy_adapter_module("ballerina")
bqn_adapter = _lazy_adapter_module("bqn")
circom_adapter = _lazy_adapter_module("circom")
clojurescript_adapter = _lazy_adapter_module("clojurescript")
dafny_adapter = _lazy_adapter_module("dafny")
forth_adapter = _lazy_adapter_module("forth")
four_d_adapter = _lazy_adapter_module("four_d")
freemarker_adapter = _lazy_adapter_module("freemarker")
groovy_adapter = _lazy_adapter_module("groovy")
hoon_adapter = _lazy_adapter_module("hoon")
isabelle_adapter = _lazy_adapter_module("isabelle")
j_adapter = _lazy_adapter_module("j")
jsonnet_adapter = _lazy_adapter_module("jsonnet")
lex_adapter = _lazy_adapter_module("lex")
m4_adapter = _lazy_adapter_module("m4")
metal_adapter = _lazy_adapter_module("metal")
mercury_adapter = _lazy_adapter_module("mercury")
motoko_adapter = _lazy_adapter_module("motoko")
moonscript_adapter = _lazy_adapter_module("moonscript")
nginx_adapter = _lazy_adapter_module("nginx")
nsis_adapter = _lazy_adapter_module("nsis")
ocamllex_adapter = _lazy_adapter_module("ocamllex")
ocamlyacc_adapter = _lazy_adapter_module("ocamlyacc")
opencl_adapter = _lazy_adapter_module("opencl")
openedge_adapter = _lazy_adapter_module("openedge")
onec_enterprise_adapter = _lazy_adapter_module("onec_enterprise")
pawn_adapter = _lazy_adapter_module("pawn")
plpgsql_adapter = _lazy_adapter_module("plpgsql")
pkl_adapter = _lazy_adapter_module("pkl")
pony_adapter = _lazy_adapter_module("pony")
postscript_adapter = _lazy_adapter_module("postscript")
purebasic_adapter = _lazy_adapter_module("purebasic")
qsharp_adapter = _lazy_adapter_module("qsharp")
rebol_adapter = _lazy_adapter_module("rebol")
red_adapter = _lazy_adapter_module("red")
sass_adapter = _lazy_adapter_module("sass")
sed_adapter = _lazy_adapter_module("sed")
smali_adapter = _lazy_adapter_module("smali")
templ_adapter = _lazy_adapter_module("templ")
thrift_adapter = _lazy_adapter_module("thrift")
vcl_adapter = _lazy_adapter_module("vcl")
webassembly_adapter = _lazy_adapter_module("webassembly")
xquery_adapter = _lazy_adapter_module("xquery")
yacc_adapter = _lazy_adapter_module("yacc")
_MODULE_INDEX_LOOKUP_CACHE_LIMIT, _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE_LIMIT, _CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE_LIMIT = 64, 16, 4096
_MODULE_INDEX_LOOKUP_CACHE: dict[tuple[str, ...], _ModuleIndexLookup] = {}; _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE: dict[str, frozenset[str]] = {}; _CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE: dict[tuple[str, str], bool] = {}  # noqa: E702
_FSHARP_PROJECT_ROOT_CACHE_LIMIT, _FSHARP_PROJECT_CONTEXT_CACHE_LIMIT = 64, 4096
_FSHARP_PROJECT_ROOT_CACHE: dict[str, frozenset[str]] = {}
_FSHARP_PROJECT_CONTEXT_CACHE: dict[tuple[str, str], bool] = {}
_AMBIGUOUS_V_REPO_HINT_CACHE_LIMIT = 256
_AMBIGUOUS_V_REPO_HINT_CACHE: dict[str, str] = {}
_AMBIGUOUS_C_HEADER_REPO_HINT_CACHE_LIMIT = 256
_AMBIGUOUS_C_HEADER_REPO_HINT_CACHE: dict[str, str] = {}
_AMBIGUOUS_C_HEADER_REPO_HINT_SAMPLE_LIMIT = 12
_CPP_REPO_HINT_SUFFIXES = frozenset(
    {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inl", ".ipp"}
)
_CPP_REPO_HINT_BASENAMES = frozenset({"cmakelists.txt", "meson.build", "meson_options.txt"})
_OBJECTIVE_C_REPO_HINT_SUFFIXES = frozenset({".m", ".mm", ".pch"})
_OBJECTIVE_C_REPO_HINT_PART_SUFFIXES = (".xcodeproj", ".xcworkspace")
_SHELL_FILE_BASENAMES = frozenset({".bash_profile", ".bashrc", ".envrc", ".profile", ".zlogin", ".zlogout", ".zprofile", ".zshenv", ".zshrc", "bash_completion"})  # noqa: E501
_JS_LIKE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"); _AGDA_SUFFIXES, _RAKU_SUFFIXES = frozenset({".agda", ".lagda", ".agda-lib"}), frozenset({".raku", ".rakumod", ".rakutest", ".pm6", ".p6"})  # noqa: E501,E702
_CLARITY_MARKER_RE = re.compile(
    r"(?im)^\s*\((?:define-(?:public|private|read-only|trait|map|data-var|constant|fungible-token|non-fungible-token)|use-trait|impl-trait|contract-call\?)\b"
)
_FREEBASIC_MARKER_RE = re.compile(
    r"(?im)^\s*(?:#include(?:\s+once)?|declare\s+(?:sub|function)\b|namespace\b|(?:private\s+)?constructor\b|(?:private\s+)?destructor\b)"
)
_DIRECT_TEXT_SUFFIX_LANGUAGE_MAP = {
    ".ampl": "ampl",
    ".scad": "openscad", ".gleam": "gleam", ".hy": "hy", ".wren": "wren", ".janet": "janet", ".fnl": "fennel", ".fnlm": "fennel", ".vy": "vyper", ".vyi": "vyper", ".bal": "ballerina", ".nf": "nextflow", ".nu": "nushell", ".nsi": "nsis", ".nsh": "nsis", ".pde": "processing",
    ".purs": "purescript", ".mbt": "moonbit", ".mbti": "moonbit", ".gd": "gdscript", ".el": "emacslisp", ".factor": "factor",
    ".fish": "fish", ".bat": "batchfile", ".cmd": "batchfile", ".mk": "makefile",
    ".cmake": "cmake", ".pro": "qmake", ".pri": "qmake", ".prf": "qmake", ".qml": "qml", ".dockerfile": "dockerfile",
    ".cu": "cuda", ".cuh": "cuda", ".cwl": "common workflow language", ".pyx": "cython", ".pxd": "cython", ".pxi": "cython", ".proto": "protobuf", ".stan": "stan", ".shader": "shaderlab", ".wgsl": "wgsl", ".j2": "jinja", ".jinja": "jinja", ".jinja2": "jinja", ".liquid": "liquid", ".hbs": "handlebars", ".handlebars": "handlebars", ".mustache": "mustache", ".njk": "nunjucks", ".nunj": "nunjucks", ".nunjucks": "nunjucks", ".twig": "twig", ".haml": "haml", ".slim": "slim", ".erb": "erb", ".rhtml": "erb", ".pug": "pug", ".jade": "pug", ".ejs": "ejs", ".vue": "vue", ".svelte": "svelte", ".astro": "astro", ".robot": "robotframework", ".resource": "robotframework", ".feature": "gherkin", ".g4": "antlr", ".dot": "graphviz", ".gv": "graphviz", ".mmd": "mermaid", ".mermaid": "mermaid", ".puml": "plantuml", ".plantuml": "plantuml", ".iuml": "plantuml", ".qasm": "openqasm", ".move": "move", ".mo": "modelica", ".roc": "roc", ".re": "reasonml", ".rei": "reasonml", ".res": "rescript", ".resi": "rescript", ".scss": "scss", ".less": "less", ".styl": "stylus", ".typ": "typst", ".tex": "tex", ".sty": "tex", ".ltx": "tex", ".dtx": "tex", ".rst": "rst", ".rest": "rst", ".adoc": "asciidoc", ".asciidoc": "asciidoc", ".asc": "asciidoc", ".org": "org",
    ".bb": "bitbake", ".bbappend": "bitbake", ".bbclass": "bitbake", ".just": "just", ".rego": "rego", ".yar": "yara", ".yara": "yara", ".tf": "hcl", ".hcl": "hcl", ".glsl": "glsl", ".vert": "glsl", ".frag": "glsl", ".geom": "glsl", ".tesc": "glsl", ".tese": "glsl", ".comp": "glsl", ".hlsl": "hlsl", ".hlsli": "hlsl", ".fx": "hlsl", ".fxh": "hlsl", ".cginc": "hlsl", ".compute": "hlsl",  # noqa: E501
    ".dhall": "dhall", ".dm": "dm", ".dme": "dm", ".dwl": "dataweave", ".4dm": "4d", ".tfvars": "hcl", ".bicep": "bicep", ".cairo": "cairo", ".chpl": "chapel", ".gml": "gml", ".gnuplot": "gnuplot", ".gp": "gnuplot", ".plt": "gnuplot", ".tla": "tlaplus", ".lgt": "logtalk", ".logtalk": "logtalk", ".hack": "hack", ".hhi": "hack", ".lean": "lean", ".odin": "odin", ".jsonnet": "jsonnet", ".libsonnet": "jsonnet", ".m4": "m4", ".fth": "forth", ".forth": "forth", ".4th": "forth", ".thy": "isabelle", ".apl": "apl", ".aplf": "apl", ".dyalog": "apl", ".reb": "rebol", ".rebol": "rebol", ".r3": "rebol", ".red": "red", ".reds": "red", ".sed": "sed", ".pb": "purebasic", ".pbi": "purebasic", ".pwn": "pawn", ".pony": "pony", ".ps": "postscript", ".eps": "postscript", ".smali": "smali", ".sw": "sway", ".xq": "xquery", ".xquery": "xquery", ".xqy": "xquery", ".xql": "xquery", ".xqm": "xquery", ".xsl": "xslt", ".xslt": "xslt", ".q": "q", ".moon": "moonscript",  # noqa: E501
    ".clar": "clarity", ".bi": "freebasic", ".aidl": "aidl", ".aj": "aspectj", ".ak": "aiken", ".als": "alloy", ".asax": "asp.net", ".ascx": "asp.net", ".ashx": "asp.net", ".asmx": "asp.net", ".aspx": "asp.net", ".asddls": "abapcds", ".asl": "asl", ".brs": "brightscript", ".bsl": "1centerprise", ".dats": "ats", ".ftl": "freemarker", ".ftlh": "freemarker", ".ftlx": "freemarker", ".gql": "graphql", ".graphql": "graphql", ".graphqls": "graphql", ".hats": "ats", ".load": "apacheconf", ".lp": "answer set programming", ".mako": "mako", ".master": "asp.net", ".pgsql": "plpgsql", ".ql": "codeql", ".qll": "codeql", ".sats": "ats", ".templ": "templ", ".thrift": "thrift", ".vcl": "vcl", ".wat": "webassembly", ".wast": "webassembly", ".xtend": "xtend",
    **dict.fromkeys(_AGDA_SUFFIXES, "agda"), **dict.fromkeys(_RAKU_SUFFIXES, "raku"),
}

# --- re-exports of split submodules (imported after the adapter machinery
# and constants above are defined so the submodules can import them back) ---
from apps.api_server.services.repository_intelligence_indexing_paths import (
    _normalize_repository_relative_path,
    _normalize_repository_relative_path_cached,
    _normalize_repository_relative_pattern,
    _matches_repository_scope,
    _matches_repository_pattern,
)
from apps.api_server.services.repository_intelligence_indexing_repo_hints import (
    _ranked_adapter_language_for_path,
    _candidate_repository_roots,
    _classic_visual_basic_project_members,
    _has_classic_visual_basic_project_context,
    _fsharp_project_roots,
    _has_fsharp_project_context,
    _iter_repository_glob_matches,
    _ambiguous_v_repo_hint_language,
    _ambiguous_c_header_repo_hint_language,
)
from apps.api_server.services.repository_intelligence_indexing_classification import (
    _language_for_path,
)

# ``_language_for_path`` is defined in the classification submodule after the split,
# but its public home is this module: restore ``__module__`` so the modularization
# contract (``repository_service._language_for_path.__module__ == indexing.__name__``)
# holds exactly as it did before the split.
_language_for_path.__module__ = __name__
from apps.api_server.services.repository_intelligence_indexing_module_index import (
    _estimate_tokens,
    _module_aliases_for_path,
    _module_index_values,
    _module_index_lookup,
    _module_index_aliases_for_file,
    _root_scoped_module_alias_builder_accepts_text,
    _iter_root_scoped_module_aliases,
    _read_repository_relative_text,
    _resolve_suffix_match,
    _resolve_directory_prefix_match,
    _build_module_index,
)
