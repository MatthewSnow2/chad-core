"""Slack List Channels Tool."""

from typing import Any
from chad_tools.base import ToolMetadata
from chad_tools.adapters.slack.client import SlackClientWrapper
from chad_tools.adapters.slack.schemas import ListChannelsInput, ListChannelsOutput, ChannelResult
from chad_tools.adapters.slack.exceptions import SlackAPIError


class ListChannelsTool:
    """Tool for listing Slack channels."""

    name = "slack.list_channels"
    description = "List Slack channels"
    metadata = ToolMetadata(requires_approval=False, dry_run_supported=True, idempotent=True, capabilities=["slack.channels.read"], risk_level="low")

    def __init__(self, bot_token: str, **kwargs):
        self.client = SlackClientWrapper(bot_token=bot_token, **kwargs)

    async def execute(self, ctx: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        input_obj = ListChannelsInput(**input_data)
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            result = await self.client.list_channels(
                exclude_archived=input_obj.exclude_archived,
                types=input_obj.types,
                limit=input_obj.limit,
            )

            results = []
            for channel in result.get("channels", []):
                results.append(ChannelResult(
                    id=channel["id"],
                    name=channel["name"],
                    topic=channel.get("topic", {}).get("value"),
                    num_members=channel.get("num_members", 0),
                    is_private=channel.get("is_private", False),
                ))

            output = ListChannelsOutput(results=results, total_count=len(results), status="success")
            return output.model_dump()
        except SlackAPIError:
            raise
        except Exception as e:
            raise SlackAPIError(f"Unexpected error listing channels: {str(e)}")

    def _dry_run_response(self, input_obj: ListChannelsInput) -> dict[str, Any]:
        mock = ChannelResult(id="C1234567890", name="general", topic="Company-wide announcements", num_members=100, is_private=False)
        output = ListChannelsOutput(results=[mock], total_count=1, status="dry_run")
        return {**output.model_dump(), "warning": "Dry-run response", "would_execute": "slack.conversations.list()"}
