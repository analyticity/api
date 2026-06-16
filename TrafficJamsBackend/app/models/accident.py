"""
SQLAlchemy model for the `accidents` table.
Schema matches the police_data.csv ingestion format.
This is a read-only model — the table is managed externally.
"""
from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, Float, DateTime, Text
)
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from app.database import Base


class Accident(Base):
    __tablename__ = "accidents"

    id = Column(BigInteger, primary_key=True)

    # Time
    event_time = Column(DateTime(timezone=True), nullable=True)
    ingested_at = Column(DateTime(timezone=True), nullable=True)

    # Location
    city = Column(String(100), nullable=True)
    street_name = Column(String(255), nullable=True)
    road_number = Column(String(50), nullable=True)
    road_type_code = Column(String(50), nullable=True)   # e.g. "street"

    # Classification (string labels from the police data source)
    accident_type = Column(String(255), nullable=True)
    accident_subtype = Column(String(255), nullable=True)
    cause_primary = Column(String(255), nullable=True)
    cause_secondary = Column(String(255), nullable=True)
    severity = Column(String(50), nullable=True)          # "property_damage", "injury", …

    # Consequences
    fatalities_count = Column(Integer, nullable=True)
    serious_injuries = Column(Integer, nullable=True)
    minor_injuries = Column(Integer, nullable=True)
    persons_involved = Column(Integer, nullable=True)
    vehicles_involved = Column(Integer, nullable=True)
    damage_czk = Column(BigInteger, nullable=True)
    damage_category = Column(String(50), nullable=True)

    # Conditions (string labels)
    weather_condition = Column(String(255), nullable=True)
    road_surface = Column(String(255), nullable=True)
    light_condition = Column(String(255), nullable=True)
    road_condition = Column(String(255), nullable=True)

    # Driver state
    alcohol_involved = Column(Boolean, nullable=True)
    drugs_involved = Column(Boolean, nullable=True)
    alcohol_level = Column(Float, nullable=True)

    # Quality
    quality_score = Column(Float, nullable=True)

    # Road segment FK (nullable — set when matched to road_segments table)
    segment_id = Column(Integer, nullable=True)

    # Geometry — WGS84 point (SRID 4326), column name matches CSV source
    location_geog = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)

    # Relationship (back-populated from cluster association)
    cluster_accidents = relationship(
        "ClusterAccident",
        back_populates="accident",
        lazy="select",
    )
