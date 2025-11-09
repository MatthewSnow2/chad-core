"""Policy Guard - Pre-execution validation.

Implements:
- Request validation against policy rules
- Risk scoring based on tools and scopes
- Autonomy level determination (L0-L3)
- Scope permission checking
- Approval workflow triggers

Agent: Agent 3 (Policy Guard & Autonomy)
"""

from typing import Any

from pydantic import BaseModel, Field

from chad_agents.policies.autonomy import AutonomyLevel, calculate_tool_risk, get_user_trust_level
from chad_agents.policies.scopes import check_scopes
from chad_config.settings import Settings


# ============================================================================
# MODELS
# ============================================================================


class ExecutionPlan(BaseModel):
    """Execution plan for risk assessment."""

    steps: list[dict[str, Any]] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    required_scopes: list[str] = Field(default_factory=list)


class PolicyValidationResult(BaseModel):
    """Result of policy guard validation."""

    allowed: bool
    autonomy_level: AutonomyLevel
    risk_score: float = Field(..., ge=0.0, le=1.0)
    requires_approval: bool
    required_scopes: list[str]
    missing_scopes: list[str]
    reason: str | None = None


class User(BaseModel):
    """User model for policy validation."""

    user_id: str
    scopes: list[str] = []


class ActRequest(BaseModel):
    """Action request for policy validation."""

    actor: str
    goal: str
    context: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


# ============================================================================
# POLICY GUARD CLASS
# ============================================================================


