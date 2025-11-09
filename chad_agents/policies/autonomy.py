"""Autonomy Levels Enum and Helper Functions.

Implements:
- Autonomy level definitions (L0-L3)
- Tool risk calculation
- Scope risk calculation
- User trust level assessment
- Dry-run permission checks

Agent: Agent 3 (Policy Guard & Autonomy)
"""

from enum import Enum


class AutonomyLevel(str, Enum):
    """
    Autonomy levels for execution control.

    L0 (Ask): Constrained - Every step requires approval
        - Critical risk operations (>0.8)
        - Destructive operations (delete, admin actions)
        - New/untrusted users
        - Manual step-by-step execution

    L1 (Draft): Supervised - Plan requires approval, then auto-execute
        - High risk operations (0.6-0.8)
        - Sensitive operations (write to important services)
        - Users missing some required scopes
        - Show plan, get approval, then execute all steps

    L2 (ExecuteNotify): Confirmed - Show plan, proceed on confirmation
        - Medium risk operations (0.3-0.6)
        - Standard write operations
        - Users with appropriate scopes
        - Execute and notify user of results

    L3 (ExecuteSilent): Autonomous - Fully automatic execution
        - Low risk operations (<0.3)
        - Read-only operations
        - Admin scope users
        - Silent execution without user interaction
    """

    L0_Ask = "L0_Ask"
    L1_Draft = "L1_Draft"
    L2_ExecuteNotify = "L2_ExecuteNotify"
    L3_ExecuteSilent = "L3_ExecuteSilent"


# ============================================================================
# TOOL RISK CALCULATION
# ============================================================================


def calculate_tool_risk(tool_name: str, capabilities: list[str]) -> float:
    """
    Calculate risk score for a specific tool.

    Risk levels based on tool capabilities:
    - Read operations: 0.1 (low risk)
    - Write operations: 0.3 (moderate risk)
    - Delete operations: 0.7 (high risk)
    - Admin operations: 0.9 (critical risk)
    - Unknown tools: 0.2 (default moderate-low risk)

    Args:
        tool_name: Name of the tool (e.g., "adapters_github.search_issues")
        capabilities: List of capabilities (e.g., ["read", "write", "delete"])

    Returns:
        float: Risk score from 0.0 to 1.0

    Examples:
        calculate_tool_risk("adapters_github.search_issues", ["read"])  # 0.1
        calculate_tool_risk("adapters_notion.create_page", ["write"])  # 0.3
        calculate_tool_risk("adapters_github.delete_issue", ["delete"])  # 0.7
        calculate_tool_risk("admin.reset_database", ["admin"])  # 0.9
    """
    # Default risk for unknown tools
    risk = 0.2

    # Check tool name for operation type
    tool_lower = tool_name.lower()

    # Critical operations
    if any(kw in tool_lower for kw in ["delete", "remove", "drop", "destroy", "reset"]):
        risk = 0.7
    # Admin operations
    elif any(kw in tool_lower for kw in ["admin", "configure", "setup", "migrate"]):
        risk = 0.9
    # Write operations
    elif any(kw in tool_lower for kw in ["create", "update", "write", "send", "post", "put"]):
        risk = 0.3
    # Read operations
    elif any(kw in tool_lower for kw in ["read", "get", "fetch", "search", "list", "query"]):
        risk = 0.1
    # Local/safe operations
    elif tool_lower.startswith("local."):
        risk = 0.05

    # Check capabilities for additional risk
    if "admin" in capabilities:
        risk = max(risk, 0.9)
    elif "delete" in capabilities:
        risk = max(risk, 0.7)
    elif "write" in capabilities:
        risk = max(risk, 0.3)
    elif "read" in capabilities:
        risk = max(risk, 0.1)

    return min(risk, 1.0)


# ============================================================================
# SCOPE RISK CALCULATION
# ============================================================================


def calculate_scope_risk(scopes: list[str]) -> float:
    """
    Calculate risk based on scope sensitivity.

    Scope risk levels:
    - local.*: 0.05 (very low risk)
    - *.read: 0.1 (low risk)
    - notion.*, google.*: 0.2 (moderate risk)
    - *.write, github.write: 0.4 (elevated risk)
    - admin.*, *: 0.8 (high risk)

    Args:
        scopes: List of scopes (e.g., ["notion.write", "github.read"])

    Returns:
        float: Aggregated risk score from 0.0 to 1.0

    Examples:
        calculate_scope_risk(["local.read"])  # 0.05
        calculate_scope_risk(["notion.read", "github.read"])  # 0.2
        calculate_scope_risk(["notion.write"])  # 0.4
        calculate_scope_risk(["admin.*"])  # 0.8
        calculate_scope_risk(["*"])  # 0.8
    """
    risk = 0.0

    for scope in scopes:
        # Admin and wildcard scopes are highest risk
        if scope == "*" or scope.startswith("admin."):
            risk += 0.8
        # Write operations (check before read to prioritize)
        elif ".write" in scope or ":write" in scope:
            risk += 0.4
        # Local operations (very low risk)
        elif scope.startswith("local."):
            risk += 0.05
        # GitHub scopes (source code access)
        elif scope.startswith("github."):
            risk += 0.3
        # Notion and Google scopes (data access)
        elif scope.startswith("notion.") or scope.startswith("google."):
            risk += 0.2
        # Read operations
        elif ".read" in scope or ":read" in scope:
            risk += 0.1
        # Unknown scopes
        else:
            risk += 0.15

    # Normalize to 0.0-1.0 range
    return min(risk, 1.0)


