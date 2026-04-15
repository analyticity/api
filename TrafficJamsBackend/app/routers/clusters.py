"""
Router: /api/clusters
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db_optional
from app.schemas.cluster import (
    ClusterListResponse,
    ClusterListItem,
    ClusterDetail,
    ClusterRunRequest,
    ClusterRunResponse,
)
from app.repositories.base import AccidentRepository, RoadSegmentRepository, ClusterRepository
from app.repositories.accident import PostgresAccidentRepository, CsvAccidentRepository
from app.repositories.road_segment import PostgresRoadSegmentRepository, CsvRoadSegmentRepository
from app.repositories.cluster import PostgresClusterRepository, InMemoryClusterRepository
from app.services.clustering import run_clustering

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/clusters", tags=["clusters"])

# Singleton in-memory repo — state persists across requests, resets on restart
_in_memory_cluster_repo = InMemoryClusterRepository()


# ─── Repository dependency factories ──────────────────────────────────────────

def get_accident_repo(db: AsyncSession = Depends(get_db_optional)) -> AccidentRepository:
    if settings.data_source == "csv":
        return CsvAccidentRepository(settings.accidents_csv_path)
    return PostgresAccidentRepository(db)


def get_road_repo(db: AsyncSession = Depends(get_db_optional)) -> RoadSegmentRepository:
    if settings.data_source == "csv":
        return CsvRoadSegmentRepository(settings.road_segments_csv_path)
    return PostgresRoadSegmentRepository(db)


def get_cluster_repo(db: AsyncSession = Depends(get_db_optional)) -> ClusterRepository:
    if db is None:
        return _in_memory_cluster_repo
    return PostgresClusterRepository(db)


# ─── POST /api/clusters/run ────────────────────────────────────────────────────

@router.post(
    "/run",
    response_model=ClusterRunResponse,
    summary="Run DBSCAN clustering and persist results",
)
async def trigger_clustering(
    request: ClusterRunRequest,
    accident_repo: AccidentRepository = Depends(get_accident_repo),
    road_repo: RoadSegmentRepository = Depends(get_road_repo),
    cluster_repo: ClusterRepository = Depends(get_cluster_repo),
) -> ClusterRunResponse:
    try:
        return await run_clustering(
            accident_repo=accident_repo,
            road_repo=road_repo,
            cluster_repo=cluster_repo,
            request=request,
        )
    except Exception as exc:
        logger.exception("Clustering failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Clustering error: {exc}") from exc


# ─── GET /api/clusters ─────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=ClusterListResponse,
    summary="List dangerous road clusters",
)
async def list_clusters(
    cluster_repo: ClusterRepository = Depends(get_cluster_repo),
) -> ClusterListResponse:
    rows = await cluster_repo.list_clusters()
    items = [ClusterListItem.model_validate(row) for row in rows]
    return ClusterListResponse(items=items)


# ─── GET /api/clusters/{cluster_id} ────────────────────────────────────────────

@router.get(
    "/{cluster_id}",
    response_model=ClusterDetail,
    summary="Get cluster detail with all accidents",
)
async def get_cluster(
    cluster_id: int,
    cluster_repo: ClusterRepository = Depends(get_cluster_repo),
) -> ClusterDetail:
    row = await cluster_repo.get_cluster(cluster_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")
    return ClusterDetail.model_validate(row)


# ─── GET /api/clusters/{cluster_id}/accidents ──────────────────────────────────

@router.get(
    "/{cluster_id}/accidents",
    summary="List accidents belonging to a cluster (paginated)",
)
async def list_cluster_accidents(
    cluster_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    cluster_repo: ClusterRepository = Depends(get_cluster_repo),
):
    result = await cluster_repo.list_accidents(cluster_id, page, page_size)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")
    total, items = result
    return {
        "cluster_id": cluster_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }