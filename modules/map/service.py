from typing import List, Optional
from sqlalchemy.orm import Session

from modules.map.schema import StreetSegmentsResponse, AccidentsResponse
from modules.map.service_db import get_street_segments_from_db, get_accidents_from_db
from modules.map.service_examples import get_street_segments_from_example, get_accidents_from_example
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
