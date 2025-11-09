"""GitHub adapter for Chad-Core.

Provides tools for interacting with GitHub:
- Search issues and pull requests
- Get pull request details
- List repositories
- Create issues
- Add comments

Usage:
    from chad_tools.adapters.github import register_github_tools
    from chad_tools.registry import ToolRegistry

    registry = ToolRegistry()
    register_github_tools(registry, token="ghp_...")
"""

from .client import GitHubClientWrapper
from .exceptions import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubValidationError,
)
from .schemas import (
    SearchIssuesInput,
    SearchIssuesOutput,
    IssueResult,
    GetPullRequestInput,
    GetPullRequestOutput,
    PRFileChange,
    ListRepositoriesInput,
    ListRepositoriesOutput,
    RepositoryResult,
    CreateIssueInput,
    CreateIssueOutput,
    AddCommentInput,
    AddCommentOutput,
)
from .tools import (
    SearchIssuesTool,
    GetPullRequestTool,
    ListRepositoriesTool,
    CreateIssueTool,
    AddCommentTool,
)

__all__ = [
    # Client
    "GitHubClientWrapper",
    # Exceptions
    "GitHubAPIError",
    "GitHubAuthError",
    "GitHubNotFoundError",
    "GitHubRateLimitError",
    "GitHubValidationError",
    # Schemas
    "SearchIssuesInput",
    "SearchIssuesOutput",
    "IssueResult",
    "GetPullRequestInput",
    "GetPullRequestOutput",
    "PRFileChange",
    "ListRepositoriesInput",
    "ListRepositoriesOutput",
    "RepositoryResult",
    "CreateIssueInput",
    "CreateIssueOutput",
    "AddCommentInput",
    "AddCommentOutput",
    # Tools
    "SearchIssuesTool",
    "GetPullRequestTool",
    "ListRepositoriesTool",
    "CreateIssueTool",
    "AddCommentTool",
]


def register_github_tools(registry, token: str) -> None:
    """Register all GitHub tools with the tool registry.

    Args:
        registry: ToolRegistry instance
        token: GitHub personal access token

    Example:
        from chad_tools.registry import ToolRegistry
        from chad_tools.adapters.github import register_github_tools

        registry = ToolRegistry()
        register_github_tools(registry, token="ghp_...")
    """
    registry.register(SearchIssuesTool(token=token))
    registry.register(GetPullRequestTool(token=token))
    registry.register(ListRepositoriesTool(token=token))
    registry.register(CreateIssueTool(token=token))
    registry.register(AddCommentTool(token=token))
