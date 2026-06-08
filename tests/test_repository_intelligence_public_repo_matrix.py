from __future__ import annotations

from pathlib import Path

import pytest

import benchmarks.repository_intelligence_public_repo_matrix as public_repo_matrix


def test_ordered_public_repository_cases_respects_global_rank() -> None:
    cases = (
        public_repo_matrix.PublicRepositoryCase(
            language="zig",
            repository_url="https://github.com/zigtools/zls.git",
            expected_primary_ecosystem="zig",
        ),
        public_repo_matrix.PublicRepositoryCase(
            language="python",
            repository_url="https://github.com/pallets/click.git",
            expected_primary_ecosystem="python",
        ),
        public_repo_matrix.PublicRepositoryCase(
            language="dart",
            repository_url="https://github.com/dart-lang/http.git",
            expected_primary_ecosystem="dart",
        ),
    )

    ordered_cases = public_repo_matrix.ordered_public_repository_cases(cases=cases)

    assert [case.language for case in ordered_cases] == ["python", "dart", "zig"]


def test_run_public_repository_seed_plan_case_uses_operational_primary_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="dart",
        repository_url="https://github.com/dart-lang/http.git",
        expected_primary_ecosystem="dart",
    )
    repo_path = tmp_path / "dart-http"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix,
        "clone_public_repository_case",
        lambda *_args, **_kwargs: repo_path,
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_derive_operational_seed_plan_without_diagnostics",
        lambda **_kwargs: {
            "candidate_file_paths": ["pkgs/http/lib/http.dart"],
            "entrypoint_files": ["pkgs/http/lib/http.dart"],
            "support_roots": ["pkgs/http/lib"],
            "config_paths": ["pkgs/http/pubspec.yaml"],
            "detected_ecosystems": ["java", "cpp", "dart", "groovy"],
            "operational_ecosystems": ["dart", "java", "cpp", "groovy"],
        },
    )

    result = public_repo_matrix.run_public_repository_seed_plan_case(
        case,
        checkout_root=tmp_path,
    )

    assert result["primary_detected_ecosystem"] == "java"
    assert result["primary_operational_ecosystem"] == "dart"
    assert result["primary_ecosystem"] == "dart"
    assert result["primary_match"] is True


def test_run_public_repository_matrix_reports_real_language_progress(tmp_path: Path) -> None:
    result = public_repo_matrix.run_public_repository_matrix(
        mode="seed_plan",
        checkout_root=tmp_path,
        runtime_root=tmp_path,
        limit=0,
        ranked_target_language_count=200,
    )

    assert result["case_count"] == 0
    assert result["support_progress"]["supported_real_language_count"] == 172
    assert result["support_progress"]["ranked_target_language_count"] == 200
    assert result["support_progress"]["progress_label"] == "172 / 200"
    assert result["support_progress"]["progress_fraction"] == pytest.approx(172 / 200)


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


def test_default_public_repository_cases_include_pug() -> None:
    pug_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "pug"
    )

    assert pug_case.repository_url == "https://github.com/StartBootstrap/startbootstrap-sb-admin.git"
    assert pug_case.expected_primary_ecosystem == "pug"


def test_default_public_repository_cases_include_ejs() -> None:
    ejs_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "ejs"
    )

    assert ejs_case.repository_url == "https://github.com/jaywcjlove/github-rank.git"
    assert ejs_case.expected_primary_ecosystem == "ejs"


def test_default_public_repository_cases_include_blade() -> None:
    blade_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "blade"
    )

    assert blade_case.repository_url == "https://github.com/thedevdojo/genesis.git"
    assert blade_case.expected_primary_ecosystem == "blade"


def test_default_public_repository_cases_include_erb() -> None:
    erb_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "erb"
    )

    assert erb_case.repository_url == "https://github.com/redmine/redmine.git"
    assert erb_case.expected_primary_ecosystem == "erb"


