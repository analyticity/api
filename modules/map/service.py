from typing import List, Optional
from sqlalchemy.orm import Session

from modules.map.schema import StreetSegmentsResponse, RoadSegmentByIdResponse, AccidentsResponse, AlertsResponse, JamsResponse, RestrictionsResponse, EventLinksResponse, NearestStreetResponse
from modules.map.service_db import get_street_segments_from_db, get_road_segment_by_id_from_db, get_accidents_from_db, get_alerts_from_db, get_jams_from_db, get_restrictions_from_db, get_event_links_from_db, get_event_links_by_source_from_db, get_event_links_by_target_from_db, get_nearest_street_from_db
from modules.map.service_examples import (
    get_street_segments_from_example,
    get_road_segment_by_id_from_example,
    get_accidents_from_example,
    get_alerts_from_example,
    get_jams_from_example,
    get_restrictions_from_example,
    get_event_links_from_example,
    get_event_links_by_source_from_example,
    get_event_links_by_target_from_example,
    get_nearest_street_from_example,
)
from core.logging_config import get_logger
from datetime import datetime

logger = get_logger(__name__)


def get_street_segments(
    db: Optional[Session],
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> StreetSegmentsResponse:
    if db is None:
        logger.warning("[segments] db=None, falling back to example data")
        return get_street_segments_from_example(street_names, date_from, date_to)

    logger.info("[segments] db session available, calling DB query")
    try:
        result = get_street_segments_from_db(db, street_names, date_from, date_to)
        logger.info(f"[segments] DB query succeeded, total_count={result.total_count}")
        return result
    except Exception as e:
        logger.error(f"[segments] DB query failed: {e}. Falling back to example data", exc_info=True)
        return get_street_segments_from_example(street_names, date_from, date_to)


def get_road_segment_by_id(
    db: Optional[Session],
    segment_id: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> Optional[RoadSegmentByIdResponse]:
    if db is None:
        logger.warning(f"[segment-by-id] db=None, falling back to example data")
        return get_road_segment_by_id_from_example(segment_id, date_from, date_to)

    logger.info(f"[segment-by-id] db session available, calling DB query for segment_id={segment_id}")
    try:
        result = get_road_segment_by_id_from_db(db, segment_id, date_from, date_to)
        logger.info(f"[segment-by-id] DB query succeeded, found={result is not None}")
        return result
    except Exception as e:
        logger.error(f"[segment-by-id] DB query failed: {e}. Falling back to example data", exc_info=True)
        return get_road_segment_by_id_from_example(segment_id, date_from, date_to)


def get_accidents(
    db: Optional[Session],
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> AccidentsResponse:
    if db is None:
        logger.warning("[accidents] db=None, falling back to example data")
        return get_accidents_from_example(street_names, date_from, date_to)

    logger.info("[accidents] db session available, calling DB query")
    try:
        result = get_accidents_from_db(db, street_names, date_from, date_to)
        logger.info(f"[accidents] DB query succeeded, total_count={result.total_count}")
        return result
    except Exception as e:
        logger.error(f"[accidents] DB query failed: {e}. Falling back to example data", exc_info=True)
        return get_accidents_from_example(street_names, date_from, date_to)


def get_alerts(
    db: Optional[Session],
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> AlertsResponse:
    if db is None:
        logger.warning("[alerts] db=None, falling back to example data")
        return get_alerts_from_example(street_names, date_from, date_to)

    logger.info("[alerts] db session available, calling DB query")
    try:
        result = get_alerts_from_db(db, street_names, date_from, date_to)
        logger.info(f"[alerts] DB query succeeded, total_count={result.total_count}")
        return result
    except Exception as e:
        logger.error(f"[alerts] DB query failed: {e}. Falling back to example data", exc_info=True)
        return get_alerts_from_example(street_names, date_from, date_to)


def get_jams(
    db: Optional[Session],
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> JamsResponse:
    if db is None:
        logger.warning("[jams] db=None, falling back to example data")
        return get_jams_from_example(street_names, date_from, date_to)

    logger.info("[jams] db session available, calling DB query")
    try:
        result = get_jams_from_db(db, street_names, date_from, date_to)
        logger.info(f"[jams] DB query succeeded, total_count={result.total_count}")
        return result
    except Exception as e:
        logger.error(f"[jams] DB query failed: {e}. Falling back to example data", exc_info=True)
        return get_jams_from_example(street_names, date_from, date_to)


def get_restrictions(
    db: Optional[Session],
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> RestrictionsResponse:
    if db is None:
        logger.warning("[restrictions] db=None, falling back to example data")
        return get_restrictions_from_example(street_names, date_from, date_to)

    logger.info("[restrictions] db session available, calling DB query")
    try:
        result = get_restrictions_from_db(db, street_names, date_from, date_to)
        logger.info(f"[restrictions] DB query succeeded, total_count={result.total_count}")
        return result
    except Exception as e:
        logger.error(f"[restrictions] DB query failed: {e}. Falling back to example data", exc_info=True)
        return get_restrictions_from_example(street_names, date_from, date_to)


def get_event_links(
    db: Optional[Session],
    source_type: Optional[str],
    target_type: Optional[str],
    date_from: datetime,
    date_to: datetime
) -> EventLinksResponse:
    if db is None:
        logger.warning("[event-links] db=None, falling back to example data")
        return get_event_links_from_example(source_type, target_type, date_from, date_to)

    logger.info("[event-links] db session available, calling DB query")
    try:
        result = get_event_links_from_db(db, source_type, target_type, date_from, date_to)
        logger.info(f"[event-links] DB query succeeded, total_count={result.total_count}")
        return result
    except Exception as e:
        logger.error(f"[event-links] DB query failed: {e}. Falling back to example data", exc_info=True)
        return get_event_links_from_example(source_type, target_type, date_from, date_to)


def get_event_links_by_source(
    db: Optional[Session],
    source_ids: List[int],
    source_type: Optional[str],
    date_from: datetime,
    date_to: datetime
) -> EventLinksResponse:
    if db is None:
        logger.warning("[event-links-by-source] db=None, falling back to example data")
        return get_event_links_by_source_from_example(source_ids, source_type, date_from, date_to)

    logger.info(f"[event-links-by-source] db session available, calling DB query for source_ids={source_ids}")
    try:
        result = get_event_links_by_source_from_db(db, source_ids, source_type, date_from, date_to)
        logger.info(f"[event-links-by-source] DB query succeeded, total_count={result.total_count}")
        return result
    except Exception as e:
        logger.error(f"[event-links-by-source] DB query failed: {e}. Falling back to example data", exc_info=True)
        return get_event_links_by_source_from_example(source_ids, source_type, date_from, date_to)


def get_nearest_street(
    db: Optional[Session],
    lat: float,
    lon: float,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> Optional[NearestStreetResponse]:
    """Find nearest street segment with automatic fallback to example data."""

    if db is None:
        logger.warning("Database unavailable, using example data fallback")
        return get_nearest_street_from_example(lat, lon, date_from, date_to)

    try:
        return get_nearest_street_from_db(db, lat, lon, date_from, date_to)
    except Exception as e:
        logger.error(f"Database query failed: {e}. Falling back to example data")
        return get_nearest_street_from_example(lat, lon, date_from, date_to)


def get_nearest_street(
    db: Optional[Session],
    lat: float,
    lon: float,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> Optional[NearestStreetResponse]:
    """Find nearest street segment with automatic fallback to example data."""

    if db is None:
        logger.warning("Database unavailable, using example data fallback")
        return get_nearest_street_from_example(lat, lon, date_from, date_to)

    try:
        return get_nearest_street_from_db(db, lat, lon, date_from, date_to)
    except Exception as e:
        logger.error(f"Database query failed: {e}. Falling back to example data")
        return get_nearest_street_from_example(lat, lon, date_from, date_to)


def get_event_links_by_target(
    db: Optional[Session],
    target_ids: List[int],
    target_type: Optional[str],
    date_from: datetime,
    date_to: datetime
) -> EventLinksResponse:
    if db is None:
        logger.warning("[event-links-by-target] db=None, falling back to example data")
        return get_event_links_by_target_from_example(target_ids, target_type, date_from, date_to)

    logger.info(f"[event-links-by-target] db session available, calling DB query for target_ids={target_ids}")
    try:
        result = get_event_links_by_target_from_db(db, target_ids, target_type, date_from, date_to)
        logger.info(f"[event-links-by-target] DB query succeeded, total_count={result.total_count}")
        return result
    except Exception as e:
        logger.error(f"[event-links-by-target] DB query failed: {e}. Falling back to example data", exc_info=True)
        return get_event_links_by_target_from_example(target_ids, target_type, date_from, date_to)