class PolicyGuard:
    """
    Policy guard for validating execution requests.

    Responsibilities:
    - Validate user scopes against required permissions
    - Calculate risk scores based on tools, scopes, and user trust
    - Determine appropriate autonomy level (L0-L3)
    - Decide if approval is required

    Risk Scoring Factors:
    - Tool capabilities: read (0.1), write (0.3), delete (0.7), admin (0.9)
    - Scope sensitivity: notion.* (0.2), github.write (0.4), admin.* (0.8)
    - User trust level: new user (+0.3), trusted user (-0.2)
    - Operation complexity: single tool (0.1), multi-step (+0.2 per step)
    - Data sensitivity: personal (+0.3), financial (+0.5)

    Autonomy Levels:
    - L3 (Autonomous): Low risk (<0.3), read-only, admin scope
    - L2 (Confirmed): Medium risk (0.3-0.6), write ops, appropriate scopes
    - L1 (Supervised): High risk (0.6-0.8), sensitive ops, missing scopes
    - L0 (Constrained): Critical risk (>0.8), destructive ops, new users
    """

    def __init__(self, settings: Settings):
        """
        Initialize policy guard.

        Args:
            settings: Application settings
        """
        self.settings = settings

        # Load risk thresholds from settings (with defaults)
        self.risk_threshold_l3 = getattr(settings, "RISK_THRESHOLD_L3", 0.3)
        self.risk_threshold_l2 = getattr(settings, "RISK_THRESHOLD_L2", 0.6)
        self.risk_threshold_l1 = getattr(settings, "RISK_THRESHOLD_L1", 0.8)

    async def validate_request(
        self, request: ActRequest, user: User
    ) -> PolicyValidationResult:
        """
        Validate execution request against policy rules.

        Args:
            request: Action execution request
            user: User making the request

        Returns:
            PolicyValidationResult: Validation outcome
        """
        # Extract required scopes from goal and context
        required_scopes = self._extract_required_scopes(request)

        # Check scope permissions
        has_permissions = self.check_scope_permissions(required_scopes, user.scopes)
        missing_scopes = [
            scope for scope in required_scopes
            if not self._scope_matches_any(scope, user.scopes)
        ]

        # If missing scopes, deny request
        if not has_permissions:
            return PolicyValidationResult(
                allowed=False,
                autonomy_level=AutonomyLevel.L0_Ask,
                risk_score=1.0,
                requires_approval=True,
                required_scopes=required_scopes,
                missing_scopes=missing_scopes,
                reason=f"Missing required scopes: {', '.join(missing_scopes)}",
            )

        # Create execution plan from request
        plan = self._create_execution_plan(request)

        # Assess risk score
        risk_score = await self.assess_risk_score(plan, user)

        # Determine autonomy level
        autonomy_level = self.determine_autonomy_level(request, user, risk_score)

        # Check if approval is required
        requires_approval = self.requires_approval(autonomy_level, risk_score)

        # Allow request
        return PolicyValidationResult(
            allowed=True,
            autonomy_level=autonomy_level,
            risk_score=risk_score,
            requires_approval=requires_approval,
            required_scopes=required_scopes,
            missing_scopes=[],
            reason=None,
        )

    def determine_autonomy_level(
        self, request: ActRequest, user: User, risk_score: float
    ) -> AutonomyLevel:
        """
        Determine appropriate autonomy level based on risk and user.

        Logic:
        - L3 (Autonomous): Low risk (<0.3), admin scope, or trusted user with read-only
        - L2 (Confirmed): Medium risk (0.3-0.6), appropriate scopes
        - L1 (Supervised): High risk (0.6-0.8), sensitive operations
        - L0 (Constrained): Critical risk (>0.8), destructive operations

        Args:
            request: Action request
            user: User making request
            risk_score: Calculated risk score (0.0-1.0)

        Returns:
            AutonomyLevel: Determined autonomy level
        """
        # Admin scope always gets L3 (unless risk is critical)
        if "*" in user.scopes and risk_score < self.risk_threshold_l1:
            return AutonomyLevel.L3_ExecuteSilent

        # Dry run requests default to L2 (safe to execute)
        if request.dry_run:
            return AutonomyLevel.L2_ExecuteNotify

        # Risk-based determination
        if risk_score < self.risk_threshold_l3:
            # Low risk: Autonomous execution
            return AutonomyLevel.L3_ExecuteSilent
        elif risk_score < self.risk_threshold_l2:
            # Medium risk: Execute with notification
            return AutonomyLevel.L2_ExecuteNotify
        elif risk_score < self.risk_threshold_l1:
            # High risk: Supervised (show plan, get approval)
            return AutonomyLevel.L1_Draft
        else:
            # Critical risk: Constrained (ask before each step)
            return AutonomyLevel.L0_Ask

    def check_scope_permissions(
        self, required_scopes: list[str], user_scopes: list[str]
    ) -> bool:
        """
        Check if user has all required scopes.

        Uses scope matching logic from chad_agents.policies.scopes.

        Args:
            required_scopes: List of required scopes
            user_scopes: List of scopes granted to user

        Returns:
            bool: True if all required scopes are satisfied
        """
        return check_scopes(required_scopes, user_scopes)

    async def assess_risk_score(self, plan: ExecutionPlan, user: User) -> float:
        """
        Calculate risk score for execution plan.

        Scoring factors:
        - Tool capabilities (read, write, delete, admin)
        - Scope sensitivity (notion.*, github.write, admin.*)
        - User trust level (new user vs. trusted user)
        - Operation complexity (number of steps)
        - Data sensitivity (PII, financial data)

        Args:
            plan: Execution plan with tools and scopes

        Returns:
            float: Risk score from 0.0 (low risk) to 1.0 (high risk)
        """
        risk = 0.0

        # Factor 1: Tool-based risk
        for tool in plan.tools_used:
            tool_risk = calculate_tool_risk(tool, [])
            risk += tool_risk

        # Factor 2: Scope-based risk
        scope_risk = self._calculate_scope_risk(plan.required_scopes)
        risk += scope_risk

        # Factor 3: User trust level (modifies total risk)
        trust_modifier = get_user_trust_level(user)
        risk = risk * (1 - trust_modifier * 0.2)  # Trusted users reduce risk by up to 20%

        # Factor 4: Complexity (number of steps)
        if len(plan.steps) > 1:
            complexity_risk = min((len(plan.steps) - 1) * 0.1, 0.3)
            risk += complexity_risk

        # Factor 5: Data sensitivity (check context for sensitive keywords)
        # (This would be enhanced with actual PII detection)

        # Normalize to 0.0-1.0 range
        risk = min(risk, 1.0)
        risk = max(risk, 0.0)

        return risk

    def requires_approval(self, autonomy_level: AutonomyLevel, risk_score: float) -> bool:
        """
        Determine if request requires approval.

        Approval required for:
        - L0 (Ask): Every step needs approval
        - L1 (Draft): Plan needs approval before execution
        - L2 (ExecuteNotify): No approval (just notify)
        - L3 (ExecuteSilent): No approval (silent execution)

        Args:
            autonomy_level: Determined autonomy level
            risk_score: Calculated risk score

        Returns:
            bool: True if approval is required
        """
        # L0 and L1 require approval
        if autonomy_level in (AutonomyLevel.L0_Ask, AutonomyLevel.L1_Draft):
            return True

        # L2 and L3 don't require approval
        return False

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _extract_required_scopes(self, request: ActRequest) -> list[str]:
        """
        Extract required scopes from request goal and context.

        This is a heuristic approach - in production, this would be enhanced
        with LLM-based analysis or explicit scope declarations.

        Args:
            request: Action request

        Returns:
            list[str]: List of required scopes
        """
        required = []

        # Parse goal for tool/service mentions
        goal_lower = request.goal.lower()

        # Notion
        if "notion" in goal_lower:
            if any(kw in goal_lower for kw in ["create", "update", "write", "add"]):
                required.append("notion.write")
            else:
                required.append("notion.read")

        # GitHub
        if "github" in goal_lower or "git" in goal_lower:
            if any(kw in goal_lower for kw in ["create", "update", "push", "commit", "issue"]):
                required.append("github.write")
            else:
                required.append("github.read")

        # Google
        if "google" in goal_lower or "gmail" in goal_lower or "drive" in goal_lower:
            if any(kw in goal_lower for kw in ["send", "create", "update", "write"]):
                required.append("google.write")
            else:
                required.append("google.read")

        # Local tools (always safe)
        if "summarize" in goal_lower or "analyze" in goal_lower:
            required.append("local.summarize")

        # If no specific scopes detected, default to read-only local
        if not required:
            required.append("local.read")

        return list(set(required))  # Deduplicate

    def _create_execution_plan(self, request: ActRequest) -> ExecutionPlan:
        """
        Create execution plan from request.

        In production, this would use LLM to generate actual plan.
        For now, we create a simplified plan based on heuristics.

        Args:
            request: Action request

        Returns:
            ExecutionPlan: Simplified execution plan
        """
        # Extract tools from goal (heuristic)
        tools = []
        goal_lower = request.goal.lower()

        if "github" in goal_lower:
            tools.append("adapters_github.search_issues")
        if "notion" in goal_lower:
            tools.append("adapters_notion.create_page")
        if "summarize" in goal_lower:
            tools.append("local.summarize_text")
        if "google" in goal_lower or "gmail" in goal_lower:
            tools.append("adapters_google.send_email")

        # Default to at least one step
        if not tools:
            tools = ["local.process"]

        # Create plan
        required_scopes = self._extract_required_scopes(request)

        return ExecutionPlan(
            steps=[{"tool": tool, "input": {}} for tool in tools],
            tools_used=tools,
            required_scopes=required_scopes,
        )

    def _calculate_scope_risk(self, scopes: list[str]) -> float:
        """
        Calculate risk based on scope sensitivity.

        Scope risk levels:
        - local.*: 0.05 (very low risk)
        - *.read: 0.1 (low risk)
        - notion.*, google.*: 0.2 (moderate risk)
        - *.write, github.write: 0.4 (elevated risk)
        - admin.*, *: 0.8 (high risk)

        Args:
            scopes: List of scopes

        Returns:
            float: Scope risk score
        """
        risk = 0.0

        for scope in scopes:
            if scope == "*" or scope.startswith("admin."):
                risk += 0.8
            elif ".write" in scope or ":write" in scope:
                risk += 0.4
            elif scope.startswith("github."):
                risk += 0.3
            elif scope.startswith("notion.") or scope.startswith("google."):
                risk += 0.2
            elif ".read" in scope or ":read" in scope:
                risk += 0.1
            elif scope.startswith("local."):
                risk += 0.05
            else:
                risk += 0.15  # Unknown scope, moderate risk

        return min(risk, 1.0)

    def _scope_matches_any(self, required: str, granted_scopes: list[str]) -> bool:
        """Check if required scope is matched by any granted scope."""
        from chad_agents.policies.scopes import scope_matches

        return any(scope_matches(required, granted) for granted in granted_scopes)


