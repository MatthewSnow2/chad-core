"""Slack adapter Pydantic schemas.

Input and output schemas for all Slack tools.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================================
# SEND MESSAGE TOOL SCHEMAS
# ============================================================================


class SendMessageInput(BaseModel):
    """Input schema for SendMessageTool."""

    channel: str = Field(..., description="Channel ID or name")
    text: str = Field(..., description="Message text")
    thread_ts: str | None = Field(None, description="Thread timestamp for replies")
    blocks: list[dict[str, Any]] = Field(default_factory=list, description="Rich message blocks")
    dry_run: bool = False


class SendMessageOutput(BaseModel):
    """Output schema for SendMessageTool."""

    ts: str = Field(..., description="Message timestamp")
    channel: str
    permalink: str
    status: Literal["sent", "dry_run"]


# ============================================================================
# GET CHANNEL INFO TOOL SCHEMAS
# ============================================================================


class GetChannelInfoInput(BaseModel):
    """Input schema for GetChannelInfoTool."""

    channel_id: str = Field(..., description="Channel ID")
    dry_run: bool = False


class GetChannelInfoOutput(BaseModel):
    """Output schema for GetChannelInfoTool."""

    id: str
    name: str
    topic: str | None = None
    purpose: str | None = None
    member_count: int
    is_private: bool
    status: Literal["success", "dry_run"] = "success"


# ============================================================================
# LIST CHANNELS TOOL SCHEMAS
# ============================================================================


class ListChannelsInput(BaseModel):
    """Input schema for ListChannelsTool."""

    exclude_archived: bool = Field(True, description="Exclude archived channels")
    types: list[str] = Field(default_factory=lambda: ["public_channel"], description="Channel types")
    limit: int = Field(100, ge=1, le=1000, description="Maximum results to return")
    dry_run: bool = False


class ChannelResult(BaseModel):
    """Single channel result."""

    id: str
    name: str
    topic: str | None = None
    num_members: int
    is_private: bool


class ListChannelsOutput(BaseModel):
    """Output schema for ListChannelsTool."""

    results: list[ChannelResult]
    total_count: int
    status: Literal["success", "dry_run"] = "success"


# ============================================================================
# ADD REACTION TOOL SCHEMAS
# ============================================================================


class AddReactionInput(BaseModel):
    """Input schema for AddReactionTool."""

    channel: str = Field(..., description="Channel ID")
    timestamp: str = Field(..., description="Message timestamp")
    emoji: str = Field(..., description="Emoji name (without colons)")
    dry_run: bool = False


class AddReactionOutput(BaseModel):
    """Output schema for AddReactionTool."""

    success: bool
    channel: str
    timestamp: str
    emoji: str
    status: Literal["added", "dry_run"]


# ============================================================================
# UPLOAD FILE TOOL SCHEMAS
# ============================================================================


class UploadFileInput(BaseModel):
    """Input schema for UploadFileTool."""

    channels: list[str] = Field(..., description="Channel IDs to share file in")
    file_content: str = Field(..., description="File content (base64 encoded for binary)")
    filename: str = Field(..., description="Filename")
    title: str | None = Field(None, description="File title")
    dry_run: bool = False


class UploadFileOutput(BaseModel):
    """Output schema for UploadFileTool."""

    file_id: str
    permalink: str
    filename: str
    status: Literal["uploaded", "dry_run"]
