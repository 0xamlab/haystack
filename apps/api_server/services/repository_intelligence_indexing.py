# ruff: noqa: I001
from __future__ import annotations
from collections.abc import Callable, Iterable, Iterator, Sequence
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from apps.api_server.services.repository_intelligence_adapters import actionscript as as3_adapter, agda as agda_adapter, apex as apex_adapter, applescript as osa_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import assembly as assembly_adapter, autoit as autoit_adapter, awk as awk_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import bicep as bicep_adapter
from apps.api_server.services.repository_intelligence_adapters import cmake as cmake_adapter, cfml as cfml_adapter, classic_visual_basic as cvb, meson as meson_adapter, qmake as qmake_adapter, qml as qml_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import antlr as antlr_adapter, asciidoc as asciidoc_adapter, astro as astro_adapter, blade as blade_adapter, coffeescript as coffee_adapter, coq as coq_adapter, cuda as cuda_adapter, cython as cython_adapter, dm as dm_adapter, ejs as ejs_adapter, erb as erb_adapter, fennel as fennel_adapter, gherkin as gherkin_adapter, graphviz as graphviz_adapter, haml as haml_adapter, handlebars as handlebars_adapter, hlsl as hlsl_adapter, hy as hy_adapter, jinja as jinja_adapter, lean as lean_adapter, liquid as liquid_adapter, mermaid as mermaid_adapter, modelica as modelica_adapter, moonbit as moonbit_adapter, move as move_adapter, mustache as mustache_adapter, nextflow as nextflow_adapter, nunjucks as nunjucks_adapter, openqasm as openqasm_adapter, org as org_adapter, plantuml as plantuml_adapter, pug as pug_adapter, rescript as rescript_adapter, roc as roc_adapter, slim as slim_adapter, smarty as smarty_adapter, svelte as svelte_adapter, twig as twig_adapter, vue as vue_adapter, wgsl as wgsl_adapter, wren as wren_adapter, vyper as vyper_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import delphi as delphi_adapter, emacslisp as emacslisp_adapter, eiffel as eiffel_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import bitbake as bitbake_adapter, cue as cue_adapter, dockerfile as dockerfile_adapter, factor as factor_adapter, fish as fish_adapter, just as just_adapter, makefile as makefile_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import foxpro as foxpro_adapter, gams as gams_adapter, gdscript as gdscript_adapter, gleam as gleam_adapter, gml as gml_adapter, hack as hack_adapter, haxe as haxe_adapter, idris as idris_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import labview as labview_adapter, ladder as ladder_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import luau as luau_adapter, matlab as matlab_adapter, nix as nix_adapter, nushell as nushell_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import objective_c as objc_adapter, openscad as openscad_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import protobuf as protobuf_adapter, prolog as prolog_adapter, puppet as puppet_adapter, rst as rst_adapter, tex as tex_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import purescript as purs_adapter, racket as racket_adapter, raku as raku_adapter, scheme as scheme_adapter, scratch as scratch_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import robotframework as robotframework_adapter, scss as scss_adapter, shaderlab as shaderlab_adapter, smalltalk as smalltalk_adapter, squirrel as squirrel_adapter, stan as stan_adapter, starlark as starlark_adapter, stylus as stylus_adapter, systemverilog as sv_adapter, tlaplus as tlaplus_adapter, tsql as tsql_adapter, typst as typst_adapter, vala as vala_adapter, less as less_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import vba as vba_adapter, vbscript as vbscript_adapter, verilog as verilog_adapter, vhdl as vhdl_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import vimscript as vimscript_adapter, vlang as v_adapter, wolfram as wolfram_adapter, xpp as xpp_adapter  # noqa: E501
from apps.api_server.services.repository_intelligence_adapters import (
    al as al_adapter,
    clojurescript as clojurescript_adapter,
    groovy as groovy_adapter,
    opencl as opencl_adapter,
    qsharp as qsharp_adapter,
    sass as sass_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import _ModuleIndexLookup
_MODULE_INDEX_LOOKUP_CACHE_LIMIT, _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE_LIMIT = 64, 16
_MODULE_INDEX_LOOKUP_CACHE: dict[tuple[str, ...], _ModuleIndexLookup] = {}; _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE: dict[str, frozenset[str]] = {}  # noqa: E702
_SHELL_FILE_BASENAMES = frozenset({".bash_profile", ".bashrc", ".envrc", ".profile", ".zlogin", ".zlogout", ".zprofile", ".zshenv", ".zshrc", "bash_completion"})  # noqa: E501
_JS_LIKE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"); _AGDA_SUFFIXES, _RAKU_SUFFIXES = frozenset({".agda", ".lagda", ".agda-lib"}), frozenset({".raku", ".rakumod", ".rakutest", ".pm6", ".p6"})  # noqa: E501,E702
_DIRECT_TEXT_SUFFIX_LANGUAGE_MAP = {
    ".scad": "openscad", ".gleam": "gleam", ".hy": "hy", ".wren": "wren", ".janet": "janet", ".fnl": "fennel", ".fnlm": "fennel", ".vy": "vyper", ".vyi": "vyper", ".nf": "nextflow", ".nu": "nushell",
    ".purs": "purescript", ".mbt": "moonbit", ".mbti": "moonbit", ".gd": "gdscript", ".el": "emacslisp", ".factor": "factor",
    ".fish": "fish", ".bat": "batchfile", ".cmd": "batchfile", ".mk": "makefile",
    ".cmake": "cmake", ".pro": "qmake", ".pri": "qmake", ".prf": "qmake", ".qml": "qml", ".dockerfile": "dockerfile",
    ".cu": "cuda", ".cuh": "cuda", ".pyx": "cython", ".pxd": "cython", ".pxi": "cython", ".proto": "protobuf", ".stan": "stan", ".shader": "shaderlab", ".wgsl": "wgsl", ".j2": "jinja", ".jinja": "jinja", ".jinja2": "jinja", ".liquid": "liquid", ".hbs": "handlebars", ".handlebars": "handlebars", ".mustache": "mustache", ".njk": "nunjucks", ".nunj": "nunjucks", ".nunjucks": "nunjucks", ".twig": "twig", ".haml": "haml", ".slim": "slim", ".erb": "erb", ".rhtml": "erb", ".pug": "pug", ".jade": "pug", ".ejs": "ejs", ".vue": "vue", ".svelte": "svelte", ".astro": "astro", ".robot": "robotframework", ".resource": "robotframework", ".feature": "gherkin", ".g4": "antlr", ".dot": "graphviz", ".gv": "graphviz", ".mmd": "mermaid", ".mermaid": "mermaid", ".puml": "plantuml", ".plantuml": "plantuml", ".iuml": "plantuml", ".qasm": "openqasm", ".move": "move", ".mo": "modelica", ".roc": "roc", ".res": "rescript", ".resi": "rescript", ".scss": "scss", ".less": "less", ".styl": "stylus", ".typ": "typst", ".tex": "tex", ".sty": "tex", ".ltx": "tex", ".dtx": "tex", ".rst": "rst", ".rest": "rst", ".adoc": "asciidoc", ".asciidoc": "asciidoc", ".asc": "asciidoc", ".org": "org",
    ".bb": "bitbake", ".bbappend": "bitbake", ".bbclass": "bitbake", ".just": "just", ".rego": "rego", ".yar": "yara", ".yara": "yara", ".tf": "hcl", ".hcl": "hcl", ".glsl": "glsl", ".vert": "glsl", ".frag": "glsl", ".geom": "glsl", ".tesc": "glsl", ".tese": "glsl", ".comp": "glsl", ".hlsl": "hlsl", ".hlsli": "hlsl", ".fx": "hlsl", ".fxh": "hlsl", ".cginc": "hlsl", ".compute": "hlsl",  # noqa: E501
    ".dhall": "dhall", ".dm": "dm", ".dme": "dm", ".tfvars": "hcl", ".bicep": "bicep", ".chpl": "chapel", ".gml": "gml", ".tla": "tlaplus", ".lgt": "logtalk", ".logtalk": "logtalk", ".hack": "hack", ".hhi": "hack", ".lean": "lean", ".odin": "odin",  # noqa: E501
    **dict.fromkeys(_AGDA_SUFFIXES, "agda"), **dict.fromkeys(_RAKU_SUFFIXES, "raku"),
}
def _normalize_repository_relative_path(value: str) -> str:
    raw_parts = PurePosixPath(str(value).replace("\\", "/")).parts
    normalized_parts: list[str] = []
    for part in raw_parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)
