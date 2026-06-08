"""Tests for repository_intelligence_real_repo_probe: operational_seed_a.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_operational_seed_paths_without_diagnostics_prefers_entrypoints(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "frontend-repo"
    (repo_path / "src" / "pages").mkdir(parents=True)
    (repo_path / "src" / "components" / "ui").mkdir(parents=True)
    (repo_path / "src" / "main.tsx").write_text("export const bootstrap = 1;\n", encoding="utf-8")
    (repo_path / "src" / "App.tsx").write_text("export const App = () => null;\n", encoding="utf-8")
    (repo_path / "src" / "pages" / "Index.tsx").write_text(
        "export const Index = () => null;\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "components" / "ui" / "button.tsx").write_text(
        "export const Button = () => null;\n",
        encoding="utf-8",
    )

    seed_paths = _derive_operational_seed_paths_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert "src/main.tsx" in seed_paths
    assert "src/App.tsx" in seed_paths
    assert "src/pages/Index.tsx" in seed_paths


def test_operational_seed_plan_without_diagnostics_uses_generic_frontend_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "frontend-profile-repo"
    (repo_path / "src" / "pages").mkdir(parents=True)
    (repo_path / "src" / "components" / "ui").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        '{\n'
        '  "name": "frontend-profile",\n'
        '  "scripts": { "dev": "vite", "build": "vite build" }\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "vite.config.js").write_text(
        "export default {};\n",
        encoding="utf-8",
    )
    (repo_path / "tsconfig.app.json").write_text(
        '{\n'
        '  "compilerOptions": {\n'
        '    "baseUrl": ".",\n'
        '    "paths": { "@/*": ["./src/*"] }\n'
        "  },\n"
        '  "include": ["src"]\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.tsx").write_text("export const bootstrap = 1;\n", encoding="utf-8")
    (repo_path / "src" / "App.tsx").write_text("export const App = () => null;\n", encoding="utf-8")
    (repo_path / "src" / "pages" / "Index.tsx").write_text(
        "export const Index = () => null;\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "components" / "ui" / "button.tsx").write_text(
        "export const Button = () => null;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert "src/main.tsx" in seed_plan["entrypoint_files"]
    assert "src/App.tsx" in seed_plan["entrypoint_files"]
    assert "src/pages/Index.tsx" in seed_plan["entrypoint_files"]
    assert "vite.config.js" not in seed_plan["entrypoint_files"]
    assert "src" in seed_plan["support_roots"]
    assert "package.json" in seed_plan["config_paths"]
    assert "tsconfig.app.json" in seed_plan["config_paths"]
    assert "node" in seed_plan["detected_ecosystems"]
    assert "typescript" in seed_plan["detected_ecosystems"]


def test_operational_seed_plan_without_diagnostics_does_not_expand_passive_package_json_app_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "clojure-passive-package-json-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "app" / "acme").mkdir(parents=True)
    (repo_path / "deps.edn").write_text(
        '{:paths ["src"]}\n',
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        json.dumps(
            {
                "name": "acme",
                "devDependencies": {
                    "shadow-cljs": "^3.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.cljc").write_text(
        "(ns acme.core)\n(def value 1)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "helper.cljc").write_text(
        "(ns acme.helper)\n(def helper 1)\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "acme" / "demo.cljc").write_text(
        "(ns acme.demo)\n(def demo 1)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "clojure" in seed_plan["detected_ecosystems"]
    assert "node" in seed_plan["detected_ecosystems"]
    assert "src" in seed_plan["support_roots"]
    assert "app" not in seed_plan["support_roots"]
    assert "src/acme/core.cljc" in seed_plan["entrypoint_files"]
    assert "app/acme/demo.cljc" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_leaf_support_root_code(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nested-polyglot-profile-repo"
    (repo_path / "website" / "pages").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "website" / "package.json").write_text(
        '{\n'
        '  "name": "nested-polyglot-profile",\n'
        '  "scripts": { "dev": "next dev" }\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "website" / "next.config.js").write_text(
        "module.exports = {};\n",
        encoding="utf-8",
    )
    (repo_path / "website" / "theme.config.jsx").write_text(
        "export default {};\n",
        encoding="utf-8",
    )
    (repo_path / "website" / "pages" / "_app.tsx").write_text(
        "export default function App() { return null; }\n",
        encoding="utf-8",
    )
    (repo_path / "build.zig").write_text(
        "const std = @import(\"std\");\n"
        "pub fn build(b: *std.Build) void {\n"
        "  _ = b;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.zig").write_text(
        "pub fn main() void {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "node" in seed_plan["detected_ecosystems"]
    assert "zig" in seed_plan["detected_ecosystems"]
    assert "website/pages/_app.tsx" in seed_plan["entrypoint_files"]
    assert "src/main.zig" in seed_plan["entrypoint_files"]
    assert "website/next.config.js" not in seed_plan["entrypoint_files"]
    assert "website/theme.config.jsx" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_pyproject_scripts(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "python-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "acme"\n'
        "[project.scripts]\n"
        'acme = "acme.cli:main"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "cli.py").write_text(
        "def main() -> int:\n    return 0\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert "src/acme/cli.py" in seed_plan["entrypoint_files"]
    assert "src" in seed_plan["support_roots"]
    assert "pyproject.toml" in seed_plan["config_paths"]
    assert "python" in seed_plan["detected_ecosystems"]


def test_operational_seed_plan_without_diagnostics_orders_detected_ecosystems_by_rank(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mixed-ranked-profile-repo"
    (repo_path / "web" / "src").mkdir(parents=True)
    (repo_path / "py" / "src" / "acme").mkdir(parents=True)
    (repo_path / "rust" / "src").mkdir(parents=True)
    (repo_path / "web" / "package.json").write_text(
        '{\n'
        '  "name": "mixed-ranked-profile",\n'
        '  "scripts": { "dev": "vite" }\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "web" / "tsconfig.json").write_text(
        '{\n'
        '  "compilerOptions": {\n'
        '    "baseUrl": ".",\n'
        '    "paths": { "@/*": ["./src/*"] }\n'
        "  },\n"
        '  "include": ["src"]\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "web" / "src" / "main.ts").write_text(
        "export const bootstrap = 1;\n",
        encoding="utf-8",
    )
    (repo_path / "py" / "pyproject.toml").write_text(
        "[project]\n"
        'name = "acme"\n'
        "[project.scripts]\n"
        'acme = "acme.cli:main"\n',
        encoding="utf-8",
    )
    (repo_path / "py" / "src" / "acme" / "cli.py").write_text(
        "def main() -> int:\n    return 0\n",
        encoding="utf-8",
    )
    (repo_path / "rust" / "Cargo.toml").write_text(
        "[package]\n"
        'name = "ranked-rust"\n'
        'version = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "rust" / "src" / "main.rs").write_text(
        "fn main() {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=256,
    )

    assert seed_plan["detected_ecosystems"] == ["typescript", "python", "node", "rust"]
    assert seed_plan["entrypoint_files"][:3] == [
        "web/src/main.ts",
        "py/src/acme/cli.py",
        "rust/src/main.rs",
    ]


def test_operational_seed_plan_without_diagnostics_uses_pubspec_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dart-profile-repo"
    (repo_path / "lib" / "src").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "pubspec.yaml").write_text(
        "name: acme_client\n"
        "environment:\n"
        '  sdk: ">=3.0.0 <4.0.0"\n',
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme_client.dart").write_text(
        "export 'src/client.dart' show Client;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "src" / "client.dart").write_text(
        "class Client {}\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "acme_client.dart").write_text(
        "import 'package:acme_client/acme_client.dart' show Client;\n"
        "Client run() => Client();\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "acme_client_test.dart").write_text(
        "void main() {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "dart" in seed_plan["detected_ecosystems"]
    assert "pubspec.yaml" in seed_plan["config_paths"]
    assert any(root in seed_plan["support_roots"] for root in {"lib", "lib/Demo"})
    assert "bin" in seed_plan["support_roots"]
    assert "lib/acme_client.dart" in seed_plan["entrypoint_files"]
    assert "bin/acme_client.dart" in seed_plan["entrypoint_files"]
    assert "test/acme_client_test.dart" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_primary_dart_workspace_ecosystem(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dart-workspace-profile-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "pkgs" / "core" / "lib").mkdir(parents=True)
    (repo_path / "pkgs" / "example" / "android").mkdir(parents=True)
    (repo_path / "pkgs" / "example" / "windows" / "runner").mkdir(parents=True)
    (repo_path / "pkgs" / "example" / "linux").mkdir(parents=True)
    (repo_path / "pubspec.yaml").write_text(
        "name: acme_workspace\n"
        "workspace:\n"
        "  - pkgs/core\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme_workspace.dart").write_text(
        "export 'package:core/core.dart';\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "core" / "pubspec.yaml").write_text(
        "name: core\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "core" / "lib" / "core.dart").write_text(
        "class Core {}\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "example" / "android" / "build.gradle").write_text(
        "plugins { id 'com.android.application' }\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "example" / "windows" / "runner" / "main.cpp").write_text(
        "int main() { return 0; }\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "example" / "linux" / "main.cc").write_text(
        "int main() { return 0; }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=256,
    )

    assert seed_plan["detected_ecosystems"][:4] == ["java", "cpp", "dart", "groovy"]
    assert seed_plan["operational_ecosystems"][0] == "dart"
    assert seed_plan["entrypoint_files"][0] == "lib/acme_workspace.dart"
    assert "pkgs/core/lib/core.dart" in seed_plan["entrypoint_files"][:3]
    assert "pkgs/example/windows/runner/main.cpp" not in seed_plan["entrypoint_files"][:2]


def test_operational_seed_plan_without_diagnostics_uses_clojure_deps_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "clojure-deps-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "deps.edn").write_text(
        '{:paths ["src"] :main acme.core}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.clj").write_text(
        "(ns acme.core)\n(defn run [] :ok)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "util.clj").write_text(
        "(ns acme.util)\n(defn helper [] :ok)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["clojure"]
    assert "deps.edn" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme/core.clj" in seed_plan["entrypoint_files"]
    assert "src/acme/util.clj" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_clojure_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "clojure-project-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "project.clj").write_text(
        '(defproject acme/core "0.1.0" :main acme.core :source-paths ["src"])\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.clj").write_text(
        "(ns acme.core)\n(defn run [] :ok)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["clojure"]
    assert "project.clj" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme/core.clj" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_lua_rockspec_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lua-rockspec-profile-repo"
    (repo_path / "lua" / "acme").mkdir(parents=True)
    (repo_path / "acme-scm-1.rockspec").write_text(
        'package = "acme"\n'
        'build = { modules = { ["acme.init"] = "lua/acme/init.lua", ["acme.util"] = "lua/acme/util.lua" } }\n',
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "init.lua").write_text(
        "local M = {}\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "util.lua").write_text(
        "local M = {}\nfunction M.helper() return 'ok' end\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "spec").mkdir(parents=True)
    (repo_path / "spec" / "acme_spec.lua").write_text(
        "return true\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["lua"]
    assert "acme-scm-1.rockspec" in seed_plan["config_paths"]
    assert "lua" in seed_plan["support_roots"]
    assert "lua/acme/init.lua" in seed_plan["entrypoint_files"]
    assert "lua/acme/util.lua" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_luau_profiles(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "luau-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "package.json").write_text('{"name":"luau-profile-repo","private":true}', encoding="utf-8")
    (repo_path / "default.project.json").write_text(
        '{\n  "name": "jecs",\n  "tree": {\n    "$path": "src/jecs.luau"\n  }\n}\n',
        encoding="utf-8",
    )
    (repo_path / "wally.toml").write_text(
        "[package]\nname = 'ukendio/jecs'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "jecs.luau").write_text(
        "--!strict\nlocal M = {}\nfunction M.helper()\n  return 'ok'\nend\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "spec.luau").write_text(
        "--!strict\nreturn {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["node", "luau"]
    assert seed_plan["operational_ecosystems"][0] == "luau"
    assert "default.project.json" in seed_plan["config_paths"]
    assert "wally.toml" in seed_plan["config_paths"]
    assert "package.json" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/jecs.luau" in seed_plan["entrypoint_files"]
    assert "test/spec.luau" not in seed_plan["entrypoint_files"]
    assert "src/jecs.luau" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_prefers_manifest_ecosystem_code(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lua-mixed-profile-repo"
    (repo_path / "doc").mkdir(parents=True)
    (repo_path / "fun-scm-1.rockspec").write_text(
        'package = "fun"\n'
        'build = { modules = { ["fun"] = "fun.lua" } }\n',
        encoding="utf-8",
    )
    (repo_path / "fun.lua").write_text(
        "local M = {}\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "doc" / "conf.py").write_text("project = 'fun'\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["lua"]
    assert "fun.lua" in seed_plan["entrypoint_files"]
    assert "doc/conf.py" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_shell_repo_conventions(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shell-profile-repo"
    (repo_path / "plugins" / "git").mkdir(parents=True)
    (repo_path / "themes").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "plugins" / "git" / "git.plugin.zsh").write_text(
        "git_main() { echo git; }\n",
        encoding="utf-8",
    )
    (repo_path / "themes" / "acme.zsh-theme").write_text(
        "prompt_acme_setup() { echo theme; }\n",
        encoding="utf-8",
    )
    (repo_path / "install.sh").write_text(
        "install_main() { echo install; }\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "install_test.sh").write_text(
        "test_install() { :; }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["shell"]
    assert "install.sh" in seed_plan["entrypoint_files"]
    assert "plugins/git/git.plugin.zsh" in seed_plan["candidate_file_paths"]
    assert "themes/acme.zsh-theme" in seed_plan["candidate_file_paths"]
    assert "test/install_test.sh" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_root_shell_entrypoints(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shell-root-entrypoint-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "toolkit.sh").write_text(
        "main() {\n"
        "  . ./lib/core.zsh\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "core.zsh").write_text("helper() { echo core; }\n", encoding="utf-8")
    (repo_path / "lib" / "helper.zsh").write_text("util() { echo util; }\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["shell"]
    assert seed_plan["entrypoint_files"][0] == "toolkit.sh"


def test_operational_seed_plan_without_diagnostics_uses_powershell_manifest_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "powershell-profile-repo"
    (repo_path / "Public").mkdir(parents=True)
    (repo_path / "Private").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Acme.psd1").write_text(
        "@{\n"
        "  RootModule = 'Acme.psm1'\n"
        "  NestedModules = @('Public/Invoke-Acme.ps1')\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Acme.psm1").write_text(
        '. "$PSScriptRoot/Private/Helpers.ps1"\n',
        encoding="utf-8",
    )
    (repo_path / "Public" / "Invoke-Acme.ps1").write_text(
        "function Invoke-Acme { Get-Helper }\n",
        encoding="utf-8",
    )
    (repo_path / "Private" / "Helpers.ps1").write_text(
        "function Get-Helper { return 'ok' }\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "Acme.Tests.ps1").write_text(
        "Describe 'Acme' {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["powershell"]
    assert "Acme.psm1" in seed_plan["entrypoint_files"]
    assert "Public" in seed_plan["support_roots"]
    assert "Private" in seed_plan["support_roots"]
    assert "tests/Acme.Tests.ps1" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_rebar_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "erlang-rebar-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "rebar.config").write_text("{erl_opts, [debug_info]}.\n", encoding="utf-8")
    (repo_path / "src" / "acme.erl").write_text(
        "-module(acme).\n-export([run/0]).\nrun() -> ok.\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "acme_SUITE.erl").write_text(
        "-module(acme_SUITE).\n-export([all/0]).\nall() -> [].\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["erlang"]
    assert "rebar.config" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.erl" in seed_plan["entrypoint_files"]
    assert "test/acme_SUITE.erl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_erlang_mk_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "erlang-mk-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "erlang.mk").write_text("PROJECT = acme\n", encoding="utf-8")
    (repo_path / "src" / "acme.erl").write_text(
        "-module(acme).\n-export([run/0]).\nrun() -> ok.\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "acme_SUITE.erl").write_text(
        "-module(acme_SUITE).\n-export([all/0]).\nall() -> [].\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["erlang"]
    assert "erlang.mk" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.erl" in seed_plan["entrypoint_files"]
    assert "test/acme_SUITE.erl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_erlang_app_src_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "erlang-app-src-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "src" / "acme.app.src").write_text(
        "{application, acme, [{modules, [acme]}]}.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.erl").write_text(
        "-module(acme).\n-export([run/0]).\nrun() -> ok.\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "acme_SUITE.erl").write_text(
        "-module(acme_SUITE).\n-export([all/0]).\nall() -> [].\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["erlang"]
    assert "src/acme.app.src" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.erl" in seed_plan["entrypoint_files"]
    assert "test/acme_SUITE.erl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_nimble_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nimble-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "acme.nimble").write_text("version = \"0.1.0\"\n", encoding="utf-8")
    (repo_path / "src" / "acme.nim").write_text("proc run*() = discard\n", encoding="utf-8")
    (repo_path / "src" / "acme" / "util.nim").write_text(
        "proc helper*() = discard\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "acme_test.nim").write_text(
        "discard\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["nim"]
    assert "acme.nimble" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.nim" in seed_plan["entrypoint_files"]
    assert "src/acme/util.nim" in seed_plan["candidate_file_paths"]
    assert "tests/acme_test.nim" not in seed_plan["entrypoint_files"]


