"""
Approval Workflow Router.

Handles:
- GET /approvals/pending: List pending approval requests
- POST /approvals/{run_id}/approve: Approve a pending run
- POST /approvals/{run_id}/reject: Reject a pending run
- GET /approvals/{run_id}/status: Check approval status

Uses Redis for storing approval state:
- Key: f"approval:{run_id}"
- Value: JSON with status, approved_by, timestamp, reason

Agent: Agent 3 (Policy Guard & Autonomy)
"""

import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from apps.core_api.deps import get_current_user, get_redis
from apps.core_api.auth import User
from chad_obs.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class ApprovalRequest(BaseModel):
    """Request to approve or reject a run."""

    action: Literal["approve", "reject"]
    reason: str | None = Field(None, description="Optional reason for approval/rejection")


class ApprovalResponse(BaseModel):
    """Response for approval status."""

    run_id: str
    status: str  # "pending", "approved", "rejected"
    approved_at: str | None = None
    approved_by: str | None = None
    rejected_at: str | None = None
    rejected_by: str | None = None
    reason: str | None = None


class PendingApprovalItem(BaseModel):
    """Pending approval item in list."""

    run_id: str
    actor: str
    goal: str
    autonomy_level: str
    risk_score: float
    required_scopes: list[str]
    created_at: str
    expires_at: str


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/pending", response_model=list[PendingApprovalItem])
async def list_pending_approvals(
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> list[PendingApprovalItem]:
    """
    List all pending approval requests.

    Returns:
        list[PendingApprovalItem]: List of pending approvals

    Example:
        GET /approvals/pending
        Authorization: Bearer <token>
    """
    try:
        # Search for all approval keys
        # NOTE: SCAN is more efficient than KEYS in production
        keys = await redis.keys("approval:*")

        pending = []
        for key in keys:
            data = await redis.get(key)
            if data:
                approval_data = json.loads(data)
                if approval_data.get("status") == "pending":
                    pending.append(
                        PendingApprovalItem(
                            run_id=approval_data.get("run_id"),
                            actor=approval_data.get("actor", "unknown"),
                            goal=approval_data.get("goal", ""),
                            autonomy_level=approval_data.get("autonomy_level", "L0_Ask"),
                            risk_score=approval_data.get("risk_score", 0.0),
                            required_scopes=approval_data.get("required_scopes", []),
                            created_at=approval_data.get("created_at", ""),
                            expires_at=approval_data.get("expires_at", ""),
                        )
                    )

        logger.info(
            "list_pending_approvals",
            user_id=user.user_id,
            count=len(pending),
        )

        return pending

    except Exception as e:
        logger.error(
            "list_pending_approvals_failed",
            user_id=user.user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list pending approvals: {str(e)}",
        )


@router.post("/{run_id}/approve", response_model=ApprovalResponse)
async def approve_run(
    run_id: str,
    request: ApprovalRequest,
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> ApprovalResponse:
    """
    Approve a pending run.

    Args:
        run_id: Run ID to approve
        request: Approval request with optional reason
        user: Current authenticated user
        redis: Redis connection

    Returns:
        ApprovalResponse: Updated approval status

    Raises:
        HTTPException: 404 if run not found, 400 if not pending

    Example:
        POST /approvals/550e8400-e29b-41d4-a716-446655440000/approve
        Authorization: Bearer <token>
        {
            "action": "approve",
            "reason": "Looks good to me"
        }
    """
    try:
        # Get existing approval data
        key = f"approval:{run_id}"
        data = await redis.get(key)

        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request not found for run_id: {run_id}",
            )

        approval_data = json.loads(data)

        # Check if already approved/rejected
        if approval_data.get("status") != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Run is already {approval_data.get('status')}",
            )

        # Update approval data
        approval_data["status"] = "approved"
        approval_data["approved_by"] = user.user_id
        approval_data["approved_at"] = datetime.now(timezone.utc).isoformat()
        approval_data["reason"] = request.reason

        # Save updated data (keep TTL)
        ttl = await redis.ttl(key)
        await redis.setex(key, max(ttl, 3600), json.dumps(approval_data))

        logger.info(
            "run_approved",
            run_id=run_id,
            approved_by=user.user_id,
            reason=request.reason,
        )

        return ApprovalResponse(
            run_id=run_id,
            status="approved",
            approved_at=approval_data["approved_at"],
            approved_by=approval_data["approved_by"],
            reason=approval_data.get("reason"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "approve_run_failed",
            run_id=run_id,
            user_id=user.user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve run: {str(e)}",
        )


@router.post("/{run_id}/reject", response_model=ApprovalResponse)
async def reject_run(
    run_id: str,
    request: ApprovalRequest,
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> ApprovalResponse:
    """
    Reject a pending run.

    Args:
        run_id: Run ID to reject
        request: Approval request with optional reason
        user: Current authenticated user
        redis: Redis connection

    Returns:
        ApprovalResponse: Updated approval status

    Raises:
        HTTPException: 404 if run not found, 400 if not pending

    Example:
        POST /approvals/550e8400-e29b-41d4-a716-446655440000/reject
        Authorization: Bearer <token>
        {
            "action": "reject",
            "reason": "Too risky, please review plan"
        }
    """
    try:
        # Get existing approval data
        key = f"approval:{run_id}"
        data = await redis.get(key)

        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request not found for run_id: {run_id}",
            )

        approval_data = json.loads(data)

        # Check if already approved/rejected
        if approval_data.get("status") != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Run is already {approval_data.get('status')}",
            )

        # Update approval data
        approval_data["status"] = "rejected"
        approval_data["rejected_by"] = user.user_id
        approval_data["rejected_at"] = datetime.now(timezone.utc).isoformat()
        approval_data["reason"] = request.reason

        # Save updated data (keep TTL)
        ttl = await redis.ttl(key)
        await redis.setex(key, max(ttl, 3600), json.dumps(approval_data))

        logger.info(
            "run_rejected",
            run_id=run_id,
            rejected_by=user.user_id,
            reason=request.reason,
        )

        return ApprovalResponse(
            run_id=run_id,
            status="rejected",
            rejected_at=approval_data["rejected_at"],
            rejected_by=approval_data["rejected_by"],
            reason=approval_data.get("reason"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "reject_run_failed",
            run_id=run_id,
            user_id=user.user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject run: {str(e)}",
        )


@router.get("/{run_id}/status", response_model=ApprovalResponse)
async def get_approval_status(
    run_id: str,
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> ApprovalResponse:
    """
    Get approval status for a run.

    Args:
        run_id: Run ID to check
        user: Current authenticated user
        redis: Redis connection

    Returns:
        ApprovalResponse: Current approval status

    Raises:
        HTTPException: 404 if run not found

    Example:
        GET /approvals/550e8400-e29b-41d4-a716-446655440000/status
        Authorization: Bearer <token>
    """
    try:
        # Get approval data
        key = f"approval:{run_id}"
        data = await redis.get(key)

        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval request not found for run_id: {run_id}",
            )

        approval_data = json.loads(data)

        return ApprovalResponse(
            run_id=run_id,
            status=approval_data.get("status", "pending"),
            approved_at=approval_data.get("approved_at"),
            approved_by=approval_data.get("approved_by"),
            rejected_at=approval_data.get("rejected_at"),
            rejected_by=approval_data.get("rejected_by"),
            reason=approval_data.get("reason"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_approval_status_failed",
            run_id=run_id,
            user_id=user.user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get approval status: {str(e)}",
        )


# ============================================================================
# HELPER FUNCTIONS (for use by /act endpoint)
# ============================================================================


async def create_pending_approval(
    redis: Redis,
    run_id: str,
    actor: str,
    goal: str,
    autonomy_level: str,
    risk_score: float,
    required_scopes: list[str],
    timeout_seconds: int = 3600,
) -> None:
    """
    Create a pending approval request in Redis.

    Args:
        redis: Redis connection
        run_id: Run ID
        actor: Actor making the request
        goal: Goal being executed
        autonomy_level: Autonomy level determined
        risk_score: Risk score calculated
        required_scopes: Required scopes
        timeout_seconds: Timeout for approval (default: 1 hour)
    """
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromtimestamp(
        now.timestamp() + timeout_seconds, tz=timezone.utc
    )

    approval_data = {
        "run_id": run_id,
        "actor": actor,
        "goal": goal,
        "status": "pending",
        "autonomy_level": autonomy_level,
        "risk_score": risk_score,
        "required_scopes": required_scopes,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    key = f"approval:{run_id}"
    await redis.setex(key, timeout_seconds, json.dumps(approval_data))

    logger.info(
        "pending_approval_created",
        run_id=run_id,
        actor=actor,
        autonomy_level=autonomy_level,
        risk_score=risk_score,
        expires_at=expires_at.isoformat(),
    )


async def check_approval_status(redis: Redis, run_id: str) -> str | None:
    """
    Check if a run has been approved.

    Args:
        redis: Redis connection
        run_id: Run ID to check

    Returns:
        str | None: "approved", "rejected", "pending", or None if not found
    """
    key = f"approval:{run_id}"
    data = await redis.get(key)

    if not data:
        return None

    approval_data = json.loads(data)
    return approval_data.get("status", "pending")


# ============================================================================
# AGENT SIGN-OFF
# ============================================================================
# ✅ Agent 3 (Policy Guard & Autonomy)
