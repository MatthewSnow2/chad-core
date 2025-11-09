"""GitHub adapter Pydantic schemas.

Input and output schemas for all GitHub tools.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================================
# SEARCH ISSUES TOOL SCHEMAS
# ============================================================================


class SearchIssuesInput(BaseModel):
    """Input schema for SearchIssuesTool."""

    query: str = Field(..., description="Search query string")
    repo: str | None = Field(None, description="Repository in format 'owner/repo'")
    state: Literal["open", "closed", "all"] = Field("open", description="Issue state filter")
    limit: int = Field(10, ge=1, le=100, description="Maximum results to return")
    dry_run: bool = False


class IssueResult(BaseModel):
    """Single issue result."""

    number: int
    title: str
    state: Literal["open", "closed"]
    labels: list[str]
    author: str
    created_at: str
    url: str
    body: str = Field("", description="Issue body/description")


class SearchIssuesOutput(BaseModel):
    """Output schema for SearchIssuesTool."""

    results: list[IssueResult]
    total_count: int
    status: Literal["success", "dry_run"] = "success"


# ============================================================================
# GET PULL REQUEST TOOL SCHEMAS
# ============================================================================


class GetPullRequestInput(BaseModel):
    """Input schema for GetPullRequestTool."""

    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    pr_number: int = Field(..., description="Pull request number")
    dry_run: bool = False


class PRFileChange(BaseModel):
    """File change in a pull request."""

    filename: str
    status: str = Field(..., description="added, modified, removed, renamed")
    additions: int
    deletions: int
    changes: int


class GetPullRequestOutput(BaseModel):
    """Output schema for GetPullRequestTool."""

    number: int
    title: str
    description: str
    state: Literal["open", "closed", "merged"]
    author: str
    created_at: str
    updated_at: str
    merged_at: str | None = None
    files_changed: list[PRFileChange]
    comments_count: int
    reviews_count: int
    url: str
    status: Literal["success", "dry_run"] = "success"


# ============================================================================
# LIST REPOSITORIES TOOL SCHEMAS
# ============================================================================


class ListRepositoriesInput(BaseModel):
    """Input schema for ListRepositoriesTool."""

    org: str | None = Field(None, description="Organization name")
    user: str | None = Field(None, description="Username")
    visibility: Literal["public", "private", "all"] = Field("all", description="Visibility filter")
    limit: int = Field(10, ge=1, le=100, description="Maximum results to return")
    dry_run: bool = False


class RepositoryResult(BaseModel):
    """Single repository result."""

    name: str
    full_name: str
    description: str | None = None
    stars: int
    language: str | None = None
    updated_at: str
    url: str
    private: bool


class ListRepositoriesOutput(BaseModel):
    """Output schema for ListRepositoriesTool."""

    results: list[RepositoryResult]
    total_count: int
    status: Literal["success", "dry_run"] = "success"


# ============================================================================
# CREATE ISSUE TOOL SCHEMAS
# ============================================================================


class CreateIssueInput(BaseModel):
    """Input schema for CreateIssueTool."""

    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    title: str = Field(..., description="Issue title")
    body: str = Field("", description="Issue body/description")
    labels: list[str] = Field(default_factory=list, description="Issue labels")
    dry_run: bool = False


class CreateIssueOutput(BaseModel):
    """Output schema for CreateIssueTool."""

    number: int
    url: str
    title: str
    created_at: str
    status: Literal["created", "dry_run"]


# ============================================================================
# ADD COMMENT TOOL SCHEMAS
# ============================================================================


class AddCommentInput(BaseModel):
    """Input schema for AddCommentTool."""

    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    issue_number: int = Field(..., description="Issue/PR number")
    comment: str = Field(..., description="Comment text")
    dry_run: bool = False


class AddCommentOutput(BaseModel):
    """Output schema for AddCommentTool."""

    comment_id: int
    url: str
    created_at: str
    status: Literal["created", "dry_run"]
