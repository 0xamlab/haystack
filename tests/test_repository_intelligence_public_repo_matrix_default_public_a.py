"""Tests for test_repository_intelligence_public_repo_matrix: default_public_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-3/tests/test_repository_intelligence_public_repo_matrix.py during modularization.
"""
from __future__ import annotations

from collections import Counter

from apps.api_server.services.repository_language_priority import supported_repository_languages

from tests._test_repository_intelligence_public_repo_matrix_helpers import *  # noqa: F401,F403


def test_default_public_repository_cases_include_top_rank_variants() -> None:
    urls_by_language = {
        language: {
            case.repository_url
            for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
            if case.language == language
        }
        for language in (
            "typescript",
            "python",
            "javascript",
            "vue",
            "svelte",
            "astro",
            "java",
            "cs",
            "php",
            "shell",
            "fish",
            "c",
            "dockerfile",
            "cpp",
            "cuda",
            "go",
            "rust",
        )
    }

    assert urls_by_language["typescript"] == {
        "https://github.com/sindresorhus/ky.git",
        "https://github.com/sindresorhus/type-fest.git",
    }
    assert urls_by_language["python"] == {
        "https://github.com/pallets/click.git",
        "https://github.com/psf/requests.git",
    }
    assert urls_by_language["javascript"] == {
        "https://github.com/expressjs/express.git",
        "https://github.com/lodash/lodash.git",
    }
    assert urls_by_language["vue"] == {
        "https://github.com/coreui/coreui-free-vue-admin-template.git",
        "https://github.com/vuejs/pinia.git",
    }
    assert urls_by_language["svelte"] == {
        "https://github.com/sveltejs/realworld.git",
        "https://github.com/sveltejs/svelte.dev.git",
    }
    assert urls_by_language["astro"] == {
        "https://github.com/withastro/astro.build.git",
        "https://github.com/withastro/starlight.git",
    }
    assert urls_by_language["java"] == {
        "https://github.com/google/gson.git",
        "https://github.com/square/okhttp.git",
    }
    assert urls_by_language["cs"] == {
        "https://github.com/dotnet/command-line-api.git",
        "https://github.com/dotnet/BenchmarkDotNet.git",
    }
    assert urls_by_language["php"] == {
        "https://github.com/Seldaek/monolog.git",
        "https://github.com/laravel/framework.git",
    }
    assert urls_by_language["shell"] == {
        "https://github.com/ohmyzsh/ohmyzsh.git",
        "https://github.com/tmux-plugins/tpm.git",
    }
    assert urls_by_language["fish"] == {
        "https://github.com/jorgebucaran/fisher.git",
        "https://github.com/PatrickF1/fzf.fish.git",
    }
    assert urls_by_language["c"] == {
        "https://github.com/tmux/tmux.git",
        "https://github.com/libgit2/libgit2.git",
    }
    assert urls_by_language["dockerfile"] == {
        "https://github.com/jessfraz/dockerfiles.git",
        "https://github.com/docker-library/hello-world.git",
    }
    assert urls_by_language["cpp"] == {
        "https://github.com/progschj/ThreadPool.git",
        "https://github.com/fmtlib/fmt.git",
    }
    assert urls_by_language["cuda"] == {
        "https://github.com/NVIDIA/cuda-samples.git",
        "https://github.com/NVIDIA/CUDALibrarySamples.git",
    }
    assert urls_by_language["go"] == {
        "https://github.com/spf13/cobra.git",
        "https://github.com/gin-gonic/gin.git",
    }
    assert urls_by_language["rust"] == {
        "https://github.com/sharkdp/fd.git",
        "https://github.com/BurntSushi/ripgrep.git",
    }


def test_default_public_repository_cases_keep_variant_depth_distinct_from_language_count() -> None:
    language_counts = Counter(
        case.language for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
    )

    assert language_counts["typescript"] == 2
    assert language_counts["python"] == 2
    assert language_counts["javascript"] == 2
    assert language_counts["vue"] == 2
    assert language_counts["svelte"] == 2
    assert language_counts["astro"] == 2
    assert language_counts["java"] == 2
    assert language_counts["cs"] == 2
    assert language_counts["php"] == 2
    assert language_counts["shell"] == 2
    assert language_counts["fish"] == 2
    assert language_counts["c"] == 2
    assert language_counts["dockerfile"] == 2
    assert language_counts["cpp"] == 2
    assert language_counts["cuda"] == 2
    assert language_counts["go"] == 2
    assert language_counts["rust"] == 2
    assert language_counts["kotlin"] == 2
    assert language_counts["scala"] == 2
    assert language_counts["dart"] == 2
    assert language_counts["groovy"] == 2
    assert language_counts["ampl"] == 1
    assert language_counts["openedge"] == 1
    assert language_counts["processing"] == 1
    assert language_counts["nsis"] == 1
    assert language_counts["lua"] == 2
    assert language_counts["elixir"] == 2
    assert language_counts["qsharp"] == 2
    assert language_counts["circom"] == 2
    assert language_counts["prolog"] == 2
    assert language_counts["slim"] == 2
    assert language_counts["smarty"] == 2
    assert language_counts["delphi"] == 2
    assert language_counts["nextflow"] == 2
    assert language_counts["robotframework"] == 2
    assert language_counts["typst"] == 2
    assert language_counts["lisp"] == 2
    assert len(public_repo_matrix.configured_public_repository_case_languages()) == len(
        supported_repository_languages()
    )


