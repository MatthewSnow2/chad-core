"""Google Search Drive Tool."""

from typing import Any
from chad_tools.base import ToolMetadata
from chad_tools.adapters.google.client import GoogleClientWrapper
from chad_tools.adapters.google.schemas import SearchDriveInput, SearchDriveOutput, DriveFileResult
from chad_tools.adapters.google.exceptions import GoogleAPIError


class SearchDriveTool:
    """Tool for searching Google Drive files."""

    name = "google.search_drive"
    description = "Search for files in Google Drive"
    metadata = ToolMetadata(requires_approval=False, dry_run_supported=True, idempotent=True, capabilities=["google.drive.read"], risk_level="low")

    def __init__(self, credentials_json: str | None = None, credentials_path: str | None = None, **kwargs):
        self.client = GoogleClientWrapper(credentials_json=credentials_json, credentials_path=credentials_path, **kwargs)

    async def execute(self, ctx: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        input_obj = SearchDriveInput(**input_data)
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            result = await self.client.search_drive(query=input_obj.query, mime_type=input_obj.mime_type, page_size=input_obj.limit)
            results = []
            for file in result.get("files", []):
                results.append(DriveFileResult(
                    id=file["id"],
                    name=file["name"],
                    mime_type=file["mimeType"],
                    size=file.get("size"),
                    modified_time=file["modifiedTime"],
                    web_url=file["webViewLink"],
                    owner=file.get("owners", [{}])[0].get("emailAddress") if file.get("owners") else None,
                ))

            output = SearchDriveOutput(results=results, total_count=len(results), status="success")
            return output.model_dump()
        except GoogleAPIError:
            raise
        except Exception as e:
            raise GoogleAPIError(f"Unexpected error searching Drive: {str(e)}")

    def _dry_run_response(self, input_obj: SearchDriveInput) -> dict[str, Any]:
        mock = DriveFileResult(id="mock-id", name=f"Mock file: {input_obj.query}", mime_type="application/pdf", size=1024, modified_time="2025-11-03T00:00:00Z", web_url="https://drive.google.com/file/mock", owner="mock@example.com")
        output = SearchDriveOutput(results=[mock], total_count=1, status="dry_run")
        return {**output.model_dump(), "warning": "Dry-run response", "would_execute": f"drive.search('{input_obj.query}')"}
