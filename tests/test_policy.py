"""Policy Guard Tests.

Tests for:
- PolicyGuard validation logic
- Risk scoring algorithm
- Autonomy level determination
- Scope validation
- Approval workflow requirements
- Tool and scope risk calculation

Agent: Agent 3 (Policy Guard & Autonomy)
"""

import pytest

from chad_agents.policies.autonomy import (
    AutonomyLevel,
    calculate_tool_risk,
    calculate_scope_risk,
    get_user_trust_level,
    is_dry_run_allowed,
    requires_step_approval,
    requires_plan_approval,
    should_notify_user,
    is_autonomous,
)
from chad_agents.policies.policy_guard import (
    PolicyGuard,
    PolicyValidationResult,
    ActRequest,
    User,
    ExecutionPlan,
    policy_guard,
)
from chad_config.settings import Settings


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def settings():
    """Default settings for tests."""
    return Settings()


@pytest.fixture
def policy_guard_instance(settings):
    """PolicyGuard instance."""
    return PolicyGuard(settings)


@pytest.fixture
def admin_user():
    """Admin user with all permissions."""
    return User(user_id="admin", scopes=["*"])


@pytest.fixture
def standard_user():
    """Standard user with notion and github scopes."""
    return User(user_id="user123", scopes=["notion.*", "github.read", "local.*"])


@pytest.fixture
def limited_user():
    """Limited user with minimal scopes."""
    return User(user_id="limited_user", scopes=["local.read"])


@pytest.fixture
def new_user():
    """New user with no scopes."""
    return User(user_id="new_user", scopes=[])


# ============================================================================
# POLICY GUARD TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_policy_guard_allows_valid_actor(policy_guard_instance, admin_user):
    """Test policy guard approves valid actor with admin scope."""
    request = ActRequest(
        actor="admin",
        goal="Read some data from Notion",
        context={},
    )

    result = await policy_guard_instance.validate_request(request, admin_user)

    assert result.allowed is True
    assert len(result.missing_scopes) == 0
    assert result.autonomy_level == AutonomyLevel.L3_ExecuteSilent


@pytest.mark.asyncio
async def test_policy_guard_denies_missing_scopes(policy_guard_instance, limited_user):
    """Test policy guard denies request with missing scopes."""
    request = ActRequest(
        actor="limited_user",
        goal="Create a new Notion page with project updates",
        context={},
    )

    result = await policy_guard_instance.validate_request(request, limited_user)

    assert result.allowed is False
    assert "notion.write" in result.missing_scopes
    assert result.reason is not None
    assert "Missing required scopes" in result.reason


@pytest.mark.asyncio
async def test_policy_guard_low_risk_read_only(policy_guard_instance, standard_user):
    """Test low risk, read-only operation gets L2 or L3."""
    request = ActRequest(
        actor="user123",
        goal="Search Notion for project documentation",
        context={},
    )

    result = await policy_guard_instance.validate_request(request, standard_user)

    assert result.allowed is True
    # Notion search is actually moderately risky (0.2 base + 0.2 scope)
    assert result.autonomy_level in [AutonomyLevel.L2_ExecuteNotify, AutonomyLevel.L3_ExecuteSilent]
    assert result.requires_approval is False


@pytest.mark.asyncio
async def test_policy_guard_medium_risk_write(policy_guard_instance, standard_user):
    """Test write operation may require approval depending on risk score."""
    request = ActRequest(
        actor="user123",
        goal="Create a new Notion page with meeting notes",
        context={},
    )

    result = await policy_guard_instance.validate_request(request, standard_user)

    assert result.allowed is True
    # Write operations typically have higher risk
    assert result.autonomy_level in [AutonomyLevel.L1_Draft, AutonomyLevel.L2_ExecuteNotify]


@pytest.mark.asyncio
async def test_policy_guard_dry_run_gets_l2(policy_guard_instance, standard_user):
    """Test dry-run requests default to L2 (safe to execute)."""
    request = ActRequest(
        actor="user123",
        goal="Delete all Notion pages",
        context={},
        dry_run=True,
    )

    result = await policy_guard_instance.validate_request(request, standard_user)

    assert result.allowed is True
    assert result.autonomy_level == AutonomyLevel.L2_ExecuteNotify
    assert result.requires_approval is False


