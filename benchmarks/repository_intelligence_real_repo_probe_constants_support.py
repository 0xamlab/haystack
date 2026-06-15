from __future__ import annotations

import re

DEFAULT_EXCLUDE_PATTERNS = [
    ".git/**",
    "node_modules/**",
    ".next/**",
    "dist/**",
    "dist_fresh/**",
    "build/**",
    "coverage/**",
    "__pycache__/**",
    ".venv/**",
    "venv/**",
    ".turbo/**",
    ".mypy_cache/**",
    ".pytest_cache/**",
    "assets/**",
    "cache/**",
    "broadcast/**",
    "**/dist/**",
    "**/dist_fresh/**",
    "**/build/**",
    "**/coverage/**",
]
_TSC_DIAGNOSTIC_RE = re.compile(
    r"^(?P<path>.+?)\((?P<line>\d+),(?P<column>\d+)\):\s+error\s+(?P<code>TS\d+):\s+(?P<message>.+)$"
)
_PYTHON_TRACEBACK_FILE_RE = re.compile(
    r'^\s*File "(?P<path>.+?)", line (?P<line>\d+)(?:, in (?P<function>.+))?\s*$'
)
_NODE_STACK_FRAME_RE = re.compile(
    r"^\s*at\s+(?:(?P<function>.*?)\s+\()?(?P<path>.+?):(?P<line>\d+):(?P<column>\d+)\)?\s*$"
)
_RUST_SPAN_RE = re.compile(r"^\s*-->\s+(?P<path>.+?):(?P<line>\d+):(?P<column>\d+)\s*$")
_COLON_DIAGNOSTIC_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<column>\d+):\s+(?P<message>.+)$"
)
_SLN_PROJECT_RE = re.compile(
    r'^Project\("[^"]+"\)\s*=\s*"[^"]+",\s*"(?P<path>[^"]+\.(?:csproj|fsproj))"',
    re.MULTILINE,
)
_COMMAND_CD_RE = re.compile(r"^\s*cd\s+(?P<path>[^&;]+?)\s*&&")
_PROJECT_ARG_RE = re.compile(r"(?:^|\s)(?:-p|--project)\s+(?P<path>[^\s]+)")
_POWERSHELL_MANIFEST_FIELD_RE = re.compile(
    r"^\s*(?P<field>RootModule|ModuleToProcess)\s*=\s*['\"](?P<value>[^'\"]+)['\"]",
    re.IGNORECASE | re.MULTILINE,
)
_POWERSHELL_MANIFEST_LIST_RE = re.compile(
    r"^\s*(?P<field>NestedModules)\s*=\s*@\((?P<body>.*?)\)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_LUAU_PROJECT_PATH_RE = re.compile(r'"\$path"\s*:\s*"(?P<path>[^"]+)"')
_LUAU_WALLY_NAME_RE = re.compile(
    r"(?ms)^\s*\[package\]\s.*?^\s*name\s*=\s*['\"](?P<name>[^'\"]+)['\"]"
)
_QUOTED_SEGMENT_RE = re.compile(r"""['"](?P<value>[^'"]+)['"]""")
_FOUNDRY_STRING_FIELD_RE = re.compile(
    r"^\s*(?P<field>src|script|test)\s*=\s*[\"'](?P<value>[^\"']+)[\"']",
    re.IGNORECASE | re.MULTILINE,
)
_FOUNDRY_LIST_FIELD_RE = re.compile(
    r"^\s*(?P<field>libs)\s*=\s*\[(?P<body>.*?)\]",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_PREPASS_CACHE_SCHEMA_VERSION = "repository-probe-prepass-v74"
_REPO_PROFILE_MANIFEST_BASENAMES = frozenset(
    {
        ".smalltalk.all.ston",
        ".smalltalk.release.ston",
        ".smalltalk.ston",
        ".ibmi.json",
        "_coqproject",
        "_rocqproject",
        "lean-toolchain",
        "lakefile.lean",
        "lakefile.toml",
        "asconfig.json",
        "bb.edn",
        "ballerina.toml",
        "bblayers.conf",
        "bicepconfig.json",
        "build",
        "build.bazel",
        "bender.yaml",
        "bender.yml",
        "bower.json",
        "build.pl",
        "brownie-config.yaml",
        "brownie-config.yml",
        "cpanfile",
        "description",
        "dockerfile",
        "namespace",
        "package.json",
        "package.dhall",
        "tsconfig.json",
        "jsconfig.json",
        "pyproject.toml",
        "pubspec.yaml",
        "dbt_project.yml",
        "dbt_project.yaml",
        "deps.edn",
        "package.yaml",
        "project.toml",
        "manifest.toml",
        "move.toml",
        "moon.mod",
        "moon.pkg",
        "qmldir",
        "qmake.conf",
        "qsharp.json",
        "containerfile",
        "alire.toml",
        "shard.yml",
        "cargo.toml",
        "go.mod",
        "iproj.json",
        "pom.xml",
        "project.clj",
        "build.sbt",
        "build.sc",
        "build.mill",
        "cask",
        "cakefile",
        "dune",
        "dune-project",
        "cabal.project",
        "cmakelists.txt",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "sfdx-project.json",
        "layer.conf",
        "local.conf",
        ".latexmkrc",
        "latexmkrc",
        "mix.exs",
        "erlang.mk",
        "fpm.toml",
        "foundry.toml",
        "dub.json",
        "dub.sdl",
        "hardhat.config.cjs",
        "hardhat.config.js",
        "hardhat.config.mjs",
        "hardhat.config.ts",
        "rebar.config",
        "remappings.txt",
        "composer.json",
        "dist.ini",
        "elm.json",
        "info.rkt",
        "project.xml",
        "package.scm",
        "flake.nix",
        "gleam.toml",
        ".hhconfig",
        "default.nix",
        "hhvm.autoload",
        "hh_autoload.json",
        "module.bazel",
        "shell.nix",
        "tectonic.toml",
        "texmf.cnf",
        "v.mod",
        "gemfile",
        "makefile.pl",
        "mason.toml",
        "config.nims",
        "nim.cfg",
        "package.swift",
        "puppetfile",
        "meta6.json",
        "modulefile",
        "bsconfig.json",
        "rescript.json",
        "default.project.json",
        "shadow-cljs.edn",
        "spago.dhall",
        "spago.yaml",
        "stack.yaml",
        "sqlproj",
        "wally.toml",
        "build.zig",
        "meson.build",
        "truffle-config.js",
        "truffle.js",
        "project.godot",
        "project.janet",
        "ipkg",
        "dbproj",
        "vhdl_ls.toml",
        "pacletinfo.m",
        "pacletinfo.wl",
        "workspace",
        "workspace.bazel",
    }
)
_NON_OPERATIONAL_PROFILE_PATH_PARTS = frozenset(
    {
        "benchmark",
        "benchmarks",
        "bench",
        "buildsrc",
        "doc",
        "docs",
        "documentation",
        "docsrc",
        "demos",
        "examples",
        "features",
        "fixtures",
        "fuzz",
        "fuzzer",
        "fuzzers",
        "fuzzing",
        "samples",
        "specs",
        "tutorial",
        "tutorials",
        "resource",
        "resources",
        "static",
        "test",
        "tests",
        "vignette",
        "vignettes",
    }
)
_NAMESPACE_PACKAGE_TOKENS = frozenset({"example", "examples", "sample", "samples"})
_DOCUMENTATION_PRIMARY_ECOSYSTEMS = frozenset({"rst", "tex", "typst", "asciidoc", "org"})
_DOCUMENTATION_OPERATIONAL_PATH_PARTS = frozenset(
    {
        "doc",
        "docs",
        "documentation",
        "docsrc",
        "demos",
        "examples",
        "samples",
        "tutorial",
        "tutorials",
        "vignette",
        "vignettes",
    }
)
_EXAMPLE_PRIMARY_ECOSYSTEMS = frozenset({"cue", "opencl", "answer set programming"})
_EXAMPLE_OPERATIONAL_PATH_PARTS = frozenset(
    {
        "demos",
        "examples",
        "samples",
        "tutorial",
        "tutorials",
    }
)
_SCENARIO_PRIMARY_ECOSYSTEMS = frozenset({"gherkin"})
_SCENARIO_OPERATIONAL_PATH_PARTS = frozenset({"features", "specs"})
_NON_OPERATIONAL_PROJECT_PATH_PARTS = frozenset(
    set(_NON_OPERATIONAL_PROFILE_PATH_PARTS) | {"doc", "docs", "documentation"}
)
_C_FAMILY_SOURCE_TOKEN_RE = re.compile(
    r"(?P<path>[A-Za-z0-9_./+-]+\.(?:asm|c|cc|cpp|cxx|m|mm|s|h|hh|hpp|hxx|ipp|tpp))"
)
_ML_MANIFEST_PATH_RE = re.compile(
    r"(?P<path>[A-Za-z0-9_./+-]+\.(?:cm|fun|mlb|sig|sml))",
    re.IGNORECASE,
)
_SYSTEMVERILOG_MANIFEST_PATH_RE = re.compile(
    r"(?P<path>[A-Za-z0-9_./+-]+\.(?:sv|svh|v|vh))",
    re.IGNORECASE,
)
_GDSCRIPT_RESOURCE_RE = re.compile(r"res://(?P<path>[^\"'\s]+)", re.IGNORECASE)
_GDSCRIPT_SCENE_SCRIPT_RE = re.compile(
    r'\[ext_resource\s+type="Script"[^]]*path="(?P<path>res://[^"]+\.gd)"',
    re.IGNORECASE,
)
_ML_SOURCE_EXTENSIONS = (".sml", ".sig", ".fun")
_ZIG_SOURCE_TOKEN_RE = re.compile(r"(?P<path>[A-Za-z0-9_./+-]+\.zig)")
_HASKELL_SOURCE_EXTENSIONS = (".hs", ".hsc", ".lhs")
_CLOJURE_QUOTED_STRING_RE = re.compile(r'"(?P<value>[^"]+)"')
_CLOJURE_VECTOR_FIELD_RE = re.compile(
    r"(?P<field>:[A-Za-z0-9_-]+)\s*\[(?P<body>.*?)\]",
    re.DOTALL,
)
_CLOJURE_MAIN_RE = re.compile(r":main\s+(?P<target>[A-Za-z][A-Za-z0-9_.-]*)")
_LUA_ROCKSPEC_MODULE_RE = re.compile(
    r"\[\s*[\"'](?P<name>[^\"']+)[\"']\s*\]\s*=\s*[\"'](?P<path>[^\"']+\.lua)[\"']"
)
_LUA_ROCKSPEC_PACKAGE_RE = re.compile(r"package\s*=\s*[\"'](?P<name>[^\"']+)[\"']")
_CRYSTAL_SHARD_NAME_RE = re.compile(
    r"^\s*name:\s*(?P<name>[A-Za-z0-9_.-]+)\s*$",
    re.MULTILINE,
)
_CRYSTAL_SHARD_MAIN_RE = re.compile(
    r"^\s*main:\s*(?P<path>[^\s#]+)\s*$",
    re.MULTILINE,
)
_ADA_PROJECT_FIELD_RE = re.compile(
    r"\bfor\s+(?P<field>source_dirs|main|source_files)\s+use\s+(?P<body>\(.*?\)|\"[^\"]+\")\s*;",
    re.IGNORECASE | re.DOTALL,
)
_TEMPLATE_SURFACE_ECOSYSTEMS = frozenset(
    {
        "astro",
        "blade",
        "erb",
        "ejs",
        "haml",
        "handlebars",
        "jinja",
        "liquid",
        "mustache",
        "nunjucks",
        "pug",
        "slim",
        "svelte",
        "twig",
        "vue",
    }
)
_TEMPLATE_SURFACE_PARTS = frozenset(
    {"views", "templates", "layouts", "partials", "shared", "components"}
)