def test_default_public_repository_cases_include_dockerfile() -> None:
    dockerfile_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "dockerfile"
    )

    assert dockerfile_case.repository_url == "https://github.com/jessfraz/dockerfiles.git"
    assert dockerfile_case.expected_primary_ecosystem == "dockerfile"


def test_default_public_repository_cases_include_cuda() -> None:
    cuda_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "cuda"
    )

    assert cuda_case.repository_url == "https://github.com/NVIDIA/cuda-samples.git"
    assert cuda_case.expected_primary_ecosystem == "cuda"


def test_default_public_repository_cases_include_opencl() -> None:
    opencl_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "opencl"
    ]

    assert [case.repository_url for case in opencl_cases] == [
        "https://github.com/bgaster/opencl-book-samples.git",
        "https://github.com/KhronosGroup/OpenCL-SDK.git",
    ]
    assert all(case.expected_primary_ecosystem == "opencl" for case in opencl_cases)


def test_default_public_repository_cases_include_dm() -> None:
    dm_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "dm"
    )

    assert dm_case.repository_url == "https://github.com/BurgerLUA/burgerstation.git"
    assert dm_case.expected_primary_ecosystem == "dm"


def test_default_public_repository_cases_include_metal() -> None:
    metal_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "metal"
    )

    assert metal_case.repository_url == "https://github.com/twostraws/Inferno.git"
    assert metal_case.expected_primary_ecosystem == "metal"
    assert metal_case.focus_paths == ("Sources/Inferno/Shaders",)


def test_default_public_repository_cases_include_bqn() -> None:
    bqn_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "bqn"
    )

    assert bqn_case.repository_url == "https://github.com/mlochbaum/bqn-libs.git"
    assert bqn_case.expected_primary_ecosystem == "bqn"


def test_default_public_repository_cases_include_rebol() -> None:
    rebol_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "rebol"
    )

    assert rebol_case.repository_url == "https://github.com/gchiu/Rebol3.git"
    assert rebol_case.expected_primary_ecosystem == "rebol"


def test_default_public_repository_cases_include_cpp() -> None:
    cpp_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "cpp"
    )

    assert cpp_case.repository_url == "https://github.com/progschj/ThreadPool.git"
    assert cpp_case.expected_primary_ecosystem == "cpp"


def test_default_public_repository_cases_include_hlsl() -> None:
    hlsl_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "hlsl"
    )

    assert hlsl_case.repository_url == "https://github.com/crosire/reshade-shaders.git"
    assert hlsl_case.expected_primary_ecosystem == "hlsl"


def test_default_public_repository_cases_include_wgsl() -> None:
    wgsl_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "wgsl"
    )

    assert wgsl_case.repository_url == "https://github.com/alphastrata/shadplay.git"
    assert wgsl_case.expected_primary_ecosystem == "wgsl"


def test_default_public_repository_cases_include_svelte() -> None:
    svelte_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "svelte"
    )

    assert svelte_case.repository_url == "https://github.com/sveltejs/realworld.git"
    assert svelte_case.expected_primary_ecosystem == "svelte"


def test_default_public_repository_cases_include_astro() -> None:
    astro_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "astro"
    )

    assert astro_case.repository_url == "https://github.com/withastro/astro.build.git"
    assert astro_case.expected_primary_ecosystem == "astro"


def test_default_public_repository_cases_include_php() -> None:
    php_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "php"
    )

    assert php_case.repository_url == "https://github.com/Seldaek/monolog.git"
    assert php_case.expected_primary_ecosystem == "php"


def test_default_public_repository_cases_include_pug() -> None:
    pug_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "pug"
    ]

    assert [case.repository_url for case in pug_cases] == [
        "https://github.com/StartBootstrap/startbootstrap-sb-admin.git",
        "https://github.com/StartBootstrap/startbootstrap-freelancer.git",
    ]
    assert all(case.expected_primary_ecosystem == "pug" for case in pug_cases)


