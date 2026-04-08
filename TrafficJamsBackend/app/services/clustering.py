"""
Clustering service — pure algorithm logic only.

All data loading is handled by AccidentRepository.
All road snapping is handled by RoadSegmentRepository.
All persistence is handled by ClusterRepository.

Flow:
1. Load accident points via AccidentRepository.
2. Project coordinates to UTM (metric CRS) for DBSCAN.
3. Run sklearn DBSCAN with eps in metres.
4. For each cluster label:
   a. Compute centroid.
   b. Snap centroid to road via RoadSegmentRepository.
   c. Compute convex hull via ClusterRepository.
   d. Build ClusterData and delegate persistence to ClusterRepository.
5. Return run summary.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import List, Dict

import numpy as np
from sklearn.cluster import DBSCAN
from pyproj import Transformer

from app.config import get_settings
from app.domain import AccidentPoint, ClusterData
from app.repositories.base import AccidentRepository, RoadSegmentRepository, ClusterRepository
from app.schemas.cluster import ClusterRunRequest, ClusterRunResponse

logger = logging.getLogger(__name__)
settings = get_settings()


def _latlon_to_utm(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Project WGS84 lat/lon to a metric UTM CRS. Returns Nx2 array in metres."""
    center_lon = float(np.mean(lons))
    center_lat = float(np.mean(lats))
    zone = int((center_lon + 180) / 6) + 1
    epsg = 32600 + zone if center_lat >= 0 else 32700 + zone
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    xs, ys = transformer.transform(lons, lats)
    return np.column_stack([xs, ys])


def _run_dbscan(coords_m: np.ndarray, eps_meters: float, min_samples: int) -> np.ndarray:
    """Run DBSCAN on metric coordinates. Returns label array (-1 = noise)."""
    db = DBSCAN(eps=eps_meters, min_samples=min_samples, algorithm="ball_tree", metric="euclidean", n_jobs=-1)
    labels = db.fit_predict(coords_m)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    logger.info("DBSCAN: %d clusters, %d noise (eps=%.0f m, min_samples=%d)",
                n_clusters, int(np.sum(labels == -1)), eps_meters, min_samples)
    return labels


async def run_clustering(
    accident_repo: AccidentRepository,
    road_repo: RoadSegmentRepository,
    cluster_repo: ClusterRepository,
    request: ClusterRunRequest,
) -> ClusterRunResponse:
    t0 = time.perf_counter()
    run_id = str(uuid.uuid4())

    # 1. Load accidents
    points: List[AccidentPoint] = await accident_repo.get_accident_points(request)
    if len(points) < request.min_samples:
        return ClusterRunResponse(
            run_id=run_id, clusters_created=0, accidents_processed=len(points),
            noise_points=len(points), eps_meters=request.eps_meters,
            min_samples=request.min_samples, duration_seconds=time.perf_counter() - t0,
        )

    # 2. Project to metric CRS and run DBSCAN
    lats = np.array([p.lat for p in points])
    lons = np.array([p.lng for p in points])
    coords_m = _latlon_to_utm(lats, lons)
    labels = _run_dbscan(coords_m, request.eps_meters, request.min_samples)

    # 3. Optionally clear previous clusters for the same parameters
    if request.replace_existing:
        await cluster_repo.delete_by_params(request.eps_meters, request.min_samples)

    # 4. Group points by label
    label_to_points: Dict[int, List[AccidentPoint]] = {}
    for point, label in zip(points, labels):
        if label != -1:
            label_to_points.setdefault(label, []).append(point)

    # 5. For each cluster: snap, hull, persist
    for label, cluster_points in label_to_points.items():
        c_lats = np.array([p.lat for p in cluster_points])
        c_lons = np.array([p.lng for p in cluster_points])
        centroid_lat = float(np.mean(c_lats))
        centroid_lng = float(np.mean(c_lons))

        snap = await road_repo.snap_to_road(centroid_lat, centroid_lng, settings.road_snap_max_distance)
        convex_hull_wkt = await cluster_repo.compute_convex_hull(cluster_points)

        await cluster_repo.save_cluster(ClusterData(
            run_id=run_id,
            dbscan_label=label,
            eps_meters=request.eps_meters,
            min_samples=request.min_samples,
            centroid_lat=centroid_lat,
            centroid_lng=centroid_lng,
            accidents=cluster_points,
            snap=snap,
            convex_hull_wkt=convex_hull_wkt,
        ))

    noise_count = int(np.sum(labels == -1))
    duration = time.perf_counter() - t0
    logger.info("Run %s: %d clusters, %d noise, %.2fs", run_id, len(label_to_points), noise_count, duration)

    return ClusterRunResponse(
        run_id=run_id,
        clusters_created=len(label_to_points),
        accidents_processed=len(points),
        noise_points=noise_count,
        eps_meters=request.eps_meters,
        min_samples=request.min_samples,
        duration_seconds=duration,
    )

