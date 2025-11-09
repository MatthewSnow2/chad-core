"""GitHub Get Pull Request Tool.

Get detailed information about a pull request.
"""

from typing import Any

from chad_tools.base import ToolMetadata
from chad_tools.adapters.github.client import GitHubClientWrapper
from chad_tools.adapters.github.schemas import (
    GetPullRequestInput,
    GetPullRequestOutput,
    PRFileChange,
)
from chad_tools.adapters.github.exceptions import GitHubAPIError


class GetPullRequestTool:
    """Tool for getting GitHub pull request details.

    Capabilities:
    - Get PR metadata (title, description, state)
    - List files changed
    - Count comments and reviews

    Use Cases:
    - "Get details for PR #42"
    - "Show files changed in PR #100"
    - "Check PR status and reviews"
    """

    name = "github.get_pull_request"
    description = "Get detailed information about a GitHub pull request"

    metadata = ToolMetadata(
        requires_approval=False,
        dry_run_supported=True,
        idempotent=True,
        capabilities=["github.read"],
        risk_level="low",
    )

    def __init__(self, token: str, **kwargs):
        """Initialize GetPullRequestTool.

        Args:
            token: GitHub API token
            **kwargs: Additional client configuration
        """
        self.client = GitHubClientWrapper(token=token, **kwargs)

    async def execute(
        self, ctx: dict[str, Any], input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute get pull request.

        Args:
            ctx: Execution context (actor, trace_id, etc.)
            input_data: Tool input matching GetPullRequestInput schema

        Returns:
            PR details matching GetPullRequestOutput schema

        Raises:
            GitHubAPIError: API errors
        """
        # Validate input
        input_obj = GetPullRequestInput(**input_data)

        # Handle dry-run mode
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            # Get PR details
            pr_data = await self.client.get_pull_request(
                owner=input_obj.owner,
                repo=input_obj.repo,
                pr_number=input_obj.pr_number,
            )

            # Get PR files
            files_data = await self.client.get_pull_request_files(
                owner=input_obj.owner,
                repo=input_obj.repo,
                pr_number=input_obj.pr_number,
            )

            # Parse files
            files_changed = []
            for file in files_data:
                file_change = PRFileChange(
                    filename=file["filename"],
                    status=file["status"],
                    additions=file["additions"],
                    deletions=file["deletions"],
                    changes=file["changes"],
                )
                files_changed.append(file_change)

            # Determine state
            state = "merged" if pr_data.get("merged") else pr_data["state"]

            # Build output
            output = GetPullRequestOutput(
                number=pr_data["number"],
                title=pr_data["title"],
                description=pr_data.get("body", ""),
                state=state,
                author=pr_data["user"]["login"],
                created_at=pr_data["created_at"],
                updated_at=pr_data["updated_at"],
                merged_at=pr_data.get("merged_at"),
                files_changed=files_changed,
                comments_count=pr_data.get("comments", 0),
                reviews_count=pr_data.get("review_comments", 0),
                url=pr_data["html_url"],
                status="success",
            )

            return output.model_dump()

        except GitHubAPIError:
            raise
        except Exception as e:
            raise GitHubAPIError(f"Unexpected error getting PR: {str(e)}")

    def _dry_run_response(self, input_obj: GetPullRequestInput) -> dict[str, Any]:
        """Generate dry-run mock response.

        Args:
            input_obj: Validated input

        Returns:
            Mock response matching GetPullRequestOutput schema
        """
        mock_file = PRFileChange(
            filename="mock/file.py",
            status="modified",
            additions=10,
            deletions=5,
            changes=15,
        )

        output = GetPullRequestOutput(
            number=input_obj.pr_number,
            title=f"Mock PR #{input_obj.pr_number}",
            description="This is a mock pull request for dry-run testing.",
            state="open",
            author="mock-user",
            created_at="2025-11-03T00:00:00Z",
            updated_at="2025-11-03T12:00:00Z",
            merged_at=None,
            files_changed=[mock_file],
            comments_count=3,
            reviews_count=2,
            url=f"https://github.com/{input_obj.owner}/{input_obj.repo}/pull/{input_obj.pr_number}",
            status="dry_run",
        )

        return {
            **output.model_dump(),
            "warning": "This is a dry-run response; no real GitHub API call was made",
            "would_execute": f"github.get_pull_request(owner='{input_obj.owner}', repo='{input_obj.repo}', pr_number={input_obj.pr_number})",
        }
