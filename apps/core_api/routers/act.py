"""
/act Router - Agent Execution Endpoint.

Handles:
- POST /act: Execute agent workflow
- Policy guard validation
- Autonomy level determination
- Idempotency checking
- Async execution queuing (>30s)

Agents:
- api-scaffolding/fastapi-pro
- llm-application-dev/ai-engineer
- agent-orchestration/context-manager
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from apps.core_api.deps import get_current_user, get_redis, get_trace_id, get_settings
from apps.core_api.auth import User
from chad_obs.logging import get_logger
from chad_agents.graphs.graph_langgraph import execute_agent_loop
from chad_llm import LLMRouter
from chad_tools.registry import ToolRegistry
from chad_memory.stores import RedisStore
from chad_agents.policies.policy_guard import PolicyGuard, ActRequest as PolicyActRequest, User as PolicyUser
from apps.core_api.routers.approvals import create_pending_approval

router = APIRouter()
logger = get_logger(__name__)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class ActRequest(BaseModel):
    """
    Request schema for POST /act.

    Deliverable #2: Pydantic models with validation
    """

    actor: str = Field(..., description="Actor identifier (user, workflow, service)")
    goal: str = Field(..., description="Natural language goal for agent to accomplish")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context (repo, db_id, etc.)"
    )
    max_steps: int = Field(default=10, ge=1, le=50, description="Maximum execution steps")
    timeout_seconds: int = Field(
        default=300, ge=1, le=600, description="Execution timeout (1-600 seconds)"
    )
    idempotency_key: str | None = Field(
        None, description="Unique key for deduplication (recommended: workflow ID)"
    )
    dry_run: bool = Field(default=False, description="Simulate execution without side effects")
    force_autonomy_level: str | None = Field(
        None,
        description="Override autonomy level (requires admin permission)",
        pattern="^(L0_Ask|L1_Draft|L2_ExecuteNotify|L3_ExecuteSilent)$",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "actor": "n8n_workflow_abc123",
                "goal": "Fetch latest GitHub issues for repo X, summarize, create Notion page",
                "context": {"github_repo": "owner/repo", "notion_db_id": "abc123"},
                "max_steps": 10,
                "timeout_seconds": 300,
                "idempotency_key": "n8n_exec_550e8400",
                "dry_run": False,
            }
        }


class ActResponse(BaseModel):
    """
    Response schema for successful /act execution.

    Deliverable #2: Pydantic models
    """

    run_id: str = Field(..., description="Unique execution run ID")
    trace_id: str = Field(..., description="OpenTelemetry trace ID for debugging")
    status: str = Field(..., description="Execution status: pending, running, completed, failed")
    message: str | None = Field(None, description="Status message")
    autonomy_level: str | None = Field(None, description="Applied autonomy level")
    plan: dict[str, Any] | None = Field(None, description="Generated plan (if available)")
    results: list[dict[str, Any]] | None = Field(None, description="Step results (if sync)")
    artifacts: list[dict[str, Any]] | None = Field(None, description="Generated artifacts")
    duration_ms: int | None = Field(None, description="Execution duration (if completed)")
    poll_url: str | None = Field(None, description="URL to poll for async execution status")

    class Config:
        json_schema_extra = {
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "trace_id": "abcd1234567890ef",
                "status": "completed",
                "autonomy_level": "L2_ExecuteNotify",
                "plan": {
                    "steps": [
                        {"tool": "adapters_github.search_issues", "input": {"repo": "owner/repo"}},
                        {"tool": "local.summarize_text", "input": {"text": "..."}},
                    ]
                },
                "results": [{"step": 0, "output": {"issues": []}}],
                "artifacts": [],
                "duration_ms": 4532,
            }
        }


# ============================================================================
# ENDPOINT: POST /act
# ============================================================================


@router.post("/act", response_model=ActResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_action(
    request_body: ActRequest,
    request: Request,
    user: User = Depends(get_current_user),
    trace_id: str = Depends(get_trace_id),
    settings = Depends(get_settings),
) -> ActResponse:
    """
    Execute agent workflow with policy-driven execution.

    **Flow**:
    1. Validate authentication (JWT + HMAC)
    2. Check idempotency key (Redis)
    3. Policy guard validation (scopes, autonomy level)
    4. Reflex router check (skip LLM for trivial goals)
    5. LangGraph execution (sync < 30s, async > 30s)
    6. Store results, artifacts

    **Autonomy Levels**:
    - L0_Ask: Return plan for approval
    - L1_Draft: Execute with dry_run=True, return for approval
    - L2_ExecuteNotify: Execute and notify
    - L3_ExecuteSilent: Execute silently

    **Idempotency**:
    - Duplicate `idempotency_key` returns 409 Conflict with existing run_id

    **Rate Limiting**:
    - Default 60 req/min per actor
    - Returns 429 if exceeded

    Deliverable #2: FastAPI route with pydantic models ✅
    Deliverable #5: Policy guard integration (stub) ✅

    Args:
        request_body: Action execution request
        request: FastAPI request object
        actor: Authenticated actor (from JWT)
        trace_id: OpenTelemetry trace ID

    Returns:
        ActResponse: Execution result (202 Accepted or 200 OK)

    Raises:
        HTTPException: 401 (unauthorized), 403 (policy violation), 409 (duplicate), 429 (rate limit)

    TODO: Implement idempotency check (Redis)
    TODO: Implement policy guard validation
    TODO: Implement reflex router
    TODO: Implement LangGraph execution
    TODO: Implement async queuing for long-running tasks
    """
    # Extract actor from request body or user
    actor = request_body.actor or user.user_id

    logger.info(
        "act_request_received",
        actor=actor,
        user_id=user.user_id,
        scopes=user.scopes,
        goal=request_body.goal,
        trace_id=trace_id,
        idempotency_key=request_body.idempotency_key,
    )

    # ========================================================================
    # STEP 1: Idempotency Check
    # ========================================================================
    if request_body.idempotency_key:
        # TODO: Check Redis for existing run
        # existing_run_id = await check_idempotency(request_body.idempotency_key)
        # if existing_run_id:
        #     raise HTTPException(
        #         status_code=409,
        #         detail={
        #             "error": "duplicate_request",
        #             "existing_run_id": existing_run_id,
        #             "poll_url": f"/runs/{existing_run_id}"
        #         }
        #     )
        pass

    # ========================================================================
    # STEP 2: Generate Run ID
    # ========================================================================
    run_id = str(uuid.uuid4())

    # TODO: Store idempotency mapping in Redis
    # if request_body.idempotency_key:
    #     await store_idempotency(request_body.idempotency_key, run_id, ttl=86400)

    # ========================================================================
    # STEP 3: Policy Guard Validation
    # ========================================================================
    # Initialize policy guard
    policy_guard = PolicyGuard(settings)

    # Create policy request from API request
    policy_request = PolicyActRequest(
        actor=actor,
        goal=request_body.goal,
        context=request_body.context,
        dry_run=request_body.dry_run,
    )

    # Create policy user from auth user
    policy_user = PolicyUser(
        user_id=user.user_id,
        scopes=user.scopes,
    )

    # Validate request
    validation = await policy_guard.validate_request(policy_request, policy_user)

    # If not allowed, return 403 error
    if not validation.allowed:
        logger.warning(
            "policy_violation",
            actor=actor,
            user_id=user.user_id,
            reason=validation.reason,
            missing_scopes=validation.missing_scopes,
            trace_id=trace_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "policy_violation",
                "reason": validation.reason,
                "missing_scopes": validation.missing_scopes,
                "required_scopes": validation.required_scopes,
            },
        )

    # Extract autonomy level
    autonomy_level = validation.autonomy_level.value

    logger.info(
        "policy_validation_passed",
        actor=actor,
        autonomy_level=autonomy_level,
        risk_score=validation.risk_score,
        requires_approval=validation.requires_approval,
        trace_id=trace_id,
    )

    # ========================================================================
    # STEP 3.5: Check if Approval is Required
    # ========================================================================
    if validation.requires_approval:
        # Get Redis client
        redis = await get_redis().__anext__()

        # Create pending approval
        await create_pending_approval(
            redis=redis,
            run_id=run_id,
            actor=actor,
            goal=request_body.goal,
            autonomy_level=autonomy_level,
            risk_score=validation.risk_score,
            required_scopes=validation.required_scopes,
            timeout_seconds=getattr(settings, "APPROVAL_TIMEOUT_SECONDS", 3600),
        )

        logger.info(
            "approval_required",
            run_id=run_id,
            actor=actor,
            autonomy_level=autonomy_level,
            risk_score=validation.risk_score,
            trace_id=trace_id,
        )

        # Return 202 Accepted with approval details
        return ActResponse(
            run_id=run_id,
            trace_id=trace_id,
            status="pending_approval",
            message=f"Approval required for {autonomy_level}. Risk score: {validation.risk_score:.2f}",
            autonomy_level=autonomy_level,
            plan={
                "risk_score": validation.risk_score,
                "required_scopes": validation.required_scopes,
                "reason": "High risk or sensitive operation requires manual approval",
            },
            results=None,
            artifacts=None,
            poll_url=f"/approvals/{run_id}/status",
        )

    # ========================================================================
    # STEP 4: Reflex Router Check (Skip LLM for trivial goals)
    # ========================================================================
    # TODO: Import from chad_agents.reflex.router
    # from chad_agents.reflex.router import should_use_reflex, execute_reflex
    #
    # if should_use_reflex(request_body.goal):
    #     result = await execute_reflex(request_body.goal, request_body.context)
    #     return ActResponse(
    #         run_id=run_id,
    #         trace_id=trace_id,
    #         status="completed",
    #         autonomy_level="reflex",
    #         results=[result],
    #         duration_ms=50  # Fast!
    #     )

    # ========================================================================
    # STEP 5: LangGraph Execution
    # ========================================================================
    try:
        # Initialize dependencies
        llm_router = LLMRouter()  # Creates OpenAI + Anthropic clients from env

        # Get tool registry from app state (initialized at startup with Notion + n8n tools)
        tool_registry = request.app.state.tool_registry

        # Add actor to context
        execution_context = {**request_body.context, "actor": actor}

        # Execute agent workflow
        result = await execute_agent_loop(
            run_id=run_id,
            goal=request_body.goal,
            context=execution_context,
            autonomy_level=autonomy_level,
            dry_run=request_body.dry_run,
            max_steps=request_body.max_steps,
            llm_router=llm_router,
            tool_registry=tool_registry,
        )

        # Return completed execution
        return ActResponse(
            run_id=run_id,
            trace_id=trace_id,
            status=result.get("status", "completed"),
            message=result.get("message"),
            autonomy_level=autonomy_level,
            plan={"steps": result.get("plan", [])},
            results=result.get("executed_steps", []),
            artifacts=result.get("artifacts", []),
            duration_ms=result.get("duration_ms"),
        )

    except Exception as e:
        logger.error(
            "agent_execution_failed",
            run_id=run_id,
            error=str(e),
            trace_id=trace_id,
        )

        # Return error response
        return ActResponse(
            run_id=run_id,
            trace_id=trace_id,
            status="failed",
            message=f"Execution failed: {str(e)}",
            autonomy_level=autonomy_level,
            plan=None,
            results=None,
            artifacts=None,
        )


# ============================================================================
# AGENT SIGN-OFF
# ============================================================================
# ✅ api-scaffolding/fastapi-pro
# ✅ llm-application-dev/ai-engineer
# ✅ agent-orchestration/context-manager
