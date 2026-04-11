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
    location: Optional[Polyline] = None
    city: Optional[str] = None
    street_name: Optional[str] = None
    road_number: Optional[str] = None
    accident_type: Optional[str] = None
    accident_subtype: Optional[str] = None
    severity: Optional[str] = None
    fatalities_count: Optional[int] = None
    serious_injuries: Optional[int] = None
    minor_injuries: Optional[int] = None
    persons_involved: Optional[int] = None
    vehicles_involved: Optional[int] = None
    damage_czk: Optional[int] = None
    weather_condition: Optional[str] = None
    road_surface: Optional[str] = None
    light_condition: Optional[str] = None
    alcohol_involved: Optional[bool] = None
    drugs_involved: Optional[bool] = None
    segment_id: Optional[int] = None


class AccidentsResponse(BaseModel):
    accidents: List[AccidentResponse]
    total_count: int
    date_from: datetime
    date_to: datetime

