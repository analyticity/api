from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class StreetSegmentsRequest(BaseModel):
    street_names: List[str] = Field(default=[], description="List of street names to fetch. If empty, returns all segments.")
    date_from: datetime = Field(..., description="Start date for statistics")
    date_to: datetime = Field(..., description="End date for statistics")

    @field_validator('date_from', 'date_to', mode='before')
    @classmethod
    def ensure_timezone_aware(cls, v):
        """Ensure datetime objects are timezone-aware (UTC if not specified)"""
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
        elif isinstance(v, datetime):
            dt = v
        else:
            return v

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        json_schema_extra = {
            "example": {
                "street_names": ["Jihlavská", "Úvoz"],
                "date_from": "2026-04-01T00:00:00Z",
                "date_to": "2026-04-11T23:59:59Z"
            }
        }


Coordinate = List[float]
Polyline = List[Coordinate]


class SegmentStatistics(BaseModel):
    jams_count: int = Field(0, description="Number of traffic jams")
    accidents_count: int = Field(0, description="Number of accidents")
    alerts_count: int = Field(0, description="Number of alerts")
    restrictions_count: int = Field(0, description="Number of restrictions")


class RoadSegmentResponse(BaseModel):
    id: int
    osm_id: Optional[int] = None
    name: Optional[str] = None
    road_ref: Optional[str] = None
    road_class: str
    city: Optional[str] = None
    max_speed: Optional[int] = None
    coordinates: Polyline
    statistics: SegmentStatistics


class StreetSegmentsResponse(BaseModel):
    segments: List[RoadSegmentResponse]
    total_count: int
    date_from: datetime
    date_to: datetime


class RoadSegmentByIdResponse(BaseModel):
    segment: RoadSegmentResponse


class AccidentsRequest(BaseModel):
    street_names: List[str] = Field(default=[], description="List of street names to filter. If empty, returns all accidents.")
    date_from: datetime = Field(..., description="Start date for filtering")
    date_to: datetime = Field(..., description="End date for filtering")

    @field_validator('date_from', 'date_to', mode='before')
    @classmethod
    def ensure_timezone_aware(cls, v):
        """Ensure datetime objects are timezone-aware (UTC if not specified)"""
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
        elif isinstance(v, datetime):
            dt = v
        else:
            return v

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        json_schema_extra = {
            "example": {
                "street_names": ["Jihlavská"],
                "date_from": "2026-04-01T00:00:00Z",
                "date_to": "2026-04-11T23:59:59Z"
            }
        }


class AccidentResponse(BaseModel):
    id: int
    event_time: Optional[datetime] = None
    ingested_at: Optional[datetime] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    location: Optional[Polyline] = None
    city: Optional[str] = None
    street_name: Optional[str] = None
    road_number: Optional[str] = None
    road_type_code: Optional[str] = None
    accident_type: Optional[str] = None
    accident_subtype: Optional[str] = None
    cause_primary: Optional[str] = None
    cause_secondary: Optional[str] = None
    severity: Optional[str] = None
    fatalities_count: Optional[int] = None
    serious_injuries: Optional[int] = None
    minor_injuries: Optional[int] = None
    persons_involved: Optional[int] = None
    vehicles_involved: Optional[int] = None
    damage_czk: Optional[int] = None
    damage_category: Optional[str] = None
    weather_condition: Optional[str] = None
    road_surface: Optional[str] = None
    light_condition: Optional[str] = None
    road_condition: Optional[str] = None
    vehicle_types: Optional[str] = None
    alcohol_involved: Optional[bool] = None
    drugs_involved: Optional[bool] = None
    alcohol_level: Optional[float] = None
    quality_score: Optional[int] = None
    segment_id: Optional[int] = None


class AccidentsResponse(BaseModel):
    accidents: List[AccidentResponse]
    total_count: int
    date_from: datetime
    date_to: datetime


