"""Tests for Slack adapter."""

import pytest
from unittest.mock import AsyncMock, patch

from chad_tools.adapters.slack import (
    SendMessageTool,
    GetChannelInfoTool,
    ListChannelsTool,
    AddReactionTool,
    UploadFileTool,
)


@pytest.fixture
def slack_token():
    """Mock Slack bot token."""
    return "xoxb-mock-token-12345"


@pytest.fixture
def mock_ctx():
    """Mock execution context."""
    return {"actor": "test_user", "trace_id": "test_trace"}


class TestSendMessageTool:
    """Tests for SendMessageTool."""

    @pytest.mark.asyncio
    async def test_dry_run_mode(self, slack_token, mock_ctx):
        """Test dry-run mode."""
        tool = SendMessageTool(bot_token=slack_token)
        input_data = {
            "channel": "C1234567890",
            "text": "Test message",
            "dry_run": True,
        }

        result = await tool.execute(mock_ctx, input_data)

        assert result["status"] == "dry_run"
        assert result["channel"] == "C1234567890"

    @pytest.mark.asyncio
    async def test_send_message_success(self, slack_token, mock_ctx):
        """Test successful message send."""
        tool = SendMessageTool(bot_token=slack_token)
        mock_response = {
            "ok": True,
            "ts": "1234567890.123456",
            "channel": "C1234567890",
        }

        with patch.object(tool.client, "post_message", AsyncMock(return_value=mock_response)):
            input_data = {
                "channel": "C1234567890",
                "text": "Test message",
            }
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "sent"
            assert result["ts"] == "1234567890.123456"


class TestGetChannelInfoTool:
    """Tests for GetChannelInfoTool."""

    @pytest.mark.asyncio
    async def test_get_channel_info_success(self, slack_token, mock_ctx):
        """Test successful channel info retrieval."""
        tool = GetChannelInfoTool(bot_token=slack_token)
        mock_response = {
            "ok": True,
            "channel": {
                "id": "C1234567890",
                "name": "general",
                "topic": {"value": "Company announcements"},
                "purpose": {"value": "General discussion"},
                "num_members": 100,
                "is_private": False,
            },
        }

        with patch.object(tool.client, "get_channel_info", AsyncMock(return_value=mock_response)):
            input_data = {"channel_id": "C1234567890"}
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "success"
            assert result["name"] == "general"
            assert result["member_count"] == 100


class TestListChannelsTool:
    """Tests for ListChannelsTool."""

    @pytest.mark.asyncio
    async def test_list_channels_success(self, slack_token, mock_ctx):
        """Test successful channel listing."""
        tool = ListChannelsTool(bot_token=slack_token)
        mock_response = {
            "ok": True,
            "channels": [
                {
                    "id": "C1234567890",
                    "name": "general",
                    "topic": {"value": "General discussion"},
                    "num_members": 100,
                    "is_private": False,
                }
            ],
        }

        with patch.object(tool.client, "list_channels", AsyncMock(return_value=mock_response)):
            input_data = {"exclude_archived": True}
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "success"
            assert len(result["results"]) == 1
            assert result["results"][0]["name"] == "general"


class TestAddReactionTool:
    """Tests for AddReactionTool."""

    @pytest.mark.asyncio
    async def test_add_reaction_success(self, slack_token, mock_ctx):
        """Test successful reaction addition."""
        tool = AddReactionTool(bot_token=slack_token)
        mock_response = {"ok": True}

        with patch.object(tool.client, "add_reaction", AsyncMock(return_value=mock_response)):
            input_data = {
                "channel": "C1234567890",
                "timestamp": "1234567890.123456",
                "emoji": "thumbsup",
            }
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "added"
            assert result["success"] is True


class TestUploadFileTool:
    """Tests for UploadFileTool."""

    @pytest.mark.asyncio
    async def test_upload_file_success(self, slack_token, mock_ctx):
        """Test successful file upload."""
        tool = UploadFileTool(bot_token=slack_token)
        mock_response = {
            "ok": True,
            "file": {
                "id": "F1234567890",
                "name": "test.txt",
                "permalink": "https://slack.com/files/test.txt",
            },
        }

        with patch.object(tool.client, "upload_file", AsyncMock(return_value=mock_response)):
            input_data = {
                "channels": ["C1234567890"],
                "file_content": "VGVzdCBjb250ZW50",  # base64 "Test content"
                "filename": "test.txt",
            }
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "uploaded"
            assert result["file_id"] == "F1234567890"
