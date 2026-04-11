from datetime import datetime
from typing import List

from modules.map.schema import (
    RoadSegmentResponse,
    SegmentStatistics,
    StreetSegmentsResponse,
    AccidentResponse,
    AccidentsResponse,
    AlertResponse,
    AlertsResponse,
    JamResponse,
    JamsResponse,
    RestrictionResponse,
    RestrictionsResponse
)
from core.example_data import ExampleDataLoader
from core.logging_config import get_logger

logger = get_logger(__name__)


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


def get_street_segments_from_example(
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> StreetSegmentsResponse:
    """Get road segments from example data"""

    segments_data = ExampleDataLoader.get_road_segments(street_names if street_names else None)

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

    logger.info(f"Loaded {len(segments_response)} segments from example data")

    return StreetSegmentsResponse(
        segments=segments_response,
        total_count=len(segments_response),
        date_from=date_from,
        date_to=date_to
    )


def get_accidents_from_example(
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> AccidentsResponse:
    """Get accidents from example data"""

    accidents_data = ExampleDataLoader.get_accidents(None, date_from, date_to)

    if street_names:
        accidents_data = [a for a in accidents_data if a.get("street_name") in street_names]

    accidents_response = []
    for accident in accidents_data:
        location = accident.get("location_geog")
        road_number = accident.get("road_number")

        accidents_response.append(
            AccidentResponse(
                id=accident.get("id"),
                event_time=accident.get("event_time"),
                location=location,
                city=accident.get("city"),
                street_name=accident.get("street_name"),
                road_number=str(road_number) if road_number is not None and road_number != "" else None,
                accident_type=accident.get("accident_type"),
                accident_subtype=accident.get("accident_subtype"),
                severity=accident.get("severity"),
                fatalities_count=accident.get("fatalities_count"),
                serious_injuries=accident.get("serious_injuries"),
                minor_injuries=accident.get("minor_injuries"),
                persons_involved=accident.get("persons_involved"),
                vehicles_involved=accident.get("vehicles_involved"),
                damage_czk=accident.get("damage_czk"),
                weather_condition=accident.get("weather_condition"),
                road_surface=accident.get("road_surface"),
                light_condition=accident.get("light_condition"),
                alcohol_involved=accident.get("alcohol_involved"),
                drugs_involved=accident.get("drugs_involved"),
                segment_id=accident.get("segment_id")
            )
        )

    logger.info(f"Loaded {len(accidents_response)} accidents from example data")

    return AccidentsResponse(
        accidents=accidents_response,
        total_count=len(accidents_response),
        date_from=date_from,
        date_to=date_to
    )


def get_alerts_from_example(
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> AlertsResponse:
    """Get alerts from example data"""

    alerts_data = ExampleDataLoader.get_alerts(None, date_from, date_to)

    if street_names:
        alerts_data = [a for a in alerts_data if a.get("street_name") in street_names]

    alerts_response = []
    for alert in alerts_data:
        location = alert.get("location_geog")
        road_number = alert.get("road_number")

        alerts_response.append(
            AlertResponse(
                id=alert.get("id"),
                first_seen=alert.get("first_seen"),
                last_seen=alert.get("last_seen"),
                location=location,
                city=alert.get("city"),
                street_name=alert.get("street_name"),
                road_number=str(road_number) if road_number is not None and road_number != "" else None,
                alert_type=alert.get("alert_type"),
                alert_subtype=alert.get("alert_subtype"),
                severity=alert.get("severity"),
                description=alert.get("description"),
                active=alert.get("active"),
                segment_id=alert.get("segment_id")
            )
        )

    logger.info(f"Loaded {len(alerts_response)} alerts from example data")

    return AlertsResponse(
        alerts=alerts_response,
        total_count=len(alerts_response),
        date_from=date_from,
        date_to=date_to
    )


def get_jams_from_example(
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> JamsResponse:
    """Get traffic jams from example data"""

    jams_data = ExampleDataLoader.get_jams(None, date_from, date_to)

    if street_names:
        jams_data = [j for j in jams_data if j.get("street_name") in street_names]

    jams_response = []
    for jam in jams_data:
        jam_line = jam.get("jam_line_geog")
        road_number = jam.get("road_number")

        jams_response.append(
            JamResponse(
                id=jam.get("id"),
                event_time=jam.get("event_time"),
                first_seen=jam.get("first_seen"),
                last_seen=jam.get("last_seen"),
                jam_line=jam_line,
                city=jam.get("city"),
                street_name=jam.get("street_name"),
                road_number=str(road_number) if road_number is not None and road_number != "" else None,
                delay_seconds=jam.get("delay_seconds"),
                length_m=jam.get("length_m"),
                speed_kmh=jam.get("speed_kmh"),
                speed_normal_kmh=jam.get("speed_normal_kmh"),
                severity=jam.get("severity"),
                segment_id=jam.get("segment_id")
            )
        )

    logger.info(f"Loaded {len(jams_response)} jams from example data")

    return JamsResponse(
        jams=jams_response,
        total_count=len(jams_response),
        date_from=date_from,
        date_to=date_to
    )


def get_restrictions_from_example(
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> RestrictionsResponse:
    """Get restrictions from example data"""

    restrictions_data = ExampleDataLoader.get_restrictions(None, date_from, date_to)

    if street_names:
        restrictions_data = [r for r in restrictions_data if r.get("street_name") in street_names]

    restrictions_response = []
    for restriction in restrictions_data:
        location_point = restriction.get("location_point_geog")
        location_line = restriction.get("location_line_geog")
        road_number = restriction.get("road_number")

        restrictions_response.append(
            RestrictionResponse(
                id=restriction.get("id"),
                event_time=restriction.get("event_time"),
                valid_from=restriction.get("valid_from"),
                valid_to=restriction.get("valid_to"),
                first_seen=restriction.get("first_seen"),
                last_seen=restriction.get("last_seen"),
                location_point=location_point,
                location_line=location_line,
                city=restriction.get("city"),
                street_name=restriction.get("street_name"),
                road_number=str(road_number) if road_number is not None and road_number != "" else None,
                direction=restriction.get("direction"),
                restriction_type=restriction.get("restriction_type"),
                restriction_subtype=restriction.get("restriction_subtype"),
                urgency=restriction.get("urgency"),
                severity=restriction.get("severity"),
                status=restriction.get("status"),
                max_speed_kmh=restriction.get("max_speed_kmh"),
                description_cs=restriction.get("description_cs"),
                segment_id=restriction.get("segment_id")
            )
        )

    logger.info(f"Loaded {len(restrictions_response)} restrictions from example data")

    return RestrictionsResponse(
        restrictions=restrictions_response,
        total_count=len(restrictions_response),
        date_from=date_from,
        date_to=date_to
    )


