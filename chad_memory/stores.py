"""Memory Store Adapters.

Redis-backed working memory for agent execution state persistence.
"""

import json
from typing import Any
from datetime import timedelta

from redis import asyncio as aioredis


# ============================================================================
# REDIS WORKING MEMORY STORE
# ============================================================================


class RedisStore:
    """Redis working memory for agent execution.

    Stores:
    - Agent state (plan, current step, working memory)
    - Step results (tool outputs)
    - LLM call tracking (model used, tokens, cost)
    - Final results

    Key Structure:
    - run:{run_id}:state → AgentState (JSON)
    - run:{run_id}:step:{step_number} → StepResult (JSON)
    - run:{run_id}:final → FinalResult (JSON)
    - run:{run_id}:llm_calls → List of LLM call records
    """

    def __init__(self, redis_url: str, default_ttl: int = 86400):
        """Initialize Redis store.

        Args:
            redis_url: Redis connection URL (redis://localhost:6379/0)
            default_ttl: Default TTL in seconds (24 hours)
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        if self._client is None:
            self._client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        """Get Redis client.

        Raises:
            RuntimeError: If not connected
        """
        if self._client is None:
            raise RuntimeError("RedisStore not connected. Call connect() first.")
        return self._client

    # ------------------------------------------------------------------------
    # BASIC OPERATIONS
    # ------------------------------------------------------------------------

    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None
    ) -> None:
        """Set key-value pair with optional TTL.

        Args:
            key: Redis key
            value: Value to store
            ttl: Time-to-live in seconds (default: 24 hours)
        """
        ttl = ttl or self.default_ttl
        await self.client.set(key, value, ex=ttl)

    async def get(self, key: str) -> str | None:
        """Get value by key.

        Args:
            key: Redis key

        Returns:
            Value or None if not found
        """
        return await self.client.get(key)

    async def delete(self, key: str) -> None:
        """Delete key.

        Args:
            key: Redis key
        """
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists.

        Args:
            key: Redis key

        Returns:
            True if key exists
        """
        return bool(await self.client.exists(key))

    async def expire(self, key: str, ttl: int) -> None:
        """Set TTL on existing key.

        Args:
            key: Redis key
            ttl: Time-to-live in seconds
        """
        await self.client.expire(key, ttl)

    # ------------------------------------------------------------------------
    # AGENT STATE OPERATIONS
    # ------------------------------------------------------------------------

    async def save_state(
        self,
        run_id: str,
        state: dict[str, Any],
        ttl: int | None = None
    ) -> None:
        """Save agent state.

        Args:
            run_id: Run identifier
            state: Agent state dict
            ttl: Optional TTL override
        """
        key = f"run:{run_id}:state"
        value = json.dumps(state)
        await self.set(key, value, ttl=ttl)

    async def get_state(self, run_id: str) -> dict[str, Any] | None:
        """Get agent state.

        Args:
            run_id: Run identifier

        Returns:
            Agent state or None if not found
        """
        key = f"run:{run_id}:state"
        value = await self.get(key)

        if value:
            return json.loads(value)
        return None

    async def update_state(
        self,
        run_id: str,
        updates: dict[str, Any]
    ) -> None:
        """Update specific fields in agent state.

        Args:
            run_id: Run identifier
            updates: Dict of fields to update
        """
        state = await self.get_state(run_id)

        if state:
            state.update(updates)
            await self.save_state(run_id, state)

    # ------------------------------------------------------------------------
    # STEP RESULT OPERATIONS
    # ------------------------------------------------------------------------

    async def save_step_result(
        self,
        run_id: str,
        step_number: int,
        result: dict[str, Any],
        ttl: int | None = None
    ) -> None:
        """Save step execution result.

        Args:
            run_id: Run identifier
            step_number: Step number (1-indexed)
            result: Step result dict
            ttl: Optional TTL override
        """
        key = f"run:{run_id}:step:{step_number}"
        value = json.dumps(result)
        await self.set(key, value, ttl=ttl)

    async def get_step_result(
        self,
        run_id: str,
        step_number: int
    ) -> dict[str, Any] | None:
        """Get step execution result.

        Args:
            run_id: Run identifier
            step_number: Step number (1-indexed)

        Returns:
            Step result or None if not found
        """
        key = f"run:{run_id}:step:{step_number}"
        value = await self.get(key)

        if value:
            return json.loads(value)
        return None

    async def get_all_step_results(
        self,
        run_id: str
    ) -> list[dict[str, Any]]:
        """Get all step results for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of step results in order
        """
        # Find all step keys
        pattern = f"run:{run_id}:step:*"
        keys = await self.client.keys(pattern)

        if not keys:
            return []

        # Sort keys by step number
        sorted_keys = sorted(keys, key=lambda k: int(k.split(":")[-1]))

        # Get all results
        results = []
        for key in sorted_keys:
            value = await self.get(key)
            if value:
                results.append(json.loads(value))

        return results

    # ------------------------------------------------------------------------
    # FINAL RESULT OPERATIONS
    # ------------------------------------------------------------------------

    async def save_final_result(
        self,
        run_id: str,
        result: dict[str, Any],
        ttl: int | None = None
    ) -> None:
        """Save final workflow result.

        Args:
            run_id: Run identifier
            result: Final result dict
            ttl: Optional TTL override (default: 7 days for final results)
        """
        key = f"run:{run_id}:final"
        value = json.dumps(result)
        # Final results get 7 day TTL by default
        ttl = ttl or (self.default_ttl * 7)
        await self.set(key, value, ttl=ttl)

    async def get_final_result(
        self,
        run_id: str
    ) -> dict[str, Any] | None:
        """Get final workflow result.

        Args:
            run_id: Run identifier

        Returns:
            Final result or None if not found
        """
        key = f"run:{run_id}:final"
        value = await self.get(key)

        if value:
            return json.loads(value)
        return None

    # ------------------------------------------------------------------------
    # LLM CALL TRACKING
    # ------------------------------------------------------------------------

    async def track_llm_call(
        self,
        run_id: str,
        model: str,
        task_type: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0
    ) -> None:
        """Track LLM API call.

        Args:
            run_id: Run identifier
            model: Model used (gpt-4o, claude-3-5-sonnet-20241022)
            task_type: Task type (planning, reflection, user_response)
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            cost: Estimated cost in USD
        """
        key = f"run:{run_id}:llm_calls"

        call_record = {
            "model": model,
            "task_type": task_type,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost": cost,
            "timestamp": None,  # Redis doesn't store timestamps in lists
        }

        # Append to list
        await self.client.rpush(key, json.dumps(call_record))
        # Set TTL on first call
        await self.expire(key, self.default_ttl)

    async def get_llm_calls(self, run_id: str) -> list[dict[str, Any]]:
        """Get all LLM calls for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of LLM call records
        """
        key = f"run:{run_id}:llm_calls"
        records = await self.client.lrange(key, 0, -1)

        return [json.loads(record) for record in records]

    async def get_llm_usage_summary(self, run_id: str) -> dict[str, Any]:
        """Get LLM usage summary for a run.

        Args:
            run_id: Run identifier

        Returns:
            Summary dict with total tokens and cost
        """
        calls = await self.get_llm_calls(run_id)

        if not calls:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "by_model": {},
            }

        total_tokens = sum(c["total_tokens"] for c in calls)
        total_cost = sum(c["cost"] for c in calls)

        # Group by model
        by_model: dict[str, Any] = {}
        for call in calls:
            model = call["model"]
            if model not in by_model:
                by_model[model] = {
                    "calls": 0,
                    "tokens": 0,
                    "cost": 0.0,
                }
            by_model[model]["calls"] += 1
            by_model[model]["tokens"] += call["total_tokens"]
            by_model[model]["cost"] += call["cost"]

        return {
            "total_calls": len(calls),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "by_model": by_model,
        }

    # ------------------------------------------------------------------------
    # CLEANUP OPERATIONS
    # ------------------------------------------------------------------------

    async def delete_run(self, run_id: str) -> int:
        """Delete all data for a run.

        Args:
            run_id: Run identifier

        Returns:
            Number of keys deleted
        """
        pattern = f"run:{run_id}:*"
        keys = await self.client.keys(pattern)

        if keys:
            return await self.client.delete(*keys)
        return 0

    async def get_run_keys(self, run_id: str) -> list[str]:
        """Get all Redis keys for a run.

        Args:
            run_id: Run identifier

        Returns:
            List of Redis keys
        """
        pattern = f"run:{run_id}:*"
        return await self.client.keys(pattern)

    # ------------------------------------------------------------------------
    # BATCH OPERATIONS
    # ------------------------------------------------------------------------

    async def get_all_run_ids(self) -> list[str]:
        """Get all run IDs in Redis.

        Returns:
            List of run IDs
        """
        pattern = "run:*:state"
        keys = await self.client.keys(pattern)

        # Extract run IDs from keys
        run_ids = [key.split(":")[1] for key in keys]
        return run_ids

    async def cleanup_expired_runs(self, max_age_hours: int = 168) -> int:
        """Clean up runs older than max_age.

        Args:
            max_age_hours: Maximum age in hours (default: 7 days)

        Returns:
            Number of runs deleted
        """
        # This is a simple implementation
        # In production, use Redis key expiration or separate metadata
        run_ids = await self.get_all_run_ids()
        deleted = 0

        for run_id in run_ids:
            # Check if run has final result (completed)
            final = await self.get_final_result(run_id)
            if final and final.get("status") in ["completed", "failed"]:
                # Could check timestamp here
                # For now, just delete completed runs
                await self.delete_run(run_id)
                deleted += 1

        return deleted