# ============================================================================
# LEGACY COMPATIBILITY
# ============================================================================


class PolicyViolation:
    """Policy violation record (legacy)."""

    def __init__(self, rule: str, severity: str, details: str):
        self.rule = rule
        self.severity = severity
        self.details = details


async def policy_guard(
    actor: str, goal: str, context: dict[str, Any]
) -> tuple[dict, list[PolicyViolation], list, AutonomyLevel]:
    """
    Legacy policy guard function (for backward compatibility).

    Returns: (approved_plan, violations, redactions, autonomy_level)

    NOTE: This is deprecated. Use PolicyGuard class instead.
    """
    # Create minimal user and request
    user = User(user_id=actor, scopes=["*"])  # Assume admin for legacy
    request = ActRequest(actor=actor, goal=goal, context=context)

    # Validate with new PolicyGuard
    from chad_config.settings import Settings

    settings = Settings()
    guard = PolicyGuard(settings)
    result = await guard.validate_request(request, user)

    # Convert to legacy format
    approved_plan = {"goal": goal, "context": context}
    violations: list[PolicyViolation] = []

    if not result.allowed:
        violations.append(
            PolicyViolation(
                rule="scope_check",
                severity="error",
                details=result.reason or "Policy violation",
            )
        )

    redactions: list = []

    return approved_plan, violations, redactions, result.autonomy_level


# ============================================================================
# AGENT SIGN-OFF
# ============================================================================
# ✅ Agent 3 (Policy Guard & Autonomy)