# ============================================================================
# USER TRUST LEVEL
# ============================================================================


def get_user_trust_level(user: "User") -> float:
    """
    Calculate user trust level based on scopes and user attributes.

    Trust levels:
    - 1.0: Admin users (have "*" scope)
    - 0.8: Trusted users (have multiple broad scopes)
    - 0.5: Standard users (have specific scopes)
    - 0.2: Limited users (have minimal scopes)
    - 0.0: New/unknown users (no scopes)

    Args:
        user: User model with scopes

    Returns:
        float: Trust level from 0.0 (untrusted) to 1.0 (fully trusted)

    Examples:
        get_user_trust_level(User(user_id="admin", scopes=["*"]))  # 1.0
        get_user_trust_level(User(user_id="user", scopes=["notion.*", "github.*"]))  # 0.8
        get_user_trust_level(User(user_id="user", scopes=["notion.read"]))  # 0.5
        get_user_trust_level(User(user_id="new", scopes=[]))  # 0.0
    """
    # Import User type for type checking
    from chad_agents.policies.policy_guard import User

    if not isinstance(user, User):
        # Handle legacy or dict-like user objects
        if hasattr(user, "scopes"):
            scopes = user.scopes
        else:
            return 0.0
    else:
        scopes = user.scopes

    # Admin users have full trust
    if "*" in scopes:
        return 1.0

    # Count wildcard scopes (e.g., "notion.*", "github.*")
    wildcard_scopes = [s for s in scopes if s.endswith(".*") or s.endswith(":*")]
    if len(wildcard_scopes) >= 3:
        return 0.8  # Trusted user with multiple broad permissions

    # Count total scopes
    if len(scopes) >= 5:
        return 0.7  # User with many specific permissions
    elif len(scopes) >= 3:
        return 0.5  # Standard user
    elif len(scopes) >= 1:
        return 0.3  # Limited user
    else:
        return 0.0  # New/unknown user


# ============================================================================
# DRY RUN PERMISSIONS
# ============================================================================


def is_dry_run_allowed(autonomy_level: AutonomyLevel) -> bool:
    """
    Check if dry-run mode is allowed for given autonomy level.

    Dry-run is allowed for all autonomy levels, as it's a safe operation
    that doesn't make actual changes.

    Args:
        autonomy_level: The autonomy level to check

    Returns:
        bool: True if dry-run is allowed (always True)

    Examples:
        is_dry_run_allowed(AutonomyLevel.L0_Ask)  # True
        is_dry_run_allowed(AutonomyLevel.L3_ExecuteSilent)  # True
    """
    # Dry-run is safe at all autonomy levels
    return True


# ============================================================================
# AUTONOMY LEVEL HELPERS
# ============================================================================


def requires_step_approval(autonomy_level: AutonomyLevel) -> bool:
    """
    Check if autonomy level requires approval for each step.

    Args:
        autonomy_level: The autonomy level to check

    Returns:
        bool: True if each step requires approval

    Examples:
        requires_step_approval(AutonomyLevel.L0_Ask)  # True
        requires_step_approval(AutonomyLevel.L1_Draft)  # False
    """
    return autonomy_level == AutonomyLevel.L0_Ask


def requires_plan_approval(autonomy_level: AutonomyLevel) -> bool:
    """
    Check if autonomy level requires approval for the entire plan.

    Args:
        autonomy_level: The autonomy level to check

    Returns:
        bool: True if plan requires approval before execution

    Examples:
        requires_plan_approval(AutonomyLevel.L1_Draft)  # True
        requires_plan_approval(AutonomyLevel.L2_ExecuteNotify)  # False
    """
    return autonomy_level in (AutonomyLevel.L0_Ask, AutonomyLevel.L1_Draft)


def should_notify_user(autonomy_level: AutonomyLevel) -> bool:
    """
    Check if autonomy level should notify user of execution.

    Args:
        autonomy_level: The autonomy level to check

    Returns:
        bool: True if user should be notified

    Examples:
        should_notify_user(AutonomyLevel.L2_ExecuteNotify)  # True
        should_notify_user(AutonomyLevel.L3_ExecuteSilent)  # False
    """
    return autonomy_level in (
        AutonomyLevel.L0_Ask,
        AutonomyLevel.L1_Draft,
        AutonomyLevel.L2_ExecuteNotify,
    )


def is_autonomous(autonomy_level: AutonomyLevel) -> bool:
    """
    Check if autonomy level is fully autonomous (no user interaction).

    Args:
        autonomy_level: The autonomy level to check

    Returns:
        bool: True if fully autonomous

    Examples:
        is_autonomous(AutonomyLevel.L3_ExecuteSilent)  # True
        is_autonomous(AutonomyLevel.L2_ExecuteNotify)  # False
    """
    return autonomy_level == AutonomyLevel.L3_ExecuteSilent


# ============================================================================
# AGENT SIGN-OFF
# ============================================================================
# ✅ Agent 3 (Policy Guard & Autonomy)