def test_default_public_repository_cases_include_mustache() -> None:
    mustache_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "mustache"
    )

    assert mustache_case.repository_url == "https://github.com/janl/mustache.js.git"
    assert mustache_case.expected_primary_ecosystem == "mustache"


def test_default_public_repository_cases_include_smarty() -> None:
    smarty_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "smarty"
    )

    assert smarty_case.repository_url == "https://github.com/prestashop/classic-theme.git"
    assert smarty_case.expected_primary_ecosystem == "smarty"


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
    nextflow_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "nextflow"
    )

    assert nextflow_case.repository_url == "https://github.com/nf-core/rnaseq.git"
    assert nextflow_case.expected_primary_ecosystem == "nextflow"


def test_default_public_repository_cases_include_nunjucks() -> None:
    nunjucks_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "nunjucks"
    )
    assert nunjucks_case.repository_url == "https://github.com/11ty/eleventy-base-blog.git"
    assert nunjucks_case.expected_primary_ecosystem == "nunjucks"


def test_default_public_repository_cases_include_twig() -> None:
    twig_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "twig"
    )
    assert twig_case.repository_url == "https://github.com/timber/starter-theme.git"
    assert twig_case.expected_primary_ecosystem == "twig"


def test_default_public_repository_cases_include_haml() -> None:
    haml_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "haml"
    )
    assert haml_case.repository_url == "https://github.com/mpv-player/mpv.io.git"
    assert haml_case.expected_primary_ecosystem == "haml"


def test_default_public_repository_cases_include_slim() -> None:
    slim_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "slim"
    )
    assert slim_case.repository_url == "https://github.com/betagouv/rdv-service-public.git"
    assert slim_case.expected_primary_ecosystem == "slim"


def test_default_public_repository_cases_include_shaderlab() -> None:
    shaderlab_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "shaderlab"
    )

    assert shaderlab_case.repository_url == "https://github.com/poiyomi/PoiyomiToonShader.git"
    assert shaderlab_case.expected_primary_ecosystem == "shaderlab"


def test_default_public_repository_cases_include_rst() -> None:
    rst_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "rst"
    )

    assert rst_case.repository_url == "https://github.com/godotengine/godot-docs.git"
    assert rst_case.expected_primary_ecosystem == "rst"


def test_default_public_repository_cases_include_asciidoc() -> None:
    asciidoc_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "asciidoc"
    )

    assert asciidoc_case.repository_url == "https://github.com/cartabinaria/asciidoc-thesis.git"
    assert asciidoc_case.expected_primary_ecosystem == "asciidoc"


def test_default_public_repository_cases_include_org() -> None:
    org_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "org"
    )

    assert org_case.repository_url == "https://github.com/lujun9972/emacs-document.git"
    assert org_case.expected_primary_ecosystem == "org"


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
    cmake_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "cmake"
    )

    assert cmake_case.repository_url == "https://github.com/ttroy50/cmake-examples.git"
    assert cmake_case.expected_primary_ecosystem == "cmake"


def test_default_public_repository_cases_include_meson() -> None:
    meson_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "meson"
    )

    assert meson_case.repository_url == "https://github.com/tiernemi/meson-sample-project.git"
    assert meson_case.expected_primary_ecosystem == "meson"


def test_default_public_repository_cases_include_qmake() -> None:
    qmake_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "qmake"
    )

    assert qmake_case.repository_url == "https://github.com/horsicq/XPEViewer.git"
    assert qmake_case.expected_primary_ecosystem == "qmake"


def test_default_public_repository_cases_include_qml() -> None:
    qml_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "qml"
    )

    assert qml_case.repository_url == "https://github.com/Qt-QML/QmlFlightInstruments.git"
    assert qml_case.expected_primary_ecosystem == "qml"


def test_default_public_repository_cases_include_vue() -> None:
    vue_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "vue"
    )

    assert vue_case.repository_url == "https://github.com/coreui/coreui-free-vue-admin-template.git"
    assert vue_case.expected_primary_ecosystem == "vue"


