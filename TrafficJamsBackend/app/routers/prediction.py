"""
Router: /api/prediction
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_optional
from app.repositories.base import ClusterRepository
from app.repositories.cluster import InMemoryClusterRepository, PostgresClusterRepository
from app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    ScenarioRequest,
    ScenarioResponse,
)
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
        )
    except Exception as exc:
        logger.exception("Prediction failed for cluster %d: %s", cluster_id, exc)
        raise HTTPException(status_code=500, detail=f"Prediction error: {exc}") from exc

    return PredictionResponse(**result)


# ─── POST /api/prediction/scenario ────────────────────────────────────────────

@router.post(
    "/scenario",
    response_model=ScenarioResponse,
    summary="Score every cluster under a single user-supplied environmental scenario",
    description=(
        "Runs both predictive models against every active cluster using the "
        "weather, lighting and temporal conditions provided in the request. "
        "No external weather call is made: omitted fields default to 'unknown'. "
        "Returns the items sorted by danger probability (highest first), "
        "filtered to those whose probability is at least *min_probability*."
    ),
)
async def predict_scenario(
    request: ScenarioRequest,
    cluster_repo: ClusterRepository = Depends(_get_cluster_repo),
) -> ScenarioResponse:
    if not PredictionService.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Prediction models are not loaded. Run scripts/train_model.py first.",
        )

    clusters = await cluster_repo.list_clusters()
    if not clusters:
        return ScenarioResponse(
            evaluated_at=datetime.now(timezone.utc),
            model_trained_at=None,
            temporal={"hour": 0, "day_of_week": 0, "month": 1, "is_weekend": False, "is_night": False},
            weather={
                "weather_condition": request.weather_condition or "unknown",
                "road_surface":      request.road_surface or "unknown",
                "light_condition":   request.light_condition or "unknown",
                "road_condition":    request.road_condition or "unknown",
                "source":            "user",
            },
            total_clusters=0,
            returned=0,
            items=[],
        )

    try:
        result = PredictionService.predict_scenario(
            clusters=clusters,
            weather_condition=request.weather_condition,
            road_surface=request.road_surface,
            light_condition=request.light_condition,
            road_condition=request.road_condition,
            hour=request.hour,
            day_of_week=request.day_of_week,
            month=request.month,
        )
    except Exception as exc:
        logger.exception("Scenario prediction failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Scenario prediction error: {exc}") from exc

    items = [it for it in result["items"] if it["danger_probability"] >= request.min_probability]
    items.sort(key=lambda it: it["danger_probability"], reverse=True)
    if request.limit is not None:
        items = items[: request.limit]

    return ScenarioResponse(
        evaluated_at=result["evaluated_at"],
        model_trained_at=result["model_trained_at"],
        temporal=result["temporal"],
        weather=result["weather"],
        total_clusters=len(clusters),
        returned=len(items),
        items=items,
    )
