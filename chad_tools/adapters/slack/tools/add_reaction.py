"""Slack Add Reaction Tool."""

from typing import Any
from chad_tools.base import ToolMetadata
from chad_tools.adapters.slack.client import SlackClientWrapper
from chad_tools.adapters.slack.schemas import AddReactionInput, AddReactionOutput
from chad_tools.adapters.slack.exceptions import SlackAPIError


class AddReactionTool:
    """Tool for adding reactions to Slack messages."""

    name = "slack.add_reaction"
    description = "Add an emoji reaction to a Slack message"
    metadata = ToolMetadata(requires_approval=True, dry_run_supported=True, idempotent=True, capabilities=["slack.reactions.write"], risk_level="low")

    def __init__(self, bot_token: str, **kwargs):
        self.client = SlackClientWrapper(bot_token=bot_token, **kwargs)

    async def execute(self, ctx: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        input_obj = AddReactionInput(**input_data)
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            result = await self.client.add_reaction(
                channel=input_obj.channel,
                timestamp=input_obj.timestamp,
                emoji=input_obj.emoji,
            )

            output = AddReactionOutput(
                success=result.get("ok", False),
                channel=input_obj.channel,
                timestamp=input_obj.timestamp,
                emoji=input_obj.emoji,
                status="added",
            )
            return output.model_dump()
        except SlackAPIError:
            raise
        except Exception as e:
            raise SlackAPIError(f"Unexpected error adding reaction: {str(e)}")

    def _dry_run_response(self, input_obj: AddReactionInput) -> dict[str, Any]:
        output = AddReactionOutput(success=True, channel=input_obj.channel, timestamp=input_obj.timestamp, emoji=input_obj.emoji, status="dry_run")
        return {**output.model_dump(), "warning": "Dry-run response", "would_execute": f"slack.reactions.add(emoji=':{input_obj.emoji}:')"}
