"""SQLAlchemy Async Models.

Driver: asyncpg ONLY (no psycopg2)
Artifacts: URL field, NO BYTEA

Deliverable #5: SQLAlchemy models with asyncpg ✅
"""

from sqlalchemy import Column, ForeignKey, String, Text, Integer, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Run(Base):
    """Top-level execution run."""

    __tablename__ = "runs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    actor = Column(Text, nullable=False, index=True)
    request_payload = Column(JSONB, nullable=False)
    status = Column(Text, nullable=False, index=True)
    autonomy_level = Column(Text)
    trace_id = Column(Text, unique=True, nullable=False, index=True)
    idempotency_key = Column(Text, unique=True, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    completed_at = Column(TIMESTAMP(timezone=True))
    error_message = Column(Text)


class Artifact(Base):
    """Artifact metadata (binary in Supabase Storage)."""

    __tablename__ = "artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type = Column(Text, nullable=False, index=True)
    url = Column(Text, nullable=False)  # Supabase Storage URL
    metadata_json = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

class Step(Base):
    """Execution step within a run."""

    __tablename__ = "steps"

    id = Column(UUID(as_uuid=True), primary_key=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    node_name = Column(Text, nullable=False)  # e.g., "plan", "execute", "reflect"
    input_data = Column(JSONB)
    output_data = Column(JSONB)
    llm_call_id = Column(Text)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    completed_at = Column(TIMESTAMP(timezone=True))
    status = Column(Text, nullable=False, index=True)  # running, completed, failed
    error_message = Column(Text)


class LLMCall(Base):
    """LLM API call tracking."""

    __tablename__ = "llm_calls"

    id = Column(UUID(as_uuid=True), primary_key=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(UUID(as_uuid=True), ForeignKey("steps.id", ondelete="SET NULL"), index=True)
    model = Column(Text, nullable=False)  # e.g., "claude-3-5-sonnet", "gpt-4o"
    provider = Column(Text, nullable=False)  # e.g., "anthropic", "openai"
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Text)  # Stored as string to avoid float precision issues
    latency_ms = Column(Integer)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Embedding(Base):
    """Vector embeddings for semantic search."""

    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True)
    content = Column(Text, nullable=False)
    # Note: Vector type will be added by pgvector migration
    # embedding = Column(Vector(1536))  # Added in migration
    metadata_json = Column(JSONB)
    source_type = Column(Text, nullable=False, index=True)  # e.g., "run", "artifact", "step"
    source_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