def test_default_public_repository_cases_include_less() -> None:
    less_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "less"
    )

    assert less_case.repository_url == "https://github.com/jerrykuku/luci-theme-argon.git"
    assert less_case.expected_primary_ecosystem == "less"


def test_default_public_repository_cases_include_stylus() -> None:
    stylus_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "stylus"
    )

    assert stylus_case.repository_url == "https://github.com/theme-next/hexo-theme-next.git"
    assert stylus_case.expected_primary_ecosystem == "stylus"


def test_default_public_repository_cases_include_cython() -> None:
    cython_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "cython"
    )

    assert cython_case.repository_url == "https://github.com/strawlab/python-pcl.git"
    assert cython_case.expected_primary_ecosystem == "cython"


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

    assert factor_case.repository_url == "https://github.com/mrjbq7/re-factor.git"
    assert factor_case.expected_primary_ecosystem == "factor"


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
    scss_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "scss"
    )

    assert scss_case.repository_url == "https://github.com/pages-themes/minimal.git"
    assert scss_case.expected_primary_ecosystem == "scss"


def test_default_public_repository_cases_include_jinja() -> None:
    jinja_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "jinja"
    )

    assert jinja_case.repository_url == "https://github.com/netbootxyz/netboot.xyz.git"
    assert jinja_case.expected_primary_ecosystem == "jinja"


def test_default_public_repository_cases_include_liquid() -> None:
    liquid_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "liquid"
    )

    assert liquid_case.repository_url == "https://github.com/Shopify/dawn.git"
    assert liquid_case.expected_primary_ecosystem == "liquid"


def test_default_public_repository_cases_include_handlebars() -> None:
    handlebars_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "handlebars"
    )

    assert handlebars_case.repository_url == "https://github.com/TryGhost/Source.git"
    assert handlebars_case.expected_primary_ecosystem == "handlebars"


def test_default_public_repository_cases_include_tex() -> None:
    tex_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "tex"
    )

    assert tex_case.repository_url == "https://github.com/posquit0/Awesome-CV.git"
    assert tex_case.expected_primary_ecosystem == "tex"


def test_default_public_repository_cases_include_protobuf() -> None:
    protobuf_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "protobuf"
    )

    assert (
        protobuf_case.repository_url == "https://github.com/googleapis/api-common-protos.git"
    )
    assert protobuf_case.expected_primary_ecosystem == "protobuf"


def test_default_public_repository_cases_include_robotframework() -> None:
    robotframework_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "robotframework"
    )

    assert robotframework_case.repository_url == "https://github.com/robotframework/WebDemo.git"
    assert robotframework_case.expected_primary_ecosystem == "robotframework"


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
    typst_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "typst"
    )

    assert typst_case.repository_url == "https://github.com/typst/packages.git"
    assert typst_case.expected_primary_ecosystem == "typst"


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

    assert vala_case.repository_url == "https://github.com/elementary/code.git"
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
    hack_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "hack"
    )

    assert hack_case.repository_url == "https://github.com/hhvm/hsl.git"
    assert hack_case.expected_primary_ecosystem == "hack"


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
    eiffel_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "eiffel"
    )

    assert eiffel_case.repository_url == "https://github.com/gobo-eiffel/gobo.git"
    assert eiffel_case.expected_primary_ecosystem == "eiffel"


def test_default_public_repository_cases_include_tlaplus() -> None:
    tlaplus_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "tlaplus"
    )

    assert tlaplus_case.repository_url == "https://github.com/tlaplus/Examples.git"
    assert tlaplus_case.expected_primary_ecosystem == "tlaplus"


def test_default_public_repository_cases_include_logtalk() -> None:
    logtalk_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "logtalk"
    )

    assert logtalk_case.repository_url == "https://github.com/LogtalkDotOrg/talkshow.git"
    assert logtalk_case.expected_primary_ecosystem == "logtalk"


