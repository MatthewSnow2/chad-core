# Chad-Core Database Layer

Complete implementation of SQLAlchemy async models, Alembic migrations, and Postgres/pgvector stores for Chad-Core.

## Overview

This database layer provides:

- **Async SQLAlchemy Models**: Full ORM models for runs, steps, artifacts, LLM calls, and embeddings
- **Alembic Migrations**: Database schema versioning and migration management
- **PostgresStore**: CRUD operations for run history and execution details
- **PgVectorStore**: Vector embeddings storage with semantic search using pgvector
- **FastAPI Integration**: Dependency injection for database sessions and stores
- **Connection Pooling**: Async connection pool management with health checks

## Architecture

### Database Schema

```
runs (execution metadata)
├── id (UUID, primary key)
├── actor (text, indexed)
├── request_payload (JSONB)
├── status (text, indexed)
├── autonomy_level (text)
├── trace_id (text, unique, indexed)
├── idempotency_key (text, unique, indexed)
├── created_at (timestamp with timezone, indexed)
├── completed_at (timestamp with timezone)
└── error_message (text)

steps (execution timeline)
├── id (UUID, primary key)
├── run_id (UUID, foreign key → runs.id, indexed)
├── step_number (integer)
├── node_name (text)
├── input_data (JSONB)
├── output_data (JSONB)
├── llm_call_id (text)
├── started_at (timestamp with timezone)
├── completed_at (timestamp with timezone)
├── status (text, indexed)
└── error_message (text)

artifacts (generated files)
├── id (UUID, primary key)
├── run_id (UUID, foreign key → runs.id, indexed)
├── artifact_type (text, indexed)
├── url (text - Supabase Storage URL)
├── metadata_json (JSONB)
└── created_at (timestamp with timezone)

llm_calls (LLM usage tracking)
├── id (UUID, primary key)
├── run_id (UUID, foreign key → runs.id, indexed)
├── step_id (UUID, foreign key → steps.id, indexed)
├── model (text)
├── provider (text)
├── prompt_tokens (integer)
├── completion_tokens (integer)
├── total_tokens (integer)
├── cost_usd (text)
├── latency_ms (integer)
└── created_at (timestamp with timezone)

embeddings (vector search)
├── id (UUID, primary key)
├── content (text)
├── embedding (vector(1536))  ← pgvector type
├── metadata_json (JSONB)
├── source_type (text, indexed)
├── source_id (UUID, indexed)
└── created_at (timestamp with timezone)
└── IVFFLAT index on embedding (cosine distance)
```

## Setup

### 1. Install Dependencies

All dependencies are already in `pyproject.toml`:

```bash
cd /workspace/chad-core-database
pip install -e .
```

Key packages:
- `sqlalchemy>=2.0.25` - Async ORM
- `asyncpg>=0.29.0` - Async Postgres driver
- `alembic>=1.13.1` - Migration tool
- `pgvector>=0.4.0` - Vector extension support

### 2. Configure Database URL

Set environment variable or update `.env`:

```bash
# For local development
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/chad_core

# For production (Supabase, etc.)
DATABASE_URL=postgresql+asyncpg://user:password@db.supabase.co:5432/postgres
```

**Important**: URL must use `postgresql+asyncpg://` driver (not `psycopg2`).

### 3. Create Database

```bash
# Using psql
psql -U postgres -c "CREATE DATABASE chad_core;"

# Enable pgvector extension
psql -U postgres -d chad_core -c "CREATE EXTENSION vector;"
```

### 4. Run Migrations

```bash
cd /workspace/chad-core-database

# Upgrade to latest schema
alembic upgrade head

# Check current version
alembic current

# Downgrade if needed
alembic downgrade -1
```

## Usage

### PostgresStore (Run History)

```python
from chad_memory.stores import PostgresStore
from chad_memory.database import get_session_factory

# Initialize store
session_factory = get_session_factory()
store = PostgresStore(session_factory)

# Save a run
from uuid import uuid4

run_id = uuid4()
await store.save_run({
    "id": run_id,
    "actor": "user@example.com",
    "request_payload": {"goal": "analyze data"},
    "status": "running",
    "trace_id": f"trace-{run_id}",
})

# Get run
run = await store.get_run(str(run_id))

# List runs for user
runs = await store.list_runs(
    actor="user@example.com",
    status="completed",
    limit=50,
    offset=0
)

# Save steps
await store.save_step({
    "id": uuid4(),
    "run_id": run_id,
    "step_number": 1,
    "node_name": "plan",
    "input_data": {"task": "planning"},
    "output_data": {"plan": ["step1", "step2"]},
    "status": "completed",
})

# Get run statistics
stats = await store.get_run_stats(str(run_id))
# Returns: {
#   "run_id": "...",
#   "step_count": 3,
#   "llm_calls": 2,
#   "total_tokens": 1500,
#   "duration_seconds": 45.2
# }
```

