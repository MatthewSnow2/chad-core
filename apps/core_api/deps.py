"""
FastAPI Dependency Injection.

Provides dependency injection for:
- Database sessions (asyncpg + SQLAlchemy)
- Redis connections
- OpenTelemetry tracers
- Queue connections
- Authentication context

Agent: api-scaffolding/backend-architect
"""

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Header, status
from opentelemetry import trace
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from chad_config.settings import Settings

# Initialize settings
settings = Settings()


# ============================================================================
# DATABASE DEPENDENCIES
# ============================================================================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency: Async database session.

    Yields:
        AsyncSession: SQLAlchemy async session

    Example Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    from chad_memory.database import get_db_session

    async for session in get_db_session():
        yield session


# ============================================================================
# REDIS DEPENDENCIES
# ============================================================================


_redis_client: Redis | None = None


async def init_redis() -> None:
    """Initialize Redis connection pool."""
    global _redis_client
    _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


def get_redis_client() -> Redis | None:
    """Get Redis client (for use in middleware and auth)."""
    return _redis_client


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    Dependency: Redis connection.

    Yields:
        Redis: Async Redis client

    Example Usage:
        @app.get("/cache/{key}")
        async def get_cached(key: str, redis: Redis = Depends(get_redis)):
            value = await redis.get(key)
            return {"key": key, "value": value}
    """
    global _redis_client
    if not _redis_client:
        _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    yield _redis_client


# ============================================================================
# TRACING DEPENDENCIES
# ============================================================================


def get_tracer() -> trace.Tracer:
    """
    Dependency: OpenTelemetry tracer.

    Returns:
        Tracer: OpenTelemetry tracer instance

    Example Usage:
        @app.get("/process")
        async def process_item(tracer: Tracer = Depends(get_tracer)):
            with tracer.start_as_current_span("process_item"):
                # Processing logic
                pass
    """
    return trace.get_tracer(__name__)


# ============================================================================
# QUEUE DEPENDENCIES
# ============================================================================


async def get_queue() -> AsyncGenerator[Redis, None]:
    """
    Dependency: Redis stream queue connection.

    Yields:
        Redis: Redis client configured for stream operations

    Example Usage:
        @app.post("/queue/task")
        async def enqueue_task(task: dict, queue: Redis = Depends(get_queue)):
            await queue.xadd(settings.REDIS_QUEUE_STREAM, task)
            return {"status": "queued"}
    """
    # Reuse existing Redis connection for queue operations
    async for redis in get_redis():
        yield redis


# ============================================================================
# QUEUE PRODUCER
# ============================================================================


class QueueProducer:
    """Queue producer for enqueuing background jobs to Redis Streams."""

    def __init__(self, redis_client: Redis, settings: Settings):
        """Initialize queue producer.

        Args:
            redis_client: Redis client instance
            settings: Application settings
        """
        self.redis = redis_client
        self.settings = settings

    async def enqueue(
        self,
        run_id: str,
        goal: str,
        actor: str,
        autonomy_level: str,
        context: dict | None = None,
        max_steps: int = 10,
        dry_run: bool = False,
        webhook_url: str | None = None,
    ) -> str:
        """Enqueue a job to Redis Stream.

        Args:
            run_id: Run identifier
            goal: Agent goal
            actor: Actor identifier
            autonomy_level: Autonomy level
            context: Additional context
            max_steps: Max execution steps
            dry_run: Dry run mode
            webhook_url: Optional webhook URL for notifications

        Returns:
            Job ID (message ID from XADD)
        """
        import json
        from datetime import datetime

        job_data = {
            "run_id": run_id,
            "goal": goal,
            "actor": actor,
            "autonomy_level": autonomy_level,
            "context": json.dumps(context or {}),
            "max_steps": str(max_steps),
            "dry_run": str(dry_run),
            "webhook_url": webhook_url or "",
            "created_at": datetime.utcnow().isoformat(),
            "retry_count": "0",
        }

        # Add to Redis Stream
        job_id = await self.redis.xadd(
            self.settings.QUEUE_STREAM_NAME,
            job_data
        )

        return job_id

    async def get_queue_depth(self) -> int:
        """Get current queue depth.

        Returns:
            Number of pending jobs in stream
        """
        info = await self.redis.xinfo_stream(self.settings.QUEUE_STREAM_NAME)
        return info.get("length", 0)


async def get_queue_producer(
    redis: Redis = Depends(get_redis),
) -> QueueProducer:
    """Dependency: Queue producer instance.

    Args:
        redis: Redis client

    Returns:
        QueueProducer instance

    Raises:
        HTTPException: 503 if Redis unavailable

    Example Usage:
        @app.post("/act")
        async def act(
            producer: QueueProducer = Depends(get_queue_producer)
        ):
            job_id = await producer.enqueue(...)
            return {"job_id": job_id}
    """
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue service unavailable"
        )
    # Use global settings instance
    return QueueProducer(redis, settings)


# ============================================================================
# AUTH DEPENDENCIES
# ============================================================================


async def get_current_user(
    authorization: str = Header(..., description="Bearer JWT token"),
) -> "User":
    """
    Dependency: Extract and validate current user from JWT.

    Args:
        authorization: Bearer token (JWT)

    Returns:
        User: User model with user_id and scopes

    Raises:
        HTTPException: 401 if authentication fails

    Example Usage:
        @app.post("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.user_id, "scopes": user.scopes}
    """
    from apps.core_api.auth import validate_jwt, User

    return await validate_jwt(authorization)


async def get_current_service_account(
    x_hmac_signature: str = Header(..., description="HMAC signature of request body"),
    x_request_timestamp: str = Header(..., description="Unix timestamp of request"),
    request: "Request" = None,
) -> "ServiceAccount":
    """
    Dependency: Validate HMAC signature and return service account.

    Args:
        x_hmac_signature: HMAC-SHA256 signature
        x_request_timestamp: Request timestamp
        request: FastAPI Request object

    Returns:
        ServiceAccount: Service account model

    Raises:
        HTTPException: 401 if HMAC validation fails

    Example Usage:
        @app.post("/webhook")
        async def webhook(
            service: ServiceAccount = Depends(get_current_service_account),
            data: dict = Body(...)
        ):
            return {"service": service.service_id}
    """
    from apps.core_api.auth import validate_hmac, ServiceAccount
    from fastapi import Request

    # Get request body
    body = await request.body()

    return await validate_hmac(body, x_hmac_signature, x_request_timestamp)


def require_scopes(required_scopes: list[str]):
    """
    Dependency factory: Require specific scopes.

    Args:
        required_scopes: List of required scopes

    Returns:
        Callable: Dependency function

    Raises:
        HTTPException: 403 if insufficient permissions

    Example Usage:
        @app.post("/admin")
        async def admin_route(
            user: User = Depends(get_current_user),
            _: None = Depends(require_scopes(["admin.*"]))
        ):
            return {"status": "authorized"}
    """
    from apps.core_api.auth import check_scopes, User

    async def scope_checker(user: User = Depends(get_current_user)) -> None:
        if not check_scopes(required_scopes, user.scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required scopes: {required_scopes}",
            )

    return scope_checker


async def get_current_user_optional(
    authorization: str | None = Header(None, description="Optional Bearer JWT token"),
) -> "User | None":
    """
    Dependency: Optional user authentication.

    Returns None if no auth provided, validates if present.

    Returns:
        User | None: User model or None
    """
    if authorization is None:
        return None

    try:
        from apps.core_api.auth import validate_jwt

        return await validate_jwt(authorization)
    except HTTPException:
        return None


# ============================================================================
# REQUEST CONTEXT DEPENDENCIES
# ============================================================================


async def get_request_id(x_request_id: str | None = Header(None)) -> str:
    """
    Dependency: Get or generate request ID.

    Args:
        x_request_id: Optional client-provided request ID

    Returns:
        str: Request ID (client-provided or generated)

    TODO: Add request ID to logging context
    TODO: Add request ID to trace attributes
    """
    import uuid

    if x_request_id:
        return x_request_id

    # Generate new request ID
    return str(uuid.uuid4())


async def get_trace_id(tracer: trace.Tracer = Depends(get_tracer)) -> str:
    """
    Dependency: Extract current trace ID from OpenTelemetry context.

    Returns:
        str: Trace ID (hex format)

    Example Usage:
        @app.get("/debug")
        async def debug_endpoint(trace_id: str = Depends(get_trace_id)):
            return {"trace_id": trace_id}
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, "032x")

    return "no_trace"


