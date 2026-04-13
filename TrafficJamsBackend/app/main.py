"""
FastAPI application: Accident Clustering API
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import async_engine, AsyncSessionLocal
from app.routers import clusters_router, prediction_router
from app.services.prediction import PredictionService

# Import models so that Base.metadata is populated before create_all
import app.models  # noqa: F401

logging.basicConfig(
    level=logging.DEBUG if get_settings().debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


async def _auto_cluster_if_empty() -> None:
    """
    Run DBSCAN clustering once if dangerous_road_clusters is empty.
    Only executes when DATA_SOURCE=postgres and AUTO_CLUSTER_ON_STARTUP=true.
    Uses the dbscan_eps_meters / dbscan_min_samples values from settings.
    """
    # Late imports to avoid circular dependencies
    from app.repositories.accident import PostgresAccidentRepository
    from app.repositories.road_segment import PostgresRoadSegmentRepository
    from app.repositories.cluster import PostgresClusterRepository
    from app.schemas.cluster import ClusterRunRequest
    from app.services.clustering import run_clustering

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM dangerous_road_clusters")
        )
        count = result.scalar()

    if count and count > 0:
        logger.info("Auto-cluster: %d clusters already exist — skipping.", count)
        return

    logger.info(
        "Auto-cluster: table is empty — running DBSCAN (eps=%.0f m, min_samples=%d)…",
        settings.dbscan_eps_meters, settings.dbscan_min_samples,
    )
    async with AsyncSessionLocal() as session:
        try:
            result = await run_clustering(
                accident_repo=PostgresAccidentRepository(session),
                road_repo=PostgresRoadSegmentRepository(session),
                cluster_repo=PostgresClusterRepository(session),
                request=ClusterRunRequest(
                    eps_meters=settings.dbscan_eps_meters,
                    min_samples=settings.dbscan_min_samples,
                ),
            )
            await session.commit()
            logger.info(
                "Auto-cluster complete: %d clusters, %d accidents processed (%.2fs).",
                result.clusters_created, result.accidents_processed, result.duration_seconds,
            )
        except Exception:
            await session.rollback()
            logger.exception("Auto-cluster failed — API will start without pre-clustered data.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup: load ML models, optionally auto-cluster. Shutdown: dispose DB engine."""
    logger.info("Starting up Accident Clustering API…")

    PredictionService.load()

    if settings.auto_cluster_on_startup and settings.data_source == "postgres":
        await _auto_cluster_if_empty()
    elif settings.auto_cluster_on_startup:
        logger.warning(
            "AUTO_CLUSTER_ON_STARTUP=true but DATA_SOURCE=%s — auto-clustering requires postgres.",
            settings.data_source,
        )

    yield

    logger.info("Shutting down — disposing DB engine.")
    await async_engine.dispose()


# Create FastAPI app
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description="REST API for traffic jams analysis",
    lifespan=lifespan,
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
app.include_router(prediction_router)

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