"""GitHub Search Issues Tool.

Search for issues and pull requests across GitHub.
"""

from typing import Any

from chad_tools.base import ToolMetadata
from chad_tools.adapters.github.client import GitHubClientWrapper
from chad_tools.adapters.github.schemas import (
    SearchIssuesInput,
    SearchIssuesOutput,
    IssueResult,
)
from chad_tools.adapters.github.exceptions import GitHubAPIError


class SearchIssuesTool:
    """Tool for searching GitHub issues and pull requests.

    Capabilities:
    - Search for issues across repositories
    - Filter by repository, state
    - Return structured results with URLs

    Use Cases:
    - "Find all open issues in repo X"
    - "Search for bugs with label 'critical'"
    - "Find PRs created by user Y"
    """

    name = "github.search_issues"
    description = "Search for GitHub issues and pull requests"

    metadata = ToolMetadata(
        requires_approval=False,
        dry_run_supported=True,
        idempotent=True,
        capabilities=["github.search", "github.read"],
        risk_level="low",
    )

    def __init__(self, token: str, **kwargs):
        """Initialize SearchIssuesTool.

        Args:
            token: GitHub API token
            **kwargs: Additional client configuration
        """
        self.client = GitHubClientWrapper(token=token, **kwargs)

    async def execute(
        self, ctx: dict[str, Any], input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute search query.

        Args:
            ctx: Execution context (actor, trace_id, etc.)
            input_data: Tool input matching SearchIssuesInput schema

        Returns:
            Search results matching SearchIssuesOutput schema

        Raises:
            GitHubAPIError: API errors
        """
        # Validate input
        input_obj = SearchIssuesInput(**input_data)

        # Handle dry-run mode
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            # Build search query
            query = input_obj.query
            if input_obj.repo:
                query += f" repo:{input_obj.repo}"
            if input_obj.state != "all":
                query += f" state:{input_obj.state}"
            query += " type:issue"  # Only search issues, not PRs

            # Execute search
            response = await self.client.search_issues(
                query=query,
                per_page=input_obj.limit,
            )

            # Parse results
            results = []
            for item in response.get("items", []):
                result = IssueResult(
                    number=item["number"],
                    title=item["title"],
                    state=item["state"],
                    labels=[label["name"] for label in item.get("labels", [])],
                    author=item["user"]["login"],
                    created_at=item["created_at"],
                    url=item["html_url"],
                    body=item.get("body", ""),
                )
                results.append(result)

            # Build output
            output = SearchIssuesOutput(
                results=results,
                total_count=response.get("total_count", len(results)),
                status="success",
            )

            return output.model_dump()

        except GitHubAPIError:
            raise
        except Exception as e:
            raise GitHubAPIError(f"Unexpected error during search: {str(e)}")

    def _dry_run_response(self, input_obj: SearchIssuesInput) -> dict[str, Any]:
        """Generate dry-run mock response.

        Args:
            input_obj: Validated input

        Returns:
            Mock response matching SearchIssuesOutput schema
        """
        mock_result = IssueResult(
            number=123,
            title=f"Mock issue for query: '{input_obj.query}'",
            state="open",
            labels=["bug", "mock"],
            author="mock-user",
            created_at="2025-11-03T00:00:00Z",
            url="https://github.com/mock/repo/issues/123",
            body="This is a mock issue for dry-run testing.",
        )

        output = SearchIssuesOutput(
            results=[mock_result],
            total_count=1,
            status="dry_run",
        )

        return {
            **output.model_dump(),
            "warning": "This is a dry-run response; no real GitHub API call was made",
            "would_execute": f"github.search_issues(query='{input_obj.query}', repo={input_obj.repo}, state={input_obj.state})",
        }