class AlertsRequest(BaseModel):
    street_names: List[str] = Field(default=[], description="List of street names to filter. If empty, returns all alerts.")
    date_from: datetime = Field(..., description="Start date for filtering")
    date_to: datetime = Field(..., description="End date for filtering")

    @field_validator('date_from', 'date_to', mode='before')
    @classmethod
    def ensure_timezone_aware(cls, v):
        """Ensure datetime objects are timezone-aware (UTC if not specified)"""
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
        elif isinstance(v, datetime):
            dt = v
        else:
            return v

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        json_schema_extra = {
            "example": {
                "street_names": [],
                "date_from": "2025-01-01T00:00:00Z",
                "date_to": "2026-12-31T23:59:59Z"
            }
        }


class AlertResponse(BaseModel):
    id: int
    ingested_at: Optional[datetime] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    location: Optional[Polyline] = None
    city: Optional[str] = None
    street_name: Optional[str] = None
    road_number: Optional[str] = None
    road_type_code: Optional[str] = None
    alert_type: Optional[str] = None
    alert_subtype: Optional[str] = None
    severity: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    quality_score: Optional[int] = None
    segment_id: Optional[int] = None


class AlertsResponse(BaseModel):
    alerts: List[AlertResponse]
    total_count: int
    date_from: datetime
    date_to: datetime


class JamsRequest(BaseModel):
    street_names: List[str] = Field(default=[], description="List of street names to filter. If empty, returns all jams.")
    date_from: datetime = Field(..., description="Start date for filtering")
    date_to: datetime = Field(..., description="End date for filtering")

    @field_validator('date_from', 'date_to', mode='before')
    @classmethod
    def ensure_timezone_aware(cls, v):
        """Ensure datetime objects are timezone-aware (UTC if not specified)"""
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
        elif isinstance(v, datetime):
            dt = v
        else:
            return v

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        json_schema_extra = {
            "example": {
                "street_names": [],
                "date_from": "2025-01-01T00:00:00Z",
                "date_to": "2026-12-31T23:59:59Z"
            }
        }


class JamResponse(BaseModel):
    id: int
    event_time: Optional[datetime] = None
    ingested_at: Optional[datetime] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    jam_line: Optional[Polyline] = None
    city: Optional[str] = None
    street_name: Optional[str] = None
    road_number: Optional[str] = None
    road_type_code: Optional[str] = None
    delay_seconds: Optional[float] = None
    length_m: Optional[float] = None
    speed_kmh: Optional[float] = None
    speed_normal_kmh: Optional[float] = None
    severity: Optional[str] = None
    quality_score: Optional[int] = None
    segment_id: Optional[int] = None


class JamsResponse(BaseModel):
    jams: List[JamResponse]
    total_count: int
    date_from: datetime
    date_to: datetime


class RestrictionsRequest(BaseModel):
    street_names: List[str] = Field(default=[], description="List of street names to filter. If empty, returns all restrictions.")
    date_from: datetime = Field(..., description="Start date for filtering")
    date_to: datetime = Field(..., description="End date for filtering")

    @field_validator('date_from', 'date_to', mode='before')
    @classmethod
    def ensure_timezone_aware(cls, v):
        """Ensure datetime objects are timezone-aware (UTC if not specified)"""
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
        elif isinstance(v, datetime):
            dt = v
        else:
            return v

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        json_schema_extra = {
            "example": {
                "street_names": [],
                "date_from": "2025-01-01T00:00:00Z",
                "date_to": "2026-12-31T23:59:59Z"
            }
        }


class RestrictionResponse(BaseModel):
    id: int
    external_version: Optional[int] = None
    event_time: Optional[datetime] = None
    ingested_at: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    location_point: Optional[Polyline] = None
    location_line: Optional[Polyline] = None
    city: Optional[str] = None
    street_name: Optional[str] = None
    road_number: Optional[str] = None
    road_type_code: Optional[str] = None
    km_from: Optional[float] = None
    km_to: Optional[float] = None
    direction: Optional[str] = None
    restriction_type: Optional[str] = None
    restriction_subtype: Optional[str] = None
    urgency: Optional[str] = None
    probability: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    max_speed_kmh: Optional[int] = None
    description_cs: Optional[str] = None
    quality_score: Optional[int] = None
    segment_id: Optional[int] = None


class RestrictionsResponse(BaseModel):
    restrictions: List[RestrictionResponse]
    total_count: int
    date_from: datetime
    date_to: datetime


