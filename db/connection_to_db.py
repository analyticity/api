import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError
from core.logging_config import get_logger

load_dotenv()
logger = get_logger(__name__)

DB_HOST = os.getenv("POSTGRES_HOST_BRNO", os.getenv("DB_HOST", "localhost"))
DB_PORT = int(os.getenv("POSTGRES_PORT_BRNO", os.getenv("DB_PORT", "5432")))
DB_NAME = os.getenv("POSTGRES_DB_BRNO")
DB_USER = os.getenv("POSTGRES_USER_BRNO")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD_BRNO")

_db_available = None
_engine = None
_SessionLocal = None


def is_database_available() -> bool:
    """Check if database connection is available"""
    global _db_available, _engine, _SessionLocal

    if _db_available is not None:
        return _db_available

    if not all([DB_HOST, DB_NAME, DB_USER, DB_PASSWORD]):
        logger.warning("Database credentials not configured, using example data fallback")
        _db_available = False
        return False

    try:
        DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

        with _engine.connect() as conn:
            conn.execute("SELECT 1")

        logger.info(f"Database connection successful: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        _db_available = True
        return True

    except (OperationalError, Exception) as e:
        logger.warning(f"Database connection failed: {e}. Using example data fallback")
        _db_available = False
        return False


def get_db() -> Session:
    """Dependency for FastAPI to get database session or None if unavailable"""
    if not is_database_available():
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


# Legacy psycopg2 connection (deprecated)
try:
    conn_params_brno = {
        "host": DB_HOST,
        "port": DB_PORT,
        "dbname": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
    }
    CONN_BRNO = psycopg2.connect(**conn_params_brno)
except Exception as e:
    logger.warning(f"Legacy psycopg2 connection failed: {e}")
    CONN_BRNO = None

