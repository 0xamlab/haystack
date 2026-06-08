from apps.api_server.services import (
    simulation_output,
    simulation_payloads,
    simulation_service,
)


def test_simulation_service_reexports_payload_helpers() -> None:
    assert (
        simulation_service._build_auto_mojo_payload is simulation_payloads._build_auto_mojo_payload
    )
    assert (
        simulation_service._build_expert_mojo_payload
        is simulation_payloads._build_expert_mojo_payload
    )
    assert simulation_service._extract_unit_context is simulation_payloads._extract_unit_context
    assert simulation_service._copy_engine_variable is simulation_payloads._copy_engine_variable
    assert (
        simulation_service._normalize_decision_tree_override_variable
        is simulation_payloads._normalize_decision_tree_override_variable
    )
    assert (
        simulation_service._merge_decision_tree_variables
        is simulation_payloads._merge_decision_tree_variables
    )
    assert (
        simulation_service._flatten_decision_tree_paths
        is simulation_payloads._flatten_decision_tree_paths
    )
    assert (
        simulation_service._raise_decision_tree_validation_error
        is simulation_payloads._raise_decision_tree_validation_error
    )


def test_simulation_service_reexports_output_helpers() -> None:
    assert simulation_service._derive_recommendation is simulation_output._derive_recommendation
    assert (
        simulation_service._simulation_class_for_model
        is simulation_output._simulation_class_for_model
    )
    assert simulation_service._validated_input_summary is simulation_output._validated_input_summary
    assert simulation_service._map_engine_output is simulation_output._map_engine_output
    assert (
        simulation_service._fallback_decision_tree_result
        is simulation_output._fallback_decision_tree_result
    )
