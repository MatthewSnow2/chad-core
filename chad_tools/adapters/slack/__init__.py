"""Slack adapter for Chad-Core.

Provides tools for interacting with Slack:
- Send messages
- Get channel information
- List channels
- Add reactions
- Upload files

Usage:
    from chad_tools.adapters.slack import register_slack_tools
    from chad_tools.registry import ToolRegistry

    registry = ToolRegistry()
    register_slack_tools(registry, bot_token="xoxb-...")
"""

from .client import SlackClientWrapper
from .exceptions import (
    SlackAPIError,
    SlackAuthError,
    SlackChannelNotFoundError,
    SlackRateLimitError,
    SlackValidationError,
)
from .schemas import (
    SendMessageInput,
    SendMessageOutput,
    GetChannelInfoInput,
    GetChannelInfoOutput,
    ListChannelsInput,
    ListChannelsOutput,
    ChannelResult,
    AddReactionInput,
    AddReactionOutput,
    UploadFileInput,
    UploadFileOutput,
)
from .tools import (
    SendMessageTool,
    GetChannelInfoTool,
    ListChannelsTool,
    AddReactionTool,
    UploadFileTool,
)

__all__ = [
    # Client
    "SlackClientWrapper",
    # Exceptions
    "SlackAPIError",
    "SlackAuthError",
    "SlackChannelNotFoundError",
    "SlackRateLimitError",
    "SlackValidationError",
    # Schemas
    "SendMessageInput",
    "SendMessageOutput",
    "GetChannelInfoInput",
    "GetChannelInfoOutput",
    "ListChannelsInput",
    "ListChannelsOutput",
    "ChannelResult",
    "AddReactionInput",
    "AddReactionOutput",
    "UploadFileInput",
    "UploadFileOutput",
    # Tools
    "SendMessageTool",
    "GetChannelInfoTool",
    "ListChannelsTool",
    "AddReactionTool",
    "UploadFileTool",
]


def register_slack_tools(registry, bot_token: str) -> None:
    """Register all Slack tools with the tool registry.

    Args:
        registry: ToolRegistry instance
        bot_token: Slack bot token (starts with xoxb-)

    Example:
        from chad_tools.registry import ToolRegistry
        from chad_tools.adapters.slack import register_slack_tools

        registry = ToolRegistry()
        register_slack_tools(registry, bot_token="xoxb-...")
    """
    registry.register(SendMessageTool(bot_token=bot_token))
    registry.register(GetChannelInfoTool(bot_token=bot_token))
    registry.register(ListChannelsTool(bot_token=bot_token))
    registry.register(AddReactionTool(bot_token=bot_token))
    registry.register(UploadFileTool(bot_token=bot_token))