# ============================================================================
# SETTINGS DEPENDENCY
# ============================================================================


def get_settings() -> Settings:
    """
    Dependency: Application settings.

    Returns:
        Settings: Pydantic settings instance

    Example Usage:
        @app.get("/config")
        async def get_config(settings: Settings = Depends(get_settings)):
            return {"environment": settings.ENVIRONMENT}
    """
    return settings


# ============================================================================
# STORE DEPENDENCIES
# ============================================================================


def get_postgres_store():
    """
    Dependency: PostgresStore instance.

    Returns:
        PostgresStore: Store instance with session factory

    Example Usage:
        @app.get("/runs")
        async def list_runs(store = Depends(get_postgres_store)):
            return await store.list_runs(actor="test")
    """
    from chad_memory.database import get_session_factory
    from chad_memory.stores import PostgresStore

    session_factory = get_session_factory()
    return PostgresStore(session_factory)


def get_vector_store():
    """
    Dependency: PgVectorStore instance.

    Returns:
        PgVectorStore: Vector store instance with session factory

    Example Usage:
        @app.post("/search")
        async def search(embedding: list, store = Depends(get_vector_store)):
            return await store.search(embedding, limit=10)
    """
    from chad_memory.database import get_session_factory
    from chad_memory.stores import PgVectorStore

    session_factory = get_session_factory()
    return PgVectorStore(session_factory)


# ============================================================================
# AGENT SIGN-OFF
# ============================================================================
# ✅ api-scaffolding/backend-architect
# ✅ api-scaffolding/fastapi-pro
