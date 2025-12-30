"""Pydantic models for Teletran1 project data and recommendations."""

from datetime import datetime

from pydantic import BaseModel, Field


class Project(BaseModel):
    """A project pulled from Notion database."""

    name: str = Field(..., description="Project name")
    completion_percent: int = Field(..., ge=0, le=100, description="Completion percentage (0-100)")
    priority: str = Field(..., description="Priority level: high, medium, or low")
    last_activity: datetime | None = Field(None, description="When the project was last worked on")
    is_client_project: bool = Field(False, description="Whether this is a client project")
    has_deadline: bool = Field(False, description="Whether this project has a deadline")
    deadline: datetime | None = Field(None, description="Project deadline if set")
    next_action: str | None = Field(None, description="Next concrete action to take")
    notes: str | None = Field(None, description="Additional notes")

    @property
    def days_since_activity(self) -> int | None:
        """Calculate days since last activity."""
        if self.last_activity is None:
            return None
        delta = datetime.now() - self.last_activity
        return delta.days

    @property
    def is_near_completion(self) -> bool:
        """Check if project is in the danger zone (>75% complete)."""
        return self.completion_percent >= 75

    @property
    def is_stale(self) -> bool:
        """Check if project is stale (>7 days inactive)."""
        days = self.days_since_activity
        return days is not None and days > 7


class Recommendation(BaseModel):
    """Weekly project recommendation output."""

    project: str = Field(..., description="Recommended project name")
    completion: int = Field(..., description="Current completion percentage")
    why_this_week: str = Field(..., description="1-2 sentences explaining why to focus on this")
    first_action: str = Field(..., description="Specific concrete next step")
    what_shipping_enables: str = Field(..., description="Motivation - what becomes possible after")

    def format_output(self) -> str:
        """Format recommendation for CLI display."""
        return f"""**Project**: {self.project}
**Completion**: {self.completion}%
**Why This Week**: {self.why_this_week}
**First Action**: {self.first_action}
**What Shipping Enables**: {self.what_shipping_enables}"""


class ProjectHealthData(BaseModel):
    """Container for all project health data."""

    projects: list[Project] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.now)

    @property
    def near_completion_projects(self) -> list[Project]:
        """Get projects >75% complete."""
        return [p for p in self.projects if p.is_near_completion]

    @property
    def client_projects_with_deadlines(self) -> list[Project]:
        """Get client projects that have deadlines."""
        return [p for p in self.projects if p.is_client_project and p.has_deadline]

    @property
    def stale_high_priority(self) -> list[Project]:
        """Get high-priority projects that are stale (>7 days inactive)."""
        return [p for p in self.projects if p.priority == "high" and p.is_stale]

    @property
    def projects_with_next_actions(self) -> list[Project]:
        """Get projects with defined next actions."""
        return [p for p in self.projects if p.next_action]