# ============================================================================
# POSTGRES STORE
# ============================================================================


class PostgresStore:
    """Postgres storage for run history and execution details.

    Stores:
    - Runs (execution metadata)
    - Steps (execution timeline)
    - Artifacts (generated files)
    - LLM calls (token usage, cost tracking)
    """

    def __init__(self, session_factory):
        """Initialize Postgres store.

        Args:
            session_factory: async_sessionmaker instance
        """
        self.session_factory = session_factory

    async def save_run(self, run_data: dict[str, Any]) -> str:
        """Insert or update a run.

        Args:
            run_data: Run data dict with keys: id, actor, request_payload, status, etc.

        Returns:
            Run ID (UUID as string)
        """
        from uuid import UUID
        from chad_memory.models import Run
        from sqlalchemy import select

        async with self.session_factory() as session:
            run_id = run_data.get("id")

            # Check if run exists
            stmt = select(Run).where(Run.id == UUID(run_id) if isinstance(run_id, str) else run_id)
            result = await session.execute(stmt)
            existing_run = result.scalar_one_or_none()

            if existing_run:
                # Update existing run
                for key, value in run_data.items():
                    if hasattr(existing_run, key):
                        setattr(existing_run, key, value)
            else:
                # Create new run
                run = Run(**run_data)
                session.add(run)

            await session.commit()
            return str(run_id)

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Retrieve a run by ID.

        Args:
            run_id: Run UUID

        Returns:
            Run data dict or None if not found
        """
        from uuid import UUID
        from chad_memory.models import Run
        from sqlalchemy import select

        async with self.session_factory() as session:
            stmt = select(Run).where(Run.id == UUID(run_id))
            result = await session.execute(stmt)
            run = result.scalar_one_or_none()

            if not run:
                return None

            return {
                "id": str(run.id),
                "actor": run.actor,
                "request_payload": run.request_payload,
                "status": run.status,
                "autonomy_level": run.autonomy_level,
                "trace_id": run.trace_id,
                "idempotency_key": run.idempotency_key,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "error_message": run.error_message,
            }

    async def list_runs(
        self,
        actor: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict[str, Any]]:
        """List runs for a user.

        Args:
            actor: User/actor identifier
            status: Filter by status (optional)
            limit: Max results
            offset: Pagination offset

        Returns:
            List of run data dicts
        """
        from chad_memory.models import Run
        from sqlalchemy import select, desc

        async with self.session_factory() as session:
            stmt = select(Run).where(Run.actor == actor)

            if status:
                stmt = stmt.where(Run.status == status)

            stmt = stmt.order_by(desc(Run.created_at)).limit(limit).offset(offset)

            result = await session.execute(stmt)
            runs = result.scalars().all()

            return [
                {
                    "id": str(run.id),
                    "actor": run.actor,
                    "request_payload": run.request_payload,
                    "status": run.status,
                    "autonomy_level": run.autonomy_level,
                    "trace_id": run.trace_id,
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                }
                for run in runs
            ]

    async def count_runs(self, actor: str, status: str | None = None) -> int:
        """Count total runs for a user.

        Args:
            actor: User/actor identifier
            status: Filter by status (optional)

        Returns:
            Total count
        """
        from chad_memory.models import Run
        from sqlalchemy import select, func

        async with self.session_factory() as session:
            stmt = select(func.count(Run.id)).where(Run.actor == actor)

            if status:
                stmt = stmt.where(Run.status == status)

            result = await session.execute(stmt)
            return result.scalar() or 0

    async def save_step(self, step_data: dict[str, Any]) -> None:
        """Insert a step record.

        Args:
            step_data: Step data dict
        """
        from chad_memory.models import Step

        async with self.session_factory() as session:
            step = Step(**step_data)
            session.add(step)
            await session.commit()

    async def get_steps(self, run_id: str) -> list[dict[str, Any]]:
        """Get all steps for a run.

        Args:
            run_id: Run UUID

        Returns:
            List of step data dicts in order
        """
        from uuid import UUID
        from chad_memory.models import Step
        from sqlalchemy import select

        async with self.session_factory() as session:
            stmt = select(Step).where(Step.run_id == UUID(run_id)).order_by(Step.step_number)
            result = await session.execute(stmt)
            steps = result.scalars().all()

            return [
                {
                    "id": str(step.id),
                    "run_id": str(step.run_id),
                    "step_number": step.step_number,
                    "node_name": step.node_name,
                    "input_data": step.input_data,
                    "output_data": step.output_data,
                    "llm_call_id": step.llm_call_id,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "status": step.status,
                    "error_message": step.error_message,
                }
                for step in steps
            ]

    async def save_artifact(self, artifact_data: dict[str, Any]) -> None:
        """Insert an artifact record.

        Args:
            artifact_data: Artifact data dict
        """
        from chad_memory.models import Artifact

        async with self.session_factory() as session:
            artifact = Artifact(**artifact_data)
            session.add(artifact)
            await session.commit()

    async def get_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        """Get all artifacts for a run.

        Args:
            run_id: Run UUID

        Returns:
            List of artifact data dicts
        """
        from uuid import UUID
        from chad_memory.models import Artifact
        from sqlalchemy import select

        async with self.session_factory() as session:
            stmt = select(Artifact).where(Artifact.run_id == UUID(run_id)).order_by(Artifact.created_at)
            result = await session.execute(stmt)
            artifacts = result.scalars().all()

            return [
                {
                    "id": str(artifact.id),
                    "run_id": str(artifact.run_id),
                    "artifact_type": artifact.artifact_type,
                    "url": artifact.url,
                    "metadata_json": artifact.metadata_json,
                    "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
                }
                for artifact in artifacts
            ]

    async def save_llm_call(self, llm_call_data: dict[str, Any]) -> None:
        """Insert an LLM call record.

        Args:
            llm_call_data: LLM call data dict
        """
        from chad_memory.models import LLMCall

        async with self.session_factory() as session:
            llm_call = LLMCall(**llm_call_data)
            session.add(llm_call)
            await session.commit()

    async def get_run_stats(self, run_id: str) -> dict[str, Any]:
        """Get aggregate stats for a run.

        Args:
            run_id: Run UUID

        Returns:
            Stats dict with token counts, cost, duration, etc.
        """
        from uuid import UUID
        from datetime import datetime
        from chad_memory.models import Run, LLMCall, Step
        from sqlalchemy import select, func

        async with self.session_factory() as session:
            # Get run
            run_stmt = select(Run).where(Run.id == UUID(run_id))
            run_result = await session.execute(run_stmt)
            run = run_result.scalar_one_or_none()

            if not run:
                return {}

            # Aggregate LLM call stats
            llm_stmt = select(
                func.count(LLMCall.id).label("total_calls"),
                func.sum(LLMCall.total_tokens).label("total_tokens"),
                func.sum(LLMCall.prompt_tokens).label("prompt_tokens"),
                func.sum(LLMCall.completion_tokens).label("completion_tokens"),
            ).where(LLMCall.run_id == UUID(run_id))

            llm_result = await session.execute(llm_stmt)
            llm_stats = llm_result.one()

            # Count steps
            step_stmt = select(func.count(Step.id)).where(Step.run_id == UUID(run_id))
            step_result = await session.execute(step_stmt)
            step_count = step_result.scalar() or 0

            # Calculate duration
            duration_seconds = None
            if run.created_at and run.completed_at:
                duration_seconds = (run.completed_at - run.created_at).total_seconds()

            return {
                "run_id": str(run_id),
                "status": run.status,
                "step_count": step_count,
                "llm_calls": llm_stats.total_calls or 0,
                "total_tokens": llm_stats.total_tokens or 0,
                "prompt_tokens": llm_stats.prompt_tokens or 0,
                "completion_tokens": llm_stats.completion_tokens or 0,
                "duration_seconds": duration_seconds,
            }


# ============================================================================
# PGVECTOR STORE
# ============================================================================


class PgVectorStore:
    """Postgres + pgvector for semantic search.

    Stores:
    - Text embeddings with metadata
    - Supports cosine similarity search
    """

    def __init__(self, session_factory):
        """Initialize PgVector store.

        Args:
            session_factory: async_sessionmaker instance
        """
        self.session_factory = session_factory

    async def add_embedding(
        self,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any],
        source_type: str,
        source_id: str,
        embedding_id: str | None = None
    ) -> str:
        """Insert an embedding.

        Args:
            content: Original text content
            embedding: Vector embedding (list of floats)
            metadata: Additional metadata (JSON)
            source_type: Source type (e.g., "run", "artifact")
            source_id: Source UUID
            embedding_id: Optional UUID for the embedding

        Returns:
            Embedding ID (UUID as string)
        """
        from uuid import UUID, uuid4
        from sqlalchemy import text

        async with self.session_factory() as session:
            embedding_uuid = UUID(embedding_id) if embedding_id else uuid4()

            # Insert with raw SQL for vector type
            stmt = text("""
                INSERT INTO embeddings (id, content, embedding, metadata_json, source_type, source_id)
                VALUES (:id, :content, :embedding::vector, :metadata::jsonb, :source_type, :source_id)
            """)

            await session.execute(
                stmt,
                {
                    "id": embedding_uuid,
                    "content": content,
                    "embedding": str(embedding),  # pgvector accepts array format
                    "metadata": json.dumps(metadata),
                    "source_type": source_type,
                    "source_id": UUID(source_id),
                }
            )
            await session.commit()
            return str(embedding_uuid)

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        metadata_filter: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Search for similar embeddings using cosine similarity.

        Args:
            query_embedding: Query vector
            limit: Max results
            metadata_filter: Optional metadata filters

        Returns:
            List of matching results with similarity scores
        """
        from sqlalchemy import text

        async with self.session_factory() as session:
            # Cosine similarity search using pgvector operator
            stmt = text("""
                SELECT
                    id,
                    content,
                    metadata_json,
                    source_type,
                    source_id,
                    1 - (embedding <=> :query_embedding::vector) as similarity
                FROM embeddings
                ORDER BY embedding <=> :query_embedding::vector
                LIMIT :limit
            """)

            result = await session.execute(
                stmt,
                {
                    "query_embedding": str(query_embedding),
                    "limit": limit,
                }
            )

            rows = result.fetchall()

            return [
                {
                    "id": str(row[0]),
                    "content": row[1],
                    "metadata": row[2],
                    "source_type": row[3],
                    "source_id": str(row[4]),
                    "similarity": float(row[5]),
                }
                for row in rows
            ]

    async def delete_by_source(self, source_id: str) -> int:
        """Delete all embeddings for a source.

        Args:
            source_id: Source UUID

        Returns:
            Number of embeddings deleted
        """
        from uuid import UUID
        from chad_memory.models import Embedding
        from sqlalchemy import delete

        async with self.session_factory() as session:
            stmt = delete(Embedding).where(Embedding.source_id == UUID(source_id))
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================


async def create_redis_store(redis_url: str) -> RedisStore:
    """Create and connect Redis store.

    Args:
        redis_url: Redis connection URL

    Returns:
        Connected RedisStore
    """
    store = RedisStore(redis_url)
    await store.connect()
    return store


async def create_postgres_store(database_url: str = None) -> PostgresStore:
    """Create Postgres store.

    Args:
        database_url: Database connection URL

    Returns:
        PostgresStore instance
    """
    from chad_memory.database import get_session_factory

    session_factory = get_session_factory(database_url)
    return PostgresStore(session_factory)


async def create_pg_vector_store(database_url: str = None) -> PgVectorStore:
    """Create Postgres vector store.

    Args:
        database_url: Database connection URL

    Returns:
        PgVectorStore instance
    """
    from chad_memory.database import get_session_factory

    session_factory = get_session_factory(database_url)
    return PgVectorStore(session_factory)
