from datetime import datetime
from typing import List, Optional
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session
from geoalchemy2.functions import ST_AsGeoJSON
import json

from modules.map.model import RoadSegment, TrafficJam, Accident, Alert, Restriction
from modules.map.schema import (
    RoadSegmentResponse,
    SegmentStatistics,
    StreetSegmentsResponse,
    Polyline
)
from core.example_data import ExampleDataLoader
from core.logging_config import get_logger

logger = get_logger(__name__)


def parse_geojson_to_coordinates(geojson_str: str) -> Polyline:
    """Convert PostGIS LineString GeoJSON to coordinate list [[lng, lat], ...]"""
    geojson = json.loads(geojson_str)
    return geojson.get("coordinates", [])


def get_segment_statistics_from_db(
    db: Session,
    segment_id: int,
    date_from: datetime,
    date_to: datetime
) -> SegmentStatistics:
    """Calculate event statistics for a road segment within date range from a database"""

    jams_count = db.query(func.count(TrafficJam.id)).filter(
        TrafficJam.segment_id == segment_id,
        TrafficJam.event_time >= date_from,
        TrafficJam.event_time <= date_to
    ).scalar() or 0

    accidents_count = db.query(func.count(Accident.id)).filter(
        Accident.segment_id == segment_id,
        Accident.event_time >= date_from,
        Accident.event_time <= date_to
    ).scalar() or 0

    alerts_count = db.query(func.count(Alert.id)).filter(
        Alert.segment_id == segment_id,
        or_(
            and_(Alert.first_seen >= date_from, Alert.first_seen <= date_to),
            and_(Alert.last_seen >= date_from, Alert.last_seen <= date_to),
            and_(Alert.first_seen <= date_from, Alert.last_seen >= date_to)
        )
    ).scalar() or 0

    restrictions_count = db.query(func.count(Restriction.id)).filter(
        Restriction.segment_id == segment_id,
        or_(
            and_(Restriction.valid_from >= date_from, Restriction.valid_from <= date_to),
            and_(Restriction.valid_to >= date_from, Restriction.valid_to <= date_to),
            and_(Restriction.valid_from <= date_from, Restriction.valid_to >= date_to),
            and_(Restriction.valid_from.is_(None), Restriction.valid_to.is_(None))
        )
    ).scalar() or 0

    return SegmentStatistics(
        jams_count=jams_count,
        accidents_count=accidents_count,
        alerts_count=alerts_count,
        restrictions_count=restrictions_count
    )


def get_segment_statistics_from_example(
    segment_id: int,
    date_from: datetime,
    date_to: datetime
) -> SegmentStatistics:
    """Calculate event statistics from example data"""

    try:
        jams = ExampleDataLoader.get_jams([segment_id], date_from, date_to)
        accidents = ExampleDataLoader.get_accidents([segment_id], date_from, date_to)
        alerts = ExampleDataLoader.get_alerts([segment_id], date_from, date_to)
        restrictions = ExampleDataLoader.get_restrictions([segment_id], date_from, date_to)

        return SegmentStatistics(
            jams_count=len(jams),
            accidents_count=len(accidents),
            alerts_count=len(alerts),
            restrictions_count=len(restrictions)
        )
    except TypeError as e:
        logger.warning(f"Datetime comparison error for segment {segment_id}: {e}")
        return SegmentStatistics(
            jams_count=0,
            accidents_count=0,
            alerts_count=0,
            restrictions_count=0
        )


def get_street_segments_from_db(
    db: Session,
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> StreetSegmentsResponse:
    """Get all road segments for given streets with event statistics from database"""

    segments_query = db.query(
        RoadSegment.id,
        RoadSegment.osm_id,
        RoadSegment.name,
        RoadSegment.road_ref,
        RoadSegment.road_class,
        RoadSegment.city,
        RoadSegment.max_speed,
        ST_AsGeoJSON(RoadSegment.geog).label('geog_json')
    ).filter(
        RoadSegment.name.in_(street_names)
    ).all()

    segments_response = []
    for segment in segments_query:
        coordinates = parse_geojson_to_coordinates(segment.geog_json)
        statistics = get_segment_statistics_from_db(db, segment.id, date_from, date_to)

        segments_response.append(
            RoadSegmentResponse(
                id=segment.id,
                osm_id=segment.osm_id,
                name=segment.name,
                road_ref=segment.road_ref,
                road_class=segment.road_class,
                city=segment.city,
                max_speed=segment.max_speed,
                coordinates=coordinates,
                statistics=statistics
            )
        )

    logger.info(f"Loaded {len(segments_response)} segments from database for streets: {street_names}")

    return StreetSegmentsResponse(
        segments=segments_response,
        total_count=len(segments_response),
        date_from=date_from,
        date_to=date_to
    )


def get_street_segments_from_example(
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> StreetSegmentsResponse:
    """Get road segments from example data as fallback"""

    segments_data = ExampleDataLoader.get_road_segments(street_names)

    segments_response = []
    for segment in segments_data:
        segment_id = segment.get("id")
        statistics = get_segment_statistics_from_example(segment_id, date_from, date_to)

        coordinates = segment.get("geog")
        if not coordinates:
            logger.warning(f"No geometry found for segment {segment_id}, skipping")
            continue

        road_ref = segment.get("road_ref")
        segments_response.append(
            RoadSegmentResponse(
                id=segment_id,
                osm_id=segment.get("osm_id"),
                name=segment.get("name"),
                road_ref=str(road_ref) if road_ref is not None else None,
                road_class=str(segment.get("road_class")),
                city=segment.get("city"),
                max_speed=segment.get("max_speed"),
                coordinates=coordinates,
                statistics=statistics
            )
        )

    logger.info(f"Loaded {len(segments_response)} segments from example data for streets: {street_names}")

    return StreetSegmentsResponse(
        segments=segments_response,
        total_count=len(segments_response),
        date_from=date_from,
        date_to=date_to
    )


def get_street_segments(
    db: Optional[Session],
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> StreetSegmentsResponse:
    """Get street segments with automatic fallback to example data"""

    if db is None:
        logger.warning("Database unavailable, using example data fallback")
        return get_street_segments_from_example(street_names, date_from, date_to)

    try:
        return get_street_segments_from_db(db, street_names, date_from, date_to)
    except Exception as e:
        logger.error(f"Database query failed: {e}. Falling back to example data")
        return get_street_segments_from_example(street_names, date_from, date_to)


