"""Tests for repository_intelligence_service: repository_intelligence_f.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_intelligence_lua_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        import_target: str,
        *,
        module_index: dict[str, str],
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "lua/acme/util.lua"

    monkeypatch.setattr(repository_service.lua_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"lua/acme/util.lua": "lua/acme/util.lua"}

    result = repository_service._resolve_lua_import("acme.util", module_index)

    assert result == "lua/acme/util.lua"
    assert observed["import_target"] == "acme.util"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_lua_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_suffix_match: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_suffix_match"] = resolve_suffix_match
        return ()

    monkeypatch.setattr(
        repository_service.lua_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"lua/acme/util.lua": "lua/acme/util.lua"}

    result = repository_service._parse_lua_dependencies_only(
        "lua/acme/core.lua",
        'local util = require "acme.util"',
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "lua/acme/core.lua"
    assert observed["text"] == 'local util = require "acme.util"'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_lua_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.lua_adapter, "parse_file", _fake_parse_file)

    module_index = {"lua/acme/util.lua": "lua/acme/util.lua"}

    result = repository_service._parse_lua_file(
        "lua/acme/core.lua",
        'local util = require "acme.util"',
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "lua/acme/core.lua"
    assert observed["text"] == 'local util = require "acme.util"'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_luau_helpers_are_modularized() -> None:
    assert repository_service.luau_adapter.has_luau_path_hints is (
        repository_luau_primitives.has_luau_path_hints
    )
    assert repository_service.luau_adapter.is_probable_luau_source is (
        repository_luau_primitives.is_probable_luau_source
    )
    assert repository_service.luau_adapter.collect_symbol_entries is (
        repository_luau_primitives.collect_symbol_entries
    )
    assert repository_service.luau_adapter.module_aliases_for_path is (
        repository_luau_analysis_support.module_aliases_for_path
    )
    assert repository_service.luau_adapter.parse_dependencies_only is (
        repository_luau_analysis_support.parse_dependencies_only
    )
    assert repository_service.luau_adapter.parse_file is (
        repository_luau_analysis_support.parse_file
    )
    assert repository_adapter_parser_dispatch.REGISTERED_ADAPTER_DEPENDENCY_PARSERS["luau"] is (
        repository_luau_parser_dispatch._parse_luau_dependencies_only
    )
    assert repository_adapter_parser_dispatch.REGISTERED_ADAPTER_FILE_PARSERS["luau"] is (
        repository_luau_parser_dispatch._parse_luau_file
    )


def test_repository_intelligence_shell_helpers_are_modularized() -> None:
    assert repository_service._SHELL_SOURCE_RE is repository_service.shell_adapter.SOURCE_RE
    assert repository_service._SHELL_CONTROL_PREFIXES is (
        repository_service.shell_adapter.CONTROL_PREFIXES
    )


def test_repository_intelligence_shell_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_source(
        *,
        current_file: str,
        source_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["source_target"] = source_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "scripts/lib.sh"

    monkeypatch.setattr(repository_service.shell_adapter, "resolve_source", _fake_resolve_source)

    module_index = {"scripts/lib.sh": "scripts/lib.sh"}

    result = repository_service._resolve_shell_source(
        current_file="scripts/main.sh",
        source_target="./lib.sh",
        module_index=module_index,
    )

    assert result == "scripts/lib.sh"
    assert observed["current_file"] == "scripts/main.sh"
    assert observed["source_target"] == "./lib.sh"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_shell_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return ()

    monkeypatch.setattr(
        repository_service.shell_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"scripts/lib.sh": "scripts/lib.sh"}

    result = repository_service._parse_shell_dependencies_only(
        "scripts/main.sh",
        "source ./lib.sh",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "scripts/main.sh"
    assert observed["text"] == "source ./lib.sh"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_shell_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(repository_service.shell_adapter, "parse_file", _fake_parse_file)

    module_index = {"scripts/lib.sh": "scripts/lib.sh"}

    result = repository_service._parse_shell_file(
        "scripts/main.sh",
        "source ./lib.sh",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "scripts/main.sh"
    assert observed["text"] == "source ./lib.sh"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_powershell_helpers_are_modularized() -> None:
    assert repository_service._POWERSHELL_DOT_SOURCE_RE is (
        repository_service.powershell_adapter.DOT_SOURCE_RE
    )
    assert repository_service._POWERSHELL_SOURCE_SUFFIXES is (
        repository_service.powershell_adapter.SOURCE_SUFFIXES
    )


def test_repository_intelligence_powershell_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "Modules/Acme/Acme.psm1"

    monkeypatch.setattr(
        repository_service.powershell_adapter,
        "resolve_import",
        _fake_resolve_import,
    )

    module_index = {"Modules/Acme/Acme.psm1": "Modules/Acme/Acme.psm1"}

    result = repository_service._resolve_powershell_import(
        current_file="Modules/Main.ps1",
        import_target="./Acme.psd1",
        module_index=module_index,
    )

    assert result == "Modules/Acme/Acme.psm1"
    assert observed["current_file"] == "Modules/Main.ps1"
    assert observed["import_target"] == "./Acme.psd1"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_powershell_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return ()

    monkeypatch.setattr(
        repository_service.powershell_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"Modules/Acme/Acme.psm1": "Modules/Acme/Acme.psm1"}

    result = repository_service._parse_powershell_dependencies_only(
        "Modules/Main.ps1",
        "Import-Module ./Acme.psd1",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "Modules/Main.ps1"
    assert observed["text"] == "Import-Module ./Acme.psd1"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_powershell_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return (), (), ()

    monkeypatch.setattr(
        repository_service.powershell_adapter,
        "parse_file",
        _fake_parse_file,
    )

    module_index = {"Modules/Acme/Acme.psm1": "Modules/Acme/Acme.psm1"}

    result = repository_service._parse_powershell_file(
        "Modules/Main.ps1",
        "Import-Module ./Acme.psd1",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "Modules/Main.ps1"
    assert observed["text"] == "Import-Module ./Acme.psd1"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_haskell_helpers_are_modularized() -> None:
    assert repository_service._HASKELL_MODULE_RE is repository_service.haskell_adapter.MODULE_RE
    assert repository_service._normalize_haskell_source_line is (
        repository_service.haskell_adapter.normalize_source_line
    )
    assert repository_service._haskell_module_aliases_for_path is (
        repository_service.haskell_adapter.module_aliases_for_path
    )


def test_repository_intelligence_haskell_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        import_target: str,
        module_index: dict[str, str],
        *,
        normalize_repository_relative_path: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return "src/Acme/Widget.hs"

    monkeypatch.setattr(repository_service.haskell_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"src/Acme/Widget.hs": "src/Acme/Widget.hs"}

    result = repository_service._resolve_haskell_import("Acme.Widget", module_index)

    assert result == "src/Acme/Widget.hs"
    assert observed["import_target"] == "Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_haskell_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.haskell_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/Acme/Widget.hs": "src/Acme/Widget.hs"}

    result = repository_service._parse_haskell_dependencies_only(
        "src/Acme/App.hs",
        "import Acme.Widget",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/Acme/App.hs"
    assert observed["text"] == "import Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_haskell_import


def test_repository_intelligence_haskell_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.haskell_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/Acme/Widget.hs": "src/Acme/Widget.hs"}

    result = repository_service._parse_haskell_file(
        "src/Acme/App.hs",
        "import Acme.Widget",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/Acme/App.hs"
    assert observed["text"] == "import Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_haskell_import


def test_repository_intelligence_clojure_helpers_are_modularized() -> None:
    assert repository_service._CLOJURE_NS_RE is repository_service.clojure_adapter.NS_RE
    assert repository_service._extract_clojure_ns_form is (
        repository_service.clojure_adapter.extract_ns_form
    )
    assert repository_service._clojure_module_aliases_for_path is (
        repository_service.clojure_adapter.module_aliases_for_path
    )


def test_repository_intelligence_clojure_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        import_target: str,
        module_index: dict[str, str],
        *,
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/acme/widget.clj"

    monkeypatch.setattr(repository_service.clojure_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"src/acme/widget.clj": "src/acme/widget.clj"}

    result = repository_service._resolve_clojure_import("acme.widget", module_index)

    assert result == "src/acme/widget.clj"
    assert observed["import_target"] == "acme.widget"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_clojure_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.clojure_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/acme/widget.clj": "src/acme/widget.clj"}

    result = repository_service._parse_clojure_dependencies_only(
        "src/acme/app.clj",
        "(ns acme.app (:require [acme.widget :as widget]))",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/acme/app.clj"
    assert observed["text"] == "(ns acme.app (:require [acme.widget :as widget]))"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_clojure_import


def test_repository_intelligence_clojure_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.clojure_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/acme/widget.clj": "src/acme/widget.clj"}

    result = repository_service._parse_clojure_file(
        "src/acme/app.clj",
        "(ns acme.app (:require [acme.widget :as widget]))",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/acme/app.clj"
    assert observed["text"] == "(ns acme.app (:require [acme.widget :as widget]))"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_clojure_import


def test_repository_intelligence_ocaml_helpers_are_modularized() -> None:
    assert repository_service._OCAML_OPEN_RE is repository_service.ocaml_adapter.OPEN_RE
    assert repository_service._ocaml_module_aliases_for_path is (
        repository_service.ocaml_adapter.module_aliases_for_path
    )


def test_repository_intelligence_ocaml_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_module(
        import_target: str,
        module_index: dict[str, str],
        *,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/widget.ml"

    monkeypatch.setattr(repository_service.ocaml_adapter, "resolve_module", _fake_resolve_module)

    module_index = {"src/widget.ml": "src/widget.ml"}

    result = repository_service._resolve_ocaml_module("Acme.Widget", module_index)

    assert result == "src/widget.ml"
    assert observed["import_target"] == "Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_ocaml_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module"] = resolve_module
        return ()

    monkeypatch.setattr(
        repository_service.ocaml_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/widget.ml": "src/widget.ml"}

    result = repository_service._parse_ocaml_dependencies_only(
        "src/app.ml",
        "open Acme.Widget",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/app.ml"
    assert observed["text"] == "open Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module"] is repository_service._resolve_ocaml_module


def test_repository_intelligence_ocaml_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module"] = resolve_module
        return (), (), ()

    monkeypatch.setattr(repository_service.ocaml_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/widget.ml": "src/widget.ml"}

    result = repository_service._parse_ocaml_file(
        "src/app.ml",
        "open Acme.Widget",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/app.ml"
    assert observed["text"] == "open Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module"] is repository_service._resolve_ocaml_module


def test_repository_intelligence_erlang_helpers_are_modularized() -> None:
    assert repository_service._ERLANG_MODULE_RE is repository_service.erlang_adapter.MODULE_RE
    assert repository_service._erlang_module_aliases_for_path is (
        repository_service.erlang_adapter.module_aliases_for_path
    )