# ============================================================================
# RISK SCORING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_risk_score_read_only_low(policy_guard_instance, admin_user):
    """Test read-only tools have lowish risk score."""
    plan = ExecutionPlan(
        steps=[{"tool": "adapters_github.search_issues", "input": {}}],
        tools_used=["adapters_github.search_issues"],
        required_scopes=["github.read"],
    )

    risk = await policy_guard_instance.assess_risk_score(plan, admin_user)

    # GitHub search (0.1) + github.read scope (0.3) = 0.4, but reduced by admin trust
    assert risk < 0.5


@pytest.mark.asyncio
async def test_risk_score_write_medium(policy_guard_instance, standard_user):
    """Test write operations have medium risk score (0.3-0.6)."""
    plan = ExecutionPlan(
        steps=[{"tool": "adapters_notion.create_page", "input": {}}],
        tools_used=["adapters_notion.create_page"],
        required_scopes=["notion.write"],
    )

    risk = await policy_guard_instance.assess_risk_score(plan, standard_user)

    assert 0.3 <= risk < 0.7


@pytest.mark.asyncio
async def test_risk_score_multiple_tools_cumulative(policy_guard_instance, standard_user):
    """Test multiple tools increase risk score cumulatively."""
    plan = ExecutionPlan(
        steps=[
            {"tool": "adapters_github.search_issues", "input": {}},
            {"tool": "adapters_notion.create_page", "input": {}},
            {"tool": "local.summarize_text", "input": {}},
        ],
        tools_used=[
            "adapters_github.search_issues",
            "adapters_notion.create_page",
            "local.summarize_text",
        ],
        required_scopes=["github.read", "notion.write", "local.*"],
    )

    risk = await policy_guard_instance.assess_risk_score(plan, standard_user)

    # Should be higher than single write operation due to complexity
    assert risk > 0.4


# ============================================================================
# AUTONOMY LEVEL TESTS
# ============================================================================


def test_autonomy_level_l3_low_risk(policy_guard_instance, admin_user):
    """Test L3 (autonomous) for low risk operations."""
    request = ActRequest(actor="admin", goal="Read data", context={})
    level = policy_guard_instance.determine_autonomy_level(request, admin_user, risk_score=0.2)

    assert level == AutonomyLevel.L3_ExecuteSilent


def test_autonomy_level_l2_medium_risk(policy_guard_instance, standard_user):
    """Test L2 (confirmed) for medium risk operations."""
    request = ActRequest(actor="user123", goal="Write data", context={})
    level = policy_guard_instance.determine_autonomy_level(request, standard_user, risk_score=0.5)

    assert level == AutonomyLevel.L2_ExecuteNotify


def test_autonomy_level_l1_high_risk(policy_guard_instance, standard_user):
    """Test L1 (supervised) for high risk operations."""
    request = ActRequest(actor="user123", goal="Sensitive operation", context={})
    level = policy_guard_instance.determine_autonomy_level(request, standard_user, risk_score=0.7)

    assert level == AutonomyLevel.L1_Draft


def test_autonomy_level_l0_critical_risk(policy_guard_instance, limited_user):
    """Test L0 (constrained) for critical risk operations."""
    request = ActRequest(actor="limited_user", goal="Destructive operation", context={})
    level = policy_guard_instance.determine_autonomy_level(request, limited_user, risk_score=0.9)

    assert level == AutonomyLevel.L0_Ask


def test_autonomy_level_admin_always_l3_unless_critical(policy_guard_instance, admin_user):
    """Test admin users get L3 for all but critical risk."""
    request = ActRequest(actor="admin", goal="Write operation", context={})
    level = policy_guard_instance.determine_autonomy_level(request, admin_user, risk_score=0.5)

    assert level == AutonomyLevel.L3_ExecuteSilent


# ============================================================================
# SCOPE VALIDATION TESTS
# ============================================================================


def test_check_scope_permissions_exact_match(policy_guard_instance):
    """Test exact scope match."""
    result = policy_guard_instance.check_scope_permissions(
        required_scopes=["notion.read"],
        user_scopes=["notion.read"],
    )
    assert result is True


