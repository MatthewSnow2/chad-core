"""Database session factory and engine initialization.

Provides async SQLAlchemy engine and session factory for Postgres with asyncpg.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from chad_config.settings import Settings

# Global engine and session factory
_engine = None
_async_session_factory = None


def get_engine(database_url: str = None):
    """Get or create async engine.

    Args:
        database_url: Database connection URL (must use asyncpg driver)

    Returns:
        AsyncEngine instance
    """
    global _engine

    if _engine is None:
        settings = Settings()
        url = database_url or settings.DATABASE_URL

        # Ensure asyncpg driver
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError(
                f"Database URL must use asyncpg driver. Got: {url.split('://')[0]}"
            )

        _engine = create_async_engine(
            url,
            echo=False,  # Set to True for SQL query logging
            pool_pre_ping=True,  # Verify connections before using
            pool_size=20,  # Connection pool size
            max_overflow=10,  # Max overflow connections
            pool_timeout=30,  # Connection timeout
            pool_recycle=3600,  # Recycle connections after 1 hour
        )

    return _engine


def get_session_factory(database_url: str = None):
    """Get or create async session factory.

    Args:
        database_url: Database connection URL

    Returns:
        async_sessionmaker instance
    """
    global _async_session_factory

    if _async_session_factory is None:
        engine = get_engine(database_url)
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
            autocommit=False,
            autoflush=False,
        )

    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: Get async database session.

    Yields:
        AsyncSession: SQLAlchemy async session

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db_connections():
    """Close database connections.

    Call this during application shutdown.
    """
    global _engine, _async_session_factory

    if _engine:
        await _engine.dispose()
        _engine = None

    _async_session_factory = None


async def check_db_connection():
    """Check database connection health.

    Returns:
        bool: True if database is reachable

    Raises:
        Exception: If connection fails
    """
    from sqlalchemy import text

    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))
        return result.scalar() == 1
