"""
/runs Router - Run Viewer API.

Endpoints:
- GET /runs: List runs for actor
- GET /runs/{id}: Get run details
- GET /runs/{id}/steps: Get step timeline
- GET /runs/{id}/artifacts: Get run artifacts
- GET /runs/{id}/stats: Get run statistics

Agent: api-scaffolding/fastapi-pro
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apps.core_api.deps import get_current_actor, get_postgres_store

router = APIRouter()


class RunListResponse(BaseModel):
    """List of runs."""

    runs: list[dict]
    total: int
    limit: int
    offset: int


class RunDetailResponse(BaseModel):
    """Single run details."""

    id: str
    actor: str
    status: str
    autonomy_level: str | None
    trace_id: str
    request_payload: dict
    artifacts: list[dict]
    created_at: str
    completed_at: str | None
    error_message: str | None


class StepListResponse(BaseModel):
    """List of steps."""

    run_id: str
    steps: list[dict]


class ArtifactListResponse(BaseModel):
    """List of artifacts."""

    run_id: str
    artifacts: list[dict]


class RunStatsResponse(BaseModel):
    """Run statistics."""

    run_id: str
    status: str
    step_count: int
    llm_calls: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    duration_seconds: float | None


@router.get("", response_model=RunListResponse)
async def list_runs(
    actor: str = Depends(get_current_actor),
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    store = Depends(get_postgres_store),
):
    """
    List runs for authenticated actor.

    Query parameters:
    - status: Filter by status (pending, running, completed, failed)
    - limit: Max results (default: 50)
    - offset: Pagination offset (default: 0)
    """
    try:
        runs = await store.list_runs(actor=actor, status=status, limit=limit, offset=offset)
        total = await store.count_runs(actor=actor, status=status)

        return RunListResponse(runs=runs, total=total, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(500, f"Failed to list runs: {str(e)}")


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: str,
    actor: str = Depends(get_current_actor),
    store = Depends(get_postgres_store),
):
    """
    Get run details with artifacts.

    Verifies the actor owns the run before returning details.
    """
    try:
        run = await store.get_run(run_id)

        if not run:
            raise HTTPException(404, "Run not found")

        # Verify actor owns this run
        if run["actor"] != actor:
            raise HTTPException(403, "Access denied")

        # Get artifacts
        artifacts = await store.get_artifacts(run_id)

        return RunDetailResponse(
            id=run["id"],
            actor=run["actor"],
            status=run["status"],
            autonomy_level=run["autonomy_level"],
            trace_id=run["trace_id"],
            request_payload=run["request_payload"],
            artifacts=artifacts,
            created_at=run["created_at"],
            completed_at=run["completed_at"],
            error_message=run["error_message"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to get run: {str(e)}")


@router.get("/{run_id}/steps", response_model=StepListResponse)
async def get_run_steps(
    run_id: str,
    actor: str = Depends(get_current_actor),
    store = Depends(get_postgres_store),
):
    """
    Get detailed step timeline for a run.

    Returns all steps in chronological order with input/output data.
    """
    try:
        # Verify run exists and actor owns it
        run = await store.get_run(run_id)
        if not run:
            raise HTTPException(404, "Run not found")

        if run["actor"] != actor:
            raise HTTPException(403, "Access denied")

        # Get steps
        steps = await store.get_steps(run_id)

        return StepListResponse(run_id=run_id, steps=steps)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to get steps: {str(e)}")


@router.get("/{run_id}/artifacts", response_model=ArtifactListResponse)
async def get_run_artifacts(
    run_id: str,
    actor: str = Depends(get_current_actor),
    store = Depends(get_postgres_store),
):
    """
    Get all artifacts for a run.

    Returns artifact metadata including URLs for accessing stored files.
    """
    try:
        # Verify run exists and actor owns it
        run = await store.get_run(run_id)
        if not run:
            raise HTTPException(404, "Run not found")

        if run["actor"] != actor:
            raise HTTPException(403, "Access denied")

        # Get artifacts
        artifacts = await store.get_artifacts(run_id)

        return ArtifactListResponse(run_id=run_id, artifacts=artifacts)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to get artifacts: {str(e)}")


@router.get("/{run_id}/stats", response_model=RunStatsResponse)
async def get_run_stats(
    run_id: str,
    actor: str = Depends(get_current_actor),
    store = Depends(get_postgres_store),
):
    """
    Get aggregate statistics for a run.

    Includes:
    - Step count
    - LLM call count and token usage
    - Total duration
    """
    try:
        # Verify run exists and actor owns it
        run = await store.get_run(run_id)
        if not run:
            raise HTTPException(404, "Run not found")

        if run["actor"] != actor:
            raise HTTPException(403, "Access denied")

        # Get stats
        stats = await store.get_run_stats(run_id)

        if not stats:
            raise HTTPException(500, "Failed to compute stats")

        return RunStatsResponse(**stats)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to get stats: {str(e)}")
