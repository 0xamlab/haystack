# ruff: noqa: I001
from __future__ import annotations
from pathlib import Path
from apps.api_server.services.repository_intelligence_indexing_repo_hints import (
    _ambiguous_c_header_repo_hint_language,
    _ambiguous_v_repo_hint_language,
    _has_classic_visual_basic_project_context,
    _has_fsharp_project_context,
    _ranked_adapter_language_for_path,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _AGDA_SUFFIXES,
    _CLARITY_MARKER_RE,
    _DIRECT_TEXT_SUFFIX_LANGUAGE_MAP,
    _FREEBASIC_MARKER_RE,
    _RAKU_SUFFIXES,
    _SHELL_FILE_BASENAMES,
    agda_adapter,
    al_adapter,
    ampl_adapter,
    antlr_adapter,
    apex_adapter,
    apl_adapter,
    as3_adapter,
    asciidoc_adapter,
    assembly_adapter,
    astro_adapter,
    autoit_adapter,
    awk_adapter,
    ballerina_adapter,
    bicep_adapter,
    bitbake_adapter,
    blade_adapter,
    bqn_adapter,
    cairo_adapter,
    cfml_adapter,
    circom_adapter,
    clojurescript_adapter,
    cmake_adapter,
    coffee_adapter,
    coq_adapter,
    cuda_adapter,
    cue_adapter,
    cvb,
    cython_adapter,
    dafny_adapter,
    delphi_adapter,
    dm_adapter,
    dockerfile_adapter,
    eiffel_adapter,
    ejs_adapter,
    emacslisp_adapter,
    erb_adapter,
    factor_adapter,
    fennel_adapter,
    fish_adapter,
    forth_adapter,
    four_d_adapter,
    foxpro_adapter,
    gams_adapter,
    gdscript_adapter,
    gherkin_adapter,
    gleam_adapter,
    gml_adapter,
    graphviz_adapter,
    groovy_adapter,
    hack_adapter,
    haml_adapter,
    handlebars_adapter,
    haxe_adapter,
    hlsl_adapter,
    hoon_adapter,
    hy_adapter,
    idris_adapter,
    isabelle_adapter,
    j_adapter,
    jinja_adapter,
    jsonnet_adapter,
    just_adapter,
    labview_adapter,
    ladder_adapter,
    lean_adapter,
    less_adapter,
    lex_adapter,
    liquid_adapter,
    luau_adapter,
    m4_adapter,
    makefile_adapter,
    matlab_adapter,
    maven_adapter,
    mercury_adapter,
    mermaid_adapter,
    meson_adapter,
    metal_adapter,
    modelica_adapter,
    moonbit_adapter,
    moonscript_adapter,
    motoko_adapter,
    move_adapter,
    mustache_adapter,
    nextflow_adapter,
    nix_adapter,
    nsis_adapter,
    nunjucks_adapter,
    nushell_adapter,
    objc_adapter,
    ocamllex_adapter,
    ocamlyacc_adapter,
    opencl_adapter,
    openedge_adapter,
    openqasm_adapter,
    openscad_adapter,
    org_adapter,
    osa_adapter,
    pawn_adapter,
    plantuml_adapter,
    plpgsql_adapter,
    pony_adapter,
    postscript_adapter,
    prolog_adapter,
    protobuf_adapter,
    pug_adapter,
    puppet_adapter,
    purebasic_adapter,
    purs_adapter,
    q_adapter,
    qmake_adapter,
    qml_adapter,
    qsharp_adapter,
    racket_adapter,
    raku_adapter,
    reasonml_adapter,
    rebol_adapter,
    red_adapter,
    rescript_adapter,
    robotframework_adapter,
    roc_adapter,
    rst_adapter,
    sass_adapter,
    scheme_adapter,
    scratch_adapter,
    scss_adapter,
    sed_adapter,
    shaderlab_adapter,
    shell_adapter,
    slim_adapter,
    smali_adapter,
    smalltalk_adapter,
    smarty_adapter,
    squirrel_adapter,
    stan_adapter,
    starlark_adapter,
    stylus_adapter,
    sv_adapter,
    svelte_adapter,
    sway_adapter,
    tcl_adapter,
    templ_adapter,
    tex_adapter,
    thrift_adapter,
    tlaplus_adapter,
    tsql_adapter,
    twig_adapter,
    typst_adapter,
    v_adapter,
    vala_adapter,
    vba_adapter,
    vbscript_adapter,
    vcl_adapter,
    verilog_adapter,
    vhdl_adapter,
    vimscript_adapter,
    vue_adapter,
    vyper_adapter,
    wgsl_adapter,
    wolfram_adapter,
    wren_adapter,
    xpp_adapter,
    xquery_adapter,
    xslt_adapter,
    yacc_adapter,
)
def _language_for_path(path: Path, *, text: str | None = None, repo_root: Path | None = None) -> str:
    basename = path.name.lower()
    if basename in _SHELL_FILE_BASENAMES:
        return "shell"
    suffix = path.suffix.lower()
    ranked_adapter_language = _ranked_adapter_language_for_path(path, text=text)
    if ranked_adapter_language is not None:
        return ranked_adapter_language
    if path.name.lower() in makefile_adapter.MAKEFILE_BASENAMES:
        return "makefile" if text is None or makefile_adapter.is_probable_makefile_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and (path.name.lower() in just_adapter.JUSTFILE_BASENAMES or path.suffix.lower() == ".just"):
        return "just" if just_adapter.is_probable_just_source(path=path, text=text) else "unknown"
    if path.name.lower() in dockerfile_adapter.DOCKERFILE_BASENAMES:
        return "dockerfile" if text is None or dockerfile_adapter.is_probable_dockerfile_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and path.suffix.lower() in antlr_adapter.ANTLR_SUFFIXES:
        return "antlr" if antlr_adapter.is_probable_antlr_source(path=path, text=text) else "unknown"
    if (
        text is not None
        and path.suffix.lower() in ampl_adapter.AMPL_SUFFIXES
        # ``v.mod`` (V) and ``moon.mod`` (MoonBit) are canonical module manifests that share
        # the ``.mod`` suffix with AMPL; the generic AMPL branch must not swallow them before
        # their dedicated branches below classify them.
        and path.name.lower() != "v.mod"
        and path.name.lower() not in moonbit_adapter.MOONBIT_CONFIG_BASENAMES
    ):
        return "ampl" if ampl_adapter.is_probable_ampl_source(path=path, text=text) else "unknown"
    if text is not None and openedge_adapter.has_openedge_path_hints(path) and suffix != ".cls":
        return "openedge" if openedge_adapter.is_probable_openedge_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in circom_adapter.CIRCOM_SUFFIXES:
        return "circom" if circom_adapter.is_probable_circom_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in dafny_adapter.DAFNY_SUFFIXES:
        return "dafny" if dafny_adapter.is_probable_dafny_source(path=path, text=text) else "unknown"
    if text is not None and (path.suffix.lower() in graphviz_adapter.GRAPHVIZ_SUFFIXES or path.suffix.lower() in mermaid_adapter.MERMAID_SUFFIXES or path.suffix.lower() in plantuml_adapter.PLANTUML_SUFFIXES or path.suffix.lower() in openqasm_adapter.OPENQASM_SUFFIXES):
        return "graphviz" if path.suffix.lower() in graphviz_adapter.GRAPHVIZ_SUFFIXES and graphviz_adapter.is_probable_graphviz_source(path=path, text=text) else ("mermaid" if path.suffix.lower() in mermaid_adapter.MERMAID_SUFFIXES and mermaid_adapter.is_probable_mermaid_source(path=path, text=text) else ("plantuml" if path.suffix.lower() in plantuml_adapter.PLANTUML_SUFFIXES and plantuml_adapter.is_probable_plantuml_source(path=path, text=text) else ("openqasm" if path.suffix.lower() in openqasm_adapter.OPENQASM_SUFFIXES and openqasm_adapter.is_probable_openqasm_source(path=path, text=text) else "unknown")))  # noqa: E501
    if text is not None and path.suffix.lower() in motoko_adapter.MOTOKO_SUFFIXES:
        if motoko_adapter.is_probable_motoko_source(path=path, text=text):
            return "motoko"
        return "modelica" if modelica_adapter.is_probable_modelica_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and (path.suffix.lower() in (move_adapter.MOVE_SUFFIXES | modelica_adapter.MODELICA_SUFFIXES | moonbit_adapter.MOONBIT_SOURCE_SUFFIXES | roc_adapter.ROC_SUFFIXES | rescript_adapter.RESCRIPT_SUFFIXES | hy_adapter.HY_SUFFIXES | wren_adapter.WREN_SUFFIXES | fennel_adapter.FENNEL_SUFFIXES | vyper_adapter.VYPER_SUFFIXES | dm_adapter.DM_SUFFIXES) or path.name.lower() in move_adapter.MOVE_CONFIG_BASENAMES or path.name.lower() in moonbit_adapter.MOONBIT_CONFIG_BASENAMES or path.name.lower() in rescript_adapter.RESCRIPT_CONFIG_BASENAMES):
        return "move" if ((path.suffix.lower() in move_adapter.MOVE_SUFFIXES and move_adapter.is_probable_move_source(path=path, text=text)) or (path.name.lower() in move_adapter.MOVE_CONFIG_BASENAMES and move_adapter.is_probable_move_config(path=path, text=text))) else ("modelica" if path.suffix.lower() in modelica_adapter.MODELICA_SUFFIXES and modelica_adapter.is_probable_modelica_source(path=path, text=text) else ("moonbit" if ((path.suffix.lower() in moonbit_adapter.MOONBIT_SOURCE_SUFFIXES and moonbit_adapter.is_probable_moonbit_source(path=path, text=text)) or (path.name.lower() in moonbit_adapter.MOONBIT_CONFIG_BASENAMES and moonbit_adapter.is_probable_moonbit_config(path=path, text=text))) else ("roc" if path.suffix.lower() in roc_adapter.ROC_SUFFIXES and roc_adapter.is_probable_roc_source(path=path, text=text) else ("rescript" if ((path.suffix.lower() in rescript_adapter.RESCRIPT_SUFFIXES and rescript_adapter.is_probable_rescript_source(path=path, text=text)) or (path.name.lower() in rescript_adapter.RESCRIPT_CONFIG_BASENAMES and rescript_adapter.is_probable_rescript_config(path=path, text=text))) else ("hy" if path.suffix.lower() in hy_adapter.HY_SUFFIXES and hy_adapter.is_probable_hy_source(path=path, text=text) else ("wren" if path.suffix.lower() in wren_adapter.WREN_SUFFIXES and wren_adapter.is_probable_wren_source(path=path, text=text) else ("fennel" if path.suffix.lower() in fennel_adapter.FENNEL_SUFFIXES and fennel_adapter.is_probable_fennel_source(path=path, text=text) else ("vyper" if path.suffix.lower() in vyper_adapter.VYPER_SUFFIXES and vyper_adapter.is_probable_vyper_source(path=path, text=text) else ("dm" if path.suffix.lower() in dm_adapter.DM_SUFFIXES and dm_adapter.is_probable_dm_source(path=path, text=text) else "unknown")))))))))  # noqa: E501
    if text is not None and (
        path.suffix.lower() in cairo_adapter.CAIRO_SUFFIXES
        or path.name.lower() in cairo_adapter.CAIRO_CONFIG_BASENAMES
        or path.suffix.lower() in sway_adapter.SWAY_SUFFIXES
        or path.name.lower() in sway_adapter.SWAY_CONFIG_BASENAMES
    ):
        return "cairo" if ((path.suffix.lower() in cairo_adapter.CAIRO_SUFFIXES and cairo_adapter.is_probable_cairo_source(path=path, text=text)) or (path.name.lower() in cairo_adapter.CAIRO_CONFIG_BASENAMES and cairo_adapter.is_probable_cairo_config(path=path, text=text))) else ("sway" if ((path.suffix.lower() in sway_adapter.SWAY_SUFFIXES and sway_adapter.is_probable_sway_source(path=path, text=text)) or (path.name.lower() in sway_adapter.SWAY_CONFIG_BASENAMES and sway_adapter.is_probable_sway_config(path=path, text=text))) else "unknown")  # noqa: E501
    if path.name.lower() in cmake_adapter.CMAKE_CONFIG_BASENAMES:
        return "cmake" if text is None or cmake_adapter.is_probable_cmake_source(path=path, text=text) else "unknown"  # noqa: E501
    if path.name.lower() in meson_adapter.MESON_CONFIG_BASENAMES and text is not None:
        return "meson" if meson_adapter.is_probable_meson_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and (path.suffix.lower() in qmake_adapter.QMAKE_SUFFIXES or path.name.lower() in qmake_adapter.QMAKE_CONFIG_BASENAMES):
        return "qmake" if qmake_adapter.is_probable_qmake_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and ((path.suffix.lower() in qml_adapter.QML_SUFFIXES or path.name.lower() in qml_adapter.QML_CONFIG_BASENAMES) or path.suffix.lower() in vue_adapter.VUE_SUFFIXES or path.suffix.lower() in svelte_adapter.SVELTE_SUFFIXES or path.suffix.lower() in astro_adapter.ASTRO_SUFFIXES):
        return "qml" if (path.suffix.lower() in qml_adapter.QML_SUFFIXES or path.name.lower() in qml_adapter.QML_CONFIG_BASENAMES) and qml_adapter.is_probable_qml_source(path=path, text=text) else ("vue" if path.suffix.lower() in vue_adapter.VUE_SUFFIXES and vue_adapter.is_probable_vue_source(path=path, text=text) else ("svelte" if path.suffix.lower() in svelte_adapter.SVELTE_SUFFIXES and svelte_adapter.is_probable_svelte_source(path=path, text=text) else ("astro" if path.suffix.lower() in astro_adapter.ASTRO_SUFFIXES and astro_adapter.is_probable_astro_source(path=path, text=text) else "unknown")))  # noqa: E501
    if text is not None and path.suffix.lower() in gherkin_adapter.GHERKIN_SUFFIXES:
        return "gherkin" if gherkin_adapter.is_probable_gherkin_source(path=path, text=text) else "unknown"
    if suffix == ".clar" and text is not None:
        return "clarity" if _CLARITY_MARKER_RE.search(text) else "unknown"
    if text is not None and path.suffix.lower() in nextflow_adapter.NEXTFLOW_SOURCE_SUFFIXES:
        return "nextflow" if nextflow_adapter.is_probable_nextflow_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and four_d_adapter.has_4d_path_hints(path):
        return "4d" if four_d_adapter.is_probable_4d_source(path=path, text=text) else "unknown"
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
        path.suffix.lower() in ballerina_adapter.BALLERINA_SUFFIXES
        or path.name.lower() in ballerina_adapter.BALLERINA_CONFIG_BASENAMES
    ):
        return "ballerina" if (
            (
                path.suffix.lower() in ballerina_adapter.BALLERINA_SUFFIXES
                and ballerina_adapter.is_probable_ballerina_source(path=path, text=text)
            )
            or (
                path.name.lower() in ballerina_adapter.BALLERINA_CONFIG_BASENAMES
                and ballerina_adapter.is_probable_ballerina_config(path=path, text=text)
            )
        ) else "unknown"
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
    if text is not None and suffix == ".fs" and _has_fsharp_project_context(path=path, repo_root=repo_root):
        return "fsharp"
    if text is not None and forth_adapter.has_forth_path_hints(path):
        return "forth" if forth_adapter.is_probable_forth_source(path=path, text=text) else ("fsharp" if path.suffix.lower() == ".fs" else "unknown")
    if text is not None and groovy_adapter.has_groovy_path_hints(path=path):
        return "groovy" if groovy_adapter.is_probable_groovy_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in isabelle_adapter.ISABELLE_SUFFIXES:
        return "isabelle" if isabelle_adapter.is_probable_isabelle_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in jsonnet_adapter.JSONNET_SUFFIXES:
        return "jsonnet" if jsonnet_adapter.is_probable_jsonnet_source(path=path, text=text) else "unknown"
    if text is not None and lex_adapter.has_lex_path_hints(path):
        return "lex" if lex_adapter.is_probable_lex_source(path=path, text=text) else "unknown"
    if text is not None and moonscript_adapter.has_moonscript_path_hints(path):
        return "moonscript" if moonscript_adapter.is_probable_moonscript_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in m4_adapter.M4_SUFFIXES:
        return "m4" if m4_adapter.is_probable_m4_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in purebasic_adapter.PUREBASIC_SUFFIXES:
        return "purebasic" if purebasic_adapter.is_probable_purebasic_source(path=path, text=text) else "unknown"  # noqa: E501
    if text is not None and path.suffix.lower() in pawn_adapter.PAWN_SOURCE_SUFFIXES:
        return "pawn" if pawn_adapter.is_probable_pawn_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in pony_adapter.PONY_SUFFIXES:
        return "pony" if pony_adapter.is_probable_pony_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in postscript_adapter.POSTSCRIPT_SUFFIXES:
        return "postscript" if postscript_adapter.is_probable_postscript_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in q_adapter.Q_SUFFIXES:
        return "q" if q_adapter.is_probable_q_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in red_adapter.RED_SUFFIXES:
        return "red" if red_adapter.is_probable_red_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in rebol_adapter.REBOL_SUFFIXES:
        if rebol_adapter.is_probable_rebol_source(path=path, text=text):
            return "rebol"
        if path.suffix.lower() in rebol_adapter.UNAMBIGUOUS_REBOL_SUFFIXES:
            return "unknown"
    if text is not None and path.suffix.lower() in sed_adapter.SED_SUFFIXES:
        return "sed" if sed_adapter.is_probable_sed_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in nsis_adapter.NSIS_SUFFIXES:
        return "nsis" if nsis_adapter.is_probable_nsis_source(path=path, text=text) else "unknown"
    if text is not None and ocamllex_adapter.has_ocamllex_path_hints(path):
        return "ocamllex" if ocamllex_adapter.is_probable_ocamllex_source(path=path, text=text) else "unknown"
    if text is not None and ocamlyacc_adapter.has_ocamlyacc_path_hints(path):
        return "ocamlyacc" if ocamlyacc_adapter.is_probable_ocamlyacc_source(path=path, text=text) else "unknown"
    if text is not None and templ_adapter.has_templ_path_hints(path):
        return "templ" if templ_adapter.is_probable_templ_source(path=path, text=text) else "unknown"
    if text is not None and thrift_adapter.has_thrift_path_hints(path):
        return "thrift" if thrift_adapter.is_probable_thrift_source(path=path, text=text) else "unknown"
    if text is not None and vcl_adapter.has_vcl_path_hints(path):
        return "vcl" if vcl_adapter.is_probable_vcl_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in smali_adapter.SMALI_SUFFIXES:
        return "smali" if smali_adapter.is_probable_smali_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in xquery_adapter.XQUERY_SUFFIXES:
        return "xquery" if xquery_adapter.is_probable_xquery_source(path=path, text=text) else "unknown"
    if text is not None and path.suffix.lower() in xslt_adapter.XSLT_SUFFIXES:
        return "xslt" if xslt_adapter.is_probable_xslt_source(path=path, text=text) else "unknown"
    if text is not None and yacc_adapter.has_yacc_path_hints(path):
        return "yacc" if yacc_adapter.is_probable_yacc_source(path=path, text=text) else "unknown"
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
        if nushell_adapter.is_probable_nushell_source(path=path, text=text):
            return "nushell"
        if tcl_adapter.is_probable_tcl_source(path=path, text=text):
            return "tcl"
        if shell_adapter.is_probable_shell_source(path=path, text=text):
            return "shell"
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
        if _has_classic_visual_basic_project_context(path=path, repo_root=repo_root) and (
            cvb.is_probable_classic_visual_basic_source(
                path=path,
                text=text,
            )
        ):
            return "vb6"
        if openedge_adapter.is_probable_openedge_source(path=path, text=text):
            return "openedge"
        if vba_adapter.is_probable_vba_source(path=path, text=text):
            return "vba"
        if cvb.is_probable_classic_visual_basic_source(
            path=path,
            text=text,
        ):
            return "vb6"
        if apex_adapter.is_probable_apex_source(path=path, text=text):
            return "apex"
        if tex_adapter.is_probable_tex_source(path=path, text=text):
            return "tex"
        return "unknown"
    if suffix in {".bas", ".frm"} and text is not None:
        if suffix == ".bas" and _FREEBASIC_MARKER_RE.search(text):
            return "freebasic"
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
    if suffix == ".bi" and text is not None:
        return "freebasic" if _FREEBASIC_MARKER_RE.search(text) else "unknown"
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
        if basename in maven_adapter.MAVEN_PROJECT_BASENAMES:
            return "maven" if maven_adapter.is_probable_maven_source(path=path, text=text) else "unknown"
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
        if pawn_adapter.is_probable_pawn_source(path=path, text=text):
            return "pawn"
        return "bitbake" if bitbake_adapter.is_probable_bitbake_source(path=path, text=text) else "unknown"  # noqa: E501
    if suffix == ".pl" and text is not None:
        if prolog_adapter.is_probable_prolog_source(path=path, text=text):
            return "prolog"
    if suffix in {".rkt", ".rktl"} and text is not None:
        if racket_adapter.is_probable_racket_source(path=path, text=text):
            return "racket"
        return "unknown"
    if suffix in apl_adapter.APL_SUFFIXES and text is not None:
        if apl_adapter.is_probable_apl_source(path=path, text=text):
            return "apl"
        return "unknown"
    if suffix in {".scm", ".ss", ".sld", ".sps"} and text is not None:
        if scheme_adapter.is_probable_scheme_source(path=path, text=text):
            return "scheme"
        return "unknown"
    if suffix == ".scad" and text is not None:
        return "openscad" if openscad_adapter.is_probable_openscad_source(path=path, text=text) else "unknown"
    if suffix == ".purs" and text is not None:
        return "purescript" if purs_adapter.is_probable_purescript_source(path=path, text=text) else "unknown"
    if suffix == ".cairo" and text is not None:
        return "cairo" if cairo_adapter.is_probable_cairo_source(path=path, text=text) else "unknown"
    if suffix in {".re", ".rei"} and text is not None:
        return "reasonml" if reasonml_adapter.is_probable_reasonml_source(path=path, text=text) else "unknown"
    if suffix in {".mo", ".roc", ".res", ".resi", ".sw"} and text is not None:
        return "modelica" if suffix == ".mo" and modelica_adapter.is_probable_modelica_source(path=path, text=text) else ("roc" if suffix == ".roc" and roc_adapter.is_probable_roc_source(path=path, text=text) else ("rescript" if suffix in {".res", ".resi"} and rescript_adapter.is_probable_rescript_source(path=path, text=text) else ("sway" if suffix == ".sw" and sway_adapter.is_probable_sway_source(path=path, text=text) else "unknown")))
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
        if suffix == ".v":
            repo_hint_language = _ambiguous_v_repo_hint_language(repo_root)
            if repo_hint_language == "coq" and coq_adapter.is_probable_coq_source(path=path, text=text):
                return "coq"
            if repo_hint_language == "v" and v_adapter.is_probable_v_source(path=path, text=text):
                return "v"
            if repo_hint_language == "unknown":
                if coq_adapter.is_probable_coq_source(path=path, text=text):
                    return "coq"
                if v_adapter.is_probable_v_source(path=path, text=text):
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
    if suffix == ".pgsql" and text is not None:
        return "plpgsql" if plpgsql_adapter.is_probable_plpgsql_source(path=path, text=text) else "unknown"
    if suffix in {".sql", ".sqlproj", ".dbproj"} and text is not None:
        if tsql_adapter.is_probable_tsql_source(path=path, text=text):
            return "tsql"
        if suffix == ".sql" and plpgsql_adapter.is_probable_plpgsql_source(path=path, text=text):
            return "plpgsql"
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
    if suffix == ".bqn":
        if text is not None and not bqn_adapter.is_probable_bqn_source(path=path, text=text):
            return "unknown"
        return "bqn"
    if suffix in j_adapter.J_SUFFIXES:
        if text is not None and not j_adapter.is_probable_j_source(path=path, text=text):
            return "unknown"
        return "j"
    if suffix == ".hoon":
        if text is not None and not hoon_adapter.is_probable_hoon_source(path=path, text=text):
            return "unknown"
        return "hoon"
    if suffix in metal_adapter.METAL_SUFFIXES:
        if text is not None and not metal_adapter.is_probable_metal_source(path=path, text=text):
            return "unknown"
        return "metal"
    if suffix == ".m":
        if text is not None and mercury_adapter.is_probable_mercury_source(path=path, text=text):
            return "mercury"
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
        ".ahk", ".agda", ".agda-lib", ".au3", ".bicep", ".brs", ".cairo", ".chpl", ".compute", ".cwl", ".dem", ".dockerfile", ".dot", ".dwl", ".factor", ".feature", ".g4", ".gp", ".gnuplot", ".gv", ".mako", ".metal", ".metalh", ".mmd", ".mermaid", ".plt", ".puml", ".plantuml", ".iuml", ".qasm", ".ql", ".qll", ".fx", ".fxh", ".cginc", ".hack", ".hhi", ".hlsl", ".hlsli", ".wgsl", ".j2", ".jinja", ".jinja2", ".liquid", ".hbs", ".handlebars", ".mustache", ".njk", ".nunj", ".nunjucks", ".twig", ".haml", ".slim", ".erb", ".rhtml", ".pug", ".jade", ".ejs", ".proto", ".move", ".roc", ".re", ".rei", ".res", ".resi", ".scss", ".less", ".styl", ".svelte", ".astro", ".shader", ".hx", ".sw", ".typ", ".tex", ".sty", ".ltx", ".dtx", ".rst", ".rest", ".adoc", ".asciidoc", ".asc", ".org",
        ".hxml", ".odin", ".pde", ".reb", ".rebol", ".r3",
        ".idr", ".ipkg", ".nut", ".tla", ".lgt", ".logtalk", ".lagda", ".lidr", ".xpp", ".xpo", ".sb3",
    }:
        return {
            ".ahk": "autohotkey", ".au3": "autoit",
            ".agda": "agda", ".agda-lib": "agda", ".brs": "brightscript", ".cairo": "cairo", ".cwl": "common workflow language", ".dem": "gnuplot", ".dwl": "dataweave", ".gp": "gnuplot", ".gnuplot": "gnuplot", ".plt": "gnuplot",
            ".mako": "mako",
            ".ql": "codeql", ".qll": "codeql",
            ".metal": "metal", ".metalh": "metal",
            ".reb": "rebol", ".rebol": "rebol", ".r3": "rebol",
            ".bicep": "bicep", ".chpl": "chapel", ".compute": "hlsl", ".dockerfile": "dockerfile", ".factor": "factor", ".fx": "hlsl", ".fxh": "hlsl", ".cginc": "hlsl",
            ".hack": "hack", ".hhi": "hack", ".nsi": "nsis", ".nsh": "nsis",
            ".hlsl": "hlsl", ".hlsli": "hlsl", ".wgsl": "wgsl", ".j2": "jinja", ".jinja": "jinja", ".jinja2": "jinja", ".liquid": "liquid", ".hbs": "handlebars", ".handlebars": "handlebars", ".mustache": "mustache", ".njk": "nunjucks", ".nunj": "nunjucks", ".nunjucks": "nunjucks", ".twig": "twig", ".haml": "haml", ".slim": "slim", ".erb": "erb", ".rhtml": "erb", ".pug": "pug", ".jade": "pug", ".ejs": "ejs", ".feature": "gherkin", ".g4": "antlr", ".dot": "graphviz", ".gv": "graphviz", ".mmd": "mermaid", ".mermaid": "mermaid", ".puml": "plantuml", ".plantuml": "plantuml", ".iuml": "plantuml", ".qasm": "openqasm", ".proto": "protobuf", ".move": "move", ".roc": "roc", ".re": "reasonml", ".rei": "reasonml", ".res": "rescript", ".resi": "rescript", ".scss": "scss", ".less": "less", ".styl": "stylus", ".svelte": "svelte", ".astro": "astro", ".shader": "shaderlab", ".hx": "haxe", ".hxml": "haxe", ".idr": "idris", ".ipkg": "idris", ".odin": "odin", ".pde": "processing", ".typ": "typst", ".tex": "tex", ".sty": "tex", ".ltx": "tex", ".dtx": "tex", ".rst": "rst", ".rest": "rst", ".adoc": "asciidoc", ".asciidoc": "asciidoc", ".asc": "asciidoc", ".org": "org",
            ".lagda": "agda", ".lidr": "idris", ".nut": "squirrel", ".sw": "sway", ".tla": "tlaplus", ".lgt": "logtalk",
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
        repo_hint_language = _ambiguous_c_header_repo_hint_language(repo_root)
        if repo_hint_language == "cpp":
            return "cpp"
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
        ".ampl": "ampl",
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
        ".kt": "kotlin", ".kts": "kotlin", ".pde": "processing",
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
        ".mqproj": "mql5", ".gms": "gams", ".hy": "hy", ".wren": "wren", ".janet": "janet", ".fnl": "fennel", ".fnlm": "fennel", ".vy": "vyper", ".vyi": "vyper", ".bal": "ballerina", ".ipkg": "idris",
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
        ".purs": "purescript", ".re": "reasonml", ".rei": "reasonml", ".res": "rescript", ".resi": "rescript", ".roc": "roc", ".cairo": "cairo", ".sw": "sway",
        **dict.fromkeys(sorted(_RAKU_SUFFIXES), "raku"),
        ".ps1": "powershell",
        ".psgi": "perl",
        ".psm1": "powershell",
        ".stan": "stan", ".cu": "cuda", ".cuh": "cuda", ".dockerfile": "dockerfile", ".metal": "metal", ".metalh": "metal", ".proto": "protobuf", ".move": "move", ".shader": "shaderlab", ".wgsl": "wgsl", ".j2": "jinja", ".jinja": "jinja", ".jinja2": "jinja", ".liquid": "liquid", ".hbs": "handlebars", ".handlebars": "handlebars", ".mustache": "mustache", ".njk": "nunjucks", ".nunj": "nunjucks", ".nunjucks": "nunjucks", ".twig": "twig", ".haml": "haml", ".slim": "slim", ".erb": "erb", ".rhtml": "erb", ".pug": "pug", ".jade": "pug", ".ejs": "ejs", ".robot": "robotframework", ".resource": "robotframework", ".feature": "gherkin", ".g4": "antlr", ".dot": "graphviz", ".gv": "graphviz", ".mmd": "mermaid", ".mermaid": "mermaid", ".puml": "plantuml", ".plantuml": "plantuml", ".iuml": "plantuml", ".qasm": "openqasm", ".re": "reasonml", ".rei": "reasonml", ".scss": "scss", ".less": "less", ".styl": "stylus", ".svelte": "svelte", ".astro": "astro", ".cairo": "cairo", ".sw": "sway", ".typ": "typst", ".tex": "tex", ".sty": "tex", ".ltx": "tex", ".dtx": "tex", ".rst": "rst", ".rest": "rst", ".adoc": "asciidoc", ".asciidoc": "asciidoc", ".asc": "asciidoc", ".org": "org", ".4dm": "4d",
        ".hlsl": "hlsl", ".hlsli": "hlsl", ".fx": "hlsl",
        ".fxh": "hlsl", ".cginc": "hlsl", ".compute": "hlsl",
        **dict.fromkeys((".pro", ".pri", ".prf"), "qmake"), ".qml": "qml",
        ".py": "python",
        ".r": "r",
        ".r3": "rebol",
        ".rb": "ruby",
        ".reb": "rebol",
        ".rebol": "rebol",
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
        ".bal": "ballerina",
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
        ".fish": "fish", ".groovy": "groovy", ".nf": "nextflow", ".nsi": "nsis", ".nsh": "nsis", ".pde": "processing", ".glsl": "glsl", ".vert": "glsl", ".frag": "glsl", ".geom": "glsl", ".tesc": "glsl", ".tese": "glsl", ".comp": "glsl", ".cwl": "common workflow language", ".dem": "gnuplot", ".dwl": "dataweave", ".gnuplot": "gnuplot", ".gp": "gnuplot", ".plt": "gnuplot", ".gpr": "txt",  # noqa: E501
    }.get(suffix, "unknown")
