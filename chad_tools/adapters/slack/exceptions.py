"""Slack adapter exceptions.

Custom exception hierarchy for Slack API errors.
"""


class SlackAPIError(Exception):
    """Base exception for Slack adapter."""

    pass


class SlackAuthError(SlackAPIError):
    """Invalid bot token or insufficient permissions."""

    pass


class SlackChannelNotFoundError(SlackAPIError):
    """Channel not found."""

    pass


class SlackRateLimitError(SlackAPIError):
    """Rate limit exceeded."""

    pass


class SlackValidationError(SlackAPIError):
    """Invalid input parameters."""

    pass
