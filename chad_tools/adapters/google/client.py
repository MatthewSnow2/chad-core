"""Google Workspace API client wrapper.

Centralized Google API client with error handling and authentication.
Note: This is a simplified implementation. In production, you would use
google-auth and google-api-python-client libraries.
"""

import asyncio
import base64
import json
from typing import Any

import httpx

from .exceptions import (
    GoogleAPIError,
    GoogleAuthError,
    GoogleQuotaExceededError,
    GoogleNotFoundError,
)


class GoogleClientWrapper:
    """Google Workspace API client with Chad-Core integration.

    Provides:
    - Error handling and exception mapping
    - OAuth 2.0 authentication
    - API access to Gmail, Drive, Calendar, Docs

    Note: This implementation uses httpx for direct API calls.
    In production, consider using official Google client libraries.
    """

    GMAIL_BASE_URL = "https://gmail.googleapis.com/gmail/v1"
    DRIVE_BASE_URL = "https://www.googleapis.com/drive/v3"
    CALENDAR_BASE_URL = "https://www.googleapis.com/calendar/v3"
    DOCS_BASE_URL = "https://docs.googleapis.com/v1"

    def __init__(
        self,
        credentials_json: str | None = None,
        credentials_path: str | None = None,
        timeout_seconds: int = 30,
    ):
        """Initialize Google client.

        Args:
            credentials_json: Service account JSON credentials as string
            credentials_path: Path to service account JSON file
            timeout_seconds: Request timeout
        """
        self.credentials_json = credentials_json
        self.credentials_path = credentials_path
        self.timeout_seconds = timeout_seconds
        self._access_token: str | None = None
        self._last_request_time = 0.0

    async def _get_access_token(self) -> str:
        """Get OAuth 2.0 access token.

        In production, this would:
        1. Load service account credentials
        2. Create JWT
        3. Exchange for access token
        4. Cache token until expiry

        For now, we'll use a placeholder or expect credentials to include token.
        """
        if self._access_token:
            return self._access_token

        # Simplified: In real implementation, use google.auth
        if self.credentials_json:
            creds = json.loads(self.credentials_json)
            # This is a placeholder - real implementation would create JWT and exchange
            self._access_token = creds.get("token", "")
        elif self.credentials_path:
            with open(self.credentials_path) as f:
                creds = json.load(f)
                self._access_token = creds.get("token", "")

        if not self._access_token:
            raise GoogleAuthError("No access token available. Set credentials properly.")

        return self._access_token

    def _get_headers(self, access_token: str) -> dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        current_time = asyncio.get_event_loop().time()
        time_since_last_request = current_time - self._last_request_time
        min_interval = 0.1  # 10 requests per second

        if time_since_last_request < min_interval:
            await asyncio.sleep(min_interval - time_since_last_request)

        self._last_request_time = asyncio.get_event_loop().time()

    def _handle_error(self, response: httpx.Response) -> None:
        """Map Google API errors to custom exceptions."""
        status = response.status_code

        try:
            error_data = response.json()
            message = error_data.get("error", {}).get("message", str(response.text))
        except Exception:
            message = str(response.text)

        if status == 401:
            raise GoogleAuthError(f"Authentication failed: {message}")
        elif status == 403:
            if "quota" in message.lower():
                raise GoogleQuotaExceededError(f"Quota exceeded: {message}")
            raise GoogleAuthError(f"Forbidden: {message}")
        elif status == 404:
            raise GoogleNotFoundError(f"Resource not found: {message}")
        else:
            raise GoogleAPIError(f"Google API error ({status}): {message}")

    # ========================================================================
    # GMAIL API
    # ========================================================================

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send email via Gmail API.

        Args:
            to: Recipient email
            subject: Email subject
            body: Email body
            cc: CC recipients
            bcc: BCC recipients

        Returns:
            Sent message data
        """
        await self._rate_limit()
        access_token = await self._get_access_token()

        # Create RFC 2822 email message
        message_parts = [
            f"To: {to}",
            f"Subject: {subject}",
        ]
        if cc:
            message_parts.append(f"Cc: {', '.join(cc)}")
        if bcc:
            message_parts.append(f"Bcc: {', '.join(bcc)}")
        message_parts.append("")
        message_parts.append(body)

        raw_message = "\r\n".join(message_parts)
        encoded_message = base64.urlsafe_b64encode(raw_message.encode()).decode()

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.GMAIL_BASE_URL}/users/me/messages/send",
                headers=self._get_headers(access_token),
                json={"raw": encoded_message},
            )

            if response.status_code != 200:
                self._handle_error(response)

            return response.json()

    # ========================================================================
    # DRIVE API
    # ========================================================================

    async def search_drive(
        self,
        query: str,
        mime_type: str | None = None,
        page_size: int = 10,
    ) -> dict[str, Any]:
        """Search Google Drive files.

        Args:
            query: Search query
            mime_type: Filter by MIME type
            page_size: Number of results

        Returns:
            Search results
        """
        await self._rate_limit()
        access_token = await self._get_access_token()

        # Build query string
        q_parts = [f"name contains '{query}'"]
        if mime_type:
            q_parts.append(f"mimeType = '{mime_type}'")
        q = " and ".join(q_parts)

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.DRIVE_BASE_URL}/files",
                headers=self._get_headers(access_token),
                params={
                    "q": q,
                    "pageSize": page_size,
                    "fields": "files(id,name,mimeType,size,modifiedTime,webViewLink,owners)",
                },
            )

            if response.status_code != 200:
                self._handle_error(response)

            return response.json()

    # ========================================================================
    # CALENDAR API
    # ========================================================================

    async def get_calendar_events(
        self,
        calendar_id: str,
        time_min: str,
        time_max: str,
        max_results: int = 10,
    ) -> dict[str, Any]:
        """Get calendar events.

        Args:
            calendar_id: Calendar ID
            time_min: Start time (ISO 8601)
            time_max: End time (ISO 8601)
            max_results: Maximum results

        Returns:
            Calendar events
        """
        await self._rate_limit()
        access_token = await self._get_access_token()

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.CALENDAR_BASE_URL}/calendars/{calendar_id}/events",
                headers=self._get_headers(access_token),
                params={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "maxResults": max_results,
                    "singleEvents": True,
                    "orderBy": "startTime",
                },
            )

            if response.status_code != 200:
                self._handle_error(response)

            return response.json()

    async def create_calendar_event(
        self,
        calendar_id: str,
        summary: str,
        start_time: str,
        end_time: str,
        attendees: list[str] | None = None,
        description: str = "",
        location: str | None = None,
    ) -> dict[str, Any]:
        """Create calendar event.

        Args:
            calendar_id: Calendar ID
            summary: Event title
            start_time: Start time (ISO 8601)
            end_time: End time (ISO 8601)
            attendees: Attendee emails
            description: Event description
            location: Event location

        Returns:
            Created event data
        """
        await self._rate_limit()
        access_token = await self._get_access_token()

        event_data = {
            "summary": summary,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
            "description": description,
        }

        if attendees:
            event_data["attendees"] = [{"email": email} for email in attendees]
        if location:
            event_data["location"] = location

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.CALENDAR_BASE_URL}/calendars/{calendar_id}/events",
                headers=self._get_headers(access_token),
                json=event_data,
            )

            if response.status_code != 200:
                self._handle_error(response)

            return response.json()

    # ========================================================================
    # DOCS API
    # ========================================================================

    async def read_document(self, document_id: str) -> dict[str, Any]:
        """Read Google Docs document.

        Args:
            document_id: Document ID

        Returns:
            Document data
        """
        await self._rate_limit()
        access_token = await self._get_access_token()

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.DOCS_BASE_URL}/documents/{document_id}",
                headers=self._get_headers(access_token),
            )

            if response.status_code != 200:
                self._handle_error(response)

            return response.json()
