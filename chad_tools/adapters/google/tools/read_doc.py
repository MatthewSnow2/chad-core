"""Google Read Document Tool."""

from typing import Any
from chad_tools.base import ToolMetadata
from chad_tools.adapters.google.client import GoogleClientWrapper
from chad_tools.adapters.google.schemas import ReadDocumentInput, ReadDocumentOutput
from chad_tools.adapters.google.exceptions import GoogleAPIError


class ReadDocumentTool:
    """Tool for reading Google Docs documents."""

    name = "google.read_document"
    description = "Read content from a Google Docs document"
    metadata = ToolMetadata(requires_approval=False, dry_run_supported=True, idempotent=True, capabilities=["google.docs.read"], risk_level="low")

    def __init__(self, credentials_json: str | None = None, credentials_path: str | None = None, **kwargs):
        self.client = GoogleClientWrapper(credentials_json=credentials_json, credentials_path=credentials_path, **kwargs)

    def _extract_text(self, doc_data: dict[str, Any]) -> str:
        """Extract text from Google Docs API response and convert to markdown."""
        content_parts = []
        body = doc_data.get("body", {})

        for element in body.get("content", []):
            if "paragraph" in element:
                paragraph = element["paragraph"]
                paragraph_text = []
                for elem in paragraph.get("elements", []):
                    if "textRun" in elem:
                        paragraph_text.append(elem["textRun"].get("content", ""))

                text = "".join(paragraph_text).strip()
                if text:
                    # Check if it's a heading
                    style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "")
                    if "HEADING_1" in style:
                        content_parts.append(f"# {text}")
                    elif "HEADING_2" in style:
                        content_parts.append(f"## {text}")
                    elif "HEADING_3" in style:
                        content_parts.append(f"### {text}")
                    else:
                        content_parts.append(text)

        return "\n\n".join(content_parts)

    async def execute(self, ctx: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        input_obj = ReadDocumentInput(**input_data)
        if input_obj.dry_run:
            return self._dry_run_response(input_obj)

        try:
            result = await self.client.read_document(document_id=input_obj.document_id)

            title = result.get("title", "Untitled")
            content = self._extract_text(result)
            word_count = len(content.split())

            # Get last modified time from revisionId (simplified)
            last_modified = "2025-11-03T00:00:00Z"  # In real impl, fetch from Drive API

            output = ReadDocumentOutput(
                document_id=input_obj.document_id,
                title=title,
                content=content,
                last_modified=last_modified,
                word_count=word_count,
                status="success",
            )
            return output.model_dump()
        except GoogleAPIError:
            raise
        except Exception as e:
            raise GoogleAPIError(f"Unexpected error reading document: {str(e)}")

    def _dry_run_response(self, input_obj: ReadDocumentInput) -> dict[str, Any]:
        output = ReadDocumentOutput(
            document_id=input_obj.document_id,
            title="Mock Document",
            content="# Mock Document\n\nThis is mock content for dry-run testing.",
            last_modified="2025-11-03T00:00:00Z",
            word_count=8,
            status="dry_run",
        )
        return {**output.model_dump(), "warning": "Dry-run response", "would_execute": f"docs.get('{input_obj.document_id}')"}
