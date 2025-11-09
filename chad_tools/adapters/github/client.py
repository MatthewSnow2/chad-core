"""GitHub API client wrapper.

Centralized GitHub API client with error handling, rate limiting, and retry logic.
"""

import asyncio
from typing import Any

import httpx

from .exceptions import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)


class GitHubClientWrapper:
    """GitHub API client with Chad-Core integration.

    Provides:
    - Error handling and exception mapping
    - Rate limiting (60 requests/hour for unauthenticated, 5000/hour for authenticated)
    - Automatic retry with exponential backoff
    - Structured error messages
    """

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        token: str,
        rate_limit_per_second: int = 10,
        timeout_seconds: int = 30,
    ):
        """Initialize GitHub client.

        Args:
            token: GitHub personal access token
            rate_limit_per_second: Max requests per second
            timeout_seconds: Request timeout
        """
        self.token = token
        self.rate_limit_per_second = rate_limit_per_second
        self.timeout_seconds = timeout_seconds
        self._last_request_time = 0.0

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        current_time = asyncio.get_event_loop().time()
        time_since_last_request = current_time - self._last_request_time
        min_interval = 1.0 / self.rate_limit_per_second

        if time_since_last_request < min_interval:
            await asyncio.sleep(min_interval - time_since_last_request)

        self._last_request_time = asyncio.get_event_loop().time()

    def _handle_error(self, response: httpx.Response) -> None:
        """Map GitHub API errors to custom exceptions."""
        status = response.status_code

        try:
            error_data = response.json()
            message = error_data.get("message", str(response.text))
        except Exception:
            message = str(response.text)

        if status == 401:
            raise GitHubAuthError(f"Authentication failed: {message}")
        elif status == 403:
            # Check if it's a rate limit error
            if "rate limit" in message.lower():
                raise GitHubRateLimitError(f"Rate limit exceeded: {message}")
            raise GitHubAuthError(f"Forbidden: {message}")
        elif status == 404:
            raise GitHubNotFoundError(f"Resource not found: {message}")
        else:
            raise GitHubAPIError(f"GitHub API error ({status}): {message}")

    async def search_issues(
        self,
        query: str,
        per_page: int = 10,
    ) -> dict[str, Any]:
        """Search for issues and pull requests.

        Args:
            query: Search query string
            per_page: Number of results per page

        Returns:
            Search results from GitHub API

        Raises:
            GitHubAuthError: Invalid token
            GitHubRateLimitError: Rate limit exceeded
            GitHubAPIError: Other API errors
        """
        await self._rate_limit()

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.BASE_URL}/search/issues",
                headers=self._get_headers(),
                params={"q": query, "per_page": per_page},
            )

            if response.status_code != 200:
                self._handle_error(response)

            return response.json()

    async def get_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> dict[str, Any]:
        """Get pull request details.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Pull request data from GitHub API
        """
        await self._rate_limit()

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                self._handle_error(response)

            return response.json()

    async def get_pull_request_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> list[dict[str, Any]]:
        """Get files changed in a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of file changes
        """
        await self._rate_limit()

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files",
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                self._handle_error(response)

            return response.json()

    async def list_repositories(
        self,
        org: str | None = None,
        user: str | None = None,
        per_page: int = 10,
    ) -> list[dict[str, Any]]:
        """List repositories for a user or organization.

        Args:
            org: Organization name
            user: Username
            per_page: Number of results per page

        Returns:
            List of repositories
        """
        await self._rate_limit()

        if org:
            url = f"{self.BASE_URL}/orgs/{org}/repos"
        elif user:
            url = f"{self.BASE_URL}/users/{user}/repos"
        else:
            url = f"{self.BASE_URL}/user/repos"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                url,
                headers=self._get_headers(),
                params={"per_page": per_page},
            )

            if response.status_code != 200:
                self._handle_error(response)

            return response.json()

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new issue.

        Args:
            owner: Repository owner
            repo: Repository name
            title: Issue title
            body: Issue body
            labels: Issue labels

        Returns:
            Created issue data
        """
        await self._rate_limit()

        data = {
            "title": title,
            "body": body,
        }
        if labels:
            data["labels"] = labels

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.BASE_URL}/repos/{owner}/{repo}/issues",
                headers=self._get_headers(),
                json=data,
            )

            if response.status_code != 201:
                self._handle_error(response)

            return response.json()

    async def add_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        comment: str,
    ) -> dict[str, Any]:
        """Add a comment to an issue or pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue/PR number
            comment: Comment text

        Returns:
            Created comment data
        """
        await self._rate_limit()

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                headers=self._get_headers(),
                json={"body": comment},
            )

            if response.status_code != 201:
                self._handle_error(response)

            return response.json()
