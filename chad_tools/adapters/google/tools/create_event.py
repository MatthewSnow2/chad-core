"""Google Create Calendar Event Tool."""

from typing import Any
from chad_tools.base import ToolMetadata
from chad_tools.adapters.google.client import GoogleClientWrapper
from chad_tools.adapters.google.schemas import CreateCalendarEventInput, CreateCalendarEventOutput
from chad_tools.adapters.google.exceptions import GoogleAPIError


class CreateCalendarEventTool:
    """Tool for creating calendar events."""

    name = "google.create_calendar_event"
    description = "Create a new event in Google Calendar"
    metadata = ToolMetadata(requires_approval=True, dry_run_supported=True, idempotent=False, capabilities=["google.calendar.write"], risk_level="medium")

    def __init__(self, credentials_json: str | None = None, credentials_path: str | None = None, **kwargs):
        self.client = GoogleClientWrapper(credentials_json=credentials_json, credentials_path=credentials_path, **kwargs)

    async def execute(self, ctx: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        input_obj = CreateCalendarEventInput(**input_data)
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            result = await self.client.create_calendar_event(
                calendar_id=input_obj.calendar_id,
                summary=input_obj.summary,
                start_time=input_obj.start_time,
                end_time=input_obj.end_time,
                attendees=input_obj.attendees if input_obj.attendees else None,
                description=input_obj.description,
                location=input_obj.location,
            )

            output = CreateCalendarEventOutput(
                event_id=result["id"],
                html_link=result["htmlLink"],
                summary=result["summary"],
                start=result["start"].get("dateTime", result["start"].get("date")),
                end=result["end"].get("dateTime", result["end"].get("date")),
                status="created",
            )
            return output.model_dump()
        except GoogleAPIError:
            raise
        except Exception as e:
            raise GoogleAPIError(f"Unexpected error creating event: {str(e)}")

    def _dry_run_response(self, input_obj: CreateCalendarEventInput) -> dict[str, Any]:
        output = CreateCalendarEventOutput(event_id="mock-event-id", html_link="https://calendar.google.com/mock", summary=input_obj.summary, start=input_obj.start_time, end=input_obj.end_time, status="dry_run")
        return {**output.model_dump(), "warning": "Dry-run response", "would_execute": f"calendar.events.create(summary='{input_obj.summary}')"}
