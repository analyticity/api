from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Annotated, Optional

from modules.map.schema import (
    StreetSegmentsRequest,
    StreetSegmentsResponse,
    AccidentsRequest,
    AccidentsResponse
)
from modules.map.service import get_street_segments, get_accidents
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


@router.post(
    "/accidents",
    response_model=AccidentsResponse,
    summary="Get accidents with filters",
    description="""
    Retrieve traffic accidents for specified streets and date range.
    
    If street_names is empty or not provided, returns all accidents.
    
    Returns detailed accident information including:
    - Event time and location
    - Accident type and severity
    - Casualties and injuries
    - Weather and road conditions
    - Alcohol/drugs involvement
    
    Accidents are filtered by event_time within the specified date range.
    
    **Fallback mode**: If database is unavailable, returns example data.
    """,
    responses={
        200: {
            "description": "Successfully retrieved accidents",
            "content": {
                "application/json": {
                    "example": {
                        "accidents": [
                            {
                                "id": 1,
                                "event_time": "2026-04-05T14:30:00Z",
                                "location": [[16.563631, 49.174137]],
                                "city": "Brno",
                                "street_name": "Jihlavská",
                                "road_number": "602",
                                "accident_type": "collision",
                                "accident_subtype": "rear_end",
                                "severity": "minor",
                                "fatalities_count": 0,
                                "serious_injuries": 0,
                                "minor_injuries": 2,
                                "persons_involved": 3,
                                "vehicles_involved": 2,
                                "damage_czk": 50000,
                                "weather_condition": "clear",
                                "road_surface": "dry",
                                "light_condition": "daylight",
                                "alcohol_involved": False,
                                "drugs_involved": False,
                                "segment_id": 8181
                            }
                        ],
                        "total_count": 1,
                        "date_from": "2026-04-01T00:00:00Z",
                        "date_to": "2026-04-11T23:59:59Z"
                    }
                }
            }
        },
        422: {"description": "Validation error in request data"},
        500: {"description": "Internal server error"}
    }
)
def get_accidents_endpoint(
    request: AccidentsRequest,
    db: Annotated[Optional[Session], Depends(get_db)]
) -> AccidentsResponse:
    """
    Get accidents for given street names and date range.

    Args:
        request: Request containing street names and date range
        db: Database session (None if unavailable, triggers fallback mode)

    Returns:
        List of accidents with detailed information
    """

    logger.info(
        f"Accidents request: {len(request.street_names) if request.street_names else 'all'} streets, "
        f"date range: {request.date_from} to {request.date_to}"
    )

    try:
        result = get_accidents(
            db=db,
            street_names=request.street_names,
            date_from=request.date_from,
            date_to=request.date_to
        )

        logger.info(f"Returning {result.total_count} accidents")
        return result

    except Exception as e:
        logger.error(f"Error processing accidents request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve accidents: {str(e)}"
        )

