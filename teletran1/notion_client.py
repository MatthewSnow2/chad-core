"""Notion API integration for pulling project health data."""

from datetime import datetime

from notion_client import Client
from notion_client.errors import APIResponseError

from teletran1.config import get_settings
from teletran1.models import Project, ProjectHealthData


class NotionProjectClient:
    """Client for fetching project data from Notion."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = Client(auth=settings.notion_api_key)
        self.database_id = settings.notion_database_id

    def fetch_projects(self) -> ProjectHealthData:
        """Fetch all projects from the Notion database."""
        projects: list[Project] = []
        has_more = True
        start_cursor = None

        while has_more:
            response = self.client.databases.query(
                database_id=self.database_id,
                start_cursor=start_cursor,
            )

            for page in response["results"]:
                project = self._parse_page(page)
                if project:
                    projects.append(project)

            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

        return ProjectHealthData(projects=projects)

    def _parse_page(self, page: dict) -> Project | None:
        """Parse a Notion page into a Project model."""
        try:
            props = page["properties"]

            # Get project name (title property)
            name = self._get_title(props.get("Name", {}))
            if not name:
                return None

            # Get completion percentage (number property)
            completion = self._get_number(props.get("Completion", {})) or 0

            # Get priority (select property)
            priority = self._get_select(props.get("Priority", {})) or "medium"

            # Get last activity date (date property)
            last_activity = self._get_date(props.get("Last Activity", {}))

            # Get client project flag (checkbox property)
            is_client = self._get_checkbox(props.get("Client Project", {}))

            # Get deadline info
            deadline = self._get_date(props.get("Deadline", {}))
            has_deadline = deadline is not None

            # Get next action (rich text property)
            next_action = self._get_rich_text(props.get("Next Action", {}))

            # Get notes (rich text property)
            notes = self._get_rich_text(props.get("Notes", {}))

            return Project(
                name=name,
                completion_percent=int(completion),
                priority=priority.lower(),
                last_activity=last_activity,
                is_client_project=is_client,
                has_deadline=has_deadline,
                deadline=deadline,
                next_action=next_action,
                notes=notes,
            )
        except (KeyError, ValueError, TypeError) as e:
            # Log and skip malformed entries
            print(f"Warning: Could not parse page: {e}")
            return None

    def _get_title(self, prop: dict) -> str | None:
        """Extract title from a title property."""
        title_list = prop.get("title", [])
        if title_list:
            return title_list[0].get("plain_text", "")
        return None

    def _get_number(self, prop: dict) -> float | None:
        """Extract number from a number property."""
        return prop.get("number")

    def _get_select(self, prop: dict) -> str | None:
        """Extract value from a select property."""
        select = prop.get("select")
        if select:
            return select.get("name")
        return None

    def _get_checkbox(self, prop: dict) -> bool:
        """Extract value from a checkbox property."""
        return prop.get("checkbox", False)

    def _get_date(self, prop: dict) -> datetime | None:
        """Extract date from a date property."""
        date_obj = prop.get("date")
        if date_obj and date_obj.get("start"):
            date_str = date_obj["start"]
            # Handle both date and datetime formats
            try:
                if "T" in date_str:
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return None
        return None

    def _get_rich_text(self, prop: dict) -> str | None:
        """Extract plain text from a rich text property."""
        rich_text = prop.get("rich_text", [])
        if rich_text:
            return "".join(block.get("plain_text", "") for block in rich_text)
        return None


def fetch_project_health() -> ProjectHealthData:
    """Convenience function to fetch project health data."""
    client = NotionProjectClient()
    return client.fetch_projects()
