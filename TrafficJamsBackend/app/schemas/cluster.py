from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, model_validator


# ─── Geometry helpers ──────────────────────────────────────────────────────────

def _wkb_to_geojson(wkb_element: Any) -> Optional[dict]:
    """
    Convert a GeoAlchemy2 WKBElement to a GeoJSON-compatible dict.
    Returns None if the element is None or unparseable.
    """
    if wkb_element is None:
        return None
    try:
        from shapely import wkb
        from shapely.geometry import mapping
        geom = wkb.loads(bytes(wkb_element.data))
        return mapping(geom)
    except Exception:
        return None


# ─── Accident summary (used inside cluster detail) ──────────────────────────────

class AccidentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_time: Optional[datetime] = None
    city: Optional[str] = None
    street_name: Optional[str] = None
    fatalities_count: Optional[int] = None
    serious_injuries: Optional[int] = None
    minor_injuries: Optional[int] = None
    damage_czk: Optional[int] = None
    severity: Optional[str] = None
    accident_type: Optional[str] = None
    road_type_code: Optional[str] = None
    weather_condition: Optional[str] = None
    road_surface: Optional[str] = None

    # Lat/lng extracted from location_geog at query time
    lat: Optional[float] = None
    lng: Optional[float] = None


class ClusterAccidentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    accident_id: str
    distance_to_road_m: Optional[float] = None
    accident: Optional[AccidentSummary] = None


# ─── Cluster schemas ────────────────────────────────────────────────────────────

class ClusterBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    dbscan_label: int
    eps_meters: float
    min_samples: int

    accident_count: int
    fatalities_total: int
    serious_injuries_total: int
    minor_injuries_total: int
    total_material_damage: int
    severity_score: float

    road_name: Optional[str] = None
    road_number: Optional[str] = None
    road_category: Optional[str] = None

    bbox_min_lat: Optional[float] = None
    bbox_min_lng: Optional[float] = None
    bbox_max_lat: Optional[float] = None
    bbox_max_lng: Optional[float] = None

    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClusterListItem(ClusterBase):
    """Cluster representation for list endpoints."""

    centroid_geojson: Optional[dict] = None
    road_point_geojson: Optional[dict] = None
    road_segment_geojson: Optional[dict] = None
    convex_hull_geojson: Optional[dict] = None

    @model_validator(mode="before")
    @classmethod
    def extract_geojson(cls, data: Any) -> Any:
        """
        When building from ORM object, convert WKBElements to GeoJSON dicts.
        """
        if hasattr(data, "__dict__") or hasattr(data, "__table__"):
            # ORM object
            obj = data
            result = {}
            for col in obj.__table__.columns:
                result[col.name] = getattr(obj, col.name)
            result["centroid_geojson"] = _wkb_to_geojson(getattr(obj, "centroid", None))
            result["road_point_geojson"] = _wkb_to_geojson(getattr(obj, "road_point", None))
            result["road_segment_geojson"] = _wkb_to_geojson(getattr(obj, "road_segment", None))
            result["convex_hull_geojson"] = _wkb_to_geojson(getattr(obj, "convex_hull", None))
            return result
        return data


class ClusterDetail(ClusterBase):
    """Full cluster with geometry and accident list."""

    centroid_geojson: Optional[dict] = None
    road_point_geojson: Optional[dict] = None
    road_segment_geojson: Optional[dict] = None
    convex_hull_geojson: Optional[dict] = None

    accidents: List[ClusterAccidentItem] = []

    @model_validator(mode="before")
    @classmethod
    def extract_geojson(cls, data: Any) -> Any:
        if hasattr(data, "__table__"):
            obj = data
            result = {}
            for col in obj.__table__.columns:
                result[col.name] = getattr(obj, col.name)
            result["centroid_geojson"] = _wkb_to_geojson(getattr(obj, "centroid", None))
            result["road_point_geojson"] = _wkb_to_geojson(getattr(obj, "road_point", None))
            result["road_segment_geojson"] = _wkb_to_geojson(getattr(obj, "road_segment", None))
            result["convex_hull_geojson"] = _wkb_to_geojson(getattr(obj, "convex_hull", None))

            # Build accident list from relationship
            cluster_accidents = getattr(obj, "cluster_accidents", [])
            accident_items = []
            for ca in cluster_accidents:
                acc = ca.accident
                acc_dict = None
                if acc is not None:
                    acc_dict = {col.name: getattr(acc, col.name) for col in acc.__table__.columns if col.name != "location_geog"}
                    # Extract lat/lng from location_geog
                    geojson = _wkb_to_geojson(getattr(acc, "location_geog", None))
                    if geojson and geojson.get("type") == "Point":
                        coords = geojson.get("coordinates", [])
                        if len(coords) >= 2:
                            acc_dict["lng"] = coords[0]
                            acc_dict["lat"] = coords[1]
                accident_items.append({
                    "accident_id": ca.accident_id,
                    "distance_to_road_m": ca.distance_to_road_m,
                    "accident": acc_dict,
                })
            result["accidents"] = accident_items
            return result
        return data


# ─── Clustering run request/response ───────────────────────────────────────────

class ClusterRunRequest(BaseModel):
    eps_meters: float = 30.0
    min_samples: int = 3
    # Optional filters for accidents to cluster
    region: Optional[int] = None
    district: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    # If True, delete previous clusters for same parameters before saving
    replace_existing: bool = False


class ClusterRunResponse(BaseModel):
    run_id: str
    clusters_created: int
    accidents_processed: int
    noise_points: int
    eps_meters: float
    min_samples: int
    duration_seconds: float


# ─── List response with pagination ─────────────────────────────────────────────

class ClusterListResponse(BaseModel):
    items: List[ClusterListItem]
