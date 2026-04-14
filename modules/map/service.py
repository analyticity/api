from typing import List, Optional
from sqlalchemy.orm import Session

from modules.map.schema import StreetSegmentsResponse, RoadSegmentByIdResponse, AccidentsResponse, AlertsResponse, JamsResponse, RestrictionsResponse
from modules.map.service_db import get_street_segments_from_db, get_road_segment_by_id_from_db, get_accidents_from_db, get_alerts_from_db, get_jams_from_db, get_restrictions_from_db
from modules.map.service_examples import get_street_segments_from_example, get_road_segment_by_id_from_example, get_accidents_from_example, get_alerts_from_example, get_jams_from_example, get_restrictions_from_example
from core.logging_config import get_logger
from datetime import datetime

logger = get_logger(__name__)


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


def get_road_segment_by_id(
    db: Optional[Session],
    segment_id: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> Optional[RoadSegmentByIdResponse]:
    """Get single road segment by ID with automatic fallback to example data"""

    if db is None:
        logger.warning("Database unavailable, using example data fallback")
        return get_road_segment_by_id_from_example(segment_id, date_from, date_to)

    try:
        return get_road_segment_by_id_from_db(db, segment_id, date_from, date_to)
    except Exception as e:
        logger.error(f"Database query failed: {e}. Falling back to example data")
        return get_road_segment_by_id_from_example(segment_id, date_from, date_to)


def get_accidents(
    db: Optional[Session],
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> AccidentsResponse:
    """Get accidents with automatic fallback to example data"""

    if db is None:
        logger.warning("Database unavailable, using example data fallback")
        return get_accidents_from_example(street_names, date_from, date_to)

    try:
        return get_accidents_from_db(db, street_names, date_from, date_to)
    except Exception as e:
        logger.error(f"Database query failed: {e}. Falling back to example data")
        return get_accidents_from_example(street_names, date_from, date_to)


def get_alerts(
    db: Optional[Session],
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> AlertsResponse:
    """Get alerts with automatic fallback to example data"""

    if db is None:
        logger.warning("Database unavailable, using example data fallback")
        return get_alerts_from_example(street_names, date_from, date_to)

    try:
        return get_alerts_from_db(db, street_names, date_from, date_to)
    except Exception as e:
        logger.error(f"Database query failed: {e}. Falling back to example data")
        return get_alerts_from_example(street_names, date_from, date_to)


def get_jams(
    db: Optional[Session],
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> JamsResponse:
    """Get traffic jams with automatic fallback to example data"""

    if db is None:
        logger.warning("Database unavailable, using example data fallback")
        return get_jams_from_example(street_names, date_from, date_to)

    try:
        return get_jams_from_db(db, street_names, date_from, date_to)
    except Exception as e:
        logger.error(f"Database query failed: {e}. Falling back to example data")
        return get_jams_from_example(street_names, date_from, date_to)


def get_restrictions(
    db: Optional[Session],
    street_names: List[str],
    date_from: datetime,
    date_to: datetime
) -> RestrictionsResponse:
    """Get restrictions with automatic fallback to example data"""

    if db is None:
        logger.warning("Database unavailable, using example data fallback")
        return get_restrictions_from_example(street_names, date_from, date_to)

    try:
        return get_restrictions_from_db(db, street_names, date_from, date_to)
    except Exception as e:
        logger.error(f"Database query failed: {e}. Falling back to example data")
        return get_restrictions_from_example(street_names, date_from, date_to)


