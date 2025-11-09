"""Tests for Google Workspace adapter."""

import pytest
from unittest.mock import AsyncMock, patch

from chad_tools.adapters.google import (
    SendEmailTool,
    SearchDriveTool,
    GetCalendarEventsTool,
    CreateCalendarEventTool,
    ReadDocumentTool,
)


@pytest.fixture
def google_creds():
    """Mock Google credentials."""
    return {"token": "mock_access_token"}


@pytest.fixture
def mock_ctx():
    """Mock execution context."""
    return {"actor": "test_user", "trace_id": "test_trace"}


class TestSendEmailTool:
    """Tests for SendEmailTool."""

    @pytest.mark.asyncio
    async def test_dry_run_mode(self, mock_ctx):
        """Test dry-run mode."""
        tool = SendEmailTool(credentials_json='{"token": "mock"}')
        input_data = {
            "to": "test@example.com",
            "subject": "Test",
            "body": "Test body",
            "dry_run": True,
        }

        result = await tool.execute(mock_ctx, input_data)

        assert result["status"] == "dry_run"
        assert result["to"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_send_email_success(self, mock_ctx):
        """Test successful email send."""
        tool = SendEmailTool(credentials_json='{"token": "mock"}')
        mock_response = {
            "id": "msg123",
            "threadId": "thread123",
        }

        with patch.object(tool.client, "send_email", AsyncMock(return_value=mock_response)):
            input_data = {
                "to": "test@example.com",
                "subject": "Test",
                "body": "Test body",
            }
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "sent"
            assert result["message_id"] == "msg123"


class TestSearchDriveTool:
    """Tests for SearchDriveTool."""

    @pytest.mark.asyncio
    async def test_search_drive_success(self, mock_ctx):
        """Test successful Drive search."""
        tool = SearchDriveTool(credentials_json='{"token": "mock"}')
        mock_response = {
            "files": [
                {
                    "id": "file123",
                    "name": "test.pdf",
                    "mimeType": "application/pdf",
                    "size": "1024",
                    "modifiedTime": "2025-11-03T00:00:00Z",
                    "webViewLink": "https://drive.google.com/file/file123",
                    "owners": [{"emailAddress": "owner@example.com"}],
                }
            ]
        }

        with patch.object(tool.client, "search_drive", AsyncMock(return_value=mock_response)):
            input_data = {"query": "test", "limit": 10}
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "success"
            assert len(result["results"]) == 1
            assert result["results"][0]["name"] == "test.pdf"


class TestGetCalendarEventsTool:
    """Tests for GetCalendarEventsTool."""

    @pytest.mark.asyncio
    async def test_get_events_success(self, mock_ctx):
        """Test successful event retrieval."""
        tool = GetCalendarEventsTool(credentials_json='{"token": "mock"}')
        mock_response = {
            "items": [
                {
                    "id": "event123",
                    "summary": "Test Meeting",
                    "start": {"dateTime": "2025-11-03T10:00:00Z"},
                    "end": {"dateTime": "2025-11-03T11:00:00Z"},
                    "attendees": [{"email": "attendee@example.com", "responseStatus": "accepted"}],
                    "location": "Office",
                    "description": "Test event",
                    "htmlLink": "https://calendar.google.com/event123",
                }
            ]
        }

        with patch.object(tool.client, "get_calendar_events", AsyncMock(return_value=mock_response)):
            input_data = {
                "calendar_id": "primary",
                "time_min": "2025-11-03T00:00:00Z",
                "time_max": "2025-11-03T23:59:59Z",
            }
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "success"
            assert len(result["results"]) == 1
            assert result["results"][0]["summary"] == "Test Meeting"


class TestCreateCalendarEventTool:
    """Tests for CreateCalendarEventTool."""

    @pytest.mark.asyncio
    async def test_create_event_success(self, mock_ctx):
        """Test successful event creation."""
        tool = CreateCalendarEventTool(credentials_json='{"token": "mock"}')
        mock_response = {
            "id": "event123",
            "htmlLink": "https://calendar.google.com/event123",
            "summary": "New Meeting",
            "start": {"dateTime": "2025-11-03T10:00:00Z"},
            "end": {"dateTime": "2025-11-03T11:00:00Z"},
        }

        with patch.object(tool.client, "create_calendar_event", AsyncMock(return_value=mock_response)):
            input_data = {
                "summary": "New Meeting",
                "start_time": "2025-11-03T10:00:00Z",
                "end_time": "2025-11-03T11:00:00Z",
            }
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "created"
            assert result["event_id"] == "event123"


class TestReadDocumentTool:
    """Tests for ReadDocumentTool."""

    @pytest.mark.asyncio
    async def test_read_doc_success(self, mock_ctx):
        """Test successful document read."""
        tool = ReadDocumentTool(credentials_json='{"token": "mock"}')
        mock_response = {
            "title": "Test Document",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Test content"}}
                            ],
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        }
                    }
                ]
            },
        }

        with patch.object(tool.client, "read_document", AsyncMock(return_value=mock_response)):
            input_data = {"document_id": "doc123"}
            result = await tool.execute(mock_ctx, input_data)

            assert result["status"] == "success"
            assert result["title"] == "Test Document"
            assert "Test content" in result["content"]
