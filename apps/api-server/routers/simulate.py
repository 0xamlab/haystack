"""POST /v1/simulate — core simulation endpoint."""
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.schemas.response import DecisionEnvelope
from apps.api_server.schemas.simulate import SimulateRequest
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.simulation_service import run_simulation

router = APIRouter(tags=["Simulation"])


@router.post(
    "/v1/simulate",
    response_model=DecisionEnvelope,
    status_code=200,
    summary="Run a simulation",
    description=(
        "Execute a Monte Carlo simulation and receive a structured decision envelope. "
        "Use `mode: 'auto'` for minimal setup or `mode: 'expert'` for full control "
        "over distributions, correlations, and scoring."
    ),
    responses={
        200: {"description": "Simulation completed successfully"},
        401: {"description": "Authentication required or invalid API key"},
        422: {"description": "Request validation failed"},
        429: {"description": "Quota exceeded"},
        500: {"description": "Engine error"},
    },
)
async def simulate(
    request: Request,
    payload: SimulateRequest,
    auth: AuthContext = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> DecisionEnvelope:
    """
    Run a simulation and return a decision envelope.

    Supports both **auto** mode (minimal input, engine infers distributions)
    and **expert** mode (full control over all parameters).
    """
    envelope = await run_simulation(
        request=payload,
        org_id=auth["org_id"],
        api_key_id=auth["key_id"],
        db=db,
    )

    # Attach run_id to request state for logging
    request.state.run_id = envelope.run_id

    return envelope
