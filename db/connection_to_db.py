import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError
from core.logging_config import get_logger


load_dotenv()
logger = get_logger(__name__)

DB_HOST = os.getenv("POSTGRES_HOST_BRNO", os.getenv("DB_HOST", "localhost"))
DB_PORT = int(os.getenv("POSTGRES_PORT_BRNO", os.getenv("DB_PORT", "5433")))
DB_NAME = os.getenv("POSTGRES_DB_BRNO")
DB_USER = os.getenv("POSTGRES_USER_BRNO")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD_BRNO")

_engine = None
_SessionLocal = None
_credentials_ok = None


def _init_engine() -> bool:
    """Create engine once per worker process. Returns False if credentials are missing."""
    global _engine, _SessionLocal, _credentials_ok

    # Once connected successfully, reuse the existing engine (pool_pre_ping handles reconnects)
    if _db_available:
        return True

    if not all([DB_HOST, DB_NAME, DB_USER, DB_PASSWORD]):
        logger.warning("Database credentials not configured, using example data fallback")
        return False

    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    _engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
    )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    _credentials_ok = True
    logger.info(f"DB engine created for this worker: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    return True


def is_database_available() -> bool:
    """Test live connection — used by health check and startup log."""
    if not _init_engine():
        return False
    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1")) 

        logger.info(f"Database connection successful: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        _db_available = True
        return True

    except (OperationalError, Exception) as e:
        logger.warning(f"Database connection failed: {e}. Using example data fallback")
        _engine = None
        _SessionLocal = None
        return False


def get_db() -> Session:
    """FastAPI dependency. Yields None if DB is unreachable so endpoints can fall back."""
    if not _init_engine():
        yield None
        return

    db = _SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
