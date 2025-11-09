"""
Chad-Core FastAPI Application Entry Point.

This module initializes the FastAPI application with:
- CORS middleware
- OpenTelemetry instrumentation
- Rate limiting middleware
- Request ID injection
- Lifespan context management (DB, Redis connections)
- Router mounting

Agents:
- api-scaffolding/fastapi-pro
- observability-monitoring/observability-engineer
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from chad_config.settings import Settings
from chad_obs.logging import setup_logging
from chad_obs.tracing import setup_tracing

# Import routers
from apps.core_api.routers import act, auth, health, metrics, runs, approvals

# Initialize settings
settings = Settings()

# Setup logging
setup_logging(settings)

# Setup OpenTelemetry tracing
setup_tracing(settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles:
    - Tool registry initialization
    - Notion and n8n tool registration
    - Database connection pool initialization
    - Redis connection initialization
    - Graceful shutdown

    TODO: Implement connection pooling
    TODO: Add health check warmup
    TODO: Implement graceful shutdown with timeout
    """
    from chad_tools.registry import ToolRegistry
    from chad_tools.adapters.notion import NotionClientWrapper
    from chad_tools.adapters.notion.tools import (
        NotionSearchTool,
        NotionReadPageTool,
        NotionCreatePageTool,
        NotionQueryDatabaseTool,
    )
    from chad_tools.adapters.n8n import N8nWorkflowRegistry
    from apps.core_api.deps import init_redis, close_redis
    from apps.core_api.auth import set_redis_client, get_redis_client
    import os

    # Startup
    print("🚀 Chad-Core API starting up...")
    print(f"📊 Environment: {settings.ENVIRONMENT}")
    print(f"🗄️  Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'local'}")
    print(f"💾 Redis: {settings.REDIS_URL}")

    # Initialize Redis connection
    try:
        await init_redis()
        redis = get_redis_client()
        if redis:
            set_redis_client(redis)
            print("✅ Redis connected")
    except Exception as e:
        print(f"⚠️  Redis connection failed: {e}")
        print("   Continuing without Redis (rate limiting and token blacklisting disabled)")

    # Initialize tool registry
    tool_registry = ToolRegistry()
    app.state.tool_registry = tool_registry

    # 1. Register Notion tools
    print("\n📚 Registering Notion tools...")
    notion_api_key = os.getenv("NOTION_API_KEY")
    notion_client = NotionClientWrapper(api_key=notion_api_key)
    app.state.notion_client = notion_client

    tool_registry.register(NotionSearchTool(api_key=notion_api_key))
    tool_registry.register(NotionReadPageTool(api_key=notion_api_key))
    tool_registry.register(NotionCreatePageTool(api_key=notion_api_key))
    tool_registry.register(NotionQueryDatabaseTool(api_key=notion_api_key))
    print(f"  ✅ Registered 4 Notion tools")

    # 2. Discover and register n8n workflows
    print("\n🔄 Discovering n8n workflows from Notion...")
    n8n_api_key = os.getenv("CHAD_ROUTER_TOKEN")  # Auth token for n8n webhooks

    n8n_registry = N8nWorkflowRegistry(
        notion_client=notion_client,
        tool_registry=tool_registry,
        api_key=n8n_api_key,
    )
    app.state.n8n_registry = n8n_registry

    try:
        workflow_count = await n8n_registry.discover_and_register()
        print(f"  ✅ Registered {workflow_count} n8n workflow(s)")
    except Exception as e:
        print(f"  ⚠️  Failed to discover n8n workflows: {e}")
        print(f"     Chad will continue without n8n workflows")
        print(f"     (This is expected if 'n8n Workflows' folder doesn't exist in Notion yet)")

    print(f"\n🎯 Chad-Core ready! Total tools: {len(tool_registry._tools)}")
    print(f"   Available tools: {', '.join(tool_registry._tools.keys())}")

    # Initialize database connection pool
    print("\n🗄️  Initializing database connection pool...")
    from chad_memory.database import get_engine, check_db_connection

    try:
        engine = get_engine(settings.DATABASE_URL)
        app.state.db_engine = engine

        # Health check
        is_healthy = await check_db_connection()
        if is_healthy:
            print("  ✅ Database connection established")
        else:
            print("  ⚠️  Database health check failed")
    except Exception as e:
        print(f"  ⚠️  Database initialization failed: {e}")
        print(f"     Chad will continue without database persistence")

    # TODO: Initialize Redis connection
    # app.state.redis = await init_redis_pool(settings.REDIS_URL)

    yield

    # Shutdown
    print("\n🛑 Chad-Core API shutting down...")

    # Close Notion client
    if hasattr(app.state, "notion_client"):
        await app.state.notion_client.close()

    # Close Redis connection
    await close_redis()

    # Close database connections
    if hasattr(app.state, "db_engine"):
        print("  🗄️  Closing database connections...")
        from chad_memory.database import close_db_connections
        await close_db_connections()
        print("  ✅ Database connections closed")

    print("✅ Graceful shutdown complete")


