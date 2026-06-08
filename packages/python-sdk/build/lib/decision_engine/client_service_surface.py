from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "batch": ("decision_engine.client_simulation_surface", "batch"),
    "cancel_job": ("decision_engine.client_job_surface", "cancel_job"),
    "compare": ("decision_engine.client_simulation_surface", "compare"),
    "create_api_key": ("decision_engine.client_account_surface", "create_api_key"),
    "distributions": ("decision_engine.client_account_surface", "distributions"),
    "explain": ("decision_engine.client_query_surface", "explain"),
    "get_job": ("decision_engine.client_job_surface", "get_job"),
    "get_job_result": ("decision_engine.client_job_surface", "get_job_result"),
    "list_jobs": ("decision_engine.client_job_surface", "list_jobs"),
    "health": ("decision_engine.client_account_surface", "health"),
    "limits": ("decision_engine.client_account_surface", "limits"),
    "list_team_members": (
        "decision_engine.client_control_plane_surface",
        "list_team_members",
    ),
    "get_audit_logs": ("decision_engine.client_control_plane_surface", "get_audit_logs"),
    "invite_team_member": (
        "decision_engine.client_control_plane_surface",
        "invite_team_member",
    ),
    "get_execution_policy": (
        "decision_engine.client_control_plane_surface",
        "get_execution_policy",
    ),
    "list_execution_policy_snapshots": (
        "decision_engine.client_control_plane_surface",
        "list_execution_policy_snapshots",
    ),
    "list_devices": ("decision_engine.client_control_plane_surface", "list_devices"),
    "list_api_keys": ("decision_engine.client_account_surface", "list_api_keys"),
    "me": ("decision_engine.client_account_surface", "me"),
    "poll_job": ("decision_engine.client_job_surface", "poll_job"),
    "query": ("decision_engine.client_query_surface", "query"),
    "recommend": ("decision_engine.client_simulation_surface", "recommend"),
    "refresh_source": ("decision_engine.client_source_surface", "refresh_source"),
    "register_source": ("decision_engine.client_source_surface", "register_source"),
    "resolve": ("decision_engine.client_query_surface", "resolve"),
    "revoke_api_key": ("decision_engine.client_account_surface", "revoke_api_key"),
    "remove_team_member": (
        "decision_engine.client_control_plane_surface",
        "remove_team_member",
    ),
    "revoke_device": ("decision_engine.client_control_plane_surface", "revoke_device"),
    "score": ("decision_engine.client_simulation_surface", "score"),
    "simulate": ("decision_engine.client_simulation_surface", "simulate"),
    "submit_job": ("decision_engine.client_job_surface", "submit_job"),
    "templates": ("decision_engine.client_account_surface", "templates"),
    "update_execution_policy": (
        "decision_engine.client_control_plane_surface",
        "update_execution_policy",
    ),
    "update_team_member_role": (
        "decision_engine.client_control_plane_surface",
        "update_team_member_role",
    ),
    "usage": ("decision_engine.client_account_surface", "usage"),
    "verify": ("decision_engine.client_query_surface", "verify"),
    "version": ("decision_engine.client_account_surface", "version"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(
            f"module 'decision_engine.client_service_surface' has no attribute '{name}'"
        )
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