def test_default_public_repository_cases_include_chapel() -> None:
    chapel_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "chapel"
    )

    assert chapel_case.repository_url == "https://github.com/chapel-lang/Crypto.git"
    assert chapel_case.expected_primary_ecosystem == "chapel"


def test_default_public_repository_cases_include_bicep() -> None:
    bicep_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "bicep"
    )

    assert (
        bicep_case.repository_url == "https://github.com/Azure/bicep-registry-modules.git"
    )
    assert bicep_case.expected_primary_ecosystem == "bicep"


def test_default_public_repository_cases_include_dhall() -> None:
    dhall_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "dhall"
    )

    assert dhall_case.repository_url == "https://github.com/regadas/github-actions-dhall.git"
    assert dhall_case.expected_primary_ecosystem == "dhall"


def test_default_public_repository_cases_include_bitbake() -> None:
    bitbake_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "bitbake"
    )

    assert (
        bitbake_case.repository_url
        == "https://github.com/openembedded/meta-openembedded.git"
    )
    assert bitbake_case.expected_primary_ecosystem == "bitbake"


def test_default_public_repository_cases_include_puppet() -> None:
    puppet_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "puppet"
    )

    assert puppet_case.repository_url == "https://github.com/puppetlabs/puppetlabs-apache.git"
    assert puppet_case.expected_primary_ecosystem == "puppet"


def test_default_public_repository_cases_include_openscad() -> None:
    openscad_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "openscad"
    )

    assert openscad_case.repository_url == "https://github.com/BelfrySCAD/BOSL2.git"
    assert openscad_case.expected_primary_ecosystem == "openscad"


def test_default_public_repository_cases_include_haxe() -> None:
    haxe_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "haxe"
    )

    assert haxe_case.repository_url == "https://github.com/HaxeFoundation/hscript.git"
    assert haxe_case.expected_primary_ecosystem == "haxe"


def test_default_public_repository_cases_include_agda() -> None:
    agda_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "agda"
    )

    assert agda_case.repository_url == "https://github.com/agda/agda-stdlib.git"
    assert agda_case.expected_primary_ecosystem == "agda"


def test_default_public_repository_cases_include_idris() -> None:
    idris_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "idris"
    )

    assert idris_case.repository_url == "https://github.com/stefan-hoeck/idris2-pack.git"
    assert idris_case.expected_primary_ecosystem == "idris"


def test_default_public_repository_cases_include_perl() -> None:
    perl_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "perl"
    )

    assert perl_case.repository_url == "https://github.com/dagolden/Path-Tiny.git"
    assert perl_case.expected_primary_ecosystem == "perl"


def test_default_public_repository_cases_include_raku() -> None:
    raku_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "raku"
    )

    assert raku_case.repository_url == "https://github.com/ugexe/zef.git"
    assert raku_case.expected_primary_ecosystem == "raku"


def test_default_public_repository_cases_include_purescript() -> None:
    purescript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "purescript"
    )

    assert (
        purescript_case.repository_url
        == "https://github.com/purescript/purescript-prelude.git"
    )
    assert purescript_case.expected_primary_ecosystem == "purescript"


def test_default_public_repository_cases_include_rescript() -> None:
    rescript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "rescript"
    )

    assert (
        rescript_case.repository_url
        == "https://github.com/glennsl/rescript-json-combinators.git"
    )
    assert rescript_case.expected_primary_ecosystem == "rescript"


def test_default_public_repository_cases_include_gleam() -> None:
    gleam_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "gleam"
    )

    assert gleam_case.repository_url == "https://github.com/gleam-lang/stdlib.git"
    assert gleam_case.expected_primary_ecosystem == "gleam"


def test_default_public_repository_cases_include_janet() -> None:
    janet_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "janet"
    )

    assert janet_case.repository_url == "https://github.com/janet-lang/jpm.git"
    assert janet_case.expected_primary_ecosystem == "janet"


def test_default_public_repository_cases_include_nushell() -> None:
    nushell_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "nushell"
    )

    assert nushell_case.repository_url == "https://github.com/nushell/nu_scripts.git"
    assert nushell_case.expected_primary_ecosystem == "nushell"


