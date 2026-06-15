from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_abapcds_parser_dispatch as repository_abapcds_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    abapcds_analysis_support as repository_abapcds_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    abapcds_primitives as repository_abapcds_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_abapcds_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["abapcds"] is (
        repository_abapcds_parser_dispatch._parse_abapcds_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["abapcds"] is (
        repository_abapcds_parser_dispatch._parse_abapcds_dependencies_only
    )


def test_repository_intelligence_abapcds_helpers_are_modularized() -> None:
    assert repository_service.abapcds_adapter.has_abapcds_path_hints is (
        repository_abapcds_primitives.has_abapcds_path_hints
    )
    assert repository_service.abapcds_adapter.is_probable_abapcds_source is (
        repository_abapcds_analysis_support.is_probable_abapcds_source
    )
    assert repository_service.abapcds_adapter.module_aliases_for_path is (
        repository_abapcds_analysis_support.module_aliases_for_path
    )
    assert repository_service.abapcds_adapter.parse_dependencies_only is (
        repository_abapcds_analysis_support.parse_dependencies_only
    )
    assert repository_service.abapcds_adapter.parse_file is (
        repository_abapcds_analysis_support.parse_file
    )


def test_abapcds_adapter_module_aliases_include_declared_entity_and_repository_stem(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "abapcds-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "#dmo#ana_i_flightcube.ddls.asddls").write_text(
        "define view entity /DMO/ANA_I_FlightCube\n"
        "  as select from /DMO/ANA_P_Flight\n"
        "{ key carrier_id as AirlineID }\n",
        encoding="utf-8",
    )

    aliases = repository_service.abapcds_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/#dmo#ana_i_flightcube.ddls.asddls",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/#dmo#ana_i_flightcube.ddls.asddls" in aliases
    assert "/DMO/ANA_I_FlightCube" in aliases
    assert "/dmo/ana_i_flightcube" in aliases
    assert "#dmo#ana_i_flightcube" in aliases


def test_abapcds_adapter_parse_file_resolves_projection_and_association_targets() -> None:
    module_index = repository_service._build_module_index(
        [
            "src/#dmo#ana_i_flightcube.ddls.asddls",
            "src/#dmo#ana_p_flight.ddls.asddls",
            "src/#dmo#ana_i_carrier.ddls.asddls",
        ],
        root_path=Path("/tmp/abapcds-index"),
    )
    text = (
        "define view entity /DMO/ANA_I_FlightCube\n"
        "  as select from /DMO/ANA_P_Flight\n"
        "  association [1..1] to /DMO/ANA_I_Carrier as _Airline on true = true\n"
        "{ key carrier_id as AirlineID }\n"
    )

    symbols, dependencies, references = repository_service.abapcds_adapter.parse_file(
        "src/#dmo#ana_i_flightcube.ddls.asddls",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        symbol.symbol_name == "/DMO/ANA_I_FlightCube" and symbol.symbol_kind == "entity"
        for symbol in symbols
    )
    assert any(
        dependency.target_file == "src/#dmo#ana_p_flight.ddls.asddls"
        and dependency.dependency_type == "selects_from"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "src/#dmo#ana_i_carrier.ddls.asddls"
        and dependency.dependency_type == "associates_to"
        for dependency in dependencies
    )
    assert any(reference.target_names == ("/DMO/ANA_P_Flight",) for reference in references)


def test_abapcds_language_detection_supports_asddls_sources_without_overclaiming() -> None:
    assert ".asddls" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("src/#dmo#ana_i_flightcube.ddls.asddls"),
            text="define view entity /DMO/ANA_I_FlightCube as select from /DMO/ANA_P_Flight { key carrier_id as AirlineID }\n",
        )
        == "abapcds"
    )
    assert (
        repository_service._language_for_path(
            Path("src/#dmo#ana_i_flightcube.ddls.asddls"),
            text="<xml />\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_abapcds_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "abapcds-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    for index in range(8):
        (repo_path / "src" / f"z_demo_entity_{index}.ddls.asddls").write_text(
            f"define view entity Z_DEMO_ENTITY_{index}\n"
            f"  as select from Z_DEMO_SOURCE_{index}\n"
            "{ key field_a as FieldA }\n",
            encoding="utf-8",
        )
    for index in range(2):
        (repo_path / "src" / f"z_demo_helper_{index}.clas.abap").write_text(
            "CLASS z_demo_helper DEFINITION PUBLIC.\nENDCLASS.\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "abapcds" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "abapcds"