def _normalize_repository_relative_pattern(value: str) -> str:
    wildcard_sentinel = "__ALGENTA_WILDCARD__"
    normalized = _normalize_repository_relative_path(str(value).replace("*", wildcard_sentinel))
    return normalized.replace(wildcard_sentinel, "*")
def _candidate_repository_roots(*, root_path: Path, focus_paths: Sequence[str]) -> tuple[Path, ...]:
    if not focus_paths:
        return (root_path,)
    candidates: list[Path] = []
    for focus_path in focus_paths:
        if not focus_path:
            candidates.append(root_path)
            continue
        candidate = (root_path / focus_path).resolve()
        if candidate.exists() and (candidate == root_path or root_path in candidate.parents):
            candidates.append(candidate)
    return tuple(candidates or [root_path])
def _classic_visual_basic_project_members(repo_root: Path) -> frozenset[str]:
    normalized_root = str(repo_root.resolve())
    cached_members = _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE.get(normalized_root)
    if cached_members is not None:
        return cached_members
    project_members: set[str] = set()
    try:
        manifest_paths = sorted(repo_root.rglob("*.vbp"))
    except OSError:
        manifest_paths = []
    for manifest_path in manifest_paths:
        try:
            relative_manifest_path = _normalize_repository_relative_path(
                str(manifest_path.relative_to(repo_root))
            )
        except ValueError:
            continue
        try:
            text = manifest_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not cvb.is_probable_classic_visual_basic_source(
            path=Path(relative_manifest_path),
            text=text,
        ):
            continue
        project_members.add(relative_manifest_path.lower())
        for entry in cvb.project_component_entries(
            text,
            manifest_path=relative_manifest_path,
        ):
            entry_path = _normalize_repository_relative_path(str(entry.get("path") or ""))
            if entry_path:
                project_members.add(entry_path.lower())
    cached_result = frozenset(project_members)
    if len(_CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE) >= (
        _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE_LIMIT
    ):
        oldest_key = next(iter(_CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE))
        _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE.pop(oldest_key, None)
    _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE[normalized_root] = cached_result
    return cached_result
def _has_classic_visual_basic_project_context(*, path: Path, repo_root: Path | None) -> bool:
    if repo_root is None:
        return False
    try:
        relative_path = _normalize_repository_relative_path(str(path.relative_to(repo_root)))
    except ValueError:
        relative_path = _normalize_repository_relative_path(str(path))
    if not relative_path:
        return False
    return relative_path.lower() in _classic_visual_basic_project_members(repo_root)
def _matches_repository_scope(relative_path: str, scope: str) -> bool:
    normalized_scope = _normalize_repository_relative_path(scope)
    if not normalized_scope:
        return True
    return relative_path == normalized_scope or relative_path.startswith(f"{normalized_scope}/")
def _matches_repository_pattern(relative_path: str, pattern: str) -> bool:
    normalized_pattern = _normalize_repository_relative_path(pattern)
    if not normalized_pattern:
        return True
    if _matches_repository_scope(relative_path, normalized_pattern):
        return True
    pattern_variants = {normalized_pattern}
    pending_patterns = [normalized_pattern]
    while pending_patterns:
        candidate_pattern = pending_patterns.pop()
        if "/**/" not in candidate_pattern:
            continue
        direct_variant = candidate_pattern.replace("/**/", "/", 1)
        if direct_variant not in pattern_variants:
            pattern_variants.add(direct_variant)
            pending_patterns.append(direct_variant)
    return any(fnmatchcase(relative_path, candidate_pattern) for candidate_pattern in sorted(pattern_variants))
