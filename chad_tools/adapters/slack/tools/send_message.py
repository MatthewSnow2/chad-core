"""Slack Send Message Tool."""

from typing import Any
from chad_tools.base import ToolMetadata
from chad_tools.adapters.slack.client import SlackClientWrapper
from chad_tools.adapters.slack.schemas import SendMessageInput, SendMessageOutput
from chad_tools.adapters.slack.exceptions import SlackAPIError


class SendMessageTool:
    """Tool for sending Slack messages."""

    name = "slack.send_message"
    description = "Send a message to a Slack channel"
    metadata = ToolMetadata(requires_approval=True, dry_run_supported=True, idempotent=False, capabilities=["slack.chat.write"], risk_level="medium")

    def __init__(self, bot_token: str, **kwargs):
        self.client = SlackClientWrapper(bot_token=bot_token, **kwargs)

    async def execute(self, ctx: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        input_obj = SendMessageInput(**input_data)
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            result = await self.client.post_message(
                channel=input_obj.channel,
                text=input_obj.text,
                thread_ts=input_obj.thread_ts,
                blocks=input_obj.blocks if input_obj.blocks else None,
            )

            # Get permalink
            permalink = f"https://slack.com/archives/{result['channel']}/p{result['ts'].replace('.', '')}"

            output = SendMessageOutput(
                ts=result["ts"],
                channel=result["channel"],
                permalink=permalink,
                status="sent",
            )
            return output.model_dump()
        except SlackAPIError:
            raise
        except Exception as e:
            raise SlackAPIError(f"Unexpected error sending message: {str(e)}")

    def _dry_run_response(self, input_obj: SendMessageInput) -> dict[str, Any]:
        output = SendMessageOutput(
            ts="1234567890.123456",
            channel=input_obj.channel,
            permalink=f"https://slack.com/archives/{input_obj.channel}/p1234567890123456",
            status="dry_run",
        )
        return {**output.model_dump(), "warning": "Dry-run response", "would_execute": f"slack.chat.postMessage(channel='{input_obj.channel}')"}
