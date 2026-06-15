"""Tests for repository_intelligence_real_repo_probe: operational_seed_d.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

import benchmarks.repository_intelligence_real_repo_probe as probe_module
from benchmarks.repository_intelligence_real_repo_probe_profile_manifest_systems_support import (
    _csproj_profile_hints,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_style_candidates_support import (
    _less_profile_hints_from_candidates,
    _scss_profile_hints_from_candidates,
    _stylus_profile_hints_from_candidates,
)

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_operational_seed_plan_without_diagnostics_promotes_typst_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "typst-profile-repo"
    (repo_path / "content").mkdir(parents=True)
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "content" / "math.typ").write_text(
        "#let add(x, y) = x + y\n"
        "#let scale(x) = x * 2\n",
        encoding="utf-8",
    )
    (repo_path / "partials" / "common.typ").write_text(
        "#let title() = [Demo]\n",
        encoding="utf-8",
    )
    (repo_path / "main.typ").write_text(
        '#import "content/math.typ": add\n'
        '#import "content/math.typ" as math\n'
        '#include "partials/common.typ"\n'
        "#let render() = {\n"
        "  add(1, 2)\n"
        "  math.scale(3)\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "typst.toml").write_text(
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "helper.py").write_text(
        "def main():\n    return None\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "typst" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "typst"
    assert "main.typ" in seed_plan["entrypoint_files"]
    assert "content" in seed_plan["support_roots"]
    assert "typst.toml" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_promotes_tex_examples_surface(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tex-examples-profile-repo"
    (repo_path / "examples" / "cv").mkdir(parents=True)
    (repo_path / "examples" / "resume").mkdir(parents=True)
    (repo_path / "examples" / "coverletter.tex").write_text(
        '\\begin{document}\\nCover letter\\n\\end{document}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "cv.tex").write_text(
        '\\input{cv/experience}\\n'
        '\\input{cv/education}\\n'
        '\\input{cv/skills}\\n'
        '\\begin{document}\\nCV\\n\\end{document}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "resume.tex").write_text(
        '\\input{resume/committees}\\n'
        '\\input{resume/summary}\\n'
        '\\begin{document}\\nResume\\n\\end{document}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "cv" / "certificates.tex").write_text(
        '\\section{Certificates}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "cv" / "committees.tex").write_text(
        '\\section{Committees}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "cv" / "education.tex").write_text(
        '\\section{Education}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "cv" / "experience.tex").write_text(
        '\\section{Experience}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "cv" / "honors.tex").write_text(
        '\\section{Honors}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "cv" / "presentation.tex").write_text(
        '\\section{Presentations}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "cv" / "skills.tex").write_text(
        '\\section{Skills}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "cv" / "writing.tex").write_text(
        '\\section{Writing}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "resume" / "committees.tex").write_text(
        '\\section{Committees}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "resume" / "education.tex").write_text(
        '\\section{Education}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "resume" / "experience.tex").write_text(
        '\\section{Experience}\\n',
        encoding="utf-8",
    )
    (repo_path / "examples" / "resume" / "summary.tex").write_text(
        '\\section{Summary}\\n',
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["examples", "examples/cv", "examples/resume"],
        max_files=128,
    )

    assert "tex" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "tex"
    assert "examples/coverletter.tex" in seed_plan["entrypoint_files"]
    assert "examples/cv.tex" in seed_plan["entrypoint_files"]
    assert "examples" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_promotes_scss_when_scss_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scss-profile-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "_mixins.scss").write_text(
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "_functions.scss").write_text(
        "@function helper-fn() {\n"
        "  @return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "app.scss").write_text(
        '@use "styles/mixins" as mixins;\n'
        '@import "styles/functions";\n'
        ".button {\n"
        "  @include mixins.button-base;\n"
        "  color: helper-fn();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "theme.scss").write_text(
        '@import "styles/functions";\n'
        ".theme {\n"
        "  color: helper-fn();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "app.rb").write_text("class App; end\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "scss" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "scss"
    assert "app.scss" in seed_plan["entrypoint_files"]
    assert "styles/_mixins.scss" in seed_plan["candidate_file_paths"]
    assert "styles" in seed_plan["support_roots"]


def test_scss_profile_hints_reuse_loaded_text_per_candidate_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "scss-profile-hints-cache-repo"
    (repo_path / "styles").mkdir(parents=True)
    mixins_path = repo_path / "styles" / "_mixins.scss"
    app_path = repo_path / "app.scss"
    mixins_path.write_text(
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n",
        encoding="utf-8",
    )
    app_path.write_text(
        '@use "styles/mixins" as mixins;\n'
        ".button {\n"
        "  @include mixins.button-base;\n"
        "}\n",
        encoding="utf-8",
    )

    original_read_text = Path.read_text
    read_counts: dict[Path, int] = {}

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in {mixins_path, app_path}:
            read_counts[self] = read_counts.get(self, 0) + 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda _path, repo_path=None: "scss",
    )

    entrypoints, roots, configs = _scss_profile_hints_from_candidates(
        repo_path,
        ["styles/_mixins.scss", "app.scss"],
    )

    assert "app.scss" in entrypoints
    assert "styles" in roots
    assert configs == set()
    assert read_counts.get(mixins_path, 0) <= 1
    assert read_counts.get(app_path, 0) <= 1


def test_style_profile_hints_share_candidate_language_buckets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "style-profile-shared-buckets-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "theme.less").write_text(
        "@brand-color: #123456;\n.card { color: @brand-color; }\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "theme.scss").write_text(
        "$brand: #123456;\n.card { color: $brand; }\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "theme.styl").write_text(
        "brandColor = #123456\n.card\n  color brandColor\n",
        encoding="utf-8",
    )
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.ts").write_text(
        "export const run = () => 'ok';\n",
        encoding="utf-8",
    )

    language_probe_calls: list[str] = []
    language_by_suffix = {
        ".less": "less",
        ".scss": "scss",
        ".styl": "stylus",
        ".ts": "typescript",
    }

    def _counting_probe_language_for_path(path: str, repo_path: Path | None = None) -> str:
        del repo_path
        language_probe_calls.append(path)
        return language_by_suffix.get(Path(path).suffix.lower(), "unknown")

    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        _counting_probe_language_for_path,
    )

    candidate_paths = [
        "styles/theme.less",
        "styles/theme.scss",
        "styles/theme.styl",
        "src/main.ts",
    ]

    less_entrypoints, _less_roots, _less_configs = _less_profile_hints_from_candidates(
        repo_path,
        candidate_paths,
    )
    scss_entrypoints, _scss_roots, _scss_configs = _scss_profile_hints_from_candidates(
        repo_path,
        candidate_paths,
    )
    stylus_entrypoints, _stylus_roots, _stylus_configs = _stylus_profile_hints_from_candidates(
        repo_path,
        candidate_paths,
    )

    assert "styles/theme.less" in less_entrypoints
    assert "styles/theme.scss" in scss_entrypoints
    assert "styles/theme.styl" in stylus_entrypoints
    assert sorted(language_probe_calls) == sorted(candidate_paths)


def test_operational_seed_plan_without_diagnostics_promotes_dockerfile_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dockerfile-profile-repo"
    (repo_path / "docker").mkdir(parents=True)
    (repo_path / "conf" / "alpha").mkdir(parents=True)
    (repo_path / "conf" / "beta").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(8):
        image_dir = repo_path / "docker" / f"image_{index}"
        image_dir.mkdir(parents=True)
        (repo_path / "scripts" / f"boot_{index}.sh").write_text(
            "#!/usr/bin/env sh\n"
            f"echo boot {index}\n",
            encoding="utf-8",
        )
        (image_dir / "Dockerfile").write_text(
            "FROM alpine:3.20\n"
            f"COPY ../../scripts/boot_{index}.sh /usr/local/bin/boot.sh\n"
            "RUN sh ../../scripts/boot_0.sh\n",
            encoding="utf-8",
        )
    (repo_path / "conf" / "alpha" / "local.conf").write_text(
        'IMAGE_INSTALL:append = " docker"\n',
        encoding="utf-8",
    )
    (repo_path / "conf" / "beta" / "local.conf").write_text(
        'MACHINE ??= "qemuarm64"\n',
        encoding="utf-8",
    )
    (repo_path / "cmd").mkdir(parents=True)
    (repo_path / "cmd" / "main.go").write_text(
        "package main\n\nfunc main() {}\n",
        encoding="utf-8",
    )
    (repo_path / "internal").mkdir(parents=True)
    (repo_path / "internal" / "helper.go").write_text(
        "package internal\n\nfunc Run() {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "dockerfile" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "dockerfile"
    assert "docker/image_0/Dockerfile" in seed_plan["entrypoint_files"]
    assert "docker/image_0/Dockerfile" in seed_plan["candidate_file_paths"]
    assert "docker/image_0" in seed_plan["support_roots"]
    assert "bitbake" in seed_plan["detected_ecosystems"]


def test_operational_seed_plan_without_diagnostics_does_not_force_dockerfile_first_in_go_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mixed-go-docker-repo"
    (repo_path / "docker").mkdir(parents=True)
    (repo_path / "cmd").mkdir(parents=True)
    (repo_path / "internal").mkdir(parents=True)
    for index in range(2):
        (repo_path / "docker" / f"build_{index}.Dockerfile").write_text(
            "FROM golang:1.24\n"
            "COPY . /src\n",
            encoding="utf-8",
        )
    for index in range(10):
        target_dir = repo_path / ("cmd" if index < 5 else "internal")
        (target_dir / f"file_{index}.go").write_text(
            f"package main\n\nfunc run{index}() {{}}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "dockerfile" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "dockerfile"


def test_operational_seed_plan_without_diagnostics_does_not_force_typst_first_in_rust_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mixed-rust-typst-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "docs" / "guide.typ").write_text(
        "#let render() = [Guide]\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "appendix.typ").write_text(
        "#include \"guide.typ\"\n",
        encoding="utf-8",
    )
    (repo_path / "typst.toml").write_text(
        "[package]\nname = \"mixed\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )
    for index in range(8):
        (repo_path / "src" / f"module_{index}.rs").write_text(
            f"pub fn run_{index}() {{}}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "typst" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "typst"
    assert "rust" in seed_plan["operational_ecosystems"]


def test_operational_seed_plan_without_diagnostics_promotes_typst_package_registry_surface(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "typst-package-registry-repo"
    (repo_path / "bundler" / "src").mkdir(parents=True)
    (repo_path / "bundler" / "Cargo.toml").write_text(
        "[package]\nname = \"bundler\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )
    (repo_path / "bundler" / "src" / "main.rs").write_text(
        "fn main() {}\n",
        encoding="utf-8",
    )
    for index in range(12):
        package_root = repo_path / "packages" / "preview" / f"pkg_{index}" / "0.1.0"
        (package_root / "src").mkdir(parents=True)
        (package_root / "template").mkdir(parents=True)
        (package_root / "src" / "lib.typ").write_text(
            f"#let render_{index}() = [Package {index}]\n",
            encoding="utf-8",
        )
        (package_root / "template" / "demo.typ").write_text(
            f'#import "../src/lib.typ": render_{index}\n',
            encoding="utf-8",
        )
        if index < 6:
            (package_root / "flake.nix").write_text(
                "{ outputs = _: {}; }\n",
                encoding="utf-8",
            )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert seed_plan["operational_ecosystems"][0] == "typst"
    assert "rust" in seed_plan["detected_ecosystems"]
    assert any(path.endswith(".typ") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_uses_build_zig_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "zig-build-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "examples").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "build.zig").write_text(
        'const std = @import("std");\n'
        "pub fn build(b: *std.Build) void {\n"
        "  _ = b.addExecutable(.{\n"
        '    .name = "acme",\n'
        '    .root_source_file = b.path("src/main.zig"),\n'
        "  });\n"
        '  _ = b.addModule("acme", .{\n'
        '    .root_source_file = b.path("src/root.zig"),\n'
        "  });\n"
        "  _ = b.addExecutable(.{\n"
        '    .name = "demo",\n'
        '    .root_source_file = b.path("examples/demo.zig"),\n'
        "  });\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.zig").write_text("pub fn main() void {}\n", encoding="utf-8")
    (repo_path / "src" / "root.zig").write_text("pub const Answer = 42;\n", encoding="utf-8")
    (repo_path / "examples" / "demo.zig").write_text(
        "pub fn main() void {}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "root_test.zig").write_text(
        "test \"answer\" {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "zig" in seed_plan["detected_ecosystems"]
    assert "build.zig" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.zig" in seed_plan["entrypoint_files"]
    assert "src/root.zig" in seed_plan["entrypoint_files"]
    assert "examples/demo.zig" not in seed_plan["entrypoint_files"]
    assert "tests/root_test.zig" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_cabal_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haskell-cabal-repo"
    (repo_path / "src" / "Text" / "ParserCombinators").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "parsec.cabal").write_text(
        "name: parsec\n"
        "version: 1.0.0.0\n"
        "library\n"
        "  hs-source-dirs: src\n"
        "  exposed-modules: Text.Parsec, Text.ParserCombinators.Parsec\n"
        "test-suite parsec-tests\n"
        "  hs-source-dirs: test\n"
        "  main-is: Main.hs\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Text" / "Parsec.hs").write_text(
        "module Text.Parsec where\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Text" / "ParserCombinators" / "Parsec.hs").write_text(
        "module Text.ParserCombinators.Parsec where\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "Main.hs").write_text(
        "module Main where\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "haskell" in seed_plan["detected_ecosystems"]
    assert "parsec.cabal" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Text/Parsec.hs" in seed_plan["entrypoint_files"]
    assert "src/Text/ParserCombinators/Parsec.hs" in seed_plan["entrypoint_files"]
    assert "test/Main.hs" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_package_yaml_haskell_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haskell-package-yaml-repo"
    (repo_path / "src" / "Acme").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "package.yaml").write_text(
        "name: acme\n"
        "library:\n"
        "  source-dirs: src\n"
        "  exposed-modules:\n"
        "    - Acme.Lib\n"
        "executables:\n"
        "  acme-cli:\n"
        "    main: Main.hs\n"
        "    source-dirs:\n"
        "      - app\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme" / "Lib.hs").write_text(
        "module Acme.Lib where\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "Main.hs").write_text(
        "module Main where\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "haskell" in seed_plan["detected_ecosystems"]
    assert "package.yaml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "app" in seed_plan["support_roots"]
    assert "src/Acme/Lib.hs" in seed_plan["entrypoint_files"]
    assert "app/Main.hs" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_csproj_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dotnet-repo"
    (repo_path / "src" / "AcmeApp").mkdir(parents=True)
    (repo_path / "src" / "AcmeApp" / "AcmeApp.csproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Program.cs").write_text(
        "class Program { static void Main() {} }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Mediator.cs").write_text(
        "public sealed class Mediator {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert "dotnet" in seed_plan["detected_ecosystems"]
    assert "src/AcmeApp/AcmeApp.csproj" in seed_plan["config_paths"]
    assert "src/AcmeApp" in seed_plan["support_roots"]
    assert "src/AcmeApp/Program.cs" in seed_plan["entrypoint_files"]
    assert "src/AcmeApp/Mediator.cs" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_fsproj_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fsharp-repo"
    (repo_path / "src" / "AcmeApp").mkdir(parents=True)
    (repo_path / "test" / "AcmeApp.Benchmarks").mkdir(parents=True)
    (repo_path / "src" / "AcmeApp" / "AcmeApp.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Program.fs").write_text(
        "namespace AcmeApp\n\nmodule Program =\n    let main _ = 0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Routes.fs").write_text(
        "namespace AcmeApp\n\nmodule Routes =\n    let ping () = \"pong\"\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "AcmeApp.Benchmarks" / "AcmeApp.Benchmarks.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "AcmeApp.Benchmarks" / "Program.fs").write_text(
        "module Benchmarks.Program\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "dotnet" in seed_plan["detected_ecosystems"]
    assert "fsharp" in seed_plan["detected_ecosystems"]
    assert "src/AcmeApp/AcmeApp.fsproj" in seed_plan["config_paths"]
    assert "src/AcmeApp" in seed_plan["support_roots"]
    assert "src/AcmeApp/Program.fs" in seed_plan["entrypoint_files"]
    assert "src/AcmeApp/Routes.fs" in seed_plan["entrypoint_files"]
    assert "test/AcmeApp.Benchmarks/Program.fs" not in seed_plan["entrypoint_files"]


def test_csproj_profile_hints_use_explicit_compile_and_project_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fsharp-library-repo"
    (repo_path / "src" / "Library").mkdir(parents=True)
    (repo_path / "src" / "Common").mkdir(parents=True)
    (repo_path / "src" / "Library" / "Library.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\">\n"
        "  <ItemGroup>\n"
        "    <Compile Include=\"Domain.fs\" />\n"
        "    <Compile Include=\"Parser.fs\" />\n"
        "    <ProjectReference Include=\"../Common/Common.fsproj\" />\n"
        "  </ItemGroup>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Common" / "Common.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )

    entrypoints, roots, configs = _csproj_profile_hints(
        "src/Library/Library.fsproj",
        repo_path=repo_path,
    )

    assert entrypoints == {
        "src/Library/Domain.fs",
        "src/Library/Parser.fs",
    }
    assert "src/Library" in roots
    assert "src/Common" in roots
    assert configs == {
        "src/Library/Library.fsproj",
        "src/Common/Common.fsproj",
    }


def test_operational_seed_plan_without_diagnostics_uses_vbproj_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "visual-basic-repo"
    (repo_path / "src" / "AcmeApp" / "tests").mkdir(parents=True)
    (repo_path / "src" / "AcmeApp" / "AcmeApp.vbproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Program.vb").write_text(
        "Namespace AcmeApp\n"
        "Module Program\n"
        "    Sub Main()\n"
        "    End Sub\n"
        "End Module\n"
        "End Namespace\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "Mediator.vb").write_text(
        "Namespace AcmeApp\n"
        "Public Class Mediator\n"
        "End Class\n"
        "End Namespace\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "AcmeApp" / "tests" / "ProgramTests.vb").write_text(
        "Public Class ProgramTests\nEnd Class\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "dotnet" in seed_plan["detected_ecosystems"]
    assert "visualbasic" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "visualbasic"
    assert "src/AcmeApp/AcmeApp.vbproj" in seed_plan["config_paths"]
    assert "src/AcmeApp" in seed_plan["support_roots"]
    assert "src/AcmeApp/Program.vb" in seed_plan["entrypoint_files"]
    assert "src/AcmeApp/Mediator.vb" in seed_plan["entrypoint_files"]
    assert "src/AcmeApp/tests/ProgramTests.vb" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_vbp_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vb6-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Project1.vbp").write_text(
        'Type=Exe\n'
        'Class=cHelper; src/cHelper.cls\n'
        'Module=modMain; src/modMain.bas\n'
        'Form=src/Form1.frm\n'
        'Startup="Form1"\n'
        'Name="Project1"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Form1.frm").write_text(
        "VERSION 5.00\n"
        "Begin VB.Form Form1\n"
        "End\n"
        'Attribute VB_Name = "Form1"\n'
        "Option Explicit\n"
        "Private Sub Form_Load()\n"
        "    modMain.RunApp\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "modMain.bas").write_text(
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "cHelper.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "cHelper"\n'
        "Option Explicit\n"
        "Public Function Helper() As String\n"
        '    Helper = "ok"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "Project1.vbp").write_text(
        'Type=Exe\nForm=Form1.frm\nStartup="Form1"\nName="Project1Tests"\n',
        encoding="utf-8",
    )
    (repo_path / "tests" / "Form1.frm").write_text(
        'VERSION 5.00\nBegin VB.Form Form1\nEnd\nAttribute VB_Name = "Form1"\n',
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["vb6"]
    assert "Project1.vbp" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Form1.frm" in seed_plan["entrypoint_files"]
    assert "src/cHelper.cls" in seed_plan["candidate_file_paths"]
    assert "tests/Form1.frm" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_vba_surface(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vba-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "JsonConverter.bas").write_text(
        'Attribute VB_Name = "JsonConverter"\n'
        "Option Explicit\n"
        "Public Sub Main()\n"
        "    Dim data As JsonData\n"
        "    Set data = New JsonData\n"
        "    Debug.Print data.ToJson()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "JsonData.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "JsonData"\n'
        "Option Explicit\n"
        "Public Function ToJson() As String\n"
        '    ToJson = "{}"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "TestJson.bas").write_text(
        'Attribute VB_Name = "TestJson"\n'
        "Option Explicit\n"
        "Public Sub TestMain()\n"
        "End Sub\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["vba"]
    assert seed_plan["operational_ecosystems"] == ["vba"]
    assert "src" in seed_plan["support_roots"]
    assert "src/JsonConverter.bas" in seed_plan["entrypoint_files"]
    assert "src/JsonData.cls" in seed_plan["candidate_file_paths"]
    assert "tests/TestJson.bas" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_vbscript_wsf_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vbscript-profile-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "helper.vbs").write_text(
        "Class Helper\nEnd Class\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.wsf").write_text(
        "<job>\n"
        '  <script language="VBScript" src="lib/helper.vbs"></script>\n'
        '  <script language="VBScript">\n'
        "    Option Explicit\n"
        "    Sub Main()\n"
        "    End Sub\n"
        "  </script>\n"
        "</job>\n",
        encoding="utf-8",
    )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "test_helper.vbs").write_text(
        "Sub TestMain()\nEnd Sub\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["vbscript"]
    assert seed_plan["operational_ecosystems"] == ["vbscript"]
    assert "scripts/main.wsf" in seed_plan["config_paths"]
    assert "scripts/main.wsf" in seed_plan["entrypoint_files"]
    assert "scripts/lib" in seed_plan["support_roots"]
    assert "tests/test_helper.vbs" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_applescript_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "applescript-profile-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "Helper.applescript").write_text(
        "script HelperScript\n"
        "    on RenderJson(value)\n"
        "        return value\n"
        "    end RenderJson\n"
        "end script\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "Main.applescript").write_text(
        'property helperScript : load script POSIX file "lib/Helper.applescript"\n'
        "on run\n"
        "    helperScript's RenderJson(\"{}\")\n"
        "end run\n",
        encoding="utf-8",
    )
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "tests" / "MainTests.applescript").write_text(
        "on run\n"
        "    return true\n"
        "end run\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["applescript"]
    assert seed_plan["operational_ecosystems"] == ["applescript"]
    assert seed_plan["config_paths"] == []
    assert any(root in seed_plan["support_roots"] for root in {"scripts", "scripts/lib"})
    assert "scripts/Main.applescript" in seed_plan["entrypoint_files"]
    assert "tests/MainTests.applescript" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_cfml_box_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cfml-profile-repo"
    (repo_path / "config").mkdir(parents=True)
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "box.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "config" / "app.cfm").write_text(
        "<cfset request.ready = true />\n",
        encoding="utf-8",
    )
    (repo_path / "Application.cfc").write_text(
        "component {\n"
        '    include "config/app.cfm";\n'
        "    function onApplicationStart() {\n"
        "        local.userService = new models.UserService();\n"
        "        local.userService.run();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "UserService.cfc").write_text(
        "component {\n"
        "    function run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "public" / "index.cfm").write_text(
        '<cfinclude template="../config/app.cfm">\n',
        encoding="utf-8",
    )
    (repo_path / "tests" / "ApplicationTest.cfc").write_text(
        "component {\n"
        "    function testRun() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["cfml"]
    assert seed_plan["operational_ecosystems"] == ["cfml"]
    assert seed_plan["config_paths"] == ["box.json"]
    assert "config" in seed_plan["support_roots"]
    assert "models" in seed_plan["support_roots"]
    assert "public" in seed_plan["support_roots"]
    assert "Application.cfc" in seed_plan["entrypoint_files"]
    assert "public/index.cfm" in seed_plan["entrypoint_files"]
    assert "tests/ApplicationTest.cfc" not in seed_plan["entrypoint_files"]
