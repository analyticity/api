"""
Shared domain dataclasses used across repositories and services.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class AccidentPoint:
    """Lightweight accident record used as input to the clustering algorithm."""
    accident_id: str
    lat: float
    lng: float
    fatalities: int = 0
    serious_injuries: int = 0
    minor_injuries: int = 0
    total_material_damage: int = 0
    road_category: Optional[str] = None
    road_number: Optional[str] = None


@dataclass
class SnapResult:
    """Result of snapping a centroid to the nearest road segment."""
    road_point_wkt: Optional[str] = None      # POINT WKT in SRID 4326
    road_segment_wkt: Optional[str] = None    # LINESTRING WKT in SRID 4326
    road_name: Optional[str] = None
    road_ref: Optional[str] = None            # e.g. "I/43", "E55"
    highway: Optional[str] = None             # OSM highway tag e.g. "primary"


@dataclass
class ClusterData:
    """All computed data for one cluster, passed to ClusterRepository for persistence."""
    run_id: str
    dbscan_label: int
    eps_meters: float
    min_samples: int
    centroid_lat: float
    centroid_lng: float
    points: List[AccidentPoint]
    snap: SnapResult
    convex_hull_wkt: Optional[str] = None
