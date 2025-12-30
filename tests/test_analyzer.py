"""Tests for the analyzer module."""

from datetime import datetime, timedelta

import pytest

from teletran1.analyzer import build_project_summary, prioritize_projects
from teletran1.models import Project, ProjectHealthData


def make_project(
    name: str,
    completion: int = 50,
    priority: str = "medium",
    days_ago: int | None = 3,
    is_client: bool = False,
    has_deadline: bool = False,
    next_action: str | None = None,
) -> Project:
    """Helper to create test projects."""
    last_activity = datetime.now() - timedelta(days=days_ago) if days_ago else None
    deadline = datetime.now() + timedelta(days=7) if has_deadline else None

    return Project(
        name=name,
        completion_percent=completion,
        priority=priority,
        last_activity=last_activity,
        is_client_project=is_client,
        has_deadline=has_deadline,
        deadline=deadline,
        next_action=next_action,
    )


class TestPrioritization:
    """Test prioritization logic."""

    def test_near_completion_highest_priority(self):
        """Projects >75% complete should be prioritized."""
        projects = [
            make_project("Low", completion=20),
            make_project("High", completion=85),
            make_project("Medium", completion=50),
        ]
        data = ProjectHealthData(projects=projects)

        result = prioritize_projects(data)

        assert result[0].name == "High"
        assert result[0].completion_percent == 85

    def test_client_deadline_priority(self):
        """Client projects with deadlines should be high priority."""
        projects = [
            make_project("Regular", completion=50),
            make_project("Client", completion=50, is_client=True, has_deadline=True),
        ]
        data = ProjectHealthData(projects=projects)

        result = prioritize_projects(data)

        assert result[0].name == "Client"

    def test_stale_high_priority(self):
        """High-priority stale projects should be prioritized."""
        projects = [
            make_project("Active", priority="high", days_ago=2),
            make_project("Stale", priority="high", days_ago=10),
        ]
        data = ProjectHealthData(projects=projects)

        result = prioritize_projects(data)

        assert result[0].name == "Stale"

    def test_next_action_bonus(self):
        """Projects with next actions should get a bonus."""
        projects = [
            make_project("No Action", completion=50),
            make_project("Has Action", completion=50, next_action="Write tests"),
        ]
        data = ProjectHealthData(projects=projects)

        result = prioritize_projects(data)

        assert result[0].name == "Has Action"

    def test_combined_scoring(self):
        """Test complex scenario with multiple factors."""
        projects = [
            make_project("Almost Done", completion=80, priority="low"),
            make_project("Client Deadline", completion=40, is_client=True, has_deadline=True),
            make_project("Stale Important", completion=30, priority="high", days_ago=14),
        ]
        data = ProjectHealthData(projects=projects)

        result = prioritize_projects(data)

        # Near completion should win
        assert result[0].name == "Almost Done"

    def test_empty_projects(self):
        """Handle empty project list."""
        data = ProjectHealthData(projects=[])

        result = prioritize_projects(data)

        assert result == []


class TestProjectSummary:
    """Test project summary generation."""

    def test_basic_summary(self):
        """Generate basic project summary."""
        projects = [make_project("Test Project", completion=50)]
        data = ProjectHealthData(projects=projects)

        result = build_project_summary(data)

        assert "Test Project" in result
        assert "50%" in result

    def test_flags_in_summary(self):
        """Status flags should appear in summary."""
        projects = [
            make_project(
                "Flagged", completion=80, is_client=True, has_deadline=True, days_ago=10
            )
        ]
        data = ProjectHealthData(projects=projects)

        result = build_project_summary(data)

        assert "NEAR COMPLETION" in result
        assert "CLIENT" in result
        assert "DEADLINE" in result
        assert "STALE" in result

    def test_empty_summary(self):
        """Handle empty project list."""
        data = ProjectHealthData(projects=[])

        result = build_project_summary(data)

        assert "No projects found" in result


class TestProjectModel:
    """Test Project model properties."""

    def test_is_near_completion(self):
        """Test near completion threshold."""
        assert make_project("A", completion=74).is_near_completion is False
        assert make_project("B", completion=75).is_near_completion is True
        assert make_project("C", completion=100).is_near_completion is True

    def test_is_stale(self):
        """Test staleness detection."""
        assert make_project("A", days_ago=6).is_stale is False
        assert make_project("B", days_ago=7).is_stale is False
        assert make_project("C", days_ago=8).is_stale is True

    def test_days_since_activity(self):
        """Test activity calculation."""
        project = make_project("Test", days_ago=5)
        assert project.days_since_activity == 5

    def test_no_activity_date(self):
        """Handle missing activity date."""
        project = make_project("Test", days_ago=None)
        assert project.days_since_activity is None
        assert project.is_stale is False
