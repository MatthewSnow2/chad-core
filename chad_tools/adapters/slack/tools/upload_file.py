"""Slack Upload File Tool."""

import base64
from typing import Any
from chad_tools.base import ToolMetadata
from chad_tools.adapters.slack.client import SlackClientWrapper
from chad_tools.adapters.slack.schemas import UploadFileInput, UploadFileOutput
from chad_tools.adapters.slack.exceptions import SlackAPIError


class UploadFileTool:
    """Tool for uploading files to Slack."""

    name = "slack.upload_file"
    description = "Upload a file to Slack channels"
    metadata = ToolMetadata(requires_approval=True, dry_run_supported=True, idempotent=False, capabilities=["slack.files.write"], risk_level="medium")

    def __init__(self, bot_token: str, **kwargs):
        self.client = SlackClientWrapper(bot_token=bot_token, **kwargs)

    async def execute(self, ctx: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        input_obj = UploadFileInput(**input_data)
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            # Decode base64 content if needed
            try:
                file_bytes = base64.b64decode(input_obj.file_content)
            except Exception:
                # If not base64, treat as text
                file_bytes = input_obj.file_content.encode()

            result = await self.client.upload_file(
                channels=input_obj.channels,
                content=file_bytes,
                filename=input_obj.filename,
                title=input_obj.title,
            )

            file_data = result["file"]

            output = UploadFileOutput(
                file_id=file_data["id"],
                permalink=file_data["permalink"],
                filename=file_data["name"],
                status="uploaded",
            )
            return output.model_dump()
        except SlackAPIError:
            raise
        except Exception as e:
            raise SlackAPIError(f"Unexpected error uploading file: {str(e)}")

    def _dry_run_response(self, input_obj: UploadFileInput) -> dict[str, Any]:
        output = UploadFileOutput(
            file_id="F1234567890",
            permalink="https://slack.com/files/mock/file",
            filename=input_obj.filename,
            status="dry_run",
        )
        return {**output.model_dump(), "warning": "Dry-run response", "would_execute": f"slack.files.upload(filename='{input_obj.filename}')"}
