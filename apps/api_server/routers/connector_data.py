"""
Connector data endpoints — fetch data from external sources and auto-map to simulations.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/v1/connectors", tags=["connectors"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ConnectorFetchRequest(BaseModel):
    """Body for POST /v1/connectors/fetch."""

    connector_type: str  # "rest_api", "sql", "file"
    config: dict[str, Any]
    domain: str = ""  # Optional domain hint for better field mapping
    auto_simulate: bool = False  # If true, run simulation immediately
    simulation_config: dict[str, Any] | None = None  # Override auto-detected settings


class ConnectorFetchResponse(BaseModel):
    """Response for POST /v1/connectors/fetch."""

    records_fetched: int
    fields_detected: list[str]
    simulation_payload: dict[str, Any]
    connector_metadata: dict[str, Any]


class ConnectorTestRequest(BaseModel):
    """Body for POST /v1/connectors/test."""

    connector_type: str
    config: dict[str, Any]


class ConnectorTestResponse(BaseModel):
    """Response for POST /v1/connectors/test."""

    success: bool
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/fetch", response_model=ConnectorFetchResponse)
async def fetch_and_map(request: ConnectorFetchRequest) -> ConnectorFetchResponse:
    """
    Fetch data from an external source and auto-map to simulation variables.

    Supports: ``rest_api``, ``sql``, ``file``

    The engine's FieldMapper auto-detects:
    - Variable names from field names
    - Distribution types from value ranges
    - Positive/negative polarity from semantics
    - Objective function from field polarities
    """
    from apps.api_server.connectors import ConnectorRegistry

    try:
        connector = ConnectorRegistry.create(request.connector_type, request.config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        data = await connector.fetch_data()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch data: {str(exc)}",
        ) from exc

    if not data:
        raise HTTPException(status_code=404, detail="No data returned from source")

    # Auto-map to simulation payload
    payload = await connector.map_to_simulation(data, domain=request.domain)

    # Apply overrides if provided
    if request.simulation_config:
        for key, value in request.simulation_config.items():
            if value is not None:
                payload[key] = value

    return ConnectorFetchResponse(
        records_fetched=len(data),
        fields_detected=list(data[0].keys()) if data else [],
        simulation_payload=payload,
        connector_metadata=payload.pop("_connector_metadata", {}),
    )


@router.post("/test", response_model=ConnectorTestResponse)
async def test_connection(request: ConnectorTestRequest) -> ConnectorTestResponse:
    """Test connectivity to a data source without fetching full data."""
    from apps.api_server.connectors import ConnectorRegistry

    try:
        connector = ConnectorRegistry.create(request.connector_type, request.config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    success, message = await connector.validate_connection()
    return ConnectorTestResponse(success=success, message=message)


@router.get("/types")
async def list_connector_types() -> dict[str, list[str]]:
    """List all registered connector types."""
    from apps.api_server.connectors import ConnectorRegistry

    return {"types": ConnectorRegistry.available_types()}
