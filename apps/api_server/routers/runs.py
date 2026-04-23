"""GET /v1/runs — simulation run history for the authenticated org."""
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.middleware.auth import AuthContext, get_current_org
from apps.api_server.models.simulation_run import SimulationRun

router = APIRouter(tags=["Runs"])


class RunSummary(BaseModel):
    run_id: str
    mode: str
    status: str
    scenarios_run: int | None = None
    duration_ms: int | None = None
    # Output hash: SHA-256 of decision envelope (tamper detection on output)
    result_hash: str | None = None
    # Input hash: SHA-256 of simulation request payload (tamper detection on input)
    request_hash: str | None = None
    execution_type: str
    created_at: datetime
    completed_at: datetime | None = None
    # Decision outcome fields (populated after migration 0006)
    recommended_action: str | None = None
    confidence: float | None = None
    expected_value: float | None = None
    probability_of_loss: float | None = None
    std_deviation: float | None = None
    rationale: str | None = None

    model_config = {"from_attributes": True}


class RunsResponse(BaseModel):
    runs: list[RunSummary]
    total: int
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=200)
    pages: int


class AnalyticsSummary(BaseModel):
    """Aggregated analytics for dashboard charts."""
    total_runs: int
    runs_by_day: list[dict]      # [{date, count}]
    runs_by_status: dict[str, int]
    runs_by_mode: dict[str, int]
    avg_duration_ms: float | None
    p95_duration_ms: int | None


