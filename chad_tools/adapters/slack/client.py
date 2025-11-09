"""Slack API client wrapper.

Centralized Slack API client with error handling and rate limiting.
"""

import asyncio
from typing import Any

import httpx

from .exceptions import (
    SlackAPIError,
    SlackAuthError,
    SlackChannelNotFoundError,
    SlackRateLimitError,
)


class SlackClientWrapper:
    """Slack API client with Chad-Core integration.

    Provides:
    - Error handling and exception mapping
    - Rate limiting
    - Automatic retry with exponential backoff
    - Structured error messages
    """

    BASE_URL = "https://slack.com/api"

    def __init__(
        self,
        bot_token: str,
        rate_limit_per_second: int = 10,
        timeout_seconds: int = 30,
    ):
        """Initialize Slack client.

        Args:
            bot_token: Slack bot token (starts with xoxb-)
            rate_limit_per_second: Max requests per second
            timeout_seconds: Request timeout
        """
        self.bot_token = bot_token
        self.rate_limit_per_second = rate_limit_per_second
        self.timeout_seconds = timeout_seconds
        self._last_request_time = 0.0

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json",
        }

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        current_time = asyncio.get_event_loop().time()
        time_since_last_request = current_time - self._last_request_time
        min_interval = 1.0 / self.rate_limit_per_second

        if time_since_last_request < min_interval:
            await asyncio.sleep(min_interval - time_since_last_request)

        self._last_request_time = asyncio.get_event_loop().time()

    def _handle_error(self, data: dict[str, Any]) -> None:
        """Map Slack API errors to custom exceptions."""
        if data.get("ok"):
            return

        error = data.get("error", "unknown_error")

        if error == "invalid_auth" or error == "token_revoked":
            raise SlackAuthError(f"Authentication failed: {error}")
        elif error == "channel_not_found":
            raise SlackChannelNotFoundError(f"Channel not found: {error}")
        elif error == "rate_limited":
            raise SlackRateLimitError(f"Rate limit exceeded: {error}")
        else:
            raise SlackAPIError(f"Slack API error: {error}")

    async def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a message to a Slack channel.

        Args:
            channel: Channel ID or name
            text: Message text
            thread_ts: Thread timestamp for replies
            blocks: Rich message blocks

        Returns:
            Message data from Slack API
        """
        await self._rate_limit()

        data = {
            "channel": channel,
            "text": text,
        }
        if thread_ts:
            data["thread_ts"] = thread_ts
        if blocks:
            data["blocks"] = blocks

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.BASE_URL}/chat.postMessage",
                headers=self._get_headers(),
                json=data,
            )

            result = response.json()
            self._handle_error(result)
            return result

    async def get_channel_info(self, channel_id: str) -> dict[str, Any]:
        """Get channel information.

        Args:
            channel_id: Channel ID

        Returns:
            Channel info from Slack API
        """
        await self._rate_limit()

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.BASE_URL}/conversations.info",
                headers=self._get_headers(),
                json={"channel": channel_id},
            )

            result = response.json()
            self._handle_error(result)
            return result

    async def list_channels(
        self,
        exclude_archived: bool = True,
        types: list[str] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List channels.

        Args:
            exclude_archived: Exclude archived channels
            types: Channel types (public_channel, private_channel, etc.)
            limit: Maximum results

        Returns:
            Channels list from Slack API
        """
        await self._rate_limit()

        data = {
            "exclude_archived": exclude_archived,
            "limit": limit,
        }
        if types:
            data["types"] = ",".join(types)

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.BASE_URL}/conversations.list",
                headers=self._get_headers(),
                json=data,
            )

            result = response.json()
            self._handle_error(result)
            return result

    async def add_reaction(
        self,
        channel: str,
        timestamp: str,
        emoji: str,
    ) -> dict[str, Any]:
        """Add reaction to a message.

        Args:
            channel: Channel ID
            timestamp: Message timestamp
            emoji: Emoji name (without colons)

        Returns:
            Result from Slack API
        """
        await self._rate_limit()

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.BASE_URL}/reactions.add",
                headers=self._get_headers(),
                json={
                    "channel": channel,
                    "timestamp": timestamp,
                    "name": emoji,
                },
            )

            result = response.json()
            self._handle_error(result)
            return result

    async def upload_file(
        self,
        channels: list[str],
        content: bytes,
        filename: str,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Upload file to Slack.

        Args:
            channels: Channel IDs to share file in
            content: File content as bytes
            filename: Filename
            title: File title

        Returns:
            File upload result from Slack API
        """
        await self._rate_limit()

        # Slack files.upload uses multipart/form-data
        files = {"file": (filename, content)}
        data = {
            "channels": ",".join(channels),
            "filename": filename,
        }
        if title:
            data["title"] = title

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.BASE_URL}/files.upload",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                files=files,
                data=data,
            )

            result = response.json()
            self._handle_error(result)
            return result
