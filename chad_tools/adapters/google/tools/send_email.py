"""Google Send Email Tool.

Send email via Gmail API.
"""

from typing import Any

from chad_tools.base import ToolMetadata
from chad_tools.adapters.google.client import GoogleClientWrapper
from chad_tools.adapters.google.schemas import (
    SendEmailInput,
    SendEmailOutput,
)
from chad_tools.adapters.google.exceptions import GoogleAPIError


class SendEmailTool:
    """Tool for sending emails via Gmail.

    Capabilities:
    - Send emails with CC/BCC
    - HTML and plain text support
    - Return message and thread IDs

    Use Cases:
    - "Send email to user@example.com"
    - "Email team with project update"
    - "Send notification email"
    """

    name = "google.send_email"
    description = "Send email via Gmail API"

    metadata = ToolMetadata(
        requires_approval=True,  # Sending emails requires approval
        dry_run_supported=True,
        idempotent=False,
        capabilities=["google.gmail.send"],
        risk_level="high",
    )

    def __init__(self, credentials_json: str | None = None, credentials_path: str | None = None, **kwargs):
        """Initialize SendEmailTool.

        Args:
            credentials_json: Service account JSON credentials
            credentials_path: Path to credentials file
            **kwargs: Additional client configuration
        """
        self.client = GoogleClientWrapper(
            credentials_json=credentials_json,
            credentials_path=credentials_path,
            **kwargs
        )

    async def execute(
        self, ctx: dict[str, Any], input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute send email.

        Args:
            ctx: Execution context
            input_data: Tool input matching SendEmailInput schema

        Returns:
            Email result matching SendEmailOutput schema
        """
        input_obj = SendEmailInput(**input_data)

        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            result = await self.client.send_email(
                to=input_obj.to,
                subject=input_obj.subject,
                body=input_obj.body,
                cc=input_obj.cc if input_obj.cc else None,
                bcc=input_obj.bcc if input_obj.bcc else None,
            )

            output = SendEmailOutput(
                message_id=result["id"],
                thread_id=result["threadId"],
                to=input_obj.to,
                subject=input_obj.subject,
                status="sent",
            )

            return output.model_dump()

        except GoogleAPIError:
            raise
        except Exception as e:
            raise GoogleAPIError(f"Unexpected error sending email: {str(e)}")

    def _dry_run_response(self, input_obj: SendEmailInput) -> dict[str, Any]:
        """Generate dry-run mock response."""
        output = SendEmailOutput(
            message_id="mock-message-id-12345",
            thread_id="mock-thread-id-12345",
            to=input_obj.to,
            subject=input_obj.subject,
            status="dry_run",
        )

        return {
            **output.model_dump(),
            "warning": "This is a dry-run response; no real email was sent",
            "would_execute": f"gmail.send(to='{input_obj.to}', subject='{input_obj.subject}')",
        }
