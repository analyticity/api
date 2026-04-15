from __future__ import annotations

from datetime import datetime
from typing import Optional

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
    accident_type: Optional[str] = Field(
        None, description="Optional accident type hint (e.g. 'collision'). Defaults to 'unknown'."
    )
    cause_primary: Optional[str] = Field(
        None, description="Optional primary cause hint (e.g. 'speed'). Defaults to 'unknown'."
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
