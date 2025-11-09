"""GitHub Create Issue Tool.

Create a new issue in a repository.
"""

from typing import Any

from chad_tools.base import ToolMetadata
from chad_tools.adapters.github.client import GitHubClientWrapper
from chad_tools.adapters.github.schemas import (
    CreateIssueInput,
    CreateIssueOutput,
)
from chad_tools.adapters.github.exceptions import GitHubAPIError


class CreateIssueTool:
    """Tool for creating GitHub issues.

    Capabilities:
    - Create new issues
    - Add labels to issues
    - Set issue title and body

    Use Cases:
    - "Create a bug report issue"
    - "Open issue for feature request"
    - "Report bug with labels"
    """

    name = "github.create_issue"
    description = "Create a new issue in a GitHub repository"

    metadata = ToolMetadata(
        requires_approval=True,  # Creating issues requires approval
        dry_run_supported=True,
        idempotent=False,  # Creating multiple times creates multiple issues
        capabilities=["github.write"],
        risk_level="medium",
    )

    def __init__(self, token: str, **kwargs):
        """Initialize CreateIssueTool.

        Args:
            token: GitHub API token
            **kwargs: Additional client configuration
        """
        self.client = GitHubClientWrapper(token=token, **kwargs)

    async def execute(
        self, ctx: dict[str, Any], input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute create issue.

        Args:
            ctx: Execution context (actor, trace_id, etc.)
            input_data: Tool input matching CreateIssueInput schema

        Returns:
            Created issue matching CreateIssueOutput schema

        Raises:
            GitHubAPIError: API errors
        """
        # Validate input
        input_obj = CreateIssueInput(**input_data)

        # Handle dry-run mode
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            # Create issue
            issue_data = await self.client.create_issue(
                owner=input_obj.owner,
                repo=input_obj.repo,
                title=input_obj.title,
                body=input_obj.body,
                labels=input_obj.labels if input_obj.labels else None,
            )

            # Build output
            output = CreateIssueOutput(
                number=issue_data["number"],
                url=issue_data["html_url"],
                title=issue_data["title"],
                created_at=issue_data["created_at"],
                status="created",
            )

            return output.model_dump()

        except GitHubAPIError:
            raise
        except Exception as e:
            raise GitHubAPIError(f"Unexpected error creating issue: {str(e)}")

    def _dry_run_response(self, input_obj: CreateIssueInput) -> dict[str, Any]:
        """Generate dry-run mock response.

        Args:
            input_obj: Validated input

        Returns:
            Mock response matching CreateIssueOutput schema
        """
        output = CreateIssueOutput(
            number=999,
            url=f"https://github.com/{input_obj.owner}/{input_obj.repo}/issues/999",
            title=input_obj.title,
            created_at="2025-11-03T00:00:00Z",
            status="dry_run",
        )

        return {
            **output.model_dump(),
            "warning": "This is a dry-run response; no real GitHub API call was made",
            "would_execute": f"github.create_issue(owner='{input_obj.owner}', repo='{input_obj.repo}', title='{input_obj.title}', labels={input_obj.labels})",
        }