def test_default_public_repository_cases_include_ejs() -> None:
    ejs_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "ejs"
    ]

    assert [case.repository_url for case in ejs_cases] == [
        "https://github.com/jaywcjlove/github-rank.git",
        "https://github.com/mde/ejs.git",
    ]
    assert all(case.expected_primary_ecosystem == "ejs" for case in ejs_cases)


def test_default_public_repository_cases_include_blade() -> None:
    blade_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "blade"
    ]

    assert [case.repository_url for case in blade_cases] == [
        "https://github.com/laravel/laravel.git",
    ]
    assert all(case.expected_primary_ecosystem == "blade" for case in blade_cases)


def test_default_public_repository_cases_include_erb() -> None:
    erb_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "erb"
    ]

    assert [case.repository_url for case in erb_cases] == [
        "https://github.com/redmine/redmine.git",
        "https://github.com/coskuntekin/middleman_starter_kit.git",
    ]
    assert all(case.expected_primary_ecosystem == "erb" for case in erb_cases)


def test_default_public_repository_cases_include_mustache() -> None:
    mustache_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "mustache"
    ]

    assert [case.repository_url for case in mustache_cases] == [
        "https://github.com/janl/mustache.js.git",
        "https://github.com/swagger-api/swagger-codegen.git",
    ]
    assert all(case.expected_primary_ecosystem == "mustache" for case in mustache_cases)


def test_default_public_repository_cases_include_smarty() -> None:
    smarty_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "smarty"
    ]

    assert [case.repository_url for case in smarty_cases] == [
        "https://github.com/prestashop/classic-theme.git",
        "https://github.com/smarty-php/smarty.git",
    ]
    assert all(case.expected_primary_ecosystem == "smarty" for case in smarty_cases)


def test_default_public_repository_cases_include_graphviz() -> None:
    graphviz_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "graphviz"
    )

    assert graphviz_case.repository_url == "https://github.com/abruzzi/graphviz-scripts.git"
    assert graphviz_case.expected_primary_ecosystem == "graphviz"


def test_default_public_repository_cases_include_mermaid() -> None:
    mermaid_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "mermaid"
    )

    assert mermaid_case.repository_url == "https://github.com/mermaid-js/mermaid-cli.git"
    assert mermaid_case.expected_primary_ecosystem == "mermaid"


def test_default_public_repository_cases_include_plantuml() -> None:
    plantuml_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "plantuml"
    )

    assert plantuml_case.repository_url == "https://github.com/plantuml-stdlib/C4-PlantUML.git"
    assert plantuml_case.expected_primary_ecosystem == "plantuml"


def test_default_public_repository_cases_include_openqasm() -> None:
    openqasm_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "openqasm"
    )

    assert openqasm_case.repository_url == "https://github.com/pnnl/QASMBench.git"
    assert openqasm_case.expected_primary_ecosystem == "openqasm"


def test_default_public_repository_cases_include_xslt() -> None:
    xslt_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "xslt"
    )

    assert xslt_case.repository_url == "https://github.com/docbook/xslt20-stylesheets.git"
    assert xslt_case.expected_primary_ecosystem == "xslt"
    assert xslt_case.focus_paths == ()


def test_default_public_repository_cases_include_4d() -> None:
    four_d_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "4d"
    ]

    assert [case.repository_url for case in four_d_cases] == [
        "https://github.com/4d/4D-NetKit.git",
        "https://github.com/4d/Build4D.git",
    ]
    assert all(case.expected_primary_ecosystem == "4d" for case in four_d_cases)
    assert four_d_cases[0].focus_paths == ("Project/Sources",)
    assert four_d_cases[1].focus_paths == ()


def test_default_public_repository_cases_include_moonbit() -> None:
    moonbit_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "moonbit"
    )

    assert moonbit_case.repository_url == "https://github.com/moonbitlang/core.git"
    assert moonbit_case.expected_primary_ecosystem == "moonbit"


def test_default_public_repository_cases_include_roc() -> None:
    roc_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "roc"
    )

    assert roc_case.repository_url == "https://github.com/roc-lang/book-of-examples.git"
    assert roc_case.expected_primary_ecosystem == "roc"


def test_default_public_repository_cases_include_modelica() -> None:
    modelica_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "modelica"
    )

    assert (
        modelica_case.repository_url
        == "https://github.com/modelica/ModelicaStandardLibrary.git"
    )
    assert modelica_case.expected_primary_ecosystem == "modelica"


def test_default_public_repository_cases_include_hy() -> None:
    hy_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "hy"
    )

    assert hy_case.repository_url == "https://github.com/hylang/hydiomatic.git"
    assert hy_case.expected_primary_ecosystem == "hy"


