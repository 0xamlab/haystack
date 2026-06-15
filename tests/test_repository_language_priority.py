from __future__ import annotations

import pytest

from apps.api_server.services.repository_language_priority import (
    DEFAULT_REAL_LANGUAGE_RANK_TARGET,
    canonical_repository_language,
    ranked_real_repository_languages,
    repository_language_support_progress,
    sort_repository_languages,
    sort_repository_languages_by_score,
    supported_repository_languages,
)


def test_sort_repository_languages_normalizes_aliases_to_canonical_names() -> None:
    assert sort_repository_languages({"JS", "TypeScript", "rb", "csharp"}) == [
        "typescript",
        "javascript",
        "cs",
        "ruby",
    ]


def test_sort_repository_languages_by_score_prefers_repo_signal_before_global_rank() -> None:
    assert sort_repository_languages_by_score(
        {"java", "cpp", "dart", "groovy"},
        scores={
            "dart": 160,
            "java": 60,
            "cpp": 40,
            "groovy": 20,
        },
    ) == [
        "dart",
        "java",
        "cpp",
        "groovy",
    ]


def test_canonical_repository_language_maps_known_aliases() -> None:
    assert canonical_repository_language("c++") == "cpp"
    assert canonical_repository_language("asm") == "assembly"
    assert canonical_repository_language("coldfusion") == "cfml"
    assert canonical_repository_language("object pascal") == "delphi"
    assert canonical_repository_language("kt") == "kotlin"
    assert canonical_repository_language("nimscript") == "nim"
    assert canonical_repository_language("objective-c") == "objectivec"
    assert canonical_repository_language("rockspec") == "lua"
    assert canonical_repository_language("roblox") == "luau"
    assert canonical_repository_language("roblox lua") == "luau"
    assert canonical_repository_language("roblox luau") == "luau"
    assert canonical_repository_language("rbxlua") == "luau"
    assert canonical_repository_language("sml") == "sml"
    assert canonical_repository_language("graphql") == "graphql"
    assert canonical_repository_language(".graphql") == "graphql"
    assert canonical_repository_language("pkl") == "pkl"
    assert canonical_repository_language("PklProject") == "pkl"
    assert canonical_repository_language("plpgsql") == "plpgsql"
    assert canonical_repository_language("PL/pgSQL") == "plpgsql"
    assert canonical_repository_language(".pgsql") == "plpgsql"
    assert canonical_repository_language("wasm") == "webassembly"
    assert canonical_repository_language(".wat") == "webassembly"
    assert canonical_repository_language("ballerina") == "ballerina"
    assert canonical_repository_language(".bal") == "ballerina"
    assert canonical_repository_language("Ballerina.toml") == "ballerina"
    assert canonical_repository_language("gnuplot") == "gnuplot"
    assert canonical_repository_language(".dem") == "gnuplot"
    assert canonical_repository_language("dataweave") == "dataweave"
    assert canonical_repository_language(".dwl") == "dataweave"
    assert canonical_repository_language("cwl") == "common workflow language"
    assert canonical_repository_language(".cwl") == "common workflow language"
    assert canonical_repository_language("common-workflow-language") == "common workflow language"
    assert canonical_repository_language("earthly") == "earthly"
    assert canonical_repository_language("Earthfile") == "earthly"
    assert canonical_repository_language("bqn") == "bqn"
    assert canonical_repository_language(".bqn") == "bqn"
    assert canonical_repository_language("rebol") == "rebol"
    assert canonical_repository_language("rebol 3") == "rebol"
    assert canonical_repository_language(".reb") == "rebol"
    assert canonical_repository_language(".r3") == "rebol"
    assert canonical_repository_language(".rebol") == "rebol"
    assert canonical_repository_language("classic visual basic") == "vb6"
    assert canonical_repository_language("visual basic for applications") == "vba"
    assert canonical_repository_language("vbs") == "vbscript"
    assert canonical_repository_language("common lisp") == "lisp"
    assert canonical_repository_language("hy") == "hy"
    assert canonical_repository_language("hylang") == "hy"
    assert canonical_repository_language(".hy") == "hy"
    assert canonical_repository_language("scm") == "scheme"
    assert canonical_repository_language("rkt") == "racket"
    assert canonical_repository_language("godot script") == "gdscript"
    assert canonical_repository_language("xbase") == "foxpro"
    assert canonical_repository_language("sol") == "solidity"
    assert canonical_repository_language("fragment shader") == "glsl"
    assert canonical_repository_language("vertex shader") == "glsl"
    assert canonical_repository_language("hlsl") == "hlsl"
    assert canonical_repository_language("directx shader") == "hlsl"
    assert canonical_repository_language(".hlsl") == "hlsl"
    assert canonical_repository_language(".hlsli") == "hlsl"
    assert canonical_repository_language(".fx") == "hlsl"
    assert canonical_repository_language(".fxh") == "hlsl"
    assert canonical_repository_language(".cginc") == "hlsl"
    assert canonical_repository_language(".compute") == "hlsl"
    assert canonical_repository_language("wgsl") == "wgsl"
    assert canonical_repository_language("webgpu shader") == "wgsl"
    assert canonical_repository_language("webgpu shading language") == "wgsl"
    assert canonical_repository_language(".wgsl") == "wgsl"
    assert canonical_repository_language("shaderlab") == "shaderlab"
    assert canonical_repository_language("shader lab") == "shaderlab"
    assert canonical_repository_language(".shader") == "shaderlab"
    assert canonical_repository_language("metal") == "metal"
    assert canonical_repository_language("metal shading language") == "metal"
    assert canonical_repository_language("msl") == "metal"
    assert canonical_repository_language(".metal") == "metal"
    assert canonical_repository_language("robotframework") == "robotframework"
    assert canonical_repository_language("antlr4") == "antlr"
    assert canonical_repository_language(".g4") == "antlr"
    assert canonical_repository_language("robot framework") == "robotframework"
    assert canonical_repository_language(".robot") == "robotframework"
    assert canonical_repository_language(".resource") == "robotframework"
    assert canonical_repository_language("dockerfile") == "dockerfile"
    assert canonical_repository_language("docker file") == "dockerfile"
    assert canonical_repository_language(".dockerfile") == "dockerfile"
    assert canonical_repository_language("containerfile") == "dockerfile"
    assert canonical_repository_language("scss") == "scss"
    assert canonical_repository_language(".scss") == "scss"
    assert canonical_repository_language("less") == "less"
    assert canonical_repository_language(".less") == "less"
    assert canonical_repository_language("stylus") == "stylus"
    assert canonical_repository_language(".styl") == "stylus"
    assert canonical_repository_language("vue") == "vue"
    assert canonical_repository_language("vuejs") == "vue"
    assert canonical_repository_language(".vue") == "vue"
    assert canonical_repository_language("svelte") == "svelte"
    assert canonical_repository_language("sveltekit") == "svelte"
    assert canonical_repository_language(".svelte") == "svelte"
    assert canonical_repository_language("astro") == "astro"
    assert canonical_repository_language(".astro") == "astro"
    assert canonical_repository_language("jinja") == "jinja"
    assert canonical_repository_language("jinja2") == "jinja"
    assert canonical_repository_language("jinja template") == "jinja"
    assert canonical_repository_language(".j2") == "jinja"
    assert canonical_repository_language(".jinja") == "jinja"
    assert canonical_repository_language(".jinja2") == "jinja"
    assert canonical_repository_language("liquid") == "liquid"
    assert canonical_repository_language(".liquid") == "liquid"
    assert canonical_repository_language("handlebars") == "handlebars"
    assert canonical_repository_language(".hbs") == "handlebars"
    assert canonical_repository_language(".handlebars") == "handlebars"
    assert canonical_repository_language("pug") == "pug"
    assert canonical_repository_language("jade") == "pug"
    assert canonical_repository_language(".pug") == "pug"
    assert canonical_repository_language(".jade") == "pug"
    assert canonical_repository_language("ejs") == "ejs"
    assert canonical_repository_language(".ejs") == "ejs"
    assert canonical_repository_language("blade") == "blade"
    assert canonical_repository_language("laravel blade") == "blade"
    assert canonical_repository_language(".blade.php") == "blade"
    assert canonical_repository_language("erb") == "erb"
    assert canonical_repository_language(".erb") == "erb"
    assert canonical_repository_language(".rhtml") == "erb"
    assert canonical_repository_language("mustache") == "mustache"
    assert canonical_repository_language(".mustache") == "mustache"
    assert canonical_repository_language("nunjucks") == "nunjucks"
    assert canonical_repository_language(".njk") == "nunjucks"
    assert canonical_repository_language(".nunjucks") == "nunjucks"
    assert canonical_repository_language("twig") == "twig"
    assert canonical_repository_language(".twig") == "twig"
    assert canonical_repository_language("slim") == "slim"
    assert canonical_repository_language(".slim") == "slim"
    assert canonical_repository_language("tex") == "tex"
    assert canonical_repository_language("latex") == "tex"
    assert canonical_repository_language(".tex") == "tex"
    assert canonical_repository_language(".sty") == "tex"
    assert canonical_repository_language(".cls") == "tex"
    assert canonical_repository_language(".ltx") == "tex"
    assert canonical_repository_language(".dtx") == "tex"
    assert canonical_repository_language("latexmkrc") == "tex"
    assert canonical_repository_language(".latexmkrc") == "tex"
    assert canonical_repository_language("rst") == "rst"
    assert canonical_repository_language("restructuredtext") == "rst"
    assert canonical_repository_language(".rst") == "rst"
    assert canonical_repository_language(".rest") == "rst"
    assert canonical_repository_language("asciidoc") == "asciidoc"
    assert canonical_repository_language(".adoc") == "asciidoc"
    assert canonical_repository_language(".asciidoc") == "asciidoc"
    assert canonical_repository_language(".asc") == "asciidoc"
    assert canonical_repository_language("org") == "org"
    assert canonical_repository_language("org-mode") == "org"
    assert canonical_repository_language(".org") == "org"
    assert canonical_repository_language("protobuf") == "protobuf"
    assert canonical_repository_language("protocol buffer") == "protobuf"
    assert canonical_repository_language("protocol buffers") == "protobuf"
    assert canonical_repository_language(".proto") == "protobuf"
    assert canonical_repository_language("buf.yaml") == "protobuf"
    assert canonical_repository_language("typst") == "typst"
    assert canonical_repository_language(".typ") == "typst"
    assert canonical_repository_language("typst.toml") == "typst"
    assert canonical_repository_language("jsonnet") == "jsonnet"
    assert canonical_repository_language(".libsonnet") == "jsonnet"
    assert canonical_repository_language("autoconf") == "m4"
    assert canonical_repository_language(".m4") == "m4"
    assert canonical_repository_language("forth") == "forth"
    assert canonical_repository_language(".fth") == "forth"
    assert canonical_repository_language(".4th") == "forth"
    assert canonical_repository_language("isabelle") == "isabelle"
    assert canonical_repository_language(".thy") == "isabelle"
    assert canonical_repository_language("gnu sed") == "sed"
    assert canonical_repository_language(".sed") == "sed"
    assert canonical_repository_language("nsis") == "nsis"
    assert canonical_repository_language("nullsoft scriptable install system") == "nsis"
    assert canonical_repository_language(".nsi") == "nsis"
    assert canonical_repository_language(".nsh") == "nsis"
    assert canonical_repository_language("makensis") == "nsis"
    assert canonical_repository_language("xslt") == "xslt"
    assert canonical_repository_language(".xsl") == "xslt"
    assert canonical_repository_language(".xslt") == "xslt"
    assert canonical_repository_language("yacc") == "yacc"
    assert canonical_repository_language(".y") == "yacc"
    assert canonical_repository_language(".yacc") == "yacc"
    assert canonical_repository_language("byacc") == "yacc"
    assert canonical_repository_language("lex") == "lex"
    assert canonical_repository_language(".l") == "lex"
    assert canonical_repository_language(".lex") == "lex"
    assert canonical_repository_language("flex") == "lex"
    assert canonical_repository_language("moonscript") == "moonscript"
    assert canonical_repository_language(".moon") == "moonscript"
    assert canonical_repository_language("ocamllex") == "ocamllex"
    assert canonical_repository_language(".mll") == "ocamllex"
    assert canonical_repository_language("ocamlyacc") == "ocamlyacc"
    assert canonical_repository_language(".mly") == "ocamlyacc"
    assert canonical_repository_language("xquery") == "xquery"
    assert canonical_repository_language("xq") == "xquery"
    assert canonical_repository_language(".xq") == "xquery"
    assert canonical_repository_language(".xquery") == "xquery"
    assert canonical_repository_language(".xqy") == "xquery"
    assert canonical_repository_language(".xql") == "xquery"
    assert canonical_repository_language(".xqm") == "xquery"
    assert canonical_repository_language("q") == "q"
    assert canonical_repository_language(".q") == "q"
    assert canonical_repository_language("kdb+") == "q"
    assert canonical_repository_language("j") == "j"
    assert canonical_repository_language(".ijs") == "j"
    assert canonical_repository_language(".ijt") == "j"
    assert canonical_repository_language("jsoftware") == "j"
    assert canonical_repository_language("motoko") == "motoko"
    assert canonical_repository_language("internet computer") == "motoko"
    assert canonical_repository_language("verilog") == "verilog"
    assert canonical_repository_language("system verilog") == "systemverilog"
    assert canonical_repository_language("vhd") == "vhdl"
    assert canonical_repository_language("salesforce apex") == "apex"
    assert canonical_repository_language("mathematica") == "wolfram"
    assert canonical_repository_language("ladder logic") == "ladder"
    assert canonical_repository_language("rpgle") == "rpg"
    assert canonical_repository_language("as3") == "actionscript"
    assert canonical_repository_language("apple script") == "applescript"
    assert canonical_repository_language("ahk") == "autohotkey"
    assert canonical_repository_language("au3") == "autoit"
    assert canonical_repository_language(".au3") == "autoit"
    assert canonical_repository_language("autoit") == "autoit"
    assert canonical_repository_language("autoit3") == "autoit"
    assert canonical_repository_language("cython") == "cython"
    assert canonical_repository_language(".pyx") == "cython"
    assert canonical_repository_language(".pxd") == "cython"
    assert canonical_repository_language(".pxi") == "cython"
    assert canonical_repository_language("pyrex") == "cython"
    assert canonical_repository_language("cuda") == "cuda"
    assert canonical_repository_language("nvcc") == "cuda"
    assert canonical_repository_language(".cu") == "cuda"
    assert canonical_repository_language(".cuh") == "cuda"
    assert canonical_repository_language("stan") == "stan"
    assert canonical_repository_language(".stan") == "stan"
    assert canonical_repository_language("cmdstan") == "stan"
    assert canonical_repository_language("squirrel") == "squirrel"
    assert canonical_repository_language(".nut") == "squirrel"
    assert canonical_repository_language("nut") == "squirrel"
    assert canonical_repository_language("gawk") == "awk"
    assert canonical_repository_language("coffee-script") == "coffeescript"
    assert canonical_repository_language("agda") == "agda"
    assert canonical_repository_language("rocq") == "coq"
    assert canonical_repository_language("lean4") == "lean"
    assert canonical_repository_language("make") == "makefile"
    assert canonical_repository_language("gnu make") == "makefile"
    assert canonical_repository_language("batch") == "batchfile"
    assert canonical_repository_language("hx") == "haxe"
    assert canonical_repository_language("nix") == "nix"
    assert canonical_repository_language("xtend") == "xtend"
    assert canonical_repository_language(".xtend") == "xtend"
    assert canonical_repository_language("vlang") == "v"
    assert canonical_repository_language("elm-lang") == "elm"
    assert canonical_repository_language("elisp") == "emacslisp"
    assert canonical_repository_language("fish shell") == "fish"
    assert canonical_repository_language("4D") == "4d"
    assert canonical_repository_language("4th dimension") == "4d"
    assert canonical_repository_language(".4dm") == "4d"
    assert canonical_repository_language("viml") == "vimscript"
    assert canonical_repository_language("x++") == "xpp"
    assert canonical_repository_language("genie") == "vala"
    assert canonical_repository_language("pharo") == "smalltalk"
    assert canonical_repository_language("mq5") == "mql5"
    assert canonical_repository_language("scad") == "openscad"
    assert canonical_repository_language("open scad") == "openscad"
    assert canonical_repository_language("factor") == "factor"
    assert canonical_repository_language("factorcode") == "factor"
    assert canonical_repository_language("scratch3") == "scratch"
    assert canonical_repository_language("lab view") == "labview"
    assert canonical_repository_language("tcl/tk") == "tcl"
    assert canonical_repository_language("pawn") == "pawn"
    assert canonical_repository_language(".pwn") == "pawn"
    assert canonical_repository_language("postscript") == "postscript"
    assert canonical_repository_language(".eps") == "postscript"
    assert canonical_repository_language("ponylang") == "pony"
    assert canonical_repository_language(".pony") == "pony"
    assert canonical_repository_language("smali") == "smali"
    assert canonical_repository_language(".smali") == "smali"
    assert canonical_repository_language("game maker language") == "gml"
    assert canonical_repository_language("gamemaker") == "gml"
    assert canonical_repository_language("transact-sql") == "tsql"
    assert canonical_repository_language("t-sql") == "tsql"
    assert canonical_repository_language("pure basic") == "purebasic"
    assert canonical_repository_language(".pb") == "purebasic"
    assert canonical_repository_language("purs") == "purescript"
    assert canonical_repository_language("pure script") == "purescript"
    assert canonical_repository_language("perl6") == "raku"
    assert canonical_repository_language("pm6") == "raku"
    assert canonical_repository_language("gleam-lang") == "gleam"
    assert canonical_repository_language("janet-lang") == "janet"
    assert canonical_repository_language("idris2") == "idris"
    assert canonical_repository_language("ipkg") == "idris"
    assert canonical_repository_language("nu") == "nushell"
    assert canonical_repository_language("skylark") == "starlark"
    assert canonical_repository_language("bzl") == "starlark"
    assert canonical_repository_language("rego") == "rego"
    assert canonical_repository_language("opa") == "rego"
    assert canonical_repository_language("terraform") == "hcl"
    assert canonical_repository_language("bicep") == "bicep"
    assert canonical_repository_language("bicepparam") == "bicep"
    assert canonical_repository_language("cue") == "cue"
    assert canonical_repository_language("cuelang") == "cue"
    assert canonical_repository_language("cmake") == "cmake"
    assert canonical_repository_language("cmakelists.txt") == "cmake"
    assert canonical_repository_language("meson") == "meson"
    assert canonical_repository_language("meson.build") == "meson"
    assert canonical_repository_language("qmake") == "qmake"
    assert canonical_repository_language(".pro") == "qmake"
    assert canonical_repository_language(".pri") == "qmake"
    assert canonical_repository_language(".prf") == "qmake"
    assert canonical_repository_language("qml") == "qml"
    assert canonical_repository_language(".qml") == "qml"
    assert canonical_repository_language("qmldir") == "qml"
    assert canonical_repository_language("just") == "just"
    assert canonical_repository_language("justfile") == "just"
    assert canonical_repository_language(".just") == "just"
    assert canonical_repository_language("puppet") == "puppet"
    assert canonical_repository_language("bitbake") == "bitbake"
    assert canonical_repository_language("yocto") == "bitbake"
    assert canonical_repository_language(".bb") == "bitbake"
    assert canonical_repository_language("hacklang") == "hack"
    assert canonical_repository_language("dhall") == "dhall"
    assert canonical_repository_language("dhall-lang") == "dhall"
    assert canonical_repository_language("move") == "move"
    assert canonical_repository_language(".move") == "move"
    assert canonical_repository_language("move.toml") == "move"
    assert canonical_repository_language("move-lang") == "move"
    assert canonical_repository_language("sway") == "sway"
    assert canonical_repository_language(".sw") == "sway"
    assert canonical_repository_language("forc.toml") == "sway"
    assert canonical_repository_language("rescript") == "rescript"
    assert canonical_repository_language("reasonml") == "reasonml"
    assert canonical_repository_language(".re") == "reasonml"
    assert canonical_repository_language(".rei") == "reasonml"
    assert canonical_repository_language(".res") == "rescript"
    assert canonical_repository_language("rescript.json") == "rescript"
    assert canonical_repository_language("bsconfig.json") == "rescript"
    assert canonical_repository_language("moonbit") == "moonbit"
    assert canonical_repository_language(".mbt") == "moonbit"
    assert canonical_repository_language(".mbti") == "moonbit"
    assert canonical_repository_language("moon.mod") == "moonbit"
    assert canonical_repository_language("moon.pkg") == "moonbit"
    assert canonical_repository_language("modelica") == "modelica"
    assert canonical_repository_language(".mo") == "modelica"
    assert canonical_repository_language("roc") == "roc"
    assert canonical_repository_language(".roc") == "roc"
    assert canonical_repository_language("wren") == "wren"
    assert canonical_repository_language("wren-lang") == "wren"
    assert canonical_repository_language(".wren") == "wren"
    assert canonical_repository_language("fennel") == "fennel"
    assert canonical_repository_language("fennel-lang") == "fennel"
    assert canonical_repository_language(".fnl") == "fennel"
    assert canonical_repository_language(".fnlm") == "fennel"
    assert canonical_repository_language("circom") == "circom"
    assert canonical_repository_language(".circom") == "circom"
    assert canonical_repository_language("cairo") == "cairo"
    assert canonical_repository_language("starknet cairo") == "cairo"
    assert canonical_repository_language(".cairo") == "cairo"
    assert canonical_repository_language("scarb.toml") == "cairo"
    assert canonical_repository_language("dafny") == "dafny"
    assert canonical_repository_language(".dfy") == "dafny"
    assert canonical_repository_language("nextflow") == "nextflow"
    assert canonical_repository_language(".nf") == "nextflow"
    assert canonical_repository_language("nextflow.config") == "nextflow"
    assert canonical_repository_language("ampl") == "ampl"
    assert canonical_repository_language(".run") == "ampl"
    assert canonical_repository_language("openedge abl") == "openedge"
    assert canonical_repository_language("abl") == "openedge"
    assert canonical_repository_language("processing") == "processing"
    assert canonical_repository_language(".pde") == "processing"
    assert canonical_repository_language("odin") == "odin"
    assert canonical_repository_language("odin-lang") == "odin"
    assert canonical_repository_language("ols.json") == "odin"
    assert canonical_repository_language("ecf") == "eiffel"
    assert canonical_repository_language("eiffel") == "eiffel"
    assert canonical_repository_language("tla") == "tlaplus"
    assert canonical_repository_language("tla+") == "tlaplus"
    assert canonical_repository_language("lgt") == "logtalk"
    assert canonical_repository_language("chpl") == "chapel"
    assert canonical_repository_language("yar") == "yara"