def _language_for_path(path: Path, *, text: str | None = None, repo_root: Path | None = None) -> str:
    if path.name.lower() in _SHELL_FILE_BASENAMES:
        return "shell"
    suffix = path.suffix.lower()
    if path.name.lower() in makefile_adapter.MAKEFILE_BASENAMES:
        return "makefile" if text is None or makefile_adapter.is_probable_makefile_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and (path.name.lower() in just_adapter.JUSTFILE_BASENAMES or path.suffix.lower() == ".just"):
        return "just" if just_adapter.is_probable_just_source(path=path, text=text) else "unknown"
    if path.name.lower() in dockerfile_adapter.DOCKERFILE_BASENAMES:
        return "dockerfile" if text is None or dockerfile_adapter.is_probable_dockerfile_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and path.suffix.lower() in antlr_adapter.ANTLR_SUFFIXES:
        return "antlr" if antlr_adapter.is_probable_antlr_source(path=path, text=text) else "unknown"
    if text is not None and (path.suffix.lower() in graphviz_adapter.GRAPHVIZ_SUFFIXES or path.suffix.lower() in mermaid_adapter.MERMAID_SUFFIXES or path.suffix.lower() in plantuml_adapter.PLANTUML_SUFFIXES or path.suffix.lower() in openqasm_adapter.OPENQASM_SUFFIXES):
        return "graphviz" if path.suffix.lower() in graphviz_adapter.GRAPHVIZ_SUFFIXES and graphviz_adapter.is_probable_graphviz_source(path=path, text=text) else ("mermaid" if path.suffix.lower() in mermaid_adapter.MERMAID_SUFFIXES and mermaid_adapter.is_probable_mermaid_source(path=path, text=text) else ("plantuml" if path.suffix.lower() in plantuml_adapter.PLANTUML_SUFFIXES and plantuml_adapter.is_probable_plantuml_source(path=path, text=text) else ("openqasm" if path.suffix.lower() in openqasm_adapter.OPENQASM_SUFFIXES and openqasm_adapter.is_probable_openqasm_source(path=path, text=text) else "unknown")))  # noqa: E501
    if text is not None and (path.suffix.lower() in (move_adapter.MOVE_SUFFIXES | modelica_adapter.MODELICA_SUFFIXES | moonbit_adapter.MOONBIT_SOURCE_SUFFIXES | roc_adapter.ROC_SUFFIXES | rescript_adapter.RESCRIPT_SUFFIXES | hy_adapter.HY_SUFFIXES | wren_adapter.WREN_SUFFIXES | fennel_adapter.FENNEL_SUFFIXES | vyper_adapter.VYPER_SUFFIXES | dm_adapter.DM_SUFFIXES) or path.name.lower() in move_adapter.MOVE_CONFIG_BASENAMES or path.name.lower() in moonbit_adapter.MOONBIT_CONFIG_BASENAMES or path.name.lower() in rescript_adapter.RESCRIPT_CONFIG_BASENAMES):
        return "move" if ((path.suffix.lower() in move_adapter.MOVE_SUFFIXES and move_adapter.is_probable_move_source(path=path, text=text)) or (path.name.lower() in move_adapter.MOVE_CONFIG_BASENAMES and move_adapter.is_probable_move_config(path=path, text=text))) else ("modelica" if path.suffix.lower() in modelica_adapter.MODELICA_SUFFIXES and modelica_adapter.is_probable_modelica_source(path=path, text=text) else ("moonbit" if ((path.suffix.lower() in moonbit_adapter.MOONBIT_SOURCE_SUFFIXES and moonbit_adapter.is_probable_moonbit_source(path=path, text=text)) or (path.name.lower() in moonbit_adapter.MOONBIT_CONFIG_BASENAMES and moonbit_adapter.is_probable_moonbit_config(path=path, text=text))) else ("roc" if path.suffix.lower() in roc_adapter.ROC_SUFFIXES and roc_adapter.is_probable_roc_source(path=path, text=text) else ("rescript" if ((path.suffix.lower() in rescript_adapter.RESCRIPT_SUFFIXES and rescript_adapter.is_probable_rescript_source(path=path, text=text)) or (path.name.lower() in rescript_adapter.RESCRIPT_CONFIG_BASENAMES and rescript_adapter.is_probable_rescript_config(path=path, text=text))) else ("hy" if path.suffix.lower() in hy_adapter.HY_SUFFIXES and hy_adapter.is_probable_hy_source(path=path, text=text) else ("wren" if path.suffix.lower() in wren_adapter.WREN_SUFFIXES and wren_adapter.is_probable_wren_source(path=path, text=text) else ("fennel" if path.suffix.lower() in fennel_adapter.FENNEL_SUFFIXES and fennel_adapter.is_probable_fennel_source(path=path, text=text) else ("vyper" if path.suffix.lower() in vyper_adapter.VYPER_SUFFIXES and vyper_adapter.is_probable_vyper_source(path=path, text=text) else ("dm" if path.suffix.lower() in dm_adapter.DM_SUFFIXES and dm_adapter.is_probable_dm_source(path=path, text=text) else "unknown")))))))))  # noqa: E501
    if path.name.lower() in cmake_adapter.CMAKE_CONFIG_BASENAMES and text is not None:
        return "cmake" if cmake_adapter.is_probable_cmake_source(path=path, text=text) else "unknown"  # noqa: E501
    if path.name.lower() in meson_adapter.MESON_CONFIG_BASENAMES and text is not None:
        return "meson" if meson_adapter.is_probable_meson_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and (path.suffix.lower() in qmake_adapter.QMAKE_SUFFIXES or path.name.lower() in qmake_adapter.QMAKE_CONFIG_BASENAMES):
        return "qmake" if qmake_adapter.is_probable_qmake_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and ((path.suffix.lower() in qml_adapter.QML_SUFFIXES or path.name.lower() in qml_adapter.QML_CONFIG_BASENAMES) or path.suffix.lower() in vue_adapter.VUE_SUFFIXES or path.suffix.lower() in svelte_adapter.SVELTE_SUFFIXES or path.suffix.lower() in astro_adapter.ASTRO_SUFFIXES):
        return "qml" if (path.suffix.lower() in qml_adapter.QML_SUFFIXES or path.name.lower() in qml_adapter.QML_CONFIG_BASENAMES) and qml_adapter.is_probable_qml_source(path=path, text=text) else ("vue" if path.suffix.lower() in vue_adapter.VUE_SUFFIXES and vue_adapter.is_probable_vue_source(path=path, text=text) else ("svelte" if path.suffix.lower() in svelte_adapter.SVELTE_SUFFIXES and svelte_adapter.is_probable_svelte_source(path=path, text=text) else ("astro" if path.suffix.lower() in astro_adapter.ASTRO_SUFFIXES and astro_adapter.is_probable_astro_source(path=path, text=text) else "unknown")))  # noqa: E501
    if text is not None and path.suffix.lower() in gherkin_adapter.GHERKIN_SUFFIXES:
        return "gherkin" if gherkin_adapter.is_probable_gherkin_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in nextflow_adapter.NEXTFLOW_SOURCE_SUFFIXES:
        return "nextflow" if nextflow_adapter.is_probable_nextflow_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and sass_adapter.has_sass_path_hints(path):
        return "sass" if sass_adapter.is_probable_sass_source(path=path, text=text) else "unknown"
    if text is not None and (
        path.suffix.lower() in qsharp_adapter.QSHARP_SUFFIXES
        or path.name.lower() in qsharp_adapter.QSHARP_CONFIG_BASENAMES
    ):
        return "qsharp" if (
            (
                path.suffix.lower() in qsharp_adapter.QSHARP_SUFFIXES
                and qsharp_adapter.is_probable_qsharp_source(path=path, text=text)
            )
            or (
                path.name.lower() in qsharp_adapter.QSHARP_CONFIG_BASENAMES
                and qsharp_adapter.is_probable_qsharp_config(path=path, text=text)
            )
        ) else "unknown"
    if text is not None and opencl_adapter.has_opencl_path_hints(path):
        return "opencl" if opencl_adapter.is_probable_opencl_source(path=path, text=text) else "unknown"
    if text is not None and (
        path.suffix.lower() in clojurescript_adapter.CLOJURESCRIPT_SUFFIXES
        or path.name.lower() in clojurescript_adapter.CLOJURESCRIPT_CONFIG_NAMES
    ):
        return "clojurescript" if clojurescript_adapter.is_probable_clojurescript_source(
            path=path,
            text=text,
        ) else "unknown"
    if text is not None and al_adapter.has_al_path_hints(path):
        return "al" if al_adapter.is_probable_al_source(path=path, text=text) else "unknown"
    if text is not None and groovy_adapter.has_groovy_path_hints(path=path):
        return "groovy" if groovy_adapter.is_probable_groovy_source(path=path, text=text) else "unknown"
    if text is not None and (path.suffix.lower() in typst_adapter.TYPST_SUFFIXES or path.name.lower() in typst_adapter.TYPST_CONFIG_BASENAMES):
        return "typst" if ((path.suffix.lower() in typst_adapter.TYPST_SUFFIXES and typst_adapter.is_probable_typst_source(path=path, text=text)) or (path.name.lower() in typst_adapter.TYPST_CONFIG_BASENAMES and typst_adapter.is_probable_typst_config(path=path, text=text))) else "unknown"  # noqa: E501
    if text is not None and (path.suffix.lower() in (jinja_adapter.JINJA_SUFFIXES | liquid_adapter.LIQUID_SUFFIXES | handlebars_adapter.HANDLEBARS_SUFFIXES | mustache_adapter.MUSTACHE_SUFFIXES | nunjucks_adapter.NUNJUCKS_SUFFIXES | twig_adapter.TWIG_SUFFIXES | haml_adapter.HAML_SUFFIXES | slim_adapter.SLIM_SUFFIXES | erb_adapter.ERB_SUFFIXES) or path.suffix.lower() in smarty_adapter.SMARTY_SUFFIXES):
        return "jinja" if path.suffix.lower() in jinja_adapter.JINJA_SUFFIXES and jinja_adapter.is_probable_jinja_source(path=path, text=text) else ("liquid" if path.suffix.lower() in liquid_adapter.LIQUID_SUFFIXES and liquid_adapter.is_probable_liquid_source(path=path, text=text) else ("handlebars" if path.suffix.lower() in handlebars_adapter.HANDLEBARS_SUFFIXES and handlebars_adapter.is_probable_handlebars_source(path=path, text=text) else ("mustache" if path.suffix.lower() in mustache_adapter.MUSTACHE_SUFFIXES and mustache_adapter.is_probable_mustache_source(path=path, text=text) else ("nunjucks" if path.suffix.lower() in nunjucks_adapter.NUNJUCKS_SUFFIXES and nunjucks_adapter.is_probable_nunjucks_source(path=path, text=text) else ("twig" if path.suffix.lower() in twig_adapter.TWIG_SUFFIXES and twig_adapter.is_probable_twig_source(path=path, text=text) else ("haml" if path.suffix.lower() in haml_adapter.HAML_SUFFIXES and haml_adapter.is_probable_haml_source(path=path, text=text) else ("slim" if path.suffix.lower() in slim_adapter.SLIM_SUFFIXES and slim_adapter.is_probable_slim_source(path=path, text=text) else ("smarty" if path.suffix.lower() in smarty_adapter.SMARTY_SUFFIXES and smarty_adapter.is_probable_smarty_source(path=path, text=text) else ("erb" if path.suffix.lower() in erb_adapter.ERB_SUFFIXES and erb_adapter.is_probable_erb_source(path=path, text=text) else "unknown")))))))))  # noqa: E501
    if text is not None and path.suffix.lower() in (rst_adapter.RST_SUFFIXES | asciidoc_adapter.ASCIIDOC_SUFFIXES | org_adapter.ORG_SUFFIXES):
        return "rst" if path.suffix.lower() in rst_adapter.RST_SUFFIXES and rst_adapter.is_probable_rst_source(path=path, text=text) else ("asciidoc" if path.suffix.lower() in asciidoc_adapter.ASCIIDOC_SUFFIXES and asciidoc_adapter.is_probable_asciidoc_source(path=path, text=text) else ("org" if path.suffix.lower() in org_adapter.ORG_SUFFIXES and org_adapter.is_probable_org_source(path=path, text=text) else "unknown"))  # noqa: E501
    if text is not None and blade_adapter.has_blade_path_hints(path):
        return "blade" if blade_adapter.is_probable_blade_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in (pug_adapter.PUG_SUFFIXES | ejs_adapter.EJS_SUFFIXES):
        return "pug" if path.suffix.lower() in pug_adapter.PUG_SUFFIXES and pug_adapter.is_probable_pug_source(path=path, text=text) else ("ejs" if path.suffix.lower() in ejs_adapter.EJS_SUFFIXES and ejs_adapter.is_probable_ejs_source(path=path, text=text) else "unknown")  # noqa: E501
    if text is not None and ((path.suffix.lower() in tex_adapter.TEX_SUFFIXES and path.suffix.lower() != ".cls") or path.name.lower() in tex_adapter.TEX_CONFIG_BASENAMES):
        return "tex" if (((path.suffix.lower() in tex_adapter.TEX_SUFFIXES and path.suffix.lower() != ".cls") and tex_adapter.is_probable_tex_source(path=path, text=text)) or (path.name.lower() in tex_adapter.TEX_CONFIG_BASENAMES and tex_adapter.is_probable_tex_config(path=path, text=text))) else "unknown"  # noqa: E501
    if text is not None and (path.suffix.lower() in protobuf_adapter.PROTOBUF_SUFFIXES or path.name.lower() in protobuf_adapter.PROTOBUF_CONFIG_BASENAMES):
        return "protobuf" if ((path.suffix.lower() in protobuf_adapter.PROTOBUF_SUFFIXES and protobuf_adapter.is_probable_protobuf_source(path=path, text=text)) or (path.name.lower() in protobuf_adapter.PROTOBUF_CONFIG_BASENAMES and protobuf_adapter.is_probable_protobuf_config(path=path, text=text))) else "unknown"  # noqa: E501
    if text is not None and path.suffix.lower() in (
        cuda_adapter.CUDA_SUFFIXES
        | cython_adapter.CYTHON_SUFFIXES
        | hlsl_adapter.HLSL_SOURCE_SUFFIXES
        | shaderlab_adapter.SHADERLAB_SOURCE_SUFFIXES
        | wgsl_adapter.WGSL_SUFFIXES
        | stan_adapter.STAN_SUFFIXES
    ):
        return "cuda" if path.suffix.lower() in cuda_adapter.CUDA_SUFFIXES and cuda_adapter.is_probable_cuda_source(path=path, text=text) else ("cython" if path.suffix.lower() in cython_adapter.CYTHON_SUFFIXES and cython_adapter.is_probable_cython_source(path=path, text=text) else ("hlsl" if path.suffix.lower() in hlsl_adapter.HLSL_SOURCE_SUFFIXES and hlsl_adapter.is_probable_hlsl_source(path=path, text=text) else ("shaderlab" if path.suffix.lower() in shaderlab_adapter.SHADERLAB_SOURCE_SUFFIXES and shaderlab_adapter.is_probable_shaderlab_source(path=path, text=text) else ("wgsl" if path.suffix.lower() in wgsl_adapter.WGSL_SUFFIXES and wgsl_adapter.is_probable_wgsl_source(path=path, text=text) else ("stan" if path.suffix.lower() in stan_adapter.STAN_SUFFIXES and stan_adapter.is_probable_stan_source(path=path, text=text) else "unknown")))))  # noqa: E501
    if path.name.lower() in bitbake_adapter.BITBAKE_CONFIG_BASENAMES and text is not None:
        return "bitbake" if bitbake_adapter.is_probable_bitbake_source(path=path, text=text) else "unknown"  # noqa: E501
    if not suffix and text is not None:
        if fish_adapter.is_probable_fish_source(path=path, text=text):
            return "fish"
        if awk_adapter.is_probable_awk_source(path=path, text=text):
            return "awk"
    if path.name.lower() == "cakefile" and text is not None:
        return "coffeescript" if coffee_adapter.is_probable_coffeescript_source(path=path, text=text) else "unknown"
    if starlark_adapter.has_starlark_path_hints(path):
        if text is not None and not starlark_adapter.is_probable_starlark_source(path=path, text=text):  # noqa: E501
            return "unknown"
        return "starlark"
    if path.name.lower() in hack_adapter.HACK_CONFIG_BASENAMES and text is not None:
        return "hack" if hack_adapter.is_probable_hack_source(path=path, text=text) else "unknown"
    if path.name.lower() in lean_adapter.LEAN_CONFIG_BASENAMES and text is not None:
        return "lean" if lean_adapter.is_probable_lean_source(path=path, text=text) else "unknown"
    if path.name.lower() in coq_adapter.COQ_CONFIG_BASENAMES and text is not None:
        return "coq" if coq_adapter.is_probable_coq_source(path=path, text=text) else "unknown"
    if path.name.lower() == "v.mod":
        if text is not None and not v_adapter.is_probable_v_source(path=path, text=text):
            return "unknown"
        return "v"
    if suffix == ".applescript":
        if text is not None and not osa_adapter.is_probable_applescript_source(path=path, text=text):  # noqa: E501
            return "unknown"
        return "applescript"
    if suffix == ".st":
        if text is not None:
            if smalltalk_adapter.is_probable_smalltalk_source(path=path, text=text):
                return "smalltalk"
            return "unknown"
        if smalltalk_adapter.has_smalltalk_path_hints(path):
            return "smalltalk"
    if suffix in {".coffee", ".litcoffee"} and text is not None:
        if coffee_adapter.is_probable_coffeescript_source(path=path, text=text):
            return "coffeescript"
        return "unknown"
    if suffix == ".scpt" and text is not None:
        if osa_adapter.is_probable_applescript_source(path=path, text=text):
            return "applescript"
        return "unknown"
    if suffix == ".bicep" and text is not None:
        if bicep_adapter.is_probable_bicep_source(path=path, text=text):
            return "bicep"
        return "unknown"
    if suffix == ".tla" and text is not None:
        if tlaplus_adapter.is_probable_tlaplus_source(path=path, text=text):
            return "tlaplus"
        return "unknown"
    if suffix in {".au3", ".nut"} and text is not None:
        return "autoit" if suffix == ".au3" and autoit_adapter.is_probable_autoit_source(path=path, text=text) else ("squirrel" if suffix == ".nut" and squirrel_adapter.is_probable_squirrel_source(path=path, text=text) else "unknown")  # noqa: E501
    if suffix in {".robot", ".resource"} and text is not None:
        return "robotframework" if robotframework_adapter.is_probable_robotframework_source(path=path, text=text) else "unknown"
    if suffix == ".dockerfile":
        return "dockerfile" if text is None or dockerfile_adapter.is_probable_dockerfile_source(path=path, text=text) else "unknown"  # noqa: E501
    if suffix in {".scss", ".less", ".styl"} and text is not None:
        return "scss" if suffix == ".scss" and scss_adapter.is_probable_scss_source(path=path, text=text) else ("less" if suffix == ".less" and less_adapter.is_probable_less_source(path=path, text=text) else ("stylus" if suffix == ".styl" and stylus_adapter.is_probable_stylus_source(path=path, text=text) else "unknown"))  # noqa: E501
    if suffix in {".mk", ".factor", ".cue", ".stan"} and text is not None:
        return "makefile" if suffix == ".mk" and makefile_adapter.is_probable_makefile_source(path=path, text=text) else ("factor" if suffix == ".factor" and factor_adapter.is_probable_factor_source(path=path, text=text) else ("cue" if suffix == ".cue" and cue_adapter.is_probable_cue_source(path=path, text=text) else ("stan" if suffix == ".stan" and stan_adapter.is_probable_stan_source(path=path, text=text) else "unknown")))  # noqa: E501
    if suffix in {".e", ".ecf", ".ace"} and text is not None:
        if eiffel_adapter.is_probable_eiffel_source(path=path, text=text):
            return "eiffel"
        return "unknown"
    if text is not None and vimscript_adapter.has_vimscript_path_hints(path):
        if suffix == ".vim" and labview_adapter.is_probable_labview_source(path=path, text=text):
            return "labview"
        if vimscript_adapter.is_probable_vimscript_source(path=path, text=text):
            return "vimscript"
        return "unknown"
    if (
        not suffix
        and text is not None
        and emacslisp_adapter.is_probable_emacslisp_source(path=path, text=text)
    ):
        return "emacslisp"
    if suffix in {".cfc", ".cfm", ".cfml"} and text is not None:
        if cfml_adapter.is_probable_cfml_source(path=path, text=text):
            return "cfml"
        return "unknown"
    if suffix == ".cls" and text is not None:
        if apex_adapter.is_probable_apex_source(path=path, text=text):
            return "apex"
        if tex_adapter.is_probable_tex_source(path=path, text=text):
            return "tex"
        if _has_classic_visual_basic_project_context(path=path, repo_root=repo_root) and (
            cvb.is_probable_classic_visual_basic_source(
                path=path,
                text=text,
            )
        ):
            return "vb6"
        if vba_adapter.is_probable_vba_source(path=path, text=text):
            return "vba"
        if cvb.is_probable_classic_visual_basic_source(
            path=path,
            text=text,
        ):
            return "vb6"
        return "unknown"
    if suffix in {".bas", ".frm"} and text is not None:
        if _has_classic_visual_basic_project_context(path=path, repo_root=repo_root) and (
            cvb.is_probable_classic_visual_basic_source(
                path=path,
                text=text,
            )
        ):
            return "vb6"
        if vba_adapter.is_probable_vba_source(path=path, text=text):
            return "vba"
        if cvb.is_probable_classic_visual_basic_source(
            path=path,
            text=text,
        ):
            return "vb6"
        return "unknown"
    if suffix in {".ctl", ".vbp"} and text is not None:
        if suffix == ".ctl" and labview_adapter.is_probable_labview_source(path=path, text=text):
            return "labview"
        if cvb.is_probable_classic_visual_basic_source(
            path=path,
            text=text,
        ):
            return "vb6"
        return "unknown"
    if suffix in {".apex", ".trigger"} and text is not None:
        if apex_adapter.is_probable_apex_source(path=path, text=text):
            return "apex"
        return "unknown"
    if suffix == ".wsf" and text is not None:
        if vbscript_adapter.is_probable_vbscript_source(path=path, text=text):
            return "vbscript"
        return "unknown"
    if path.name in {"Puppetfile", "Modulefile"} and text is not None:
        return "puppet" if puppet_adapter.is_probable_puppet_source(path=path, text=text) else "unknown"  # noqa: E501
    if path.name.lower() == "metadata.json" and text is not None and puppet_adapter.is_probable_puppet_source(path=path, text=text):  # noqa: E501
        return "puppet"
    if path.name.lower() == "nextflow.config" and text is not None:
        return "nextflow" if nextflow_adapter.is_probable_nextflow_source(path=path, text=text) else "unknown"  # noqa: E501
    if suffix in {".vala", ".vapi"} and text is not None:
        return "vala" if vala_adapter.is_probable_vala_source(path=path, text=text) else "unknown"
    if suffix == ".as" and text is not None:
        return "actionscript" if as3_adapter.is_probable_actionscript_source(path=path, text=text) else "unknown"  # noqa: E501
    if suffix == ".sb3" and text is not None:
        return "scratch" if scratch_adapter.is_probable_scratch_source(path=path, text=text) else "unknown"  # noqa: E501
    if suffix == ".gd" and text is not None:
        if gdscript_adapter.is_probable_gdscript_source(path=path, text=text):
            return "gdscript"
        return "unknown"
    if suffix == ".gml" and text is not None:
        return "gml" if gml_adapter.is_probable_gml_source(path=path, text=text) else "unknown"
    if (
        text is not None
        and (
            suffix in _AGDA_SUFFIXES
            or str(path).lower().endswith((".lagda.md", ".lagda.rst", ".lagda.tex", ".lagda.org"))
        )
    ):
        return "agda" if agda_adapter.is_probable_agda_source(path=path, text=text) else "unknown"
    if suffix == ".gleam" and text is not None:
        return "gleam" if gleam_adapter.is_probable_gleam_source(path=path, text=text) else "unknown"  # noqa: E501
    if suffix in {".hx", ".hxml"} and text is not None:
        return "haxe" if haxe_adapter.is_probable_haxe_source(path=path, text=text) else "unknown"
    if suffix in {".idr", ".lidr", ".ipkg"} and text is not None:
        return "idris" if idris_adapter.is_probable_idris_source(path=path, text=text) else "unknown"  # noqa: E501
    if suffix in {".hack", ".hh", ".hhi", ".php"} and text is not None:
        if hack_adapter.is_probable_hack_source(path=path, text=text):
            return "hack"
        if suffix in {".hack", ".hhi"}:
            return "unknown"
    if suffix in {".lua", ".luau"} and text is not None:
        return "luau" if luau_adapter.is_probable_luau_source(path=path, text=text) else (
            "unknown" if suffix == ".luau" else "lua"
        )
    if suffix == ".nix" and text is not None:
        return "nix" if nix_adapter.is_probable_nix_source(path=path, text=text) else "unknown"
    if suffix == ".nu" and text is not None:
        return "nushell" if nushell_adapter.is_probable_nushell_source(path=path, text=text) else "unknown"  # noqa: E501
    if suffix == ".xml" and text is not None:
        if xpp_adapter.is_probable_xpp_source(path=path, text=text) or (
            xpp_adapter.is_probable_xpp_descriptor_config(path=path, text=text)
        ):
            return "xpp"
        if haxe_adapter.is_probable_haxe_source(path=path, text=text):
            return "haxe"
        return "unknown"
    if suffix == ".inc" and text is not None:
        if assembly_adapter.is_probable_assembly_source(path=path, text=text):
            return "assembly"
        if gams_adapter.is_probable_gams_source(path=path, text=text):
            return "gams"
        return "bitbake" if bitbake_adapter.is_probable_bitbake_source(path=path, text=text) else "unknown"  # noqa: E501
    if suffix == ".pl" and text is not None:
        if prolog_adapter.is_probable_prolog_source(path=path, text=text):
            return "prolog"
    if suffix in {".rkt", ".rktl"} and text is not None:
        if racket_adapter.is_probable_racket_source(path=path, text=text):
            return "racket"
        return "unknown"
    if suffix in {".scm", ".ss", ".sld", ".sps"} and text is not None:
        if scheme_adapter.is_probable_scheme_source(path=path, text=text):
            return "scheme"
        return "unknown"
    if suffix == ".scad" and text is not None:
        return "openscad" if openscad_adapter.is_probable_openscad_source(path=path, text=text) else "unknown"
    if suffix == ".purs" and text is not None:
        return "purescript" if purs_adapter.is_probable_purescript_source(path=path, text=text) else "unknown"
    if suffix in {".mo", ".roc", ".res", ".resi"} and text is not None:
        return "modelica" if suffix == ".mo" and modelica_adapter.is_probable_modelica_source(path=path, text=text) else ("roc" if suffix == ".roc" and roc_adapter.is_probable_roc_source(path=path, text=text) else ("rescript" if suffix in {".res", ".resi"} and rescript_adapter.is_probable_rescript_source(path=path, text=text) else "unknown"))
    if suffix in _RAKU_SUFFIXES and text is not None:
        if raku_adapter.is_probable_raku_source(path=path, text=text):
            return "raku"
        return "unknown"
    if suffix == ".el" and text is not None:
        return (
            "emacslisp"
            if emacslisp_adapter.is_probable_emacslisp_source(path=path, text=text)
            else "unknown"
        )
    if suffix == ".fish" and text is not None:
        return "fish" if fish_adapter.is_probable_fish_source(path=path, text=text) else "unknown"
    if suffix in {".v", ".vh"} and text is not None:
        if suffix == ".v" and coq_adapter.is_probable_coq_source(path=path, text=text):
            return "coq"
        if suffix == ".v" and v_adapter.is_probable_v_source(path=path, text=text):
            return "v"
        if verilog_adapter.is_probable_verilog_source(path=path, text=text):
            return "verilog"
        if sv_adapter.is_probable_systemverilog_source(path=path, text=text):
            return "systemverilog"
        return "unknown"
    if suffix in {".vhd", ".vhdl"} and text is not None:
        if vhdl_adapter.is_probable_vhdl_source(path=path, text=text):
            return "vhdl"
        return "unknown"
    if suffix in {".sql", ".sqlproj", ".dbproj"} and text is not None:
        if tsql_adapter.is_probable_tsql_source(path=path, text=text):
            return "tsql"
        return "unknown" if suffix in {".sqlproj", ".dbproj"} else "sql"
    if suffix == ".pp" and text is not None:
        if puppet_adapter.is_probable_puppet_source(path=path, text=text):
            return "puppet"
        if delphi_adapter.is_probable_delphi_source(path=path, text=text):
            return "delphi"
    if suffix in {".pas", ".dpr", ".dpk", ".dfm", ".fmx"} and text is not None:
        if delphi_adapter.is_probable_delphi_source(path=path, text=text):
            return "delphi"
    if suffix == ".l5x":
        if text is not None and not ladder_adapter.is_probable_ladder_source(path=path, text=text):
            return "unknown"
        return "ladder"
    if suffix == ".prg" and text is not None:
        if foxpro_adapter.is_probable_foxpro_source(path=path, text=text):
            return "foxpro"
        return "unknown"
    if suffix in {".asd", ".lisp", ".lsp"}:
        return "lisp"
    if suffix in {".rkt", ".rktl"}:
        return "racket"
    if suffix in {".scm", ".ss", ".sld", ".sps"}:
        return "scheme"
    if suffix == ".nf":
        return "nextflow"
    if suffix in _DIRECT_TEXT_SUFFIX_LANGUAGE_MAP:
        return _DIRECT_TEXT_SUFFIX_LANGUAGE_MAP[suffix]
    if suffix in {".sml", ".sig", ".fun"}:
        return "sml"
    if suffix == ".m":
        if text is not None and matlab_adapter.is_probable_matlab_source(path=path, text=text):
            return "matlab"
        if (
            text is not None
            and objc_adapter.is_probable_objective_c_source(path=path, text=text)
        ):
            return "objectivec"
        if text is not None and wolfram_adapter.is_probable_wolfram_source(path=path, text=text):
            return "wolfram"
        if matlab_adapter.has_matlab_path_hints(path):
            return "matlab"
        if wolfram_adapter.has_wolfram_path_hints(path):
            return "wolfram"
        return "unknown"
    if suffix == ".mm":
        if text is not None and not objc_adapter.is_probable_objective_c_source(
            path=path,
            text=text,
        ):
            return "cpp"
        return "objectivec"
    if suffix in {".v", ".vh"}:
        if verilog_adapter.has_verilog_path_hints(path):
            return "verilog"
        if sv_adapter.has_systemverilog_path_hints(path):
            return "systemverilog"
        return "unknown"
    if suffix in {".vhd", ".vhdl"}:
        return "vhdl"
    if suffix in {".dpr", ".dpk", ".dfm", ".fmx"}:
        return "delphi"
    if suffix in {
        ".ahk", ".agda", ".agda-lib", ".au3", ".bicep", ".chpl", ".compute", ".dockerfile", ".factor", ".feature", ".g4", ".dot", ".gv", ".mmd", ".mermaid", ".puml", ".plantuml", ".iuml", ".qasm", ".fx", ".fxh", ".cginc", ".hack", ".hhi", ".hlsl", ".hlsli", ".wgsl", ".j2", ".jinja", ".jinja2", ".liquid", ".hbs", ".handlebars", ".mustache", ".njk", ".nunj", ".nunjucks", ".twig", ".haml", ".slim", ".erb", ".rhtml", ".pug", ".jade", ".ejs", ".proto", ".move", ".roc", ".res", ".resi", ".scss", ".less", ".styl", ".svelte", ".astro", ".shader", ".hx", ".typ", ".tex", ".sty", ".ltx", ".dtx", ".rst", ".rest", ".adoc", ".asciidoc", ".asc", ".org",
        ".hxml", ".odin",
        ".idr", ".ipkg", ".nut", ".tla", ".lgt", ".logtalk", ".lagda", ".lidr", ".xpp", ".xpo", ".sb3",
    }:
        return {
            ".ahk": "autohotkey", ".au3": "autoit",
            ".agda": "agda", ".agda-lib": "agda",
            ".bicep": "bicep", ".chpl": "chapel", ".compute": "hlsl", ".dockerfile": "dockerfile", ".factor": "factor", ".fx": "hlsl", ".fxh": "hlsl", ".cginc": "hlsl",
            ".hack": "hack", ".hhi": "hack",
            ".hlsl": "hlsl", ".hlsli": "hlsl", ".wgsl": "wgsl", ".j2": "jinja", ".jinja": "jinja", ".jinja2": "jinja", ".liquid": "liquid", ".hbs": "handlebars", ".handlebars": "handlebars", ".mustache": "mustache", ".njk": "nunjucks", ".nunj": "nunjucks", ".nunjucks": "nunjucks", ".twig": "twig", ".haml": "haml", ".slim": "slim", ".erb": "erb", ".rhtml": "erb", ".pug": "pug", ".jade": "pug", ".ejs": "ejs", ".feature": "gherkin", ".g4": "antlr", ".dot": "graphviz", ".gv": "graphviz", ".mmd": "mermaid", ".mermaid": "mermaid", ".puml": "plantuml", ".plantuml": "plantuml", ".iuml": "plantuml", ".qasm": "openqasm", ".proto": "protobuf", ".move": "move", ".roc": "roc", ".res": "rescript", ".resi": "rescript", ".scss": "scss", ".less": "less", ".styl": "stylus", ".svelte": "svelte", ".astro": "astro", ".shader": "shaderlab", ".hx": "haxe", ".hxml": "haxe", ".idr": "idris", ".ipkg": "idris", ".odin": "odin", ".typ": "typst", ".tex": "tex", ".sty": "tex", ".ltx": "tex", ".dtx": "tex", ".rst": "rst", ".rest": "rst", ".adoc": "asciidoc", ".asciidoc": "asciidoc", ".asc": "asciidoc", ".org": "org",
            ".lagda": "agda", ".lidr": "idris", ".nut": "squirrel", ".tla": "tlaplus", ".lgt": "logtalk",
            ".logtalk": "logtalk", ".xpp": "xpp", ".xpo": "xpp", ".sb3": "scratch",
        }[suffix]
    if suffix == ".xml":
        if xpp_adapter.has_xpp_path_hints(path):
            return "xpp"
        return "unknown"
    if suffix in {".mq5", ".mqh", ".mqproj", ".vala", ".vapi"}:
        return "mql5" if suffix.startswith(".mq") else "vala"
    if path.name.lower() == "cakefile":
        return "coffeescript"
    if suffix in {".h", ".pch"} and text is not None:
        if objc_adapter.is_probable_objective_c_source(path=path, text=text):
            return "objectivec"
    return {
        ".abap": "abap",
        ".agda": "agda",
        ".agda-lib": "agda",
        ".ada": "ada",
        ".adb": "ada",
        ".a51": "assembly",
        ".ahk": "autohotkey",
        ".asm": "assembly",
        ".auk": "awk",
        ".as": "actionscript",
        ".applescript": "applescript",
        ".ads": "ada",
        ".apex": "apex", ".au3": "autoit",
        ".awk": "awk",
        ".bicep": "bicep",
        ".bzl": "starlark",
        ".bash": "shell",
        ".bashrc": "shell",
        ".c": "c",
        ".cbl": "cobol",
        ".cc": "cpp",
        ".clj": "clojure",
        ".cljc": "clojure",
        ".cljs": "clojurescript",
        ".cob": "cobol",
        ".cobol": "cobol",
        ".coffee": "coffeescript",
        ".cpp": "cpp",
        ".cpy": "cobol",
        ".cr": "crystal",
        ".cfc": "cfml",
        ".cfm": "cfml",
        ".cfml": "cfml",
        ".cxx": "cpp",
        ".cs": "cs",
        ".csx": "cs",
        ".d": "d",
        ".dart": "dart",
        ".dfm": "delphi", ".di": "d", ".dpk": "delphi", ".dpr": "delphi",
        ".edn": "edn",
        ".el": "emacslisp",
        ".elm": "elm",
        ".erl": "erlang", ".ex": "ex", ".exs": "ex",
        ".f": "fortran", ".f03": "fortran", ".f08": "fortran",
        ".f90": "fortran", ".f95": "fortran", ".for": "fortran",
        ".hrl": "erlang",
        ".hack": "hack", ".hhi": "hack",
        ".hx": "haxe",
        ".hxml": "haxe",
        ".idr": "idris",
        ".h": "cpp",
        ".hh": "cpp",
        ".hpp": "cpp",
        ".hs": "haskell",
        ".hsc": "haskell",
        ".hxx": "cpp",
        ".s": "assembly",
        ".ipp": "cpp",
        ".java": "java",
        ".jl": "julia",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ksh": "shell",
        ".kt": "kotlin", ".kts": "kotlin",
        ".lhs": "haskell", ".litcoffee": "coffeescript", ".lgt": "logtalk", ".logtalk": "logtalk",
        ".chpl": "chapel", ".lvclass": "labview",
        ".lvlib": "labview",
        ".lvproj": "labview",
        ".lisp": "lisp",
        ".lsp": "lisp",
        ".lua": "lua",
        ".luau": "luau",
        ".mawk": "awk",
        ".mj": "mojo",
        ".mq5": "mql5",
        ".mqh": "mql5",
        ".mqproj": "mql5", ".gms": "gams", ".hy": "hy", ".wren": "wren", ".janet": "janet", ".fnl": "fennel", ".fnlm": "fennel", ".vy": "vyper", ".vyi": "vyper", ".ipkg": "idris",
        ".odin": "odin", ".factor": "factor",
        ".lagda": "agda",
        ".lidr": "idris",
        ".nix": "nix",
        ".ml": "ocaml",
        ".mlb": "txt",
        ".mli": "ocaml",
        ".mojo": "mojo",
        ".cm": "txt",
        ".nim": "nim",
        ".nimble": "nimble",
        ".nims": "nimscript",
        ".nawk": "awk",
        ".asd": "lisp",
        ".opam": "opam",
        ".pas": "pascal",
        ".php": "php",
        ".pl": "perl",
        ".pkb": "plsql",
        ".pks": "plsql",
        ".pm": "perl",
        ".pp": "pascal",
        ".prolog": "prolog",
        ".prg": "unknown",
        ".prc": "plsql",
        ".pls": "plsql",
        ".purs": "purescript", ".res": "rescript", ".resi": "rescript", ".roc": "roc",
        **dict.fromkeys(sorted(_RAKU_SUFFIXES), "raku"),
        ".ps1": "powershell",
        ".psgi": "perl",
        ".psm1": "powershell",
        ".stan": "stan", ".cu": "cuda", ".cuh": "cuda", ".dockerfile": "dockerfile", ".proto": "protobuf", ".move": "move", ".shader": "shaderlab", ".wgsl": "wgsl", ".j2": "jinja", ".jinja": "jinja", ".jinja2": "jinja", ".liquid": "liquid", ".hbs": "handlebars", ".handlebars": "handlebars", ".mustache": "mustache", ".njk": "nunjucks", ".nunj": "nunjucks", ".nunjucks": "nunjucks", ".twig": "twig", ".haml": "haml", ".slim": "slim", ".erb": "erb", ".rhtml": "erb", ".pug": "pug", ".jade": "pug", ".ejs": "ejs", ".robot": "robotframework", ".resource": "robotframework", ".feature": "gherkin", ".g4": "antlr", ".dot": "graphviz", ".gv": "graphviz", ".mmd": "mermaid", ".mermaid": "mermaid", ".puml": "plantuml", ".plantuml": "plantuml", ".iuml": "plantuml", ".qasm": "openqasm", ".scss": "scss", ".less": "less", ".styl": "stylus", ".svelte": "svelte", ".astro": "astro", ".typ": "typst", ".tex": "tex", ".sty": "tex", ".ltx": "tex", ".dtx": "tex", ".rst": "rst", ".rest": "rst", ".adoc": "asciidoc", ".asciidoc": "asciidoc", ".asc": "asciidoc", ".org": "org",
        ".hlsl": "hlsl", ".hlsli": "hlsl", ".fx": "hlsl",
        ".fxh": "hlsl", ".cginc": "hlsl", ".compute": "hlsl",
        **dict.fromkeys((".pro", ".pri", ".prf"), "qmake"), ".qml": "qml",
        ".py": "python",
        ".r": "r",
        ".rb": "ruby",
        **dict.fromkeys((".rkt", ".rktl"), "racket"),
        ".rockspec": "rockspec",
        ".rpg": "rpg",
        ".rpginc": "rpg",
        ".rpgle": "rpg",
        ".rpgleinc": "rpg",
        ".rs": "rust",
        ".sas": "sas",
        ".scad": "openscad",
        **dict.fromkeys((".scm", ".sld", ".sps", ".ss"), "scheme"),
        ".scpt": "unknown",
        ".sb3": "scratch",
        ".sol": "solidity",
        ".go": "go",
        ".sbt": "scala",
        ".scala": "scala",
        ".sh": "shell",
        ".dbproj": "tsql",
        ".sqlrpg": "rpg",
        ".sqlrpgle": "rpg",
        ".trg": "plsql",
        ".sqlproj": "tsql",
        ".st": "unknown",
        ".swift": "swift",
        ".star": "starlark",
        ".sv": "systemverilog",
        ".svh": "systemverilog",
        ".tla": "tlaplus",
        ".trigger": "apex",
        ".sql": "sql",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".tcl": "tcl",
        ".tm": "tcl",
        ".tpp": "cpp",
        ".vala": "vala",
        ".vapi": "vala",
        ".vb": "vb",
        ".vh": "unknown",
        ".v": "unknown",
        ".vhd": "vhdl",
        ".vhdl": "vhdl",
        ".bas": "unknown",
        ".cls": "unknown",
        ".ctl": "unknown",
        ".frm": "unknown",
        ".gawk": "awk",
        ".gd": "gdscript",
        ".gleam": "gleam",
        ".gml": "gml",
        ".nu": "nushell",
        ".nut": "squirrel",
        ".vbe": "vbscript",
        ".vbp": "unknown",
        ".vbs": "vbscript",
        ".vi": "labview",
        ".vim": "unknown",
        ".vit": "labview",
        ".wl": "wolfram", ".wls": "wolfram", ".xpo": "xpp", ".xpp": "xpp",
        ".wsf": "unknown",
        ".dproj": "xml",
        ".fmx": "delphi",
        ".lpi": "xml",
        ".lpk": "xml",
        ".lpr": "pascal",
        ".podspec": "txt",
        ".zsh": "shell", ".zsh-theme": "shell", ".cue": "cue", ".zig": "zig",
        ".json": "json", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml",
        ".html": "html", ".css": "css", ".md": "markdown",
        ".fs": "fsharp",
        ".fsi": "fsharp",
        ".fsx": "fsharp",
        ".fish": "fish", ".groovy": "groovy", ".nf": "nextflow", ".glsl": "glsl", ".vert": "glsl", ".frag": "glsl", ".geom": "glsl", ".tesc": "glsl", ".tese": "glsl", ".comp": "glsl", ".gpr": "txt",  # noqa: E501
    }.get(suffix, "unknown")
