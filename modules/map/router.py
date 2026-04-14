from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Annotated, Optional
from datetime import datetime

from modules.map.schema import (
    StreetSegmentsRequest,
    StreetSegmentsResponse,
    RoadSegmentByIdResponse,
    AccidentsRequest,
    AccidentsResponse,
    AlertsRequest,
    AlertsResponse,
    JamsRequest,
    JamsResponse,
    RestrictionsRequest,
    RestrictionsResponse
)
from modules.map.service import get_street_segments, get_road_segment_by_id, get_accidents, get_alerts, get_jams, get_restrictions
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


@router.get(
    "/road-segment/{segment_id}",
    response_model=RoadSegmentByIdResponse,
    summary="Get road segment by ID",
    description="""
    Retrieve single road segment by its ID.
    
    Returns road segment details including:
    - OSM ID and metadata
    - Road class and speed limit
    - Coordinate polyline
    - Event statistics (if date range provided)
    
    **Query parameters (optional):**
    - date_from: Start date for statistics calculation
    - date_to: End date for statistics calculation
    
    If date range is not provided, statistics will be empty (all zeros).
    
    **Fallback mode**: If database is unavailable, returns example data.
    """,
    responses={
        200: {
            "description": "Successfully retrieved road segment",
            "content": {
                "application/json": {
                    "example": {
                        "segment": {
                            "id": 8107,
                            "osm_id": 421610453,
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
                    }
                }
            }
        },
        404: {"description": "Road segment not found"},
        500: {"description": "Internal server error"}
    }
)
def get_road_segment_by_id_endpoint(
    segment_id: int,
    db: Annotated[Optional[Session], Depends(get_db)],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> RoadSegmentByIdResponse:
    """
    Get single road segment by ID.

    Args:
        segment_id: Road segment ID
        db: Database session (None if unavailable, triggers fallback mode)
        date_from: Optional start date for statistics
        date_to: Optional end date for statistics

    Returns:
        Road segment with coordinates and statistics
    """

    logger.info(f"Road segment by ID request: {segment_id}, date_range: {date_from} to {date_to}")

    try:
        result = get_road_segment_by_id(
            db=db,
            segment_id=segment_id,
            date_from=date_from,
            date_to=date_to
        )

        if not result:
            logger.warning(f"Road segment {segment_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Road segment with ID {segment_id} not found"
            )

        logger.info(f"Returning segment {segment_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing road segment by ID request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve road segment: {str(e)}"
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


@router.post(
    "/alerts",
    response_model=AlertsResponse,
    summary="Get alerts with filters",
    description="""
    Retrieve traffic alerts for specified streets and date range.
    
    If street_names is empty or not provided, returns all alerts.
    
    Returns detailed alert information including:
    - Alert type and subtype
    - Severity and description
    - Active status
    - Location
    
    Alerts are filtered by first_seen/last_seen overlap with the specified date range.
    
    **Fallback mode**: If database is unavailable, returns example data.
    """,
    responses={
        200: {
            "description": "Successfully retrieved alerts",
            "content": {
                "application/json": {
                    "example": {
                        "alerts": [
                            {
                                "id": 1,
                                "first_seen": "2026-04-05T14:30:00Z",
                                "last_seen": "2026-04-05T16:30:00Z",
                                "location": [[16.563631, 49.174137]],
                                "city": "Brno",
                                "street_name": "Jihlavská",
                                "road_number": "602",
                                "alert_type": "HAZARD",
                                "alert_subtype": "HAZARD_ON_ROAD",
                                "severity": "minor",
                                "description": "Pothole on road",
                                "active": True,
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
def get_alerts_endpoint(
    request: AlertsRequest,
    db: Annotated[Optional[Session], Depends(get_db)]
) -> AlertsResponse:
    """
    Get alerts for given street names and date range.

    Args:
        request: Request containing street names and date range
        db: Database session (None if unavailable, triggers fallback mode)

    Returns:
        List of alerts with detailed information
    """

    logger.info(
        f"Alerts request: {len(request.street_names) if request.street_names else 'all'} streets, "
        f"date range: {request.date_from} to {request.date_to}"
    )

    try:
        result = get_alerts(
            db=db,
            street_names=request.street_names,
            date_from=request.date_from,
            date_to=request.date_to
        )

        logger.info(f"Returning {result.total_count} alerts")
        return result

    except Exception as e:
        logger.error(f"Error processing alerts request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve alerts: {str(e)}"
        )


@router.post(
    "/jams",
    response_model=JamsResponse,
    summary="Get traffic jams with filters",
    description="""
    Retrieve traffic jams for specified streets and date range.
    
    If street_names is empty or not provided, returns all traffic jams.
    
    Returns detailed traffic jam information including:
    - Event time and duration
    - Jam line geometry
    - Delay and speed information
    - Severity level
    
    Jams are filtered by event_time within the specified date range.
    
    **Fallback mode**: If database is unavailable, returns example data.
    """,
    responses={
        200: {
            "description": "Successfully retrieved traffic jams",
            "content": {
                "application/json": {
                    "example": {
                        "jams": [
                            {
                                "id": 1,
                                "event_time": "2026-04-05T14:30:00Z",
                                "first_seen": "2026-04-05T14:30:00Z",
                                "last_seen": "2026-04-05T15:30:00Z",
                                "jam_line": [[16.563631, 49.174137], [16.564209, 49.174157]],
                                "city": "Brno",
                                "street_name": "Jihlavská",
                                "road_number": "602",
                                "delay_seconds": 300,
                                "length_m": 500,
                                "speed_kmh": 15,
                                "speed_normal_kmh": 50,
                                "severity": "moderate",
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
def get_jams_endpoint(
    request: JamsRequest,
    db: Annotated[Optional[Session], Depends(get_db)]
) -> JamsResponse:
    """
    Get traffic jams for given street names and date range.

    Args:
        request: Request containing street names and date range
        db: Database session (None if unavailable, triggers fallback mode)

    Returns:
        List of traffic jams with detailed information
    """

    logger.info(
        f"Jams request: {len(request.street_names) if request.street_names else 'all'} streets, "
        f"date range: {request.date_from} to {request.date_to}"
    )

    try:
        result = get_jams(
            db=db,
            street_names=request.street_names,
            date_from=request.date_from,
            date_to=request.date_to
        )

        logger.info(f"Returning {result.total_count} jams")
        return result

    except Exception as e:
        logger.error(f"Error processing jams request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve jams: {str(e)}"
        )


@router.post(
    "/restrictions",
    response_model=RestrictionsResponse,
    summary="Get restrictions with filters",
    description="""
    Retrieve traffic restrictions for specified streets and date range.
    
    If street_names is empty or not provided, returns all restrictions.
    
    Returns detailed restriction information including:
    - Restriction type and subtype
    - Validity period
    - Location (point or line)
    - Urgency and severity
    - Speed limits
    
    Restrictions are filtered by valid_from/valid_to overlap with the specified date range.
    
    **Fallback mode**: If database is unavailable, returns example data.
    """,
    responses={
        200: {
            "description": "Successfully retrieved restrictions",
            "content": {
                "application/json": {
                    "example": {
                        "restrictions": [
                            {
                                "id": 1,
                                "event_time": "2026-04-05T14:30:00Z",
                                "valid_from": "2026-04-05T00:00:00Z",
                                "valid_to": "2026-04-10T23:59:59Z",
                                "first_seen": "2026-04-05T14:30:00Z",
                                "last_seen": "2026-04-05T14:30:00Z",
                                "location_point": [[16.563631, 49.174137]],
                                "location_line": None,
                                "city": "Brno",
                                "street_name": "Jihlavská",
                                "road_number": "602",
                                "direction": "both",
                                "restriction_type": "ROAD_CLOSED",
                                "restriction_subtype": "ROAD_CLOSED_CONSTRUCTION",
                                "urgency": "high",
                                "severity": "major",
                                "status": "active",
                                "max_speed_kmh": None,
                                "description_cs": "Uzavírka z důvodu stavebních prací",
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
def get_restrictions_endpoint(
    request: RestrictionsRequest,
    db: Annotated[Optional[Session], Depends(get_db)]
) -> RestrictionsResponse:
    """
    Get restrictions for given street names and date range.

    Args:
        request: Request containing street names and date range
        db: Database session (None if unavailable, triggers fallback mode)

    Returns:
        List of restrictions with detailed information
    """

    logger.info(
        f"Restrictions request: {len(request.street_names) if request.street_names else 'all'} streets, "
        f"date range: {request.date_from} to {request.date_to}"
    )

    try:
        result = get_restrictions(
            db=db,
            street_names=request.street_names,
            date_from=request.date_from,
            date_to=request.date_to
        )

        logger.info(f"Returning {result.total_count} restrictions")
        return result

    except Exception as e:
        logger.error(f"Error processing restrictions request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve restrictions: {str(e)}"
        )
