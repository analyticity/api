from fastapi import FastAPI
from api.api_v1 import api_router
from core.logging_config import setup_logging, get_logger
from core.middleware import LoggingMiddleware
from db.connection_to_db import is_database_available

setup_logging(log_level="INFO")
logger = get_logger(__name__)

app = FastAPI(
    title="Analyticity API",
    description="""
    Traffic and geospatial analytics API for Brno.
    
    This API provides access to traffic data including:
    - Road segments with coordinates
    - Traffic jams
    - Accidents
    - Alerts
    - Restrictions
    
    **Automatic fallback**: When database is unavailable, the API automatically switches 
    to example data mode for testing and development.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(LoggingMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("Starting Analyticity API v1.0.0")
    db_status = "connected" if is_database_available() else "unavailable (using example data)"
    logger.info(f"Database status: {db_status}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("Shutting down Analyticity API")


@app.get("/", tags=["root"])
def read_root():
    """API root endpoint with basic information"""
    db_available = is_database_available()

    return {
        "message": "Analyticity API",
        "version": "1.0.0",
        "database_status": "connected" if db_available else "unavailable (fallback mode)",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health", tags=["health"])
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database_available": is_database_available()
    }


