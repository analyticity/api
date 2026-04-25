"""
PredictionService — loads trained RandomForest models and runs inference.

Models are loaded once at application startup (via lifespan) and held as
class-level attributes, so every request reuses the same in-memory objects.

Weather is fetched from Open-Meteo (free, no API key) when not supplied by
the caller.  All temporal features are always derived server-side from the
current UTC clock.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import httpx
import joblib
import numpy as np
import pandas as pd

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Feature column order must match scripts/train_model.py exactly.
_CATEGORICAL_FEATURES = [
    "road_type_code",
    "weather_condition",
    "road_surface",
    "light_condition",
    "road_condition",
    "accident_type",
    "cause_primary",
]
_NUMERIC_FEATURES = [
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "is_night",
    "road_number_int",
]
_ALL_FEATURES = _CATEGORICAL_FEATURES + _NUMERIC_FEATURES


# ─── WMO weather-code helpers ─────────────────────────────────────────────────

def _wmo_to_condition(code: int) -> str:
    """Map a WMO weather interpretation code to a readable label."""
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 67:
        return "rain"
    if 71 <= code <= 77:
        return "snow"
    if 80 <= code <= 82:
        return "rain"
    if 85 <= code <= 86:
        return "snow"
    if 95 <= code <= 99:
        return "thunderstorm"
    return "unknown"


def _derive_road_conditions(weather_condition: str, precipitation: float) -> tuple[str, str]:
    """Return (road_surface, road_condition) derived from weather."""
    if weather_condition == "snow":
        return "ice", "slippery"
    if weather_condition in ("rain", "thunderstorm") or precipitation > 0:
        return "wet", "slippery"
    if weather_condition == "fog":
        return "unknown", "reduced_visibility"
    return "dry", "normal"


def _parse_road_number(road_number: Optional[str]) -> Optional[float]:
    if not road_number:
        return None
    match = re.search(r"(\d+)", str(road_number))
    return float(match.group(1)) if match else None


# ─── Open-Meteo weather fetch ─────────────────────────────────────────────────

async def _fetch_weather(cluster: dict) -> dict:
    """
    Fetch current weather for the cluster centroid from Open-Meteo.
    Returns a dict with weather_condition, road_surface, road_condition.
    Returns an empty dict on any network or parse failure so the caller
    can fall back to 'unknown' without crashing.
    """
    centroid = cluster.get("centroid_geojson") or {}
    coords = centroid.get("coordinates", [])
    if len(coords) < 2:
        logger.warning("_fetch_weather: cluster has no centroid coordinates")
        return {}

    lng, lat = coords[0], coords[1]
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lng}"
        f"&current=weather_code,precipitation"
        f"&timezone=auto"
    )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("_fetch_weather: Open-Meteo request failed — %s", exc)
        return {}

    current = data.get("current", {})
    wmo_code = int(current.get("weather_code", 0))
    precipitation = float(current.get("precipitation", 0.0))

    weather_condition = _wmo_to_condition(wmo_code)
    road_surface, road_condition = _derive_road_conditions(weather_condition, precipitation)

    return {
        "weather_condition": weather_condition,
        "road_surface": road_surface,
        "road_condition": road_condition,
    }



# ─── Service ──────────────────────────────────────────────────────────────────

class PredictionService:
    """
    Singleton that holds the two trained pipelines in memory.
    Call PredictionService.load() once at application startup.
    """

    _clf = None
    _reg = None
    _metadata: dict = {}

    @classmethod
    def load(cls) -> None:
        """Load classifier.joblib, regressor.joblib, and metadata.json from models_dir."""
        models_dir = Path(settings.models_dir)
        clf_path = models_dir / "classifier.joblib"
        reg_path = models_dir / "regressor.joblib"
        meta_path = models_dir / "metadata.json"

        if not clf_path.exists() or not reg_path.exists():
            logger.warning(
                "PredictionService: model files not found in %s — "
                "run scripts/train_model.py first. /api/prediction will return 503.",
                models_dir,
            )
            return

        cls._clf = joblib.load(clf_path)
        cls._reg = joblib.load(reg_path)
        if meta_path.exists():
            cls._metadata = json.loads(meta_path.read_text())

        logger.info(
            "PredictionService: models loaded from %s (trained at %s)",
            models_dir,
            cls._metadata.get("trained_at", "unknown"),
        )

    @classmethod
    def is_ready(cls) -> bool:
        return cls._clf is not None and cls._reg is not None

    @classmethod
    async def predict_for_cluster(
        cls,
        cluster: dict,
        weather_condition: Optional[str],
        road_surface: Optional[str],
        light_condition: Optional[str],
        road_condition: Optional[str],
        accident_type: Optional[str],
        cause_primary: Optional[str],
    ) -> dict:
        """
        Build the feature row from temporal + weather context, run both models,
        and return a result dict that maps directly onto PredictionResponse.
        """
        # ── Temporal features (always from server clock) ──────────────────────
        now = datetime.now(timezone.utc)
        hour = now.hour
        day_of_week = now.weekday()
        month = now.month
        is_weekend = int(day_of_week >= 5)
        is_night = int(hour < 6 or hour >= 22)

        # ── Weather features ──────────────────────────────────────────────────
        weather_source = "user"
        if weather_condition is None:
            fetched = await _fetch_weather(cluster)
            weather_condition = fetched.get("weather_condition", "unknown")
            if road_surface is None:
                road_surface = fetched.get("road_surface", "unknown")
            if road_condition is None:
                road_condition = fetched.get("road_condition", "unknown")
            weather_source = "api"

        # Derive remaining condition fields from what we now know
        if light_condition is None:
            light_condition = "dark" if is_night else "daylight"
        if road_surface is None:
            road_surface = "unknown"
        if road_condition is None:
            road_condition = "unknown"

        # ── Road features from cluster ────────────────────────────────────────
        road_type_code = cluster.get("road_category") or "unknown"
        road_number_int = _parse_road_number(cluster.get("road_number"))

        # ── Feature DataFrame (column order must match train_model.py) ────────
        row = pd.DataFrame([{
            "road_type_code":    road_type_code,
            "weather_condition": weather_condition,
            "road_surface":      road_surface,
            "light_condition":   light_condition,
            "road_condition":    road_condition,
            "accident_type":     accident_type or "unknown",
            "cause_primary":     cause_primary or "unknown",
            "hour":              hour,
            "day_of_week":       day_of_week,
            "month":             month,
            "is_weekend":        is_weekend,
            "is_night":          is_night,
            "road_number_int":   road_number_int,
        }])

        # ── Inference ─────────────────────────────────────────────────────────
        danger_prob = float(cls._clf.predict_proba(row)[0][1])
        expected_damage = float(np.expm1(cls._reg.predict(row)[0]))
        risk_level = "high" if danger_prob >= 0.6 else "medium" if danger_prob >= 0.3 else "low"

        return {
            "cluster_id": cluster["id"],
            "evaluated_at": now,
            "temporal": {
                "hour": hour,
                "day_of_week": day_of_week,
                "month": month,
                "is_weekend": bool(is_weekend),
                "is_night": bool(is_night),
            },
            "weather": {
                "weather_condition": weather_condition,
                "road_surface":      road_surface,
                "light_condition":   light_condition,
                "road_condition":    road_condition,
                "source":            weather_source,
            },
            "danger_probability":  round(danger_prob, 4),
            "risk_level":          risk_level,
            "expected_damage_czk": int(expected_damage),
            "model_trained_at":    cls._metadata.get("trained_at"),
        }

    @classmethod
    def predict_scenario(
        cls,
        clusters: List[dict],
        weather_condition: Optional[str],
        road_surface: Optional[str],
        light_condition: Optional[str],
        road_condition: Optional[str],
        accident_type: Optional[str],
        cause_primary: Optional[str],
        hour: Optional[int],
        day_of_week: Optional[int],
        month: Optional[int],
    ) -> dict:
        """
        Score every cluster under a single shared environmental scenario.
        No Open-Meteo calls are made; missing fields default to 'unknown'.
        Builds a single DataFrame and runs both pipelines in one batch call.
        """
        now = datetime.now(timezone.utc)
        eff_hour = hour if hour is not None else now.hour
        eff_dow = day_of_week if day_of_week is not None else now.weekday()
        eff_month = month if month is not None else now.month
        is_weekend = int(eff_dow >= 5)
        is_night = int(eff_hour < 6 or eff_hour >= 22)

        eff_weather = weather_condition or "unknown"
        eff_surface = road_surface or "unknown"
        eff_light = light_condition or ("dark" if is_night else "daylight")
        eff_road_cond = road_condition or "unknown"
        eff_accident = accident_type or "unknown"
        eff_cause = cause_primary or "unknown"

        rows = []
        cluster_ids: List[int] = []
        for c in clusters:
            cluster_ids.append(int(c["id"]))
            rows.append({
                "road_type_code":    c.get("road_category") or "unknown",
                "weather_condition": eff_weather,
                "road_surface":      eff_surface,
                "light_condition":   eff_light,
                "road_condition":    eff_road_cond,
                "accident_type":     eff_accident,
                "cause_primary":     eff_cause,
                "hour":              eff_hour,
                "day_of_week":       eff_dow,
                "month":             eff_month,
                "is_weekend":        is_weekend,
                "is_night":          is_night,
                "road_number_int":   _parse_road_number(c.get("road_number")),
            })

        df = pd.DataFrame(rows)
        probs = cls._clf.predict_proba(df)[:, 1]
        damages = np.expm1(cls._reg.predict(df))

        items = []
        for cid, p, d in zip(cluster_ids, probs, damages):
            risk = "high" if p >= 0.6 else "medium" if p >= 0.3 else "low"
            items.append({
                "cluster_id":          cid,
                "danger_probability":  round(float(p), 4),
                "risk_level":          risk,
                "expected_damage_czk": int(d),
            })

        return {
            "evaluated_at": now,
            "model_trained_at": cls._metadata.get("trained_at"),
            "temporal": {
                "hour": eff_hour,
                "day_of_week": eff_dow,
                "month": eff_month,
                "is_weekend": bool(is_weekend),
                "is_night": bool(is_night),
            },
            "weather": {
                "weather_condition": eff_weather,
                "road_surface":      eff_surface,
                "light_condition":   eff_light,
                "road_condition":    eff_road_cond,
                "source":            "user",
            },
            "items": items,
        }
