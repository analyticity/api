"""
Abstract repository interfaces.

Implement these to plug in different data sources (PostgreSQL, CSV, etc.)
without changing the clustering service or router logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, TYPE_CHECKING

from app.domain import AccidentPoint, SnapResult, ClusterData

if TYPE_CHECKING:
    from app.schemas.cluster import ClusterRunRequest


class AccidentRepository(ABC):
    """Provides accident data to the clustering pipeline."""

    @abstractmethod
    async def get_accident_points(
        self,
        request: "ClusterRunRequest",
    ) -> List[AccidentPoint]:
        """
        Return accident points to be clustered.
        Implementations may apply date filters from *request*.
        """
        ...


class RoadSegmentRepository(ABC):
    """Provides road-snapping capability."""

    @abstractmethod
    async def snap_to_road(
        self,
        lat: float,
        lng: float,
        max_distance_m: float,
    ) -> SnapResult:
        """
        Find the nearest road segment within *max_distance_m* metres.
        Returns an empty SnapResult if no road is found.
        """
        ...


class ClusterRepository(ABC):
    """Handles all cluster persistence operations."""

    @abstractmethod
    async def compute_convex_hull(self, points: List[AccidentPoint]) -> Optional[str]:
        """Return convex hull WKT (SRID 4326) for the given accident points, or None."""
        ...

    @abstractmethod
    async def save_cluster(self, data: ClusterData) -> None:
        """Persist a cluster and its accident memberships."""
        ...

    @abstractmethod
    async def delete_by_params(self, eps_meters: float, min_samples: int) -> None:
        """Delete existing clusters matching the given DBSCAN parameters."""
        ...

    @abstractmethod
    async def list_clusters(self) -> List[dict]:
        """Return all active clusters as plain dicts (ready for ClusterListItem validation)."""
        ...

    @abstractmethod
    async def get_cluster(self, cluster_id: int) -> Optional[dict]:
        """Return a single cluster as a plain dict (ready for ClusterDetail), or None if not found."""
        ...

    @abstractmethod
    async def list_accidents(
        self,
        cluster_id: int,
        page: int,
        page_size: int,
    ) -> Optional[tuple[int, List[dict]]]:
        """
        Return (total_count, page_items) for accidents in a cluster.
        Returns None when the cluster_id does not exist.
        """
        ...
