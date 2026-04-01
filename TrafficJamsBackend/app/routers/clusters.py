"""
Router: /api/clusters
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# from app.database import get_db
from app.models.cluster import DangerousRoadCluster, ClusterAccident
from app.models.accident import Accident
from app.schemas.cluster import (
    ClusterListResponse,
    ClusterListItem,
    ClusterDetail,
    ClusterRunRequest,
    ClusterRunResponse,
)
from app.services.clustering import run_clustering

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clusters", tags=["clusters"])

# ─── GET /api/clusters ─────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=ClusterListResponse,
    summary="List dangerous road clusters",
)
async def list_clusters(
    # TODO: add pagination/sorting/filtering

    # # Pagination
    # page: int = Query(1, ge=1, description="Page number (1-based)"),
    # page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    # # Filters
    # run_id: Optional[str] = Query(None, description="Filter by clustering run UUID"),
    # is_active: Optional[bool] = Query(True, description="Filter by active status"),
    # min_severity: Optional[float] = Query(None, description="Minimum severity score"),
    # min_accidents: Optional[int] = Query(None, description="Minimum accident count"),
    # region: Optional[int] = Query(None, description="Filter by region code"),
    # # Sorting
    # sort_by: str = Query(
    #     "severity_score",
    #     description="Field to sort by: severity_score | accident_count | created_at",
    # ),
    # sort_desc: bool = Query(True, description="Sort descending"),
    # # Bounding box filter
    # bbox: Optional[str] = Query(
    #     None,
    #     description="Bounding box filter: 'min_lng,min_lat,max_lng,max_lat'",
    # ),
    db: AsyncSession = Depends(get_db),
) -> ClusterListResponse:
    stmt = select(DangerousRoadCluster)

    result = await db.execute(stmt)
    clusters = result.scalars().all()

    items = [ClusterListItem.model_validate(c) for c in clusters]

    return ClusterListResponse(
        items=items
    )

# ─── GET /api/clusters/{cluster_id} ────────────────────────────────────────────

@router.get(
    "/{cluster_id}",
    response_model=ClusterDetail,
    summary="Get cluster detail with all accidents",
)
async def get_cluster(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
) -> ClusterDetail:

    stmt = (
        select(DangerousRoadCluster)
        .where(DangerousRoadCluster.id == cluster_id)
        .options(
            selectinload(DangerousRoadCluster.cluster_accidents).selectinload(
                ClusterAccident.accident
            )
        )
    )
    result = await db.execute(stmt)
    cluster = result.scalar_one_or_none()

    if cluster is None:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")

    return ClusterDetail.model_validate(cluster)


# ─── GET /api/clusters/{cluster_id}/accidents ──────────────────────────────────

@router.get(
    "/{cluster_id}/accidents",
    summary="List accidents belonging to a cluster (paginated)",
)
async def list_cluster_accidents(
    cluster_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    # Check cluster exists
    exists_stmt = select(DangerousRoadCluster.id).where(
        DangerousRoadCluster.id == cluster_id
    )
    exists = (await db.execute(exists_stmt)).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")

    stmt = (
        select(ClusterAccident)
        .where(ClusterAccident.cluster_id == cluster_id)
        .options(selectinload(ClusterAccident.accident))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).where(ClusterAccident.cluster_id == cluster_id)
    )
    total = count_result.scalar_one()

    return {
        "cluster_id": cluster_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "accident_id": ca.accident_id,
                "distance_to_road_m": ca.distance_to_road_m,
            }
            for ca in items
        ],
    }