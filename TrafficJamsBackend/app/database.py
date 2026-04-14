from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import create_engine
from app.config import get_settings

settings = get_settings()

# Async engine for FastAPI routes
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Sync engine for Alembic migrations only
sync_engine = create_engine(
    settings.database_url_sync,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass

async def get_db_optional():
    """
    FastAPI dependency: yields a DB session only when data_source='postgres'.
    Yields None when data_source='csv', so no connection is attempted.
    """
    if settings.data_source != "postgres":
        yield None
        return
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