### PgVectorStore (Semantic Search)

```python
from chad_memory.stores import PgVectorStore
from chad_memory.database import get_session_factory

# Initialize store
session_factory = get_session_factory()
vector_store = PgVectorStore(session_factory)

# Add embedding
embedding = [0.1, 0.2, ..., 0.8]  # 1536-dimensional vector
await vector_store.add_embedding(
    content="User requested data analysis on sales Q4",
    embedding=embedding,
    metadata={"category": "request", "quarter": "Q4"},
    source_type="run",
    source_id=str(run_id)
)

# Search similar content
query_embedding = [0.15, 0.25, ..., 0.85]
results = await vector_store.search(
    query_embedding=query_embedding,
    limit=5
)
# Returns: [
#   {
#     "id": "...",
#     "content": "User requested...",
#     "metadata": {"category": "request"},
#     "similarity": 0.95
#   },
#   ...
# ]

# Delete embeddings by source
deleted = await vector_store.delete_by_source(str(run_id))
```

### FastAPI Integration

```python
from fastapi import Depends
from apps.core_api.deps import get_postgres_store, get_vector_store

@app.get("/runs")
async def list_runs(
    actor: str,
    store = Depends(get_postgres_store)
):
    runs = await store.list_runs(actor=actor)
    return {"runs": runs}

@app.post("/search")
async def search_similar(
    query_embedding: list[float],
    store = Depends(get_vector_store)
):
    results = await store.search(query_embedding)
    return {"results": results}
```

## API Endpoints

The `/runs` router provides:

- `GET /runs` - List runs for authenticated actor
  - Query params: `status`, `limit`, `offset`
- `GET /runs/{run_id}` - Get run details with artifacts
- `GET /runs/{run_id}/steps` - Get step timeline
- `GET /runs/{run_id}/artifacts` - Get run artifacts
- `GET /runs/{run_id}/stats` - Get aggregate statistics

## Testing

Run the test suite:

```bash
# Run all tests (requires running Postgres)
pytest tests/test_memory.py -v

# Run only integration tests
pytest tests/test_memory.py -v -m integration

# Skip integration tests (unit tests only)
pytest tests/test_memory.py -v -m "not integration"

# With coverage
pytest tests/test_memory.py -v --cov=chad_memory --cov-report=html
```

Test coverage includes:
- PostgresStore CRUD operations
- Run creation, update, retrieval
- Step and artifact management
- LLM call tracking
- Run statistics aggregation
- PgVectorStore embedding operations
- Vector similarity search
- Full workflow integration tests

## Migration Management

### Create New Migration

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "add new field to runs table"

# Create empty migration
alembic revision -m "custom migration"
```

### Migration Files

Located in `/workspace/chad-core-database/alembic/versions/`:

- `001_create_initial_schema.py` - Initial schema with all tables

### Migration Best Practices

1. **Always test migrations** on a dev database before production
2. **Backup production data** before running migrations
3. **Review autogenerated migrations** - they may miss custom indexes or constraints
4. **Use transactions** - migrations run in transactions by default
5. **Document breaking changes** in migration docstrings

## Connection Pool Configuration

Configure in `chad_config/settings.py`:

```python
# Connection pool settings (defaults shown)
DB_POOL_SIZE = 20           # Max connections in pool
DB_MAX_OVERFLOW = 10        # Additional connections beyond pool_size
DB_POOL_TIMEOUT = 30        # Seconds to wait for connection
DB_POOL_RECYCLE = 3600      # Recycle connections after 1 hour
```

## Performance Considerations

### Indexes

All critical columns are indexed:
- `runs.actor` - For user queries
- `runs.created_at` - For time-range queries
- `runs.status` - For status filtering
- `steps.run_id` - For step retrieval
- `llm_calls.run_id`, `llm_calls.step_id` - For stats aggregation
- `embeddings.embedding` - IVFFLAT index for vector search

### Vector Index Tuning

For production, consider HNSW index (better for large datasets):

```sql
-- Replace IVFFLAT with HNSW
DROP INDEX ix_embeddings_embedding_ivfflat;

