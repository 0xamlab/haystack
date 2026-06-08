from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import benchmarks.repository_intelligence_real_repo_probe as probe_module
from apps.api_server.services.repository_language_priority import (
    DEFAULT_REAL_LANGUAGE_RANK_TARGET,
    repository_language_support_progress,
    sort_repository_languages,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "repository_intelligence_public_repo_matrix.json"
DEFAULT_CHECKOUT_ROOT = PROJECT_ROOT / "build" / "repository_intelligence_public_repo_matrix_repos"
MatrixMode = Literal["seed_plan", "probe"]


@dataclass(frozen=True)
class PublicRepositoryCase:
    language: str
    repository_url: str
    expected_primary_ecosystem: str
    focus_paths: tuple[str, ...] = ()
    notes: str | None = None


DEFAULT_PUBLIC_REPOSITORY_CASES: tuple[PublicRepositoryCase, ...] = (
    PublicRepositoryCase(
        language="typescript",
        repository_url="https://github.com/sindresorhus/ky.git",
        expected_primary_ecosystem="typescript",
    ),
    PublicRepositoryCase(
        language="python",
        repository_url="https://github.com/pallets/click.git",
        expected_primary_ecosystem="python",
    ),
    PublicRepositoryCase(
        language="dockerfile",
        repository_url="https://github.com/jessfraz/dockerfiles.git",
        expected_primary_ecosystem="dockerfile",
    ),
    PublicRepositoryCase(
        language="cython",
        repository_url="https://github.com/strawlab/python-pcl.git",
        expected_primary_ecosystem="cython",
    ),
    PublicRepositoryCase(
        language="stan",
        repository_url="https://github.com/stan-dev/example-models.git",
        expected_primary_ecosystem="stan",
    ),
    PublicRepositoryCase(
        language="javascript",
        repository_url="https://github.com/expressjs/express.git",
        expected_primary_ecosystem="node",
    ),
    PublicRepositoryCase(
        language="vue",
        repository_url="https://github.com/coreui/coreui-free-vue-admin-template.git",
        expected_primary_ecosystem="vue",
    ),
    PublicRepositoryCase(
        language="svelte",
        repository_url="https://github.com/sveltejs/realworld.git",
        expected_primary_ecosystem="svelte",
    ),
    PublicRepositoryCase(
        language="astro",
        repository_url="https://github.com/withastro/astro.build.git",
        expected_primary_ecosystem="astro",
    ),
    PublicRepositoryCase(
        language="pug",
        repository_url="https://github.com/StartBootstrap/startbootstrap-sb-admin.git",
        expected_primary_ecosystem="pug",
    ),
    PublicRepositoryCase(
        language="ejs",
        repository_url="https://github.com/jaywcjlove/github-rank.git",
        expected_primary_ecosystem="ejs",
    ),
    PublicRepositoryCase(
        language="blade",
        repository_url="https://github.com/thedevdojo/genesis.git",
        expected_primary_ecosystem="blade",
    ),
    PublicRepositoryCase(
        language="erb",
        repository_url="https://github.com/redmine/redmine.git",
        expected_primary_ecosystem="erb",
    ),
    PublicRepositoryCase(
        language="mustache",
        repository_url="https://github.com/janl/mustache.js.git",
        expected_primary_ecosystem="mustache",
    ),
    PublicRepositoryCase(
        language="nunjucks",
        repository_url="https://github.com/11ty/eleventy-base-blog.git",
        expected_primary_ecosystem="nunjucks",
    ),
    PublicRepositoryCase(
        language="twig",
        repository_url="https://github.com/timber/starter-theme.git",
        expected_primary_ecosystem="twig",
    ),
    PublicRepositoryCase(
        language="haml",
        repository_url="https://github.com/mpv-player/mpv.io.git",
        expected_primary_ecosystem="haml",
    ),
    PublicRepositoryCase(
        language="slim",
        repository_url="https://github.com/betagouv/rdv-service-public.git",
        expected_primary_ecosystem="slim",
    ),
    PublicRepositoryCase(
        language="smarty",
        repository_url="https://github.com/prestashop/classic-theme.git",
        expected_primary_ecosystem="smarty",
    ),
    PublicRepositoryCase(
        language="graphviz",
        repository_url="https://github.com/abruzzi/graphviz-scripts.git",
        expected_primary_ecosystem="graphviz",
    ),
    PublicRepositoryCase(
        language="mermaid",
        repository_url="https://github.com/mermaid-js/mermaid-cli.git",
        expected_primary_ecosystem="mermaid",
    ),
    PublicRepositoryCase(
        language="plantuml",
        repository_url="https://github.com/plantuml-stdlib/C4-PlantUML.git",
        expected_primary_ecosystem="plantuml",
    ),
    PublicRepositoryCase(
        language="openqasm",
        repository_url="https://github.com/pnnl/QASMBench.git",
        expected_primary_ecosystem="openqasm",
    ),
    PublicRepositoryCase(
        language="less",
        repository_url="https://github.com/jerrykuku/luci-theme-argon.git",
        expected_primary_ecosystem="less",
    ),
    PublicRepositoryCase(
        language="stylus",
        repository_url="https://github.com/theme-next/hexo-theme-next.git",
        expected_primary_ecosystem="stylus",
    ),
    PublicRepositoryCase(
        language="java",
        repository_url="https://github.com/google/gson.git",
        expected_primary_ecosystem="java",
    ),
    PublicRepositoryCase(
        language="cs",
        repository_url="https://github.com/dotnet/command-line-api.git",
        expected_primary_ecosystem="dotnet",
    ),
    PublicRepositoryCase(
        language="php",
        repository_url="https://github.com/monolog/monolog.git",
        expected_primary_ecosystem="php",
    ),
    PublicRepositoryCase(
        language="hack",
        repository_url="https://github.com/hhvm/hsl.git",
        expected_primary_ecosystem="hack",
    ),
    PublicRepositoryCase(
        language="eiffel",
        repository_url="https://github.com/gobo-eiffel/gobo.git",
        expected_primary_ecosystem="eiffel",
    ),
    PublicRepositoryCase(
        language="shell",
        repository_url="https://github.com/ohmyzsh/ohmyzsh.git",
        expected_primary_ecosystem="shell",
    ),
    PublicRepositoryCase(
        language="fish",
        repository_url="https://github.com/jorgebucaran/fisher.git",
        expected_primary_ecosystem="fish",
    ),
    PublicRepositoryCase(
        language="c",
        repository_url="https://github.com/tmux/tmux.git",
        expected_primary_ecosystem="c",
    ),
    PublicRepositoryCase(
        language="cpp",
        repository_url="https://github.com/fmtlib/fmt.git",
        expected_primary_ecosystem="cpp",
    ),
    PublicRepositoryCase(
        language="cuda",
        repository_url="https://github.com/NVIDIA/cuda-samples.git",
        expected_primary_ecosystem="cuda",
    ),
    PublicRepositoryCase(
        language="cmake",
        repository_url="https://github.com/ttroy50/cmake-examples.git",
        expected_primary_ecosystem="cmake",
    ),
    PublicRepositoryCase(
        language="protobuf",
        repository_url="https://github.com/googleapis/api-common-protos.git",
        expected_primary_ecosystem="protobuf",
    ),
    PublicRepositoryCase(
        language="meson",
        repository_url="https://github.com/tiernemi/meson-sample-project.git",
        expected_primary_ecosystem="meson",
    ),
    PublicRepositoryCase(
        language="qmake",
        repository_url="https://github.com/horsicq/XPEViewer.git",
        expected_primary_ecosystem="qmake",
    ),
    PublicRepositoryCase(
        language="qml",
        repository_url="https://github.com/Qt-QML/QmlFlightInstruments.git",
        expected_primary_ecosystem="qml",
    ),
    PublicRepositoryCase(
        language="shaderlab",
        repository_url="https://github.com/poiyomi/PoiyomiToonShader.git",
        expected_primary_ecosystem="shaderlab",
    ),
    PublicRepositoryCase(
        language="scratch",
        repository_url="https://github.com/https-sharif/Scratch-Game.git",
        expected_primary_ecosystem="scratch",
    ),
    PublicRepositoryCase(
        language="go",
        repository_url="https://github.com/spf13/cobra.git",
        expected_primary_ecosystem="go",
    ),
    PublicRepositoryCase(
        language="rust",
        repository_url="https://github.com/sharkdp/fd.git",
        expected_primary_ecosystem="rust",
    ),
    PublicRepositoryCase(
        language="assembly",
        repository_url="https://github.com/microsoft/MS-DOS.git",
        expected_primary_ecosystem="assembly",
    ),
    PublicRepositoryCase(
        language="ruby",
        repository_url="https://github.com/sinatra/sinatra.git",
        expected_primary_ecosystem="ruby",
    ),
    PublicRepositoryCase(
        language="prolog",
        repository_url="https://github.com/Anniepoo/prolog-examples.git",
        expected_primary_ecosystem="prolog",
    ),
    PublicRepositoryCase(
        language="logtalk",
        repository_url="https://github.com/LogtalkDotOrg/talkshow.git",
        expected_primary_ecosystem="logtalk",
    ),
    PublicRepositoryCase(
        language="chapel",
        repository_url="https://github.com/chapel-lang/Crypto.git",
        expected_primary_ecosystem="chapel",
    ),
    PublicRepositoryCase(
        language="swift",
        repository_url="https://github.com/pointfreeco/swift-parsing.git",
        expected_primary_ecosystem="swift",
    ),
    PublicRepositoryCase(
        language="scss",
        repository_url="https://github.com/pages-themes/minimal.git",
        expected_primary_ecosystem="scss",
    ),
    PublicRepositoryCase(
        language="jinja",
        repository_url="https://github.com/netbootxyz/netboot.xyz.git",
        expected_primary_ecosystem="jinja",
    ),
    PublicRepositoryCase(
        language="liquid",
        repository_url="https://github.com/Shopify/dawn.git",
        expected_primary_ecosystem="liquid",
    ),
    PublicRepositoryCase(
        language="handlebars",
        repository_url="https://github.com/TryGhost/Source.git",
        expected_primary_ecosystem="handlebars",
    ),
    PublicRepositoryCase(
        language="tex",
        repository_url="https://github.com/posquit0/Awesome-CV.git",
        expected_primary_ecosystem="tex",
    ),
    PublicRepositoryCase(
        language="rst",
        repository_url="https://github.com/godotengine/godot-docs.git",
        expected_primary_ecosystem="rst",
    ),
    PublicRepositoryCase(
        language="asciidoc",
        repository_url="https://github.com/cartabinaria/asciidoc-thesis.git",
        expected_primary_ecosystem="asciidoc",
    ),
        PublicRepositoryCase(
            language="org",
            repository_url="https://github.com/lujun9972/emacs-document.git",
            expected_primary_ecosystem="org",
        ),
    PublicRepositoryCase(
        language="delphi",
        repository_url="https://github.com/VSoftTechnologies/DUnitX.git",
        expected_primary_ecosystem="delphi",
    ),
    PublicRepositoryCase(
        language="sql",
        repository_url="https://github.com/dbt-labs/jaffle-shop-classic.git",
        expected_primary_ecosystem="sql",
    ),
    PublicRepositoryCase(
        language="tsql",
        repository_url="https://github.com/BrentOzarULTD/SQL-Server-First-Responder-Kit.git",
        expected_primary_ecosystem="tsql",
    ),
    PublicRepositoryCase(
        language="vb6",
        repository_url="https://github.com/badcodes/vb6.git",
        expected_primary_ecosystem="vb6",
    ),
    PublicRepositoryCase(
        language="vba",
        repository_url="https://github.com/VBA-tools/VBA-JSON.git",
        expected_primary_ecosystem="vba",
    ),
    PublicRepositoryCase(
        language="plsql",
        repository_url="https://github.com/mortenbra/alexandria-plsql-utils.git",
        expected_primary_ecosystem="plsql",
    ),
    PublicRepositoryCase(
        language="ada",
        repository_url="https://github.com/alire-project/alire.git",
        expected_primary_ecosystem="ada",
    ),
    PublicRepositoryCase(
        language="cobol",
        repository_url="https://github.com/openmainframeproject/cobol-programming-course.git",
        expected_primary_ecosystem="cobol",
    ),
    PublicRepositoryCase(
        language="sas",
        repository_url="https://github.com/friendly/SAS-macros.git",
        expected_primary_ecosystem="sas",
    ),
    PublicRepositoryCase(
        language="ml",
        repository_url="https://github.com/minoki/LunarML.git",
        expected_primary_ecosystem="ml",
    ),
    PublicRepositoryCase(
        language="abap",
        repository_url="https://github.com/abapGit/abapGit.git",
        expected_primary_ecosystem="abap",
    ),
    PublicRepositoryCase(
        language="kotlin",
        repository_url="https://github.com/square/kotlinpoet.git",
        expected_primary_ecosystem="kotlin",
    ),
    PublicRepositoryCase(
        language="scala",
        repository_url="https://github.com/playframework/play-json.git",
        expected_primary_ecosystem="scala",
    ),
    PublicRepositoryCase(
        language="dart",
        repository_url="https://github.com/dart-lang/http.git",
        expected_primary_ecosystem="dart",
    ),
    PublicRepositoryCase(
        language="groovy",
        repository_url="https://github.com/apache/groovy.git",
        expected_primary_ecosystem="groovy",
    ),
    PublicRepositoryCase(
        language="nextflow",
        repository_url="https://github.com/nf-core/rnaseq.git",
        expected_primary_ecosystem="nextflow",
    ),
    PublicRepositoryCase(
        language="robotframework",
        repository_url="https://github.com/robotframework/WebDemo.git",
        expected_primary_ecosystem="robotframework",
    ),
    PublicRepositoryCase(
        language="gherkin",
        repository_url="https://github.com/FriendsOfBehat/SymfonyExtension.git",
        expected_primary_ecosystem="gherkin",
    ),
    PublicRepositoryCase(
        language="antlr",
        repository_url="https://github.com/drforr/perl6-ANTLR4.git",
        expected_primary_ecosystem="antlr",
    ),
    PublicRepositoryCase(
        language="typst",
        repository_url="https://github.com/typst/packages.git",
        expected_primary_ecosystem="typst",
    ),
    PublicRepositoryCase(
        language="lua",
        repository_url="https://github.com/luarocks/luarocks.git",
        expected_primary_ecosystem="lua",
    ),
    PublicRepositoryCase(
        language="luau",
        repository_url="https://github.com/Ukendio/jecs.git",
        expected_primary_ecosystem="luau",
    ),
    PublicRepositoryCase(
        language="lisp",
        repository_url="https://github.com/fukamachi/clack.git",
        expected_primary_ecosystem="lisp",
    ),
    PublicRepositoryCase(
        language="puppet",
        repository_url="https://github.com/puppetlabs/puppetlabs-apache.git",
        expected_primary_ecosystem="puppet",
    ),
    PublicRepositoryCase(
        language="bitbake",
        repository_url="https://github.com/openembedded/meta-openembedded.git",
        expected_primary_ecosystem="bitbake",
    ),
    PublicRepositoryCase(
        language="janet",
        repository_url="https://github.com/janet-lang/jpm.git",
        expected_primary_ecosystem="janet",
    ),
    PublicRepositoryCase(
        language="scheme",
        repository_url="https://github.com/ashinn/irregex.git",
        expected_primary_ecosystem="scheme",
    ),
    PublicRepositoryCase(
        language="racket",
        repository_url="https://github.com/mbutterick/pollen.git",
        expected_primary_ecosystem="racket",
    ),
    PublicRepositoryCase(
        language="gdscript",
        repository_url="https://github.com/Orama-Interactive/Pixelorama.git",
        expected_primary_ecosystem="gdscript",
    ),
    PublicRepositoryCase(
        language="gml",
        repository_url="https://github.com/Gizmo199/BehaviorTree.git",
        expected_primary_ecosystem="gml",
    ),
    PublicRepositoryCase(
        language="vbscript",
        repository_url="https://github.com/susam/aes.vbs.git",
        expected_primary_ecosystem="vbscript",
    ),
    PublicRepositoryCase(
        language="elixir",
        repository_url="https://github.com/phoenixframework/phoenix.git",
        expected_primary_ecosystem="elixir",
    ),
    PublicRepositoryCase(
        language="ladder",
        repository_url="https://github.com/JeremyMedders/LogixLibraries.git",
        expected_primary_ecosystem="ladder",
    ),
    PublicRepositoryCase(
        language="solidity",
        repository_url="https://github.com/OpenZeppelin/openzeppelin-contracts.git",
        expected_primary_ecosystem="solidity",
    ),
    PublicRepositoryCase(
        language="glsl",
        repository_url="https://github.com/ashima/webgl-noise.git",
        expected_primary_ecosystem="glsl",
    ),
    PublicRepositoryCase(
        language="hlsl",
        repository_url="https://github.com/crosire/reshade-shaders.git",
        expected_primary_ecosystem="hlsl",
    ),
    PublicRepositoryCase(
        language="wgsl",
        repository_url="https://github.com/alphastrata/shadplay.git",
        expected_primary_ecosystem="wgsl",
    ),
    PublicRepositoryCase(
        language="verilog",
        repository_url="https://github.com/TimRudy/uart-verilog.git",
        expected_primary_ecosystem="verilog",
    ),
    PublicRepositoryCase(
        language="systemverilog",
        repository_url="https://github.com/pulp-platform/axi.git",
        expected_primary_ecosystem="systemverilog",
    ),
    PublicRepositoryCase(
        language="vhdl",
        repository_url="https://github.com/kevinpt/vhdl-extras.git",
        expected_primary_ecosystem="vhdl",
    ),
    PublicRepositoryCase(
        language="erlang",
        repository_url="https://github.com/erlang/rebar3.git",
        expected_primary_ecosystem="erlang",
    ),
    PublicRepositoryCase(
        language="clojure",
        repository_url="https://github.com/clojure/clojure.git",
        expected_primary_ecosystem="clojure",
    ),
    PublicRepositoryCase(
        language="r",
        repository_url="https://github.com/tidyverse/ggplot2.git",
        expected_primary_ecosystem="r",
    ),
    PublicRepositoryCase(
        language="cfml",
        repository_url="https://github.com/ghidinelli/cfpayment.git",
        expected_primary_ecosystem="cfml",
    ),
    PublicRepositoryCase(
        language="xpp",
        repository_url="https://github.com/TrudAX/XppTools.git",
        expected_primary_ecosystem="xpp",
    ),
    PublicRepositoryCase(
        language="matlab",
        repository_url="https://github.com/matlab2tikz/matlab2tikz.git",
        expected_primary_ecosystem="matlab",
    ),
    PublicRepositoryCase(
        language="objectivec",
        repository_url="https://github.com/AFNetworking/AFNetworking.git",
        expected_primary_ecosystem="objectivec",
    ),
    PublicRepositoryCase(
        language="julia",
        repository_url="https://github.com/JuliaData/DataFrames.jl.git",
        expected_primary_ecosystem="julia",
    ),
    PublicRepositoryCase(
        language="haskell",
        repository_url="https://github.com/commercialhaskell/stack.git",
        expected_primary_ecosystem="haskell",
    ),
    PublicRepositoryCase(
        language="lean",
        repository_url="https://github.com/leanprover-community/batteries.git",
        expected_primary_ecosystem="lean",
    ),
    PublicRepositoryCase(
        language="agda",
        repository_url="https://github.com/agda/agda-stdlib.git",
        expected_primary_ecosystem="agda",
    ),
    PublicRepositoryCase(
        language="coq",
        repository_url="https://github.com/coq-community/coq-art.git",
        expected_primary_ecosystem="coq",
    ),
    PublicRepositoryCase(
        language="idris",
        repository_url="https://github.com/stefan-hoeck/idris2-pack.git",
        expected_primary_ecosystem="idris",
    ),
    PublicRepositoryCase(
        language="haxe",
        repository_url="https://github.com/HaxeFoundation/hscript.git",
        expected_primary_ecosystem="haxe",
    ),
    PublicRepositoryCase(
        language="move",
        repository_url="https://github.com/aave/aptos-aave-v3.git",
        expected_primary_ecosystem="move",
    ),
    PublicRepositoryCase(
        language="odin",
        repository_url="https://github.com/odin-lang/examples.git",
        expected_primary_ecosystem="odin",
    ),
    PublicRepositoryCase(
        language="ocaml",
        repository_url="https://github.com/ocaml/dune.git",
        expected_primary_ecosystem="ocaml",
    ),
    PublicRepositoryCase(
        language="perl",
        repository_url="https://github.com/dagolden/Path-Tiny.git",
        expected_primary_ecosystem="perl",
    ),
    PublicRepositoryCase(
        language="raku",
        repository_url="https://github.com/ugexe/zef.git",
        expected_primary_ecosystem="raku",
    ),
    PublicRepositoryCase(
        language="powershell",
        repository_url="https://github.com/Pester/Pester.git",
        expected_primary_ecosystem="powershell",
    ),
    PublicRepositoryCase(
        language="just",
        repository_url="https://github.com/ublue-os/image-template.git",
        expected_primary_ecosystem="just",
    ),
    PublicRepositoryCase(
        language="makefile",
        repository_url="https://github.com/lindenb/makefile2graph.git",
        expected_primary_ecosystem="makefile",
    ),
    PublicRepositoryCase(
        language="batchfile",
        repository_url="https://github.com/npocmaka/batch.scripts.git",
        expected_primary_ecosystem="batchfile",
    ),
    PublicRepositoryCase(
        language="autohotkey",
        repository_url="https://github.com/thqby/ahk2_lib.git",
        expected_primary_ecosystem="autohotkey",
    ),
    PublicRepositoryCase(
        language="autoit",
        repository_url="https://github.com/rcmaehl/WhyNotWin11.git",
        expected_primary_ecosystem="autoit",
    ),
    PublicRepositoryCase(
        language="squirrel",
        repository_url="https://github.com/p2r3/HTTPortal.git",
        expected_primary_ecosystem="squirrel",
    ),
    PublicRepositoryCase(
        language="starlark",
        repository_url="https://github.com/bazelbuild/bazel-skylib.git",
        expected_primary_ecosystem="starlark",
    ),
    PublicRepositoryCase(
        language="hcl",
        repository_url="https://github.com/terraform-aws-modules/terraform-aws-vpc.git",
        expected_primary_ecosystem="hcl",
    ),
    PublicRepositoryCase(
        language="tlaplus",
        repository_url="https://github.com/tlaplus/Examples.git",
        expected_primary_ecosystem="tlaplus",
    ),
    PublicRepositoryCase(
        language="bicep",
        repository_url="https://github.com/Azure/bicep-registry-modules.git",
        expected_primary_ecosystem="bicep",
    ),
    PublicRepositoryCase(
        language="cue",
        repository_url="https://github.com/cue-labs/cue-by-example.git",
        expected_primary_ecosystem="cue",
    ),
    PublicRepositoryCase(
        language="dhall",
        repository_url="https://github.com/regadas/github-actions-dhall.git",
        expected_primary_ecosystem="dhall",
    ),
    PublicRepositoryCase(
        language="rego",
        repository_url="https://github.com/open-policy-agent/library.git",
        expected_primary_ecosystem="rego",
    ),
    PublicRepositoryCase(
        language="yara",
        repository_url="https://github.com/YARA-Rules/rules.git",
        expected_primary_ecosystem="yara",
    ),
    PublicRepositoryCase(
        language="nix",
        repository_url="https://github.com/numtide/flake-utils.git",
        expected_primary_ecosystem="nix",
    ),
    PublicRepositoryCase(
        language="openscad",
        repository_url="https://github.com/BelfrySCAD/BOSL2.git",
        expected_primary_ecosystem="openscad",
    ),
    PublicRepositoryCase(
        language="factor",
        repository_url="https://github.com/mrjbq7/re-factor.git",
        expected_primary_ecosystem="factor",
    ),
    PublicRepositoryCase(
        language="purescript",
        repository_url="https://github.com/purescript/purescript-prelude.git",
        expected_primary_ecosystem="purescript",
    ),
    PublicRepositoryCase(
        language="rescript",
        repository_url="https://github.com/glennsl/rescript-json-combinators.git",
        expected_primary_ecosystem="rescript",
    ),
    PublicRepositoryCase(
        language="roc",
        repository_url="https://github.com/roc-lang/book-of-examples.git",
        expected_primary_ecosystem="roc",
    ),
    PublicRepositoryCase(
        language="moonbit",
        repository_url="https://github.com/moonbitlang/core.git",
        expected_primary_ecosystem="moonbit",
    ),
    PublicRepositoryCase(
        language="hy",
        repository_url="https://github.com/hylang/hydiomatic.git",
        expected_primary_ecosystem="hy",
    ),
    PublicRepositoryCase(
        language="wren",
        repository_url="https://github.com/exercism/wren.git",
        expected_primary_ecosystem="wren",
    ),
    PublicRepositoryCase(
        language="fennel",
        repository_url="https://github.com/bakpakin/Fennel.git",
        expected_primary_ecosystem="fennel",
    ),
    PublicRepositoryCase(
        language="modelica",
        repository_url="https://github.com/modelica/ModelicaStandardLibrary.git",
        expected_primary_ecosystem="modelica",
    ),
    PublicRepositoryCase(
        language="gleam",
        repository_url="https://github.com/gleam-lang/stdlib.git",
        expected_primary_ecosystem="gleam",
    ),
    PublicRepositoryCase(
        language="nushell",
        repository_url="https://github.com/nushell/nu_scripts.git",
        expected_primary_ecosystem="nushell",
    ),
    PublicRepositoryCase(
        language="apex",
        repository_url="https://github.com/apex-enterprise-patterns/fflib-apex-common.git",
        expected_primary_ecosystem="apex",
    ),
    PublicRepositoryCase(
        language="labview",
        repository_url="https://github.com/LabVIEW-Open-Source/ui-tools.git",
        expected_primary_ecosystem="labview",
    ),
    PublicRepositoryCase(
        language="tcl",
        repository_url="https://github.com/tcltk/tcllib.git",
        expected_primary_ecosystem="tcl",
    ),
    PublicRepositoryCase(
        language="v",
        repository_url="https://github.com/vlang/ui.git",
        expected_primary_ecosystem="v",
    ),
    PublicRepositoryCase(
        language="vala",
        repository_url="https://github.com/elementary/code.git",
        expected_primary_ecosystem="vala",
    ),
    PublicRepositoryCase(
        language="smalltalk",
        repository_url="https://github.com/pharo-spec/Spec.git",
        expected_primary_ecosystem="smalltalk",
    ),
    PublicRepositoryCase(
        language="visualbasic",
        repository_url="https://github.com/kimmknight/remoteapptool.git",
        expected_primary_ecosystem="visualbasic",
    ),
    PublicRepositoryCase(
        language="mql5",
        repository_url="https://github.com/geraked/metatrader5.git",
        expected_primary_ecosystem="mql5",
    ),
    PublicRepositoryCase(
        language="gams",
        repository_url="https://github.com/psztorc/DICE.git",
        expected_primary_ecosystem="gams",
    ),
    PublicRepositoryCase(
        language="wolfram",
        repository_url="https://github.com/WolframResearch/PacletCICD.git",
        expected_primary_ecosystem="wolfram",
    ),
    PublicRepositoryCase(
        language="rpg",
        repository_url="https://github.com/IBM/bob-recursive-example.git",
        expected_primary_ecosystem="rpg",
    ),
    PublicRepositoryCase(
        language="actionscript",
        repository_url="https://github.com/Gamua/Starling-Framework.git",
        expected_primary_ecosystem="actionscript",
    ),
    PublicRepositoryCase(
        language="applescript",
        repository_url="https://github.com/unforswearing/applescript.git",
        expected_primary_ecosystem="applescript",
    ),
    PublicRepositoryCase(
        language="awk",
        repository_url="https://github.com/step-/JSON.awk.git",
        expected_primary_ecosystem="awk",
    ),
    PublicRepositoryCase(
        language="coffeescript",
        repository_url="https://github.com/jashkenas/coffeescript.git",
        expected_primary_ecosystem="coffeescript",
    ),
    PublicRepositoryCase(
        language="elm",
        repository_url="https://github.com/elm/core.git",
        expected_primary_ecosystem="elm",
    ),
    PublicRepositoryCase(
        language="emacslisp",
        repository_url="https://github.com/magnars/dash.el.git",
        expected_primary_ecosystem="emacslisp",
    ),
    PublicRepositoryCase(
        language="vimscript",
        repository_url="https://github.com/tpope/vim-fugitive.git",
        expected_primary_ecosystem="vimscript",
    ),
    PublicRepositoryCase(
        language="zig",
        repository_url="https://github.com/zigtools/zls.git",
        expected_primary_ecosystem="zig",
    ),
    PublicRepositoryCase(
        language="nim",
        repository_url="https://github.com/nim-lang/nimble.git",
        expected_primary_ecosystem="nim",
    ),
    PublicRepositoryCase(
        language="crystal",
        repository_url="https://github.com/crystal-lang/crystal.git",
        expected_primary_ecosystem="crystal",
    ),
    PublicRepositoryCase(
        language="fsharp",
        repository_url="https://github.com/fsprojects/FSharp.Data.git",
        expected_primary_ecosystem="fsharp",
    ),
    PublicRepositoryCase(
        language="foxpro",
        repository_url="https://github.com/VFPX/nfJson.git",
        expected_primary_ecosystem="foxpro",
    ),
    PublicRepositoryCase(
        language="pascal",
        repository_url="https://github.com/transmission-remote-gui/transgui.git",
        expected_primary_ecosystem="pascal",
    ),
    PublicRepositoryCase(
        language="fortran",
        repository_url="https://github.com/fortran-lang/fpm.git",
        expected_primary_ecosystem="fortran",
    ),
    PublicRepositoryCase(
        language="mojo",
        repository_url="https://github.com/gabrieldemarmiesse/mojo-stdlib-extensions.git",
        expected_primary_ecosystem="mojo",
    ),
    PublicRepositoryCase(
        language="d",
        repository_url="https://github.com/dlang/phobos.git",
        expected_primary_ecosystem="d",
    ),
)


def _case_checkout_name(case: PublicRepositoryCase) -> str:
    parsed = urlparse(case.repository_url)
    path_parts = [part for part in parsed.path.removesuffix(".git").split("/") if part]
    if len(path_parts) < 2:
        raise ValueError(f"repository_url must include owner/repo: {case.repository_url}")
    owner, repo = path_parts[-2], path_parts[-1]
    return f"{case.language}-{owner}-{repo}"


def ordered_public_repository_cases(
    *,
    cases: tuple[PublicRepositoryCase, ...] = DEFAULT_PUBLIC_REPOSITORY_CASES,
    languages: tuple[str, ...] = (),
    limit: int | None = None,
) -> list[PublicRepositoryCase]:
    allowed_languages = {language.strip().lower() for language in languages if language.strip()}
    filtered_cases = [
        case
        for case in cases
        if not allowed_languages or case.language.lower() in allowed_languages
    ]
    language_order = sort_repository_languages(case.language for case in filtered_cases)
    language_index = {language: index for index, language in enumerate(language_order)}
    ordered_cases = sorted(
        filtered_cases,
        key=lambda case: (
            language_index.get(case.language, len(language_index)),
            case.language,
            _case_checkout_name(case),
        ),
    )
    if limit is None:
        return ordered_cases
    return ordered_cases[: max(0, limit)]


def _validated_public_repository_url(repository_url: str) -> str:
    parsed = urlparse(repository_url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise ValueError(
            f"Only https://github.com public repositories are supported: {repository_url}"
        )
    if len([part for part in parsed.path.removesuffix(".git").split("/") if part]) < 2:
        raise ValueError(f"repository_url must include owner/repo: {repository_url}")
    return repository_url


def _git_executable() -> str:
    git_path = shutil.which("git")
    if not git_path:
        raise RuntimeError(
            json.dumps(
                {
                    "error": {
                        "code": "git_not_found",
                        "message": "The public repository matrix requires git to be installed.",
                        "details": {},
                    }
                }
            )
        )
    return git_path


def _ecosystem_summary(
    *,
    detected_ecosystems: list[str],
    operational_ecosystems: list[str],
    expected_primary_ecosystem: str,
) -> dict[str, Any]:
    primary_detected_ecosystem = detected_ecosystems[0] if detected_ecosystems else None
    primary_operational_ecosystem = (
        operational_ecosystems[0] if operational_ecosystems else primary_detected_ecosystem
    )
    return {
        "detected_ecosystems": detected_ecosystems,
        "operational_ecosystems": operational_ecosystems,
        "primary_detected_ecosystem": primary_detected_ecosystem,
        "primary_operational_ecosystem": primary_operational_ecosystem,
        "primary_ecosystem": primary_operational_ecosystem,
        "primary_match": primary_operational_ecosystem == expected_primary_ecosystem,
    }


def clone_public_repository_case(
    case: PublicRepositoryCase,
    *,
    checkout_root: Path,
    refresh: bool = False,
) -> Path:
    checkout_path = checkout_root / _case_checkout_name(case)
    if checkout_path.exists() and refresh:
        shutil.rmtree(checkout_path)
    if checkout_path.is_dir() and (checkout_path / ".git").is_dir():
        return checkout_path
    if checkout_path.exists():
        shutil.rmtree(checkout_path)
    checkout_root.mkdir(parents=True, exist_ok=True)
    validated_repository_url = _validated_public_repository_url(case.repository_url)
    completed = subprocess.run(  # noqa: S603
        [
            _git_executable(),
            "clone",
            "--depth",
            "1",
            validated_repository_url,
            str(checkout_path),
        ],
        capture_output=True,
        check=False,
        encoding="utf-8",
        text=True,
        timeout=300,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            json.dumps(
                {
                    "error": {
                        "code": "public_repo_clone_failed",
                        "message": f"Failed to clone {validated_repository_url}.",
                        "details": {
                            "returncode": completed.returncode,
                            "stderr": completed.stderr.strip(),
                        },
                    }
                }
            )
        )
    return checkout_path


def run_public_repository_seed_plan_case(
    case: PublicRepositoryCase,
    *,
    checkout_root: Path,
    refresh: bool = False,
    max_files: int = 512,
) -> dict[str, Any]:
    repo_path = clone_public_repository_case(
        case,
        checkout_root=checkout_root,
        refresh=refresh,
    )
    seed_plan = probe_module._derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=list(case.focus_paths),
        max_files=max_files,
    )
    detected_ecosystems = list(seed_plan["detected_ecosystems"])
    operational_ecosystems = list(
        seed_plan.get("operational_ecosystems") or detected_ecosystems
    )
    return {
        "case": asdict(case),
        "repo_path": str(repo_path),
        **_ecosystem_summary(
            detected_ecosystems=detected_ecosystems,
            operational_ecosystems=operational_ecosystems,
            expected_primary_ecosystem=case.expected_primary_ecosystem,
        ),
        "entrypoint_files": list(seed_plan["entrypoint_files"]),
        "support_roots": list(seed_plan["support_roots"]),
        "config_paths": list(seed_plan["config_paths"]),
        "candidate_file_count": len(seed_plan["candidate_file_paths"]),
    }


def run_public_repository_probe_case(
    case: PublicRepositoryCase,
    *,
    checkout_root: Path,
    runtime_root: Path,
    refresh: bool = False,
    max_files: int = 512,
    max_file_size_bytes: int = 250_000,
    max_total_bytes: int = 8_000_000,
    max_dependency_depth: int = 3,
    max_connected_files: int = 96,
) -> dict[str, Any]:
    repo_path = clone_public_repository_case(
        case,
        checkout_root=checkout_root,
        refresh=refresh,
    )
    probe_result = probe_module.run_probe(
        repo_path=repo_path,
        focus_paths=list(case.focus_paths),
        diagnostic_command=None,
        diagnostic_base_path=None,
        planner_model=None,
        runtime_dir=runtime_root / _case_checkout_name(case),
        reuse_existing_state=False,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_total_bytes=max_total_bytes,
        max_dependency_depth=max_dependency_depth,
        max_connected_files=max_connected_files,
    )
    detected_ecosystems = list(probe_result["operational_seed_plan"]["detected_ecosystems"])
    operational_ecosystems = list(
        probe_result["operational_seed_plan"].get("operational_ecosystems")
        or detected_ecosystems
    )
    return {
        "case": asdict(case),
        "repo_path": str(repo_path),
        "planner_status": probe_result["planner_status"],
        **_ecosystem_summary(
            detected_ecosystems=detected_ecosystems,
            operational_ecosystems=operational_ecosystems,
            expected_primary_ecosystem=case.expected_primary_ecosystem,
        ),
        "snapshot_file_count": int(probe_result["snapshot"]["file_count"]),
        "connected_file_count": int(probe_result["connected_map"]["connected_file_count"]),
        "seed_files": list(probe_result["connected_map"]["seed_files"]),
    }


def run_public_repository_matrix(
    *,
    mode: MatrixMode,
    checkout_root: Path,
    runtime_root: Path,
    refresh: bool = False,
    languages: tuple[str, ...] = (),
    limit: int | None = None,
    ranked_target_language_count: int = DEFAULT_REAL_LANGUAGE_RANK_TARGET,
) -> dict[str, Any]:
    ordered_cases = ordered_public_repository_cases(
        languages=languages,
        limit=limit,
    )
    support_progress = repository_language_support_progress(
        ranked_target_language_count=ranked_target_language_count
    )
    results: list[dict[str, Any]] = []
    for case in ordered_cases:
        try:
            if mode == "seed_plan":
                result = run_public_repository_seed_plan_case(
                    case,
                    checkout_root=checkout_root,
                    refresh=refresh,
                )
            else:
                result = run_public_repository_probe_case(
                    case,
                    checkout_root=checkout_root,
                    runtime_root=runtime_root,
                    refresh=refresh,
                )
        except Exception as exc:
            result = {
                "case": asdict(case),
                "error": {
                    "code": exc.__class__.__name__,
                    "message": str(exc),
                    "details": {},
                },
            }
        results.append(result)
    return {
        "mode": mode,
        "case_count": len(ordered_cases),
        "support_progress": {
            "supported_real_language_count": support_progress.supported_real_language_count,
            "ranked_target_language_count": support_progress.ranked_target_language_count,
            "progress_fraction": support_progress.progress_fraction,
            "progress_label": support_progress.progress_label,
        },
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the ranked public GitHub repository matrix for Repository Intelligence."
    )
    parser.add_argument(
        "--mode",
        choices=("seed_plan", "probe"),
        default="seed_plan",
    )
    parser.add_argument(
        "--language",
        dest="languages",
        action="append",
        default=[],
        help="Optional language/ecosystem filter. May be passed multiple times.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--checkout-root",
        type=Path,
        default=DEFAULT_CHECKOUT_ROOT,
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=PROJECT_ROOT / "build" / "repository_intelligence_public_repo_matrix_runtime",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--rank-target",
        type=int,
        default=DEFAULT_REAL_LANGUAGE_RANK_TARGET,
        help="Display real-language support progress against this ranked-language total.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = run_public_repository_matrix(
        mode=args.mode,
        checkout_root=args.checkout_root,
        runtime_root=args.runtime_root,
        refresh=bool(args.refresh),
        languages=tuple(args.languages),
        limit=args.limit,
        ranked_target_language_count=args.rank_target,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
