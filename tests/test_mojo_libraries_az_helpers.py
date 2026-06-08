from __future__ import annotations

from pathlib import Path

from tests import generate_mojo_tests as mojo_gen
from tests.integration import test_mojo_kernel_libraries_az as kernel_az
from tests.integration import test_mojo_libraries_az as mojo_az


def test_makefile_build_mojo_uses_repo_local_pixi_and_missing_entrypoint_guard() -> None:
    makefile_text = (Path(__file__).resolve().parents[1] / "Makefile").read_text(encoding="utf-8")

    assert "build-mojo:" in makefile_text
    assert "$(PWD)/.pixi/bin/pixi" in makefile_text
    assert "mojo/engine/main.mojo not found" in makefile_text


def test_native_mojo_build_helper_uses_object_then_runtime_link() -> None:
    helper_text = (
        Path(__file__).resolve().parents[1] / "scripts" / "build_mojo_binary.sh"
    ).read_text(encoding="utf-8")

    assert "--emit object" in helper_text
    assert "xcrun --show-sdk-path" in helper_text
    assert "-isysroot" in helper_text
    assert "-Wl,-syslibroot" in helper_text
    assert "libKGENCompilerRTShared" in helper_text or "-lKGENCompilerRTShared" in helper_text
    assert "libAsyncRTRuntimeGlobals" in helper_text or "-lAsyncRTRuntimeGlobals" in helper_text
    assert "libAsyncRTMojoBindings" in helper_text or "-lAsyncRTMojoBindings" in helper_text
    assert "libpython3.14" in helper_text or "-lpython3.14" in helper_text


def test_mojo_run_command_prefers_direct_binary_when_present(monkeypatch, tmp_path) -> None:
    mojo_bin = tmp_path / "mojo"
    mojo_bin.write_text("", encoding="utf-8")

    monkeypatch.setattr(mojo_az.shutil, "which", lambda name: "/usr/bin/pixi")
    monkeypatch.setattr(mojo_az.Path, "home", classmethod(lambda cls: Path("/missing-home")))
    monkeypatch.setattr(mojo_az, "MOJO_BIN", mojo_bin)
    monkeypatch.setattr(mojo_az, "ENGINE_DIR", Path("/tmp/engine"))

    command = mojo_az._mojo_run_command(Path("/tmp/test_lib.mojo"))

    assert command == [
        str(mojo_bin),
        "run",
        "-I/tmp/engine",
        "/tmp/test_lib.mojo",
    ]


def test_mojo_run_command_prefers_pixi_when_available(monkeypatch) -> None:
    monkeypatch.setattr(
        mojo_az.shutil,
        "which",
        lambda name: "/usr/bin/pixi" if name == "pixi" else None,
    )
    monkeypatch.setattr(mojo_az, "MOJO_BIN", Path("/missing/mojo"))
    monkeypatch.setattr(mojo_az, "ENGINE_DIR", Path("/tmp/engine"))

    command = mojo_az._mojo_run_command(Path("/tmp/test_lib.mojo"))

    assert command == [
        "/usr/bin/pixi",
        "run",
        "mojo",
        "run",
        "-I/tmp/engine",
        "/tmp/test_lib.mojo",
    ]


def test_pixi_binary_falls_back_to_home_install(monkeypatch, tmp_path) -> None:
    pixi_path = tmp_path / ".pixi" / "bin" / "pixi"
    pixi_path.parent.mkdir(parents=True)
    pixi_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(mojo_az.shutil, "which", lambda name: None)
    monkeypatch.delenv("PIXI_HOME", raising=False)
    monkeypatch.setattr(mojo_az, "_PROJECT_ROOT", Path("/missing-root"))
    monkeypatch.setattr(mojo_az.Path, "home", classmethod(lambda cls: tmp_path))

    assert mojo_az._pixi_binary() == str(pixi_path)