def test_default_public_repository_cases_include_wren() -> None:
    wren_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "wren"
    )

    assert wren_case.repository_url == "https://github.com/exercism/wren.git"
    assert wren_case.expected_primary_ecosystem == "wren"


def test_default_public_repository_cases_include_fennel() -> None:
    fennel_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "fennel"
    )

    assert fennel_case.repository_url == "https://github.com/bakpakin/Fennel.git"
    assert fennel_case.expected_primary_ecosystem == "fennel"


def test_default_public_repository_cases_include_nextflow() -> None:
    nextflow_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "nextflow"
    ]

    assert [case.repository_url for case in nextflow_cases] == [
        "https://github.com/nf-core/rnaseq.git",
        "https://github.com/nf-core/atacseq.git",
    ]
    assert all(case.expected_primary_ecosystem == "nextflow" for case in nextflow_cases)


def test_default_public_repository_cases_include_processing() -> None:
    processing_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "processing"
    )

    assert (
        processing_case.repository_url
        == "https://github.com/processing/processing-examples.git"
    )
    assert processing_case.expected_primary_ecosystem == "processing"


def test_default_public_repository_cases_include_ampl() -> None:
    ampl_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "ampl"
    )

    assert ampl_case.repository_url == "https://github.com/ampl/ampl.github.io.git"
    assert ampl_case.expected_primary_ecosystem == "ampl"
    assert ampl_case.focus_paths == ("models",)


def test_default_public_repository_cases_include_openedge() -> None:
    openedge_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "openedge"
    )

    assert openedge_case.repository_url == "https://github.com/CameronWills/OEUnit.git"
    assert openedge_case.expected_primary_ecosystem == "openedge"
    assert openedge_case.focus_paths == ("src/OEUnit",)


def test_default_public_repository_cases_include_nsis() -> None:
    nsis_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "nsis"
    )

    assert nsis_case.repository_url == "https://github.com/bmatzelle/gow.git"
    assert nsis_case.expected_primary_ecosystem == "nsis"


def test_default_public_repository_cases_include_nunjucks() -> None:
    nunjucks_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "nunjucks"
    ]
    assert [case.repository_url for case in nunjucks_cases] == [
        "https://github.com/11ty/eleventy-base-blog.git",
        "https://github.com/madrilene/eleventy-excellent.git",
    ]
    assert all(case.expected_primary_ecosystem == "nunjucks" for case in nunjucks_cases)


def test_default_public_repository_cases_include_twig() -> None:
    twig_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "twig"
    ]
    assert [case.repository_url for case in twig_cases] == [
        "https://github.com/timber/starter-theme.git",
        "https://github.com/symfony/web-profiler-bundle.git",
    ]
    assert all(case.expected_primary_ecosystem == "twig" for case in twig_cases)


def test_default_public_repository_cases_include_haml() -> None:
    haml_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "haml"
    ]
    assert [case.repository_url for case in haml_cases] == [
        "https://github.com/mpv-player/mpv.io.git",
        "https://github.com/olivierlacan/keep-a-changelog.git",
    ]
    assert all(case.expected_primary_ecosystem == "haml" for case in haml_cases)


def test_default_public_repository_cases_include_slim() -> None:
    slim_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "slim"
    ]
    assert [case.repository_url for case in slim_cases] == [
        "https://github.com/betagouv/rdv-service-public.git",
        "https://github.com/slim-template/slim.git",
    ]
    assert all(case.expected_primary_ecosystem == "slim" for case in slim_cases)


def test_default_public_repository_cases_include_ml_with_sml_runtime_surface() -> None:
    ml_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "ml"
    )
    assert ml_case.repository_url == "https://github.com/minoki/LunarML.git"
    assert ml_case.expected_primary_ecosystem == "sml"


def test_default_public_repository_cases_include_sass() -> None:
    sass_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "sass"
    ]
    assert [case.repository_url for case in sass_cases] == [
        "https://github.com/readthedocs/sphinx_rtd_theme.git",
        "https://github.com/pradyunsg/furo.git",
    ]
    assert all(case.expected_primary_ecosystem == "sass" for case in sass_cases)


def test_default_public_repository_cases_include_sml() -> None:
    sml_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "sml"
    )
    assert sml_case.repository_url == "https://github.com/SMLFamily/BasisLibrary.git"
    assert sml_case.expected_primary_ecosystem == "sml"


def test_default_public_repository_cases_include_vyper() -> None:
    vyper_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "vyper"
    )
    assert vyper_case.repository_url == "https://github.com/curvefi/tricrypto-ng.git"
    assert vyper_case.expected_primary_ecosystem == "vyper"


def test_default_public_repository_cases_include_qsharp() -> None:
    qsharp_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "qsharp"
    )
    assert qsharp_case.repository_url == "https://github.com/microsoft/QuantumLibraries.git"
    assert qsharp_case.expected_primary_ecosystem == "qsharp"


