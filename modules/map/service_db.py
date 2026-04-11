from datetime import datetime
from typing import List
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session
from geoalchemy2.functions import ST_AsGeoJSON
import json

from models import RoadSegment, TrafficJam, Accident, Alert, Restriction
from modules.map.schema import (
    RoadSegmentResponse,
    SegmentStatistics,
    StreetSegmentsResponse,
    AccidentResponse,
    AccidentsResponse,
    Polyline
)
from core.logging_config import get_logger

logger = get_logger(__name__)


def parse_geojson_to_coordinates(geojson_str: str) -> Polyline:
    """Convert PostGIS GeoJSON to coordinate list"""
    geojson = json.loads(geojson_str)
    coords = geojson.get("coordinates", [])
    if geojson.get("type") == "Point":
        return [coords]
    return coords


def get_segment_statistics_from_db(
    db: Session,
    segment_id: int,
    date_from: datetime,
    date_to: datetime
) -> SegmentStatistics:
    """Calculate event statistics for a road segment within date range from database"""

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


def get_street_segments_from_db(
    db: Session,
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> StreetSegmentsResponse:
    """Get road segments for given streets with event statistics from database"""

    query = db.query(
        RoadSegment.id,
        RoadSegment.osm_id,
        RoadSegment.name,
        RoadSegment.road_ref,
        RoadSegment.road_class,
        RoadSegment.city,
        RoadSegment.max_speed,
        ST_AsGeoJSON(RoadSegment.geog).label('geog_json')
    )

    if street_names:
        query = query.filter(RoadSegment.name.in_(street_names))

    segments_query = query.all()

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


def get_accidents_from_db(
    db: Session,
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> AccidentsResponse:
    """Get accidents for given streets and date range from database"""

    query = db.query(Accident).filter(
        Accident.event_time >= date_from,
        Accident.event_time <= date_to
    )

    if street_names:
        query = query.filter(Accident.street_name.in_(street_names))

    accidents_query = query.all()

    accidents_response = []
    for accident in accidents_query:
        location = None
        if accident.location_geog:
            location_json = db.scalar(ST_AsGeoJSON(accident.location_geog))
            location = parse_geojson_to_coordinates(location_json)

        accidents_response.append(
            AccidentResponse(
                id=accident.id,
                event_time=accident.event_time,
                location=location,
                city=accident.city,
                street_name=accident.street_name,
                road_number=accident.road_number,
                accident_type=accident.accident_type,
                accident_subtype=accident.accident_subtype,
                severity=accident.severity,
                fatalities_count=accident.fatalities_count,
                serious_injuries=accident.serious_injuries,
                minor_injuries=accident.minor_injuries,
                persons_involved=accident.persons_involved,
                vehicles_involved=accident.vehicles_involved,
                damage_czk=accident.damage_czk,
                weather_condition=accident.weather_condition,
                road_surface=accident.road_surface,
                light_condition=accident.light_condition,
                alcohol_involved=accident.alcohol_involved,
                drugs_involved=accident.drugs_involved,
                segment_id=accident.segment_id
            )
        )

    logger.info(f"Loaded {len(accidents_response)} accidents from database")

    return AccidentsResponse(
        accidents=accidents_response,
        total_count=len(accidents_response),
        date_from=date_from,
        date_to=date_to
    )

