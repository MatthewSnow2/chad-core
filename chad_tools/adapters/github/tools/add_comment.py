"""GitHub Add Comment Tool.

Add a comment to an issue or pull request.
"""

from typing import Any

from chad_tools.base import ToolMetadata
from chad_tools.adapters.github.client import GitHubClientWrapper
from chad_tools.adapters.github.schemas import (
    AddCommentInput,
    AddCommentOutput,
)
from chad_tools.adapters.github.exceptions import GitHubAPIError


class AddCommentTool:
    """Tool for adding comments to GitHub issues/PRs.

    Capabilities:
    - Add comments to issues
    - Add comments to pull requests
    - Participate in discussions

    Use Cases:
    - "Comment on issue #42"
    - "Add review comment to PR"
    - "Reply to discussion"
    """

    name = "github.add_comment"
    description = "Add a comment to a GitHub issue or pull request"

    metadata = ToolMetadata(
        requires_approval=True,  # Adding comments requires approval
        dry_run_supported=True,
        idempotent=False,  # Adding multiple times creates multiple comments
        capabilities=["github.write"],
        risk_level="medium",
    )

    def __init__(self, token: str, **kwargs):
        """Initialize AddCommentTool.

        Args:
            token: GitHub API token
            **kwargs: Additional client configuration
        """
        self.client = GitHubClientWrapper(token=token, **kwargs)

    async def execute(
        self, ctx: dict[str, Any], input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute add comment.

        Args:
            ctx: Execution context (actor, trace_id, etc.)
            input_data: Tool input matching AddCommentInput schema

        Returns:
            Created comment matching AddCommentOutput schema

        Raises:
            GitHubAPIError: API errors
        """
        # Validate input
        input_obj = AddCommentInput(**input_data)

        # Handle dry-run mode
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            # Add comment
            comment_data = await self.client.add_comment(
                owner=input_obj.owner,
                repo=input_obj.repo,
                issue_number=input_obj.issue_number,
                comment=input_obj.comment,
            )

            # Build output
            output = AddCommentOutput(
                comment_id=comment_data["id"],
                url=comment_data["html_url"],
                created_at=comment_data["created_at"],
                status="created",
            )

            return output.model_dump()

        except GitHubAPIError:
            raise
        except Exception as e:
            raise GitHubAPIError(f"Unexpected error adding comment: {str(e)}")

    def _dry_run_response(self, input_obj: AddCommentInput) -> dict[str, Any]:
        """Generate dry-run mock response.

        Args:
            input_obj: Validated input

        Returns:
            Mock response matching AddCommentOutput schema
        """
        output = AddCommentOutput(
            comment_id=123456789,
            url=f"https://github.com/{input_obj.owner}/{input_obj.repo}/issues/{input_obj.issue_number}#issuecomment-123456789",
            created_at="2025-11-03T00:00:00Z",
            status="dry_run",
        )

        return {
            **output.model_dump(),
            "warning": "This is a dry-run response; no real GitHub API call was made",
            "would_execute": f"github.add_comment(owner='{input_obj.owner}', repo='{input_obj.repo}', issue_number={input_obj.issue_number})",
        }
