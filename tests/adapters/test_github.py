"""Tests for GitHub adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from chad_tools.adapters.github import (
    SearchIssuesTool,
    GetPullRequestTool,
    ListRepositoriesTool,
    CreateIssueTool,
    AddCommentTool,
)
from chad_tools.adapters.github.exceptions import GitHubAPIError, GitHubNotFoundError


@pytest.fixture
def github_token():
    """Mock GitHub token."""
    return "ghp_mock_token_12345"


@pytest.fixture
def mock_ctx():
    """Mock execution context."""
    return {"actor": "test_user", "trace_id": "test_trace"}


class TestSearchIssuesTool:
    """Tests for SearchIssuesTool."""

    @pytest.mark.asyncio
    async def test_dry_run_mode(self, github_token, mock_ctx):
        """Test dry-run mode returns mock data."""
        tool = SearchIssuesTool(token=github_token)
        input_data = {"query": "bug", "repo": "owner/repo", "state": "open", "dry_run": True}

        result = await tool.execute(mock_ctx, input_data)

        assert result["status"] == "dry_run"
        assert result["total_count"] == 1
        assert "warning" in result

    @pytest.mark.asyncio
    async def test_search_issues_success(self, github_token, mock_ctx):
        """Test successful issue search."""
        tool = SearchIssuesTool(token=github_token)
        mock_response = {
            "total_count": 1,
            "items": [
                {
                    "number": 42,
                    "title": "Test Issue",
                    "state": "open",
                    "labels": [{"name": "bug"}],
                    "user": {"login": "testuser"},
                    "created_at": "2025-11-03T00:00:00Z",
                    "html_url": "https://github.com/owner/repo/issues/42",
                    "body": "Test body",
                }
            ],
        }

        with patch.object(tool.client, "search_issues", AsyncMock(return_value=mock_response)):
            input_data = {"query": "bug", "repo": "owner/repo", "state": "open"}
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "success"
            assert result["total_count"] == 1
            assert result["results"][0]["number"] == 42
            assert result["results"][0]["title"] == "Test Issue"


class TestGetPullRequestTool:
    """Tests for GetPullRequestTool."""

    @pytest.mark.asyncio
    async def test_dry_run_mode(self, github_token, mock_ctx):
        """Test dry-run mode."""
        tool = GetPullRequestTool(token=github_token)
        input_data = {"owner": "owner", "repo": "repo", "pr_number": 1, "dry_run": True}

        result = await tool.execute(mock_ctx, input_data)

        assert result["status"] == "dry_run"
        assert result["number"] == 1

    @pytest.mark.asyncio
    async def test_get_pr_success(self, github_token, mock_ctx):
        """Test successful PR fetch."""
        tool = GetPullRequestTool(token=github_token)
        mock_pr = {
            "number": 1,
            "title": "Test PR",
            "body": "Test description",
            "state": "open",
            "merged": False,
            "user": {"login": "testuser"},
            "created_at": "2025-11-03T00:00:00Z",
            "updated_at": "2025-11-03T12:00:00Z",
            "merged_at": None,
            "comments": 5,
            "review_comments": 3,
            "html_url": "https://github.com/owner/repo/pull/1",
        }
        mock_files = [
            {
                "filename": "test.py",
                "status": "modified",
                "additions": 10,
                "deletions": 5,
                "changes": 15,
            }
        ]

        with patch.object(tool.client, "get_pull_request", AsyncMock(return_value=mock_pr)):
            with patch.object(tool.client, "get_pull_request_files", AsyncMock(return_value=mock_files)):
                input_data = {"owner": "owner", "repo": "repo", "pr_number": 1}
                result = await tool.execute(mock_ctx, input_data)

                assert result["status"] == "success"
                assert result["number"] == 1
                assert result["title"] == "Test PR"
                assert len(result["files_changed"]) == 1


class TestListRepositoriesTool:
    """Tests for ListRepositoriesTool."""

    @pytest.mark.asyncio
    async def test_list_repos_success(self, github_token, mock_ctx):
        """Test successful repo listing."""
        tool = ListRepositoriesTool(token=github_token)
        mock_repos = [
            {
                "name": "test-repo",
                "full_name": "owner/test-repo",
                "description": "Test repo",
                "stargazers_count": 42,
                "language": "Python",
                "updated_at": "2025-11-03T00:00:00Z",
                "html_url": "https://github.com/owner/test-repo",
                "private": False,
            }
        ]

        with patch.object(tool.client, "list_repositories", AsyncMock(return_value=mock_repos)):
            input_data = {"user": "testuser", "visibility": "all"}
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "success"
            assert result["total_count"] == 1
            assert result["results"][0]["name"] == "test-repo"


class TestCreateIssueTool:
    """Tests for CreateIssueTool."""

    @pytest.mark.asyncio
    async def test_create_issue_success(self, github_token, mock_ctx):
        """Test successful issue creation."""
        tool = CreateIssueTool(token=github_token)
        mock_issue = {
            "number": 42,
            "html_url": "https://github.com/owner/repo/issues/42",
            "title": "New Issue",
            "created_at": "2025-11-03T00:00:00Z",
        }

        with patch.object(tool.client, "create_issue", AsyncMock(return_value=mock_issue)):
            input_data = {
                "owner": "owner",
                "repo": "repo",
                "title": "New Issue",
                "body": "Issue body",
                "labels": ["bug"],
            }
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "created"
            assert result["number"] == 42
            assert result["title"] == "New Issue"


class TestAddCommentTool:
    """Tests for AddCommentTool."""

    @pytest.mark.asyncio
    async def test_add_comment_success(self, github_token, mock_ctx):
        """Test successful comment addition."""
        tool = AddCommentTool(token=github_token)
        mock_comment = {
            "id": 123456789,
            "html_url": "https://github.com/owner/repo/issues/42#issuecomment-123456789",
            "created_at": "2025-11-03T00:00:00Z",
        }

        with patch.object(tool.client, "add_comment", AsyncMock(return_value=mock_comment)):
            input_data = {
                "owner": "owner",
                "repo": "repo",
                "issue_number": 42,
                "comment": "Test comment",
            }
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "created"
            assert result["comment_id"] == 123456789
