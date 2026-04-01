"""
FastAPI application: Accident Clustering API
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import async_engine, Base
from app.routers import clusters_router

# Import models so that Base.metadata is populated before create_all
import app.models  # noqa: F401

logging.basicConfig(
    level=logging.DEBUG if get_settings().debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


# TODO: Enable checking of DB connection

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """
#     Startup: verify DB connection.
#     Shutdown: dispose engine.
#     """
#     logger.info("Starting up Accident Clustering API…")
#     async with async_engine.connect() as conn:
#         from sqlalchemy import text
#         await conn.execute(text("SELECT 1"))
#         logger.info("Database connection OK.")
#     yield
#     logger.info("Shutting down — disposing DB engine.")
#     await async_engine.dispose()

# Create Fast API app
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=(
        "REST API for traffic jams analysis"
    ),
    # lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(clusters_router)

# Health check
@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "version": settings.app_version}


@app.get("/", tags=["meta"])
async def root():
    return JSONResponse({
        "service": settings.app_title,
        "version": settings.app_version,
        "docs": "/docs",
    })