def test_default_public_repository_cases_include_fish() -> None:
    fish_case = next(
        case for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES if case.language == "fish"
    )

    assert fish_case.repository_url == "https://github.com/jorgebucaran/fisher.git"
    assert fish_case.expected_primary_ecosystem == "fish"


def test_default_public_repository_cases_include_applescript() -> None:
    applescript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "applescript"
    )

    assert applescript_case.repository_url == "https://github.com/unforswearing/applescript.git"
    assert applescript_case.expected_primary_ecosystem == "applescript"


def test_default_public_repository_cases_include_elm() -> None:
    elm_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "elm"
    )

    assert elm_case.repository_url == "https://github.com/elm/core.git"
    assert elm_case.expected_primary_ecosystem == "elm"


def test_default_public_repository_cases_include_emacslisp() -> None:
    emacslisp_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "emacslisp"
    )

    assert emacslisp_case.repository_url == "https://github.com/magnars/dash.el.git"
    assert emacslisp_case.expected_primary_ecosystem == "emacslisp"


def test_default_public_repository_cases_include_vimscript() -> None:
    vimscript_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "vimscript"
    )

    assert vimscript_case.repository_url == "https://github.com/tpope/vim-fugitive.git"
    assert vimscript_case.expected_primary_ecosystem == "vimscript"


def test_default_public_repository_cases_include_vba() -> None:
    vba_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "vba"
    )

    assert vba_case.repository_url == "https://github.com/VBA-tools/VBA-JSON.git"
    assert vba_case.expected_primary_ecosystem == "vba"


def test_default_public_repository_cases_include_racket() -> None:
    racket_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "racket"
    )

    assert racket_case.repository_url == "https://github.com/mbutterick/pollen.git"
    assert racket_case.expected_primary_ecosystem == "racket"


def test_default_public_repository_cases_include_scheme() -> None:
    scheme_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "scheme"
    )

    assert scheme_case.repository_url == "https://github.com/ashinn/irregex.git"
    assert scheme_case.expected_primary_ecosystem == "scheme"


def test_default_public_repository_cases_include_cfml() -> None:
    cfml_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "cfml"
    )

    assert cfml_case.repository_url == "https://github.com/ghidinelli/cfpayment.git"
    assert cfml_case.expected_primary_ecosystem == "cfml"


def test_default_public_repository_cases_include_delphi() -> None:
    delphi_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "delphi"
    )

    assert delphi_case.repository_url == "https://github.com/VSoftTechnologies/DUnitX.git"
    assert delphi_case.expected_primary_ecosystem == "delphi"


def test_default_public_repository_cases_include_tsql() -> None:
    tsql_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "tsql"
    )

    assert (
        tsql_case.repository_url
        == "https://github.com/BrentOzarULTD/SQL-Server-First-Responder-Kit.git"
    )
    assert tsql_case.expected_primary_ecosystem == "tsql"


def test_default_public_repository_cases_include_xpp() -> None:
    xpp_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "xpp"
    )

    assert xpp_case.repository_url == "https://github.com/TrudAX/XppTools.git"
    assert xpp_case.expected_primary_ecosystem == "xpp"


def test_default_public_repository_cases_include_pascal() -> None:
    pascal_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "pascal"
    )

    assert (
        pascal_case.repository_url
        == "https://github.com/transmission-remote-gui/transgui.git"
    )
    assert pascal_case.expected_primary_ecosystem == "pascal"


def test_default_public_repository_cases_include_mojo() -> None:
    mojo_case = next(
        case
        for case in public_repo_matrix.DEFAULT_PUBLIC_REPOSITORY_CASES
        if case.language == "mojo"
    )

    assert (
        mojo_case.repository_url
        == "https://github.com/gabrieldemarmiesse/mojo-stdlib-extensions.git"
    )
    assert mojo_case.expected_primary_ecosystem == "mojo"