def test_default_public_repository_cases_include_clojurescript() -> None:
    clojurescript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "clojurescript"
    )
    assert clojurescript_case.repository_url == "https://github.com/reagent-project/reagent.git"
    assert clojurescript_case.expected_primary_ecosystem == "clojurescript"


def test_default_public_repository_cases_include_al() -> None:
    al_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "al"
    )
    assert al_case.repository_url == "https://github.com/microsoft/ALAppExtensions.git"
    assert al_case.expected_primary_ecosystem == "al"


def test_default_public_repository_cases_include_shaderlab() -> None:
    shaderlab_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "shaderlab"
    )

    assert shaderlab_case.repository_url == "https://github.com/poiyomi/PoiyomiToonShader.git"
    assert shaderlab_case.expected_primary_ecosystem == "shaderlab"


def test_default_public_repository_cases_include_rst() -> None:
    rst_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "rst"
    ]

    assert [case.repository_url for case in rst_cases] == [
        "https://github.com/godotengine/godot-docs.git",
        "https://github.com/python/peps.git",
    ]
    assert all(case.expected_primary_ecosystem == "rst" for case in rst_cases)


def test_default_public_repository_cases_include_asciidoc() -> None:
    asciidoc_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "asciidoc"
    ]

    assert [case.repository_url for case in asciidoc_cases] == [
        "https://github.com/cartabinaria/asciidoc-thesis.git",
        "https://github.com/lnbook/lnbook.git",
    ]
    assert all(case.expected_primary_ecosystem == "asciidoc" for case in asciidoc_cases)


def test_default_public_repository_cases_include_org() -> None:
    org_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "org"
    ]

    assert [case.repository_url for case in org_cases] == [
        "https://github.com/lujun9972/emacs-document.git",
        "https://github.com/tecosaur/emacs-config.git",
    ]
    assert all(case.expected_primary_ecosystem == "org" for case in org_cases)


def test_default_public_repository_cases_include_scratch() -> None:
    scratch_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "scratch"
    )

    assert scratch_case.repository_url == "https://github.com/https-sharif/Scratch-Game.git"
    assert scratch_case.expected_primary_ecosystem == "scratch"


def test_default_public_repository_cases_include_gml() -> None:
    gml_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "gml"
    )

    assert gml_case.repository_url == "https://github.com/Gizmo199/BehaviorTree.git"
    assert gml_case.expected_primary_ecosystem == "gml"


def test_default_public_repository_cases_include_makefile() -> None:
    makefile_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "makefile"
    )

    assert makefile_case.repository_url == "https://github.com/lindenb/makefile2graph.git"
    assert makefile_case.expected_primary_ecosystem == "makefile"


def test_default_public_repository_cases_include_cmake() -> None:
    cmake_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "cmake"
    ]

    assert [case.repository_url for case in cmake_cases] == [
        "https://github.com/ttroy50/cmake-examples.git",
        "https://github.com/pr0g/cmake-examples.git",
    ]
    assert all(case.expected_primary_ecosystem == "cmake" for case in cmake_cases)


def test_default_public_repository_cases_include_meson() -> None:
    meson_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "meson"
    ]

    assert [case.repository_url for case in meson_cases] == [
        "https://github.com/tiernemi/meson-sample-project.git",
        "https://github.com/frida/frida.git",
    ]
    assert all(case.expected_primary_ecosystem == "meson" for case in meson_cases)


def test_default_public_repository_cases_include_qmake() -> None:
    qmake_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "qmake"
    ]

    assert [case.repository_url for case in qmake_cases] == [
        "https://github.com/horsicq/XPEViewer.git",
        "https://github.com/codyps/qmake-protobuf-example.git",
    ]
    assert all(case.expected_primary_ecosystem == "qmake" for case in qmake_cases)


def test_default_public_repository_cases_include_qml() -> None:
    qml_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "qml"
    ]

    assert [case.repository_url for case in qml_cases] == [
        "https://github.com/Qt-QML/QmlFlightInstruments.git",
        "https://github.com/qmlbook/qmlbook.git",
    ]
    assert all(case.expected_primary_ecosystem == "qml" for case in qml_cases)


def test_default_public_repository_cases_include_vue() -> None:
    vue_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "vue"
    )

    assert vue_case.repository_url == "https://github.com/coreui/coreui-free-vue-admin-template.git"
    assert vue_case.expected_primary_ecosystem == "vue"


def test_default_public_repository_cases_include_less() -> None:
    less_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "less"
    ]

    assert [case.repository_url for case in less_cases] == [
        "https://github.com/jerrykuku/luci-theme-argon.git",
        "https://github.com/Remix-Design/RemixIcon.git",
    ]
    assert all(case.expected_primary_ecosystem == "less" for case in less_cases)