def _estimate_tokens(text: str) -> int:
    return max(1, (len(text.encode("utf-8")) + 3) // 4)
def _module_aliases_for_path(file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    suffix_lower = path.suffix.lower()
    if suffix_lower == ".m":
        return set()
    aliases = {path.stem, file_path}
    without_suffix_path = str(path.with_suffix(""))
    without_suffix = without_suffix_path.replace("/", ".")
    aliases.add(without_suffix)
    if path.name == "__init__.py":
        aliases.add(str(path.parent).replace("/", "."))
    if suffix_lower in {
        ".abap",
        ".ada",
        ".adb",
        ".ads",
        ".awk",
        ".auk",
        ".c",
        ".cbl",
        ".cc",
        ".cpp",
        ".pxd",
        ".pxi",
        ".pyx",
        ".cob",
        ".cobol",
        ".coffee",
        ".cfc",
        ".cfm",
        ".cfml",
        ".cpy",
        ".cxx",
        ".clj",
        ".cljc",
        ".cljs",
        ".cr",
        ".dart",
        ".erl",
        ".ex",
        ".exs",
        ".fs",
        ".fsi",
        ".fsx",
        ".h",
        ".hack",
        ".hh",
        ".hhi",
        ".hpp",
        ".hrl",
        ".hs",
        ".hsc",
        ".hxx",
        ".ipp",
        ".jl",
        ".js",
        ".jsx",
        ".ksh",
        ".lhs",
        ".litcoffee",
        ".lisp",
        ".lsp",
        ".lvclass",
        ".lvlib",
        ".lvproj",
        ".lua",
        ".luau",
        ".mawk",
        ".mj",
        ".ml",
        ".mli",
        ".mojo",
        ".mq5",
        ".mqh",
        ".gms",
        ".nix",
        ".odin",
        ".factor",
        ".pas",
        ".php",
        ".pl",
        ".pkb",
        ".pks",
        ".pm",
        ".pp",
        ".prolog",
        ".prg",
        ".prc",
        ".pls",
        ".purs",
        *_RAKU_SUFFIXES,
        ".ps1",
        ".psgi",
        ".psm1",
        ".py",
        ".r",
        ".rb",
        ".rpg",
        ".rpginc",
        ".rpgle",
        ".rpgleinc",
        ".sas",
        ".scad",
        ".sml",
        ".sol",
        ".apex",
        ".applescript",
        ".sig",
        ".sh",
        ".scpt",
        ".st",
        ".sqlrpg",
        ".sqlrpgle",
        ".sql",
        ".swift",
        ".tcl",
        ".tm",
        ".trigger",
        ".trg",
        ".tpp",
        ".ts",
        ".tsx",
        ".v",
        ".fun",
        ".vala",
        ".vapi",
        ".vb",
        ".vbe",
        ".vi",
        ".vim",
        ".vit",
        ".bas",
        ".cls",
        ".ctl",
        ".frm",
        ".vbp",
        ".vbs",
        ".wl",
        ".wls",
        ".wsf",
        ".asd", ".dockerfile", ".feature", ".g4", ".dot", ".gv", ".mmd", ".mermaid", ".puml", ".plantuml", ".iuml", ".nf", ".fnl", ".fnlm", ".qasm", ".gawk", ".gleam", ".hy", ".wren", ".janet", ".bicep", ".chpl", ".tla", ".lgt", ".logtalk", ".cue", ".proto", ".move", ".roc", ".stan", ".cu", ".cuh", ".hlsl", ".hlsli", ".wgsl", ".j2", ".jinja", ".jinja2", ".liquid", ".hbs", ".handlebars", ".mustache", ".njk", ".nunj", ".nunjucks", ".twig", ".haml", ".slim", ".tpl", ".erb", ".rhtml", ".pug", ".jade", ".ejs", ".scss", ".less", ".styl", ".svelte", ".astro", ".shader", ".fx", ".fxh", ".cginc", ".compute", ".typ", ".tex", ".sty", ".ltx", ".dtx", ".rst", ".rest", ".adoc", ".asciidoc", ".asc", ".org",
        ".agda", ".agda-lib", ".nu", ".nawk", ".dpk", ".dpr", ".lpr", ".zsh",
        ".zsh-theme",
        ".zig",
        ".cs",
    }:
        aliases.add(without_suffix_path)
    if suffix_lower in _JS_LIKE_SUFFIXES and path.stem == "index":
        parent = str(path.parent)
        if parent and parent != ".":
            aliases.add(parent)
            aliases.add(parent.replace("/", "."))
    if suffix_lower == ".go":
        parent = str(path.parent)
        if parent and parent != ".":
            aliases.add(parent)
            aliases.add(parent.replace("/", "."))
    if suffix_lower == ".rs" and path.stem in {"mod", "lib", "main"}:
        parent = str(path.parent)
        if parent and parent != ".":
            aliases.add(parent)
            aliases.add(parent.replace("/", "."))
        if path.stem in {"lib", "main"}:
            aliases.add("crate")
    if suffix_lower in {".java", ".kt", ".kts", ".scala"}:
        source_parts = list(path.parts)
        marker_index = None
        for index, part in enumerate(source_parts):
            lowered_part = part.lower()
            if lowered_part in {"java", "kotlin"} or lowered_part.startswith("scala"):
                marker_index = index
                break
        if marker_index is not None:
            package_parts = list(source_parts[marker_index + 1 : -1])
            if suffix_lower == ".scala" and path.stem == "package":
                if package_parts:
                    aliases.add(".".join(package_parts))
            elif path.stem != "package-info":
                package_parts.append(path.stem)
                if package_parts:
                    aliases.add(".".join(package_parts))
    if suffix_lower in {".ex", ".exs"}:
        source_parts = list(path.parts)
        if "lib" in source_parts:
            lib_index = source_parts.index("lib")
            module_parts = list(source_parts[lib_index + 1 : -1])
            stem_parts = [part for part in path.stem.split(".") if part]
            module_parts.extend(stem_parts)
            camelized_parts = [
                "".join(piece.capitalize() for piece in segment.split("_") if piece)
                for segment in module_parts
                if segment
            ]
            if camelized_parts:
                aliases.add(".".join(camelized_parts))
    return {alias for alias in aliases if alias}
def _module_index_values(module_index: dict[str, str]) -> tuple[str, ...]:
    return _module_index_lookup(module_index).values
def _module_index_lookup(module_index: dict[str, str]) -> _ModuleIndexLookup:
    cache_key = tuple(sorted(set(module_index.values())))
    cached_lookup = _MODULE_INDEX_LOOKUP_CACHE.get(cache_key)
    if cached_lookup is not None:
        return cached_lookup
    values = cache_key
    exact_paths: dict[str, str] = {}
    suffix_paths: dict[str, str] = {}
    directory_suffix_paths: dict[str, str] = {}
    for file_path in values:
        lowered_file_path = file_path.lower()
        exact_paths.setdefault(lowered_file_path, file_path)
        path_parts = PurePosixPath(lowered_file_path).parts
        for start in range(len(path_parts)):
            suffix_paths.setdefault("/".join(path_parts[start:]), file_path)
        directory_parts = path_parts[:-1]
        for start in range(len(directory_parts)):
            directory_suffix_paths.setdefault("/".join(directory_parts[start:]), file_path)
    lookup = _ModuleIndexLookup(
        values=values,
        exact_paths=exact_paths,
        suffix_paths=suffix_paths,
        directory_suffix_paths=directory_suffix_paths,
    )
    if len(_MODULE_INDEX_LOOKUP_CACHE) >= _MODULE_INDEX_LOOKUP_CACHE_LIMIT:
        _MODULE_INDEX_LOOKUP_CACHE.clear()
    _MODULE_INDEX_LOOKUP_CACHE[cache_key] = lookup
    return lookup
def _module_index_aliases_for_file(module_index: dict[str, str], file_path: str) -> set[str]:
    return {
        alias
        for alias, resolved_path in module_index.items()
        if resolved_path == file_path
    }
def _iter_root_scoped_module_aliases(
    *,
    root_path: Path,
    file_path: str,
    root_scoped_module_alias_builders: Sequence[Callable[..., Iterable[str]]],
) -> Iterator[str]:
    for builder in root_scoped_module_alias_builders:
        yield from builder(root_path=root_path, file_path=file_path)
def _resolve_suffix_match(*, module_index: dict[str, str], suffixes: Sequence[str]) -> str | None:
    normalized_suffixes = []
    for suffix in suffixes:
        normalized_suffix = _normalize_repository_relative_path(suffix)
        if normalized_suffix:
            normalized_suffixes.append(normalized_suffix)
    if not normalized_suffixes:
        return None
    lookup = _module_index_lookup(module_index)
    for suffix in normalized_suffixes:
        lowered_suffix = suffix.lower()
        direct_match = lookup.exact_paths.get(lowered_suffix)
        if direct_match is not None:
            return direct_match
        suffix_match = lookup.suffix_paths.get(lowered_suffix)
        if suffix_match is not None:
            return suffix_match
    return None
def _resolve_directory_prefix_match(
    *, module_index: dict[str, str], prefixes: Sequence[str]
) -> str | None:
    normalized_prefixes = []
    for prefix in prefixes:
        normalized_prefix = _normalize_repository_relative_path(prefix)
        if normalized_prefix:
            normalized_prefixes.append(normalized_prefix)
    if not normalized_prefixes:
        return None
    lookup = _module_index_lookup(module_index)
    for prefix in normalized_prefixes:
        prefix_match = lookup.directory_suffix_paths.get(prefix.lower())
        if prefix_match is not None:
            return prefix_match
    return None
def _build_module_index(
    file_paths: Sequence[str],
    *,
    root_path: Path | None = None,
    root_scoped_module_alias_builders: Sequence[Callable[..., Iterable[str]]] = (),
    module_index_extenders: Sequence[Callable[..., None]] = (),
) -> dict[str, str]:
    index: dict[str, str] = {}
    for file_path in file_paths:
        for alias in _module_aliases_for_path(file_path):
            index.setdefault(alias, file_path)
        if root_path is not None:
            for alias in _iter_root_scoped_module_aliases(root_path=root_path, file_path=file_path, root_scoped_module_alias_builders=root_scoped_module_alias_builders):
                index.setdefault(alias, file_path)
    if root_path is not None:
        for extender in module_index_extenders:
            extender(root_path=root_path, file_paths=file_paths, index=index)
    return index
