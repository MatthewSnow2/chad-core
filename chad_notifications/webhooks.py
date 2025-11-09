"""
Webhook notification system with retry logic.

Implements:
- HTTP POST webhook delivery
- Exponential backoff retry
- Failure tracking
- Timeout handling

Agent: queue-worker/agent-5
"""

import asyncio
import json
from datetime import datetime
from typing import Any

import httpx

from chad_obs.logging import get_logger

logger = get_logger(__name__)


class WebhookNotifier:
    """Webhook notification service with retry logic."""

    def __init__(
        self,
        timeout_seconds: int = 10,
        max_retries: int = 3,
        backoff_base: int = 2,
    ):
        """Initialize webhook notifier.

        Args:
            timeout_seconds: HTTP request timeout
            max_retries: Maximum retry attempts
            backoff_base: Base for exponential backoff (seconds)
        """
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    async def send_completion_webhook(
        self,
        run_id: str,
        actor: str,
        result: dict[str, Any],
        webhook_url: str,
    ) -> bool:
        """Send completion notification webhook.

        Args:
            run_id: Run identifier
            actor: Actor identifier
            result: Execution result data
            webhook_url: Webhook URL to POST to

        Returns:
            True if webhook delivered successfully, False otherwise
        """
        payload = {
            "event": "run.completed",
            "run_id": run_id,
            "actor": actor,
            "status": "completed",
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return await self._send_webhook(webhook_url, payload)

    async def send_failure_webhook(
        self,
        run_id: str,
        actor: str,
        error: str,
        webhook_url: str,
    ) -> bool:
        """Send failure notification webhook.

        Args:
            run_id: Run identifier
            actor: Actor identifier
            error: Error message
            webhook_url: Webhook URL to POST to

        Returns:
            True if webhook delivered successfully, False otherwise
        """
        payload = {
            "event": "run.failed",
            "run_id": run_id,
            "actor": actor,
            "status": "failed",
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return await self._send_webhook(webhook_url, payload)

    async def send_status_update_webhook(
        self,
        run_id: str,
        actor: str,
        status: str,
        progress: int,
        webhook_url: str,
    ) -> bool:
        """Send status update webhook.

        Args:
            run_id: Run identifier
            actor: Actor identifier
            status: Current status
            progress: Progress percentage (0-100)
            webhook_url: Webhook URL to POST to

        Returns:
            True if webhook delivered successfully, False otherwise
        """
        payload = {
            "event": "run.status_update",
            "run_id": run_id,
            "actor": actor,
            "status": status,
            "progress": progress,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return await self._send_webhook(webhook_url, payload)

    async def _send_webhook(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> bool:
        """Send webhook with retry logic.

        Args:
            url: Webhook URL
            payload: JSON payload

        Returns:
            True if delivered successfully, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        json=payload,
                        timeout=self.timeout_seconds,
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": "Chad-Core-Queue-Worker/1.0",
                        },
                    )

                    # Check response status
                    if response.status_code >= 200 and response.status_code < 300:
                        logger.info(
                            "webhook_delivered",
                            url=url,
                            event_type=payload.get("event"),
                            run_id=payload.get("run_id"),
                            status_code=response.status_code,
                            attempt=attempt + 1,
                        )
                        return True
                    else:
                        logger.warning(
                            "webhook_failed_status",
                            url=url,
                            event_type=payload.get("event"),
                            run_id=payload.get("run_id"),
                            status_code=response.status_code,
                            attempt=attempt + 1,
                        )

            except httpx.TimeoutException as e:
                logger.warning(
                    "webhook_timeout",
                    url=url,
                    event_type=payload.get("event"),
                    run_id=payload.get("run_id"),
                    attempt=attempt + 1,
                    error=str(e),
                )

            except httpx.RequestError as e:
                logger.warning(
                    "webhook_request_error",
                    url=url,
                    event_type=payload.get("event"),
                    run_id=payload.get("run_id"),
                    attempt=attempt + 1,
                    error=str(e),
                )

            except Exception as e:
                logger.error(
                    "webhook_unexpected_error",
                    url=url,
                    event_type=payload.get("event"),
                    run_id=payload.get("run_id"),
                    attempt=attempt + 1,
                    error=str(e),
                )

            # Exponential backoff before retry (skip on last attempt)
            if attempt < self.max_retries - 1:
                delay = self.backoff_base ** attempt
                logger.info(
                    "webhook_retry_backoff",
                    url=url,
                    event_type=payload.get("event"),
                    run_id=payload.get("run_id"),
                    delay_seconds=delay,
                    next_attempt=attempt + 2,
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(
            "webhook_delivery_failed",
            url=url,
            event_type=payload.get("event"),
            run_id=payload.get("run_id"),
            max_retries=self.max_retries,
        )
        return False


# ============================================================================
# FACTORY FUNCTION
# ============================================================================


def create_webhook_notifier(
    timeout_seconds: int = 10,
    max_retries: int = 3,
    backoff_base: int = 2,
) -> WebhookNotifier:
    """Create webhook notifier instance.

    Args:
        timeout_seconds: HTTP request timeout
        max_retries: Maximum retry attempts
        backoff_base: Base for exponential backoff

    Returns:
        WebhookNotifier instance
    """
    return WebhookNotifier(
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        backoff_base=backoff_base,
    )
