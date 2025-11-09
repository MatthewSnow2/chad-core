"""Google Workspace adapter for Chad-Core.

Provides tools for interacting with Google Workspace:
- Send emails via Gmail
- Search Google Drive
- Get calendar events
- Create calendar events
- Read Google Docs

Usage:
    from chad_tools.adapters.google import register_google_tools
    from chad_tools.registry import ToolRegistry

    registry = ToolRegistry()
    register_google_tools(registry, credentials_json="...")
"""

from .client import GoogleClientWrapper
from .exceptions import (
    GoogleAPIError,
    GoogleAuthError,
    GoogleQuotaExceededError,
    GoogleNotFoundError,
    GoogleValidationError,
)
from .schemas import (
    SendEmailInput,
    SendEmailOutput,
    SearchDriveInput,
    SearchDriveOutput,
    DriveFileResult,
    GetCalendarEventsInput,
    GetCalendarEventsOutput,
    CalendarEventResult,
    CalendarAttendee,
    CreateCalendarEventInput,
    CreateCalendarEventOutput,
    ReadDocumentInput,
    ReadDocumentOutput,
)
from .tools import (
    SendEmailTool,
    SearchDriveTool,
    GetCalendarEventsTool,
    CreateCalendarEventTool,
    ReadDocumentTool,
)

__all__ = [
    # Client
    "GoogleClientWrapper",
    # Exceptions
    "GoogleAPIError",
    "GoogleAuthError",
    "GoogleQuotaExceededError",
    "GoogleNotFoundError",
    "GoogleValidationError",
    # Schemas
    "SendEmailInput",
    "SendEmailOutput",
    "SearchDriveInput",
    "SearchDriveOutput",
    "DriveFileResult",
    "GetCalendarEventsInput",
    "GetCalendarEventsOutput",
    "CalendarEventResult",
    "CalendarAttendee",
    "CreateCalendarEventInput",
    "CreateCalendarEventOutput",
    "ReadDocumentInput",
    "ReadDocumentOutput",
    # Tools
    "SendEmailTool",
    "SearchDriveTool",
    "GetCalendarEventsTool",
    "CreateCalendarEventTool",
    "ReadDocumentTool",
]


def register_google_tools(registry, credentials_json: str | None = None, credentials_path: str | None = None) -> None:
    """Register all Google Workspace tools with the tool registry.

    Args:
        registry: ToolRegistry instance
        credentials_json: Service account JSON credentials as string
        credentials_path: Path to service account JSON file

    Example:
        from chad_tools.registry import ToolRegistry
        from chad_tools.adapters.google import register_google_tools

        registry = ToolRegistry()
        register_google_tools(registry, credentials_json="...")
    """
    registry.register(SendEmailTool(credentials_json=credentials_json, credentials_path=credentials_path))
    registry.register(SearchDriveTool(credentials_json=credentials_json, credentials_path=credentials_path))
    registry.register(GetCalendarEventsTool(credentials_json=credentials_json, credentials_path=credentials_path))
    registry.register(CreateCalendarEventTool(credentials_json=credentials_json, credentials_path=credentials_path))
    registry.register(ReadDocumentTool(credentials_json=credentials_json, credentials_path=credentials_path))
