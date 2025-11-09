"""create initial schema with runs steps artifacts llm_calls and embeddings tables

Revision ID: 001
Revises:
Create Date: 2025-11-08 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create runs table
    op.create_table(
        'runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor', sa.Text(), nullable=False),
        sa.Column('request_payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('autonomy_level', sa.Text(), nullable=True),
        sa.Column('trace_id', sa.Text(), nullable=False),
        sa.Column('idempotency_key', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trace_id'),
        sa.UniqueConstraint('idempotency_key')
    )
    op.create_index(op.f('ix_runs_actor'), 'runs', ['actor'], unique=False)
    op.create_index(op.f('ix_runs_created_at'), 'runs', ['created_at'], unique=False)
    op.create_index(op.f('ix_runs_status'), 'runs', ['status'], unique=False)

    # Create artifacts table
    op.create_table(
        'artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('artifact_type', sa.Text(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_artifacts_artifact_type'), 'artifacts', ['artifact_type'], unique=False)
    op.create_index(op.f('ix_artifacts_run_id'), 'artifacts', ['run_id'], unique=False)

    # Create steps table
    op.create_table(
        'steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('node_name', sa.Text(), nullable=False),
        sa.Column('input_data', postgresql.JSONB(), nullable=True),
        sa.Column('output_data', postgresql.JSONB(), nullable=True),
        sa.Column('llm_call_id', sa.Text(), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_steps_run_id'), 'steps', ['run_id'], unique=False)
    op.create_index(op.f('ix_steps_status'), 'steps', ['status'], unique=False)

    # Create llm_calls table
    op.create_table(
        'llm_calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('model', sa.Text(), nullable=False),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['steps.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_llm_calls_run_id'), 'llm_calls', ['run_id'], unique=False)
    op.create_index(op.f('ix_llm_calls_step_id'), 'llm_calls', ['step_id'], unique=False)

    # Create embeddings table with vector column
    op.create_table(
        'embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(), nullable=True),
        sa.Column('source_type', sa.Text(), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    # Add vector column with raw SQL (pgvector type)
    op.execute("ALTER TABLE embeddings ADD COLUMN embedding vector(1536)")

    op.create_index(op.f('ix_embeddings_source_id'), 'embeddings', ['source_id'], unique=False)
    op.create_index(op.f('ix_embeddings_source_type'), 'embeddings', ['source_type'], unique=False)

    # Create vector index for similarity search (IVFFLAT for development, HNSW for production)
    # Using IVFFLAT with 100 lists (good for datasets with 10k-1M rows)
    op.execute("""
        CREATE INDEX ix_embeddings_embedding_ivfflat
        ON embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop indexes
    op.drop_index('ix_embeddings_embedding_ivfflat', table_name='embeddings')
    op.drop_index(op.f('ix_embeddings_source_type'), table_name='embeddings')
    op.drop_index(op.f('ix_embeddings_source_id'), table_name='embeddings')

    op.drop_index(op.f('ix_llm_calls_step_id'), table_name='llm_calls')
    op.drop_index(op.f('ix_llm_calls_run_id'), table_name='llm_calls')

    op.drop_index(op.f('ix_steps_status'), table_name='steps')
    op.drop_index(op.f('ix_steps_run_id'), table_name='steps')

    op.drop_index(op.f('ix_artifacts_run_id'), table_name='artifacts')
    op.drop_index(op.f('ix_artifacts_artifact_type'), table_name='artifacts')

    op.drop_index(op.f('ix_runs_status'), table_name='runs')
    op.drop_index(op.f('ix_runs_created_at'), table_name='runs')
    op.drop_index(op.f('ix_runs_actor'), table_name='runs')

    # Drop tables
    op.drop_table('embeddings')
    op.drop_table('llm_calls')
    op.drop_table('steps')
    op.drop_table('artifacts')
    op.drop_table('runs')

    # Drop extension
    op.execute("DROP EXTENSION IF EXISTS vector")
