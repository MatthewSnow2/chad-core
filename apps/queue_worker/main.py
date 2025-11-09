"""
Queue Worker - Background Job Processor.

Redis Streams-based worker that:
- Consumes jobs from Redis Stream
- Executes agent workflows
- Updates job status in Postgres
- Sends webhook notifications
- Handles retries and dead-letter queue

Agent: queue-worker/agent-5
"""

import asyncio
import json
import os
import signal
import sys
from datetime import datetime
from typing import Any

from redis import asyncio as aioredis

from chad_config.settings import Settings
from chad_obs.logging import get_logger
from chad_memory.stores import PostgresStore
from chad_memory.database import get_session_factory
from chad_agents.graphs.graph_langgraph import execute_agent_loop
from chad_llm import LLMRouter
from chad_tools.registry import ToolRegistry
from chad_notifications.webhooks import WebhookNotifier

logger = get_logger(__name__)


class QueueWorker:
    """Redis Streams queue worker for background job processing."""

    def __init__(
        self,
        redis_url: str,
        db_url: str,
        settings: Settings,
    ):
        """Initialize queue worker.

        Args:
            redis_url: Redis connection URL
            db_url: Database connection URL
            settings: Application settings
        """
        self.redis_url = redis_url
        self.db_url = db_url
        self.settings = settings
        self.running = False

        # Initialize components
        self.redis: aioredis.Redis | None = None
        self.postgres_store: PostgresStore | None = None
        self.llm_router: LLMRouter | None = None
        self.tool_registry: ToolRegistry | None = None
        self.webhook_notifier: WebhookNotifier | None = None

        # Consumer name (unique per worker instance)
        self.consumer_name = settings.QUEUE_CONSUMER_NAME
        if self.consumer_name == "worker-default":
            # Use hostname + PID for uniqueness
            import socket
            hostname = socket.gethostname()
            pid = os.getpid()
            self.consumer_name = f"worker-{hostname}-{pid}"

    async def connect(self) -> None:
        """Connect to Redis and initialize components."""
        logger.info("queue_worker_connecting", redis_url=self.redis_url)

        # Connect to Redis
        self.redis = await aioredis.from_url(
            self.redis_url,
            decode_responses=True
        )

        # Initialize Postgres store
        session_factory = get_session_factory(self.db_url)
        self.postgres_store = PostgresStore(session_factory)

        # Initialize LLM router
        self.llm_router = LLMRouter()

        # Initialize tool registry
        self.tool_registry = ToolRegistry()
        # TODO: Register tools (Notion, n8n, GitHub, etc.)
        # For now, basic registry is sufficient

        # Initialize webhook notifier
        self.webhook_notifier = WebhookNotifier(
            timeout_seconds=self.settings.WEBHOOK_TIMEOUT_SECONDS,
            max_retries=self.settings.WEBHOOK_MAX_RETRIES,
            backoff_base=self.settings.WEBHOOK_RETRY_BACKOFF_BASE,
        )

        # Ensure consumer group exists
        await self._ensure_consumer_group()

        logger.info(
            "queue_worker_connected",
            consumer_name=self.consumer_name,
            stream=self.settings.QUEUE_STREAM_NAME,
            group=self.settings.QUEUE_CONSUMER_GROUP,
        )

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            logger.info("queue_worker_disconnected")

    async def _ensure_consumer_group(self) -> None:
        """Create consumer group if it doesn't exist."""
        try:
            await self.redis.xgroup_create(
                name=self.settings.QUEUE_STREAM_NAME,
                groupname=self.settings.QUEUE_CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
            logger.info(
                "consumer_group_created",
                stream=self.settings.QUEUE_STREAM_NAME,
                group=self.settings.QUEUE_CONSUMER_GROUP,
            )
        except aioredis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                # Group already exists
                logger.info(
                    "consumer_group_exists",
                    stream=self.settings.QUEUE_STREAM_NAME,
                    group=self.settings.QUEUE_CONSUMER_GROUP,
                )
            else:
                raise

    async def start(self) -> None:
        """Start consuming jobs from Redis Stream."""
        self.running = True
        logger.info(
            "queue_worker_starting",
            consumer_name=self.consumer_name,
            stream=self.settings.QUEUE_STREAM_NAME,
        )

        # Main worker loop
        while self.running:
            try:
                # Read from stream (blocking with timeout)
                messages = await self.redis.xreadgroup(
                    groupname=self.settings.QUEUE_CONSUMER_GROUP,
                    consumername=self.consumer_name,
                    streams={self.settings.QUEUE_STREAM_NAME: ">"},
                    count=1,
                    block=self.settings.QUEUE_BLOCK_MS,
                )

                if not messages:
                    # No messages, continue polling
                    continue

                # Process each message
                for stream_name, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        await self._process_message(message_id, message_data)

            except asyncio.CancelledError:
                logger.info("queue_worker_cancelled")
                break
            except Exception as e:
                logger.error(
                    "queue_worker_loop_error",
                    error=str(e),
                    consumer_name=self.consumer_name,
                )
                # Brief delay before continuing
                await asyncio.sleep(1)

        logger.info("queue_worker_stopped")

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        logger.info("queue_worker_stopping")
        self.running = False

    async def _process_message(
        self,
        message_id: str,
        message_data: dict[str, str],
    ) -> None:
        """Process a single job message.

        Args:
            message_id: Redis Stream message ID
            message_data: Job data from stream
        """
        run_id = message_data.get("run_id")
        logger.info(
            "job_processing_start",
            message_id=message_id,
            run_id=run_id,
            consumer_name=self.consumer_name,
        )

        try:
            # Parse job data
            job = self._parse_job(message_data)

            # Process job
            result = await self.process_job(job)

            # Update status to completed
            await self.update_job_status(
                run_id=job["run_id"],
                status="completed",
                result=result,
            )

            # Send webhook notification (if configured)
            if job.get("webhook_url"):
                await self.send_webhook_notification(job, result, success=True)

            # Acknowledge message (remove from pending)
            await self.redis.xack(
                self.settings.QUEUE_STREAM_NAME,
                self.settings.QUEUE_CONSUMER_GROUP,
                message_id,
            )

            logger.info(
                "job_processing_complete",
                message_id=message_id,
                run_id=run_id,
                status="completed",
            )

        except Exception as e:
            logger.error(
                "job_processing_failed",
                message_id=message_id,
                run_id=run_id,
                error=str(e),
            )

            # Check retry count
            retry_count = int(message_data.get("retry_count", "0"))

            if retry_count < self.settings.QUEUE_MAX_RETRIES:
                # Retry: re-add to stream with incremented retry count
                await self._retry_job(message_data, retry_count)
            else:
                # Max retries exceeded: move to DLQ
                await self._move_to_dlq(message_id, message_data, str(e))

                # Update status to failed
                await self.update_job_status(
                    run_id=run_id,
                    status="failed",
                    error=str(e),
                )

                # Send failure webhook (if configured)
                if message_data.get("webhook_url"):
                    job = self._parse_job(message_data)
                    await self.send_webhook_notification(
                        job,
                        {"error": str(e)},
                        success=False,
                    )

            # Acknowledge message (remove from pending)
            await self.redis.xack(
                self.settings.QUEUE_STREAM_NAME,
                self.settings.QUEUE_CONSUMER_GROUP,
                message_id,
            )

    def _parse_job(self, message_data: dict[str, str]) -> dict[str, Any]:
        """Parse job data from Redis Stream message.

        Args:
            message_data: Raw message data (all strings)

        Returns:
            Parsed job data with correct types
        """
        return {
            "run_id": message_data["run_id"],
            "goal": message_data["goal"],
            "actor": message_data["actor"],
            "autonomy_level": message_data["autonomy_level"],
            "context": json.loads(message_data.get("context", "{}")),
            "max_steps": int(message_data.get("max_steps", "10")),
            "dry_run": message_data.get("dry_run", "false").lower() == "true",
            "webhook_url": message_data.get("webhook_url", ""),
            "created_at": message_data.get("created_at"),
        }

    async def process_job(self, job: dict[str, Any]) -> dict[str, Any]:
        """Execute agent workflow for a job.

        Args:
            job: Job data

        Returns:
            Execution result
        """
        logger.info(
            "job_execution_start",
            run_id=job["run_id"],
            goal=job["goal"],
            actor=job["actor"],
        )

        # Update status to running
        await self.update_job_status(
            run_id=job["run_id"],
            status="running",
        )

        # Execute agent loop
        result = await execute_agent_loop(
            run_id=job["run_id"],
            goal=job["goal"],
            context=job["context"],
            autonomy_level=job["autonomy_level"],
            dry_run=job["dry_run"],
            max_steps=job["max_steps"],
            llm_router=self.llm_router,
            tool_registry=self.tool_registry,
        )

        logger.info(
            "job_execution_complete",
            run_id=job["run_id"],
            status=result.get("status"),
        )

        return result

    async def update_job_status(
        self,
        run_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Update job status in Postgres.

        Args:
            run_id: Run identifier
            status: New status (running, completed, failed)
            result: Execution result (if completed)
            error: Error message (if failed)
        """
        update_data = {
            "id": run_id,
            "status": status,
        }

        if status == "completed" or status == "failed":
            update_data["completed_at"] = datetime.utcnow()

        if error:
            update_data["error_message"] = error

        await self.postgres_store.save_run(update_data)

        logger.info(
            "job_status_updated",
            run_id=run_id,
            status=status,
        )

    async def send_webhook_notification(
        self,
        job: dict[str, Any],
        result: dict[str, Any],
        success: bool = True,
    ) -> None:
        """Send webhook notification for job completion/failure.

        Args:
            job: Job data
            result: Execution result
            success: True if completed, False if failed
        """
        webhook_url = job.get("webhook_url")
        if not webhook_url:
            return

        if success:
            await self.webhook_notifier.send_completion_webhook(
                run_id=job["run_id"],
                actor=job["actor"],
                result=result,
                webhook_url=webhook_url,
            )
        else:
            await self.webhook_notifier.send_failure_webhook(
                run_id=job["run_id"],
                actor=job["actor"],
                error=result.get("error", "Unknown error"),
                webhook_url=webhook_url,
            )

    async def _retry_job(
        self,
        message_data: dict[str, str],
        retry_count: int,
    ) -> None:
        """Retry a failed job by re-adding to stream.

        Args:
            message_data: Original message data
            retry_count: Current retry count
        """
        # Increment retry count
        retry_data = dict(message_data)
        retry_data["retry_count"] = str(retry_count + 1)

        # Add to stream
        await self.redis.xadd(
            self.settings.QUEUE_STREAM_NAME,
            retry_data,
        )

        logger.info(
            "job_retry_scheduled",
            run_id=message_data["run_id"],
            retry_count=retry_count + 1,
            max_retries=self.settings.QUEUE_MAX_RETRIES,
        )

        # Delay before processing retry
        await asyncio.sleep(self.settings.QUEUE_RETRY_DELAY_SECONDS)

    async def _move_to_dlq(
        self,
        message_id: str,
        message_data: dict[str, str],
        error: str,
    ) -> None:
        """Move failed job to dead-letter queue.

        Args:
            message_id: Original message ID
            message_data: Job data
            error: Error message
        """
        dlq_data = dict(message_data)
        dlq_data["error"] = error
        dlq_data["failed_at"] = datetime.utcnow().isoformat()
        dlq_data["original_message_id"] = message_id

        await self.redis.xadd(
            self.settings.QUEUE_DEAD_LETTER_STREAM,
            dlq_data,
        )

        logger.error(
            "job_moved_to_dlq",
            run_id=message_data["run_id"],
            message_id=message_id,
            error=error,
        )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


async def main():
    """Main entry point for queue worker."""
    # Load settings
    settings = Settings()

    # Initialize worker
    worker = QueueWorker(
        redis_url=settings.REDIS_URL,
        db_url=settings.DATABASE_URL,
        settings=settings,
    )

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler(sig):
        logger.info("signal_received", signal=sig)
        loop.create_task(worker.stop())

    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s))

    # Connect and start worker
    await worker.connect()

    try:
        await worker.start()
    finally:
        await worker.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("queue_worker_interrupted")
        sys.exit(0)