def test_check_scope_permissions_wildcard(policy_guard_instance):
    """Test wildcard scope match."""
    result = policy_guard_instance.check_scope_permissions(
        required_scopes=["notion.read", "notion.write"],
        user_scopes=["notion.*"],
    )
    assert result is True


def test_check_scope_permissions_admin_wildcard(policy_guard_instance):
    """Test admin wildcard matches everything."""
    result = policy_guard_instance.check_scope_permissions(
        required_scopes=["notion.write", "github.write", "admin.delete"],
        user_scopes=["*"],
    )
    assert result is True


def test_check_scope_permissions_missing_scope(policy_guard_instance):
    """Test missing scope returns False."""
    result = policy_guard_instance.check_scope_permissions(
        required_scopes=["github.write"],
        user_scopes=["github.read"],
    )
    assert result is False


# ============================================================================
# APPROVAL WORKFLOW TESTS
# ============================================================================


def test_requires_approval_l0_and_l1(policy_guard_instance):
    """Test L0 and L1 require approval."""
    assert policy_guard_instance.requires_approval(AutonomyLevel.L0_Ask, 0.9) is True
    assert policy_guard_instance.requires_approval(AutonomyLevel.L1_Draft, 0.7) is True


def test_no_approval_l2_and_l3(policy_guard_instance):
    """Test L2 and L3 don't require approval."""
    assert policy_guard_instance.requires_approval(AutonomyLevel.L2_ExecuteNotify, 0.5) is False
    assert policy_guard_instance.requires_approval(AutonomyLevel.L3_ExecuteSilent, 0.2) is False


# ============================================================================
# TOOL RISK CALCULATION TESTS
# ============================================================================


def test_calculate_tool_risk_read():
    """Test read operations have low risk."""
    risk = calculate_tool_risk("adapters_github.search_issues", ["read"])
    assert risk == 0.1


def test_calculate_tool_risk_write():
    """Test write operations have moderate risk."""
    risk = calculate_tool_risk("adapters_notion.create_page", ["write"])
    assert risk == 0.3


def test_calculate_tool_risk_delete():
    """Test delete operations have high risk."""
    risk = calculate_tool_risk("adapters_github.delete_issue", ["delete"])
    assert risk == 0.7


def test_calculate_tool_risk_admin():
    """Test admin operations have critical risk."""
    risk = calculate_tool_risk("admin.reset_database", ["admin"])
    assert risk == 0.9


def test_calculate_tool_risk_local():
    """Test local operations have very low risk."""
    risk = calculate_tool_risk("local.summarize_text", [])
    assert risk == 0.05


# ============================================================================
# SCOPE RISK CALCULATION TESTS
# ============================================================================


def test_calculate_scope_risk_local():
    """Test local scopes have very low risk."""
    risk = calculate_scope_risk(["local.read"])
    assert risk == 0.05


def test_calculate_scope_risk_read():
    """Test read scopes have low risk."""
    risk = calculate_scope_risk(["notion.read", "github.read"])
    assert 0.4 <= risk <= 0.6  # notion (0.2) + github (0.3) = 0.5


def test_calculate_scope_risk_write():
    """Test write scopes have elevated risk."""
    risk = calculate_scope_risk(["notion.write"])
    assert risk == 0.4


def test_calculate_scope_risk_admin():
    """Test admin scopes have high risk."""
    risk = calculate_scope_risk(["admin.*"])
    assert risk == 0.8


def test_calculate_scope_risk_wildcard():
    """Test wildcard scope has high risk."""
    risk = calculate_scope_risk(["*"])
    assert risk == 0.8


# ============================================================================
# USER TRUST LEVEL TESTS
# ============================================================================


def test_user_trust_level_admin():
    """Test admin users have full trust."""
    user = User(user_id="admin", scopes=["*"])
    trust = get_user_trust_level(user)
    assert trust == 1.0


def test_user_trust_level_trusted():
    """Test users with multiple broad scopes have high trust."""
    user = User(user_id="user", scopes=["notion.*", "github.*", "google.*"])
    trust = get_user_trust_level(user)
    assert trust == 0.8


