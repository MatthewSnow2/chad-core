"""
Application Settings (Pydantic Settings).

Loads configuration from environment variables (.env file or system env).

Production Secrets Management:
- Local: .env file (gitignored)
- Production: Doppler CLI or 1Password CLI
  - Doppler: `doppler run -- uvicorn apps.core_api.main:app`
  - 1Password: `op run --env-file=".env.prod" -- uvicorn apps.core_api.main:app`

Agent: api-scaffolding/backend-architect
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings documented in .env.example.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars
    )

    # ========================================================================
    # DATABASE (Supabase Postgres + pgvector)
    # ========================================================================
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/chad_core",
        description="Async Postgres connection string (asyncpg ONLY, no psycopg2)",
    )

    EMBED_INDEX_TYPE: str = Field(
        default="IVF",
        description="Vector index type: IVF (dev), HNSW (prod), FLAT (tiny)",
        pattern="^(IVF|HNSW|FLAT)$",
    )

    # ========================================================================
    # SUPABASE STORAGE
    # ========================================================================
    SUPABASE_URL: str = Field(default="https://placeholder.supabase.co")
    SUPABASE_ANON_KEY: str = Field(default="")
    SUPABASE_SERVICE_KEY: str = Field(default="")
    SUPABASE_ARTIFACTS_BUCKET: str = Field(default="chad-core-artifacts")
    ARTIFACT_URL_EXPIRY: int = Field(default=86400, description="Signed URL TTL (seconds)")

    # ========================================================================
    # REDIS
    # ========================================================================
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_QUEUE_STREAM: str = Field(default="queue:act_tasks")
    REDIS_QUEUE_CONSUMER_GROUP: str = Field(default="chad-core-workers")
    REDIS_QUEUE_CONSUMER_NAME: str = Field(default="worker-1")
    REDIS_IDEMPOTENCY_TTL: int = Field(default=86400)
    REDIS_RATE_LIMIT_WINDOW: int = Field(default=60)

    # Queue Worker Settings
    QUEUE_STREAM_NAME: str = Field(default="chad:jobs", description="Redis stream name for jobs")
    QUEUE_CONSUMER_GROUP: str = Field(default="chad-workers", description="Consumer group name")
    QUEUE_CONSUMER_NAME: str = Field(default="worker-default", description="Consumer name (set to hostname in production)")
    QUEUE_MAX_RETRIES: int = Field(default=3, description="Max retry attempts for failed jobs")
    QUEUE_RETRY_DELAY_SECONDS: int = Field(default=60, description="Delay before retrying failed jobs")
    QUEUE_DEAD_LETTER_STREAM: str = Field(default="chad:jobs:dlq", description="Dead letter queue stream")
    QUEUE_POLL_INTERVAL_MS: int = Field(default=1000, description="Stream polling interval in milliseconds")
    QUEUE_BLOCK_MS: int = Field(default=5000, description="Block time for XREADGROUP in milliseconds")

    # Webhook Settings
    WEBHOOK_TIMEOUT_SECONDS: int = Field(default=10, description="HTTP timeout for webhook calls")
    WEBHOOK_MAX_RETRIES: int = Field(default=3, description="Max webhook delivery retries")
    WEBHOOK_RETRY_BACKOFF_BASE: int = Field(default=2, description="Exponential backoff base for webhook retries")

    # ========================================================================
    # AUTH & SECURITY
    # ========================================================================
    JWT_SECRET_KEY: str = Field(
        default="CHANGE_ME_dev_secret_key_min_32_chars",
        description="JWT signing key (rotate in production!)",
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRATION_MINUTES: int = Field(default=60)

    HMAC_SECRET_KEY: str = Field(
        default="CHANGE_ME_dev_hmac_secret",
        description="HMAC signature key shared with n8n",
    )

    RATE_LIMIT_PER_ACTOR: int = Field(default=60)
    RATE_LIMIT_ADMIN: int = Field(default=300)
    RATE_LIMIT_ANONYMOUS: int = Field(default=10)

    # ========================================================================
    # OPENTELEMETRY
    # ========================================================================
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(default="http://localhost:4317")
    OTEL_SERVICE_NAME: str = Field(default="chad-core")
    OTEL_TRACES_ENABLED: bool = Field(default=True)
    OTEL_TRACES_SAMPLER: str = Field(default="parentbased_always_on")

    # ========================================================================
    # LANGFUSE (Optional)
    # ========================================================================
    LANGFUSE_PUBLIC_KEY: str = Field(default="")
    LANGFUSE_SECRET_KEY: str = Field(default="")
    LANGFUSE_HOST: str = Field(default="https://cloud.langfuse.com")
    LANGFUSE_ENABLED: bool = Field(default=False)

    # ========================================================================
    # REFLEX ROUTER
    # ========================================================================
    REFLEX_STRATEGY: str = Field(
        default="rules", description="rules (regex) or slm (small LLM)", pattern="^(rules|slm)$"
    )

    # ========================================================================
    # API SERVER
    # ========================================================================
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_WORKERS: int = Field(default=4)
    API_CORS_ORIGINS: str = Field(default="http://localhost:5173")
    API_CORS_ALLOW_CREDENTIALS: bool = Field(default=True)
    API_REQUEST_TIMEOUT: int = Field(default=300)

    # ========================================================================
    # LOGGING
    # ========================================================================
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_FORMAT: str = Field(default="json", pattern="^(json|text)$")
    LOG_FILE: str = Field(default="")

    # ========================================================================
    # ADAPTERS
    # ========================================================================
    ADAPTER_NOTION_URL: str = Field(default="http://localhost:8001")
    ADAPTER_GOOGLE_URL: str = Field(default="http://localhost:8002")
    ADAPTER_GITHUB_URL: str = Field(default="http://localhost:8003")
    ADAPTER_OUTLOOK_URL: str = Field(default="http://localhost:8004")
    ADAPTER_SUPABASE_URL: str = Field(default="http://localhost:8005")

    # Adapter credentials (encrypt in production!)
    NOTION_API_KEY: str = Field(default="")
    GOOGLE_SERVICE_ACCOUNT_JSON: str = Field(default="")
    GOOGLE_CREDENTIALS_PATH: str | None = Field(default=None)
    GITHUB_TOKEN: str = Field(default="")
    SLACK_BOT_TOKEN: str = Field(default="")
    OUTLOOK_CLIENT_ID: str = Field(default="")
    OUTLOOK_CLIENT_SECRET: str = Field(default="")
    SUPABASE_ADMIN_KEY: str = Field(default="")

    # ========================================================================
    # DEPLOYMENT
    # ========================================================================
    ENVIRONMENT: str = Field(
        default="development", pattern="^(development|staging|production)$"
    )

    # ========================================================================
    # FEATURE FLAGS
    # ========================================================================
    FEATURE_LANGFUSE_ENABLED: bool = Field(default=False)
    FEATURE_SWARM_ROUTER_ENABLED: bool = Field(default=False)
    FEATURE_WEBHOOK_NOTIFICATIONS: bool = Field(default=False)
    FEATURE_AUTO_ROLLBACK: bool = Field(default=False)


# ============================================================================
# AGENT SIGN-OFF
# ============================================================================
# ✅ api-scaffolding/backend-architect
