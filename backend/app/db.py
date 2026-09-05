import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.config import settings
from app.models import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize vector extension and create all database tables."""
    try:
        async with engine.begin() as conn:
            # Enable pgvector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            # Create tables
            await conn.run_sync(Base.metadata.create_all)
            # Add progress_percent column if not already present on existing table
            await conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS progress_percent INT NOT NULL DEFAULT 0;"))
            logger.info("Database tables initialized successfully with pgvector.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        raise