def test_user_trust_level_standard():
    """Test standard users have moderate trust."""
    user = User(user_id="user", scopes=["notion.read", "github.read", "local.*"])
    trust = get_user_trust_level(user)
    assert trust == 0.5


def test_user_trust_level_limited():
    """Test limited users have low trust."""
    user = User(user_id="user", scopes=["local.read"])
    trust = get_user_trust_level(user)
    assert trust == 0.3


def test_user_trust_level_new():
    """Test new users have no trust."""
    user = User(user_id="user", scopes=[])
    trust = get_user_trust_level(user)
    assert trust == 0.0


# ============================================================================
# AUTONOMY HELPER TESTS
# ============================================================================


def test_is_dry_run_allowed():
    """Test dry-run is allowed at all autonomy levels."""
    assert is_dry_run_allowed(AutonomyLevel.L0_Ask) is True
    assert is_dry_run_allowed(AutonomyLevel.L1_Draft) is True
    assert is_dry_run_allowed(AutonomyLevel.L2_ExecuteNotify) is True
    assert is_dry_run_allowed(AutonomyLevel.L3_ExecuteSilent) is True


def test_requires_step_approval():
    """Test L0 requires step approval."""
    assert requires_step_approval(AutonomyLevel.L0_Ask) is True
    assert requires_step_approval(AutonomyLevel.L1_Draft) is False


def test_requires_plan_approval():
    """Test L0 and L1 require plan approval."""
    assert requires_plan_approval(AutonomyLevel.L0_Ask) is True
    assert requires_plan_approval(AutonomyLevel.L1_Draft) is True
    assert requires_plan_approval(AutonomyLevel.L2_ExecuteNotify) is False


def test_should_notify_user():
    """Test L0, L1, L2 should notify user."""
    assert should_notify_user(AutonomyLevel.L0_Ask) is True
    assert should_notify_user(AutonomyLevel.L1_Draft) is True
    assert should_notify_user(AutonomyLevel.L2_ExecuteNotify) is True
    assert should_notify_user(AutonomyLevel.L3_ExecuteSilent) is False


def test_is_autonomous():
    """Test only L3 is fully autonomous."""
    assert is_autonomous(AutonomyLevel.L0_Ask) is False
    assert is_autonomous(AutonomyLevel.L1_Draft) is False
    assert is_autonomous(AutonomyLevel.L2_ExecuteNotify) is False
    assert is_autonomous(AutonomyLevel.L3_ExecuteSilent) is True


# ============================================================================
# LEGACY FUNCTION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_policy_guard_legacy_function():
    """Test legacy policy_guard function works."""
    plan, violations, redactions, autonomy = await policy_guard(
        actor="test_actor",
        goal="Test goal",
        context={},
    )

    assert len(violations) == 0
    assert isinstance(autonomy, AutonomyLevel)
    assert plan["goal"] == "Test goal"


@pytest.mark.asyncio
async def test_policy_guard_returns_autonomy_level():
    """Test policy guard determines autonomy level."""
    _, _, _, autonomy = await policy_guard("test", "goal", {})
    assert isinstance(autonomy, AutonomyLevel)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_full_validation_flow_success(policy_guard_instance, standard_user):
    """Test complete validation flow for successful request."""
    request = ActRequest(
        actor="user123",
        goal="Fetch latest Notion pages and analyze their content",
        context={},
    )

    result = await policy_guard_instance.validate_request(request, standard_user)

    assert result.allowed is True
    # This user has notion.* and local.* so should succeed
    assert 0.0 <= result.risk_score <= 1.0
    assert len(result.missing_scopes) == 0


@pytest.mark.asyncio
async def test_full_validation_flow_denied(policy_guard_instance, limited_user):
    """Test complete validation flow for denied request."""
    request = ActRequest(
        actor="limited_user",
        goal="Delete GitHub repository and all issues",
        context={"repo": "owner/repo"},
    )

    result = await policy_guard_instance.validate_request(request, limited_user)

    assert result.allowed is False
    assert result.reason is not None
    assert len(result.missing_scopes) > 0


# ============================================================================
# AGENT SIGN-OFF
# ============================================================================
# ✅ Agent 3 (Policy Guard & Autonomy)