class EventLinksRequest(BaseModel):
    source_type: Optional[str] = Field(default=None, description="Filter by source type (e.g. 'alert', 'restriction'). If None, returns all.")
    target_type: Optional[str] = Field(default=None, description="Filter by target type (e.g. 'traffic_jam'). If None, returns all.")
    date_from: datetime = Field(..., description="Start date for filtering by created_at")
    date_to: datetime = Field(..., description="End date for filtering by created_at")

    @field_validator('date_from', 'date_to', mode='before')
    @classmethod
    def ensure_timezone_aware(cls, v):
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
        elif isinstance(v, datetime):
            dt = v
        else:
            return v
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        json_schema_extra = {
            "example": {
                "source_type": "alert",
                "target_type": "traffic_jam",
                "date_from": "2026-04-01T00:00:00Z",
                "date_to": "2026-04-30T23:59:59Z"
            }
        }


class EventLinkResponse(BaseModel):
    id: int
    source_type: str
    source_id: int
    target_type: str
    target_id: int
    link_type: str
    confidence: Optional[int] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class EventLinksResponse(BaseModel):
    event_links: List[EventLinkResponse]
    total_count: int
    date_from: datetime
    date_to: datetime


class EventLinksBySourceRequest(BaseModel):
    source_ids: List[int] = Field(..., description="List of source_ids to filter by")
    source_type: Optional[str] = Field(default=None, description="Optional source type filter (e.g. 'alert', 'restriction')")
    date_from: datetime = Field(..., description="Start date for filtering by created_at")
    date_to: datetime = Field(..., description="End date for filtering by created_at")

    @field_validator('date_from', 'date_to', mode='before')
    @classmethod
    def ensure_timezone_aware(cls, v):
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
        elif isinstance(v, datetime):
            dt = v
        else:
            return v
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        json_schema_extra = {
            "example": {
                "source_ids": [8, 74],
                "source_type": "alert",
                "date_from": "2026-04-01T00:00:00Z",
                "date_to": "2026-04-30T23:59:59Z"
            }
        }


class NearestStreetRequest(BaseModel):
    lat: float = Field(..., description="Latitude of the clicked point", ge=-90, le=90)
    lon: float = Field(..., description="Longitude of the clicked point", ge=-180, le=180)
    date_from: Optional[datetime] = Field(default=None, description="Start date for statistics (if omitted, all-time counts are returned)")
    date_to: Optional[datetime] = Field(default=None, description="End date for statistics (if omitted, all-time counts are returned)")

    @field_validator('date_from', 'date_to', mode='before')
    @classmethod
    def ensure_timezone_aware(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
        elif isinstance(v, datetime):
            dt = v
        else:
            return v
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        json_schema_extra = {
            "example": {
                "lat": 49.195,
                "lon": 16.608,
                "date_from": "2026-04-01T00:00:00Z",
                "date_to": "2026-04-30T23:59:59Z"
            }
        }


class NearestStreetResponse(BaseModel):
    street_name: Optional[str] = Field(None, description="Name of the found street")
    city: Optional[str] = Field(None, description="City of the found street")
    segments: List[RoadSegmentResponse] = Field(..., description="All road segments belonging to this street")
    total_count: int = Field(..., description="Total number of segments for this street")
    nearest_segment_id: int = Field(..., description="ID of the segment closest to the clicked point")
    distance_m: float = Field(..., description="Distance in metres from the clicked point to the nearest segment")


class EventLinksByTargetRequest(BaseModel):
    target_ids: List[int] = Field(..., description="List of target_ids to filter by")
    target_type: Optional[str] = Field(default=None, description="Optional target type filter (e.g. 'traffic_jam')")
    date_from: datetime = Field(..., description="Start date for filtering by created_at")
    date_to: datetime = Field(..., description="End date for filtering by created_at")

    @field_validator('date_from', 'date_to', mode='before')
    @classmethod
    def ensure_timezone_aware(cls, v):
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
        elif isinstance(v, datetime):
            dt = v
        else:
            return v
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        json_schema_extra = {
            "example": {
                "target_ids": [283, 26, 28],
                "target_type": "traffic_jam",
                "date_from": "2026-04-01T00:00:00Z",
                "date_to": "2026-04-30T23:59:59Z"
            }
        }

