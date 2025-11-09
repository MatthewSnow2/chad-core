"""Slack Get Channel Info Tool."""

from typing import Any
from chad_tools.base import ToolMetadata
from chad_tools.adapters.slack.client import SlackClientWrapper
from chad_tools.adapters.slack.schemas import GetChannelInfoInput, GetChannelInfoOutput
from chad_tools.adapters.slack.exceptions import SlackAPIError


class GetChannelInfoTool:
    """Tool for getting Slack channel information."""

    name = "slack.get_channel_info"
    description = "Get information about a Slack channel"
    metadata = ToolMetadata(requires_approval=False, dry_run_supported=True, idempotent=True, capabilities=["slack.channels.read"], risk_level="low")

    def __init__(self, bot_token: str, **kwargs):
        self.client = SlackClientWrapper(bot_token=bot_token, **kwargs)

    async def execute(self, ctx: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        input_obj = GetChannelInfoInput(**input_data)
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            result = await self.client.get_channel_info(channel_id=input_obj.channel_id)
            channel = result["channel"]

            output = GetChannelInfoOutput(
                id=channel["id"],
                name=channel["name"],
                topic=channel.get("topic", {}).get("value"),
                purpose=channel.get("purpose", {}).get("value"),
                member_count=channel.get("num_members", 0),
                is_private=channel.get("is_private", False),
                status="success",
            )
            return output.model_dump()
        except SlackAPIError:
            raise
        except Exception as e:
            raise SlackAPIError(f"Unexpected error getting channel info: {str(e)}")

    def _dry_run_response(self, input_obj: GetChannelInfoInput) -> dict[str, Any]:
        output = GetChannelInfoOutput(id=input_obj.channel_id, name="mock-channel", topic="Mock topic", purpose="Mock purpose", member_count=42, is_private=False, status="dry_run")
        return {**output.model_dump(), "warning": "Dry-run response", "would_execute": f"slack.conversations.info(channel='{input_obj.channel_id}')"}
