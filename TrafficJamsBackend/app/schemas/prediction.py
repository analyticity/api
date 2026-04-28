from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """
    All fields are optional.
    Omitted weather fields are fetched from Open-Meteo using the cluster centroid.
    Omitted temporal fields are derived from the server clock.
    """

    weather_condition: Optional[str] = Field(
        None, description="e.g. 'clear', 'rain', 'snow', 'fog'. Fetched from Open-Meteo if omitted."
    )
    road_surface: Optional[str] = Field(
        None, description="e.g. 'dry', 'wet', 'ice'. Derived from weather if omitted."
    )
    light_condition: Optional[str] = Field(
        None, description="e.g. 'daylight', 'dark'. Derived from current hour if omitted."
    )
    road_condition: Optional[str] = Field(
        None, description="e.g. 'normal', 'slippery'. Derived from weather if omitted."
    )


class TemporalFeatures(BaseModel):
    hour: int
    day_of_week: int = Field(..., description="0 = Monday, 6 = Sunday")
    month: int
    is_weekend: bool
    is_night: bool = Field(..., description="True when hour < 6 or hour >= 22")


class WeatherFeatures(BaseModel):
    weather_condition: str
    road_surface: str
    light_condition: str
    road_condition: str
    source: str = Field(..., description="'user' if provided in request, 'api' if fetched from Open-Meteo")


class PredictionResponse(BaseModel):
    cluster_id: int
    evaluated_at: datetime
    temporal: TemporalFeatures
    weather: WeatherFeatures
    danger_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: str = Field(..., description="'low' (< 0.3), 'medium' (0.3–0.6), 'high' (>= 0.6)")
    expected_damage_czk: int = Field(..., description="Predicted material damage in CZK")
    model_trained_at: Optional[str] = Field(None, description="ISO timestamp of last model training")


# ─── Scenario (bulk) prediction ───────────────────────────────────────────────

class ScenarioRequest(BaseModel):
    """
    Bulk prediction request: score every active cluster under a single set of
    environmental conditions. All overrides are optional; omitted fields are
    treated as 'unknown' (no Open-Meteo fetch is performed in scenario mode).
    Optional temporal overrides allow what-if queries such as 'Friday 22:00'.
    """

    weather_condition: Optional[str] = Field(None, description="e.g. 'clear', 'rain', 'snow', 'fog'")
    road_surface: Optional[str] = Field(None, description="e.g. 'dry', 'wet', 'ice'")
    light_condition: Optional[str] = Field(None, description="e.g. 'daylight', 'dark'")
    road_condition: Optional[str] = Field(None, description="e.g. 'normal', 'slippery'")

    hour: Optional[int] = Field(None, ge=0, le=23, description="Hour of day, 0–23")
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="0 = Monday, 6 = Sunday")
    month: Optional[int] = Field(None, ge=1, le=12, description="1 = January, 12 = December")

    min_probability: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Only return clusters whose predicted danger probability is >= this threshold.",
    )
    limit: Optional[int] = Field(
        None, ge=1,
        description="If set, return at most this many highest-probability clusters.",
    )


class ScenarioPredictionItem(BaseModel):
    cluster_id: int
    danger_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: str = Field(..., description="'low', 'medium' or 'high'")
    expected_damage_czk: int


class ScenarioResponse(BaseModel):
    evaluated_at: datetime
    model_trained_at: Optional[str] = None
    temporal: TemporalFeatures
    weather: WeatherFeatures
    total_clusters: int = Field(..., description="Total number of clusters considered")
    returned: int = Field(..., description="Number of items in the response after filtering")
    items: List[ScenarioPredictionItem]