def test_default_public_repository_cases_include_stylus() -> None:
    stylus_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "stylus"
    ]

    assert [case.repository_url for case in stylus_cases] == [
        "https://github.com/theme-next/hexo-theme-next.git",
        "https://github.com/probberechts/hexo-theme-cactus.git",
    ]
    assert all(case.expected_primary_ecosystem == "stylus" for case in stylus_cases)


def test_default_public_repository_cases_include_cython() -> None:
    cython_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "cython"
    ]

    assert [case.repository_url for case in cython_cases] == [
        "https://github.com/strawlab/python-pcl.git",
        "https://github.com/cython/cython.git",
    ]
    assert all(case.expected_primary_ecosystem == "cython" for case in cython_cases)


def test_default_public_repository_cases_include_ruby() -> None:
    ruby_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "ruby"
    ]

    assert [case.repository_url for case in ruby_cases] == [
        "https://github.com/sinatra/sinatra.git",
        "https://github.com/rails/rails.git",
    ]
    assert all(case.expected_primary_ecosystem == "ruby" for case in ruby_cases)


def test_default_public_repository_cases_include_stan() -> None:
    stan_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "stan"
    )

    assert stan_case.repository_url == "https://github.com/stan-dev/example-models.git"
    assert stan_case.expected_primary_ecosystem == "stan"


def test_default_public_repository_cases_include_just() -> None:
    just_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "just"
    )

    assert just_case.repository_url == "https://github.com/ublue-os/image-template.git"
    assert just_case.expected_primary_ecosystem == "just"


def test_default_public_repository_cases_include_odin() -> None:
    odin_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "odin"
    )

    assert odin_case.repository_url == "https://github.com/odin-lang/examples.git"
    assert odin_case.expected_primary_ecosystem == "odin"


def test_default_public_repository_cases_include_factor() -> None:
    factor_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "factor"
    )

    assert factor_case.repository_url == "https://github.com/bjourne/playground-factor.git"
    assert factor_case.expected_primary_ecosystem == "factor"


def test_default_public_repository_cases_include_q() -> None:
    q_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "q"
    )

    assert q_case.repository_url == "https://github.com/DataIntellectTech/TorQ.git"
    assert q_case.expected_primary_ecosystem == "q"
    assert q_case.focus_paths == ("code", "config/settings")


def test_default_public_repository_cases_include_j() -> None:
    j_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "j"
    )

    assert j_case.repository_url == "https://github.com/jsoftware/base9.git"
    assert j_case.expected_primary_ecosystem == "j"


def test_default_public_repository_cases_include_cue() -> None:
    cue_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "cue"
    )

    assert cue_case.repository_url == "https://github.com/cue-labs/cue-by-example.git"
    assert cue_case.expected_primary_ecosystem == "cue"


def test_default_public_repository_cases_include_kotlin() -> None:
    kotlin_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "kotlin"
    )

    assert kotlin_case.repository_url == "https://github.com/square/kotlinpoet.git"
    assert kotlin_case.expected_primary_ecosystem == "kotlin"


def test_default_public_repository_cases_include_scss() -> None:
    scss_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "scss"
    ]

    assert [case.repository_url for case in scss_cases] == [
        "https://github.com/pages-themes/minimal.git",
        "https://github.com/IanLunn/Hover.git",
    ]
    assert all(case.expected_primary_ecosystem == "scss" for case in scss_cases)


def test_default_public_repository_cases_include_jinja() -> None:
    jinja_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "jinja"
    )

    assert jinja_case.repository_url == "https://github.com/netbootxyz/netboot.xyz.git"
    assert jinja_case.expected_primary_ecosystem == "jinja"


def test_default_public_repository_cases_include_liquid() -> None:
    liquid_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "liquid"
    ]

    assert [case.repository_url for case in liquid_cases] == [
        "https://github.com/Shopify/dawn.git",
        "https://github.com/uicrooks/shopify-foundation-theme.git",
    ]
    assert all(case.expected_primary_ecosystem == "liquid" for case in liquid_cases)


def test_default_public_repository_cases_include_handlebars() -> None:
    handlebars_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "handlebars"
    ]

    assert [case.repository_url for case in handlebars_cases] == [
        "https://github.com/TryGhost/Source.git",
        "https://github.com/TryGhost/Casper.git",
    ]
    assert all(case.expected_primary_ecosystem == "handlebars" for case in handlebars_cases)


