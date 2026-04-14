"""
ClusterRepository implementations:
  - PostgresClusterRepository — persists clusters and accidents to PostgreSQL
  - NullClusterRepository     — no-op implementation for CSV / no-DB mode
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from geoalchemy2.functions import ST_GeomFromText

from app.domain import AccidentPoint, ClusterData
from app.models.cluster import DangerousRoadCluster, ClusterAccident
from app.repositories.base import ClusterRepository

logger = logging.getLogger(__name__)


def _severity_score(accident_count: int, fatalities: int, serious: int, minor: int, damage: int) -> float:
    return fatalities * 10.0 + serious * 3.0 + minor * 1.0 + accident_count * 0.5 + damage / 1_000_000


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi, dlam = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return float(2 * R * np.arcsin(np.sqrt(a)))


def _wkt_to_geojson(wkt_str: Optional[str]) -> Optional[dict]:
    """Convert a WKT geometry string to a GeoJSON-compatible dict via Shapely."""
    if not wkt_str:
        return None
    try:
        from shapely import wkt
        from shapely.geometry import mapping
        return mapping(wkt.loads(wkt_str))
    except Exception:
        return None


def _orm_to_list_dict(obj: DangerousRoadCluster) -> dict:
    """Convert an ORM cluster object to a plain dict for ClusterListItem."""
    from app.schemas.cluster import _wkb_to_geojson
    row = {col.name: getattr(obj, col.name) for col in obj.__table__.columns}
    row["centroid_geojson"] = _wkb_to_geojson(getattr(obj, "centroid", None))
    row["road_point_geojson"] = _wkb_to_geojson(getattr(obj, "road_point", None))
    row["road_segment_geojson"] = _wkb_to_geojson(getattr(obj, "road_segment", None))
    row["convex_hull_geojson"] = _wkb_to_geojson(getattr(obj, "convex_hull", None))
    return row


def _orm_to_detail_dict(obj: DangerousRoadCluster) -> dict:
    """Convert an ORM cluster object (with loaded accidents) to a plain dict for ClusterDetail."""
    from app.schemas.cluster import _wkb_to_geojson
    row = {col.name: getattr(obj, col.name) for col in obj.__table__.columns}
    row["centroid_geojson"] = _wkb_to_geojson(getattr(obj, "centroid", None))
    row["road_point_geojson"] = _wkb_to_geojson(getattr(obj, "road_point", None))
    row["road_segment_geojson"] = _wkb_to_geojson(getattr(obj, "road_segment", None))
    row["convex_hull_geojson"] = _wkb_to_geojson(getattr(obj, "convex_hull", None))
    accident_items = []
    for ca in getattr(obj, "cluster_accidents", []):
        acc = ca.accident
        acc_dict = None
        if acc is not None:
            acc_dict = {c.name: getattr(acc, c.name) for c in acc.__table__.columns if c.name != "location_geog"}
            geojson = _wkb_to_geojson(getattr(acc, "location_geog", None))
            if geojson and geojson.get("type") == "Point":
                coords = geojson.get("coordinates", [])
                if len(coords) >= 2:
                    acc_dict["lng"] = coords[0]
                    acc_dict["lat"] = coords[1]
        accident_items.append({
            "accident_id": ca.accident_id,
            "distance_to_road_m": ca.distance_to_road_m,
            "accident": acc_dict,
        })
    row["accidents"] = accident_items
    return row


class PostgresClusterRepository(ClusterRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def compute_convex_hull(self, points: List[AccidentPoint]) -> Optional[str]:
        if len(points) < 3:
            return None
        accident_ids = [p.accident_id for p in points]
        query = text("""
            SELECT ST_AsText(ST_ConvexHull(ST_Collect(location_geog)))
            FROM accidents
            WHERE id = ANY(:ids) AND location_geog IS NOT NULL
        """)
        result = await self._session.execute(query, {"ids": accident_ids})
        row = result.fetchone()
        return row[0] if row and row[0] else None

    async def save_cluster(self, data: ClusterData) -> None:
        lats = np.array([p.lat for p in data.accidents])
        lons = np.array([p.lng for p in data.accidents])

        fatalities_total = sum(p.fatalities for p in data.accidents)
        serious_total = sum(p.serious_injuries for p in data.accidents)
        minor_total = sum(p.minor_injuries for p in data.accidents)
        damage_total = sum(p.total_material_damage for p in data.accidents)
        score = _severity_score(len(data.accidents), fatalities_total, serious_total, minor_total, damage_total)

        road_numbers = [p.road_number for p in data.accidents if p.road_number]
        dominant_road_num = max(set(road_numbers), key=road_numbers.count) if road_numbers else data.snap.road_ref
        road_cats = [p.road_category for p in data.accidents if p.road_category]
        dominant_road_cat = max(set(road_cats), key=road_cats.count) if road_cats else data.snap.highway

        cluster = DangerousRoadCluster(
            run_id=data.run_id,
            dbscan_label=data.dbscan_label,
            eps_meters=data.eps_meters,
            min_samples=data.min_samples,
            centroid=ST_GeomFromText(f"POINT({data.centroid_lng} {data.centroid_lat})", 4326),
            road_point=ST_GeomFromText(data.snap.road_point_wkt, 4326) if data.snap.road_point_wkt else None,
            road_segment=ST_GeomFromText(data.snap.road_segment_wkt, 4326) if data.snap.road_segment_wkt else None,
            convex_hull=ST_GeomFromText(data.convex_hull_wkt, 4326) if data.convex_hull_wkt else None,
            road_name=data.snap.road_name,
            road_number=dominant_road_num,
            road_category=dominant_road_cat,
            accident_count=len(data.accidents),
            fatalities_total=fatalities_total,
            serious_injuries_total=serious_total,
            minor_injuries_total=minor_total,
            total_material_damage=damage_total,
            severity_score=score,
            bbox_min_lat=float(np.min(lats)),
            bbox_max_lat=float(np.max(lats)),
            bbox_min_lng=float(np.min(lons)),
            bbox_max_lng=float(np.max(lons)),
            is_active=True,
        )
        self._session.add(cluster)
        await self._session.flush()

        road_lat, road_lng = None, None
        if data.snap.road_point_wkt:
            try:
                coords = data.snap.road_point_wkt.replace("POINT(", "").replace(")", "").strip().split()
                road_lng, road_lat = float(coords[0]), float(coords[1])
            except Exception:
                pass

        for p in data.accidents:
            dist = _haversine_m(p.lat, p.lng, road_lat, road_lng) if road_lat is not None else None
            self._session.add(ClusterAccident(
                cluster_id=cluster.id,
                accident_id=p.accident_id,
                distance_to_road_m=dist,
            ))

    async def delete_by_params(self, eps_meters: float, min_samples: int) -> None:
        await self._session.execute(
            text("DELETE FROM dangerous_road_clusters WHERE eps_meters = :eps AND min_samples = :ms"),
            {"eps": eps_meters, "ms": min_samples},
        )
        await self._session.flush()

    async def list_clusters(self) -> List[dict]:
        stmt = select(DangerousRoadCluster).where(DangerousRoadCluster.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [_orm_to_list_dict(c) for c in result.scalars().all()]

    async def get_cluster(self, cluster_id: int) -> Optional[dict]:
        stmt = (
            select(DangerousRoadCluster)
            .where(DangerousRoadCluster.id == cluster_id)
            .options(
                selectinload(DangerousRoadCluster.cluster_accidents).selectinload(ClusterAccident.accident)
            )
        )
        result = await self._session.execute(stmt)
        obj = result.scalar_one_or_none()
        return _orm_to_detail_dict(obj) if obj is not None else None

    async def list_accidents(
        self,
        cluster_id: int,
        page: int,
        page_size: int,
    ) -> Optional[tuple[int, List[dict]]]:
        exists = (
            await self._session.execute(
                select(DangerousRoadCluster.id).where(DangerousRoadCluster.id == cluster_id)
            )
        ).scalar_one_or_none()
        if exists is None:
            return None

        stmt = (
            select(ClusterAccident)
            .where(ClusterAccident.cluster_id == cluster_id)
            .options(selectinload(ClusterAccident.accident))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = (await self._session.execute(stmt)).scalars().all()
        total = (
            await self._session.execute(
                select(func.count()).where(ClusterAccident.cluster_id == cluster_id)
            )
        ).scalar_one()
        return total, [
            {"accident_id": ca.accident_id, "distance_to_road_m": ca.distance_to_road_m}
            for ca in items
        ]


class NullClusterRepository(ClusterRepository):
    """No-op implementation used when no database is available (e.g. data_source=csv)."""

    async def compute_convex_hull(self, _points: List[AccidentPoint]) -> Optional[str]:
        return None

    async def save_cluster(self, data: ClusterData) -> None:
        logger.debug("NullClusterRepository: skipping persistence for cluster label=%d", data.dbscan_label)

    async def delete_by_params(self, eps_meters: float, min_samples: int) -> None:
        logger.debug("NullClusterRepository: skipping delete for eps=%.0f, min_samples=%d", eps_meters, min_samples)

    async def list_clusters(self) -> List[dict]:
        return []

    async def get_cluster(self, _cluster_id: int) -> Optional[dict]:
        return None

    async def list_accidents(
        self,
        _cluster_id: int,
        _page: int,
        _page_size: int,
    ) -> Optional[tuple[int, List[dict]]]:
        return None


# ─── Module-level in-memory store (survives requests, resets on restart) ───────

_CLUSTER_STORE: Dict[int, dict] = {}
_CLUSTER_COUNTER: int = 0


class InMemoryClusterRepository(ClusterRepository):
    """
    Stores clusters in a module-level dict.
    Useful in CSV / no-DB mode — data survives individual requests but is lost on restart.
    """

    async def compute_convex_hull(self, points: List[AccidentPoint]) -> Optional[str]:
        if len(points) < 3:
            return None
        try:
            from shapely.geometry import MultiPoint
            from shapely import wkt as shapely_wkt
            hull = MultiPoint([(p.lng, p.lat) for p in points]).convex_hull
            if hull.geom_type not in ("Point", "LineString"):
                return shapely_wkt.dumps(hull)
        except Exception:
            pass
        return None

    async def save_cluster(self, data: ClusterData) -> None:
        global _CLUSTER_COUNTER
        _CLUSTER_COUNTER += 1
        cluster_id = _CLUSTER_COUNTER
        now = datetime.now(timezone.utc)

        lats = [p.lat for p in data.accidents]
        lons = [p.lng for p in data.accidents]
        fatalities_total = sum(p.fatalities for p in data.accidents)
        serious_total = sum(p.serious_injuries for p in data.accidents)
        minor_total = sum(p.minor_injuries for p in data.accidents)
        damage_total = sum(p.total_material_damage for p in data.accidents)
        score = _severity_score(len(data.accidents), fatalities_total, serious_total, minor_total, damage_total)

        road_numbers = [p.road_number for p in data.accidents if p.road_number]
        dominant_road_num = max(set(road_numbers), key=road_numbers.count) if road_numbers else data.snap.road_ref
        road_cats = [p.road_category for p in data.accidents if p.road_category]
        dominant_road_cat = max(set(road_cats), key=road_cats.count) if road_cats else data.snap.highway

        road_lat, road_lng = None, None
        if data.snap.road_point_wkt:
            try:
                coords = data.snap.road_point_wkt.replace("POINT(", "").replace(")", "").strip().split()
                road_lng, road_lat = float(coords[0]), float(coords[1])
            except Exception:
                pass

        accidents = [
            {
                "accident_id": p.accident_id,
                "distance_to_road_m": _haversine_m(p.lat, p.lng, road_lat, road_lng) if road_lat is not None else None,
                "accident": None,
            }
            for p in data.accidents
        ]

        _CLUSTER_STORE[cluster_id] = {
            "id": cluster_id,
            "run_id": data.run_id,
            "dbscan_label": data.dbscan_label,
            "eps_meters": data.eps_meters,
            "min_samples": data.min_samples,
            "accident_count": len(data.accidents),
            "fatalities_total": fatalities_total,
            "serious_injuries_total": serious_total,
            "minor_injuries_total": minor_total,
            "total_material_damage": damage_total,
            "severity_score": score,
            "road_name": data.snap.road_name,
            "road_number": dominant_road_num,
            "road_category": dominant_road_cat,
            "bbox_min_lat": min(lats),
            "bbox_max_lat": max(lats),
            "bbox_min_lng": min(lons),
            "bbox_max_lng": max(lons),
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "centroid_geojson": {"type": "Point", "coordinates": [data.centroid_lng, data.centroid_lat]},
            "road_point_geojson": _wkt_to_geojson(data.snap.road_point_wkt),
            "road_segment_geojson": _wkt_to_geojson(data.snap.road_segment_wkt),
            "convex_hull_geojson": _wkt_to_geojson(data.convex_hull_wkt),
            "accidents": accidents,
        }
        logger.debug("InMemoryClusterRepository: saved cluster id=%d label=%d", cluster_id, data.dbscan_label)

    async def delete_by_params(self, eps_meters: float, min_samples: int) -> None:
        ids_to_delete = [
            k for k, v in _CLUSTER_STORE.items()
            if v["eps_meters"] == eps_meters and v["min_samples"] == min_samples
        ]
        for k in ids_to_delete:
            del _CLUSTER_STORE[k]
        logger.debug("InMemoryClusterRepository: deleted %d clusters", len(ids_to_delete))

    async def list_clusters(self) -> List[dict]:
        return list(_CLUSTER_STORE.values())

    async def get_cluster(self, cluster_id: int) -> Optional[dict]:
        return _CLUSTER_STORE.get(cluster_id)

    async def list_accidents(
        self,
        cluster_id: int,
        page: int,
        page_size: int,
    ) -> Optional[tuple[int, List[dict]]]:
        cluster = _CLUSTER_STORE.get(cluster_id)
        if cluster is None:
            return None
        all_accidents = cluster.get("accidents", [])
        total = len(all_accidents)
        start = (page - 1) * page_size
        return total, all_accidents[start : start + page_size]
