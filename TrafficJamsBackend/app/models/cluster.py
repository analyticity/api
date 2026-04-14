"""
Models for dangerous road clusters and their accident membership.
"""
from sqlalchemy import (
    Column, Integer, BigInteger, SmallInteger, Float,
    DateTime, String, ForeignKey, Boolean, func
)
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from app.database import Base


class DangerousRoadCluster(Base):
    __tablename__ = "dangerous_road_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # DBSCAN run metadata
    run_id = Column(String(64), nullable=False, index=True)
    dbscan_label = Column(Integer, nullable=False)

    # Clustering parameters
    eps_meters = Column(Float, nullable=False)
    min_samples = Column(Integer, nullable=False)

    # Geometry (all SRID 4326)
    centroid = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    road_point = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    road_segment = Column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=True)
    convex_hull = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)

    # Road identification
    road_name = Column(String(255), nullable=True)
    road_number = Column(String(50), nullable=True)
    road_category = Column(String(50), nullable=True)

    # Severity statistics
    accident_count = Column(Integer, nullable=False, default=0)
    fatalities_total = Column(Integer, nullable=False, default=0)
    serious_injuries_total = Column(Integer, nullable=False, default=0)
    minor_injuries_total = Column(Integer, nullable=False, default=0)
    total_material_damage = Column(BigInteger, nullable=False, default=0)
    severity_score = Column(Float, nullable=False, default=0.0)

    # Bounding box (for fast spatial queries)
    bbox_min_lat = Column(Float, nullable=True)
    bbox_min_lng = Column(Float, nullable=True)
    bbox_max_lat = Column(Float, nullable=True)
    bbox_max_lng = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    is_active = Column(Boolean, nullable=False, default=True)

    cluster_accidents = relationship(
        "ClusterAccident",
        back_populates="cluster",
        cascade="all, delete-orphan",
        lazy="select",
    )


class ClusterAccident(Base):
    """Join table: cluster ↔ accident."""
    __tablename__ = "cluster_accidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_id = Column(
        Integer,
        ForeignKey("dangerous_road_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    accident_id = Column(
        String(50),
        ForeignKey("accidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    distance_to_road_m = Column(Float, nullable=True)

    cluster = relationship("DangerousRoadCluster", back_populates="cluster_accidents")
    accident = relationship("Accident", back_populates="cluster_accidents")
