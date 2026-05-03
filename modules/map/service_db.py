from datetime import datetime
from typing import List, Optional
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session
from geoalchemy2.functions import ST_AsGeoJSON
import json

from models import RoadSegment, TrafficJam, Accident, Alert, Restriction, EventLink
from modules.map.schema import (
    RoadSegmentResponse,
    SegmentStatistics,
    StreetSegmentsResponse,
    RoadSegmentByIdResponse,
    AccidentResponse,
    AccidentsResponse,
    AlertResponse,
    AlertsResponse,
    JamResponse,
    JamsResponse,
    RestrictionResponse,
    RestrictionsResponse,
    EventLinkResponse,
    EventLinksResponse,
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
    jams_count = db.query(func.count(TrafficJam.id)).filter(
        TrafficJam.segment_id == segment_id,
        TrafficJam.first_seen >= date_from,
        TrafficJam.first_seen <= date_to
    ).scalar() or 0

    accidents_count = db.query(func.count(Accident.id)).filter(
        Accident.segment_id == segment_id,
        Accident.first_seen >= date_from,
        Accident.first_seen <= date_to
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
    logger.info(f"[segments] querying DB: streets={street_names}, date_from={date_from}, date_to={date_to}")

    total_count = db.query(func.count(RoadSegment.id)).scalar()
    logger.info(f"[segments] total rows in road_segments table: {total_count}")

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
    logger.info(f"[segments] raw rows from DB: {len(segments_query)}")

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

    logger.info(f"[segments] built {len(segments_response)} response objects")

    return StreetSegmentsResponse(
        segments=segments_response,
        total_count=len(segments_response),
        date_from=date_from,
        date_to=date_to
    )


def get_road_segment_by_id_from_db(
    db: Session,
    segment_id: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> Optional[RoadSegmentByIdResponse]:
    logger.info(f"[segment-by-id] querying DB: segment_id={segment_id}, date_from={date_from}, date_to={date_to}")

    segment = db.query(
        RoadSegment.id,
        RoadSegment.osm_id,
        RoadSegment.name,
        RoadSegment.road_ref,
        RoadSegment.road_class,
        RoadSegment.city,
        RoadSegment.max_speed,
        ST_AsGeoJSON(RoadSegment.geog).label('geog_json')
    ).filter(RoadSegment.id == segment_id).first()

    if not segment:
        logger.warning(f"[segment-by-id] segment {segment_id} not found in DB")
        return None

    coordinates = parse_geojson_to_coordinates(segment.geog_json)

    statistics = SegmentStatistics()
    if date_from and date_to:
        statistics = get_segment_statistics_from_db(db, segment_id, date_from, date_to)

    logger.info(f"[segment-by-id] found segment {segment_id}, stats: {statistics}")

    return RoadSegmentByIdResponse(
        segment=RoadSegmentResponse(
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


def get_accidents_from_db(
    db: Session,
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> AccidentsResponse:
    logger.info(f"[accidents] querying DB: streets={street_names}, date_from={date_from}, date_to={date_to}")

    total_count = db.query(func.count(Accident.id)).scalar()
    logger.info(f"[accidents] total rows in accidents table (no filter): {total_count}")

    date_count = db.query(func.count(Accident.id)).filter(
        Accident.first_seen >= date_from,
        Accident.first_seen <= date_to
    ).scalar()
    logger.info(f"[accidents] rows matching date filter only (first_seen): {date_count}")

    if street_names:
        street_count = db.query(func.count(Accident.id)).filter(
            Accident.street_name.in_(street_names)
        ).scalar()
        logger.info(f"[accidents] rows matching street filter only: {street_count}")

    query = db.query(Accident).filter(
        Accident.first_seen >= date_from,
        Accident.first_seen <= date_to
    )

    if street_names:
        query = query.filter(Accident.street_name.in_(street_names))

    accidents_query = query.all()
    logger.info(f"[accidents] raw rows from DB: {len(accidents_query)}")

    accidents_response = []
    for accident in accidents_query:
        location = None
        if accident.location_geog:
            location_json = db.scalar(ST_AsGeoJSON(accident.location_geog))
            location = parse_geojson_to_coordinates(location_json)

        accidents_response.append(
            AccidentResponse(
                id=accident.id,
                event_time=accident.first_seen,
                ingested_at=accident.ingested_at,
                first_seen=accident.first_seen,
                last_seen=accident.last_seen,
                location=location,
                city=accident.city,
                street_name=accident.street_name,
                road_number=accident.road_number,
                road_type_code=accident.road_type_code,
                accident_type=accident.accident_type,
                accident_subtype=accident.accident_subtype,
                cause_primary=accident.cause_primary,
                cause_secondary=accident.cause_secondary,
                severity=accident.severity,
                fatalities_count=accident.fatalities_count,
                serious_injuries=accident.serious_injuries,
                minor_injuries=accident.minor_injuries,
                persons_involved=accident.persons_involved,
                vehicles_involved=accident.vehicles_involved,
                damage_czk=accident.damage_czk,
                damage_category=accident.damage_category,
                weather_condition=accident.weather_condition,
                road_surface=accident.road_surface,
                light_condition=accident.light_condition,
                road_condition=accident.road_condition,
                vehicle_types=accident.vehicle_types,
                alcohol_involved=accident.alcohol_involved,
                drugs_involved=accident.drugs_involved,
                alcohol_level=accident.alcohol_level,
                quality_score=accident.quality_score,
                segment_id=accident.segment_id
            )
        )

    logger.info(f"[accidents] built {len(accidents_response)} response objects")

    return AccidentsResponse(
        accidents=accidents_response,
        total_count=len(accidents_response),
        date_from=date_from,
        date_to=date_to
    )


def get_alerts_from_db(
    db: Session,
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> AlertsResponse:
    logger.info(f"[alerts] querying DB: streets={street_names}, date_from={date_from}, date_to={date_to}")

    total_count = db.query(func.count(Alert.id)).scalar()
    logger.info(f"[alerts] total rows in alerts table (no filter): {total_count}")

    date_count = db.query(func.count(Alert.id)).filter(
        or_(
            and_(Alert.first_seen >= date_from, Alert.first_seen <= date_to),
            and_(Alert.last_seen >= date_from, Alert.last_seen <= date_to),
            and_(Alert.first_seen <= date_from, Alert.last_seen >= date_to)
        )
    ).scalar()
    logger.info(f"[alerts] rows matching date filter only (first_seen/last_seen): {date_count}")

    if street_names:
        street_count = db.query(func.count(Alert.id)).filter(
            Alert.street_name.in_(street_names)
        ).scalar()
        logger.info(f"[alerts] rows matching street filter only: {street_count}")

    query = db.query(Alert).filter(
        or_(
            and_(Alert.first_seen >= date_from, Alert.first_seen <= date_to),
            and_(Alert.last_seen >= date_from, Alert.last_seen <= date_to),
            and_(Alert.first_seen <= date_from, Alert.last_seen >= date_to)
        )
    )

    if street_names:
        query = query.filter(Alert.street_name.in_(street_names))

    alerts_query = query.all()
    logger.info(f"[alerts] raw rows from DB: {len(alerts_query)}")

    alerts_response = []
    for alert in alerts_query:
        location = None
        if alert.location_geog:
            location_json = db.scalar(ST_AsGeoJSON(alert.location_geog))
            location = parse_geojson_to_coordinates(location_json)

        road_number = alert.road_number
        alerts_response.append(
            AlertResponse(
                id=alert.id,
                ingested_at=alert.ingested_at,
                first_seen=alert.first_seen,
                last_seen=alert.last_seen,
                location=location,
                city=alert.city,
                street_name=alert.street_name,
                road_number=str(road_number) if road_number is not None and road_number != "" else None,
                road_type_code=alert.road_type_code,
                alert_type=alert.alert_type,
                alert_subtype=alert.alert_subtype,
                severity=alert.severity,
                description=alert.description,
                active=alert.active,
                quality_score=alert.quality_score,
                segment_id=alert.segment_id
            )
        )

    logger.info(f"[alerts] built {len(alerts_response)} response objects")

    return AlertsResponse(
        alerts=alerts_response,
        total_count=len(alerts_response),
        date_from=date_from,
        date_to=date_to
    )


def get_jams_from_db(
    db: Session,
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> JamsResponse:
    logger.info(f"[jams] querying DB: streets={street_names}, date_from={date_from}, date_to={date_to}")

    total_count = db.query(func.count(TrafficJam.id)).scalar()
    logger.info(f"[jams] total rows in traffic_jams table (no filter): {total_count}")

    date_count = db.query(func.count(TrafficJam.id)).filter(
        TrafficJam.first_seen >= date_from,
        TrafficJam.first_seen <= date_to
    ).scalar()
    logger.info(f"[jams] rows matching date filter only (first_seen): {date_count}")

    if street_names:
        street_count = db.query(func.count(TrafficJam.id)).filter(
            TrafficJam.street_name.in_(street_names)
        ).scalar()
        logger.info(f"[jams] rows matching street filter only: {street_count}")

    query = db.query(TrafficJam).filter(
        TrafficJam.first_seen >= date_from,
        TrafficJam.first_seen <= date_to
    )

    if street_names:
        query = query.filter(TrafficJam.street_name.in_(street_names))

    jams_query = query.all()
    logger.info(f"[jams] raw rows from DB: {len(jams_query)}")

    jams_response = []
    for jam in jams_query:
        jam_line = None
        if jam.jam_line_geog:
            jam_line_json = db.scalar(ST_AsGeoJSON(jam.jam_line_geog))
            jam_line = parse_geojson_to_coordinates(jam_line_json)

        road_number = jam.road_number
        jams_response.append(
            JamResponse(
                id=jam.id,
                event_time=jam.first_seen,
                ingested_at=jam.ingested_at,
                first_seen=jam.first_seen,
                last_seen=jam.last_seen,
                jam_line=jam_line,
                city=jam.city,
                street_name=jam.street_name,
                road_number=str(road_number) if road_number is not None and road_number != "" else None,
                road_type_code=jam.road_type_code,
                delay_seconds=jam.delay_seconds,
                length_m=jam.length_m,
                speed_kmh=jam.speed_kmh,
                speed_normal_kmh=jam.speed_normal_kmh,
                severity=jam.severity,
                quality_score=jam.quality_score,
                segment_id=jam.segment_id
            )
        )

    logger.info(f"[jams] built {len(jams_response)} response objects")

    return JamsResponse(
        jams=jams_response,
        total_count=len(jams_response),
        date_from=date_from,
        date_to=date_to
    )


def get_restrictions_from_db(
    db: Session,
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> RestrictionsResponse:
    logger.info(f"[restrictions] querying DB: streets={street_names}, date_from={date_from}, date_to={date_to}")

    total_count = db.query(func.count(Restriction.id)).scalar()
    logger.info(f"[restrictions] total rows in restrictions table (no filter): {total_count}")

    date_count = db.query(func.count(Restriction.id)).filter(
        or_(
            and_(Restriction.valid_from >= date_from, Restriction.valid_from <= date_to),
            and_(Restriction.valid_to >= date_from, Restriction.valid_to <= date_to),
            and_(Restriction.valid_from <= date_from, Restriction.valid_to >= date_to),
            and_(Restriction.valid_from.is_(None), Restriction.valid_to.is_(None))
        )
    ).scalar()
    logger.info(f"[restrictions] rows matching date filter only (valid_from/valid_to): {date_count}")

    if street_names:
        street_count = db.query(func.count(Restriction.id)).filter(
            Restriction.street_name.in_(street_names)
        ).scalar()
        logger.info(f"[restrictions] rows matching street filter only: {street_count}")

    query = db.query(Restriction).filter(
        or_(
            and_(Restriction.valid_from >= date_from, Restriction.valid_from <= date_to),
            and_(Restriction.valid_to >= date_from, Restriction.valid_to <= date_to),
            and_(Restriction.valid_from <= date_from, Restriction.valid_to >= date_to),
            and_(Restriction.valid_from.is_(None), Restriction.valid_to.is_(None))
        )
    )

    if street_names:
        query = query.filter(Restriction.street_name.in_(street_names))

    restrictions_query = query.all()
    logger.info(f"[restrictions] raw rows from DB: {len(restrictions_query)}")

    restrictions_response = []
    for restriction in restrictions_query:
        location_point = None
        location_line = None

        if restriction.location_point_geog:
            point_json = db.scalar(ST_AsGeoJSON(restriction.location_point_geog))
            location_point = parse_geojson_to_coordinates(point_json)

        if restriction.location_line_geog:
            line_json = db.scalar(ST_AsGeoJSON(restriction.location_line_geog))
            location_line = parse_geojson_to_coordinates(line_json)

        road_number = restriction.road_number
        restrictions_response.append(
            RestrictionResponse(
                id=restriction.id,
                external_version=restriction.external_version,
                event_time=None,
                ingested_at=restriction.ingested_at,
                valid_from=restriction.valid_from,
                valid_to=restriction.valid_to,
                first_seen=restriction.first_seen,
                last_seen=restriction.last_seen,
                location_point=location_point,
                location_line=location_line,
                city=restriction.city,
                street_name=restriction.street_name,
                road_number=str(road_number) if road_number is not None and road_number != "" else None,
                road_type_code=restriction.road_type_code,
                km_from=restriction.km_from,
                km_to=restriction.km_to,
                direction=restriction.direction,
                restriction_type=restriction.restriction_type,
                restriction_subtype=restriction.restriction_subtype,
                urgency=restriction.urgency,
                probability=restriction.probability,
                severity=restriction.severity,
                status=restriction.status,
                max_speed_kmh=restriction.max_speed_kmh,
                description_cs=restriction.description_cs,
                quality_score=restriction.quality_score,
                segment_id=restriction.segment_id
            )
        )

    logger.info(f"[restrictions] built {len(restrictions_response)} response objects")

    return RestrictionsResponse(
        restrictions=restrictions_response,
        total_count=len(restrictions_response),
        date_from=date_from,
        date_to=date_to
    )


def get_event_links_from_db(
    db: Session,
    source_type: Optional[str],
    target_type: Optional[str],
    date_from: datetime,
    date_to: datetime
) -> EventLinksResponse:
    logger.info(f"[event-links] querying DB: source_type={source_type}, target_type={target_type}, date_from={date_from}, date_to={date_to}")

    total_count = db.query(func.count(EventLink.id)).scalar()
    logger.info(f"[event-links] total rows in event_links table (no filter): {total_count}")

    query = db.query(EventLink).filter(
        EventLink.created_at >= date_from,
        EventLink.created_at <= date_to
    )

    if source_type:
        query = query.filter(EventLink.source_type == source_type)
    if target_type:
        query = query.filter(EventLink.target_type == target_type)

    links = query.all()
    logger.info(f"[event-links] raw rows from DB: {len(links)}")

    links_response = [
        EventLinkResponse(
            id=link.id,
            source_type=link.source_type,
            source_id=link.source_id,
            target_type=link.target_type,
            target_id=link.target_id,
            link_type=link.link_type,
            confidence=link.confidence,
            description=link.description,
            created_at=link.created_at
        )
        for link in links
    ]

    logger.info(f"[event-links] built {len(links_response)} response objects")

    return EventLinksResponse(
        event_links=links_response,
        total_count=len(links_response),
        date_from=date_from,
        date_to=date_to
    )


def get_event_links_by_source_from_db(
    db: Session,
    source_ids: List[int],
    source_type: Optional[str],
    date_from: datetime,
    date_to: datetime
) -> EventLinksResponse:
    logger.info(f"[event-links-by-source] querying DB: source_ids={source_ids}, source_type={source_type}, date_from={date_from}, date_to={date_to}")

    query = db.query(EventLink).filter(
        EventLink.source_id.in_(source_ids),
        EventLink.created_at >= date_from,
        EventLink.created_at <= date_to
    )

    if source_type:
        query = query.filter(EventLink.source_type == source_type)

    links = query.all()
    logger.info(f"[event-links-by-source] raw rows from DB: {len(links)}")

    links_response = [
        EventLinkResponse(
            id=link.id,
            source_type=link.source_type,
            source_id=link.source_id,
            target_type=link.target_type,
            target_id=link.target_id,
            link_type=link.link_type,
            confidence=link.confidence,
            description=link.description,
            created_at=link.created_at
        )
        for link in links
    ]

    logger.info(f"[event-links-by-source] built {len(links_response)} response objects")

    return EventLinksResponse(
        event_links=links_response,
        total_count=len(links_response),
        date_from=date_from,
        date_to=date_to
    )


def get_event_links_by_target_from_db(
    db: Session,
    target_ids: List[int],
    target_type: Optional[str],
    date_from: datetime,
    date_to: datetime
) -> EventLinksResponse:
    logger.info(f"[event-links-by-target] querying DB: target_ids={target_ids}, target_type={target_type}, date_from={date_from}, date_to={date_to}")

    query = db.query(EventLink).filter(
        EventLink.target_id.in_(target_ids),
        EventLink.created_at >= date_from,
        EventLink.created_at <= date_to
    )

    if target_type:
        query = query.filter(EventLink.target_type == target_type)

    links = query.all()
    logger.info(f"[event-links-by-target] raw rows from DB: {len(links)}")

    links_response = [
        EventLinkResponse(
            id=link.id,
            source_type=link.source_type,
            source_id=link.source_id,
            target_type=link.target_type,
            target_id=link.target_id,
            link_type=link.link_type,
            confidence=link.confidence,
            description=link.description,
            created_at=link.created_at
        )
        for link in links
    ]

    logger.info(f"[event-links-by-target] built {len(links_response)} response objects")

    return EventLinksResponse(
        event_links=links_response,
        total_count=len(links_response),
        date_from=date_from,
        date_to=date_to
    )
