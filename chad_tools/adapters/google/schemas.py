"""Google Workspace adapter Pydantic schemas.

Input and output schemas for all Google Workspace tools.
"""

from typing import Any, Literal
from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================================
# SEND EMAIL TOOL SCHEMAS
# ============================================================================


class SendEmailInput(BaseModel):
    """Input schema for SendEmailTool."""

    to: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body (HTML or plain text)")
    cc: list[str] = Field(default_factory=list, description="CC recipients")
    bcc: list[str] = Field(default_factory=list, description="BCC recipients")
    dry_run: bool = False


class SendEmailOutput(BaseModel):
    """Output schema for SendEmailTool."""

    message_id: str
    thread_id: str
    to: str
    subject: str
    status: Literal["sent", "dry_run"]


# ============================================================================
# SEARCH DRIVE TOOL SCHEMAS
# ============================================================================


class SearchDriveInput(BaseModel):
    """Input schema for SearchDriveTool."""

    query: str = Field(..., description="Search query string")
    mime_type: str | None = Field(None, description="Filter by MIME type")
    limit: int = Field(10, ge=1, le=100, description="Maximum results to return")
    dry_run: bool = False


class DriveFileResult(BaseModel):
    """Single Drive file result."""

    id: str
    name: str
    mime_type: str
    size: int | None = None
    modified_time: str
    web_url: str
    owner: str | None = None


class SearchDriveOutput(BaseModel):
    """Output schema for SearchDriveTool."""

    results: list[DriveFileResult]
    total_count: int
    status: Literal["success", "dry_run"] = "success"


# ============================================================================
# GET CALENDAR EVENTS TOOL SCHEMAS
# ============================================================================


class GetCalendarEventsInput(BaseModel):
    """Input schema for GetCalendarEventsTool."""

    calendar_id: str = Field("primary", description="Calendar ID")
    time_min: str = Field(..., description="Start time (ISO 8601)")
    time_max: str = Field(..., description="End time (ISO 8601)")
    max_results: int = Field(10, ge=1, le=100, description="Maximum results to return")
    dry_run: bool = False


class CalendarAttendee(BaseModel):
    """Calendar event attendee."""

    email: str
    response_status: str | None = None


class CalendarEventResult(BaseModel):
    """Single calendar event result."""

    id: str
    summary: str
    start: str
    end: str
    attendees: list[CalendarAttendee] = Field(default_factory=list)
    location: str | None = None
    description: str | None = None
    html_link: str


class GetCalendarEventsOutput(BaseModel):
    """Output schema for GetCalendarEventsTool."""

    results: list[CalendarEventResult]
    total_count: int
    status: Literal["success", "dry_run"] = "success"


# ============================================================================
# CREATE CALENDAR EVENT TOOL SCHEMAS
# ============================================================================


class CreateCalendarEventInput(BaseModel):
    """Input schema for CreateCalendarEventTool."""

    summary: str = Field(..., description="Event title")
    start_time: str = Field(..., description="Start time (ISO 8601)")
    end_time: str = Field(..., description="End time (ISO 8601)")
    attendees: list[str] = Field(default_factory=list, description="Attendee emails")
    description: str = Field("", description="Event description")
    location: str | None = Field(None, description="Event location")
    calendar_id: str = Field("primary", description="Calendar ID")
    dry_run: bool = False


class CreateCalendarEventOutput(BaseModel):
    """Output schema for CreateCalendarEventTool."""

    event_id: str
    html_link: str
    summary: str
    start: str
    end: str
    status: Literal["created", "dry_run"]


# ============================================================================
# READ DOCUMENT TOOL SCHEMAS
# ============================================================================


class ReadDocumentInput(BaseModel):
    """Input schema for ReadDocumentTool."""

    document_id: str = Field(..., description="Google Docs document ID")
    dry_run: bool = False


class ReadDocumentOutput(BaseModel):
    """Output schema for ReadDocumentTool."""

    document_id: str
    title: str
    content: str = Field(..., description="Document content in markdown format")
    last_modified: str
    word_count: int
    status: Literal["success", "dry_run"] = "success"
