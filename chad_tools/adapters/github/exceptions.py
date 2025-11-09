"""GitHub adapter exceptions.

Custom exception hierarchy for GitHub API errors.
"""


class GitHubAPIError(Exception):
    """Base exception for GitHub adapter."""

    pass


class GitHubAuthError(GitHubAPIError):
    """Invalid API token or insufficient permissions."""

    pass


class GitHubNotFoundError(GitHubAPIError):
    """Repository, issue, or PR not found (404 response)."""

    pass


class GitHubRateLimitError(GitHubAPIError):
    """Rate limit exceeded (403 with rate limit headers)."""

    pass


class GitHubValidationError(GitHubAPIError):
    """Invalid input parameters."""

    pass
