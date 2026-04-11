from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Annotated, Optional

from modules.map.schema import StreetSegmentsRequest, StreetSegmentsResponse
from modules.map.service import get_street_segments
from db.connection_to_db import get_db
from core.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/street-segments",
    response_model=StreetSegmentsResponse,
    summary="Get street segments with statistics",
    description="""
    Retrieve road segments for specified streets with event statistics.
    
    If street_names is empty or not provided, returns all road segments.
    
    Returns coordinate polylines for each segment along with counts of:
    - Traffic jams
    - Accidents  
    - Alerts
    - Restrictions
    
    Statistics are calculated for the specified date range.
    
    **Fallback mode**: If database is unavailable, returns example data for testing.
    """,
    responses={
        200: {
            "description": "Successfully retrieved street segments",
            "content": {
                "application/json": {
                    "example": {
                        "segments": [
                            {
                                "id": 8181,
                                "osm_id": 205262250,
                                "name": "Jihlavská",
                                "road_ref": "602",
                                "road_class": "secondary",
                                "city": "Brno",
                                "max_speed": 50,
                                "coordinates": [[16.563631, 49.174137], [16.564209, 49.174157]],
                                "statistics": {
                                    "jams_count": 5,
                                    "accidents_count": 3,
                                    "alerts_count": 2,
                                    "restrictions_count": 1
                                }
                            }
                        ],
                        "total_count": 1,
                        "date_from": "2026-04-01T00:00:00",
                        "date_to": "2026-04-11T23:59:59"
                    }
                }
            }
        },
        422: {"description": "Validation error in request data"},
        500: {"description": "Internal server error"}
    }
)
def get_street_segments_endpoint(
    request: StreetSegmentsRequest,
    db: Annotated[Optional[Session], Depends(get_db)]
) -> StreetSegmentsResponse:
    """
    Get road segments for given street names with event statistics.

    Args:
        request: Request containing street names and date range
        db: Database session (None if unavailable, triggers fallback mode)

    Returns:
        List of road segments with coordinates and statistics
    """

    logger.info(
        f"Street segments request: {len(request.street_names) if request.street_names else 'all'} streets, "
        f"date range: {request.date_from} to {request.date_to}"
    )

    try:
        result = get_street_segments(
            db=db,
            street_names=request.street_names,
            date_from=request.date_from,
            date_to=request.date_to
        )

        logger.info(f"Returning {result.total_count} segments")
        return result

    except Exception as e:
        logger.error(f"Error processing street segments request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve street segments: {str(e)}"
        )