def test_pixi_binary_falls_back_to_repo_local_install(monkeypatch, tmp_path) -> None:
    pixi_path = tmp_path / ".pixi" / "bin" / "pixi"
    pixi_path.parent.mkdir(parents=True)
    pixi_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(mojo_az.shutil, "which", lambda name: None)
    monkeypatch.delenv("PIXI_HOME", raising=False)
    monkeypatch.setattr(mojo_az, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(mojo_az.Path, "home", classmethod(lambda cls: Path("/missing-home")))

    assert mojo_az._pixi_binary() == str(pixi_path)


def test_pixi_binary_honors_explicit_pixi_home(monkeypatch, tmp_path) -> None:
    pixi_home = tmp_path / "custom-pixi-home"
    pixi_path = pixi_home / "bin" / "pixi"
    pixi_path.parent.mkdir(parents=True)
    pixi_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(mojo_az.shutil, "which", lambda name: None)
    monkeypatch.setenv("PIXI_HOME", str(pixi_home))
    monkeypatch.setattr(mojo_az, "_PROJECT_ROOT", Path("/missing-root"))
    monkeypatch.setattr(mojo_az.Path, "home", classmethod(lambda cls: Path("/missing-home")))

    assert mojo_az._pixi_binary() == str(pixi_path)


def test_module_source_exists_handles_nested_and_allowed_imports(tmp_path) -> None:
    (tmp_path / "json").mkdir()
    (tmp_path / "json" / "parser.mojo").write_text("", encoding="utf-8")
    (tmp_path / "vector_kernels").mkdir()
    (tmp_path / "vector_kernels" / "__init__.mojo").write_text("", encoding="utf-8")

    assert mojo_az._module_source_exists("json.parser", tmp_path) is True
    assert mojo_az._module_source_exists("vector_kernels", tmp_path) is True
    assert mojo_az._module_source_exists("std.math", tmp_path) is True
    assert mojo_az._module_source_exists("conv", tmp_path) is False


def test_discover_missing_test_imports_reports_missing_modules(tmp_path) -> None:
    libs_dir = tmp_path / "libs"
    engine_dir = tmp_path / "engine"
    libs_dir.mkdir()
    engine_dir.mkdir()
    (engine_dir / "json").mkdir()
    (engine_dir / "json" / "parser.mojo").write_text("", encoding="utf-8")
    (libs_dir / "test_json_parser.mojo").write_text(
        "from json.parser import json_get_string\nfrom conv import parse_float64\n",
        encoding="utf-8",
    )

    missing = mojo_az._discover_missing_test_imports(libs_dir, engine_dir)

    assert missing == {
        "conv": ["test_json_parser.mojo"],
    }


def test_generated_test_inventory_needs_refresh_detects_drift(monkeypatch, tmp_path) -> None:
    libs_dir = tmp_path / "libs"
    libs_dir.mkdir()
    (libs_dir / "test_json_parser.mojo").write_text("", encoding="utf-8")
    (libs_dir / "test_stale.mojo").write_text("", encoding="utf-8")

    target = mojo_gen.ModuleTarget(
        path=tmp_path / "json" / "parser.mojo",
        import_path="json.parser",
        module_id="json_parser",
    )
    monkeypatch.setattr(
        mojo_az.mojo_test_gen,
        "build_generation_plan",
        lambda: [(target, [])],
    )

    assert mojo_az._generated_test_inventory_needs_refresh(libs_dir) is True


def test_generated_test_inventory_needs_refresh_accepts_matching_inventory(
    monkeypatch,
    tmp_path,
) -> None:
    libs_dir = tmp_path / "libs"
    libs_dir.mkdir()
    (libs_dir / "test_json_parser.mojo").write_text("", encoding="utf-8")

    target = mojo_gen.ModuleTarget(
        path=tmp_path / "json" / "parser.mojo",
        import_path="json.parser",
        module_id="json_parser",
    )
    monkeypatch.setattr(
        mojo_az.mojo_test_gen,
        "build_generation_plan",
        lambda: [(target, [])],
    )

    assert mojo_az._generated_test_inventory_needs_refresh(libs_dir) is False


def test_parse_library_ignores_docstring_api_examples(tmp_path) -> None:
    module_path = tmp_path / "url.mojo"
    module_path.write_text(
        '''"""
Public API:
  fn url_parse()    — parse a URL string into components
  fn url_to_string()— reconstruct URL from components
"""

fn url_parse(raw: String) -> Int:
    return 1
''',
        encoding="utf-8",
    )

    sigs = mojo_gen.parse_library(
        module_path,
        module_id="url",
        import_path="url",
    )

    assert sigs == [
        mojo_gen.FnSig(
            name="url_parse",
            params=[mojo_gen.Param(name="raw", typ="String", has_default=False, is_mut=False)],
            ret="Int",
            module_id="url",
            import_path="url",
        )
    ]


def test_discover_library_modules_skips_internal_compatibility_modules(tmp_path) -> None:
    (tmp_path / "conv.mojo").write_text("fn parse_float64(s: String) -> Float64:\n    return 0.0\n")
    (tmp_path / "math_ext.mojo").write_text(
        "fn mean(data: List[Float64]) -> Float64:\n    return 0.0\n"
    )
    (tmp_path / "runtime_library_dispatch_generated.mojo").write_text(
        "fn dispatch_runtime_library(module_name: String, function_name: String, args_array: String) -> String:\n    return module_name\n",
        encoding="utf-8",
    )
    (tmp_path / "sha256.mojo").write_text(
        "fn sha256_hex(data: String) -> String:\n    return data\n"
    )
    (tmp_path / "json").mkdir()
    (tmp_path / "json" / "parser.mojo").write_text(
        "fn json_get_int(raw: String, key: String, default: Int) -> Int:\n    return default\n",
        encoding="utf-8",
    )

    modules = mojo_gen.discover_library_modules(tmp_path)

    assert [module.import_path for module in modules] == ["json.parser"]


def test_is_testable_uses_crypto_input_shape_overrides() -> None:
    aes_sig = mojo_gen.FnSig(
        name="shift_rows",
        params=[mojo_gen.Param(name="state", typ="List[Int]", has_default=False, is_mut=False)],
        ret="List[Int]",
        module_id="crypto_aes_sbox",
        import_path="crypto.aes_sbox",
    )
    chacha_sig = mojo_gen.FnSig(
        name="chacha20_encrypt",
        params=[
            mojo_gen.Param(name="plaintext", typ="List[Int]", has_default=False, is_mut=False),
            mojo_gen.Param(name="key", typ="List[Int]", has_default=False, is_mut=False),
            mojo_gen.Param(name="nonce", typ="List[Int]", has_default=False, is_mut=False),
        ],
        ret="List[Int]",
        module_id="crypto_chacha20",
        import_path="crypto.chacha20",
    )

    assert mojo_gen._is_testable(aes_sig) == (True, ["_li16"])
    assert mojo_gen._is_testable(chacha_sig) == (True, ["_li16", "_li8", "_li3"])


def test_is_testable_uses_safe_domain_specific_overrides() -> None:
    shapley_sig = mojo_gen.FnSig(
        name="shapley_value_3player",
        params=[mojo_gen.Param(name="v", typ="List[Float64]", has_default=False, is_mut=False)],
        ret="List[Float64]",
        module_id="game_theory",
        import_path="game_theory",
    )
    borda_sig = mojo_gen.FnSig(
        name="borda_score",
        params=[
            mojo_gen.Param(name="ranks", typ="List[Int]", has_default=False, is_mut=False),
            mojo_gen.Param(name="n_candidates", typ="Int", has_default=False, is_mut=False),
            mojo_gen.Param(name="candidate_idx", typ="Int", has_default=False, is_mut=False),
        ],
        ret="Int",
        module_id="voting",
        import_path="voting",
    )

    assert mojo_gen._is_testable(shapley_sig) == (True, ["_lf8_coalitions"])
    assert mojo_gen._is_testable(borda_sig) == (True, ["_li10_borda", "5", "2"])
    assert "runtime_library_dispatch_generated" in mojo_gen.SKIP_IMPORT_PATHS


def test_kernel_harness_understands_generator_safe_sample_names() -> None:
    assert kernel_az._expr_to_python_value("_li6_grid2x3") == [0, 1, 0, 1, 1, 0]
    assert kernel_az._expr_to_python_value("_li10_borda") == [0, 1, 2, 3, 4, 1, 0, 2, 4, 3]
    assert kernel_az._expr_to_python_value("_lf8_coalitions") == [
        0.0,
        1.0,
        2.0,
        4.0,
        3.0,
        5.0,
        6.0,
        9.0,
    ]