CREATE INDEX ix_embeddings_embedding_hnsw
ON embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

HNSW parameters:
- `m = 16` - Number of connections per node (default: 16)
- `ef_construction = 64` - Search scope during index build (default: 64)

### Query Optimization

- Use pagination (`limit`, `offset`) for large result sets
- Filter by indexed columns first (`actor`, `status`, `created_at`)
- Use `get_run_stats()` for aggregations instead of manual queries
- Batch operations when possible (e.g., bulk insert steps)

## Troubleshooting

### Connection Errors

```python
# Test database connection
from chad_memory.database import check_db_connection

is_healthy = await check_db_connection()
```

### Migration Issues

```bash
# Check current schema version
alembic current

# View migration history
alembic history

# Reset to specific version
alembic downgrade <revision>
alembic upgrade <revision>
```

### pgvector Not Available

```sql
-- Check extension
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Install if missing
CREATE EXTENSION vector;
```

## Schema Decisions

### Design Choices

1. **UUID Primary Keys** - Distributed-friendly, no collision risk
2. **JSONB for Flexible Data** - Request payloads, metadata can evolve
3. **Text for Status** - Simple, readable, easy to filter
4. **Timestamps with Timezone** - UTC storage, timezone-aware
5. **Cascade Deletes** - Clean up child records automatically
6. **No Binary Artifacts** - URLs to Supabase Storage instead
7. **String Cost Fields** - Avoid float precision issues

### Trade-offs

- **Flexibility vs. Performance**: JSONB allows schema evolution but slower than typed columns
- **IVFFLAT vs. HNSW**: IVFFLAT faster for small datasets, HNSW better for large
- **Text Status vs. Enum**: Text is flexible but no DB-level constraint

## Production Deployment

### Pre-deployment Checklist

- [ ] Backup production database
- [ ] Test migrations on staging
- [ ] Review connection pool settings
- [ ] Monitor query performance (use `EXPLAIN ANALYZE`)
- [ ] Set up database monitoring (connection count, query times)
- [ ] Enable SSL for production connections
- [ ] Rotate database credentials regularly
- [ ] Set up automated backups

### SSL Connection

```bash
# For Supabase/production
DATABASE_URL=postgresql+asyncpg://user:pass@db.supabase.co:5432/postgres?ssl=require
```

### Monitoring

Key metrics to track:
- Connection pool utilization
- Query latency (p50, p95, p99)
- Slow queries (> 1s)
- Table sizes and growth rate
- Index usage

## Files Modified/Created

### New Files
- `/workspace/chad-core-database/chad_memory/database.py` - Session factory and engine
- `/workspace/chad-core-database/alembic/` - Migration directory
- `/workspace/chad-core-database/alembic/versions/001_create_initial_schema.py` - Initial migration
- `/workspace/chad-core-database/DATABASE_README.md` - This file

### Modified Files
- `/workspace/chad-core-database/chad_memory/models.py` - Added Step, LLMCall, Embedding models
- `/workspace/chad-core-database/chad_memory/stores.py` - Implemented PostgresStore and PgVectorStore
- `/workspace/chad-core-database/apps/core_api/deps.py` - Added database dependencies
- `/workspace/chad-core-database/apps/core_api/main.py` - Added database initialization
- `/workspace/chad-core-database/apps/core_api/routers/runs.py` - Implemented all endpoints
- `/workspace/chad-core-database/tests/test_memory.py` - Comprehensive test suite

## Next Steps

1. **Run migrations** when Postgres is available
2. **Test API endpoints** with real database
3. **Integrate with LangGraph agent** to persist run state
4. **Add LLM call tracking** in agent execution
5. **Implement embedding generation** for semantic search
6. **Set up monitoring** for production

## Support

For issues or questions:
- Check migration logs: `alembic history`
- Enable SQL logging: Set `echo=True` in `database.py`
- Review test failures for debugging hints
- Consult Alembic docs: https://alembic.sqlalchemy.org/
- pgvector docs: https://github.com/pgvector/pgvector
