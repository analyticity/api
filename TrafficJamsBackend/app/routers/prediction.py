"""
Router: /api/prediction
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_optional
from app.repositories.base import ClusterRepository
from app.repositories.cluster import InMemoryClusterRepository, PostgresClusterRepository
from app.schemas.prediction import PredictionRequest, PredictionResponse
from app.services.prediction import PredictionService
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/prediction", tags=["prediction"])

# Re-use the same singleton that the clusters router writes into
from app.routers.clusters import _in_memory_cluster_repo  # noqa: E402


# ─── Repository dependency ────────────────────────────────────────────────────

def _get_cluster_repo(db: AsyncSession = Depends(get_db_optional)) -> ClusterRepository:
    if db is None:
        return _in_memory_cluster_repo
    return PostgresClusterRepository(db)


# ─── GET /api/prediction/clusters/{cluster_id} ────────────────────────────────

@router.get(
    "/clusters/{cluster_id}",
    response_model=PredictionResponse,
    summary="Predict danger level and expected damage for a cluster under current conditions",
    description=(
        "Returns a classification (danger probability + risk level) and a regression result "
        "(expected material damage in CZK) for the given cluster. "
        "Temporal features are always derived from the server clock. "
        "Weather features are fetched from Open-Meteo using the cluster centroid "
        "unless explicitly provided as query parameters."
    ),
)
async def predict_for_cluster(
    cluster_id: int,
    weather_condition: Optional[str] = Query(
        None,
        description="Current weather (e.g. 'clear', 'rain', 'snow', 'fog'). Fetched from Open-Meteo if omitted.",
    ),
    road_surface: Optional[str] = Query(
        None,
        description="Current road surface (e.g. 'dry', 'wet', 'ice'). Derived from weather if omitted.",
    ),
    light_condition: Optional[str] = Query(
        None,
        description="Current light condition (e.g. 'daylight', 'dark'). Derived from server hour if omitted.",
    ),
    road_condition: Optional[str] = Query(
        None,
        description="Current road condition (e.g. 'normal', 'slippery'). Derived from weather if omitted.",
    ),
    accident_type: Optional[str] = Query(
        None,
        description="Optional accident type hint (e.g. 'collision'). Defaults to 'unknown'.",
    ),
    cause_primary: Optional[str] = Query(
        None,
        description="Optional primary cause hint (e.g. 'speed'). Defaults to 'unknown'.",
    ),
    cluster_repo: ClusterRepository = Depends(_get_cluster_repo),
) -> PredictionResponse:
    if not PredictionService.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Prediction models are not loaded. Run scripts/train_model.py first.",
        )

    cluster = await cluster_repo.get_cluster(cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")

    try:
        result = await PredictionService.predict_for_cluster(
            cluster=cluster,
            weather_condition=weather_condition,
            road_surface=road_surface,
            light_condition=light_condition,
            road_condition=road_condition,
            accident_type=accident_type,
            cause_primary=cause_primary,
        )
    except Exception as exc:
        logger.exception("Prediction failed for cluster %d: %s", cluster_id, exc)
        raise HTTPException(status_code=500, detail=f"Prediction error: {exc}") from exc

    return PredictionResponse(**result)