def test_default_public_repository_cases_include_tex() -> None:
    tex_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "tex"
    ]

    assert [case.repository_url for case in tex_cases] == [
        "https://github.com/posquit0/Awesome-CV.git",
        "https://github.com/HarisIqbal88/PlotNeuralNet.git",
    ]
    assert all(case.expected_primary_ecosystem == "tex" for case in tex_cases)


def test_default_public_repository_cases_include_protobuf() -> None:
    protobuf_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "protobuf"
    ]

    assert [case.repository_url for case in protobuf_cases] == [
        "https://github.com/googleapis/api-common-protos.git",
        "https://github.com/googleapis/googleapis.git",
    ]
    assert all(case.expected_primary_ecosystem == "protobuf" for case in protobuf_cases)


def test_default_public_repository_cases_include_robotframework() -> None:
    robotframework_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "robotframework"
    ]

    assert [case.repository_url for case in robotframework_cases] == [
        "https://github.com/robotframework/WebDemo.git",
        "https://github.com/robotframework/RobotDemo.git",
    ]
    assert all(
        case.expected_primary_ecosystem == "robotframework" for case in robotframework_cases
    )


def test_default_public_repository_cases_include_gherkin() -> None:
    gherkin_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "gherkin"
    )

    assert (
        gherkin_case.repository_url == "https://github.com/FriendsOfBehat/SymfonyExtension.git"
    )
    assert gherkin_case.expected_primary_ecosystem == "gherkin"


def test_default_public_repository_cases_include_antlr() -> None:
    antlr_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "antlr"
    )

    assert antlr_case.repository_url == "https://github.com/drforr/perl6-ANTLR4.git"
    assert antlr_case.expected_primary_ecosystem == "antlr"


def test_default_public_repository_cases_include_move() -> None:
    move_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "move"
    )

    assert move_case.repository_url == "https://github.com/aave/aptos-aave-v3.git"
    assert move_case.expected_primary_ecosystem == "move"


def test_default_public_repository_cases_include_typst() -> None:
    typst_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "typst"
    ]

    assert [case.repository_url for case in typst_cases] == [
        "https://github.com/typst/packages.git",
        "https://github.com/typst/templates.git",
    ]
    assert all(case.expected_primary_ecosystem == "typst" for case in typst_cases)


def test_default_public_repository_cases_include_luau() -> None:
    luau_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "luau"
    )

    assert luau_case.repository_url == "https://github.com/Ukendio/jecs.git"
    assert luau_case.expected_primary_ecosystem == "luau"


def test_default_public_repository_cases_include_awk() -> None:
    awk_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "awk"
    )

    assert awk_case.repository_url == "https://github.com/step-/JSON.awk.git"
    assert awk_case.expected_primary_ecosystem == "awk"


def test_default_public_repository_cases_include_autohotkey() -> None:
    autohotkey_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "autohotkey"
    )

    assert autohotkey_case.repository_url == "https://github.com/thqby/ahk2_lib.git"
    assert autohotkey_case.expected_primary_ecosystem == "autohotkey"


def test_default_public_repository_cases_include_autoit() -> None:
    autoit_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "autoit"
    )

    assert autoit_case.repository_url == "https://github.com/rcmaehl/WhyNotWin11.git"
    assert autoit_case.expected_primary_ecosystem == "autoit"


def test_default_public_repository_cases_include_squirrel() -> None:
    squirrel_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "squirrel"
    )

    assert squirrel_case.repository_url == "https://github.com/p2r3/HTTPortal.git"
    assert squirrel_case.expected_primary_ecosystem == "squirrel"


def test_default_public_repository_cases_include_v() -> None:
    v_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "v"
    )

    assert v_case.repository_url == "https://github.com/vlang/ui.git"
    assert v_case.expected_primary_ecosystem == "v"


def test_default_public_repository_cases_include_coffeescript() -> None:
    coffeescript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "coffeescript"
    )

    assert coffeescript_case.repository_url == "https://github.com/jashkenas/coffeescript.git"
    assert coffeescript_case.expected_primary_ecosystem == "coffeescript"


def test_default_public_repository_cases_include_verilog() -> None:
    verilog_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "verilog"
    )

    assert verilog_case.repository_url == "https://github.com/TimRudy/uart-verilog.git"
    assert verilog_case.expected_primary_ecosystem == "verilog"


def test_default_public_repository_cases_include_vala() -> None:
    vala_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "vala"
    )

    assert vala_case.repository_url == "https://github.com/GNOME/vala.git"
    assert vala_case.expected_primary_ecosystem == "vala"


def test_default_public_repository_cases_include_smalltalk() -> None:
    smalltalk_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "smalltalk"
    )

    assert smalltalk_case.repository_url == "https://github.com/pharo-spec/Spec.git"
    assert smalltalk_case.expected_primary_ecosystem == "smalltalk"


