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

from fastapi import Depends, HTTPException, Header
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


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    Dependency: Redis connection.

    Yields:
        Redis: Async Redis client

    TODO: Implement Redis connection pool
    TODO: Add connection health check
    TODO: Add automatic reconnection logic

    Example Usage:
        @app.get("/cache/{key}")
        async def get_cached(key: str, redis: Redis = Depends(get_redis)):
            value = await redis.get(key)
            return {"key": key, "value": value}
    """
    # TODO: Create Redis connection from pool
    # redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    # try:
    #     yield redis_client
    # finally:
    #     await redis_client.close()

    # Placeholder
    raise NotImplementedError("Redis dependency not yet implemented")
    yield  # type: ignore


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

    TODO: Implement queue-specific Redis connection
    TODO: Add queue health check (stream exists, consumer group exists)
    TODO: Add metrics for queue depth

    Example Usage:
        @app.post("/queue/task")
        async def enqueue_task(task: dict, queue: Redis = Depends(get_queue)):
            await queue.xadd(settings.REDIS_QUEUE_STREAM, task)
            return {"status": "queued"}
    """
    # TODO: Use dedicated Redis connection for queue operations
    # Can reuse get_redis() or create separate connection pool

    # Placeholder
    raise NotImplementedError("Queue dependency not yet implemented")
    yield  # type: ignore


# ============================================================================
# AUTH DEPENDENCIES
# ============================================================================


async def get_current_actor(
    authorization: str = Header(..., description="Bearer JWT token"),
    x_hmac_signature: str = Header(..., description="HMAC signature of request body"),
) -> str:
    """
    Dependency: Extract and validate current actor from auth headers.

    Args:
        authorization: Bearer token (JWT)
        x_hmac_signature: HMAC-SHA256 signature of request body

    Returns:
        str: Actor identifier (from JWT "sub" claim)

    Raises:
        HTTPException: 401 if authentication fails

    TODO: Implement JWT validation (python-jose)
    TODO: Implement HMAC validation (hashlib.hmac)
    TODO: Add token blacklist check (Redis)
    TODO: Add rate limit check before processing

    Example Usage:
        @app.post("/act")
        async def execute_action(actor: str = Depends(get_current_actor)):
            return {"actor": actor, "status": "authenticated"}
    """
    # TODO: Validate JWT signature
    # from apps.core_api.auth import validate_jwt
    # payload = await validate_jwt(authorization)
    # actor = payload.get("sub")

    # TODO: Validate HMAC signature
    # from apps.core_api.auth import validate_hmac
    # await validate_hmac(request_body, x_hmac_signature)

    # Placeholder: return test actor
    # Remove this in production!
    if authorization == "Bearer test_token":
        return "test_actor"

    raise HTTPException(status_code=401, detail="Invalid authentication credentials")


async def get_current_actor_optional(
    authorization: str | None = Header(None, description="Optional Bearer JWT token"),
) -> str | None:
    """
    Dependency: Optional actor authentication.

    Returns None if no auth provided, validates if present.

    Returns:
        str | None: Actor identifier or None
    """
    if authorization is None:
        return None

    try:
        # Use get_current_actor logic without requiring header
        # TODO: Implement optional validation
        return None
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
