"""Memory Store Tests.

Comprehensive tests for PostgresStore and PgVectorStore.

Note: These tests require a running Postgres instance with pgvector extension.
Set DATABASE_URL environment variable or use default local connection.
"""

import pytest
from uuid import uuid4
from datetime import datetime

from chad_memory.stores import PostgresStore, PgVectorStore, RedisStore
from chad_memory.database import get_session_factory


# ============================================================================
# REDIS STORE TESTS (existing)
# ============================================================================


@pytest.mark.asyncio
async def test_redis_store_interface():
    """Test RedisStore interface exists."""
    store = RedisStore(redis_url="redis://localhost:6379/0")
    # Interface test - no connection needed
    assert hasattr(store, "connect")
    assert hasattr(store, "save_state")
    assert hasattr(store, "get_state")


# ============================================================================
# POSTGRES STORE TESTS
# ============================================================================


@pytest.fixture
def session_factory():
    """Provide async session factory for tests."""
    return get_session_factory()


@pytest.fixture
async def postgres_store(session_factory):
    """Provide PostgresStore instance."""
    return PostgresStore(session_factory)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_store_save_and_get_run(postgres_store):
    """Test saving and retrieving a run."""
    run_id = uuid4()
    run_data = {
        "id": run_id,
        "actor": "test_user",
        "request_payload": {"goal": "test goal"},
        "status": "pending",
        "autonomy_level": "L1",
        "trace_id": f"trace-{run_id}",
        "idempotency_key": f"idem-{run_id}",
    }

    # Save run
    saved_id = await postgres_store.save_run(run_data)
    assert saved_id == str(run_id)

    # Retrieve run
    retrieved = await postgres_store.get_run(str(run_id))
    assert retrieved is not None
    assert retrieved["id"] == str(run_id)
    assert retrieved["actor"] == "test_user"
    assert retrieved["status"] == "pending"
    assert retrieved["request_payload"]["goal"] == "test goal"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_store_update_run(postgres_store):
    """Test updating an existing run."""
    run_id = uuid4()
    run_data = {
        "id": run_id,
        "actor": "test_user",
        "request_payload": {"goal": "test goal"},
        "status": "pending",
        "trace_id": f"trace-{run_id}",
    }

    # Create run
    await postgres_store.save_run(run_data)

    # Update run
    run_data["status"] = "completed"
    run_data["completed_at"] = datetime.utcnow()
    await postgres_store.save_run(run_data)

    # Verify update
    retrieved = await postgres_store.get_run(str(run_id))
    assert retrieved["status"] == "completed"
    assert retrieved["completed_at"] is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_store_list_runs(postgres_store):
    """Test listing runs for a user."""
    actor = f"test_actor_{uuid4()}"

    # Create multiple runs
    run_ids = []
    for i in range(3):
        run_id = uuid4()
        run_ids.append(run_id)
        await postgres_store.save_run({
            "id": run_id,
            "actor": actor,
            "request_payload": {"goal": f"goal {i}"},
            "status": "completed" if i % 2 == 0 else "pending",
            "trace_id": f"trace-{run_id}",
        })

    # List all runs
    runs = await postgres_store.list_runs(actor=actor, limit=10)
    assert len(runs) == 3

    # Filter by status
    completed_runs = await postgres_store.list_runs(actor=actor, status="completed")
    assert len(completed_runs) == 2

    # Test pagination
    page_1 = await postgres_store.list_runs(actor=actor, limit=2, offset=0)
    assert len(page_1) == 2

    page_2 = await postgres_store.list_runs(actor=actor, limit=2, offset=2)
    assert len(page_2) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_store_count_runs(postgres_store):
    """Test counting runs."""
    actor = f"test_actor_{uuid4()}"

    # Create runs
    for i in range(5):
        run_id = uuid4()
        await postgres_store.save_run({
            "id": run_id,
            "actor": actor,
            "request_payload": {"goal": f"goal {i}"},
            "status": "completed" if i < 3 else "pending",
            "trace_id": f"trace-{run_id}",
        })

    # Count all
    total = await postgres_store.count_runs(actor=actor)
    assert total == 5

    # Count by status
    completed_count = await postgres_store.count_runs(actor=actor, status="completed")
    assert completed_count == 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_store_save_and_get_steps(postgres_store):
    """Test saving and retrieving steps."""
    run_id = uuid4()

    # Create run first
    await postgres_store.save_run({
        "id": run_id,
        "actor": "test_user",
        "request_payload": {"goal": "test"},
        "status": "running",
        "trace_id": f"trace-{run_id}",
    })

    # Create steps
    step_ids = []
    for i in range(3):
        step_id = uuid4()
        step_ids.append(step_id)
        await postgres_store.save_step({
            "id": step_id,
            "run_id": run_id,
            "step_number": i + 1,
            "node_name": f"step_{i}",
            "input_data": {"input": f"data {i}"},
            "output_data": {"output": f"result {i}"},
            "status": "completed",
        })

    # Retrieve steps
    steps = await postgres_store.get_steps(str(run_id))
    assert len(steps) == 3
    assert steps[0]["step_number"] == 1
    assert steps[1]["step_number"] == 2
    assert steps[2]["step_number"] == 3
    assert steps[0]["node_name"] == "step_0"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_store_save_and_get_artifacts(postgres_store):
    """Test saving and retrieving artifacts."""
    run_id = uuid4()

    # Create run
    await postgres_store.save_run({
        "id": run_id,
        "actor": "test_user",
        "request_payload": {"goal": "test"},
        "status": "running",
        "trace_id": f"trace-{run_id}",
    })

    # Create artifacts
    for i in range(2):
        artifact_id = uuid4()
        await postgres_store.save_artifact({
            "id": artifact_id,
            "run_id": run_id,
            "artifact_type": "file",
            "url": f"https://storage.example.com/artifact_{i}.txt",
            "metadata_json": {"name": f"artifact_{i}"},
        })

    # Retrieve artifacts
    artifacts = await postgres_store.get_artifacts(str(run_id))
    assert len(artifacts) == 2
    assert artifacts[0]["artifact_type"] == "file"
    assert "artifact_0" in artifacts[0]["url"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_store_save_llm_call(postgres_store):
    """Test saving LLM call records."""
    run_id = uuid4()

    # Create run
    await postgres_store.save_run({
        "id": run_id,
        "actor": "test_user",
        "request_payload": {"goal": "test"},
        "status": "running",
        "trace_id": f"trace-{run_id}",
    })

    # Save LLM call
    llm_call_id = uuid4()
    await postgres_store.save_llm_call({
        "id": llm_call_id,
        "run_id": run_id,
        "model": "claude-3-5-sonnet",
        "provider": "anthropic",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "cost_usd": "0.005",
        "latency_ms": 1200,
    })

    # Verify via stats
    stats = await postgres_store.get_run_stats(str(run_id))
    assert stats["llm_calls"] == 1
    assert stats["total_tokens"] == 150


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_store_get_run_stats(postgres_store):
    """Test getting run statistics."""
    run_id = uuid4()

    # Create run
    created_at = datetime.utcnow()
    await postgres_store.save_run({
        "id": run_id,
        "actor": "test_user",
        "request_payload": {"goal": "test"},
        "status": "running",
        "trace_id": f"trace-{run_id}",
        "created_at": created_at,
    })

    # Add steps
    for i in range(3):
        step_id = uuid4()
        await postgres_store.save_step({
            "id": step_id,
            "run_id": run_id,
            "step_number": i + 1,
            "node_name": f"step_{i}",
            "status": "completed",
        })

    # Add LLM calls
    for i in range(2):
        llm_call_id = uuid4()
        await postgres_store.save_llm_call({
            "id": llm_call_id,
            "run_id": run_id,
            "model": "gpt-4o",
            "provider": "openai",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        })

    # Get stats
    stats = await postgres_store.get_run_stats(str(run_id))
    assert stats["run_id"] == str(run_id)
    assert stats["step_count"] == 3
    assert stats["llm_calls"] == 2
    assert stats["total_tokens"] == 300
    assert stats["prompt_tokens"] == 200
    assert stats["completion_tokens"] == 100


# ============================================================================
# PGVECTOR STORE TESTS
# ============================================================================


@pytest.fixture
async def vector_store(session_factory):
    """Provide PgVectorStore instance."""
    return PgVectorStore(session_factory)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pgvector_store_add_embedding(vector_store):
    """Test adding an embedding."""
    source_id = uuid4()
    embedding = [0.1] * 1536  # OpenAI embedding dimension

    embedding_id = await vector_store.add_embedding(
        content="This is test content",
        embedding=embedding,
        metadata={"type": "test"},
        source_type="run",
        source_id=str(source_id),
    )

    assert embedding_id is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pgvector_store_search(vector_store):
    """Test vector similarity search."""
    # Add test embeddings
    source_id = uuid4()

    # Add similar embeddings
    embedding_1 = [0.1] * 1536
    embedding_2 = [0.15] * 1536  # Similar to embedding_1
    embedding_3 = [0.9] * 1536  # Different

    await vector_store.add_embedding(
        content="Content 1",
        embedding=embedding_1,
        metadata={"category": "A"},
        source_type="run",
        source_id=str(source_id),
    )

    await vector_store.add_embedding(
        content="Content 2",
        embedding=embedding_2,
        metadata={"category": "A"},
        source_type="run",
        source_id=str(source_id),
    )

    await vector_store.add_embedding(
        content="Content 3",
        embedding=embedding_3,
        metadata={"category": "B"},
        source_type="run",
        source_id=str(source_id),
    )

    # Search with query similar to embedding_1
    query_embedding = [0.12] * 1536
    results = await vector_store.search(query_embedding, limit=2)

    assert len(results) <= 2
    assert all("similarity" in r for r in results)
    assert all("content" in r for r in results)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pgvector_store_delete_by_source(vector_store):
    """Test deleting embeddings by source."""
    source_id = uuid4()
    embedding = [0.1] * 1536

    # Add embeddings
    for i in range(3):
        await vector_store.add_embedding(
            content=f"Content {i}",
            embedding=embedding,
            metadata={"index": i},
            source_type="run",
            source_id=str(source_id),
        )

    # Delete by source
    deleted_count = await vector_store.delete_by_source(str(source_id))
    assert deleted_count == 3

    # Verify deletion
    results = await vector_store.search(embedding, limit=10)
    source_results = [r for r in results if r["source_id"] == str(source_id)]
    assert len(source_results) == 0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_run_workflow(postgres_store):
    """Test complete run workflow: create → steps → artifacts → retrieve."""
    run_id = uuid4()

    # 1. Create run
    await postgres_store.save_run({
        "id": run_id,
        "actor": "integration_test_user",
        "request_payload": {"goal": "complete workflow test"},
        "status": "running",
        "trace_id": f"trace-{run_id}",
    })

    # 2. Add steps
    for i in range(2):
        step_id = uuid4()
        await postgres_store.save_step({
            "id": step_id,
            "run_id": run_id,
            "step_number": i + 1,
            "node_name": f"node_{i}",
            "input_data": {"step": i},
            "output_data": {"result": i * 2},
            "status": "completed",
        })

    # 3. Add artifacts
    artifact_id = uuid4()
    await postgres_store.save_artifact({
        "id": artifact_id,
        "run_id": run_id,
        "artifact_type": "output",
        "url": "https://storage.example.com/output.txt",
    })

    # 4. Add LLM call
    llm_call_id = uuid4()
    await postgres_store.save_llm_call({
        "id": llm_call_id,
        "run_id": run_id,
        "model": "claude-3-5-sonnet",
        "provider": "anthropic",
        "total_tokens": 200,
    })

    # 5. Complete run
    await postgres_store.save_run({
        "id": run_id,
        "status": "completed",
        "completed_at": datetime.utcnow(),
    })

    # 6. Retrieve all data
    run = await postgres_store.get_run(str(run_id))
    steps = await postgres_store.get_steps(str(run_id))
    artifacts = await postgres_store.get_artifacts(str(run_id))
    stats = await postgres_store.get_run_stats(str(run_id))

    # 7. Verify
    assert run["status"] == "completed"
    assert len(steps) == 2
    assert len(artifacts) == 1
    assert stats["step_count"] == 2
    assert stats["llm_calls"] == 1
    assert stats["total_tokens"] == 200