def test_default_public_repository_cases_include_visualbasic() -> None:
    visualbasic_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "visualbasic"
    )

    assert visualbasic_case.repository_url == "https://github.com/kimmknight/remoteapptool.git"
    assert visualbasic_case.expected_primary_ecosystem == "visualbasic"


def test_default_public_repository_cases_include_mql5() -> None:
    mql5_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "mql5"
    )

    assert mql5_case.repository_url == "https://github.com/geraked/metatrader5.git"
    assert mql5_case.expected_primary_ecosystem == "mql5"


def test_default_public_repository_cases_include_gams() -> None:
    gams_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "gams"
    )

    assert gams_case.repository_url == "https://github.com/psztorc/DICE.git"
    assert gams_case.expected_primary_ecosystem == "gams"


def test_default_public_repository_cases_include_nix() -> None:
    nix_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "nix"
    )

    assert nix_case.repository_url == "https://github.com/numtide/flake-utils.git"
    assert nix_case.expected_primary_ecosystem == "nix"


def test_default_public_repository_cases_include_starlark() -> None:
    starlark_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "starlark"
    )

    assert (
        starlark_case.repository_url
        == "https://github.com/bazelbuild/bazel-skylib.git"
    )
    assert starlark_case.expected_primary_ecosystem == "starlark"


def test_default_public_repository_cases_include_rego() -> None:
    rego_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "rego"
    )

    assert rego_case.repository_url == "https://github.com/open-policy-agent/library.git"
    assert rego_case.expected_primary_ecosystem == "rego"


def test_default_public_repository_cases_include_yara() -> None:
    yara_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "yara"
    )

    assert yara_case.repository_url == "https://github.com/YARA-Rules/rules.git"
    assert yara_case.expected_primary_ecosystem == "yara"


def test_default_public_repository_cases_include_hcl() -> None:
    hcl_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "hcl"
    )

    assert hcl_case.repository_url == "https://github.com/terraform-aws-modules/terraform-aws-vpc.git"
    assert hcl_case.expected_primary_ecosystem == "hcl"


def test_default_public_repository_cases_include_hack() -> None:
    hack_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "hack"
    ]

    assert [case.repository_url for case in hack_cases] == [
        "https://github.com/hhvm/hsl.git",
        "https://github.com/hhvm/xhp-lib.git",
    ]
    assert all(case.expected_primary_ecosystem == "hack" for case in hack_cases)


def test_default_public_repository_cases_include_glsl() -> None:
    glsl_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "glsl"
    )

    assert glsl_case.repository_url == "https://github.com/ashima/webgl-noise.git"
    assert glsl_case.expected_primary_ecosystem == "glsl"


def test_default_public_repository_cases_include_coq() -> None:
    coq_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "coq"
    )

    assert coq_case.repository_url == "https://github.com/coq-community/coq-art.git"
    assert coq_case.expected_primary_ecosystem == "coq"


def test_default_public_repository_cases_include_lean() -> None:
    lean_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "lean"
    )

    assert lean_case.repository_url == "https://github.com/leanprover-community/batteries.git"
    assert lean_case.expected_primary_ecosystem == "lean"


def test_default_public_repository_cases_include_batchfile() -> None:
    batchfile_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "batchfile"
    )

    assert batchfile_case.repository_url == "https://github.com/npocmaka/batch.scripts.git"
    assert batchfile_case.expected_primary_ecosystem == "batchfile"


def test_default_public_repository_cases_include_eiffel() -> None:
    eiffel_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "eiffel"
    ]

    assert [case.repository_url for case in eiffel_cases] == [
        "https://github.com/ttencate/aoc2017.git",
        "https://github.com/gobo-eiffel/gobo.git",
    ]
    assert all(case.expected_primary_ecosystem == "eiffel" for case in eiffel_cases)


def test_default_public_repository_cases_include_tlaplus() -> None:
    tlaplus_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "tlaplus"
    )

    assert tlaplus_case.repository_url == "https://github.com/tlaplus/Examples.git"
    assert tlaplus_case.expected_primary_ecosystem == "tlaplus"


def test_default_public_repository_cases_include_logtalk() -> None:
    logtalk_cases = [
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "logtalk"
    ]

    assert [case.repository_url for case in logtalk_cases] == [
        "https://github.com/LogtalkDotOrg/talkshow.git",
        "https://github.com/LogtalkDotOrg/logtalk3.git",
    ]
    assert all(case.expected_primary_ecosystem == "logtalk" for case in logtalk_cases)


def test_default_public_repository_cases_include_ocaml() -> None:
    ocaml_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "ocaml"
    )

    assert ocaml_case.repository_url == "https://github.com/ocaml-community/utop.git"
    assert ocaml_case.expected_primary_ecosystem == "ocaml"
