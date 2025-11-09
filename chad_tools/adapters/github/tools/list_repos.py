"""GitHub List Repositories Tool.

List repositories for a user or organization.
"""

from typing import Any

from chad_tools.base import ToolMetadata
from chad_tools.adapters.github.client import GitHubClientWrapper
from chad_tools.adapters.github.schemas import (
    ListRepositoriesInput,
    ListRepositoriesOutput,
    RepositoryResult,
)
from chad_tools.adapters.github.exceptions import GitHubAPIError


class ListRepositoriesTool:
    """Tool for listing GitHub repositories.

    Capabilities:
    - List user repositories
    - List organization repositories
    - Filter by visibility

    Use Cases:
    - "List all my repositories"
    - "Show repositories for organization X"
    - "Find public repos for user Y"
    """

    name = "github.list_repositories"
    description = "List GitHub repositories for a user or organization"

    metadata = ToolMetadata(
        requires_approval=False,
        dry_run_supported=True,
        idempotent=True,
        capabilities=["github.read"],
        risk_level="low",
    )

    def __init__(self, token: str, **kwargs):
        """Initialize ListRepositoriesTool.

        Args:
            token: GitHub API token
            **kwargs: Additional client configuration
        """
        self.client = GitHubClientWrapper(token=token, **kwargs)

    async def execute(
        self, ctx: dict[str, Any], input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute list repositories.

        Args:
            ctx: Execution context (actor, trace_id, etc.)
            input_data: Tool input matching ListRepositoriesInput schema

        Returns:
            Repository list matching ListRepositoriesOutput schema

        Raises:
            GitHubAPIError: API errors
        """
        # Validate input
        input_obj = ListRepositoriesInput(**input_data)

        # Handle dry-run mode
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            # Get repositories
            repos_data = await self.client.list_repositories(
                org=input_obj.org,
                user=input_obj.user,
                per_page=input_obj.limit,
            )

            # Parse results
            results = []
            for repo in repos_data:
                # Filter by visibility
                if input_obj.visibility == "public" and repo.get("private", False):
                    continue
                elif input_obj.visibility == "private" and not repo.get("private", False):
                    continue

                result = RepositoryResult(
                    name=repo["name"],
                    full_name=repo["full_name"],
                    description=repo.get("description"),
                    stars=repo.get("stargazers_count", 0),
                    language=repo.get("language"),
                    updated_at=repo["updated_at"],
                    url=repo["html_url"],
                    private=repo.get("private", False),
                )
                results.append(result)

                # Respect limit after filtering
                if len(results) >= input_obj.limit:
                    break

            # Build output
            output = ListRepositoriesOutput(
                results=results,
                total_count=len(results),
                status="success",
            )

            return output.model_dump()

        except GitHubAPIError:
            raise
        except Exception as e:
            raise GitHubAPIError(f"Unexpected error listing repositories: {str(e)}")

    def _dry_run_response(self, input_obj: ListRepositoriesInput) -> dict[str, Any]:
        """Generate dry-run mock response.

        Args:
            input_obj: Validated input

        Returns:
            Mock response matching ListRepositoriesOutput schema
        """
        mock_repo = RepositoryResult(
            name="mock-repo",
            full_name=f"{input_obj.org or input_obj.user or 'user'}/mock-repo",
            description="This is a mock repository for dry-run testing.",
            stars=42,
            language="Python",
            updated_at="2025-11-03T00:00:00Z",
            url=f"https://github.com/{input_obj.org or input_obj.user or 'user'}/mock-repo",
            private=False,
        )

        output = ListRepositoriesOutput(
            results=[mock_repo],
            total_count=1,
            status="dry_run",
        )

        return {
            **output.model_dump(),
            "warning": "This is a dry-run response; no real GitHub API call was made",
            "would_execute": f"github.list_repositories(org='{input_obj.org}', user='{input_obj.user}', visibility='{input_obj.visibility}')",
        }
