"""Google Workspace adapter exceptions.

Custom exception hierarchy for Google API errors.
"""


class GoogleAPIError(Exception):
    """Base exception for Google Workspace adapter."""

    pass


class GoogleAuthError(GoogleAPIError):
    """Invalid credentials or insufficient permissions."""

    pass


class GoogleQuotaExceededError(GoogleAPIError):
    """API quota exceeded."""

    pass


class GoogleNotFoundError(GoogleAPIError):
    """Resource not found (404 response)."""

    pass


class GoogleValidationError(GoogleAPIError):
    """Invalid input parameters."""

    pass