@router.get(
    "/v1/runs",
    response_model=RunsResponse,
    summary="List simulation runs for this org",
)
async def list_runs(
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int | None = Query(default=None, ge=0),
    status: str | None = Query(default=None),
    mode: str | None = Query(default=None),
) -> RunsResponse:
    """Return paginated simulation run history for the authenticated org."""
    base_q = select(SimulationRun).where(SimulationRun.org_id == auth["org_id"])

    if status:
        base_q = base_q.where(SimulationRun.status == status)
    if mode:
        base_q = base_q.where(SimulationRun.mode == mode)

    count_q = select(func.count()).select_from(base_q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    effective_offset = offset if offset is not None else (page - 1) * limit
    effective_page = page if offset is None else (effective_offset // limit) + 1
    items_q = base_q.order_by(desc(SimulationRun.created_at)).offset(effective_offset).limit(limit)
    result = await db.execute(items_q)
    runs = result.scalars().all()

    return RunsResponse(
        runs=[
            RunSummary(
                run_id=str(r.id),
                mode=r.mode.value,
                status=r.status.value,
                scenarios_run=r.scenarios_run,
                duration_ms=r.duration_ms,
                result_hash=r.result_hash,
                execution_type=r.execution_type.value,
                created_at=r.created_at,
                completed_at=r.completed_at,
                recommended_action=r.recommended_action,
                confidence=r.confidence,
                expected_value=r.expected_value,
                probability_of_loss=r.probability_of_loss,
                std_deviation=r.std_deviation,
                rationale=r.rationale,
            )
            for r in runs
        ],
        total=total,
        page=effective_page,
        limit=limit,
        pages=max(1, (total + limit - 1) // limit),
    )


@router.get(
    "/v1/runs/{run_id}",
    response_model=RunSummary,
    summary="Get a single simulation run",
)
async def get_run(
    run_id: UUID,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RunSummary:
    """Return details for a single simulation run (org-scoped)."""
    from fastapi import HTTPException

    result = await db.execute(
        select(SimulationRun).where(
            SimulationRun.id == run_id,
            SimulationRun.org_id == auth["org_id"],
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "Run not found."}},
        )
    return RunSummary(
        run_id=str(run.id),
        mode=run.mode.value,
        status=run.status.value,
        scenarios_run=run.scenarios_run,
        duration_ms=run.duration_ms,
        result_hash=run.result_hash,
        execution_type=run.execution_type.value,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


@router.get(
    "/v1/analytics",
    response_model=AnalyticsSummary,
    summary="Aggregated analytics for dashboard charts",
)
async def get_analytics(
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    days: int = Query(default=30, ge=1, le=365),
) -> AnalyticsSummary:
    """
    Return aggregated analytics using real SQL GROUP BY — O(1) in DB, not O(n) in Python.
    """
    from datetime import timedelta

    from sqlalchemy import Date, cast

    since = datetime.now(tz=UTC) - timedelta(days=days)

    # ── Total count ────────────────────────────────────────────────────────────
    total_result = await db.execute(
        select(func.count(SimulationRun.id)).where(
            SimulationRun.org_id == auth["org_id"],
            SimulationRun.created_at >= since,
        )
    )
    total = total_result.scalar_one() or 0

    # ── Runs by day — GROUP BY DATE ────────────────────────────────────────────
    day_result = await db.execute(
        select(
            cast(SimulationRun.created_at, Date).label("day"),
            func.count(SimulationRun.id).label("cnt"),
        )
        .where(
            SimulationRun.org_id == auth["org_id"],
            SimulationRun.created_at >= since,
        )
        .group_by(cast(SimulationRun.created_at, Date))
        .order_by(cast(SimulationRun.created_at, Date))
    )
    runs_by_day = [{"date": str(row.day), "count": row.cnt} for row in day_result]

    # ── By status ──────────────────────────────────────────────────────────────
    status_result = await db.execute(
        select(
            SimulationRun.status.label("st"),
            func.count(SimulationRun.id).label("cnt"),
        )
        .where(
            SimulationRun.org_id == auth["org_id"],
            SimulationRun.created_at >= since,
        )
        .group_by(SimulationRun.status)
    )
    by_status = {
        str(row.st.value if hasattr(row.st, "value") else row.st): row.cnt
        for row in status_result
    }

    # ── By mode ────────────────────────────────────────────────────────────────
    mode_result = await db.execute(
        select(
            SimulationRun.mode.label("md"),
            func.count(SimulationRun.id).label("cnt"),
        )
        .where(
            SimulationRun.org_id == auth["org_id"],
            SimulationRun.created_at >= since,
        )
        .group_by(SimulationRun.mode)
    )
    by_mode = {
        str(row.md.value if hasattr(row.md, "value") else row.md): row.cnt
        for row in mode_result
    }

    # ── By recommended_action (from migration 0006) ────────────────────────────
    action_result = await db.execute(
        select(
            SimulationRun.recommended_action.label("action"),
            func.count(SimulationRun.id).label("cnt"),
        )
        .where(
            SimulationRun.org_id == auth["org_id"],
            SimulationRun.created_at >= since,
            SimulationRun.recommended_action.isnot(None),
        )
        .group_by(SimulationRun.recommended_action)
    )
    for row in action_result:
        by_status[f"action_{row.action}"] = row.cnt

    # ── Latency stats (avg + p95 via percentile_cont) ─────────────────────────
    latency_result = await db.execute(
        select(
            func.avg(SimulationRun.duration_ms).label("avg_ms"),
            func.percentile_cont(0.95).within_group(
                SimulationRun.duration_ms
            ).label("p95_ms"),
        )
        .where(
            SimulationRun.org_id == auth["org_id"],
            SimulationRun.created_at >= since,
            SimulationRun.duration_ms.isnot(None),
        )
    )
    lat_row = latency_result.first()
    avg_dur = float(lat_row.avg_ms) if lat_row and lat_row.avg_ms is not None else None
    p95_dur = int(lat_row.p95_ms) if lat_row and lat_row.p95_ms is not None else None

    return AnalyticsSummary(
        total_runs=total,
        runs_by_day=runs_by_day,
        runs_by_status=by_status,
        runs_by_mode=by_mode,
        avg_duration_ms=avg_dur,
        p95_duration_ms=p95_dur,
    )
