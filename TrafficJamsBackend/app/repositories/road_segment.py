"""
RoadSegmentRepository implementations:
  - PostgresRoadSegmentRepository — queries planet_osm_line via PostGIS
  - CsvRoadSegmentRepository      — reads road_segments.csv, uses shapely STRtree
"""
from __future__ import annotations

import logging
from typing import Optional, List

import math

import pandas as pd
import shapely
from shapely.geometry import Point
from shapely.strtree import STRtree
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import SnapResult
from app.repositories.base import RoadSegmentRepository

logger = logging.getLogger(__name__)

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


class PostgresRoadSegmentRepository(RoadSegmentRepository):
    """
    Snaps to roads using PostGIS ST_ClosestPoint on the road_segments table
    (populated by scripts/load_csv_to_db.py).

    The geometry column (geog) is GEOMETRY(LINESTRING, 4326).
    Casting to ::geography enables meter-based ST_DWithin / ST_Distance.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def snap_to_road(self, lat: float, lng: float, max_distance_m: float) -> SnapResult:
        query = text("""
            WITH input_point AS (
                SELECT ST_SetSRID(ST_MakePoint(:lng, :lat), 4326) AS geom
            ),
            nearby AS (
                SELECT r.geog AS way, r.name, r.road_ref, r.road_class,
                       ST_Distance(r.geog::geography, ip.geom::geography) AS dist_m
                FROM road_segments r, input_point ip
                WHERE ST_DWithin(r.geog::geography, ip.geom::geography, :max_dist)
                ORDER BY dist_m
                LIMIT 1
            )
            SELECT
                ST_AsText(ST_ClosestPoint(nr.way, ip.geom)) AS road_point_wkt,
                ST_AsText(nr.way)                           AS road_segment_wkt,
                nr.name, nr.road_ref, nr.road_class
            FROM nearby nr, input_point ip
            LIMIT 1
        """)
        try:
            # Use a savepoint so a query failure doesn't abort the outer transaction
            async with self._session.begin_nested():
                result = await self._session.execute(
                    query, {"lat": lat, "lng": lng, "max_dist": max_distance_m}
                )
                row = result.fetchone()
            if row is None:
                return SnapResult()
            return SnapResult(
                road_point_wkt=row[0],
                road_segment_wkt=row[1],
                road_name=row[2],
                road_ref=row[3],
                highway=row[4],
            )
        except Exception as exc:
            logger.warning("PostgresRoadSegmentRepository: snap failed — %s", exc)
            return SnapResult()


class CsvRoadSegmentRepository(RoadSegmentRepository):
    """
    Snaps to roads loaded from a CSV file (e.g. road_segments.csv).

    Expected columns:
      id, osm_id, geog (EWKB hex LINESTRING SRID 4326),
      name, road_ref, road_class, city, max_speed
    """

    def __init__(self, csv_path: str) -> None:
        self._csv_path = csv_path
        self._segments: Optional[List] = None
        self._rows: Optional[List[dict]] = None
        self._tree: Optional[STRtree] = None

    def _load(self) -> None:
        if self._segments is not None:
            return
        df = pd.read_csv(self._csv_path)
        segments = []
        rows = []
        for _, row in df.iterrows():
            hex_str = row.get("geog")
            if not hex_str or pd.isna(hex_str):
                continue
            try:
                geom = shapely.from_wkb(bytes.fromhex(str(hex_str)))
                segments.append(geom)
                rows.append(row.to_dict())
            except Exception:
                continue
        self._segments = segments
        self._rows = rows
        self._tree = STRtree(segments)
        logger.info("CsvRoadSegmentRepository: indexed %d road segments from %s", len(segments), self._csv_path)

    async def snap_to_road(self, lat: float, lng: float, max_distance_m: float) -> SnapResult:
        self._load()
        if not self._segments:
            logger.warning("CsvRoadSegmentRepository: no road segments loaded.")
            return SnapResult()

        point = Point(lng, lat)
        nearest_idx = self._tree.nearest(point)
        seg = self._segments[nearest_idx]
        row = self._rows[nearest_idx]

        # Closest point on the segment geometry
        closest_pt = seg.interpolate(seg.project(point))

        # Enforce the max-distance threshold (STRtree.nearest never returns None,
        # so we must check manually using the haversine distance in metres)
        dist_m = _haversine_m(lat, lng, closest_pt.y, closest_pt.x)
        if dist_m > max_distance_m:
            logger.debug(
                "CsvRoadSegmentRepository: nearest road is %.0f m away (max %.0f m) — no snap",
                dist_m, max_distance_m,
            )
            return SnapResult()

        road_point_wkt = f"POINT({closest_pt.x} {closest_pt.y})"
        name = row.get("name")
        road_ref = row.get("road_ref")
        highway = row.get("road_class")

        return SnapResult(
            road_point_wkt=road_point_wkt,
            road_segment_wkt=seg.wkt,
            road_name=name if name and not pd.isna(name) else None,
            road_ref=road_ref if road_ref and not pd.isna(road_ref) else None,
            highway=highway if highway and not pd.isna(highway) else None,
        )