# Initialize FastAPI application
app = FastAPI(
    title="Chad-Core API",
    description="Jarvis-inspired hybrid agentic service with LangGraph orchestration",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ============================================================================
# MIDDLEWARE
# ============================================================================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.API_CORS_ORIGINS.split(",") if settings.API_CORS_ORIGINS else ["*"],
    allow_credentials=settings.API_CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Trace-ID"],
)

# Request ID middleware (must be added before other middleware)
from apps.core_api.middleware import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)

# Rate limiting middleware
from apps.core_api.middleware import RateLimitMiddleware

app.add_middleware(RateLimitMiddleware)

# Request logging middleware (optional, for debugging)
from apps.core_api.middleware import RequestLoggingMiddleware

app.add_middleware(RequestLoggingMiddleware)

# OpenTelemetry FastAPI instrumentation is auto-applied in chad_obs/tracing.py

# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled exceptions.

    TODO: Add structured logging with trace context
    TODO: Sanitize error messages (don't expose internal details)
    TODO: Add Sentry/error tracking integration
    """
    import traceback

    print(f"❌ Unhandled exception: {exc}")
    traceback.print_exc()

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please contact support.",
            # TODO: Include trace_id for debugging
        },
    )


# ============================================================================
# ROUTERS
# ============================================================================

# Authentication endpoints
app.include_router(auth.router, prefix="/auth", tags=["auth"])

# Core execution endpoint
app.include_router(act.router, prefix="", tags=["execution"])

# Approval workflow endpoints
app.include_router(approvals.router, prefix="/approvals", tags=["approvals"])

# Run viewer endpoints
app.include_router(runs.router, prefix="/runs", tags=["runs"])

# Health and metrics
app.include_router(health.router, prefix="", tags=["health"])
app.include_router(metrics.router, prefix="", tags=["metrics"])


# ============================================================================
# ROOT ENDPOINT
# ============================================================================


@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint - API information.

    Returns:
        API metadata and available endpoints
    """
    return {
        "name": "Chad-Core API",
        "version": "0.1.0",
        "description": "Jarvis-inspired hybrid agentic service",
        "docs": "/docs",
        "health": "/healthz",
        "metrics": "/metrics",
        "endpoints": {
            "execution": "POST /act",
            "runs": "GET /runs",
            "run_detail": "GET /runs/{id}",
            "run_steps": "GET /runs/{id}/steps",
        },
    }


# ============================================================================
# DEVELOPMENT HELPERS
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Development server (auto-reload enabled)
    uvicorn.run(
        "apps.core_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

# ============================================================================
# AGENT SIGN-OFF
# ============================================================================
# ✅ api-scaffolding/fastapi-pro
# ✅ observability-monitoring/observability-engineer
