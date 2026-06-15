from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_native_dispatch as repository_native_dispatch,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_clarity_parser_dispatch_routes_to_native_lisp_wrapper() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["clarity"] is (
        repository_native_dispatch._parse_clarity_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["clarity"] is (
        repository_native_dispatch._parse_clarity_dependencies_only
    )


def test_clarity_language_detection_supports_contract_sources_without_overclaiming() -> None:
    assert ".clar" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("contracts/market.clar"),
            text=(
                "(define-public (mint (amount uint))\n"
                "  (ok amount))\n"
            ),
        )
        == "clarity"
    )
    assert (
        repository_service._language_for_path(
            Path("notes/example.clar"),
            text="<xml />\n",
        )
        == "unknown"
    )


def test_clarity_native_wrapper_extracts_symbols_and_cross_contract_dependencies() -> None:
    module_index = repository_service._build_module_index(
        ["contracts/traits.clar", "contracts/market.clar"],
        root_path=Path("/tmp/clarity-index"),
    )
    text = (
        '(use-trait nft-trait .traits.nft-trait)\n'
        '(define-public (mint (amount uint))\n'
        '  (ok amount))\n'
    )

    symbols, dependencies, references = repository_native_dispatch._parse_clarity_file(
        "contracts/market.clar",
        text,
        module_index,
    )

    assert any(symbol.symbol_name == "mint" for symbol in symbols)
    assert any(dependency.target_file == "contracts/traits.clar" for dependency in dependencies)
    assert any(reference.target_file == "contracts/traits.clar" for reference in references)


def test_operational_seed_plan_without_diagnostics_promotes_clarity_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "clarity-profile-repo"
    contracts_dir = repo_path / "contracts"
    contracts_dir.mkdir(parents=True)
    for name in ("market", "token", "vault", "registry", "dao", "traits"):
        (contracts_dir / f"{name}.clar").write_text(
            (
                f"(define-public ({name}-entry)\n"
                "  (ok true))\n"
            ),
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "def helper() -> int:\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "clarity" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "clarity"

