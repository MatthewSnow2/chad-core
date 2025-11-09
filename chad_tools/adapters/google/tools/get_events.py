"""Google Get Calendar Events Tool."""

from typing import Any
from chad_tools.base import ToolMetadata
from chad_tools.adapters.google.client import GoogleClientWrapper
from chad_tools.adapters.google.schemas import GetCalendarEventsInput, GetCalendarEventsOutput, CalendarEventResult, CalendarAttendee
from chad_tools.adapters.google.exceptions import GoogleAPIError


class GetCalendarEventsTool:
    """Tool for getting calendar events."""

    name = "google.get_calendar_events"
    description = "Get events from Google Calendar"
    metadata = ToolMetadata(requires_approval=False, dry_run_supported=True, idempotent=True, capabilities=["google.calendar.read"], risk_level="low")

    def __init__(self, credentials_json: str | None = None, credentials_path: str | None = None, **kwargs):
        self.client = GoogleClientWrapper(credentials_json=credentials_json, credentials_path=credentials_path, **kwargs)

    async def execute(self, ctx: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        input_obj = GetCalendarEventsInput(**input_data)
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            result = await self.client.get_calendar_events(calendar_id=input_obj.calendar_id, time_min=input_obj.time_min, time_max=input_obj.time_max, max_results=input_obj.max_results)
            results = []
            for event in result.get("items", []):
                attendees = [CalendarAttendee(email=a["email"], response_status=a.get("responseStatus")) for a in event.get("attendees", [])]
                results.append(CalendarEventResult(
                    id=event["id"],
                    summary=event.get("summary", "No title"),
                    start=event["start"].get("dateTime", event["start"].get("date")),
                    end=event["end"].get("dateTime", event["end"].get("date")),
                    attendees=attendees,
                    location=event.get("location"),
                    description=event.get("description"),
                    html_link=event["htmlLink"],
                ))

            output = GetCalendarEventsOutput(results=results, total_count=len(results), status="success")
            return output.model_dump()
        except GoogleAPIError:
            raise
        except Exception as e:
            raise GoogleAPIError(f"Unexpected error getting events: {str(e)}")

    def _dry_run_response(self, input_obj: GetCalendarEventsInput) -> dict[str, Any]:
        mock = CalendarEventResult(id="mock-event", summary="Mock Event", start=input_obj.time_min, end=input_obj.time_max, attendees=[], location="Virtual", description="Mock event", html_link="https://calendar.google.com/mock")
        output = GetCalendarEventsOutput(results=[mock], total_count=1, status="dry_run")
        return {**output.model_dump(), "warning": "Dry-run response", "would_execute": f"calendar.events.list()"}
