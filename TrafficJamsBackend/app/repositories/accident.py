"""
AccidentRepository implementations:
  - PostgresAccidentRepository  — reads from the `accidents` table via SQLAlchemy
  - CsvAccidentRepository       — reads from a CSV file (e.g. police_data.csv)
"""
from __future__ import annotations

import logging
from typing import List, Optional

import pandas as pd
import shapely
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_X, ST_Y

from app.domain import AccidentPoint
from app.models.accident import Accident
from app.repositories.base import AccidentRepository
from app.schemas.cluster import ClusterRunRequest

logger = logging.getLogger(__name__)


class PostgresAccidentRepository(AccidentRepository):
    """Reads accidents from PostgreSQL using an async SQLAlchemy session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_accident_points(self, request: ClusterRunRequest) -> List[AccidentPoint]:
        stmt = select(
            Accident.id,
            ST_Y(Accident.location_geog).label("lat"),
            ST_X(Accident.location_geog).label("lng"),
            Accident.fatalities_count,
            Accident.serious_injuries,
            Accident.minor_injuries,
            Accident.damage_czk,
            Accident.road_type_code,
            Accident.road_number,
        ).where(Accident.location_geog.isnot(None))

        if request.date_from is not None:
            stmt = stmt.where(Accident.event_time >= request.date_from)
        if request.date_to is not None:
            stmt = stmt.where(Accident.event_time <= request.date_to)

        result = await self._session.execute(stmt)
        rows = result.fetchall()

        points: List[AccidentPoint] = []
        for row in rows:
            if row.lat is None or row.lng is None:
                continue
            points.append(AccidentPoint(
                accident_id=row.id,
                lat=float(row.lat),
                lng=float(row.lng),
                fatalities=int(row.fatalities_count or 0),
                serious_injuries=int(row.serious_injuries or 0),
                minor_injuries=int(row.minor_injuries or 0),
                total_material_damage=int(row.damage_czk or 0),
                road_category=row.road_type_code,
                road_number=row.road_number,
            ))

        logger.info("PostgresAccidentRepository: loaded %d accident points.", len(points))
        return points


class CsvAccidentRepository(AccidentRepository):
    """
    Reads accidents from a CSV file (e.g. police_data.csv).

    Expected columns:
      id, location_geog (EWKB hex, SRID 4326), event_time,
      fatalities_count, serious_injuries, minor_injuries, damage_czk,
      road_type_code, road_number
    """

    def __init__(self, csv_path: str) -> None:
        self._csv_path = csv_path
        self._df: Optional[pd.DataFrame] = None

    def _load(self) -> pd.DataFrame:
        if self._df is None:
            self._df = pd.read_csv(self._csv_path)
            logger.info("CsvAccidentRepository: loaded %d rows from %s", len(self._df), self._csv_path)
        return self._df

    async def get_accident_points(self, request: ClusterRunRequest) -> List[AccidentPoint]:
        df = self._load().copy()

        if request.date_from or request.date_to:
            df["event_time"] = pd.to_datetime(df["event_time"], utc=True)
            if request.date_from:
                df = df[df["event_time"].dt.date >= request.date_from]
            if request.date_to:
                df = df[df["event_time"].dt.date <= request.date_to]

        points: List[AccidentPoint] = []
        for _, row in df.iterrows():
            hex_str = row.get("location_geog")
            if not hex_str or pd.isna(hex_str):
                continue
            try:
                geom = shapely.from_wkb(bytes.fromhex(str(hex_str)))
                road_number = row.get("road_number")
                points.append(AccidentPoint(
                    accident_id=str(row["id"]),
                    lat=float(geom.y),
                    lng=float(geom.x),
                    fatalities=int(row.get("fatalities_count", 0) or 0),
                    serious_injuries=int(row.get("serious_injuries", 0) or 0),
                    minor_injuries=int(row.get("minor_injuries", 0) or 0),
                    total_material_damage=int(row.get("damage_czk", 0) or 0),
                    road_category=str(row["road_type_code"]) if not pd.isna(row.get("road_type_code", float("nan"))) else None,
                    road_number=str(road_number) if road_number and not pd.isna(road_number) else None,
                ))
            except Exception as exc:
                logger.warning("CsvAccidentRepository: skipping row id=%s — %s", row.get("id"), exc)

        logger.info("CsvAccidentRepository: returning %d accident points.", len(points))
        return points
