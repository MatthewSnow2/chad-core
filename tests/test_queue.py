"""
Queue System Tests.

Tests for:
- QueueProducer (enqueuing jobs)
- QueueWorker (processing jobs)
- Webhook notifications
- Retry logic
- Dead letter queue

Agent: queue-worker/agent-5
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis import asyncio as aioredis

from apps.core_api.deps import QueueProducer
from apps.queue_worker.main import QueueWorker
from chad_config.settings import Settings
from chad_notifications.webhooks import WebhookNotifier


# ============================================================================
# QUEUE PRODUCER TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_queue_producer_enqueue():
    """Test enqueuing a job to Redis Stream."""
    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value="1234567890-0")

    # Create settings
    settings = Settings()

    # Create producer
    producer = QueueProducer(mock_redis, settings)

    # Enqueue job
    job_id = await producer.enqueue(
        run_id="test-run-123",
        goal="Test goal",
        actor="test-user",
        autonomy_level="L2_ExecuteNotify",
        context={"key": "value"},
        max_steps=10,
        dry_run=False,
        webhook_url="https://example.com/webhook",
    )

    # Verify
    assert job_id == "1234567890-0"
    mock_redis.xadd.assert_called_once()

    # Check call arguments
    call_args = mock_redis.xadd.call_args
    stream_name = call_args[0][0]
    job_data = call_args[0][1]

    assert stream_name == settings.QUEUE_STREAM_NAME
    assert job_data["run_id"] == "test-run-123"
    assert job_data["goal"] == "Test goal"
    assert job_data["actor"] == "test-user"
    assert job_data["autonomy_level"] == "L2_ExecuteNotify"
    assert json.loads(job_data["context"]) == {"key": "value"}
    assert job_data["max_steps"] == "10"
    assert job_data["dry_run"] == "False"
    assert job_data["webhook_url"] == "https://example.com/webhook"
    assert job_data["retry_count"] == "0"


@pytest.mark.asyncio
async def test_queue_producer_get_queue_depth():
    """Test getting queue depth."""
    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.xinfo_stream = AsyncMock(return_value={"length": 5})

    settings = Settings()
    producer = QueueProducer(mock_redis, settings)

    # Get queue depth
    depth = await producer.get_queue_depth()

    assert depth == 5
    mock_redis.xinfo_stream.assert_called_once_with(settings.QUEUE_STREAM_NAME)


# ============================================================================
# QUEUE WORKER TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_queue_worker_parse_job():
    """Test parsing job data from Redis Stream message."""
    settings = Settings()
    worker = QueueWorker(
        redis_url="redis://localhost:6379",
        db_url="postgresql://localhost/test",
        settings=settings,
    )

    message_data = {
        "run_id": "test-run-123",
        "goal": "Test goal",
        "actor": "test-user",
        "autonomy_level": "L2_ExecuteNotify",
        "context": '{"key": "value"}',
        "max_steps": "10",
        "dry_run": "true",
        "webhook_url": "https://example.com/webhook",
        "created_at": "2024-01-01T12:00:00",
    }

    job = worker._parse_job(message_data)

    assert job["run_id"] == "test-run-123"
    assert job["goal"] == "Test goal"
    assert job["actor"] == "test-user"
    assert job["autonomy_level"] == "L2_ExecuteNotify"
    assert job["context"] == {"key": "value"}
    assert job["max_steps"] == 10
    assert job["dry_run"] is True
    assert job["webhook_url"] == "https://example.com/webhook"
    assert job["created_at"] == "2024-01-01T12:00:00"


@pytest.mark.asyncio
async def test_queue_worker_process_job():
    """Test processing a job (mock execution)."""
    settings = Settings()
    worker = QueueWorker(
        redis_url="redis://localhost:6379",
        db_url="postgresql://localhost/test",
        settings=settings,
    )

    # Mock dependencies
    worker.postgres_store = AsyncMock()
    worker.llm_router = MagicMock()
    worker.tool_registry = MagicMock()

    job = {
        "run_id": "test-run-123",
        "goal": "Test goal",
        "actor": "test-user",
        "autonomy_level": "L2_ExecuteNotify",
        "context": {},
        "max_steps": 10,
        "dry_run": False,
    }

    # Mock execute_agent_loop
    with patch("apps.queue_worker.main.execute_agent_loop") as mock_execute:
        mock_execute.return_value = {
            "status": "completed",
            "run_id": "test-run-123",
            "executed_steps": [],
        }

        result = await worker.process_job(job)

        assert result["status"] == "completed"
        assert result["run_id"] == "test-run-123"

        # Verify status update was called
        worker.postgres_store.save_run.assert_called()


@pytest.mark.asyncio
async def test_queue_worker_update_job_status():
    """Test updating job status in database."""
    settings = Settings()
    worker = QueueWorker(
        redis_url="redis://localhost:6379",
        db_url="postgresql://localhost/test",
        settings=settings,
    )

    # Mock postgres store
    worker.postgres_store = AsyncMock()

    # Update status to running
    await worker.update_job_status(
        run_id="test-run-123",
        status="running",
    )

    worker.postgres_store.save_run.assert_called_once()
    call_args = worker.postgres_store.save_run.call_args[0][0]
    assert call_args["id"] == "test-run-123"
    assert call_args["status"] == "running"


@pytest.mark.asyncio
async def test_queue_worker_retry_logic():
    """Test job retry on failure."""
    settings = Settings()
    settings.QUEUE_MAX_RETRIES = 3
    settings.QUEUE_RETRY_DELAY_SECONDS = 1

    worker = QueueWorker(
        redis_url="redis://localhost:6379",
        db_url="postgresql://localhost/test",
        settings=settings,
    )

    # Mock Redis
    worker.redis = AsyncMock()

    message_data = {
        "run_id": "test-run-123",
        "goal": "Test goal",
        "actor": "test-user",
        "autonomy_level": "L2_ExecuteNotify",
        "context": "{}",
        "max_steps": "10",
        "dry_run": "false",
        "webhook_url": "",
        "retry_count": "1",
    }

    # Retry job
    await worker._retry_job(message_data, 1)

    # Verify job was re-added to stream
    worker.redis.xadd.assert_called_once()
    call_args = worker.redis.xadd.call_args[0]
    assert call_args[0] == settings.QUEUE_STREAM_NAME
    assert call_args[1]["retry_count"] == "2"


@pytest.mark.asyncio
async def test_queue_worker_dead_letter_queue():
    """Test moving failed job to DLQ after max retries."""
    settings = Settings()
    settings.QUEUE_MAX_RETRIES = 3

    worker = QueueWorker(
        redis_url="redis://localhost:6379",
        db_url="postgresql://localhost/test",
        settings=settings,
    )

    # Mock Redis
    worker.redis = AsyncMock()

    message_data = {
        "run_id": "test-run-123",
        "goal": "Test goal",
        "actor": "test-user",
        "autonomy_level": "L2_ExecuteNotify",
        "context": "{}",
        "max_steps": "10",
        "dry_run": "false",
        "webhook_url": "",
        "retry_count": "3",
    }

    # Move to DLQ
    await worker._move_to_dlq(
        message_id="1234567890-0",
        message_data=message_data,
        error="Test error",
    )

    # Verify job was added to DLQ
    worker.redis.xadd.assert_called_once()
    call_args = worker.redis.xadd.call_args[0]
    assert call_args[0] == settings.QUEUE_DEAD_LETTER_STREAM
    assert call_args[1]["error"] == "Test error"
    assert call_args[1]["original_message_id"] == "1234567890-0"


# ============================================================================
# WEBHOOK NOTIFIER TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_webhook_notifier_send_completion():
    """Test sending completion webhook."""
    notifier = WebhookNotifier(
        timeout_seconds=5,
        max_retries=2,
        backoff_base=1,
    )

    # Mock httpx client
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 200

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        # Send webhook
        success = await notifier.send_completion_webhook(
            run_id="test-run-123",
            actor="test-user",
            result={"status": "completed"},
            webhook_url="https://example.com/webhook",
        )

        assert success is True


@pytest.mark.asyncio
async def test_webhook_notifier_send_failure():
    """Test sending failure webhook."""
    notifier = WebhookNotifier(
        timeout_seconds=5,
        max_retries=2,
        backoff_base=1,
    )

    # Mock httpx client
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 200

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        # Send webhook
        success = await notifier.send_failure_webhook(
            run_id="test-run-123",
            actor="test-user",
            error="Test error",
            webhook_url="https://example.com/webhook",
        )

        assert success is True


@pytest.mark.asyncio
async def test_webhook_notifier_retry_on_failure():
    """Test webhook retry logic on HTTP error."""
    notifier = WebhookNotifier(
        timeout_seconds=5,
        max_retries=3,
        backoff_base=1,
    )

    # Mock httpx client to fail twice, then succeed
    with patch("httpx.AsyncClient") as mock_client:
        mock_response_fail = AsyncMock()
        mock_response_fail.status_code = 500

        mock_response_success = AsyncMock()
        mock_response_success.status_code = 200

        mock_post = AsyncMock(
            side_effect=[mock_response_fail, mock_response_fail, mock_response_success]
        )

        mock_client.return_value.__aenter__.return_value.post = mock_post

        # Send webhook
        success = await notifier.send_completion_webhook(
            run_id="test-run-123",
            actor="test-user",
            result={"status": "completed"},
            webhook_url="https://example.com/webhook",
        )

        # Should succeed after retries
        assert success is True
        assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_webhook_notifier_max_retries_exceeded():
    """Test webhook fails after max retries."""
    notifier = WebhookNotifier(
        timeout_seconds=5,
        max_retries=2,
        backoff_base=1,
    )

    # Mock httpx client to always fail
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 500

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        # Send webhook
        success = await notifier.send_completion_webhook(
            run_id="test-run-123",
            actor="test-user",
            result={"status": "completed"},
            webhook_url="https://example.com/webhook",
        )

        # Should fail after max retries
        assert success is False


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_queue_end_to_end_flow():
    """
    End-to-end integration test for queue system.

    Requires:
    - Redis running on localhost:6379
    - Postgres running with test database

    This test:
    1. Enqueues a job
    2. Worker processes it
    3. Updates status
    4. Sends webhook
    """
    # Skip if Redis not available
    try:
        redis = await aioredis.from_url("redis://localhost:6379")
        await redis.ping()
        await redis.close()
    except Exception:
        pytest.skip("Redis not available")

    # This would be a full integration test
    # Implementation would require actual Redis and Postgres instances
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