def test_supported_repository_languages_excludes_ecosystem_and_format_labels() -> None:
    supported_languages = supported_repository_languages()

    assert "c" in supported_languages
    assert "assembly" in supported_languages
    assert "cfml" in supported_languages
    assert "scratch" in supported_languages
    assert "prolog" in supported_languages
    assert "logtalk" in supported_languages
    assert "luau" in supported_languages
    assert "chapel" in supported_languages
    assert "typescript" in supported_languages
    assert "visualbasic" in supported_languages
    assert "vb6" in supported_languages
    assert "vba" in supported_languages
    assert "vbscript" in supported_languages
    assert "cobol" in supported_languages
    assert "plsql" in supported_languages
    assert "sas" in supported_languages
    assert "ml" in supported_languages
    assert "abap" in supported_languages
    assert "matlab" in supported_languages
    assert "objectivec" in supported_languages
    assert "lisp" in supported_languages
    assert "lean" in supported_languages
    assert "just" in supported_languages
    assert "makefile" in supported_languages
    assert "batchfile" in supported_languages
    assert "scheme" in supported_languages
    assert "racket" in supported_languages
    assert "gdscript" in supported_languages
    assert "gml" in supported_languages
    assert "ladder" in supported_languages
    assert "foxpro" in supported_languages
    assert "solidity" in supported_languages
    assert "glsl" in supported_languages
    assert "hlsl" in supported_languages
    assert "wgsl" in supported_languages
    assert "shaderlab" in supported_languages
    assert "robotframework" in supported_languages
    assert "gherkin" in supported_languages
    assert "antlr" in supported_languages
    assert "typst" in supported_languages
    assert "dockerfile" in supported_languages
    assert "protobuf" in supported_languages
    assert "scss" in supported_languages
    assert "less" in supported_languages
    assert "stylus" in supported_languages
    assert "vue" in supported_languages
    assert "jinja" in supported_languages
    assert "liquid" in supported_languages
    assert "tex" in supported_languages
    assert "asciidoc" in supported_languages
    assert "org" in supported_languages
    assert "coq" in supported_languages
    assert "dafny" in supported_languages
    assert "verilog" in supported_languages
    assert "systemverilog" in supported_languages
    assert "vhdl" in supported_languages
    assert "apex" in supported_languages
    assert "labview" in supported_languages
    assert "wolfram" in supported_languages
    assert "rpg" in supported_languages
    assert "actionscript" in supported_languages
    assert "applescript" in supported_languages
    assert "autohotkey" in supported_languages
    assert "autoit" in supported_languages
    assert "cython" in supported_languages
    assert "stan" in supported_languages
    assert "squirrel" in supported_languages
    assert "awk" in supported_languages
    assert "coffeescript" in supported_languages
    assert "moonscript" in supported_languages
    assert "haxe" in supported_languages
    assert "move" in supported_languages
    assert "sway" in supported_languages
    assert "hy" in supported_languages
    assert "modelica" in supported_languages
    assert "rescript" in supported_languages
    assert "reasonml" in supported_languages
    assert "circom" in supported_languages
    assert "cairo" in supported_languages
    assert "moonbit" in supported_languages
    assert "odin" in supported_languages
    assert "delphi" in supported_languages
    assert "tsql" in supported_languages
    assert "elm" in supported_languages
    assert "emacslisp" in supported_languages
    assert "fish" in supported_languages
    assert "4d" in supported_languages
    assert "vimscript" in supported_languages
    assert "xpp" in supported_languages
    assert "tcl" in supported_languages
    assert "vala" in supported_languages
    assert "smalltalk" in supported_languages
    assert "mql5" in supported_languages
    assert "gams" in supported_languages
    assert "openscad" in supported_languages
    assert "factor" in supported_languages
    assert "ocamllex" in supported_languages
    assert "ocamlyacc" in supported_languages
    assert "cmake" in supported_languages
    assert "meson" in supported_languages
    assert "qmake" in supported_languages
    assert "qml" in supported_languages
    assert "cuda" in supported_languages
    assert "purescript" in supported_languages
    assert "gleam" in supported_languages
    assert "ballerina" in supported_languages
    assert "ampl" in supported_languages
    assert "openedge" in supported_languages
    assert "processing" in supported_languages
    assert "bqn" in supported_languages
    assert "rebol" in supported_languages
    assert "roc" in supported_languages
    assert "wren" in supported_languages
    assert "fennel" in supported_languages
    assert "nextflow" in supported_languages
    assert "janet" in supported_languages
    assert "idris" in supported_languages
    assert "tlaplus" in supported_languages
    assert "raku" in supported_languages
    assert "nushell" in supported_languages
    assert "starlark" in supported_languages
    assert "hcl" in supported_languages
    assert "vcl" in supported_languages
    assert "mako" in supported_languages
    assert "puppet" in supported_languages
    assert "bitbake" in supported_languages
    assert "bicep" in supported_languages
    assert "cue" in supported_languages
    assert "dhall" in supported_languages
    assert "eiffel" in supported_languages
    assert "rego" in supported_languages
    assert "yara" in supported_languages
    assert "nix" in supported_languages
    assert "v" in supported_languages
    assert "pkl" in supported_languages
    assert "plpgsql" in supported_languages
    assert "webassembly" in supported_languages
    assert "handlebars" in supported_languages
    assert "pug" in supported_languages
    assert "ejs" in supported_languages
    assert "blade" in supported_languages
    assert "mustache" in supported_languages
    assert "nunjucks" in supported_languages
    assert "nginx" in supported_languages
    assert "haml" in supported_languages
    assert "slim" in supported_languages
    assert "erb" in supported_languages
    assert "graphviz" in supported_languages
    assert "graphql" in supported_languages
    assert "mermaid" in supported_languages
    assert "plantuml" in supported_languages
    assert "openqasm" in supported_languages
    assert "forth" in supported_languages
    assert "isabelle" in supported_languages
    assert "mercury" in supported_languages
    assert "codeql" in supported_languages
    assert "maven" in supported_languages
    assert "gnuplot" in supported_languages
    assert "dataweave" in supported_languages
    assert "brightscript" in supported_languages
    assert "common workflow language" in supported_languages
    assert "earthly" in supported_languages
    assert "xtend" in supported_languages
    assert "sed" in supported_languages
    assert "nsis" in supported_languages
    assert "yacc" in supported_languages
    assert "lex" in supported_languages
    assert "xquery" in supported_languages
    assert "xslt" in supported_languages
    assert "q" in supported_languages
    assert "j" in supported_languages
    assert "metal" in supported_languages
    assert "apl" in supported_languages
    assert "hoon" in supported_languages
    assert "svelte" in supported_languages
    assert "node" not in supported_languages
    assert "dotnet" not in supported_languages
    assert "json" not in supported_languages
    assert len(supported_languages) >= 186


def test_repository_language_support_progress_reports_real_language_progress() -> None:
    progress = repository_language_support_progress(
        ranked_target_language_count=DEFAULT_REAL_LANGUAGE_RANK_TARGET
    )
    expected_count = len(supported_repository_languages())
    available_count = len(ranked_real_repository_languages())

    assert progress.supported_real_language_count == expected_count
    assert progress.supported_real_language_count >= 180
    assert progress.ranked_target_language_count == available_count
    assert progress.requested_ranked_target_language_count == DEFAULT_REAL_LANGUAGE_RANK_TARGET
    assert progress.available_ranked_real_language_count == available_count
    assert progress.target_clamped_to_available_ranked_real_languages is (
        DEFAULT_REAL_LANGUAGE_RANK_TARGET != available_count
    )
    assert progress.progress_label == f"{expected_count} / {available_count}"
    assert progress.progress_fraction == pytest.approx(expected_count / available_count)


def test_repository_language_support_progress_rejects_non_positive_targets() -> None:
    with pytest.raises(ValueError, match="ranked_target_language_count must be positive"):
        repository_language_support_progress(ranked_target_language_count=0)
